@echo off
setlocal
title DETEKTO Launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-detekto.ps1" %*
if errorlevel 1 (
  echo.
  echo [DETEKTO] Launcher berhenti karena error. Baca pesan di atas.
  pause
  exit /b 1
)
endlocal
