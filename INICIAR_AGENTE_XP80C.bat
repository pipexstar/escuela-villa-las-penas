@echo off
chcp 65001 >nul
title Agente de Impresión XP-80C - Escuela Villa Las Peñas
echo ========================================================
echo   AGENTE DE IMPRESIÓN XP-80C (ESC/POS)
echo   Escuela Villa Las Peñas
echo ========================================================
echo.
echo Comprobando dependencias...
pip show supabase >nul 2>&1
if %errorlevel% neq 0 (
    echo Instalando supabase...
    pip install supabase
)
pip show pywin32 >nul 2>&1
if %errorlevel% neq 0 (
    echo Instalando pywin32...
    pip install pywin32
)

echo.
echo ========================================================
echo   Iniciando Agente de Impresión...
echo   (No cierres esta ventana mientras uses el sistema)
echo ========================================================
echo.

python "%~dp0agente_impresion_xp80c.py"
pause
