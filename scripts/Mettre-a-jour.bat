@echo off
title Mise a jour - YouTube pour Resolve
echo Mise a jour de yt-dlp, Deno et ffmpeg (a faire si YouTube ne marche plus)...
set "TEMP=%~dp0tmp"
set "TMP=%~dp0tmp"
if not exist "%TEMP%" mkdir "%TEMP%"
"%~dp0python\python.exe" -m pip install --no-cache-dir --disable-pip-version-check --no-warn-script-location -q --upgrade -r "%~dp0app\requirements.txt"
rmdir /S /Q "%~dp0tmp" 2>nul
echo Termine.
pause
