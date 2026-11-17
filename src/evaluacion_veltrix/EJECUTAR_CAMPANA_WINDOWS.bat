@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%..\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo No se encontro el Python del entorno QA: %PY%
  echo Ejecuta primero INICIAR_SISTEMA_QA.bat o crea backend\.venv.
  pause
  exit /b 1
)
if "%VELTRIX_OWNER_PASSWORD%"=="" (
  echo Falta la variable VELTRIX_OWNER_PASSWORD.
  echo Configurala en esta ventana antes de ejecutar:
  echo   set /p VELTRIX_OWNER_PASSWORD=Clave owner Aurora:
  pause
  exit /b 1
)
"%PY%" "%ROOT%scripts\campana_veltrix.py" %*
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo La campana finalizo con error. Codigo: %EXITCODE%
  pause
)
exit /b %EXITCODE%
