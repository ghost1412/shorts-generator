@echo off
title Build ShortsFlow Core EXE
color 0A

echo ============================================================
echo      🔨 Compiling ShortsFlow AI Studio (PyInstaller)
echo ============================================================
echo.
echo [Info] Installing PyInstaller...
python -m pip install pyinstaller

echo [Info] Cleaning old builds...
if exist "build" rmdir /s /q build
if exist "dist\ShortsFlow_Core.exe" del /q "dist\ShortsFlow_Core.exe"

echo [Info] Running PyInstaller...
:: --onefile: Create a single executable
:: --windowed: Hide the console window for the GUI (Warning: This hides stdout. We might want a console for logging, or let the GUI handle it)
:: Wait, if we use --windowed, our subprocess might not have a console to write to, but we capture stdout via PIPE anyway.
:: Let's stick to console mode for now so users can see fatal crashes, or windowed mode since we have a GUI log box.
:: Actually, --noconsole is better for a GUI app.
python -m PyInstaller --noconfirm --onedir --windowed --icon=NONE --name "ShortsFlow_Core" --hidden-import main --hidden-import engine --hidden-import customtkinter gui_app.py

:: Note: We use --onedir here because we are going to package it all into an SFX anyway!
:: Oh wait, if we use SFX, we don't even need --onefile! --onedir is much faster to launch because it doesn't extract itself every time.
:: Our SFX will just extract the --onedir folder.
echo.
echo [Success] Compilation finished. The executable is in dist\ShortsFlow_Core\ShortsFlow_Core.exe
pause
