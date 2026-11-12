# ShortsFlow Launch Drafts

Post from your own accounts. Edit freely - keep the honest tone; HN and Reddit punish hype.
Best timing: Show HN on a weekday morning US Eastern; stay around for the first 2 hours to answer comments.

## Before you post (checklist)

- [ ] `pip install shortsflow` works in a fresh venv; `shortsflow doctor` is green; `shortsflow clip some_video.mp4` makes shorts with no keys
- [ ] The Windows installer (`ShortsFlow-Setup-<version>.exe` on the latest GitHub release) has been run end to end on a PC that is not yours (or a fresh VM) and made a short; note the SmartScreen "More info > Run anyway" step in your post
- [ ] The daily channel workflow is green again (Groq model fix, 2026-11-03)
- [ ] GHCR package `ghcr.io/ghost1412/shortsflow` is public and `docker run` starts the WebUI
- [ ] Colab notebook runs top to bottom
- [ ] `pip install -U edge-tts` (Edge TTS breaks when Microsoft rotates its token)
- [ ] CI badge on the README is green
- [ ] README demo GIFs load; the clipping GIF credits its CC BY-SA source

## What is new since the first drafts (use these as the hook)

- **One-click Windows install** (no Python, Node or API key first): download `ShortsFlow-Setup` from the Releases page, open ShortsFlow, paste a link or drop a video, press one button. Unsigned (SmartScreen warning), roughly 2 GB download (about 5 GB with an NVIDIA card), CPU works but is slow
- **`shortsflow clip VIDEO_OR_LINK`**: one command, no API key; plain-language error messages and a friendlier `shortsflow doctor`
- **Beginner browser tab** ("Start here"): link or upload, how many shorts, one button, plain progress ("Listening to the video...", "Finding the best moments...")
- Still-image avatars now render as cut-outs (the green screen is removed)
- `pip install shortsflow`, then `shortsflow init` / `shortsflow doctor`
- Prompt-based clipping: `--find "where they discuss pricing"` clips only the moments that match
- Edit the video by editing its transcript: `--cut "you know"` or delete words in `transcript.txt` and re-run with `--edit_transcript`
- `--remove_fillers` cuts um/uh/er; `--tighten` removes silences
- Active-speaker layout now uses a face detector (YuNet) plus voice-pitch diarisation instead of mouth motion alone
- REST API with a job queue, API keys and signed webhooks (`shortsflow api`), plus an n8n example
- Brand kit: `--logo`, `--handle`, `--end_card`
- Fully local: Whisper on your GPU, Ollama for the LLM, Kokoro for the voice (`--tts_provider kokoro`); only stock footage needs a key

---

## 1. Show HN

**Title** (max 80 chars):
Show HN: ShortsFlow – open-source, local-first alternative to Opus Clip

**URL:** https://github.com/ghost1412/shortsflow

**Text:**
I built ShortsFlow to make vertical Shorts/Reels without paying per minute for clipping SaaS, and without uploading footage anywhere.

On Windows there is a one-click installer (no Python or API key needed): open it, paste a link or drop in a video, press a button. Otherwise `pip install shortsflow` (or Docker, or Colab) and `shortsflow clip my_video.mp4` works with no key at all. Under the hood:

- Whisper transcribes locally with word timestamps and an LLM scores the hooks. FFmpeg cuts 9:16 clips with face tracking, and captions are rendered with Remotion.
- `--find "where they discuss pricing"` clips only the moments that match your request.
- You can edit the video by editing its transcript: `--cut "you know"`, or delete words in the exported `transcript.txt` and re-run. The cuts are rendered into an edited copy and the captions are retimed to it.
- For podcasts, `--layout active` cuts to whoever is talking. It combines a face detector with voice-pitch clustering, because mouth motion alone was weak on real footage (on one real two-person interview, pitch got the speaker right for 92% of speaking time versus 45% for mouth motion).
- It can also generate from an idea (30+ formats: facts quizzes, Manim explainers, stories). That mode runs a YouTube channel, @spottheliee, from one GitHub Actions workflow.

It can run fully locally: Whisper on your GPU, Ollama for the LLM, Kokoro for the voice. There is a REST API with webhooks for automation (an n8n example is included) and an MCP server for agents. MIT licensed.

Honest limitations: the Windows installer is not code-signed yet (SmartScreen will warn you), it downloads around 2 GB (about 5 GB with an NVIDIA card), and on a CPU-only machine transcribing a long video is slow. It started as a script and grew, so parts are still being refactored. The pitch-based speaker switching needs the two voices to differ by roughly 20%, and I have only checked it on a few interviews. Filler removal and the publishing integration (Upload-Post) have had little testing on real footage, so treat them as experimental. Rendering a short takes a few minutes, and a GPU helps a lot.

I'd love feedback on clipping quality and on which features are worth keeping.

---

## 2. r/selfhosted

**Title:** ShortsFlow – self-hosted Opus Clip alternative: long videos to captioned Shorts (pip/Docker, local Whisper, MIT)

**Body:**
Hi r/selfhosted! I've been building an open-source tool for making vertical short-form video without uploading footage to a SaaS.

- **Clipping**: YouTube link or local file → local Whisper → hook scoring → 9:16 clips with face tracking and animated captions
- **Ask for moments**: `--find "where they discuss pricing"`
- **Edit by transcript**: delete words from a text file and the video follows
- **Podcast mode**: cuts to the active speaker, or shows both stacked when it's unsure
- **Fully local**: Whisper on your GPU, Ollama for the LLM, Kokoro for the voice; only stock footage (Pexels) needs an API key, and only for the generate-from-a-topic mode
- **Automate it**: REST API with API keys and signed webhooks, n8n example included
- **Install**: a one-click Windows installer from the Releases page (unsigned, so SmartScreen warns), `pip install shortsflow` then `shortsflow clip video.mp4` (no API key needed for clipping), `docker run -p 7860:7860 ghcr.io/ghost1412/shortsflow`, or open the Colab

Repo: https://github.com/ghost1412/shortsflow

Feedback and issues welcome. ROADMAP.md lists what's open, and there are a few `good first issue` tickets.

*(Check the subreddit's self-promotion rules first; some require mod approval or a flair like "Release".)*

---

## 3. r/LocalLLaMA (angle: runs on local models)

**Title:** Open-source Shorts clipper that runs end-to-end on local models (Whisper + Ollama + Kokoro), with a REST API and MCP server

**Body:** Lead with the local stack: Whisper on the GPU, Ollama for hook scoring and `--find`, Kokoro for the voice. Mention the Gemini → Ollama → Hugging Face fallback order, and that a 7B model is enough for scoring but sometimes invents details in clip titles, so check them. Keep stock footage as the only cloud dependency.

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

Tagline: "Open-source Opus Clip - local Shorts from any video or idea"
Wait until the Colab notebook and Docker image are confirmed working; PH visitors won't install from source.
