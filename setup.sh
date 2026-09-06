#!/usr/bin/env bash
set -e

echo "============================================================"
echo "        ⚡ ShortsFlow AI Studio - Linux/macOS Setup ⚡"
echo "============================================================"
echo ""

# 1. Check Python
echo "[1/5] Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed! Please install Python 3.12+"
    exit 1
fi
python3 --version

# 2. Check Node.js & npm
echo "[2/5] Checking Node.js & npm..."
if ! command -v npm &> /dev/null; then
    echo "❌ Node.js / npm is not installed! Required for Remotion video rendering."
    exit 1
fi
npm --version

# 3. Check FFmpeg
echo "[3/5] Checking FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg is not installed! Please install FFmpeg (e.g. sudo apt install ffmpeg or brew install ffmpeg)."
    exit 1
fi
ffmpeg -version | head -n 1

# 4. Install Python dependencies
echo "[4/5] Installing Python requirements..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 5. Install Remotion npm dependencies
echo "[5/5] Installing Remotion React dependencies..."
if [ -d "remotion-video" ]; then
    cd remotion-video
    npm install
    cd ..
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "💡 Created .env file from template."
fi

echo ""
echo "============================================================"
echo "🎉 SETUP COMPLETE! Run: python main.py or python gui_app.py"
echo "============================================================"
