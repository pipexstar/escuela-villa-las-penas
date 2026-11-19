@echo off
setlocal
cd /d "%~dp0"
title Configurador - Inicio Automatico Vercel 2027

echo ========================================================
echo   CONFIGURADOR - ACCESO DIRECTO VERCEL 2027
echo   Escuela Villa Las Penas
echo ========================================================
echo.

set "SCRIPT_VBS=%TEMP%\crear_acceso_vercel_startup.vbs"

:: CONFIGURAR AQUI LA URL DE TU PROYECTO EN VERCEL
set "URL_APP=https://gestionescolarevlp.vercel.app"

echo URL configurada: %URL_APP%
echo.

:: Detectar Chrome
set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_PATH%" set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_PATH%" set "CHROME_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"

:: Detectar Edge como alternativa
set "EDGE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_PATH%" set "EDGE_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

set "NAVEGADOR=%CHROME_PATH%"
if not exist "%CHROME_PATH%" (
    if exist "%EDGE_PATH%" (
        set "NAVEGADOR=%EDGE_PATH%"
        echo [INFO] Se usara Microsoft Edge.
    ) else (
        echo [ERROR] No se encontro Google Chrome ni Microsoft Edge.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Se encontro Google Chrome.
)

echo.
echo Configurando accesos directos e inicio automatico...

set "SCRIPT_DIR=%~dp0"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%SCRIPT_VBS%"

:: 1. Carpeta LOCAL
echo sLinkLocal = "%SCRIPT_DIR%Sistema Escolar 2027 - Vercel.lnk" >> "%SCRIPT_VBS%"
echo Set oLink1 = oWS.CreateShortcut(sLinkLocal) >> "%SCRIPT_VBS%"
echo oLink1.TargetPath = "%NAVEGADOR%" >> "%SCRIPT_VBS%"
echo oLink1.Arguments = "--kiosk-printing --user-data-dir=""" ^& oWS.ExpandEnvironmentStrings("%%TEMP%%") ^& "\kiosk_escuela_vercel"" " ^& Chr(34) ^& "%URL_APP%" ^& Chr(34) >> "%SCRIPT_VBS%"
echo oLink1.Save >> "%SCRIPT_VBS%"

:: 2. ESCRITORIO
echo sLinkDesk = oWS.SpecialFolders("Desktop") ^& "\Sistema Escolar 2027 - Vercel.lnk" >> "%SCRIPT_VBS%"
echo Set oLink2 = oWS.CreateShortcut(sLinkDesk) >> "%SCRIPT_VBS%"
echo oLink2.TargetPath = "%NAVEGADOR%" >> "%SCRIPT_VBS%"
echo oLink2.Arguments = "--kiosk-printing --user-data-dir=""" ^& oWS.ExpandEnvironmentStrings("%%TEMP%%") ^& "\kiosk_escuela_vercel"" " ^& Chr(34) ^& "%URL_APP%" ^& Chr(34) >> "%SCRIPT_VBS%"
echo oLink2.Save >> "%SCRIPT_VBS%"

cscript //nologo "%SCRIPT_VBS%"
if exist "%SCRIPT_VBS%" del "%SCRIPT_VBS%"

echo.
echo ========================================================
echo   CONFIGURACION COMPLETADA CON EXITO
echo.
echo   1. En el Escritorio:  Acceso directo creado
echo   2. En esta carpeta:   Acceso directo creado
echo ========================================================
echo.
pause
