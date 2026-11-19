@echo off
setlocal
cd /d "%~dp0"
title Agente de Impresion XP-80C - Escuela Villa Las Penas

echo ========================================================
echo   AGENTE DE IMPRESION XP-80C (ESC/POS)
echo   Escuela Villa Las Penas
echo ========================================================
echo.

:: Detectar Python
set "PY=C:\Python315\python.exe"
if not exist "%PY%" (
    if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
        set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
    ) else (
        set "PY=python"
    )
)

echo Usando Python en: %PY%
echo.
echo ========================================================
echo   Iniciando Agente de Impresion...
echo   (No cierres esta ventana mientras uses el sistema)
echo ========================================================
echo.

"%PY%" "%~dp0agente_impresion_xp80c.py"
pause
