@echo off
title Desinstallation - YouTube pour Resolve
echo Supprime l'application de %~dp0
echo Tes videos et sons (dossier Telechargements) sont conserves.
choice /M "Continuer"
if errorlevel 2 exit /b 0
del /Q "%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\YouTube_pour_Resolve.lua" 2>nul
powershell -NoProfile -Command "Remove-Item -ErrorAction SilentlyContinue ([Environment]::GetFolderPath('Desktop')+'\YouTube pour Resolve.lnk')"
rmdir /S /Q "%~dp0python" 2>nul
rmdir /S /Q "%~dp0app" 2>nul
rmdir /S /Q "%~dp0cache" 2>nul
del /Q "%~dp0settings.json" "%~dp0Lancer.bat" "%~dp0Mettre-a-jour.bat" "%~dp0LISEZMOI.txt" 2>nul
echo Termine. Le dossier Telechargements est toujours la : %~dp0Telechargements
pause
(goto) 2>nul & del "%~f0"
