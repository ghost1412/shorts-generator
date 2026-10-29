---
name: shortsflow
description: Create vertical short-form videos (YouTube Shorts, TikTok, Reels) with ShortsFlow AI Studio - clip viral moments out of a long video or YouTube link, or generate a narrated short from a topic. Use when the user asks to make shorts, clip a podcast/video, add animated captions, or batch-produce faceless content.
---

# ShortsFlow AI Studio

Local-first pipeline: Whisper transcription → LLM hook scoring → face-tracked 9:16 crop → Remotion animated captions → FFmpeg render.

## Setup (once)

```bash
git clone --depth 1 https://github.com/ghost1412/shorts-generator.git && cd shorts-generator
pip install -r requirements-full.txt        # or requirements.txt for idea-to-video modes only
cd remotion-video && npm install && cd ..
cp env.example .env                         # set GEMINI_API_KEY (or use --llm_provider ollama)
```

Requires Python 3.12+, Node.js 18+ and FFmpeg on PATH.

## Clip a long video

```bash
python main.py --source_video "<youtube url or local file>" --extract_mode shorts \
  --clip_count 3 --smart_crop --tighten --use_remotion --caption_style HORMOZI --skip-upload
```

Useful flags: `--target_duration 30`, `--srt`, `--broll`, `--target_lang es` (dub), `--output_json result.json` (transcript, clips, scores, hooks).

## Generate a short from an idea

```bash
python main.py --mode FACTS --category "space mysteries" --vibe suspense --use_remotion --skip-upload
python main.py --mode EXPLAINER --prompt "Explain how gravity works visually" --skip-upload
```

Modes: FACTS, STORY, EXPLAINER, WYR, TOP_5, CHAT_STORY, HORROR, TRUE_CRIME, REDDIT, TRIVIA, QUOTE, RIDDLE, EMOJI_GUESS, NEWS, ARTICLE, UGC, PODCAST, DUB, AUTO.

## Rules

- Always pass `--skip-upload` unless the user explicitly asks to publish.
- Output files are `interactive_short_<id>.mp4` in the project root (or the `--session_dir`), each with a `.txt` / `.meta.json` caption package.
- LLM fallback order is Gemini → Ollama → HuggingFace; choose explicitly with `--llm_provider` / `--llm_model`.
- For agents that speak MCP, prefer `python mcp_server.py` (tools: `generate_short`, `extract_clips`, `get_render_status`, `generate_social_package`, `list_supported_modes`).
