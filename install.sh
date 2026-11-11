#!/usr/bin/env sh
# ShortsFlow installer for macOS and Linux.
#   curl -fsSL https://raw.githubusercontent.com/ghost1412/shorts-generator/main/install.sh | sh
# Installs into ~/.shortsflow (its own Python environment) and links a `shortsflow` command into ~/.local/bin.
# Nothing outside those two places is changed. Remove it with: rm -rf ~/.shortsflow ~/.local/bin/shortsflow
set -eu

HOME_DIR="${SHORTSFLOW_HOME:-$HOME/.shortsflow}"
BIN_DIR="${SHORTSFLOW_BIN:-$HOME/.local/bin}"
EXTRA="${SHORTSFLOW_EXTRA:-clip}"

say() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Python 3.10 or newer
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$cand"; break
    fi
done
[ -n "$PY" ] || fail "Python 3.10 or newer is needed. macOS: brew install python. Ubuntu/Debian: sudo apt install python3 python3-venv"
say "Using $($PY --version)"

# 2. FFmpeg (the one thing pip cannot bring)
if ! command -v ffmpeg >/dev/null 2>&1; then
    say "FFmpeg is not installed. Install it, then run this again:"
    say "  macOS:          brew install ffmpeg"
    say "  Ubuntu/Debian:  sudo apt install ffmpeg"
    say "  Fedora:         sudo dnf install ffmpeg"
    exit 1
fi

# 3. Own environment, so nothing else on the computer is touched
say "Creating $HOME_DIR ..."
"$PY" -m venv "$HOME_DIR" || fail "Could not create a Python environment (on Ubuntu/Debian: sudo apt install python3-venv)"
"$HOME_DIR/bin/python" -m pip install --quiet --upgrade pip
say "Installing ShortsFlow (this downloads a few hundred MB; the speech model comes on first use) ..."
"$HOME_DIR/bin/python" -m pip install --upgrade "shortsflow[$EXTRA]"

# 4. A command on the PATH
mkdir -p "$BIN_DIR"
ln -sf "$HOME_DIR/bin/shortsflow" "$BIN_DIR/shortsflow"

say ""
say "Done. Check the setup:   $BIN_DIR/shortsflow doctor"
say "Clip a video:            $BIN_DIR/shortsflow clip my_video.mp4"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "Note: $BIN_DIR is not on your PATH yet. Add this to your shell profile:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
