@echo off
title ShortsFlow AI - Generator Launcher
color 0A
cls
echo ============================================================
echo           ⚡ ShortsFlow AI Shorts Generator ⚡
echo ============================================================
echo.

:: Detect Python executable (prefer Python 3.12 CUDA GPU environment)
set PYTHON_EXE=python
if exist "C:\Users\win10\AppData\Local\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=C:\Users\win10\AppData\Local\Programs\Python\Python312\python.exe"
    echo [Info] GPU CUDA PyTorch Environment detected!
) else (
    echo [Info] Using default Python environment...
)

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
echo Select Editing Style Preset:
echo   1) Standard (Clean)
echo   2) Meme (High energy sound effects & captions)
echo   3) Funny
echo   4) Action
set /p STYLE_CHOICE="Choice (1-4, Default: 1): "

set STYLE_FLAG=
if "%STYLE_CHOICE%"=="2" set STYLE_FLAG=--style meme
if "%STYLE_CHOICE%"=="3" set STYLE_FLAG=--style funny
if "%STYLE_CHOICE%"=="4" set STYLE_FLAG=--style action

echo.
echo ============================================================
echo [Starting Extraction Pipeline...]
echo Video Input: %VIDEO_INPUT%
echo Clips Count: %CLIP_COUNT%
echo ============================================================
echo.

"%PYTHON_EXE%" main.py --source_video "%VIDEO_INPUT%" --clip_count %CLIP_COUNT% --target_duration 30 --smart_crop --tighten %STYLE_FLAG% --output_json "latest_run.json"

echo.
echo ============================================================
echo SUCCESS! Your clips have been generated in the sessions/ folder.
echo Structured output metadata saved to latest_run.json
echo ============================================================
echo.
pause
