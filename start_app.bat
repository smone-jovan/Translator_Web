@echo off
title ReadOmni AI Control Hub
chcp 65001 >nul
cd /d "%~dp0"

:: Check virtual environments first
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" launcher.py
) else if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" launcher.py
) else if exist "backend\venv\Scripts\python.exe" (
    "backend\venv\Scripts\python.exe" launcher.py
) else (
    py -u launcher.py 2>nul || python -u launcher.py || python3 -u launcher.py
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo  [ERROR] Launcher keluar dengan error code %ERRORLEVEL%.
    echo          Pastikan Python 3.11+ sudah terinstall.
    echo.
    pause
)
