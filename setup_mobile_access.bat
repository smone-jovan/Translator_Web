@echo off
chcp 65001 >nul
title ReadOmni AI - Setup Mobile Access
echo.
echo  ══════════════════════════════════════════════
echo   ReadOmni AI - Mobile WiFi Access Setup
echo  ══════════════════════════════════════════════
echo.

:: Check if already admin
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [!] Butuh akses Administrator.
    echo      Klik kanan file ini ^> "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo  [*] Membuka port 5173 (Frontend Vite)...
netsh advfirewall firewall show rule name="ReadOmni AI - Frontend (Vite)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    netsh advfirewall firewall add rule name="ReadOmni AI - Frontend (Vite)" dir=in action=allow protocol=TCP localport=5173 profile=private,domain >nul
    echo  [OK] Port 5173 berhasil dibuka
) else (
    echo  [OK] Port 5173 sudah terbuka
)

echo  [*] Membuka port 8000 (Backend FastAPI)...
netsh advfirewall firewall show rule name="ReadOmni AI - Backend (FastAPI)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    netsh advfirewall firewall add rule name="ReadOmni AI - Backend (FastAPI)" dir=in action=allow protocol=TCP localport=8000 profile=private,domain >nul
    echo  [OK] Port 8000 berhasil dibuka
) else (
    echo  [OK] Port 8000 sudah terbuka
)

echo.
echo  ══════════════════════════════════════════════
echo   DONE! HP kamu sekarang bisa akses ReadOmni AI
echo   lewat WiFi yang sama.
echo  ══════════════════════════════════════════════
echo.
pause
