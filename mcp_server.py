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

TOOLS_DEFINITIONS = [
    {
        "name": "generate_short",
        "description": "Generate an AI Short video (Facts, Explainer, Podcast, Story, WYR, Dubbing, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Content mode: FACTS, EXPLAINER, STORY, WYR, TOP_5, CHAT_STORY, PODCAST, HORROR, TRUE_CRIME, BIBLE, ARTICLE, UGC, DUB, EMOJI_GUESS, REDDIT, TRIVIA, QUOTE",
                    "default": "FACTS"
                },
                "category": {
                    "type": "string",
                    "description": "Topic or category (e.g. 'space mysteries', 'quantum physics', 'psychology')",
                    "default": "space mysteries"
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed prompt or script context for AI generation"
                },
                "script": {
                    "type": "string",
                    "description": "Custom manual script to use directly (skips LLM generation)"
                },
                "vibe": {
                    "type": "string",
                    "enum": ["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"],
                    "default": "suspense"
                },
                "use_remotion": {
                    "type": "boolean",
                    "description": "Use React-based Remotion subtitle engine for dynamic spring animations",
                    "default": True
                },
                "caption_style": {
                    "type": "string",
                    "enum": ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"],
                    "default": "HORMOZI"
                },
                "tts_provider": {
                    "type": "string",
                    "enum": ["edge-tts", "elevenlabs", "voicestudio", "gtts"],
                    "default": "edge-tts"
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["9:16", "16:9", "1:1", "4:5"],
                    "default": "9:16"
                },
                "auto_ducking": {
                    "type": "boolean",
                    "description": "Automatically duck background music when voice audio plays",
                    "default": True
                },
                "sfx_preset": {
                    "type": "string",
                    "enum": ["none", "pop", "whoosh", "chime", "riser", "boom"],
                    "default": "whoosh"
                },
                "target_lang": {
                    "type": "string",
                    "description": "Language code for translation/dubbing (e.g., 'es', 'fr', 'de', 'ja')"
                }
            },
            "required": []
        }
    },
    {
        "name": "extract_clips",
        "description": "Extract vertical viral shorts from a long video or YouTube URL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_video": {
                    "type": "string",
                    "description": "YouTube video URL or local video file path"
                },
                "clip_count": {
                    "type": "integer",
                    "description": "Number of viral shorts to extract",
                    "default": 3
                },
                "smart_crop": {
                    "type": "boolean",
                    "description": "Enable AI face and subject tracking crop for 9:16 vertical video",
                    "default": True
                },
                "tighten": {
                    "type": "boolean",
                    "description": "Automatically trim silence gaps for punchy high retention",
                    "default": True
                },
                "layout": {
                    "type": "string",
                    "enum": ["single", "split"],
                    "default": "single",
                    "description": "Single speaker crop or dual-speaker top/bottom split screen layout for podcasts"
                },
                "use_remotion": {
                    "type": "boolean",
                    "default": True
                },
                "caption_style": {
                    "type": "string",
                    "default": "HORMOZI"
                }
            },
            "required": ["source_video"]
        }
    },
    {
        "name": "generate_social_package",
        "description": "Generate viral social media titles, descriptions, hashtags, and hooks for YouTube Shorts, TikTok, and Instagram Reels",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or title of the video"
                },
                "category": {
                    "type": "string",
                    "default": "general"
                },
                "mode": {
                    "type": "string",
                    "default": "FACTS"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "get_render_status",
        "description": "Check the progress and status of a video rendering job",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The unique job ID returned by generate_short or extract_clips"
                }
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "list_supported_modes",
        "description": "List all available content generation modes, TTS engines, caption styles, and aspect ratios",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

def run_main_command(job_id: str, args_list: list):
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "processing", "progress": 0, "logs": [], "output": None}

    cmd = [sys.executable, "main.py", "--video_id", job_id, "--skip_upload"] + args_list
    print(f"[MCP Worker] Starting command: {' '.join(cmd)}", file=sys.stderr)

    try:
        process = subprocess.Popen(
            cmd,
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
                # Check for output mp4 files
                JOBS[job_id]["output"] = f"interactive_short_{job_id}.mp4"
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
        if args.get("target_lang"):
            cli_args.extend(["--target_lang", args["target_lang"]])

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
        except Exception as e:
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
            "content_modes": [
                "FACTS", "EXPLAINER", "STORY", "WYR", "TOP_5", "CHAT_STORY", "PODCAST",
                "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC", "DUB", "EMOJI_GUESS",
                "REDDIT", "TRIVIA", "QUOTE", "NEWS", "RIDDLE"
            ],
            "caption_styles": ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"],
            "tts_providers": ["edge-tts", "elevenlabs", "voicestudio", "gtts"],
            "aspect_ratios": ["9:16", "16:9", "1:1", "4:5"],
            "sfx_presets": ["none", "pop", "whoosh", "chime", "riser", "boom"]
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
                            "version": "2.5.0"
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

if __name__ == "__main__":
    main()
