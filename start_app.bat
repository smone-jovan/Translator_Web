@echo off
title Translator Web Control Hub
chcp 65001 >nul
cd /d "%~dp0"

set "ARGS=%*"
if "%~1"=="" set "ARGS=--no-browser"

:: Check virtual environments first
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py %ARGS%
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" launcher.py %ARGS%
) else if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" launcher.py %ARGS%
) else if exist "backend\venv\Scripts\python.exe" (
    "backend\venv\Scripts\python.exe" launcher.py %ARGS%
) else (
    py -u launcher.py %ARGS% 2>nul || python -u launcher.py %ARGS% || python3 -u launcher.py %ARGS%
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo  [ERROR] Launcher keluar dengan error code %ERRORLEVEL%.
    echo          Pastikan Python 3.11+ sudah terinstall.
    echo.
    pause
)
