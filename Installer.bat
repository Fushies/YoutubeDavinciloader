@echo off
setlocal EnableExtensions
title Installation - YouTube pour Resolve
set "PYVER=3.13.17"
set "SCRIPTS=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"

echo.
echo  ===== YouTube pour Resolve : installation =====
echo.
echo  Tout est installe dans un seul dossier : Python, l'application, le cache
echo  et tes videos/sons telecharges. Rien n'est installe sur C: (a part le petit
echo  raccourci du Bureau et l'entree du menu Scripts de Resolve).
echo.

rem --- 0. Choix du dossier (D: par defaut) --------------------------------
set "DEFAULT=D:\YouTubePourResolve"
if not exist "D:\" set "DEFAULT=%LOCALAPPDATA%\YouTubePourResolve"
echo  Dossier propose : %DEFAULT%
echo  Appuie sur Entree pour l'accepter, ou tape un autre dossier.
echo.
set "DEST="
set /p "DEST=  Dossier d'installation : "
if not defined DEST set "DEST=%DEFAULT%"
set "DEST=%DEST:"=%"
if "%DEST:~-1%"=="\" set "DEST=%DEST:~0,-1%"
if not exist "%DEST%\" mkdir "%DEST%" 2>nul
if not exist "%DEST%\" (
    echo.
    echo  Impossible de creer "%DEST%". Verifie que le disque existe.
    goto :err
)
echo.
echo  Installation dans : %DEST%
echo.
set "TEMP=%DEST%\tmp"
set "TMP=%DEST%\tmp"
if not exist "%TEMP%" mkdir "%TEMP%"

rem --- 1. Python portable (dans le dossier, pas sur C:) ---------------------
if exist "%DEST%\python\python.exe" goto :have_python
echo  [1/5] Telechargement de Python %PYVER% portable (environ 15 Mo)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing 'https://www.nuget.org/api/v2/package/python/%PYVER%' -OutFile '%TEMP%\python.zip'; Expand-Archive -Force '%TEMP%\python.zip' '%TEMP%\python_pkg'"
if not exist "%TEMP%\python_pkg\tools\python.exe" goto :err
move "%TEMP%\python_pkg\tools" "%DEST%\python" >nul || goto :err
:have_python
echo  [1/5] Python : OK

rem --- 2. Dependances -------------------------------------------------------
echo  [2/5] Installation de yt-dlp, ffmpeg, Deno et de l'interface (1re fois : quelques minutes)...
"%DEST%\python\python.exe" -m ensurepip --upgrade >nul 2>&1
"%DEST%\python\python.exe" -m pip install --no-cache-dir --disable-pip-version-check --no-warn-script-location -q --upgrade pip
"%DEST%\python\python.exe" -m pip install --no-cache-dir --disable-pip-version-check --no-warn-script-location -q --upgrade -r "%~dp0app\requirements.txt" || goto :err

rem --- 3. Application -------------------------------------------------------
echo  [3/5] Copie de l'application
xcopy /E /I /Y /Q "%~dp0app" "%DEST%\app" >nul || goto :err
copy /Y "%~dp0scripts\*.bat" "%DEST%\" >nul
copy /Y "%~dp0LISEZMOI.txt" "%DEST%\" >nul
if not exist "%DEST%\Telechargements" mkdir "%DEST%\Telechargements"

rem --- 4. Menu Workspace > Scripts de Resolve -------------------------------
echo  [4/5] Ajout au menu Workspace ^> Scripts de DaVinci Resolve
if not exist "%SCRIPTS%" mkdir "%SCRIPTS%"
set "LUA=%SCRIPTS%\YouTube_pour_Resolve.lua"
> "%LUA%" echo -- DaVinci Resolve ^> Workspace ^> Scripts ^> YouTube_pour_Resolve (marche aussi avec Resolve gratuit)
>>"%LUA%" echo local base = [[%DEST%]]
>>"%LUA%" echo local pyw = base .. "\\python\\pythonw.exe"
>>"%LUA%" echo local app = base .. "\\app\\yt_resolve.py"
>>"%LUA%" echo os.execute('start "" "' .. pyw .. '" "' .. app .. '"')

rem --- 5. Raccourci sur le Bureau ------------------------------------------
echo  [5/5] Raccourci sur le Bureau
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\YouTube pour Resolve.lnk'); $s.TargetPath='%DEST%\python\pythonw.exe'; $s.Arguments='\"%DEST%\app\yt_resolve.py\"'; $s.WorkingDirectory='%DEST%\app'; $s.Description='Rechercher et telecharger des videos YouTube pour DaVinci Resolve'; $s.Save()" >nul 2>&1

rem --- Ancienne version installee sur C: ? ---------------------------------
if /I not "%DEST%"=="%LOCALAPPDATA%\YouTubePourResolve" if exist "%LOCALAPPDATA%\YouTubePourResolve\venv" (
    echo.
    echo  Une ancienne version est installee sur C: ^(%LOCALAPPDATA%\YouTubePourResolve^).
    choice /M "  La supprimer pour liberer de la place sur C:"
    if not errorlevel 2 rmdir /S /Q "%LOCALAPPDATA%\YouTubePourResolve"
)

rmdir /S /Q "%DEST%\tmp" 2>nul
echo.
echo  Termine !
echo    - Application et telechargements : %DEST%
echo    - Bureau : raccourci "YouTube pour Resolve"
echo    - Dans Resolve : Workspace ^> Scripts ^> YouTube_pour_Resolve  (redemarre Resolve une fois)
echo.
start "" "%DEST%\python\pythonw.exe" "%DEST%\app\yt_resolve.py"
pause
exit /b 0

:err
echo.
echo  ERREUR pendant l'installation. Verifie ta connexion Internet et relance Installer.bat.
rmdir /S /Q "%DEST%\tmp" 2>nul
pause
exit /b 1
