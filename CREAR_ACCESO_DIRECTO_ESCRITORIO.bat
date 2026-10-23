@echo off
chcp 65001 >nul
echo ========================================================
echo   CREADOR DE ACCESO DIRECTO - IMPRESIÓN TÉRMICA SILENCIOSA
echo   Escuela Villa Las Peñas
echo ========================================================
echo.

set SCRIPT_VBS="%TEMP%\crear_acceso.vbs"
set URL_APP=https://gestionescolarevlp.streamlit.app

:: Detectar Chrome
set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME_PATH% set CHROME_PATH="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME_PATH% set CHROME_PATH="%LocalAppData%\Google\Chrome\Application\chrome.exe"

:: Detectar Edge como alternativa
set EDGE_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist %EDGE_PATH% set EDGE_PATH="C:\Program Files\Microsoft\Edge\Application\msedge.exe"

set NAVEGADOR=%CHROME_PATH%
if not exist %CHROME_PATH% (
    if exist %EDGE_PATH% (
        set NAVEGADOR=%EDGE_PATH%
        echo [INFO] Se usará Microsoft Edge.
    ) else (
        echo [ERROR] No se encontró Google Chrome ni Microsoft Edge.
        pause
        exit /b
    )
) else (
    echo [INFO] Se encontró Google Chrome.
)

echo Creando acceso directo en el Escritorio...

echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT_VBS%
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Sistema Escolar - Atrasos.lnk" >> %SCRIPT_VBS%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT_VBS%
echo oLink.TargetPath = %NAVEGADOR% >> %SCRIPT_VBS%
echo oLink.Arguments = "--kiosk-printing --user-data-dir=""" ^& oWS.ExpandEnvironmentStrings("%%TEMP%%") ^& "\kiosk_escuela"" " ^& Chr(34) ^& "%URL_APP%" ^& Chr(34) >> %SCRIPT_VBS%
echo oLink.Description = "Sistema Escolar Villa Las Peñas - Impresión Térmica" >> %SCRIPT_VBS%
echo oLink.Save >> %SCRIPT_VBS%

cscript //nologo %SCRIPT_VBS%
del %SCRIPT_VBS%

echo.
echo ========================================================
echo   ¡ACCESO DIRECTO CREADO CON ÉXITO EN EL ESCRITORIO!
echo   Nombre: 'Sistema Escolar - Atrasos'
echo ========================================================
echo.
echo Recuerda que la impresora térmica de 80mm debe estar
echo configurada como la Impresora Predeterminada en Windows.
echo.
pause
