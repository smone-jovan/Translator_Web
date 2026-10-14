@echo off
title Translator Web Control Hub
chcp 65001 >nul
cd /d "%~dp0"

:: Jika dipanggil dengan argumen CLI (mis. doctor, --help, --cli), jalankan di konsol saat ini
if not "%~1"=="" goto :run_cli

:: Mode Sekali Pencet (Tanpa Argumen): Jalankan Desktop Control Hub GUI tanpa jendela CMD hitam
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else if exist "backend\.venv\Scripts\pythonw.exe" (
    start "" "backend\.venv\Scripts\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else if exist "backend\venv\Scripts\pythonw.exe" (
    start "" "backend\venv\Scripts\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" launcher.py --gui --no-browser
    exit /b 0
) else (
    where pythonw >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        start "" pythonw launcher.py --gui --no-browser
        exit /b 0
    )
)

:run_cli
set "ARGS=%*"
if "%~1"=="" set "ARGS=--gui --no-browser"

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
