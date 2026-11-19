@echo off
setlocal
cd /d "%~dp0"
title Creador de Acceso Directo - Impresion Termica

echo ========================================================
echo   CREADOR DE ACCESO DIRECTO - IMPRESION TERMICA
echo   Escuela Villa Las Penas
echo ========================================================
echo.

set "SCRIPT_VBS=%TEMP%\crear_acceso_escritorio.vbs"
set "URL_APP=https://gestionescolarevlp.vercel.app"

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

echo Creando acceso directo en el Escritorio...

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%SCRIPT_VBS%"
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Sistema Escolar - Atrasos.lnk" >> "%SCRIPT_VBS%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%SCRIPT_VBS%"
echo oLink.TargetPath = "%NAVEGADOR%" >> "%SCRIPT_VBS%"
echo oLink.Arguments = "--kiosk-printing --user-data-dir=""" ^& oWS.ExpandEnvironmentStrings("%%TEMP%%") ^& "\kiosk_escuela"" " ^& Chr(34) ^& "%URL_APP%" ^& Chr(34) >> "%SCRIPT_VBS%"
echo oLink.Description = "Sistema Escolar Villa Las Penas - Impresion Termica" >> "%SCRIPT_VBS%"
echo oLink.Save >> "%SCRIPT_VBS%"

cscript //nologo "%SCRIPT_VBS%"
if exist "%SCRIPT_VBS%" del "%SCRIPT_VBS%"

echo.
echo ========================================================
echo   ACCESO DIRECTO CREADO CON EXITO EN EL ESCRITORIO
echo ========================================================
echo.
pause
