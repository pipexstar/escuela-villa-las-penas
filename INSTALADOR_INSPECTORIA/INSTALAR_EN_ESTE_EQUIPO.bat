@echo off
title Instalador Agente XP-80C
echo ========================================================
echo   INSTALADOR DEL AGENTE DE IMPRESION XP-80C
echo   Escuela Villa Las Penas
echo ========================================================
echo.

set DESTINO=C:\AgenteImpresion_XP80C
if not exist "%DESTINO%" mkdir "%DESTINO%"

echo [1/3] Copiando ejecutable a %DESTINO%...
copy /y "%~dp0AgenteImpresion_XP80C.exe" "%DESTINO%\AgenteImpresion_XP80C.exe" >nul

echo [2/3] Configurando inicio automatico con Windows...
set SCRIPT_VBS="%TEMP%\crear_acceso_inicio.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT_VBS%
echo sLinkFile = oWS.SpecialFolders("Startup") ^& "\AgenteImpresion_XP80C.lnk" >> %SCRIPT_VBS%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT_VBS%
echo oLink.TargetPath = "%DESTINO%\AgenteImpresion_XP80C.exe" >> %SCRIPT_VBS%
echo oLink.WorkingDirectory = "%DESTINO%" >> %SCRIPT_VBS%
echo oLink.Description = "Agente de Impresion Termica XP-80C" >> %SCRIPT_VBS%
echo oLink.WindowStyle = 7 >> %SCRIPT_VBS%
echo oLink.Save >> %SCRIPT_VBS%

cscript //nologo %SCRIPT_VBS%
del %SCRIPT_VBS%

echo [3/3] Iniciando el agente de impresion...
start "" "%DESTINO%\AgenteImpresion_XP80C.exe"

echo.
echo ========================================================
echo   INSTALACION COMPLETADA CON EXITO!
echo   El agente ya esta activo y se iniciara solo
echo   cada vez que se encienda este computador.
echo ========================================================
echo.
pause