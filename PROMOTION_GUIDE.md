# 🚀 ShortsFlow AI Studio — Social Proof & Launch Promotion Kit

> **Goal**: Reach **50–100 GitHub Stars** within 48 hours of posting high-quality demos on X (Twitter) and Reddit.

---

## 🎯 Strategic Positioning

**Core Tagline**: *"The open-source AI Video Studio that turns long YouTube videos into viral 9:16 Shorts on autopilot."*

**Key Differentiators to Highlight**:
1. **100% Open Source & Self-Hostable** (No $50/mo subscription like OpusClip or Captions.ai).
2. **Remotion React Engine** (Professional dynamic captions, spring pop animations, Hormozi styling).
3. **Manim Support** (Automated 3D educational math explainer animations).
4. **Dual LLM Architecture** (Cloud Gemini + Local Ollama for $0 offline processing).

---

## 📱 Twitter / X Launch Thread Template

### Tweet 1 (Hook + Video Demo)
```text
I built an open-source AI Video Studio that turns long-form YouTube videos into high-retention 9:16 Shorts in 1 click. ⚡

No subscription. Local Whisper + PyTorch GPU + Remotion React renderer.

Here is a before/after of a long podcast clip 🧵👇
[Attach demo_longform_to_short.mp4]
```

### Tweet 2 (How It Works & Tech Stack)
```text
How ShortsFlow works under the hood:

1. 📥 Ingests YouTube URL or local file (yt-dlp + persistent cache)
2. 🧠 Multimodal Signal Analysis (Whisper transcript + energy deltas + face tracking)
3. ✂️ Smart Re-framing (9:16 auto-crop with EMA anti-jitter smoothing + padded silence removal)
4. 🎨 Remotion Animation Engine (Word-by-word spring pop captions)
```

### Tweet 3 (Standalone AI Modes)
```text
It's not just a clipper — it also generates standalone shorts from scratch:

🧮 Math Explainers (Manim animations)
💡 Facts & Mystery Shorts
📖 AI Story Mode
🤔 Split-Screen This-or-That

Everything is scripted, voiced, and rendered automatically.
[Attach demo_mode_facts.mp4]
```

### Tweet 4 (Repository Link + Call to Action)
```text
ShortsFlow is 100% open source on GitHub.

Check out the code, run it locally with 1-click `launch.bat`, or build your own automated channel!

If you find it useful, a ⭐ on GitHub would mean the world!

GitHub Repo: https://github.com/ghost1412/shorts-generator
```

---

## Reddit Launch Posts

### 1. `r/Python` Post (Technical Focus)
**Title**: `I built an open-source Python system that auto-clips YouTube videos into 9:16 Shorts using PyTorch, Whisper & Remotion`

**Body**:
```text
Hey r/Python!

I wanted to share a project I've been working on: **ShortsFlow AI Studio**.

It's an autonomous video processing pipeline that takes long-form videos or YouTube links and extracts high-retention 9:16 Shorts.

**Tech Stack**:
- **Whisper + PyTorch CUDA**: For fast word-level timestamps & transcription.
- **Multimodal Signal Analysis**: Combines text keyword density, audio energy shifts, and OpenCV face tracking.
- **Remotion (React/Node.js)**: Subtitle rendering with Hormozi-style spring-pop animations.
- **CustomTkinter GUI**: Simple desktop interface for non-technical usage.
- **Manim CE**: Integrated for rendering educational math animations.

**How we solved camera jitter during 9:16 auto-cropping**:
We implemented an Exponential Moving Average (EMA) position smoother with velocity limits (max 30% width shift/sec) and deadband hysteresis so talking heads stay centered without camera shaking.

GitHub: https://github.com/ghost1412/shorts-generator

Would love feedback on the codebase and architecture!
```

---

### 2. `r/SideProject` Post (Product Focus)
**Title**: `ShortsFlow – Open-source alternative to OpusClip for creating viral Shorts`

**Body**:
```text
Hey everyone!

Tired of paying $30-$50/month for video clipping tools with strict monthly minute limits, I built an open-source solution: **ShortsFlow AI Studio**.

**What it does**:
1. Paste a YouTube URL or upload a video.
2. Select subtitle preset (`HORMOZI`, `GLOW_BOX`, `BOUNCE`, `MINIMAL`).
3. Click Generate!

It automatically detects the top moments, crops to 9:16, removes awkward silences, and renders word-by-word animated captions.

It also supports **Local Ollama LLMs**, so you can process videos 100% offline for $0.

Repository: https://github.com/ghost1412/shorts-generator

Check it out and let me know what features you'd like to see next!
```

---

### 3. `r/SelfHosted` Post (Privacy & Local LLM Focus)
**Title**: `ShortsFlow: Self-hostable AI Short generator with local Ollama + Whisper support`

**Body**:
```text
For anyone looking for a privacy-first video clipping tool: ShortsFlow can run completely offline without sending video data to third-party APIs.

- **Local Speech Recognition**: OpenAI Whisper (via local CUDA PyTorch).
- **Local Reasoning**: Integrates directly with Ollama (`qwen3:8b` / `llama3`).
- **No Cloud Subscription Required**.

Runs via Python CLI or Desktop CustomTkinter GUI.

GitHub: https://github.com/ghost1412/shorts-generator
```

---

## 🎬 2-Step Demo Video Production Plan

To create the 2 launch videos for your social posts:

1. **Demo Video 1: Long-Form to Short Extraction**
   - Take a popular podcast clip (e.g. tech podcast or interview).
   - Run: `python main.py --source_video "sample_podcast.mp4" --clip_count 1 --smart_crop --tighten --use_remotion --caption_style HORMOZI`
   - Yields a crisp 30s vertical short with Hormozi pop captions and smooth face tracking.

2. **Demo Video 2: Facts / Standalone Mode**
   - Run: `python main.py --mode FACTS --category "space mysteries" --use_remotion --caption_style GLOW_BOX`
   - Yields an animated facts short with split backgrounds and glassmorphic glowing captions.
