#!/usr/bin/env python3
"""
ShortsFlow AI Studio - Browser WebUI (Gradio)
Runs locally, in Docker, on Google Colab or on Hugging Face Spaces.

    python webui.py               # http://localhost:7860
    python webui.py --share       # public gradio.live link (Colab)
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

import gradio as gr

ROOT = os.path.dirname(os.path.abspath(__file__))

GENERATE_MODES = [
    "AUTO", "FACTS", "STORY", "EXPLAINER", "WYR", "TOP_5", "CHAT_STORY", "HORROR",
    "TRUE_CRIME", "REDDIT", "TRIVIA", "QUOTE", "RIDDLE", "EMOJI_GUESS", "ODD_ONE_OUT",
    "NEWS", "BIBLE", "ARTICLE", "UGC", "FUNNY_EXPLAINER",
]
CAPTION_STYLES = ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "AUTO", "RANDOM"]
VIBES = ["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"]
ASPECTS = ["9:16", "16:9", "1:1", "4:5"]
LLM_PROVIDERS = ["auto", "gemini", "ollama", "openai", "anthropic", "deepseek", "groq", "openrouter"]


def _snapshot_videos():
    """All rendered .mp4 files main.py may write (project root and sessions/)."""
    patterns = [os.path.join(ROOT, "*.mp4"), os.path.join(ROOT, "sessions*", "**", "*.mp4")]
    files = {}
    for pattern in patterns:
        for path in glob.glob(pattern, recursive=True):
            if "TEMP_MPY" in path or "temp_segments" in path or os.path.basename(path).startswith(("preview_", "scene_clip_", "temp_", "seg_")):
                continue
            files[path] = os.path.getmtime(path)
    return files


def _run(cmd):
    """Run main.py, streaming its log; yields (log, videos) and finally the new videos."""
    before = _snapshot_videos()
    log = f"$ {' '.join(cmd)}\n\n"
    yield log, []

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env,
    )
    for line in proc.stdout:
        log += line
        yield log[-20000:], []
    proc.wait()

    after = _snapshot_videos()
    new = sorted(
        (p for p, m in after.items() if p not in before or m > before[p]),
        key=lambda p: after[p],
    )
    status = "✅ Done" if proc.returncode == 0 else f"❌ main.py exited with code {proc.returncode}"
    log += f"\n{status} - {len(new)} video(s) rendered.\n"
    yield log[-20000:], new


def _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider):
    args = ["--caption_style", caption_style, "--aspect_ratio", aspect_ratio,
            "--llm_provider", llm_provider, "--tts_provider", tts_provider, "--skip-upload"]
    if use_remotion:
        args.append("--use_remotion")
    return args


def clip_video(url, upload, clip_count, target_duration, layout, smart_crop, tighten, broll, srt,
               target_lang, caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider):
    source = upload or (url or "").strip()
    if not source:
        raise gr.Error("Paste a YouTube link or upload a video file.")
    cmd = [sys.executable, "main.py", "--source_video", source, "--extract_mode", "shorts",
           "--clip_count", str(int(clip_count)), "--target_duration", str(int(target_duration)),
           "--layout", layout]
    for flag, on in (("--smart_crop", smart_crop), ("--tighten", tighten), ("--broll", broll), ("--srt", srt)):
        if on:
            cmd.append(flag)
    if target_lang:
        cmd += ["--target_lang", target_lang.strip()]
    cmd += _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider)
    yield from _run(cmd)


def generate_short(mode, category, prompt, script, vibe, voice, caption_style, aspect_ratio,
                   use_remotion, llm_provider, tts_provider):
    cmd = [sys.executable, "main.py", "--mode", mode, "--vibe", vibe]
    for flag, value in (("--category", category), ("--prompt", prompt), ("--script", script), ("--voice", voice)):
        if value and value.strip():
            cmd += [flag, value.strip()]
    cmd += _common_args(caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider)
    yield from _run(cmd)


def setup_status():
    """Markdown checklist of what is ready on this machine (same checks as `shortsflow doctor`)."""
    from shortsflow import onboarding, workspace
    try:
        return onboarding.checklist_markdown(workspace.doctor(ROOT))
    except Exception as e:  # never break the page over a diagnostics problem
        return f"Could not check the setup automatically ({e})."


def save_groq_key(key):
    from shortsflow import onboarding
    if onboarding.save_env_key(os.path.join(ROOT, ".env"), "GROQ_API_KEY", key):
        return "✅ Saved. AI titles and descriptions will use your free Groq key from the next run."
    return "⚠️ That does not look like a key. Copy it again from console.groq.com (no spaces)."


def quick_clip(url, upload, clip_count, captions):
    """The beginner flow: a video in, shorts out, with plain-language progress instead of a raw log."""
    from shortsflow import onboarding
    source = upload or (url or "").strip()
    if not source:
        raise gr.Error("Paste a video link or upload a video file first.")
    cmd = [sys.executable, "main.py", "--source_video", source, "--extract_mode", "shorts",
           "--clip_count", str(int(clip_count)), "--smart_crop", "--tighten", "--skip-upload"]
    if captions:
        cmd += ["--use_remotion", "--caption_style", "HORMOZI"]
    progress, seen = onboarding.Progress(), 0
    status = progress.message
    yield status, [], ""
    log, videos = "", []
    for log, videos in _run(cmd):
        lines = log.splitlines()
        for line in lines[seen:]:
            status = progress.feed(line)
        seen = len(lines)
        yield status, videos, log
    if not videos and not status.startswith("⚠️"):
        status = "❌ No shorts were made. Open 'Technical details' below for the reason, or check the setup list above."
    yield status, videos, log


def _render_settings():
    with gr.Accordion("Render settings", open=False):
        with gr.Row():
            caption_style = gr.Dropdown(CAPTION_STYLES, value="HORMOZI", label="Caption style")
            aspect_ratio = gr.Dropdown(ASPECTS, value="9:16", label="Aspect ratio")
        with gr.Row():
            llm_provider = gr.Dropdown(LLM_PROVIDERS, value="auto", label="LLM provider")
            tts_provider = gr.Dropdown(["auto", "edgetts", "elevenlabs", "voicestudio", "local"],
                                       value="auto", label="Voice (TTS) provider")
        use_remotion = gr.Checkbox(value=True, label="Remotion animated captions (needs Node.js)")
    return [caption_style, aspect_ratio, use_remotion, llm_provider, tts_provider]


def build_ui():
    with gr.Blocks(title="ShortsFlow AI Studio", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            "# ⚡ ShortsFlow AI Studio\n"
            "Open-source, local-first Opus Clip alternative. "
            "[GitHub](https://github.com/ghost1412/shorts-generator) · ⭐ Star if it helps!"
        )
        with gr.Tabs():
            with gr.Tab("🚀 Start here"):
                gr.Markdown("### Make shorts from a video in one click\n"
                            "No account or API key is needed for this. Paste a link or upload a video, then press the button.")
                with gr.Row():
                    with gr.Column():
                        q_url = gr.Textbox(label="Video link (YouTube or other)", placeholder="https://www.youtube.com/watch?v=...")
                        q_upload = gr.File(label="...or upload a video from your computer", file_types=["video"], type="filepath")
                        q_count = gr.Slider(1, 10, value=3, step=1, label="How many shorts?")
                        q_captions = gr.Checkbox(value=bool(shutil.which("node")), label="Add animated captions",
                                                 info="Needs Node.js (nodejs.org). Untick if it is not installed.")
                        q_btn = gr.Button("✨ Make my shorts", variant="primary")
                    with gr.Column():
                        q_status = gr.Markdown("Waiting for a video...")
                        q_videos = gr.Files(label="Your shorts")
                with gr.Accordion("Is my computer ready?", open=False):
                    q_check = gr.Markdown(setup_status())
                    gr.Button("Check again").click(setup_status, None, q_check)
                with gr.Accordion("Want AI-written titles and descriptions? (optional, free)", open=False):
                    gr.Markdown("Get a free key at [console.groq.com](https://console.groq.com) (sign in, then *API Keys*), paste it here and save. "
                                "You can skip this; your shorts are made either way.")
                    q_key = gr.Textbox(label="Groq API key", type="password", placeholder="gsk_...")
                    q_key_msg = gr.Markdown()
                    gr.Button("Save key").click(save_groq_key, q_key, q_key_msg)
                with gr.Accordion("Technical details", open=False):
                    q_log = gr.Textbox(label="Full log", lines=14, max_lines=14, autoscroll=True)
                q_btn.click(quick_clip, [q_url, q_upload, q_count, q_captions], [q_status, q_videos, q_log])

            with gr.Tab("✂️ Clip (advanced)"):
                with gr.Row():
                    with gr.Column():
                        url = gr.Textbox(label="YouTube / video URL", placeholder="https://www.youtube.com/watch?v=...")
                        upload = gr.File(label="...or upload a video", file_types=["video"], type="filepath")
                        with gr.Row():
                            clip_count = gr.Slider(1, 15, value=3, step=1, label="Number of clips")
                            target_duration = gr.Slider(15, 90, value=30, step=5, label="Target length (s)")
                        layout = gr.Radio(["single", "active", "split"], value="single", label="Framing",
                                          info="active = cut to whoever is talking (podcasts, interviews)")
                        with gr.Row():
                            smart_crop = gr.Checkbox(value=True, label="Face-tracking 9:16 crop")
                            tighten = gr.Checkbox(value=True, label="Remove silences")
                            broll = gr.Checkbox(label="Auto B-roll")
                            srt = gr.Checkbox(label="Export .srt")
                        target_lang = gr.Textbox(label="Dub to language (not implemented yet, ignored)")
                        clip_settings = _render_settings()
                        clip_btn = gr.Button("Find viral clips", variant="primary")
                    with gr.Column():
                        clip_videos = gr.Files(label="Rendered clips")
                        clip_log = gr.Textbox(label="Log", lines=22, max_lines=22, autoscroll=True)
                clip_btn.click(
                    clip_video,
                    [url, upload, clip_count, target_duration, layout, smart_crop, tighten, broll, srt, target_lang, *clip_settings],
                    [clip_log, clip_videos],
                )

            with gr.Tab("🪄 Generate from an idea"):
                with gr.Row():
                    with gr.Column():
                        mode = gr.Dropdown(GENERATE_MODES, value="FACTS", label="Mode")
                        category = gr.Textbox(label="Topic / category", placeholder="space mysteries")
                        prompt = gr.Textbox(label="Prompt (optional)", lines=2,
                                            placeholder="Explain how black holes bend light")
                        script = gr.Textbox(label="Your own script (optional, skips the LLM)", lines=4)
                        with gr.Row():
                            vibe = gr.Dropdown(VIBES, value="suspense", label="Music vibe")
                            voice = gr.Textbox(label="Voice (optional)", placeholder="en-US-GuyNeural")
                        gen_settings = _render_settings()
                        gen_btn = gr.Button("Generate short", variant="primary")
                    with gr.Column():
                        gen_videos = gr.Files(label="Rendered video")
                        gen_log = gr.Textbox(label="Log", lines=22, max_lines=22, autoscroll=True)
                gen_btn.click(
                    generate_short,
                    [mode, category, prompt, script, vibe, voice, *gen_settings],
                    [gen_log, gen_videos],
                )

        gr.Markdown("API keys are read from `.env` (`GEMINI_API_KEY`, `PEXELS_API_KEY`, ...). "
                    "See `env.example`. Nothing is uploaded unless you run `main.py` without `--skip-upload`.")
    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShortsFlow AI Studio WebUI")
    parser.add_argument("--host", default=os.getenv("WEBUI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEBUI_PORT", "7860")))
    parser.add_argument("--share", action="store_true", help="Create a public gradio.live link (useful on Colab).")
    cli = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass

    build_ui().queue(default_concurrency_limit=1).launch(
        server_name=cli.host, server_port=cli.port, share=cli.share
    )
