@echo off
title Translator Web Control Hub
chcp 65001 >nul
cd /d "%~dp0"

set "ARGS=%*"

:: Check virtual environments first
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)
if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)
if exist "backend\venv\Scripts\python.exe" (
    "backend\venv\Scripts\python.exe" launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)

:: Test Python launcher 'py'
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -u launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)

:: Check Local AppData Python installations
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -u launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -u launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -u launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)

:: Test standard 'python'
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python -u launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)

:: Test 'python3'
where python3 >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python3 -u launcher.py %ARGS%
    exit /b %ERRORLEVEL%
)

echo.
echo  [ERROR] Python tidak ditemukan.
echo          Pastikan Python 3.11+ sudah terinstall dan ditambahkan ke PATH.
echo.
pause
