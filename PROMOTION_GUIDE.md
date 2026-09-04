# ShortsFlow Promotion Guide

Here are optimized templates for X (Twitter) and Reddit to promote ShortsFlow.

## 🧵 X (Twitter) Thread Template

**Tweet 1 (The Hook & Visual Proof)**
Stop paying $20/mo for Opus Clip. 🛑

I just open-sourced ShortsFlow Studio — a fully autonomous, local AI engine that turns any long video or podcast into highly viral 9:16 Shorts. 

Check out the caption quality 🤯 👇 (Attach demo GIF 1 here)

**Tweet 2 (The Architecture)**
How it works under the hood:
1️⃣ Whisper/CUDA transcribes the video locally 
2️⃣ Gemini 3.7 (or local Ollama) analyzes narrative density to find the highest-retention hooks 
3️⃣ Exponential Moving Average (EMA) Face Tracking crops perfectly
4️⃣ Remotion React engine renders the final video

**Tweet 3 (The Visuals)**
I rebuilt the caption engine from scratch to mimic top-tier editors. 
We support 4 dynamic styles, including the viral "Hormozi" pop.
It even automatically ducks the background music when someone is speaking. 

**(Attach demo GIF 2 here)**

**Tweet 4 (Beyond Extraction)**
But it doesn't just clip podcasts. It’s an entire autonomous studio. 
It can generate videos from scratch:
- Manim Educational Explainers
- "This or That" Splitscreen challenges
- AI Voiceover story facts

**(Attach demo GIF 3 here)**

**Tweet 5 (The Call to Action)**
The entire project is 100% open-source on GitHub. 
I built a 1-click `setup.bat` so you can install and run it locally in under 60 seconds without messing with dependencies.

Star it, fork it, break it:
🔗 [Link to GitHub Repo]

---

## 👽 Reddit Templates

### For r/SideProject and r/Python

**Title:** I built an open-source Opus Clip alternative (Autonomous AI Video Studio)

**Body:**
Hey guys, I got tired of paying monthly subscriptions just to clip my podcasts and gaming videos into Shorts, so I built an entirely local, open-source alternative called **ShortsFlow Studio**.

Instead of using basic heuristic clipping, it uses a multi-LLM architecture (Gemini Flash or local Ollama) to analyze the actual narrative density and find the most viral "hooks".

**The Tech Stack:**
- **Python / FFmpeg** for the heavy lifting and media slicing
- **Whisper (CUDA accelerated)** for lightning-fast transcription
- **Remotion (React)** for rendering buttery smooth, modern "Hormozi-style" captions and transitions (instead of clunky MoviePy text).

I also built in some custom computer vision to track faces and apply Exponential Moving Average (EMA) smoothing, so the vertical crop never jitters. 

I made a 1-click Windows `setup.bat` so you don't even have to know how to install Python dependencies to try it out. 

Would love for you guys to tear it apart, contribute, or just use it to grow your channels. 

**Demo Video:** [Link to Demo]
**GitHub Repo:** [Link to GitHub Repo]

---

### For r/OpenSource

**Title:** ShortsFlow Studio: An open-source, AI-powered vertical video generator (Alternative to Opus Clip)

**Body:**
*Use the exact same body as above, but emphasize that you welcome PRs for new caption styles or LLM integrations.*
