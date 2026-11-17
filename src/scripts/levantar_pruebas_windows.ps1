param(
  [int]$BackendPort = 5000,
  [int]$FrontendPort = 5173,
  [string]$AdminEmail = "usuario@example.invalid",
  [string]$AdminName = "Administrador",
  [string]$AdminPassword = "REEMPLAZAR_SECRETO_LOCAL",
  [switch]$SkipInstall,
  [switch]$SkipAdmin,
  [switch]$SkipSeleniumCheck,
  [switch]$KillPorts,
  [switch]$UseSqlite,
  [switch]$NoBrowser,
  [Alias("?")]
  [switch]$Help
)

$ErrorActionPreference = "Stop"

# PowerShell necesita estas extensiones para ejecutar Python y npm como comandos.
# Completa el entorno de este proceso si PATHEXT fue sobrescrito en Windows.
$commandExtensions = @($env:PATHEXT -split ';' | Where-Object { $_ })
foreach ($extension in @('.COM', '.EXE', '.BAT', '.CMD')) {
  if ($commandExtensions -notcontains $extension) {
    $commandExtensions += $extension
  }
}
$env:PATHEXT = $commandExtensions -join ';'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$LogDir = Join-Path $RootDir ".logs"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$StorageDir = Join-Path $RootDir "almacenamiento"
$NpmExe = $null

if ($Help) {
  Write-Host "Uso:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\levantar_pruebas_windows.ps1 [opciones]"
  Write-Host ""
  Write-Host "Opciones:"
  Write-Host "  -UseSqlite    Usa SQLite local en almacenamiento\calidad_web_dev.db y no requiere PostgreSQL."
  Write-Host "  -KillPorts     Libera los puertos del backend y frontend antes de arrancar."
  Write-Host "  -SkipInstall   Omite instalacion/verificacion de dependencias."
  Write-Host "  -SkipAdmin     No crea/verifica el administrador de prueba."
  Write-Host "  -SkipSeleniumCheck Omite la verificacion previa de Chrome/Selenium."
  Write-Host "  -BackendPort   Puerto del backend. Default: 5000."
  Write-Host "  -FrontendPort  Puerto preferido del frontend. Default: 5173; busca otro si Windows lo bloquea."
  Write-Host "  -NoBrowser     No abre el portal web al terminar."
  Write-Host ""
  Write-Host "Credenciales por defecto:"
  Write-Host "  usuario@example.invalid / REEMPLAZAR_SECRETO_LOCAL"
  exit 0
}

function Write-Step($Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-PortPids([int]$Port) {
  try {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
      Select-Object -ExpandProperty OwningProcess |
      Sort-Object -Unique
    return
  } catch {
    $netstatPath = Join-Path $env:SystemRoot "System32\netstat.exe"
    if (Test-Path $netstatPath) {
      $lines = & $netstatPath -ano | Select-String ":$Port\s+.*LISTENING"
      $lines | ForEach-Object {
        $parts = ($_ -replace "\s+", " ").Trim().Split(" ")
        $parts[-1]
      } | Sort-Object -Unique
    }
  }
}

function Clear-Port([int]$Port, [string]$Name) {
  $pids = @(Get-PortPids $Port)
  if ($pids.Count -eq 0) {
    return
  }

  if (-not $KillPorts) {
    throw "El puerto $Port ($Name) ya esta en uso por PID(s): $($pids -join ', '). Cierra ese proceso o ejecuta con -KillPorts."
  }

  Write-Step "Liberando puerto $Port para $Name"
  foreach ($pidValue in $pids) {
    taskkill /PID $pidValue /F | Out-Null
  }
}

function Test-HttpOk([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Wait-Url([string]$Url, [int]$Seconds, [string]$Name) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpOk $Url) {
      Write-Host "$Name disponible: $Url" -ForegroundColor Green
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "$Name no respondio en $Url despues de $Seconds segundos. Revisa los logs en $LogDir."
}

function Ensure-PortReusableOrFree([int]$Port, [string]$Name, [string]$ProbeUrl) {
  $pids = @(Get-PortPids $Port)
  if ($pids.Count -eq 0) {
    return $false
  }
  if (Test-HttpOk $ProbeUrl) {
    Write-Host "$Name ya responde en $ProbeUrl. Se reutilizara; no se abre otra instancia." -ForegroundColor Yellow
    return $true
  }
  Clear-Port $Port $Name
  return $false
}

function Resolve-FrontendPort([int]$PreferredPort) {
  # Windows puede reservar puertos sin que aparezca un proceso escuchando.
  # Vite no puede usarlos aunque Get-NetTCPConnection indique que estan libres.
  $lastPort = [Math]::Min($PreferredPort + 200, 65535)
  for ($candidate = $PreferredPort; $candidate -le $lastPort; $candidate++) {
    if ($candidate -eq $BackendPort) {
      continue
    }
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
    try {
      $listener.Start()
      return $candidate
    } catch [System.Net.Sockets.SocketException] {
      if ($_.Exception.SocketErrorCode -eq [System.Net.Sockets.SocketError]::AddressAlreadyInUse) {
        # Conserva la comprobacion existente para reutilizar servicios activos.
        return $candidate
      }
      if ($_.Exception.SocketErrorCode -ne [System.Net.Sockets.SocketError]::AccessDenied) {
        throw
      }
    } finally {
      $listener.Stop()
    }
  }
  throw "Windows no permite usar los puertos $PreferredPort a $lastPort. Indica otro con -FrontendPort."
}

function Ensure-Npm {
  if ($script:NpmExe) {
    return
  }

  $npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
  if (-not $npmCommand) {
    $npmCommand = Get-Command "npm" -ErrorAction SilentlyContinue
  }
  if (-not $npmCommand) {
    $npmPath = Join-Path $env:ProgramFiles "nodejs\npm.cmd"
    if (Test-Path $npmPath) {
      $script:NpmExe = $npmPath
      return
    }
    throw "No encontre npm. Instala Node.js LTS y vuelve a ejecutar el script."
  }
  $script:NpmExe = $npmCommand.Source
}

function Ensure-BackendEnv {
  if (-not (Test-Path $PythonExe)) {
    Write-Step "Creando entorno virtual del backend"
    $pythonLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
      & $pythonLauncher.Source -3 -m venv (Join-Path $BackendDir ".venv")
    } else {
      $python = Get-Command "python" -ErrorAction SilentlyContinue
      if (-not $python) {
        throw "No encontre Python. Instala Python 3.12 o compatible y agregalo al PATH."
      }
      & $python.Source -m venv (Join-Path $BackendDir ".venv")
    }
  }

  if (-not $SkipInstall) {
    & $PythonExe -c "import flask, flask_migrate, flask_sqlalchemy, flask_jwt_extended" 2>$null
    if ($LASTEXITCODE -ne 0) {
      Write-Step "Instalando dependencias del backend"
      & $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")
    }
  }
}

function Ensure-FrontendEnv {
  if ($SkipInstall) {
    return
  }
  Ensure-Npm
  if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Step "Instalando dependencias del frontend"
    Push-Location $FrontendDir
    & $NpmExe install
    Pop-Location
  }
}

function Test-SeleniumChrome {
  Write-Step "Verificando Selenium con Chrome o Chromium"
  $seleniumCheck = @"
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=800,600")
driver = webdriver.Chrome(options=options)
try:
    driver.get("data:text/html,<title>selenium-ok</title>")
    assert "selenium-ok" in driver.title
finally:
    driver.quit()
print("Selenium Chrome OK")
"@
  Push-Location $BackendDir
  $seleniumCheck | & $PythonExe -
  $code = $LASTEXITCODE
  Pop-Location
  if ($code -ne 0) {
    throw "Selenium no pudo abrir Chrome/Chromium. Instala Google Chrome o Chromium actualizado y verifica que el entorno Python tenga selenium."
  }
}

function Invoke-BackendCommand([string[]]$Arguments) {
  Push-Location $BackendDir
  & $PythonExe @Arguments
  Pop-Location
}

function Ensure-Admin {
  if ($SkipAdmin) {
    return
  }

  Write-Step "Verificando administrador de prueba"
  $adminScript = @"
from werkzeug.security import generate_password_hash

from aplicacion import crear_aplicacion
from aplicacion.extensiones import db
from aplicacion.modelos import Rol, Usuario

correo = "$AdminEmail".lower()
nombre = "$AdminName"
contrasena = "$AdminPassword"

app = crear_aplicacion()
with app.app_context():
    rol = Rol.query.filter_by(nombre="administrador").first()
    if rol is None:
        rol = Rol(nombre="administrador", descripcion="Gestion completa de la plataforma")
        db.session.add(rol)
    usuario = Usuario.query.filter_by(correo=correo).first()
    if usuario is None:
        usuario = Usuario(
            nombre=nombre,
            correo=correo,
            contrasena_hash=generate_password_hash(contrasena),
            activo=True,
            roles=[rol],
        )
        db.session.add(usuario)
        db.session.commit()
        print(f"Administrador creado: {correo}")
    else:
        print(f"Administrador existente: {correo}")
"@
  Push-Location $BackendDir
  $adminScript | & $PythonExe -
  Pop-Location
}

function Test-PidFileAlive([string]$PidPath) {
  if (-not (Test-Path $PidPath)) {
    return $false
  }
  $pidValue = Get-Content $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $pidValue) {
    return $false
  }
  return [bool](Get-Process -Id $pidValue -ErrorAction SilentlyContinue)
}

function Remove-StalePidFile([string]$PidPath) {
  if ((Test-Path $PidPath) -and -not (Test-PidFileAlive $PidPath)) {
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
  }
}

function Test-CommandLineRunning([string]$Fragment) {
  if (-not $Fragment) {
    return $true
  }
  $escaped = $Fragment -replace "\\", "\\"
  $matches = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like "python*.exe" -and $_.CommandLine -and $_.CommandLine -like "*$escaped*"
  })
  return $matches.Count -gt 0
}

function Start-LoggedProcess([string]$Name, [string]$WorkingDirectory, [string]$FilePath, [string[]]$Arguments, [string]$LogPath, [string]$PidPath, [string]$ExpectedCommandFragment = "") {
  Remove-StalePidFile $PidPath
  if (Test-PidFileAlive $PidPath) {
    $pidValue = Get-Content $PidPath | Select-Object -First 1
    if ($ExpectedCommandFragment -and -not (Test-CommandLineRunning $ExpectedCommandFragment)) {
      Write-Host "$Name tenia PID registrado ($pidValue), pero el proceso real no esta activo. Se iniciara nuevamente." -ForegroundColor Yellow
      Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
      Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    } else {
    Write-Host "$Name ya esta registrado como activo en PID $pidValue. Se reutilizara."
    return
    }
  }
  $logParent = Split-Path -Parent $LogPath
  if ($logParent) {
    New-Item -ItemType Directory -Force -Path $logParent | Out-Null
  }
  $failurePath = "$PidPath.error"
  Remove-Item $failurePath -Force -ErrorAction SilentlyContinue
  $quote = {
    param([string]$Value)
    "'" + ($Value -replace "'", "''") + "'"
  }
  $argumentLine = ($Arguments | ForEach-Object { & $quote $_ }) -join " "
  $command = @"
Set-Location -LiteralPath $(& $quote $WorkingDirectory)
try {
  & $(& $quote $FilePath) $argumentLine *> $(& $quote $LogPath)
  `$code = if (`$null -eq `$LASTEXITCODE) { 0 } else { `$LASTEXITCODE }
  if (`$code -ne 0) {
    Set-Content -Path $(& $quote $failurePath) -Value "$Name termino inmediatamente con codigo `$code. Revisa $LogPath"
    exit `$code
  }
} catch {
  Set-Content -Path $(& $quote $failurePath) -Value "$Name no pudo iniciar: `$(`$_.Exception.Message). Revisa $LogPath"
  exit 1
}
"@
  $process = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command -WindowStyle Normal -PassThru
  Set-Content -Path $PidPath -Value $process.Id
  Start-Sleep -Seconds 2
  if (Test-Path $failurePath) {
    $message = Get-Content $failurePath -Raw
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
    throw $message
  }
  if (-not (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
    throw "$Name termino inmediatamente durante el arranque. Revisa $LogPath"
  }
  Write-Host "$Name iniciado. PID ventana: $($process.Id). Log consola: $LogPath"
}

$selectedFrontendPort = Resolve-FrontendPort $FrontendPort
if ($selectedFrontendPort -ne $FrontendPort) {
  Write-Host "Windows bloquea el puerto $FrontendPort. Se usara el puerto $selectedFrontendPort para el frontend." -ForegroundColor Yellow
  $FrontendPort = $selectedFrontendPort
}

$env:ENTORNO_APLICACION = if ($env:ENTORNO_APLICACION) { $env:ENTORNO_APLICACION } else { "desarrollo" }
$env:CLAVE_SESION = if ($env:CLAVE_SESION) { $env:CLAVE_SESION } else { "clave-local-desarrollo-cambiala" }
$env:CLAVE_JWT = if ($env:CLAVE_JWT) { $env:CLAVE_JWT } else { "clave-jwt-local-desarrollo-cambiala" }
$env:CLAVE_CIFRADO_SECRETOS = if ($env:CLAVE_CIFRADO_SECRETOS) { $env:CLAVE_CIFRADO_SECRETOS } else { "clave-local-de-cifrado-minimo-32-bytes" }
$env:ORIGEN_FRONTEND_PERMITIDO = "http://localhost:$FrontendPort"
$env:URL_PUBLICA_BACKEND = "http://localhost:$BackendPort"
$env:URL_PUBLICA_FRONTEND = "http://localhost:$FrontendPort"
$env:RUTA_EVIDENCIAS = if ($env:RUTA_EVIDENCIAS) { $env:RUTA_EVIDENCIAS } else { Join-Path $RootDir "almacenamiento\evidencias" }

if ($UseSqlite) {
  New-Item -ItemType Directory -Force -Path $StorageDir | Out-Null
  $sqlitePath = Join-Path $StorageDir "calidad_web_dev.db"
  $env:CADENA_CONEXION_POSTGRESQL = "sqlite:///$($sqlitePath -replace '\\', '/')"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Ensure-Npm

Ensure-BackendEnv
if (-not $SkipSeleniumCheck) {
  Test-SeleniumChrome
}
Ensure-FrontendEnv

Write-Step "Aplicando migraciones en la base configurada"
Invoke-BackendCommand @("-m", "flask", "--app", "wsgi", "db", "upgrade")

Ensure-Admin

$backendHealthUrl = "http://localhost:$BackendPort/api/salud"
$frontendUrl = "http://localhost:$FrontendPort"
$backendRunning = Ensure-PortReusableOrFree $BackendPort "backend" $backendHealthUrl
$frontendRunning = Ensure-PortReusableOrFree $FrontendPort "frontend" $frontendUrl

Write-Step "Arrancando servicios"
if (-not $backendRunning) {
  Start-LoggedProcess "Backend" $BackendDir $PythonExe @("-m", "flask", "--app", "wsgi", "run", "--host", "127.0.0.1", "--port", "$BackendPort") (Join-Path $LogDir "backend.log") (Join-Path $LogDir "backend.pid")
}
Start-LoggedProcess "Trabajador" $BackendDir $PythonExe @("trabajador.py") (Join-Path $LogDir "trabajador_consola.log") (Join-Path $LogDir "trabajador.pid") "trabajador.py"
Start-LoggedProcess "Programador" $BackendDir $PythonExe @("programador.py") (Join-Path $LogDir "programador.log") (Join-Path $LogDir "programador.pid")
if (-not $frontendRunning) {
  Start-LoggedProcess "Frontend" $FrontendDir $NpmExe @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort") (Join-Path $LogDir "frontend.log") (Join-Path $LogDir "frontend.pid")
}

Write-Step "Esperando disponibilidad"
Wait-Url $backendHealthUrl 45 "Backend"
Wait-Url $frontendUrl 45 "Frontend"

Write-Host ""
Write-Host "Listo para probar:" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:$FrontendPort"
Write-Host "  Backend:  http://localhost:$BackendPort"
Write-Host "  Usuario:  $AdminEmail"
if (-not $SkipAdmin) {
  Write-Host "  Clave:    $AdminPassword"
}
Write-Host ""
Write-Host "Se abrieron ventanas PowerShell para cada proceso. Cierralas para apagar los servicios."
Write-Host "Logs: $LogDir"

if (-not $NoBrowser) {
  Start-Process $frontendUrl
}
