@echo off
chcp 65001 >nul
echo ========================================================
echo   PRUEBA DE IMPRESIÓN DIRECTA ESC/POS - XP-80C
echo   Escuela Villa Las Peñas
echo ========================================================
echo.
echo Enviando voucher de prueba a la impresora térmica...
echo.

python "%~dp0agente_impresion_xp80c.py" --test

echo.
echo ========================================================
echo Si la XP-80C imprimió y cortó el papel correctamente,
echo la configuración está 100%% lista.
echo ========================================================
echo.
pause
