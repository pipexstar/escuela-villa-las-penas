@echo off
setlocal
cd /d "%~dp0"
title Agente de Impresion XP-80C - Vercel

echo ========================================================
echo   AGENTE DE IMPRESION XP-80C - ESCUELA VILLA LAS PENAS
echo   Conectado a Vercel 2027
echo ========================================================
echo.

:: Detectar Python por ruta exacta
set "PY=C:\Python315\python.exe"
if not exist "%PY%" (
    if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
        set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
    ) else (
        if exist "C:\Users\VLP\AppData\Local\Programs\Python\Python313\python.exe" (
            set "PY=C:\Users\VLP\AppData\Local\Programs\Python\Python313\python.exe"
        )
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
