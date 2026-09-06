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
echo [2/5] Checking Node.js ^& npm (Required for Remotion video rendering)...
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [31m[Error] Node.js / npm not found! [0m
    echo Remotion rendering requires Node.js.
    echo Please install Node.js (v18+) from https://nodejs.org
    pause
    exit /b 1
) else (
    echo  [32m[Info] Node.js npm detected! [0m
)

:: 3. Check FFmpeg
echo.
echo [3/5] Checking FFmpeg (Required for video processing)...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [31m[Error] FFmpeg is not installed or not in PATH! [0m
    echo Please install FFmpeg from https://ffmpeg.org/download.html and add it to your system PATH.
    echo The video generation engine will fail without it.
    pause
    exit /b 1
) else (
    echo  [32m[Info] FFmpeg detected! [0m
)

:: 4. Check CUDA / GPU
echo.
echo [4/5] Checking for NVIDIA GPU (CUDA)...
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo  [33m[Notice] No NVIDIA GPU detected or nvidia-smi not in PATH. [0m
    echo The pipeline will run on CPU. Video encoding and transcription may be slower.
) else (
    echo  [32m[Info] NVIDIA GPU detected! Hardware acceleration enabled. [0m
)

:: 5. Install Python requirements
echo.
echo [5/6] Installing Python requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo  [31m[Error] Failed to install Python dependencies! [0m
    pause
    exit /b 1
)

:: 6. Install Remotion npm dependencies
echo.
echo [6/6] Installing Remotion React dependencies...
if exist "remotion-video\package.json" (
    cd remotion-video
    npm install
    if %errorlevel% neq 0 (
        echo  [31m[Error] Failed to install Remotion dependencies! [0m
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo  [33m[Warning] remotion-video folder not found! Skipping Remotion setup. [0m
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
