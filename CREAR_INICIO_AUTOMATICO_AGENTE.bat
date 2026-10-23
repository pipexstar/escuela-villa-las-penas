@echo off
chcp 65001 >nul
echo ========================================================
echo   CONFIGURADOR DE INICIO AUTOMÁTICO - XP-80C
echo   Escuela Villa Las Peñas
echo ========================================================
echo.

set SCRIPT_VBS="%TEMP%\crear_acceso_agente.vbs"
set DIR_ACTUAL=%~dp0
set AGENTE_PY=%DIR_ACTUAL%agente_impresion_xp80c.py

:: Obtener ruta de pythonw.exe
for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do set PYTHONW_PATH=%%i
if "%PYTHONW_PATH%"=="" (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do set PYTHONW_PATH=%%i
)

if "%PYTHONW_PATH%"=="" (
    echo [ERROR] No se encontró Python en el sistema.
    pause
    exit /b
)

echo Se encontró Python en: %PYTHONW_PATH%
echo Creando acceso en la carpeta Inicio de Windows...

echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT_VBS%
echo sLinkFile = oWS.SpecialFolders("Startup") ^& "\AgenteImpresion_XP80C.lnk" >> %SCRIPT_VBS%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT_VBS%
echo oLink.TargetPath = "%PYTHONW_PATH%" >> %SCRIPT_VBS%
echo oLink.Arguments = """" ^& "%AGENTE_PY%" ^& """" >> %SCRIPT_VBS%
echo oLink.WorkingDirectory = "%DIR_ACTUAL%" >> %SCRIPT_VBS%
echo oLink.Description = "Agente de Impresión Térmica XP-80C" >> %SCRIPT_VBS%
echo oLink.WindowStyle = 7 >> %SCRIPT_VBS%
echo oLink.Save >> %SCRIPT_VBS%

cscript //nologo %SCRIPT_VBS%
del %SCRIPT_VBS%

echo.
echo ========================================================
echo   ¡CONFIGURADO CON ÉXITO!
echo.
echo   Cada vez que se encienda este computador, el agente
echo   de impresión se iniciará automáticamente en segundo
echo   plano y estará listo para imprimir los atrasos.
echo ========================================================
echo.
pause
