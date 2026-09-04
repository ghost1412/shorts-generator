@echo off
title ShortsFlow AI Studio - Launcher
color 0A
cls
echo ============================================================
echo           ⚡ ShortsFlow AI Studio Launcher ⚡
echo ============================================================
echo.
echo Select Mode:
echo   [1] 🖥️  Launch Desktop GUI (Recommended for Visual Workflow)
echo   [2] ⚡ Quick CLI Video Extractor
echo   [3] 🛠️  Run Automated Environment Setup (setup.bat)
echo.
set /p LAUNCH_CHOICE="Enter Choice (1-3, Default: 1): "

if "%LAUNCH_CHOICE%"=="3" (
    call setup.bat
    exit /b 0
)

if "%LAUNCH_CHOICE%"=="2" goto CLI_MODE

:: DEFAULT: LAUNCH DESKTOP GUI
echo.
echo [Info] Launching ShortsFlow Studio GUI...
python gui_app.py
exit /b 0

:CLI_MODE
cls
echo ============================================================
echo             ⚡ Quick CLI Video Extractor ⚡
echo ============================================================
echo.
set /p VIDEO_INPUT="Enter YouTube URL or Video File Path: "

if "%VIDEO_INPUT%"=="" (
    echo [Error] No input provided. Exiting.
    pause
    exit /b 1
)

echo.
set /p CLIP_COUNT="How many clips to extract? (Default: 3): "
if "%CLIP_COUNT%"=="" set CLIP_COUNT=3

echo.
echo Select Subtitle / Caption Style:
echo   1) HORMOZI (Dynamic Word Pop + Multi-color)
echo   2) GLOW_BOX (Glassmorphic Pill Box)
echo   3) BOUNCE (Spring Jump + Glow Shadow)
echo   4) MINIMAL (Clean Modern Bar)
set /p STYLE_CHOICE="Choice (1-4, Default: 1): "

set CAPTION_PRESET=HORMOZI
if "%STYLE_CHOICE%"=="2" set CAPTION_PRESET=GLOW_BOX
if "%STYLE_CHOICE%"=="3" set CAPTION_PRESET=BOUNCE
if "%STYLE_CHOICE%"=="4" set CAPTION_PRESET=MINIMAL

echo.
echo ============================================================
echo [Starting Extraction Pipeline...]
echo Input: %VIDEO_INPUT%
echo Clips: %CLIP_COUNT%
echo Subtitle Style: %CAPTION_PRESET%
echo ============================================================
echo.

python main.py --source_video "%VIDEO_INPUT%" --clip_count %CLIP_COUNT% --target_duration 30 --smart_crop --tighten --use_remotion --caption_style %CAPTION_PRESET% --output_json "latest_run.json"

echo.
echo ============================================================
echo 🎉 SUCCESS! Your clips have been generated in sessions/
echo Output metadata saved to latest_run.json
echo ============================================================
echo.
pause
