# ShortsFlow Launch Drafts

Post from your own accounts. Edit freely - keep the honest tone; HN and Reddit punish hype.
Best timing: Show HN on a weekday morning US Eastern; stay around for the first 2 hours to answer comments.

---

## 1. Show HN

**Title** (max 80 chars):
Show HN: ShortsFlow – open-source, self-hosted alternative to Opus Clip

**URL:** https://github.com/ghost1412/shorts-generator

**Text:**
I built ShortsFlow to make vertical Shorts/Reels without paying per-minute for clipping SaaS.

Two things it does:

1. Clip long videos: paste a YouTube link or file. Whisper transcribes it locally, an LLM scores hooks, and FFmpeg cuts 9:16 clips with face tracking. For podcasts, `--layout active` cuts to whoever is talking (mouth motion weighted by audio loudness, 2.5 s minimum shot length, stacked split when it's unsure). Captions are rendered with Remotion (React).

2. Generate from an idea: 30+ formats (facts quizzes, explainers rendered with Manim, Reddit-style stories, top-5 lists). The LLM writes the script, Edge TTS or ElevenLabs voices it, and Pexels supplies the footage.

It runs in production: the YouTube channel @spottheliee is generated and posted entirely by one GitHub Actions workflow, 6 videos a day.

Ways to run it: a browser UI (Gradio), Docker, a Colab notebook with a free GPU, a CLI, and an MCP server so Claude/Cursor can drive it. The LLM falls back from Gemini to Ollama to Hugging Face, so it can run fully locally. MIT licensed.

Honest limitations: it's a Python script that grew organically and is mid-refactor. Active-speaker detection uses OpenCV Haar cascades, not a learned model. Rendering a short takes a few minutes on CPU.

I'd love feedback on the clipping quality and on which formats are worth keeping.

---

## 2. r/selfhosted

**Title:** ShortsFlow – self-hosted Opus Clip alternative: turn long videos into captioned Shorts (Docker, local Whisper, MIT)

**Body:**
Hi r/selfhosted! I've been building an open-source tool for making vertical short-form video without uploading footage to a SaaS.

- **Clipping**: YouTube link or local file → local Whisper transcription → hook scoring → 9:16 clips with face tracking and animated captions
- **Podcast mode**: cuts to the active speaker, or shows both stacked when it's unsure
- **Generate from a topic**: script → TTS → stock footage → render (30+ formats)
- **Fully local**: Ollama is supported for the LLM step and Whisper runs on your GPU; only stock footage (Pexels) needs an API key
- **Deploy**: `docker run -p 7860:7860 ghcr.io/ghost1412/shorts-generator` → browser UI at :7860

It runs my own YouTube channel unattended (6 videos/day from GitHub Actions).

Repo: https://github.com/ghost1412/shorts-generator

Feedback and issues welcome. ROADMAP.md lists what I'm working on, and there are a few `good first issue` tickets.

*(Check the subreddit's self-promotion rules first; some require mod approval or a flair like "Release".)*

---

## 3. r/LocalLLaMA (angle: runs on local models)

**Title:** Made a Shorts generator that runs end-to-end on local models (Ollama + Whisper), with an MCP server for agents

**Body:** Same as above, but lead with the Ollama fallback, local Whisper and the MCP server. Keep stock footage as the only cloud dependency.

---

## 4. MCP directories

Short description (reuse everywhere):
> ShortsFlow MCP server: generate vertical Shorts from a topic or clip viral moments out of a YouTube video. Tools: generate_short, extract_clips (face tracking / active-speaker layout), get_render_status, generate_social_package, list_supported_modes. Local-first, MIT.

- **awesome-mcp-servers** (github.com/punkpeye/awesome-mcp-servers): open a PR adding one line under a media/video category:
  `- [ghost1412/shorts-generator](https://github.com/ghost1412/shorts-generator) 🐍 🏠 - Generate Shorts from topics or clip YouTube videos into captioned vertical shorts.`
- **Smithery** (smithery.ai): sign in with GitHub → "Add server" → point at the repo (`mcp_server.py`, stdio).
- **Glama** (glama.ai/mcp/servers): "Add server" with the repo URL.

---

## 5. Product Hunt (optional, later)

Tagline: "Open-source Opus Clip - self-hosted Shorts from any video or idea"
Wait until the Colab notebook and Docker image are confirmed working; PH visitors won't install from source.
