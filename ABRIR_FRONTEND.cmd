@echo off
cd /d "%~dp0frontend"
if not exist "node_modules" (
 echo Primero completa la instalacion de LEEME_PRIMERO.html.
 pause
 exit /b 1
)
call npm.cmd run dev
pause
