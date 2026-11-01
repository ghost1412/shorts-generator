import os
import sys
import io
import time
import random
import argparse
import json
import re
import subprocess
from dotenv import load_dotenv

# 🟢 Force UTF-8 for all standard streams (fixes CP1252/Emoji crashes on Windows)
# Use line_buffering=True to prevent prints from different stages/threads from buffering and overlapping.
if sys.stdout.encoding != 'utf-8' or sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr.encoding != 'utf-8' or sys.platform == "win32":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from supabase import create_client, Client
from engine.utils import decrypt_secret, find_fact_start_times
from engine.pipeline import POOL_SIZE, VIBE_VOICE_MAP, CARTOON_VOICE_MAP, CARTOON_AUDIO_CONFIG, report_status, export_srt, print_clip_score_table

load_dotenv()

from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge, generate_odd_one_out_script, generate_riddle, generate_jwst_script
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx, fetch_jwst_images, is_url, download_source_video_from_url
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage





def parse_args():
    parser = argparse.ArgumentParser(description="Generate either FACTS, STORY, FIND_IT, WYR, REDDIT, TRIVIA, QUOTE, JWST, RIDDLE, ODD_ONE_OUT, or FILTER shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "WYR", "REDDIT", "TRIVIA", "QUOTE", "ODD_ONE_OUT", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "RIDDLE", "TREND", "CHALLENGE", "JWST", "TRAILER_MISSED", "MUSIC", "EXPLAINER", "FILTER", "EMOJI_GUESS", "PHOTO_REEL", "FUNNY_EXPLAINER", "TEACH", "DUB", "SPLIT_SCREEN", "PODCAST", "TOP_5", "CHAT_STORY", "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC", "AUTO"], help="Force a specific mode.")
    parser.add_argument("--scene", help="Scene or scenario prompt for FUNNY_EXPLAINER mode.")
    parser.add_argument("--photos_dir", help="Directory containing photos for PHOTO_REEL mode.")
    parser.add_argument("--music", help="Path to audio/music track for PHOTO_REEL or background music.")
    parser.add_argument("--smart_story", action="store_true", help="Use Multimodal Vision LLM to re-order photos into a narrative story arc and generate captions.")
    parser.add_argument("--prompt", help="Prompt for AI Music/Image generation.")
    parser.add_argument("--ckpt_name", default="stable_audio_3_medium_base.safetensors", help="Checkpoint name for ComfyUI audio model.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"], default="suspense", help="Select background music vibe.")
    parser.add_argument("--voice", help="Specify TTS voice (e.g. en-US-GuyNeural, en-US-ChristopherNeural, en-US-EricNeural, en-US-AnaNeural).")
    parser.add_argument("--user_id", help="The Supabase user ID triggering the generation.")
    parser.add_argument("--video_id", help="The unique ID for this video job.")
    parser.add_argument("--skip-upload", "--skip_upload", action="store_true", dest="skip_upload", help="Generate video but do not upload to social media.")
    parser.add_argument("--recap_title", help="Movie/Story title for MOVIE_RECAP mode.")
    parser.add_argument("--pinterest", action="store_true", help="Enable optional upload to Pinterest.")
    parser.add_argument("--instagram", action="store_true", help="Enable optional upload to Instagram.")
    parser.add_argument("--pinterest_link", help="Optional destination URL for Pinterest Pin (e.g. affiliate link).")
    
    # AI Extraction Flags (Long-form to Short-form)
    parser.add_argument("--source_video", help="Path to long-form source video for AI extraction")
    parser.add_argument("--extract_mode", choices=["shorts", "long"], default="shorts")
    parser.add_argument("--clip_count", type=int, default=5)
    parser.add_argument("--target_duration", type=int, default=30)
    parser.add_argument("--min_duration", type=int, default=15, help="Minimum clip duration for extraction (default 15s).")
    parser.add_argument("--session_dir", help="Reuse session for transcription.")
    parser.add_argument("--use_audio_detect", action="store_true", help="Use audio signals (energy/delta) for extraction.")
    parser.add_argument("--style", choices=["sarcastic", "meme", "funny", "action", "stylish"], action="append", help="Optional viral editing styles (can be used multiple times).")
    parser.add_argument("--find", help="Clip only moments matching this request, e.g. \"where they discuss pricing\" (clipping mode).")
    parser.add_argument("--user_context", help="Extra context to guide AI extraction (specific scenes/styles).")
    parser.add_argument("--style_context", help="Context for editing style and pacing (e.g. 'fast cuts', 'cinematic').")
    parser.add_argument("--gif_dir", help="Path to external GIF library (e.g. animated-gifs repo).")
    parser.add_argument("--hq", action="store_true", help="Enable High-Quality (Premium) enhancements (sharpening, color enhancement).")
    parser.add_argument("--superres", action="store_true", help="Enable Super-Resolution & Deinterlacing filter pipeline for legacy/VCD/VHS videos.")
    parser.add_argument("--video_filter", choices=["auto", "none", "dynamic", "kurosawa", "teal_orange", "cyberpunk", "cinematic_warm", "vibrant_action", "vintage_vhs", "moody_dark", "anime_vivid", "matrix_green", "sepia_western", "cold_thriller", "hdr_pop"], default="none", help="Visual color grade filter preset to apply (or 'auto' / 'dynamic' for AI auto-selection).")
    parser.add_argument("--use_cache", action="store_true", help="Reuse cached highlights and skip existing segments/rendered clips.")
    parser.add_argument("--mashup", action="store_true", help="Create a single mashup/remix video of all highlights instead of separate clips.")
    parser.add_argument("--mashup_mode", choices=["attach", "edit"], default="edit", help="Assembly style for mashup: 'attach' for simple concatenation, 'edit' for premium transition effects and background music.")
    
    parser.add_argument("--output_json", help="Path to write structured JSON results (transcript, clips, scores, hooks).")
    parser.add_argument("--batch_file", help="Path to text file containing list of video URLs or local files to process in batch.")
    parser.add_argument("--cookies_from_browser", default=None, help="Browser to extract cookies from for age-restricted videos (edge, chrome, firefox, brave).")
    parser.add_argument("--cookies", help="Path to cookies.txt file for YouTube authentication.")
    
    parser.add_argument("--use_comfy", action="store_true", help="Use local ComfyUI for premium AI backgrounds.")
    parser.add_argument("--use_ai_audio", action="store_true", help="Use local ComfyUI for premium AI music & SFX.")
    parser.add_argument("--bitrate", type=str, help="Manual bitrate override (e.g. 12000k)")
    parser.add_argument("--preset", type=str, help="Manual preset override (e.g. medium)")
    parser.add_argument("--quality", type=str, default="medium", choices=["low", "medium", "high", "ultra"], help="Output quality preset")
    
    # 🟢 Auto-Editor & AutoClip Flags
    parser.add_argument("--tighten", action="store_true", help="Remove silences from the final video.")
    parser.add_argument("--tighten_mode", choices=["cut", "speed"], default="cut", help="How to handle silences: 'cut' them or 'speed' them up.")
    parser.add_argument("--layout", choices=["single", "split", "active"], default="single", help="Vertical framing for clips: single (face/center crop), split (two speakers stacked), active (cut to whoever is talking, stacked when unsure).")
    parser.add_argument("--smart_crop", action="store_true", help="Enabled AI-powered face/interest tracking for vertical cropping.")
    parser.add_argument("--add_commentary", action="store_true", help="Generate an AI voiceover intro commentary hook for third-party clips to ensure 100%% YouTube policy compliance.")
    parser.add_argument("--show_banner", action="store_true", help="Overlay visual rounded header banner ('VIRAL MOMENT') on top of commentary intro clips.")
    
    # 🟢 Gap Closure Flags
    parser.add_argument("--srt", action="store_true", help="Export SRT subtitle file alongside each video.")
    parser.add_argument("--use_chapters", action="store_true", help="Boost scores for segments overlapping YouTube chapters.")
    parser.add_argument("--broll", action="store_true", help="Automatically download and insert B-roll cutaways during silences.")
    parser.add_argument("--preview", action="store_true", help="Render a low-res 3fps proxy video for quick preview.")
    
    # Cartoon/Persona Flags
    parser.add_argument("--cartoon", action="store_true", help="Enable cartoon-style news persona.")
    parser.add_argument("--persona", help="Select a specific cartoon persona (rabbit, robot, squirrel, superhero).")
    parser.add_argument("--use_remotion", action="store_true", help="Use Remotion engine instead of MoviePy for modern professional rendering.")
    parser.add_argument("--caption_style", default="HORMOZI", choices=["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "AUTO", "RANDOM"], help="Subtitle animation preset for Remotion renderer (default: HORMOZI).")
    parser.add_argument("--subtitle_y_pos", type=int, default=1150, help="Vertical pixel position for subtitles in Remotion (default: 1150).")
    parser.add_argument("--max_workers", type=int, default=None, help="Force number of parallel rendering worker threads (e.g. 2 or 4 for Remotion/FFmpeg).")
    
    # Provider & Media Overrides
    parser.add_argument("--use_ollama", action="store_true", help="Force local Ollama LLM execution.")
    parser.add_argument("--llm_provider", choices=["auto", "gemini", "ollama", "openai", "anthropic", "deepseek", "groq", "openrouter", "custom"], default="auto", help="Specify LLM provider (gemini, ollama, openai, anthropic, deepseek, groq, openrouter, custom).")
    parser.add_argument("--llm_model", help="Specify exact model name for the LLM provider (e.g., gpt-4o-mini, deepseek-chat, llama-3.3-70b-versatile, qwen3:8b).")
    parser.add_argument("--bg_media", help="Path to custom local background image (.jpg, .png) or video (.mp4, .mov).")
    
    # Interactive Kids Story Creator Flags
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI prompt to create kids characters.")
    parser.add_argument("--hero", help="Type of hero (e.g. teddy bear, friendly dragon).")
    parser.add_argument("--hero_name", help="Name of the hero (e.g. Luna).")
    parser.add_argument("--companion", help="Hero's companion (e.g. Twinkle the Pixie).")
    parser.add_argument("--quest", help="Hero's adventure quest.")
    # YouTube Multi-Account Flags
    parser.add_argument("--youtube_account", help="Select YouTube account slot (e.g. 1, 2, channel_b).")
    parser.add_argument("--youtube_token_file", help="Path to custom YouTube token.json file.")
    parser.add_argument("--youtube_secrets_file", help="Path to custom YouTube client_secrets.json file.")

    # Voice, Production & Aspect Ratio Flags
    parser.add_argument("--tts_provider", choices=["auto", "elevenlabs", "voicestudio", "edgetts", "local"], default="auto", help="Specify Text-to-Speech synthesis provider.")
    parser.add_argument("--clone_voice", help="Path to custom audio sample file (.wav, .mp3) for zero-shot voice cloning.")
    parser.add_argument("--aspect_ratio", choices=["9:16", "16:9", "1:1", "4:5"], default="9:16", help="Select output video aspect ratio (default 9:16 vertical).")
    parser.add_argument("--target_lang", help="Target language code for automatic video translation and dubbing (e.g. es, hi, de, fr, ja, pt).")
    parser.add_argument("--auto_ducking", action="store_true", help="Enable dynamic background music ducking during voice audio.")
    parser.add_argument("--sfx_preset", choices=["auto", "whoosh", "pop", "riser", "boom", "none"], default="auto", help="Select sound effects preset to overlay on visual transitions.")
    parser.add_argument("--enable_zoom", action="store_true", help="Apply smooth camera push-in zoom motion keyframing.")
    parser.add_argument("--enhance_audio", action="store_true", help="Apply studio audio mastering (highpass, noise gate, compressor, EBU R128 loudnorm).")

    args = parser.parse_args()
    return args



args = parse_args()

if getattr(args, "use_ollama", False):
    os.environ["FORCE_OLLAMA"] = "true"
    os.environ["LLM_PROVIDER"] = "ollama"
    print("[Log] 🦙 FORCING Local Ollama LLM execution.")

if getattr(args, "llm_provider", None) and args.llm_provider != "auto":
    os.environ["LLM_PROVIDER"] = args.llm_provider
    print(f"[Log] 🤖 Requested LLM Provider: {args.llm_provider}")

if getattr(args, "batch_file", None) and os.path.exists(args.batch_file):
    print(f"\n[Log] 📦 BATCH PROCESSING MODE ACTIVE: Reading {args.batch_file}...")
    with open(args.batch_file, "r", encoding="utf-8") as bf:
        lines = [line.strip() for line in bf if line.strip() and not line.strip().startswith("#")]
        
    print(f"[Log] Found {len(lines)} item(s) in batch list. Executing sequential generation...\n")
    for b_idx, item in enumerate(lines, 1):
        print(f"\n" + "="*70)
        print(f"📦 BATCH ITEM {b_idx}/{len(lines)}: {item}")
        print("="*70)
        
        cmd = [sys.executable, "main.py"]
        if is_url(item) or item.endswith((".mp4", ".mov", ".mkv")):
            cmd.extend(["--source_video", item])
        else:
            cmd.extend(["--mode", args.mode or "FACTS", "--category", item])
            
        if args.use_remotion: cmd.append("--use_remotion")
        if args.caption_style: cmd.extend(["--caption_style", args.caption_style])
        if args.aspect_ratio: cmd.extend(["--aspect_ratio", args.aspect_ratio])
        if args.tts_provider: cmd.extend(["--tts_provider", args.tts_provider])
        if args.auto_ducking: cmd.append("--auto_ducking")
        if args.enable_zoom: cmd.append("--enable_zoom")
        if args.enhance_audio: cmd.append("--enhance_audio")
        cmd.append("--skip_upload")
        
        subprocess.run(cmd, check=False)
        
    print("\n[Log] 🏁 All batch queue items completed successfully.")
    sys.exit(0)

# Quality Mapping (Overridden by manual flags if present)
bitrate_map = {"low": "4M", "medium": "12M", "high": "25M", "ultra": "50M"}
preset_map = {"low": "ultrafast", "medium": "medium", "high": "slow", "ultra": "slower"}

# 🟢 HQ AUTO-BOOST: If --hq is set, default to 'high' quality unless manually specified
if args.hq and (not hasattr(args, 'quality') or args.quality == "medium"):
    args.quality = "high"

target_bitrate = args.bitrate if args.bitrate else bitrate_map.get(args.quality or "medium")
target_preset = args.preset if args.preset else preset_map.get(args.quality or "medium")

# 🟢 PRO CONFIG: ComfyUI Availability Health Check
if args.use_comfy or args.use_ai_audio:
    from engine.comfy_bridge import is_comfy_available
    if not is_comfy_available():
        print("\n[Warning] ⚠️ PRO FEATURE ALERT: Local ComfyUI is NOT reachable on port 8188.")
        print("[Warning] Falling back to standard generation flow for this run.\n")
        args.use_comfy = False
        args.use_ai_audio = False

# Force UTF-8 encoding for Windows was handled above with line buffering.

# 🟢 Standalone AI Music Generation Mode
if getattr(args, "mode", None) == "MUSIC":
    from engine.modes.music import run as run_music
    run_music(args, target_bitrate, target_preset)

# 🟢 Standalone EXPLAINER Mode
if getattr(args, "mode", None) == "EXPLAINER":
    from engine.modes.explainer import run as run_explainer
    run_explainer(args, target_bitrate, target_preset)

# 🟢 PHASE 13: AI Extraction (High-Speed FFmpeg path)
# 🟢 Batch Video File/URL Processing
if getattr(args, "batch_file", None):
    if not os.path.exists(args.batch_file):
        print(f"[Error] Batch file not found: {args.batch_file}")
        sys.exit(1)
        
    print(f"--- Starting Batch Video Processing from: {args.batch_file} ---")
    with open(args.batch_file, "r", encoding="utf-8") as bf:
        urls = [line.strip() for line in bf if line.strip() and not line.strip().startswith("#")]
        
    print(f"[Log] Found {len(urls)} video items to process in batch.")
    import subprocess
    for idx, item in enumerate(urls, start=1):
        print(f"\n==========================================")
        print(f"[Batch {idx}/{len(urls)}] Processing: {item}")
        print(f"==========================================")
        cmd = [sys.executable, "main.py", "--source_video", item]
        if args.extract_mode: cmd.extend(["--extract_mode", args.extract_mode])
        if args.clip_count: cmd.extend(["--clip_count", str(args.clip_count)])
        if args.target_duration: cmd.extend(["--target_duration", str(args.target_duration)])
        if args.smart_crop: cmd.append("--smart_crop")
        if args.tighten: cmd.append("--tighten")
        if args.use_audio_detect: cmd.append("--use_audio_detect")
        if args.hq: cmd.append("--hq")
        if args.superres: cmd.append("--superres")
        if args.mashup: cmd.append("--mashup")
        if args.mashup_mode: cmd.extend(["--mashup_mode", args.mashup_mode])
        if args.user_context: cmd.extend(["--user_context", args.user_context])
        if args.style_context: cmd.extend(["--style_context", args.style_context])
        if args.style:
            styles = args.style if isinstance(args.style, list) else [args.style]
            for s in styles: cmd.extend(["--style", s])
        if args.output_json: cmd.extend(["--output_json", f"batch_out_{idx}.json"])
        
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[Warning] Batch item {idx} failed with return code {res.returncode}. Continuing...")
    print("\n[Log] Batch processing completed.")
    sys.exit(0)

# 🟢 Standalone Photo Reel Mode (Photos + Music Beat Sync)
if getattr(args, "mode", None) == "PHOTO_REEL":
    from engine.modes.photo_reel import run as run_photo_reel
    run_photo_reel(args, target_bitrate, target_preset)

# 🟢 Standalone Video Filter Mode
if getattr(args, "mode", None) == "FILTER":
    from engine.modes.video_filter import run as run_video_filter
    run_video_filter(args, target_bitrate, target_preset)

if getattr(args, "source_video", None) and args.mode not in ["TRAILER_MISSED", "FUNNY_EXPLAINER", "PHOTO_REEL"]:
    from engine.modes.clip_extract import run as run_clip_extract
    run_clip_extract(args, target_bitrate, target_preset)

from engine.modes.generate import run as run_generate
run_generate(args, target_bitrate, target_preset)
