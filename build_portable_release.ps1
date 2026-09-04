<#
.SYNOPSIS
Builds a fully portable, standalone distribution of ShortsFlow AI Studio.

.DESCRIPTION
This script automates the creation of a portable folder containing:
1. Portable Python 3.12 (Embeddable)
2. Portable Node.js
3. FFmpeg binaries
4. All required project files and pip/npm dependencies.

The resulting folder can be zipped and shared. Users can run the software without installing Python, Node, or FFmpeg globally!
#>

$BuildDir = "ShortsFlow_Portable_Build"
$PythonUrl = "https://www.python.org/ftp/python/3.11.8/python-3.11.8-embed-amd64.zip"
$NodeUrl = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-win-x64.zip"
$FfmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   🚀 Building ShortsFlow Portable Release Bundle" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Clean and Create Build Dir
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Path "$BuildDir\bin" | Out-Null

# 2. Download and Extract Portable Python
Write-Host "[1/6] Downloading Portable Python 3.11..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $PythonUrl -OutFile "$BuildDir\python.zip"
Expand-Archive -Path "$BuildDir\python.zip" -DestinationPath "$BuildDir\python" -Force
Remove-Item "$BuildDir\python.zip"

# Enable pip in embedded python
$pthFile = Get-ChildItem "$BuildDir\python\*._pth" | Select-Object -First 1
(Get-Content $pthFile.FullName) -replace '#import site', 'import site' | Set-Content $pthFile.FullName

Write-Host "[2/6] Installing PIP and Python Dependencies..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "$BuildDir\python\get-pip.py"
& "$BuildDir\python\python.exe" "$BuildDir\python\get-pip.py"

# 3. Download and Extract Portable Node.js
Write-Host "[3/6] Downloading Portable Node.js..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $NodeUrl -OutFile "$BuildDir\node.zip"
Expand-Archive -Path "$BuildDir\node.zip" -DestinationPath "$BuildDir\node_tmp" -Force
Move-Item -Path "$BuildDir\node_tmp\node-v20.11.1-win-x64" -Destination "$BuildDir\node"
Remove-Item "$BuildDir\node.zip"
Remove-Item "$BuildDir\node_tmp" -Recurse -Force

# 4. Download FFmpeg
Write-Host "[4/6] Downloading FFmpeg..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $FfmpegUrl -OutFile "$BuildDir\ffmpeg.zip"
Expand-Archive -Path "$BuildDir\ffmpeg.zip" -DestinationPath "$BuildDir\ffmpeg_tmp" -Force
Copy-Item "$BuildDir\ffmpeg_tmp\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" -Destination "$BuildDir\bin\"
Copy-Item "$BuildDir\ffmpeg_tmp\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" -Destination "$BuildDir\bin\"
Remove-Item "$BuildDir\ffmpeg.zip"
Remove-Item "$BuildDir\ffmpeg_tmp" -Recurse -Force

# 5. Copy Project Files
Write-Host "[5/6] Copying ShortsFlow App Files..." -ForegroundColor Yellow
$ExcludeList = @('.git', 'venv', '__pycache__', 'node_modules', 'sessions', 'demos', $BuildDir)
Copy-Item -Path .\* -Destination $BuildDir -Recurse -Exclude $ExcludeList -Force

# 6. Create Portable Launcher
Write-Host "[6/6] Creating Portable Launcher (ShortsFlow.bat)..." -ForegroundColor Yellow
$LauncherContent = @"
@echo off
title ShortsFlow AI Studio - Portable
color 0A

:: Add portable folders to PATH temporarily for this session
set "BASE_DIR=%~dp0"
set "PATH=%BASE_DIR%python;%BASE_DIR%python\Scripts;%BASE_DIR%node;%BASE_DIR%bin;%PATH%"

echo ============================================================
echo      ⚡ ShortsFlow AI Studio (Portable Edition) ⚡
echo ============================================================
echo.
echo [Info] Checking dependencies...

:: Check if pip dependencies are installed
if not exist "%BASE_DIR%python\Lib\site-packages\customtkinter" (
    echo [Info] First time setup: Installing Python packages...
    python -m pip install -r requirements.txt
)

:: Check if Node dependencies are installed
if not exist "%BASE_DIR%remotion-video\node_modules" (
    echo [Info] First time setup: Installing Remotion packages...
    cd remotion-video
    call npm install
    cd ..
)

echo [Info] Launching GUI...
python gui_app.py

if %errorlevel% neq 0 (
    echo.
    echo [Error] ShortsFlow Studio crashed.
    pause
)
exit /b 0
"@
Set-Content -Path "$BuildDir\ShortsFlow.bat" -Value $LauncherContent

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🎉 SUCCESS! Portable Build is ready in: .\$BuildDir" -ForegroundColor Green
Write-Host "You can now ZIP this folder and distribute it." -ForegroundColor Cyan
Write-Host "Users just need to double-click 'ShortsFlow.bat' to run." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
