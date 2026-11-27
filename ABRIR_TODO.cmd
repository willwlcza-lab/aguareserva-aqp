@echo off
start "AguaReserva Backend" cmd /k ""%~dp0ABRIR_BACKEND.cmd""
start "AguaReserva Frontend" cmd /k ""%~dp0ABRIR_FRONTEND.cmd""
start "AguaReserva Fuentes" cmd /k ""%~dp0ABRIR_SINCRONIZADOR.cmd""
echo Abre http://localhost:5173 cuando el frontend indique que esta listo.
echo Manten las tres ventanas abiertas. Para detener, Ctrl+C en cada una.
pause
