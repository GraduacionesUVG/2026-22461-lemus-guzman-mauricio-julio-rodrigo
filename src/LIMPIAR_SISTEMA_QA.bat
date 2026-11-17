@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo No se encontro el entorno Python del backend:
  echo   %PY%
  echo Ejecuta primero la instalacion del backend o INICIAR_SISTEMA_QA.bat.
  pause
  exit /b 1
)

:MENU
cls
echo ================================================================
echo  LIMPIADOR SEGURO - SISTEMA INTEGRAL DE CALIDAD WEB
echo ================================================================
echo.
echo  1. Ver que datos se eliminaran (simulacion)
echo  2. Detener servicios QA y realizar limpieza completa
echo  3. Verificar estado del sistema
echo  4. Salir
echo.
set "OPCION="
set /p OPCION=Selecciona una opcion: 

if "%OPCION%"=="1" (
  "%PY%" "%ROOT%scripts\limpiar_sistema_qa.py" simular --use-sqlite
  pause
  goto MENU
)
if "%OPCION%"=="2" (
  "%PY%" "%ROOT%scripts\limpiar_sistema_qa.py" limpiar --use-sqlite --detener-servicios
  pause
  goto MENU
)
if "%OPCION%"=="3" (
  "%PY%" "%ROOT%scripts\limpiar_sistema_qa.py" verificar --use-sqlite
  pause
  goto MENU
)
if "%OPCION%"=="4" exit /b 0

echo Opcion invalida.
pause
goto MENU
