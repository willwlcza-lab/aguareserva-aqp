@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
 echo Completa primero la instalacion.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m app.cli crear-admin
pause
