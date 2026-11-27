@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" goto falta
if not exist ".env" goto falta
.venv\Scripts\python.exe -m app.sincronizador
pause
exit /b
:falta
echo Completa la instalacion indicada en LEEME_PRIMERO.html.
pause
