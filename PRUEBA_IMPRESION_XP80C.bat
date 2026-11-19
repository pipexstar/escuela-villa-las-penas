@echo off
setlocal
cd /d "%~dp0"
title Prueba Impresora XP-80C

echo ========================================================
echo   PRUEBA DE IMPRESION DIRECTA ESC/POS - XP-80C
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
echo Enviando voucher de prueba a la impresora termica...
echo.

"%PY%" "%~dp0agente_impresion_xp80c.py" --test

echo.
echo ========================================================
echo Si la XP-80C imprimio y corto el papel correctamente,
echo la configuracion esta 100%% lista.
echo ========================================================
echo.
pause
