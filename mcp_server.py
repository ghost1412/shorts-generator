#!/usr/bin/env python3
"""
ShortsFlow AI Studio - Model Context Protocol (MCP) Server
Allows AI Agents (Claude Desktop, Cursor, Antigravity, n8n, AutoGPT, etc.)
to trigger AI Shorts generation, clipping, and social metadata creation autonomously over stdio.
"""

import sys
import os
import json
import subprocess
import threading
import uuid
from typing import Dict, Any

# Ensure stdout uses UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Active jobs tracking
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
# AI tools start this server from any working directory, so find main.py (and run it) relative to this file, not to the caller
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _server_version():
    """The ShortsFlow version (so the MCP handshake does not report a stale number)."""
    try:
        import re
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shortsflow", "__init__.py"), encoding="utf-8") as f:
            return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
    except Exception:
        return "0.2.0"

CONTENT_MODES = ["FACTS", "EXPLAINER", "STORY", "WYR", "TOP_5", "CHAT_STORY", "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC",
                 "EMOJI_GUESS", "REDDIT", "TRIVIA", "QUOTE", "NEWS", "RIDDLE"]
CAPTION_STYLES = ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "AUTO", "RANDOM"]
TTS_PROVIDERS = ["auto", "edgetts", "elevenlabs", "voicestudio", "local", "kokoro"]
ASPECT_RATIOS = ["9:16", "16:9", "1:1", "4:5"]
SFX_PRESETS = ["auto", "whoosh", "pop", "riser", "boom", "none"]
VIBES = ["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"]

_CAPTION_HELP = ("Animated caption look (needs use_remotion): HORMOZI = bold yellow single words, GLOW_BOX = words in boxes with a "
                 "pink highlight, BOUNCE = bouncy gold single words, MINIMAL = clean dark boxes, AUTO/RANDOM = pick for me.")

TOOLS_DEFINITIONS = [
    {
        "name": "generate_short",
        "description": (
            "Create an original vertical short video from an idea: an AI-written script, voice-over, stock footage, background "
            "music and animated captions, rendered locally by the ShortsFlow pipeline. It runs in the background: the call "
            "returns a job_id immediately and the render takes a few minutes, so poll get_render_status until the job is "
            "'completed' or 'failed'. It uses the user's own LLM, voice and stock-footage keys from the ShortsFlow .env, writes "
            "files only inside the ShortsFlow folder, and never uploads or posts anything. Use this to make a new short from a "
            "topic; use extract_clips instead to cut shorts out of an existing video."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string", "enum": CONTENT_MODES, "default": "FACTS",
                    "description": ("Content format. FACTS = a 'spot the lie' quiz of three claims; STORY / HORROR / TRUE_CRIME = "
                                    "narrated stories; EXPLAINER = an animated explainer; WYR = 'would you rather'; TOP_5 = a ranked "
                                    "list; TRIVIA / RIDDLE / EMOJI_GUESS = quiz formats; NEWS = a news recap; others as named.")},
                "category": {
                    "type": "string", "default": "space mysteries",
                    "description": "Topic or category the script should be about, e.g. 'space mysteries', 'ancient Rome', 'psychology'."},
                "prompt": {
                    "type": "string",
                    "description": "Optional extra instructions or context for the script writer, e.g. 'Explain how black holes bend light'."},
                "script": {
                    "type": "string",
                    "description": "Optional finished script to narrate as written. When given, no AI script is generated."},
                "vibe": {"type": "string", "enum": VIBES, "default": "suspense", "description": "Mood of the background music."},
                "use_remotion": {
                    "type": "boolean", "default": True,
                    "description": "Render animated captions with the Remotion engine (needs Node.js). False uses simple captions."},
                "caption_style": {"type": "string", "enum": CAPTION_STYLES, "default": "HORMOZI", "description": _CAPTION_HELP},
                "tts_provider": {
                    "type": "string", "enum": TTS_PROVIDERS, "default": "auto",
                    "description": ("Voice-over engine. auto picks the best available; edgetts is free; kokoro and local run fully "
                                    "offline; elevenlabs and voicestudio need their own setup.")},
                "aspect_ratio": {"type": "string", "enum": ASPECT_RATIOS, "default": "9:16",
                                 "description": "Output shape: 9:16 vertical (Shorts, Reels, TikTok), 16:9, 1:1 or 4:5."},
                "auto_ducking": {"type": "boolean", "default": True,
                                 "description": "Lower the background music while the voice is speaking."},
                "sfx_preset": {"type": "string", "enum": SFX_PRESETS, "default": "auto",
                               "description": "Sound effects on visual transitions; none turns them off."},
            },
            "required": [],
        },
    },
    {
        "name": "extract_clips",
        "description": (
            "Cut the best moments out of a long video (a local file path or a YouTube link) into captioned vertical shorts: it "
            "transcribes the speech with Whisper, scores the moments, crops to 9:16 with face tracking and burns in animated "
            "captions. It runs in the background: the call returns a job_id immediately and the work can take several minutes "
            "(longer on a computer without an NVIDIA GPU), so poll get_render_status until the job is 'completed' or 'failed'. "
            "Clipping works without any API key; an AI key only improves scoring and titles. Files are written under the "
            "ShortsFlow folder (sessions/...) and nothing is uploaded. Use generate_short instead to create a video from a topic."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_video": {"type": "string",
                                 "description": "Local video file path or a YouTube/other video URL to clip. Required."},
                "clip_count": {"type": "integer", "default": 3, "minimum": 1,
                               "description": "How many shorts to cut out."},
                "smart_crop": {"type": "boolean", "default": True,
                               "description": "Follow the speaker's face when cropping the wide video to vertical."},
                "tighten": {"type": "boolean", "default": True,
                            "description": "Cut out silences and dead air inside each short."},
                "layout": {"type": "string", "enum": ["single", "split", "active", "fit"], "default": "single",
                           "description": ("Framing: single = face-tracked crop; split = two speakers stacked; active = cut to "
                                           "whoever is talking (stacked when unsure), best for podcasts and interviews; fit = the whole picture centred over a "
                                           "blurred copy of itself, nothing cropped off the sides (screen recordings, gameplay).")},
                "use_remotion": {"type": "boolean", "default": True,
                                 "description": "Animated captions (needs Node.js). False renders without animated captions."},
                "caption_style": {"type": "string", "enum": CAPTION_STYLES, "default": "HORMOZI", "description": _CAPTION_HELP},
                "language": {"type": "string", "default": "en",
                             "description": "Language spoken in the video (en, hi, es, fr, ...; 'auto' detects it)."},
                "auto_edit": {"type": "string", "enum": ["podcast", "hype", "educational", "vlog"],
                              "description": "Edit like an editor: cuts, zooms, cutaways, teaser opening, colour and sound effects for this kind of video."},
                "edit_strength": {"type": "string", "enum": ["subtle", "medium", "hyped"], "default": "medium",
                                  "description": "With auto_edit: how much of the edit shows (subtle keeps it quiet, hyped uses everything)."},
            },
            "required": ["source_video"],
        },
    },
    {
        "name": "generate_social_package",
        "description": (
            "Write platform-ready text for a short: a title, description, hashtags and a short caption for YouTube Shorts, TikTok "
            "and Instagram Reels. It answers immediately (no job). It uses the configured AI model; if none is reachable it "
            "returns a generic template filled with the topic instead, so check the wording. It does not publish anything."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What the video is about, e.g. 'Why the sky is blue'. Required."},
                "category": {"type": "string", "default": "general",
                             "description": "Broad category used to pick hashtags, e.g. 'science' or 'history'."},
                "mode": {"type": "string", "enum": CONTENT_MODES, "default": "FACTS",
                         "description": "Format of the video, which shapes the tone of the text."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_render_status",
        "description": (
            "Check a background job started by generate_short or extract_clips. Returns a JSON object with status "
            "('processing', 'completed', 'failed' or 'not_found'), progress (0-100), the last log lines, and an error message "
            "(the last lines of the log) when the job failed. Jobs are remembered only while this server is running. "
            "Call it every 20-30 seconds until the status is no longer 'processing'. It changes nothing."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string",
                           "description": "The job_id returned by generate_short or extract_clips. Required."},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_supported_modes",
        "description": (
            "List the options the other tools accept: content modes for generate_short, caption styles, voice-over engines, "
            "aspect ratios and sound-effect presets. Instant, read-only, takes no input. Call it first if you are unsure "
            "which value to pass."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

def run_main_command(job_id: str, args_list: list):
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "processing", "progress": 0, "logs": [], "output": None}

    main_py = os.path.join(ROOT_DIR, "main.py")
    if not os.path.exists(main_py):
        # e.g. a minimal container that only serves tools/list: say so plainly instead of failing with a Python error
        with JOBS_LOCK:
            JOBS[job_id].update({"status": "failed", "error": "Rendering needs the full ShortsFlow checkout (main.py and its "
                                 "requirements). Clone https://github.com/ghost1412/shorts-generator and run mcp_server.py from it."})
        return
    cmd = [sys.executable, main_py, "--video_id", job_id, "--skip_upload"] + args_list
    results_json = None
    if "--source_video" in args_list and "--output_json" not in args_list:
        # the clipping pipeline reports where the finished clips are; read that instead of guessing a file name
        results_json = os.path.join(ROOT_DIR, "sessions", f"mcp_{job_id}.json")
        os.makedirs(os.path.dirname(results_json), exist_ok=True)
        cmd += ["--output_json", results_json]
    print(f"[MCP Worker] Starting command: {' '.join(cmd)}", file=sys.stderr)

    try:
        process = subprocess.Popen(
            cmd,
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        log_lines = []
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            cleaned = line.strip()
            log_lines.append(cleaned)
            print(f"[Job {job_id[:8]}] {cleaned}", file=sys.stderr)

        process.wait()

        with JOBS_LOCK:
            if process.returncode == 0:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["logs"] = log_lines[-20:]
                JOBS[job_id]["output"] = None
                if results_json and os.path.exists(results_json):
                    try:
                        with open(results_json, "r", encoding="utf-8") as f:
                            clips = json.load(f).get("clips", [])
                        paths = [c.get("video_path") for c in clips if c.get("video_path")]
                        JOBS[job_id]["outputs"] = paths
                        JOBS[job_id]["output"] = paths[0] if paths else None
                    except (OSError, ValueError):
                        pass
            else:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["error"] = "\n".join(log_lines[-10:])
    except Exception as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)

def handle_tool_call(tool_name: str, args: dict) -> dict:
    job_id = str(uuid.uuid4())[:8]

    if tool_name == "generate_short":
        cli_args = [
            "--mode", args.get("mode", "FACTS"),
            "--vibe", args.get("vibe", "suspense"),
            "--caption_style", args.get("caption_style", "HORMOZI")
        ]

        if args.get("category"):
            cli_args.extend(["--category", args["category"]])
        if args.get("prompt"):
            cli_args.extend(["--prompt", args["prompt"]])
        if args.get("script"):
            cli_args.extend(["--script", args["script"]])
        if args.get("use_remotion", True):
            cli_args.append("--use_remotion")
        if args.get("tts_provider"):
            cli_args.extend(["--tts_provider", args["tts_provider"]])
        if args.get("aspect_ratio"):
            cli_args.extend(["--aspect_ratio", args["aspect_ratio"]])
        if args.get("auto_ducking", True):
            cli_args.append("--auto_ducking")
        if args.get("sfx_preset"):
            cli_args.extend(["--sfx_preset", args["sfx_preset"]])

        thread = threading.Thread(target=run_main_command, args=(job_id, cli_args))
        thread.start()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "job_id": job_id,
                        "status": "processing",
                        "message": f"Short video generation started for mode '{args.get('mode', 'FACTS')}'."
                    }, indent=2)
                }
            ]
        }

    elif tool_name == "extract_clips":
        if not str(args.get("source_video", "")).strip():
            return {"isError": True, "content": [{"type": "text", "text": "extract_clips needs 'source_video' (a video URL or a file path)."}]}
        cli_args = [
            "--source_video", args["source_video"],
            "--extract_mode", "shorts",
            "--clip_count", str(args.get("clip_count", 3)),
            "--caption_style", args.get("caption_style", "HORMOZI")
        ]

        if args.get("smart_crop", True):
            cli_args.append("--smart_crop")
        if args.get("tighten", True):
            cli_args.append("--tighten")
        if args.get("use_remotion", True):
            cli_args.append("--use_remotion")
        if args.get("layout"):
            cli_args.extend(["--layout", args["layout"]])
        if args.get("language"):
            cli_args.extend(["--language", str(args["language"])])
        if args.get("auto_edit") in ("podcast", "hype", "educational", "vlog"):
            cli_args.extend(["--auto_edit", args["auto_edit"], "--edit_strength",
                             args.get("edit_strength") if args.get("edit_strength") in ("subtle", "medium", "hyped") else "medium"])

        thread = threading.Thread(target=run_main_command, args=(job_id, cli_args))
        thread.start()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "job_id": job_id,
                        "status": "processing",
                        "message": f"Viral clip extraction started for {args['source_video']}."
                    }, indent=2)
                }
            ]
        }

    elif tool_name == "generate_social_package":
        topic = args.get("topic", "General Video")
        category = args.get("category", "general")
        mode = args.get("mode", "FACTS")

        try:
            from engine.social_gen import generate_viral_metadata
            metadata = generate_viral_metadata([{"fact": topic}], mode=mode, category=category)
        except Exception:
            metadata = {
                "title": f"Unbelievable {topic} Revealed! 💥 #Shorts",
                "description": f"Check out this amazing video on {topic}! Like & Subscribe for more daily videos.",
                "hashtags": ["#Shorts", "#Viral", f"#{category.replace(' ', '')}", "#FYP"],
                "tiktok_caption": f"You won't believe this about {topic}! 😱 #fyp #viral #trending",
                "reels_caption": f"Tag a friend who needs to see this! 👇 {topic} #reels #explore"
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(metadata, indent=2)
                }
            ]
        }

    elif tool_name == "get_render_status":
        req_id = args.get("job_id", "")
        with JOBS_LOCK:
            job_info = JOBS.get(req_id, {"status": "not_found", "message": f"Job ID {req_id} not recognized."})

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(job_info, indent=2)
                }
            ]
        }

    elif tool_name == "list_supported_modes":
        info = {
            "content_modes": CONTENT_MODES,
            "caption_styles": CAPTION_STYLES,
            "tts_providers": TTS_PROVIDERS,
            "aspect_ratios": ASPECT_RATIOS,
            "sfx_presets": SFX_PRESETS,
            "vibes": VIBES,
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(info, indent=2)
                }
            ]
        }

    else:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]
        }

def main():
    """Reads JSON-RPC standard input line-by-line and writes responses to stdout."""
    print("[MCP Server] ShortsFlow AI Studio MCP Server listening on stdio...", file=sys.stderr)

    while True:
        req_id = None
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "ShortsFlow AI Studio MCP Server",
                            "version": _server_version()
                        }
                    }
                }
                print(json.dumps(resp), flush=True)

            elif method == "notifications/initialized":
                # Client acknowledging initialization
                pass

            elif method == "ping":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                print(json.dumps(resp), flush=True)

            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS_DEFINITIONS
                    }
                }
                print(json.dumps(resp), flush=True)

            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                tool_result = handle_tool_call(tool_name, arguments)

                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": tool_result
                }
                print(json.dumps(resp), flush=True)

            else:
                if req_id is not None:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
                    print(json.dumps(resp), flush=True)

        except Exception as e:
            print(f"[MCP Error] Exception handling request: {e}", file=sys.stderr)
            if req_id is not None:   # answer anyway: a client that gets no reply waits forever
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Internal error: {e}"}}), flush=True)

if __name__ == "__main__":
    main()
