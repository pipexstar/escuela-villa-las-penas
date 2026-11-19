@echo off
setlocal
cd /d "%~dp0"
title Prueba Impresora XP-80C - Vercel

echo ========================================================
echo   PRUEBA DE IMPRESION DIRECTA XP-80C
echo   Escuela Villa Las Penas
echo ========================================================
echo.

:: Detectar Python
set "PY=python"
if exist "C:\Python315\python.exe" (
    set "PY=C:\Python315\python.exe"
) else (
    if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
        set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
    )
)

echo Usando Python en: %PY%
echo Enviando ticket de prueba directamente al puerto USB de la impresora...
echo.

"%PY%" "%~dp0agente_impresion_xp80c.py" --test

echo.
echo ========================================================
echo Si la impresora corto el ticket de prueba, esta lista!
echo ========================================================
echo.
pause
