$ErrorActionPreference = 'Stop'
$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $rootDir 'backend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$logDir = Join-Path $rootDir '.logs'

function Test-QaService($Process) {
    $command = [string]$Process.CommandLine
    $isService = $command -match '(?i)\b(trabajador|programador)\.py\b' -or
        $command -match '(?i)\bflask\b.*--app\s+[''"]?wsgi\b.*\brun\b'
    if (-not $isService) { return $false }
    # Los PID del iniciador son ventanas PowerShell, no los procesos Python.
    # Comprueba la identidad antes de terminar el arbol; un PID puede reutilizarse.
    if ($Process.Name -ieq 'powershell.exe') {
        return $command.IndexOf($backendDir, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            $command.IndexOf($pythonExe, [StringComparison]::OrdinalIgnoreCase) -ge 0
    }
    return $Process.Name -like 'python*.exe' -and $Process.ExecutablePath -ieq $pythonExe
}

try {
    $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $services = @($processes | Where-Object { Test-QaService $_ })
    # Primero las ventanas: /T termina tambien Python, navegadores y sus hijos.
    $services = @($services | Sort-Object @{Expression = { if ($_.Name -ieq 'powershell.exe') { 0 } else { 1 } }})
    foreach ($service in $services) {
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($service.ProcessId)" -ErrorAction Stop
        if ($null -eq $current) { continue }
        if ($current.CreationDate -ne $service.CreationDate -or -not (Test-QaService $current)) {
            throw "El PID $($service.ProcessId) cambio de identidad. Intenta nuevamente."
        }
        Write-Host "Deteniendo servicio QA: $($service.Name), PID $($service.ProcessId)"
        & taskkill.exe /PID $service.ProcessId /T /F | Out-Host
        if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $service.ProcessId -ErrorAction SilentlyContinue)) {
            throw "No se pudo detener el PID $($service.ProcessId)."
        }
    }
    $remaining = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { Test-QaService $_ })
    if ($remaining.Count -gt 0) { throw 'Aun hay servicios QA activos. No se limpiara la base.' }
    foreach ($name in @('backend.pid', 'trabajador.pid', 'programador.pid')) {
        $pidPath = Join-Path $logDir $name
        if (Test-Path -LiteralPath $pidPath) {
            # Los PID ajenos quedan intactos; solo se retira el registro obsoleto.
            Remove-Item -LiteralPath $pidPath -Force
        }
    }
    Write-Host 'Servicios QA detenidos. Al terminar la limpieza, ejecuta INICIAR_SISTEMA_QA.bat.'
} catch {
    Write-Host "No se pudieron detener los servicios QA: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
