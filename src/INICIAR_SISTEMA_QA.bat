@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\levantar_pruebas_windows.ps1" -UseSqlite
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo El arranque del Sistema Integral de Calidad Web finalizo con error. Codigo: %EXITCODE%
  echo Revisa el mensaje anterior antes de cerrar esta ventana.
  pause
)
exit /b %EXITCODE%
