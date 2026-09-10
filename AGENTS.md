# 🤖 ShortsFlow AI Studio - Agent Prompt & Onboarding Guide

> **System Prompt for AI Agents (Antigravity, Cursor, Claude Code, Copilot, AutoGPT, LLMs)**

Welcome Agent! This document provides structured architectural context, setup instructions, CLI capabilities, and operational guidelines for working with **ShortsFlow AI Studio** (`shorts-generator`).

---

## 🏗️ 1. Project Overview & Architecture

ShortsFlow AI Studio is an open-source, local-first AI video generator and automated clipping engine (an open-source alternative to Opus Clip).

### Tech Stack Components:
* **Core Pipeline (`main.py`)**: Slices, transcribes, scores hooks, crops 9:16 vertical video, and renders final shorts.
* **Transcription Engine (`Whisper / CUDA`)**: Local GPU-accelerated word-timestamped transcription.
* **Animation & Rendering Engine (`remotion-video/`)**: React-based video engine rendering high-retention spring captions (Hormozi, Glow Box, Bounce, Minimal).
* **Educational Explainer Engine (`Manim`)**: Renders programmatic 2D/3D math and computer science animations (`test_manim.py`).
* **Desktop Studio GUI (`gui_app.py`)**: Single-window 3-column CustomTkinter studio interface with live 9:16 video canvas preview.
* **Web Dashboard (`web/` & `server.py`)**: Next.js 15 App Router interface with Stripe/LemonSqueezy payments & YouTube OAuth.
* **Automated CI/CD Workflows (`.github/workflows/daily_generate.yml`)**: GitHub Action for scheduled autonomous short generation and social posting.

---

## ⚙️ 2. Quick Setup & Environment Commands

### Prerequisites Check
* **Python**: `3.12+`
* **Node.js**: `v18+` (Required for Remotion React video rendering)
* **FFmpeg**: Must be available in system `PATH`

### 1-Click Installation & GUI Launch
```bash
# Windows Setup & Interactive Launcher
setup.bat
launch.bat  # Select Option 1 for Desktop Studio GUI

# Launch GUI directly via Python:
python gui_app.py

# Linux / macOS
chmod +x setup.sh && ./setup.sh
python3 gui_app.py

# Docker Container
docker compose up -d
```

### Required `.env` File Schema
```env
GEMINI_API_KEY=your_gemini_key_here
HF_API_KEY=your_huggingface_key_here
PEXELS_API_KEY=your_pexels_key_here
```

---

## 🎬 3. Execution Commands & Skills Reference

### Skill 1: Extract Shorts from Long Videos or YouTube Links
```bash
python main.py \
  --source_video "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" \
  --extract_mode shorts \
  --clip_count 3 \
  --smart_crop \
  --tighten \
  --use_remotion \
  --caption_style HORMOZI
```

### Skill 2: Educational Math & Code Explainers (Manim)
```bash
python main.py \
  --mode EXPLAINER \
  --prompt "Explain how gravity works visually" \
  --skip-upload
```

### Skill 3: High-Retention AI Facts & Narrative Shorts
```bash
python main.py \
  --mode FACTS \
  --category "space mysteries" \
  --vibe "suspense" \
  --use_remotion \
  --caption_style GLOW_BOX
```

### Skill 4: Interactive Dilemma Challenges ("This or That")
```bash
python main.py \
  --mode WYR \
  --category "superpowers" \
  --use_remotion
```

### Skill 5: Launch Single-Window Interactive Studio GUI
```bash
# Launch visual CustomTkinter 3-column studio layout
python gui_app.py
```

---

## 📜 4. Engine Codebase Map

| File Path | Functional Role |
| :--- | :--- |
| `main.py` | Primary CLI entry point & global pipeline orchestrator |
| `gui_app.py` | Single-window 3-column CustomTkinter Desktop Studio application |
| `engine/media_gen.py` | Stock media downloader (Pexels API fallback), AI image generation |
| `engine/video_gen.py` | FFmpeg filters, face-tracking EMA, silence removal (`--tighten`) |
| `engine/remotion_renderer.py` | Bridge between Python pipeline and Node.js Remotion React renderer |
| `engine/voice_gen.py` | Text-to-Speech synthesizer (ElevenLabs / EdgeTTS) |
| `engine/script_gen.py` | Multi-LLM prompt orchestration (Gemini -> Ollama -> HuggingFace fallback) |
| `remotion-video/src/` | React video components & animated subtitle spring physics |

---

## 🛡️ 5. Operational Rules for AI Agents

1. **Repository Cleanliness**:
   * NEVER commit raw `.mp4` video outputs or binary assets from `assets/backgrounds/local/` into Git tracking.
   * Store temporary outputs inside `sessions/` or root directory (covered by `.gitignore`).
2. **Fallback Integrity**:
   * Always verify that `PEXELS_API_KEY` fallback works seamlessly when local background media is absent.
   * Maintain the Multi-LLM fallback order: **Gemini API -> Local Ollama -> HuggingFace**.
3. **Subtitles & Caption Positioning**:
   * Remotion captions use vertical `y_pos` offset defaulting to `1150` for 9:16 vertical resolution (1080x1920).
