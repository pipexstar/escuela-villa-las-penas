@echo off
setlocal
cd /d "%~dp0"
title Configurar Inicio Automatico - XP-80C

echo ========================================================
echo   CONFIGURADOR DE INICIO AUTOMATICO - XP-80C
echo   Escuela Villa Las Penas
echo ========================================================
echo.

:: Detectar pythonw.exe o python.exe
set "PYW=C:\Python315\pythonw.exe"
if not exist "%PYW%" (
    if exist "%LocalAppData%\Programs\Python\Python313\pythonw.exe" (
        set "PYW=%LocalAppData%\Programs\Python\Python313\pythonw.exe"
    ) else (
        if exist "C:\Python315\python.exe" (
            set "PYW=C:\Python315\python.exe"
        ) else (
            set "PYW=pythonw"
        )
    )
)

echo Se encontro Python en: %PYW%
echo Configurando inicio automatico de Windows en segundo plano...
echo.

set "SCRIPT_VBS=%TEMP%\crear_acceso_agente_xp80c.vbs"
set "DIR_ACTUAL=%~dp0"
set "AGENTE_PY=%DIR_ACTUAL%agente_impresion_xp80c.py"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%SCRIPT_VBS%"
echo sLinkFile = oWS.SpecialFolders("Startup") ^& "\AgenteImpresion_XP80C.lnk" >> "%SCRIPT_VBS%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%SCRIPT_VBS%"
echo oLink.TargetPath = "%PYW%" >> "%SCRIPT_VBS%"
echo oLink.Arguments = """" ^& "%AGENTE_PY%" ^& """" >> "%SCRIPT_VBS%"
echo oLink.WorkingDirectory = "%DIR_ACTUAL%" >> "%SCRIPT_VBS%"
echo oLink.Description = "Agente de Impresion Termica XP-80C Silencioso" >> "%SCRIPT_VBS%"
echo oLink.WindowStyle = 7 >> "%SCRIPT_VBS%"
echo oLink.Save >> "%SCRIPT_VBS%"

cscript //nologo "%SCRIPT_VBS%"
if exist "%SCRIPT_VBS%" del "%SCRIPT_VBS%"

echo ========================================================
echo   CONFIGURADO CON EXITO
echo.
echo   Cada vez que inicie Windows en este equipo, el agente
echo   se ejecutara en segundo plano y cortara los vouchers
echo   de forma automatica y silenciosa.
echo ========================================================
echo.
pause
