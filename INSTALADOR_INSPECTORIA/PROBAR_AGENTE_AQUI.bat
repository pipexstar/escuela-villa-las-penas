@echo off
title Diagnostico Agente XP-80C
echo ========================================================
echo   DIAGNOSTICO DEL AGENTE XP-80C
echo   Escuela Villa Las Penas
echo ========================================================
echo.
echo Ejecutando prueba de impresion y conexion...
echo.

"%~dp0AgenteImpresion_XP80C.exe" --test

echo.
echo ========================================================
echo Si la prueba fue EXITOSA, la impresora imprimio un ticket.
echo Si dio ERROR o no se cerro, lee el mensaje de arriba.
echo ========================================================
echo.
pause