@echo off
title ShortsFlow AI - Environment & Dependency Setup
color 0A
cls
echo ============================================================
echo         ⚡ ShortsFlow AI Studio - 1-Click Setup ⚡
echo ============================================================
echo.

:: 1. Check Python installation
echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python is not installed or not in PATH!
    echo Please install Python 3.12+ from https://python.org
    pause
    exit /b 1
)
python --version

:: 2. Check Node.js & npm for Remotion
echo.
echo [2/4] Checking Node.js & npm (Required for Remotion video rendering)...
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Warning] Node.js / npm not found! Remotion rendering requires Node.js.
    echo Please install Node.js (v18+) from https://nodejs.org
) else (
    echo [Info] Node.js npm detected!
)

:: 3. Install Python requirements
echo.
echo [3/4] Installing Python requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

:: 4. Install Remotion npm dependencies
echo.
echo [4/4] Installing Remotion React dependencies...
if exist "remotion-video\package.json" (
    cd remotion-video
    npm install
    cd ..
) else (
    echo [Warning] remotion-video folder not found!
)

:: 5. Copy .env.example if .env does not exist
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo [Info] Created .env configuration file from template.
    )
)

echo.
echo ============================================================
echo 🎉 SETUP COMPLETE! You are ready to run ShortsFlow AI.
echo Run launch.bat to start the Studio GUI or CLI.
echo ============================================================
echo.
pause
