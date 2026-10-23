@echo off
setlocal
title DETEKTO Stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-detekto.ps1" %*
endlocal
pause
