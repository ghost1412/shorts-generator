---
title: ShortsFlow AI Studio
emoji: ⚡
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
license: mit
short_description: Open-source Opus Clip alternative, try it on CPU
---

# ShortsFlow AI Studio (demo Space)

A CPU-only try-out of [ShortsFlow](https://github.com/ghost1412/shorts-generator): paste a video link or upload a short
video and get vertical shorts with animated captions.

- Runs on free CPU hardware, so it is slow and limited to short videos. For full speed (GPU transcription, Remotion
  captions, the recap engine) install it on your PC: `pip install "shortsflow[webui]"`.
- Uploaded videos are processed on this Space's server and are not kept after the session ends. Nothing is sent to other
  services unless you add an AI key yourself.
