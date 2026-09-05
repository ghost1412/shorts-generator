<#
.SYNOPSIS
Builds a fully portable, compiled Standalone SFX Executable of ShortsFlow AI Studio.

.DESCRIPTION
This script automates:
1. Compiling the Python source code into a standalone directory using PyInstaller.
2. Downloading Portable Node.js.
3. Downloading FFmpeg binaries.
4. Packaging them into a final payload directory.
(Note: To convert the final directory into a single .exe, use 7-Zip SFX Maker or WinRAR).
#>

$BuildDir = "ShortsFlow_Final_Build"
$NodeUrl = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-win-x64.zip"
$FfmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   🚀 Building ShortsFlow Compiled Executable Bundle" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Clean and Create Build Dir
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Path "$BuildDir\bin" | Out-Null

# 2. Compile Python Source (Hides Code + Bundles Python)
Write-Host "[1/5] Compiling Python Source Code with PyInstaller..." -ForegroundColor Yellow
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onedir --windowed --icon=NONE --name "ShortsFlow_Core" --hidden-import main --hidden-import engine --hidden-import customtkinter gui_app.py

Write-Host "[2/5] Copying Compiled Core..." -ForegroundColor Yellow
Copy-Item -Path "dist\ShortsFlow_Core\*" -Destination $BuildDir -Recurse -Force

# 3. Download and Extract Portable Node.js
Write-Host "[3/5] Downloading Portable Node.js..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $NodeUrl -OutFile "$BuildDir\node.zip"
Expand-Archive -Path "$BuildDir\node.zip" -DestinationPath "$BuildDir\node_tmp" -Force
Move-Item -Path "$BuildDir\node_tmp\node-v20.11.1-win-x64" -Destination "$BuildDir\node"
Remove-Item "$BuildDir\node.zip"
Remove-Item "$BuildDir\node_tmp" -Recurse -Force

# 4. Download FFmpeg
Write-Host "[4/5] Downloading FFmpeg..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $FfmpegUrl -OutFile "$BuildDir\ffmpeg.zip"
Expand-Archive -Path "$BuildDir\ffmpeg.zip" -DestinationPath "$BuildDir\ffmpeg_tmp" -Force
Copy-Item "$BuildDir\ffmpeg_tmp\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" -Destination "$BuildDir\bin\"
Copy-Item "$BuildDir\ffmpeg_tmp\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" -Destination "$BuildDir\bin\"
Remove-Item "$BuildDir\ffmpeg.zip"
Remove-Item "$BuildDir\ffmpeg_tmp" -Recurse -Force

# 5. Copy Remotion Code
Write-Host "[5/5] Copying React Subtitle Engine..." -ForegroundColor Yellow
Copy-Item -Path "remotion-video" -Destination "$BuildDir\remotion-video" -Recurse -Force

# 6. Create Launcher
$LauncherContent = @"
@echo off
title ShortsFlow AI Studio
color 0A

:: Add portable folders to PATH temporarily for this session
set "BASE_DIR=%~dp0"
set "PATH=%BASE_DIR%node;%BASE_DIR%bin;%PATH%"

echo ============================================================
echo      ⚡ ShortsFlow AI Studio (Compiled Edition) ⚡
echo ============================================================

:: Check if Node dependencies are installed
if not exist "%BASE_DIR%remotion-video\node_modules" (
    echo [Info] First time setup: Installing Remotion packages...
    cd remotion-video
    call npm install
    cd ..
)

echo [Info] Launching Studio...
start ShortsFlow_Core.exe
exit /b 0
"@
Set-Content -Path "$BuildDir\Run_ShortsFlow.bat" -Value $LauncherContent

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🎉 SUCCESS! Compiled Build is ready in: .\$BuildDir" -ForegroundColor Green
Write-Host "To create your single SFX .exe:" -ForegroundColor Cyan
Write-Host "  1. Install 7-Zip" -ForegroundColor Cyan
Write-Host "  2. Right-click the folder '$BuildDir' -> 7-Zip -> Add to Archive" -ForegroundColor Cyan
Write-Host "  3. Check 'Create SFX archive'" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
