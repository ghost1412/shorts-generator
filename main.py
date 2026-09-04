import os
import sys
import io
import random
import argparse
import json
import subprocess
from dotenv import load_dotenv

# 🟢 Force UTF-8 for all standard streams (fixes CP1252/Emoji crashes on Windows)
# Use line_buffering=True to prevent prints from different stages/threads from buffering and overlapping.
if sys.stdout.encoding != 'utf-8' or sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr.encoding != 'utf-8' or sys.platform == "win32":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from supabase import create_client, Client
from engine.utils import decrypt_secret

POOL_SIZE = 4
load_dotenv()

from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge, generate_odd_one_out_script, generate_riddle, generate_jwst_script
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx, fetch_jwst_images, is_url, download_source_video_from_url
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage

VIBE_VOICE_MAP = {
    "suspense": "en-US-ChristopherNeural", # Deep, intense
    "spooky": "en-US-AndrewNeural",       # Atmospheric
    "cinematic": "en-GB-SoniaNeural",      # Sophisticated narrator
    "upbeat": "en-US-AvaNeural"             # Energetic, modern
}

CARTOON_VOICE_MAP = {
    "rabbit": "en-US-AnaNeural",      # Squeaky/Child
    "robot": "en-US-SteffanNeural",   # Robotic/Formal
    "squirrel": "en-US-AnaNeural",    # Squeaky
    "superhero": "en-US-ChristopherNeural", # Deep/Heroic
    "old_man": "en-US-RogerNeural",   # Grumpy/Old
    "mafia_cat": "en-US-RogerNeural", # Deep/Raspy/Boss-like
    "orange_cat": "en-US-AvaNeural",  # Girly/Energetic
    "default": "en-US-GuyNeural"      # High Energy
}

CARTOON_AUDIO_CONFIG = {
    "rabbit": {"pitch": "+25Hz", "rate": "+25%"},
    "squirrel": {"pitch": "+35Hz", "rate": "+30%"},
    "robot": {"pitch": "-15Hz", "rate": "+10%"},
    "superhero": {"pitch": "-5Hz", "rate": "+15%"},
    "old_man": {"pitch": "-20Hz", "rate": "-5%"},
    "mafia_cat": {"pitch": "-10Hz", "rate": "-5%"},
    "orange_cat": {"pitch": "+15Hz", "rate": "+10%"},
    "default": {"pitch": "+0Hz", "rate": "+15%"}
}

def report_status(video_id, user_id, title="Shorts Video", status="Processing", download_url=None, mode="AUTO", youtube_video_id=None, storage_path=None, thumbnail_path=None):
    """Updates video generation status directly in Supabase (no webhook needed)."""
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("[Error] Supabase credentials missing - cannot update status.")
        return

    try:
        from supabase import create_client
        db = create_client(supabase_url, supabase_key)

        update_data = {"status": status}
        if title: update_data["title"] = title
        if mode: update_data["mode"] = mode
        if download_url: update_data["download_url"] = download_url
        if storage_path: update_data["storage_path"] = storage_path
        if thumbnail_path: update_data["thumbnail_path"] = thumbnail_path
        if youtube_video_id: update_data["youtube_video_id"] = youtube_video_id

        result = db.table("video_logs").update(update_data).eq("id", video_id).execute()
        print(f"[Log] DB updated: video_id={video_id}, status={status}, rows={len(result.data)}")

        # On success, increment the generations_used counter
        if status == "Published" and user_id:
            config_res = db.table("user_configs").select("generations_used").eq("user_id", user_id).single().execute()
            if config_res.data:
                current = config_res.data.get("generations_used", 0) or 0
                db.table("user_configs").update({"generations_used": current + 1}).eq("user_id", user_id).execute()
                print(f"[Log] generations_used incremented to {current + 1}")

    except Exception as e:
        print(f"[Error] Failed to update Supabase directly: {e}")
        import traceback
        traceback.print_exc()

def parse_args():
    parser = argparse.ArgumentParser(description="Generate either FACTS, STORY, FIND_IT, WYR, REDDIT, TRIVIA, QUOTE, JWST, RIDDLE or ODD_ONE_OUT shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "WYR", "REDDIT", "TRIVIA", "QUOTE", "ODD_ONE_OUT", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "RIDDLE", "TREND", "CHALLENGE", "JWST", "TRAILER_MISSED", "MUSIC", "EXPLAINER", "AUTO"], help="Force a specific mode.")
    parser.add_argument("--prompt", help="Prompt for AI Music/Image generation.")
    parser.add_argument("--ckpt_name", default="stable_audio_3_medium_base.safetensors", help="Checkpoint name for ComfyUI audio model.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat"], default="suspense", help="Select background music vibe.")
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
    parser.add_argument("--user_context", help="Extra context to guide AI extraction (specific scenes/styles).")
    parser.add_argument("--style_context", help="Context for editing style and pacing (e.g. 'fast cuts', 'cinematic').")
    parser.add_argument("--gif_dir", help="Path to external GIF library (e.g. animated-gifs repo).")
    parser.add_argument("--hq", action="store_true", help="Enable High-Quality (Premium) enhancements (sharpening, denoising).")
    parser.add_argument("--use_cache", action="store_true", help="Reuse cached highlights and skip existing segments/rendered clips.")
    parser.add_argument("--mashup", action="store_true", help="Create a single mashup/remix video of all highlights instead of separate clips.")
    parser.add_argument("--mashup_mode", choices=["attach", "edit"], default="edit", help="Assembly style for mashup: 'attach' for simple concatenation, 'edit' for premium transition effects and background music.")
    
    parser.add_argument("--output_json", help="Path to write structured JSON results (transcript, clips, scores, hooks).")
    parser.add_argument("--batch_file", help="Path to text file containing list of video URLs or local files to process in batch.")
    
    parser.add_argument("--use_comfy", action="store_true", help="Use local ComfyUI for premium AI backgrounds.")
    parser.add_argument("--use_ai_audio", action="store_true", help="Use local ComfyUI for premium AI music & SFX.")
    parser.add_argument("--bitrate", type=str, help="Manual bitrate override (e.g. 12000k)")
    parser.add_argument("--preset", type=str, help="Manual preset override (e.g. medium)")
    parser.add_argument("--quality", type=str, default="medium", choices=["low", "medium", "high", "ultra"], help="Output quality preset")
    
    # 🟢 Auto-Editor & AutoClip Flags
    parser.add_argument("--tighten", action="store_true", help="Remove silences from the final video.")
    parser.add_argument("--tighten_mode", choices=["cut", "speed"], default="cut", help="How to handle silences: 'cut' them or 'speed' them up.")
    parser.add_argument("--smart_crop", action="store_true", help="Enabled AI-powered face/interest tracking for vertical cropping.")
    
    # 🟢 Gap Closure Flags
    parser.add_argument("--srt", action="store_true", help="Export SRT subtitle file alongside each video.")
    parser.add_argument("--use_chapters", action="store_true", help="Boost scores for segments overlapping YouTube chapters.")
    parser.add_argument("--broll", action="store_true", help="Automatically download and insert B-roll cutaways during silences.")
    parser.add_argument("--preview", action="store_true", help="Render a low-res 3fps proxy video for quick preview.")
    
    # Cartoon/Persona Flags
    parser.add_argument("--cartoon", action="store_true", help="Enable cartoon-style news persona.")
    parser.add_argument("--persona", help="Select a specific cartoon persona (rabbit, robot, squirrel, superhero).")
    parser.add_argument("--use_remotion", action="store_true", help="Use Remotion engine instead of MoviePy for modern professional rendering.")
    parser.add_argument("--caption_style", default="HORMOZI", choices=["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"], help="Subtitle animation preset for Remotion renderer (default: HORMOZI).")
    parser.add_argument("--subtitle_y_pos", type=int, default=1150, help="Vertical pixel position for subtitles in Remotion (default: 1150).")
    
    # Provider & Media Overrides
    parser.add_argument("--use_ollama", action="store_true", help="Force local Ollama LLM execution.")
    parser.add_argument("--bg_media", help="Path to custom local background image (.jpg, .png) or video (.mp4, .mov).")
    
    # Interactive Kids Story Creator Flags
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI prompt to create kids characters.")
    parser.add_argument("--hero", help="Type of hero (e.g. teddy bear, friendly dragon).")
    parser.add_argument("--hero_name", help="Name of the hero (e.g. Luna).")
    parser.add_argument("--companion", help="Hero's companion (e.g. Twinkle the Pixie).")
    parser.add_argument("--quest", help="Hero's adventure quest.")
    parser.add_argument("--setting", help="Adventure setting (e.g. Starry Night Forest).")

    args = parser.parse_args()
    return args

def export_srt(transcript_data, output_path):
    """Exports transcript segments to a standard .srt file."""
    segments = transcript_data.get('segments', [])
    if not segments: return
    
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_time(seg.get('start', 0))
            end = format_time(seg.get('end', 0))
            text = seg.get('text', '').strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def print_clip_score_table(highlights):
    """Prints a formatted table of clip scores to the console."""
    if not highlights: return
    print("\n" + "="*85)
    print(f"{'CLIP SCORE RANKING':^85}")
    print("="*85)
    print(f"{'Rank':<5} | {'Start':<8} | {'End':<8} | {'Score':<10} | {'Reason'}")
    print("-" * 85)
    for i, h in enumerate(highlights):
        # Look for the best available score (supports our hybrid engine output)
        score = float(h.get('final_score', h.get('viral_score', h.get('score', 0))))
        
        # Check if LLM score specifically exists for display suffix
        if 'llm_score' in h and h['llm_score'] is not None:
            score_str = f"{score:.1f} (LLM)"
        else:
            score_str = f"{score:.1f}"
            
        reason = str(h.get('reason', h.get('llm_reason', h.get('hook_text', 'Viral Moment'))))
        print(f"#{i+1:<4} | {h['start']:<7.1f}s | {h['end']:<7.1f}s | {score_str:<10} | {reason[:40]}")
    print("="*85 + "\n")

args = parse_args()

if getattr(args, "use_ollama", False):
    os.environ["FORCE_OLLAMA"] = "true"
    print("[Log] 🦙 FORCING Local Ollama LLM execution.")

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
    import os
    import sys
    import time
    from engine.comfy_bridge import generate_ai_audio, generate_cinematic_backgrounds, is_comfy_available
    from engine.social_gen import generate_expanded_music_prompt, generate_viral_metadata
    
    # Check ComfyUI Availability
    if not is_comfy_available():
        print("[Error] ComfyUI server is not running or unreachable at the configured URL.")
        if args.video_id and args.user_id:
            report_status(args.video_id, args.user_id, "ComfyUI Unreachable", "Failed", None, "MUSIC")
        sys.exit(1)
        
    prompt = args.prompt if args.prompt else (args.script if args.script else (args.user_context if args.user_context else "cinematic synthwave track, high quality"))
    duration = args.target_duration if args.target_duration else 30
    ckpt_name = args.ckpt_name if args.ckpt_name else "ace_step_v1_3.5b.safetensors"
    
    print(f"--- Starting Standalone AI Music Generation ---")
    print(f"[Log] Original Prompt: '{prompt}'")
    
    # Expand Prompt via LLM
    expanded_prompt = generate_expanded_music_prompt(prompt)
    print(f"[Log] Expanded Prompt: '{expanded_prompt}'")
    
    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, f"AI Music: {prompt}", "Processing", None, "MUSIC")
        
    # Generate metadata for the AI music video
    meta = generate_viral_metadata(f"AI Music Track: {expanded_prompt}", mode="MUSIC", category="music")
    if not meta.get("title"):
        meta["title"] = f"AI Music: {prompt[:30]} ⚡"
    meta["title"] = meta["title"][:95]
    
    # Setup session directory
    session_id = args.video_id if args.video_id else str(int(time.time()))
    if args.session_dir:
        session_dir = args.session_dir
    else:
        session_dir = os.path.join("sessions", f"music_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"[Log] Session directory initialized at: {session_dir}")

    # Generate Audio
    print(f"[Log] Generating AI audio...")
    audio_path = generate_ai_audio(expanded_prompt, duration=duration, output_dir=session_dir, ckpt_name=ckpt_name)
    if not audio_path:
        print("[Error] AI Music generation failed.")
        if args.video_id and args.user_id:
            report_status(args.video_id, args.user_id, meta["title"], "Failed", None, "MUSIC")
        sys.exit(1)
        
    print(f"[Log] AI Audio generated successfully at: {audio_path}")
    
    # Generate visual background & compile video
    print(f"[Log] Creating visual video container for the generated music...")
    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, meta["title"], "Processing", None, "MUSIC")
        
    # Generate matching background image
    bg_images = generate_cinematic_backgrounds(expanded_prompt, count=1, output_dir=session_dir, width=768, height=1344)
    if bg_images and len(bg_images) > 0:
        bg_image_path = bg_images[0]
        print(f"[Log] Generated matching visual background: {bg_image_path}")
    else:
        print("[Warning] Background generation failed, using fallback image.")
        bg_image_path = os.path.join(session_dir, "fallback_bg.png")
        if not os.path.exists(bg_image_path):
            import subprocess
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920", "-frames:v", "1", bg_image_path], capture_output=True)
            
    # output video path
    output_filename = f"music_short_{session_id}.mp4"
    output_path = os.path.join("sessions", output_filename)
    
    # Helper to escape special characters for FFmpeg drawtext filter
    def escape_ffmpeg_text(text):
        escaped = text.replace('\\', '\\\\')
        escaped = escaped.replace("'", "'\\''")
        escaped = escaped.replace(':', '\\:')
        escaped = escaped.replace(',', '\\,')
        escaped = escaped.replace('%', '\\%')
        return escaped

    title_escaped = escape_ffmpeg_text(meta.get("title", "AI Music Track"))
    import re
    title_clean = re.sub(r'[^\x00-\x7F]+', '', title_escaped).strip()
    if not title_clean:
        title_clean = "AI Music Track"
        
    prompt_clean = re.sub(r'[^\x00-\x7F]+', '', prompt).strip()
    prompt_escaped = escape_ffmpeg_text(prompt_clean[:40] + "..." if len(prompt_clean) > 40 else prompt_clean)
    if not prompt_escaped:
        prompt_escaped = "ComfyUI Generated Soundtrack"
        
    font_arg = "fontfile='C\\:/Windows/Fonts/arial.ttf':" if sys.platform == "win32" else ""
    
    # Build filter complex for scaling, cropping and title card drawing
    video_filter = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"drawtext=text='{title_clean}':{font_arg}fontcolor=white:fontsize=54:x=(w-text_w)/2:y=(h-text_h)/2-60:box=1:boxcolor=black@0.5:boxborderw=20,"
        f"drawtext=text='{prompt_escaped}':{font_arg}fontcolor=gray:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2+60"
    )
    
    # Combine image + audio into MP4
    print(f"[Log] Compiling final video...")
    import subprocess
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg_image_path,
        "-i", audio_path,
        "-vf", video_filter,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest", output_path
    ]
    
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(output_path):
        print(f"[Log] SUCCESS! Combined video created: {output_path}")
        
        # Post-processing / upload if tracked in Supabase
        if args.video_id and args.user_id:
            os.environ["USER_ID"] = args.user_id
            from engine.storage import upload_to_storage
            
            # Extract thumbnail
            thumbnail_file = os.path.join(session_dir, f"thumb_music_{session_id}.jpg")
            thumbnail_path = None
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', output_path, 
                    '-ss', '00:00:01', '-vframes', '1', 
                    thumbnail_file
                ], check=True, capture_output=True)
                thumbnail_path = upload_to_storage(thumbnail_file, args.video_id, is_video=False)
                try: os.remove(thumbnail_file)
                except: pass
            except Exception as te:
                print(f"[Warning] Thumbnail extraction failed: {te}")
                
            storage_path = upload_to_storage(output_path, args.video_id, is_video=True)
            
            report_status(
                args.video_id,
                args.user_id,
                meta["title"],
                "Published",
                None,
                "MUSIC",
                None,
                storage_path,
                thumbnail_path
            )
        print(f"[Log] Standalone AI music job complete: {output_path}")
        sys.exit(0)
    else:
        print(f"[Error] FFmpeg compilation failed: {result.stderr}")
        if args.video_id and args.user_id:
            report_status(args.video_id, args.user_id, meta["title"], "Failed", None, "MUSIC")
        sys.exit(1)

# 🟢 Standalone EXPLAINER Mode
if getattr(args, "mode", None) == "EXPLAINER":
    import time
    from engine.script_gen import generate_manim_script
    from engine.video_gen import render_manim_scene
    
    extract_mode = getattr(args, "extract_mode", "shorts") or "shorts"
    print(f"--- Starting Standalone EXPLAINER Animation Generation (Extract Mode: {extract_mode}) ---")
    topic = args.prompt if args.prompt else (args.category if args.category else "Pythagorean Theorem")
    print(f"[Log] Explaining topic: '{topic}'")
    
    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, f"Explainer: {topic}", "Processing", None, "EXPLAINER")
        
    session_id = args.video_id if args.video_id else str(int(time.time()))
    session_dir = args.session_dir if args.session_dir else os.path.join("sessions", f"explainer_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    
    script_data = generate_manim_script(topic, extract_mode=extract_mode)
    title = script_data.get('title', f"Explainer: {topic}")
    
    print(f"[Log] LLM Script Generated. Title: {title}")
    
    # 1. Generate Voiceover
    from engine.voice_gen import generate_voice
    voiceover_text = script_data.get('voiceover_text', f"Today we are explaining {topic}.")
    audio_path, subs_path = generate_voice(
        voiceover_text, 
        output_audio=os.path.join(session_dir, "voice.mp3"), 
        output_subs=os.path.join(session_dir, "subs.json"),
        add_cta=False
    )
    
    # 2. Render Manim Scene
    manim_output_path = render_manim_scene(script_data['code'], session_dir, extract_mode=extract_mode)
    
    if manim_output_path and os.path.exists(manim_output_path):
        output_path = manim_output_path
        # 3. Merge Audio and Video if voiceover succeeded
        if audio_path and os.path.exists(audio_path):
            merged_path = os.path.join(session_dir, "final_explainer.mp4")
            import subprocess
            
            # Helper to get media duration
            def get_dur(p):
                try:
                    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", p], capture_output=True, text=True)
                    return float(res.stdout.strip())
                except: return 0.1
                
            v_dur = get_dur(manim_output_path)
            a_dur = get_dur(audio_path)
            speed_factor = a_dur / v_dur if v_dur > 0 else 1.0
            print(f"[Log] Synchronizing Explainer Timing... Video: {v_dur:.2f}s, Audio: {a_dur:.2f}s (Stretch: {speed_factor:.2f}x)")

            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", manim_output_path,
                "-i", audio_path,
                "-vf", f"setpts={speed_factor}*PTS,tpad=stop_mode=clone:stop_duration=2",
                "-c:v", "libx264",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest", merged_path
            ]
            res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(merged_path):
                output_path = merged_path
            else:
                print(f"[Warning] Failed to merge audio: {res.stderr}")

        print(f"[Log] SUCCESS! Explainer video created: {output_path}")
        if args.video_id and args.user_id:
            from engine.storage import upload_to_storage
            storage_path = upload_to_storage(output_path, args.video_id, is_video=True)
            report_status(args.video_id, args.user_id, title, "Published", None, "EXPLAINER", None, storage_path)
        sys.exit(0)
    else:
        print("[Error] Manim rendering failed.")
        if args.video_id and args.user_id:
            report_status(args.video_id, args.user_id, title, "Failed", None, "EXPLAINER")
        sys.exit(1)

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
        if args.style:
            styles = args.style if isinstance(args.style, list) else [args.style]
            for s in styles: cmd.extend(["--style", s])
        if args.output_json: cmd.extend(["--output_json", f"batch_out_{idx}.json"])
        
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[Warning] Batch item {idx} failed with return code {res.returncode}. Continuing...")
    print("\n[Log] Batch processing completed for all items.")
    sys.exit(0)

if getattr(args, "source_video", None) and args.mode != "TRAILER_MISSED":
    import time
    from engine.video_gen import extract_segments
    from engine.analysis import process_source_video
    from engine.social_gen import generate_viral_metadata
    
    print(f"--- Starting AI Extraction: {args.source_video} ---")
    
    session_dir = args.session_dir if args.session_dir else f"sessions/extraction_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    
    # 🟢 Auto-download video if source_video is a URL
    if is_url(args.source_video):
        print(f"[Log] Detected Video URL: '{args.source_video}'. Downloading stream...")
        args.source_video = download_source_video_from_url(args.source_video, session_dir)
        print(f"[Log] Video downloaded locally to: {args.source_video}")

    print("[Log] Running Transcript-based Highlight Analysis...")
    # 🟢 EXPERT GUARD: Prevention of Mode Confusion
    if args.extract_mode == "shorts" and args.target_duration > 60:
        print(f"[Warning] Target duration {args.target_duration}s exceeds YouTube Shorts limit (60s).")
        print(f"[Log] Capping short duration at 60s. For longer highlights, use --extract_mode long.")
        args.target_duration = 60
        
    # Get chapters if requested
    chapters_path = None
    if args.use_chapters:
        from engine.media_gen import get_chapters_json_path
        chapters_path = get_chapters_json_path(args.source_video, session_dir)

    highlights, transcript_path, interest_points, silence_intervals = process_source_video(
        args.source_video, session_dir, mode=args.extract_mode, 
        clip_count=args.clip_count, target_duration=args.target_duration,
        min_duration=args.min_duration,
        use_audio_detect=args.use_audio_detect, style=args.style,
        user_context=args.user_context, style_context=args.style_context,
        smart_crop=args.smart_crop, tighten=args.tighten, use_cache=args.use_cache,
        chapters_path=chapters_path, use_llm_scoring=True
    )
    
    # 🟢 Print the beautiful new score table
    print_clip_score_table(highlights)
    
    # 🟢 Download B-roll if requested
    if args.broll:
        from engine.media_gen import download_broll_clips
        download_broll_clips()
        
    # 🟢 Handle Preview Mode
    if args.preview:
        print("\n[Log] 🔍 PREVIEW MODE ENABLED: Rendering fast 3fps proxy instead of full extraction...")
        import subprocess
        for i, h in enumerate(highlights):
            out_preview = os.path.join(session_dir, f"preview_clip_{i+1}.mp4")
            cmd = [
                "ffmpeg", "-y", "-ss", str(h['start']), "-i", args.source_video,
                "-t", str(h['end'] - h['start']),
                "-vf", "scale=-2:360", "-r", "3", "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", out_preview
            ]
            subprocess.run(cmd, capture_output=True)
            print(f"  -> Generated {out_preview}")
        print("\n[Log] Preview renders complete. Check session folder.")
        sys.exit(0)
    
    
    # Filter signals based on user flags
    final_interest = interest_points if args.smart_crop else None
    final_silence = silence_intervals if args.tighten else None
    
    if not highlights:
        print("[Error] No highlights identified.")
        sys.exit(1)
        
    print(f"[Log] Extracting {len(highlights)} segments in parallel via FFmpeg...")
    
    # Check orientation and letterbox
    from engine.analysis import detect_letterbox, detect_orientation
    letterbox_crop = detect_letterbox(args.source_video) if args.smart_crop else None
    orientation = detect_orientation(args.source_video) if args.smart_crop else "landscape"
    
    extracted_files = extract_segments(
        args.source_video, highlights, transcript_path, session_dir, 
        mode=args.extract_mode, bitrate=target_bitrate, preset=target_preset, codec="libx264",
        is_challenge=(args.mode == "CHALLENGE"), use_hq=args.hq, 
        editing_style=args.style, gif_dir=args.gif_dir,
        interest_points=final_interest, silence_intervals=final_silence,
        tighten_mode=args.tighten_mode, use_remotion=args.use_remotion, use_cache=args.use_cache,
        mashup=args.mashup, mashup_mode=args.mashup_mode,
        orientation=orientation, letterbox_crop=letterbox_crop,
        caption_style=args.caption_style, subtitle_y_pos=args.subtitle_y_pos
    )
    
    # Export SRT for each extracted file
    if args.srt and os.path.exists(transcript_path):
        print(f"[Log] Exporting SRT files for {len(extracted_files)} clips...")
        with open(transcript_path, 'r', encoding='utf-8') as f:
            t_data = json.load(f)
        for i, clip_file in enumerate(extracted_files):
            # Try to map the global transcript to the specific clip bounds
            hi = highlights[i]
            clip_segs = [s for s in t_data.get('segments', []) if s['start'] >= hi['start'] and s['end'] <= hi['end']]
            # Offset times relative to clip start
            for s in clip_segs:
                s['start'] = max(0, s['start'] - hi['start'])
                s['end'] = max(0, s['end'] - hi['start'])
            srt_path = clip_file.rsplit('.', 1)[0] + ".srt"
            export_srt({'segments': clip_segs}, srt_path)
            

    
    if not extracted_files:
        print("[Error] No videos were generated. Check the logs for FFmpeg failures.")
        sys.exit(1)
    
    # Generate viral metadata for Highlights
    print("[Log] Generating viral metadata for extracted clips...")
    highlights_meta = []
    
    if args.extract_mode == "long" or getattr(args, "mashup", False):
        summary_context = " ".join([h.get('context', h.get('reason', '')) for h in highlights[:5]])
        meta = generate_viral_metadata(summary_context, mode="STORY", category="gaming")
        filename = "mashup_reel.mp4" if getattr(args, "mashup", False) else "highlight_reel.mp4"
        highlights_meta.append({
            "file": filename,
            "title": meta.get('title', 'Viral Mashup' if getattr(args, "mashup", False) else 'Viral Highlight Reel'),
            "description": meta.get('description', ''),
            "tags": meta.get('tags', [])
        })
    else:
        from concurrent.futures import ThreadPoolExecutor
        def fetch_meta(idx_h):
            i, h = idx_h
            if i >= len(extracted_files): return None
            # Sanitize technical jargon from the context/reason
            raw_context = h.get('context', h.get('reason', 'Gamer Highlight'))
            if "Recovered" in raw_context or "Regex" in raw_context:
                raw_context = "Epic Gaming Moment"
            
            # Auto-detect game name from session dir or source video name
            lower_session = args.session_dir.lower() if args.session_dir else ""
            lower_source = args.source_video.lower() if args.source_video else ""
            game_name = "Gaming"
            if "gta" in lower_session or "gta" in lower_source:
                game_name = "GTA 6"
            elif "rdr" in lower_session or "rdr" in lower_source:
                game_name = "Red Dead Redemption 2"
            elif "witcher" in lower_session or "witcher" in lower_source:
                game_name = "The Witcher 3"
                
            content_info = {
                "game_name": game_name,
                "scene_description": raw_context,
                "styles": args.style if isinstance(args.style, list) else ([args.style] if args.style else [])
            }
            
            meta = generate_viral_metadata(content_info, mode="STORY", category="gaming")
            return {
                "file": os.path.basename(extracted_files[i]),
                "title": meta.get('title', 'Viral Moment'),
                "description": meta.get('description', ''),
                "tags": meta.get('tags', [])
            }

        with ThreadPoolExecutor(max_workers=min(POOL_SIZE, len(highlights))) as executor:
            results = list(executor.map(fetch_meta, enumerate(highlights)))
            highlights_meta = [r for r in results if r is not None]
        
    with open(os.path.join(session_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(highlights_meta, f, indent=4)
        
    if getattr(args, "output_json", None):
        output_json_data = {
            "source_video": args.source_video,
            "session_dir": session_dir,
            "total_clips": len(highlights),
            "clips": []
        }
        for i, h in enumerate(highlights):
            clip_path = extracted_files[i] if i < len(extracted_files) else ""
            meta_item = highlights_meta[i] if i < len(highlights_meta) else {}
            output_json_data["clips"].append({
                "clip_index": i + 1,
                "video_path": clip_path,
                "start": h.get("start"),
                "end": h.get("end"),
                "duration": round(h.get("end", 0) - h.get("start", 0), 2),
                "viral_score": h.get("viral_score", 85),
                "hook": h.get("hook_text", meta_item.get("title", "")),
                "reason": h.get("reason", "High-engagement segment"),
                "title": meta_item.get("title", f"Clip #{i+1}"),
                "tags": meta_item.get("tags", [])
            })
        with open(args.output_json, "w", encoding="utf-8") as f_out:
            json.dump(output_json_data, f_out, indent=4)
        print(f"[Log] Exported structured JSON results to: {args.output_json}")

    print(f"[Log] SUCCESS! Extracted videos to {session_dir}")
    sys.exit(0)

print("--- Starting Shorts Generator ---", flush=True)
    
# 0. Manual Script Override
youtube_video_id = None
if args.script:
    print("[Log] Manual script detected. Skipping generation...")
    full_script = args.script
    mode = "STORY" # Default to story-style branding for manual scripts
    category = "tech"
    story_data = {"title": "coding setup", "story": full_script}
    facts_data = [] # Not used in story mode but kept for metadata function compatibility
else:
    # 1. Choose Mode (Manual override or random)
    if args.mode and args.mode != "AUTO":
        mode = args.mode
    else:
        # 🟢 WINNER-HEAVY SELECTION: Facts (Spot the Lie) and News are 2x more likely than others
        mode = random.choices(
            ["FACTS", "FIND_IT", "WYR", "ODD_ONE_OUT", "STORY", "TRIVIA", "REDDIT", "QUOTE", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "RIDDLE", "EXPLAINER"],
            weights=[20, 0, 0, 20, 5, 5, 0, 5, 10, 20, 0, 20, 30]
        )[0]
    if args.recap_title and not args.mode: mode = "MOVIE_RECAP"
    
    # 🟢 AUTO-CARTOON: Enforce character personas for all News modes
    if mode in ("NEWS", "NEWS_SERIOUS"):
        if not args.cartoon:
            print(f"[Log] {mode} detected. Auto-enabling Cartoon Mode...")
            args.cartoon = True
        
        # 🟢 MULTI-CAT RANDOMIZATION: Pick between cats if no persona is set
        if not args.persona:
            args.persona = random.choice(["mafia_cat", "orange_cat"])
            print(f"[Log] Randomly selected persona: {args.persona}")
    
    # 2. Choose Category
    categories = ["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks", "world", "politics", "celebrities", "tech", "sports", "kids", "children", "bedtime"]
    category = args.category if args.category and args.category in categories else random.choice(categories)
    topic = args.prompt if args.prompt else category
    if args.hero or args.interactive:
        category = "kids"
    print(f"[Log] Generating content for category/topic: '{topic}' (Category: {category})...", flush=True)
    
    try:
        if mode == "EXPLAINER":
            from engine.script_gen import generate_manim_script
            manim_data = generate_manim_script(topic, extract_mode=args.extract_mode, target_duration=args.target_duration)
            full_script = manim_data["voiceover_text"]
            facts_data = []
            print(f"[Log] EXPLAINER Script generated for topic '{topic}': Title='{manim_data['title']}'")
        elif mode == "FACTS":
            facts_res = generate_mixed_facts(category)
            hook = facts_res["hook"]
            facts_data = facts_res["facts"]
            
            # Construct the script: Hook -> Challenge Intro -> Facts -> Loop Outro
            full_script = f"{hook} ... One of these facts is a LIE! ... "
            fact_segments = []
            for i, f in enumerate(facts_data[:3]): # Max 3 segments for UI consistency
                fact_segments.append(f"{i+1}: {f['fact']}")
            
            full_script += " ... ".join(fact_segments)
            
            # 🟢 UPGRADE: Seamless Viral Loop
            full_script += f" ... The real answer is ... wait... {facts_res.get('loop_lead', 'Go back and check again.')}"
        elif mode == "MOVIE_RECAP":
            from engine.script_gen import generate_movie_recap
            recap_data = generate_movie_recap(args.recap_title)
            full_script = recap_data.get("story") or recap_data.get("script", "")
            facts_data = []
            story_data = {"title": args.recap_title, "story": full_script}
        elif mode == "TRAILER_MISSED":
            from engine.script_gen import generate_trailer_missed_script
            trailer_title = args.recap_title or args.category
            if not trailer_title and args.source_video:
                base = os.path.splitext(os.path.basename(args.source_video))[0]
                trailer_title = base.replace("_", " ").replace("-", " ")
            if not trailer_title:
                trailer_title = "the trailer"
            
            recap_data = generate_trailer_missed_script(trailer_title)
            full_script = f"{recap_data['story']} ... {recap_data.get('loop_lead', 'Go back and check for yourself.')}"
            facts_data = []
            story_data = {"title": trailer_title, "story": full_script}
        elif mode == "STORY":
            hero = args.hero
            hero_name = args.hero_name
            companion = args.companion
            quest = args.quest
            setting = args.setting

            if args.interactive:
                print("\n🌟 --- Welcome to the Interactive Children's Story Creator! --- 🌟\n")
                print("Let's build a character together!")
                
                # 1. Hero selection
                heroes = [
                    "Sleepy Bear 🧸",
                    "Friendly Dragon 🐉",
                    "Brave Squirrel 🐿️",
                    "Magic Unicorn 🦄",
                    "Curious Fish 🐟"
                ]
                print("\n1. Choose a Hero type:")
                for idx, h in enumerate(heroes):
                    print(f"  [{idx + 1}] {h}")
                try:
                    choice = int(input("Enter number (1-5): "))
                    hero = heroes[choice - 1]
                except Exception:
                    hero = "Sleepy Bear 🧸"
                
                # 2. Hero name
                hero_name = input("\n2. Enter your Hero's name: ").strip()
                if not hero_name:
                    hero_name = "Luna"
                
                # 3. Companion selection
                companions = [
                    "Twinkle the Pixie 🧚",
                    "Oliver the Wise Owl 🦉",
                    "Barnaby the Busy Beaver 🦫",
                    "Flutter the Rainbow Butterfly 🦋"
                ]
                print("\n3. Choose a friendly companion:")
                for idx, c in enumerate(companions):
                    print(f"  [{idx + 1}] {c}")
                try:
                    choice = int(input("Enter number (1-4): "))
                    companion = companions[choice - 1]
                except Exception:
                    companion = "Twinkle the Pixie 🧚"

                # 4. Quest selection
                quests = [
                    "find the lost star 🌟",
                    "learn to fly high in the sky 🎈",
                    "find a secret hidden treasure 💎",
                    "help a sad friend feel better 🤝"
                ]
                print("\n4. Choose a magical quest:")
                for idx, q in enumerate(quests):
                    print(f"  [{idx + 1}] {q}")
                try:
                    choice = int(input("Enter number (1-4): "))
                    quest = quests[choice - 1]
                except Exception:
                    quest = "find the lost star 🌟"

                # 5. Setting selection
                settings = [
                    "Starry Night Forest 🌌",
                    "Candy Land Hills 🍭",
                    "Underwater Castle 🏰",
                    "Sky Island Palace ☁️"
                ]
                print("\n5. Choose the setting:")
                for idx, s in enumerate(settings):
                    print(f"  [{idx + 1}] {s}")
                try:
                    choice = int(input("Enter number (1-4): "))
                    setting = settings[choice - 1]
                except Exception:
                    setting = "Starry Night Forest 🌌"
                
                # Force category to kids
                category = "kids"

            if hero:
                story_data = generate_story(
                    category=category,
                    hero=hero,
                    hero_name=hero_name,
                    companion=companion,
                    quest=quest,
                    setting=setting
                )
            else:
                story_data = generate_story(topic if topic else category)

            if not story_data: sys.exit(0)
            
            # Construct script with strategic viral pauses
            full_script = f"{story_data['story']} ... {story_data.get('loop_lead', 'Hit the plus if you want more.')}"
            facts_data = [] # Not used in story mode but kept for metadata function compatibility
            print(f"[Log] Story: {story_data['story']}")
        elif mode == "FIND_IT" or mode == "FIND_CAT": # Supporting old flag for safety
            # Channel Manager Intro
            intros = [
                "Only GIGACHADS can find this! 🗿",
                "Bro is hiding from the IRS! 🤫",
                "99% of you will FAIL this challenge! 🧠",
                "POV: You are searching for your brain cells... found him yet?",
                "If you don't find this, you owe me a sub! 🤝"
            ]
            full_script = f"{random.choice(intros)} ... 🔍 Spot the target in 5 seconds! ... ... ... ... ... Did you find it? ... ... "
            facts_data = []
            print(f"[Log] Game mode: {mode}", flush=True)
        elif mode == "WYR":
            wyr_data = generate_wyr(category)
            full_script = f"Would you rather? 🔴 {wyr_data['option_a']} ... OR ... 🔵 {wyr_data['option_b']} ... ... What did you choose? Let me know in the comments!"
            facts_data = [] # Not used
            print(f"[Log] WYR Data: {wyr_data}")
        elif mode == "REDDIT":
            reddit_data = generate_reddit_story(category)
            full_script = f"{reddit_data['title']} ... {reddit_data['story']} ... Whose side are you on? Let me know!"
            facts_data = []
            print(f"[Log] Reddit Data: {reddit_data}")
        elif mode == "TRIVIA":
            trivia_data = generate_trivia(category)
            full_script = f"Are you a genius? Let's find out! ... {trivia_data['question']} ... A: {trivia_data['opt_a']} ... B: {trivia_data['opt_b']} ... C: {trivia_data['opt_c']} ... ... Answer is ... {trivia_data['answer']}. Did you get it right?"
            facts_data = [] # Not used
            print(f"[Log] TRIVIA Data: {trivia_data}")
        elif mode == "QUOTE":
            quote_data = generate_quote(category)
            full_script = f"Listen closely... ... {quote_data['quote']} ... ... ... ... Do you agree?"
            facts_data = []
            print(f"[Log] QUOTE Data: {quote_data}")
        elif mode == "ODD_ONE_OUT":
            # 🟢 REVERT: Static high-tension script for better viral engagement
            intros = [
                "99% of people FAIL this test! 🧠",
                "Only a GENIUS can spot the odd one! 🗿",
                "Is your brain awake? Find the difference! 🧐",
                "Bro, this one is actually impossible! 🤫",
                "If you find it in 3 seconds, you're a LEGEND! 🏆"
            ]
            hook = random.choice(intros)
            theme = f"One of these is NOT a {category}..."
            full_script = f"{hook} ... {theme} ... Find it before the time runs out! ... ... ... ... ... Did you spot the odd one? Let me know!"
            odd_res = {"hook": hook, "theme": theme} # For metadata consistency
            facts_data = []
            print(f"[Log] ODD_ONE_OUT (Revert): {full_script}")
        elif mode == "RIDDLE":
            riddle_data = generate_riddle(category)
            full_script = f"{riddle_data['hook']} ... {riddle_data['question']} ... ... ... ... Comment the answer below!"
            facts_data = []
            print(f"[Log] RIDDLE Data: {riddle_data}")
        elif mode == "NEWS":
            selected_persona = args.persona if args.persona else ("rabbit" if args.cartoon else None)
            news_data = generate_funny_news(category, tone="funny", persona=selected_persona)
            news_source = news_data.get('source', 'Unknown')
            full_script = f"{news_data['hook']} ... {news_data['story']}"
            facts_data = []
            print(f"[Log] NEWS (funny) Data: {news_data}")
        elif mode == "NEWS_SERIOUS":
            selected_persona = args.persona if args.persona else ("rabbit" if args.cartoon else None)
            news_data = generate_funny_news(category, tone="serious", persona=selected_persona)
            news_source = news_data.get('source', 'Unknown')
            full_script = f"{news_data['hook']} ... {news_data['story']}"
            facts_data = []
            print(f"[Log] NEWS_SERIOUS Data: {news_data}")
        elif mode == "GUESS_SOUND":
            sound_data = generate_sound_challenge(category)
            full_script = f"{sound_data['hook']} ... ... ... ... ... {sound_data['reveal_text']}"
            facts_data = [] # Not used
            print(f"[Log] GUESS_SOUND Data: {sound_data}")
        elif mode == "CHALLENGE":
            from engine.script_gen import generate_breath_challenge
            challenge_data = generate_breath_challenge()
            full_script = challenge_data["script"]
            facts_data = []
            print(f"[Log] CHALLENGE Data: {challenge_data}")
        elif mode == "TREND":
            from engine.script_gen import generate_trend_script
            trend_data = generate_trend_script(category)
            if not trend_data: sys.exit(0)
            full_script = trend_data.get("script") or trend_data.get("story", "")
            facts_data = []
            print(f"[Log] TREND Data: {trend_data}")
        elif mode == "JWST":
            jwst_data = generate_jwst_script()
            full_script = f"{jwst_data['hook']} ... {jwst_data['story']} ... {jwst_data.get('loop_lead', '')}"
            facts_data = []
            print(f"[Log] JWST Data: {jwst_data}")
    except RuntimeError as e:
        print(f"[Error] Generation failed: {e}")
        print("[Log] Gracefully skipping this video to maintain channel diversity.")
        sys.exit(0)

print(f"[Log] Full Script: \"{full_script}\"", flush=True)

# 2. Generate Voice & Timings
print("[Log] Generating voiceover and timing data...", flush=True)
# Use a unique session ID and directory for complete isolation
session_id = random.randint(100000, 999999)
session_dir = f"assets/temp_{session_id}"
os.makedirs(session_dir, exist_ok=True)

voice_file = os.path.join(session_dir, "voice.mp3")
subs_file = os.path.join(session_dir, "subs.json")

# Map vibe to an emotional voice
is_kids_story = category.lower() in ["kids", "children", "bedtime"] or bool(args.hero or args.interactive)
if is_kids_story:
    selected_voice = "en-US-AvaNeural"
    selected_pitch = "+0Hz"
    selected_rate = "+5%"
    print(f"[Log] Kids Story Mode Active: Voice={selected_voice}, Pitch={selected_pitch}, Rate={selected_rate}")
else:
    selected_voice = VIBE_VOICE_MAP.get(args.vibe, "en-US-AriaNeural")
    selected_pitch = "+0Hz"
    selected_rate = "+15%"

# Overwrite voice if Cartoon persona is active
selected_persona = args.persona if args.persona else ("mafia_cat" if args.cartoon else None)
if selected_persona and mode in ["NEWS", "NEWS_SERIOUS"]:
    p_key = selected_persona.lower()
    selected_voice = CARTOON_VOICE_MAP.get(p_key, CARTOON_VOICE_MAP["default"])
    audio_cfg = CARTOON_AUDIO_CONFIG.get(p_key, CARTOON_AUDIO_CONFIG["default"])
    selected_pitch = audio_cfg["pitch"]
    selected_rate = audio_cfg["rate"]
    print(f"[Log] Cartoon Persona '{selected_persona}' Active: Voice={selected_voice}, Pitch={selected_pitch}, Rate={selected_rate}")
else:
    print(f"[Log] Selected voice for '{args.vibe}' vibe: {selected_voice}")

# Voice CTA only for interactive/game modes
add_cta = mode in ["FACTS", "WYR", "FIND_IT", "ODD_ONE_OUT", "TRIVIA", "GUESS_SOUND"]
audio_path, subs_path = generate_voice(
    full_script, 
    output_audio=voice_file, 
    output_subs=subs_file, 
    voice_name=selected_voice, 
    rate=selected_rate, 
    pitch=selected_pitch, 
    add_cta=add_cta
)

if args.video_id and args.user_id:
    report_status(args.video_id, args.user_id, "In-Progress Video", "Processing", None, mode)

if not audio_path or not subs_path:
    print("[Error] Voice generation failed.")
    sys.exit(0)
    
# 3. Source Media (Dynamic Backgrounds)
print("[Log] Searching for relevant background videos...")
bg_video_paths = []

# 🧪 A/B EXPERIMENT: 60% chance to use local high-retention collection
LOCAL_BG_DIR = "assets/backgrounds/local"
is_local_experiment = random.random() < 0.8 if os.path.exists(LOCAL_BG_DIR) else False
local_bg_pool = []
if is_local_experiment:
    local_bg_pool = [os.path.join(LOCAL_BG_DIR, f) for f in os.listdir(LOCAL_BG_DIR) if f.endswith(".mp4")]
    if local_bg_pool:
        print(f"[Log] 🧪 SEARCH_EXPERIMENT: Local Collection Selected (60% Bucket)")
    else:
        print(f"[Log] [Warning] Local experiment selected but pool is empty, falling back to Pexels.")
        is_local_experiment = False

def get_video_duration(path):
    """Gets duration of a video using ffprobe."""
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[Warning] Failed to get duration for {path}: {e}")
        return 10.0 # Fallback

def get_bg_path(query, out_path, target_duration=15.0):
    if getattr(args, "bg_media", None) and os.path.exists(args.bg_media):
        from engine.media_gen import download_background_video
        path = download_background_video(query, output_path=out_path, custom_bg=args.bg_media)
        return [path] if path else []

    if is_local_experiment and local_bg_pool:
        # Pick one or more random videos from the local pool until target_duration is covered
        selected_paths = []
        current_len = 0
        while current_len < target_duration and local_bg_pool:
            choice = random.choice(local_bg_pool)
            d = get_video_duration(choice)
            selected_paths.append(os.path.abspath(choice))
            current_len += d
            if len(local_bg_pool) > 1: local_bg_pool.remove(choice)
            if not local_bg_pool: break # Pool exhausted
        return selected_paths

    if args.use_comfy:
        from engine.media_gen import generate_ai_background
        path = generate_ai_background(query, output_path=out_path.replace(".mp4", ".png"))
        if path: return [path]
        print("[Warning] ComfyUI failed, falling back to Pexels...")
    from engine.media_gen import download_background_video
    path = download_background_video(query, output_path=out_path)
    return [path] if path else []

# Calculate segments for staggered backgrounds
audio_duration = get_video_duration(audio_path)
total_bg_duration = audio_duration + 1.5

if mode == "FACTS":
    # 3 facts, 3 segments
    seg_len = total_bg_duration / 3
    for i, fact in enumerate(facts_data):
        bg_filename = os.path.join(session_dir, f"bg_fact_{i+1}.mp4")
        paths = get_bg_path(fact['fact'], bg_filename, target_duration=seg_len)
        bg_video_paths.extend(paths)
elif mode == "STORY":
    # 2 segments
    seg_len = total_bg_duration / 2
    is_custom_kids = bool(args.hero or args.interactive)
    
    for i in range(2):
        bg_filename = os.path.join(session_dir, f"bg_story_{i}.mp4")
        if is_custom_kids:
            if args.use_comfy:
                search_query = f"Whimsical Pixar style 3D render, claymation, cute colorful cartoon illustration for children, scene {i+1}: {story_data['story']}"
            else:
                search_query = f"{args.setting or category or 'magical forest'}"
        else:
            search_query = f"{category} {story_data['title']}"
            
        paths = get_bg_path(search_query, bg_filename, target_duration=seg_len)
        bg_video_paths.extend(paths)
elif mode == "FIND_IT" or mode == "FIND_CAT": # Supporting old flag for safety
    from engine.media_gen import get_game_assets
    # Pass a custom directory or unique prefix if possible (get_game_assets needs update)
    game_assets = get_game_assets(50, output_dir=session_dir)
    target_path = game_assets["target_path"]
    target_name = game_assets["target_name"]
    obj_paths = game_assets["objects"]
    if not target_path:
        print(f"[Error] Failed to download {target_name} image.", flush=True)
        sys.exit(0)
elif mode == "WYR":
    # 2 backgrounds for split screen
    seg_len = total_bg_duration / 2
    search_query = f"{category} satisfying"
    for i in range(2):
        bg_filename = os.path.join(session_dir, f"bg_wyr_{i}.mp4")
        paths = get_bg_path(search_query if i == 0 else "minecraft parkour", bg_filename, target_duration=seg_len)
        bg_video_paths.extend(paths)
elif mode == "REDDIT":
    bg_filename = os.path.join(session_dir, "bg_reddit.mp4")
    paths = get_bg_path("satisfying sand", bg_filename, target_duration=total_bg_duration)
    bg_video_paths.extend(paths)
elif mode == "TRIVIA":
    bg_filename = os.path.join(session_dir, "bg_trivia.mp4")
    paths = get_bg_path("minecraft parkour", bg_filename, target_duration=total_bg_duration)
    bg_video_paths.extend(paths)
elif mode == "QUOTE":
    bg_filename = os.path.join(session_dir, "bg_quote.mp4")
    paths = get_bg_path("dark cinematic moody slow motion", bg_filename, target_duration=total_bg_duration)
    bg_video_paths.extend(paths)
elif mode == "ODD_ONE_OUT":
    from engine.media_gen import get_game_assets
    game_assets = get_game_assets(1, output_dir=session_dir)
    target_path = game_assets["target_path"]
    target_name = game_assets["target_name"]
    if not target_path:
        print(f"[Error] Failed to download {target_name} image for ODD_ONE_OUT.", flush=True)
        sys.exit(0)
elif mode in ("NEWS", "NEWS_SERIOUS"):
    search_query = news_data.get('search_term', 'breaking news broadcast') if 'news_data' in locals() else 'breaking news broadcast'
    bg_filename = os.path.join(session_dir, "bg_news.mp4")
    paths = get_bg_path(search_query, bg_filename, target_duration=total_bg_duration)
    if not paths:
        paths = get_bg_path("news studio broadcast", os.path.join(session_dir, "bg_news_fallback.mp4"), target_duration=total_bg_duration)
    bg_video_paths.extend(paths)
elif mode == "GUESS_SOUND":
    bg_filename = os.path.join(session_dir, "bg_sound.mp4")
    paths = get_bg_path("satisfying sand", bg_filename, target_duration=total_bg_duration)
    bg_video_paths.extend(paths)
    
    # Download object image for reveal
    obj_filename = os.path.join(session_dir, "reveal_obj.png")
    download_image(sound_data["object"], output_path=obj_filename)
    
    # Download sound effect
    sfx_filename = os.path.join(session_dir, "challenge_sfx.mp3")
    download_sfx(sound_data["sound_query"], output_path=sfx_filename)
    bg_filename = os.path.join(session_dir, "bg_gen.mp4")
    path = get_bg_path(category + " satisfying", bg_filename)
    if path: bg_video_paths.append(path)
elif mode == "RIDDLE":
    bg_filename = os.path.join(session_dir, "bg_riddle.mp4")
    paths = get_bg_path(category + " background", bg_filename, target_duration=total_bg_duration)
    bg_video_paths.extend(paths)
    clue_path = None
elif mode == "JWST":
    print("[Log] Fetching James Webb Telescope images...")
    bg_video_paths = fetch_jwst_images(num_images=random.randint(1, 4))
    if not bg_video_paths:
        print("[Warning] No JWST images found, falling back to Pexels space video.")
        bg_filename = os.path.join(session_dir, "bg_jwst_fallback.mp4")
        bg_video_paths = get_bg_path("outer space james webb telescope", bg_filename)
elif mode == "EXPLAINER":
    print("[Log] Rendering Manim animation code...")
    from engine.video_gen import render_manim_scene
    manim_mp4 = render_manim_scene(manim_data["code"], output_dir=session_dir, extract_mode=args.extract_mode)
    bg_video_paths = [manim_mp4]
elif mode == "TRAILER_MISSED":
    if not getattr(args, "source_video", None):
        print("[Error] --source_video is required for TRAILER_MISSED mode.")
        sys.exit(1)
        
    print("[Log] Extracting high-energy clips from trailer video to use as backgrounds...")
    temp_trailer_dir = os.path.join(session_dir, "trailer_clips")
    os.makedirs(temp_trailer_dir, exist_ok=True)
    
    from engine.analysis import process_source_video
    from engine.video_gen import extract_segments
    
    # We want 5 highlights of about 8 seconds each
    highlights, transcript_path, interest_points, silence_intervals = process_source_video(
        args.source_video, temp_trailer_dir, mode="shorts", 
        clip_count=5, target_duration=8,
        use_audio_detect=True
    )
    
    extracted_files = extract_segments(
        args.source_video, highlights, transcript_path, temp_trailer_dir, 
        mode="shorts", bitrate=target_bitrate, preset=target_preset, codec="libx264",
        is_challenge=False, use_hq=args.hq, 
        editing_style=args.style, gif_dir=args.gif_dir,
        interest_points=interest_points, silence_intervals=None,
        use_remotion=args.use_remotion,
        caption_style=args.caption_style, subtitle_y_pos=args.subtitle_y_pos
    )
    
    bg_video_paths = extracted_files

if mode not in ["FIND_IT", "FIND_CAT", "ODD_ONE_OUT"] and not any(bg_video_paths):
    print("[Error] Failed to download any background videos.")
    sys.exit(0)

if args.video_id and args.user_id:
    report_status(args.video_id, args.user_id, "In-Progress Video", "Processing", None, mode)

# 4. Compose Video
print(f"[Log] Composing final interactive video with {args.vibe} mood (Job ID: {session_id})...", flush=True)
output_filename = f"interactive_short_{session_id}.mp4"

# Dynamic Music Selection based on Vibe
vibe_music_map = {
    "suspense": "music/bg_music.mp3",
    "spooky": "music/spooky.mp3",
    "cinematic": "music/cinematic.mp3",
    "upbeat": "music/upbeat.mp3"
}
music_file = vibe_music_map.get(args.vibe, "music/bg_music.mp3")
bg_music = music_file if os.path.exists(music_file) else "music/bg_music.mp3"

# 🟢 PRO CONFIG: Unique AI Music generation
if args.use_ai_audio:
    from engine.comfy_bridge import generate_ai_audio
    print(f"[Log] Generating UNIQUE AI soundtrack for vibe: {args.vibe}")
    # Prompt based on vibe + category
    music_prompt = f"{args.vibe} cinematic {category} background music, high quality, studio grade"
    ai_music = generate_ai_audio(music_prompt, duration=30)
    if ai_music:
        bg_music = ai_music
        print(f"[Log] Using AI-generated soundtrack: {bg_music}")
    else:
        print("[Warning] AI Music generation failed, falling back to stock music.")

remotion_supported_modes = ["FACTS", "STORY", "NEWS", "NEWS_SERIOUS", "RIDDLE", "WYR"]
if args.use_remotion and mode in remotion_supported_modes:
    from engine.remotion_renderer import render_with_remotion
    
    remotion_mode = mode
    this_or_that_data = None
    
    if mode == "WYR":
        remotion_mode = "THIS_OR_THAT"
        path_a = bg_video_paths[0] if len(bg_video_paths) > 0 else None
        path_b = bg_video_paths[1] if len(bg_video_paths) > 1 else (path_a if path_a else None)
        this_or_that_data = {
            "option_a": wyr_data.get("option_a", "Option A"),
            "option_b": wyr_data.get("option_b", "Option B"),
            "path_a": path_a,
            "path_b": path_b
        }
    
    final_video = render_with_remotion(
        audio_path=audio_path,
        subs_path=subs_path,
        output_path=output_filename,
        mode=remotion_mode,
        bg_music_path=bg_music,
        title_text=args.recap_title or args.category or "ShortsFlow",
        background_paths=bg_video_paths,
        this_or_that=this_or_that_data,
        caption_style=getattr(args, "caption_style", "HORMOZI")
    )
else:
    if mode == "FIND_IT" or mode == "FIND_CAT":
        from engine.video_gen import create_game_video
        final_video = create_game_video(
            audio_path,
            subs_path,
            target_path,
            obj_paths,
            output_filename,
            target_name=target_name,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "WYR":
        from engine.video_gen import create_wyr_video
        final_video = create_wyr_video(
            audio_path,
            wyr_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "REDDIT":
        from engine.video_gen import create_reddit_video
        final_video = create_reddit_video(
            audio_path,
            subs_path,
            reddit_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "TRIVIA":
        from engine.video_gen import create_trivia_video
        final_video = create_trivia_video(
            audio_path,
            trivia_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "QUOTE":
        from engine.video_gen import create_quote_video
        final_video = create_quote_video(
            audio_path,
            quote_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "ODD_ONE_OUT":
        from engine.video_gen import create_odd_one_out_video
        final_video = create_odd_one_out_video(
            audio_path,
            target_path,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "RIDDLE":
        from engine.video_gen import create_riddle_video
        final_video = create_riddle_video(
            audio_path,
            riddle_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset,
            clue_path=clue_path
        )
    elif mode == "GUESS_SOUND":
        from engine.video_gen import create_sound_challenge_video
        sfx_path = os.path.join(session_dir, "challenge_sfx.mp3")
        obj_path = os.path.join(session_dir, "reveal_obj.png")
        final_video = create_sound_challenge_video(
            audio_path,
            subs_path,
            sfx_path,
            obj_path,
            bg_video_paths,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    elif mode == "EXPLAINER":
        from engine.video_gen import create_explainer_video
        final_video = create_explainer_video(
            audio_path,
            manim_mp4,
            output_filename,
            music_path=bg_music,
            bitrate=target_bitrate,
            preset=target_preset
        )
    else:
        # Check for avatar if persona is active
        avatar_path = None
        # 🟢 UPGRADE: Mafia Cat is now the default persona for Cartoon News
        selected_persona = args.persona if args.persona else ("mafia_cat" if args.cartoon else None)
        if selected_persona:
            for ext in [".mp4", ".mov", ".png"]:
                p_path = f"assets/avatars/{selected_persona.lower()}{ext}"
                if os.path.exists(p_path):
                    avatar_path = p_path
                    break

        final_video = create_shorts_video(
            audio_path, 
            subs_path, 
            bg_video_paths, 
            output_filename,
            music_path=bg_music,
            mode=mode,
            use_ai_audio=args.use_ai_audio,
            bitrate=target_bitrate,
            preset=target_preset,
            avatar_path=avatar_path,
            category=category
        )

print(f"[Log] SUCCESS! Interactive video created: {final_video}")

# 5. Social Media Automation
# 5. Viral Metadata Generation (Required for both Upload and Local Report)
print("[Log] Generating viral metadata...")
from engine.social_gen import generate_viral_metadata, generate_pinterest_metadata, YouTubeUploader, InstagramUploader, PinterestUploader

def ensure_dict(data):
    if isinstance(data, list) and len(data) > 0:
        data = data[0]
    if not isinstance(data, dict):
        return {"title": "Viral Short", "description": "", "tags": []}
    
    # Ensure description is a string
    desc = data.get("description", "")
    if isinstance(desc, list):
        data["description"] = "\n".join([str(i) for i in desc])
    elif not isinstance(desc, str):
        data["description"] = str(desc)
    
    # Ensure title is a string
    title = data.get("title", "")
    if not isinstance(title, str):
        data["title"] = str(title) if title else "Viral Short"
        
    return data

if mode == "FACTS":
    metadata = ensure_dict(generate_viral_metadata(facts_data, category=category))
elif mode == "FIND_IT" or mode == "FIND_CAT":
    metadata = ensure_dict(generate_viral_metadata({"target_name": target_name}, mode="FIND_IT"))
elif mode == "WYR":
    metadata = ensure_dict(generate_viral_metadata(f"Would You Rather: {wyr_data['option_a']} OR {wyr_data['option_b']}", mode="STORY", category=category))
elif mode == "REDDIT":
    metadata = ensure_dict(generate_viral_metadata(reddit_data['story'], mode="STORY", category=category))
    # Use reddit title but enforce YouTube's length limit (100 chars max, use 95 for safety)
    metadata['title'] = reddit_data['title'][:95]
elif mode == "TRIVIA":
    metadata = ensure_dict(generate_viral_metadata(f"Trivia: {trivia_data['question']} Did you guess right?", mode="STORY", category=category))
elif mode == "QUOTE":
    metadata = ensure_dict(generate_viral_metadata(f"Deep Quote: {quote_data['quote']}", mode="STORY", category=category))
elif mode == "ODD_ONE_OUT":
    metadata = ensure_dict(generate_viral_metadata({"target_name": f"Odd {target_name}"}, mode="FIND_IT"))
elif mode in ("NEWS", "NEWS_SERIOUS"):
    metadata = ensure_dict(generate_viral_metadata(news_data.get('story', 'Breaking News'), mode="NEWS", category=category))
    # Append source credit to description
    source_credit = news_data.get('source', '')
    if source_credit:
        metadata['description'] = metadata.get('description', '') + f"\n\n📰 Source: {source_credit}"
elif mode == "GUESS_SOUND":
    metadata = ensure_dict(generate_viral_metadata(f"Can you guess this sound? It's a {sound_data['object']}", mode="STORY", category=category))
else:
    # For STORY or other modes
    story_content = story_data['story'] if 'story_data' in locals() and story_data else "Viral Story"
    metadata = ensure_dict(generate_viral_metadata(story_content, mode=mode, category=category))

# Ensure title is never empty or too long
if not metadata.get("title"):
    metadata["title"] = f"Shocking {category} reveal! 😱"
metadata["title"] = (metadata["title"] or "Viral Short")[:95]

print(f"[Log] Viral Title: {metadata['title']}")

if args.video_id and args.user_id:
    report_status(args.video_id, args.user_id, metadata['title'], "Processing", None, mode)

# 6. Social Media Automation
actually_skip_upload = args.skip_upload

if not actually_skip_upload:
    print("[Log] Checking for user-specific upload credentials...")
    from engine.social_gen import YouTubeUploader, InstagramUploader
    
    youtube_creds = None
    if args.user_id:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Use Service Role for backend
        
        if supabase_url and supabase_key:
            supabase: Client = create_client(supabase_url, supabase_key)
            user_res = supabase.from_("user_configs").select("*").eq("user_id", args.user_id).execute()
            
            if user_res.data:
                config = user_res.data[0]
                # Logic: If user has a refresh token, we need a client_id/secret to use it.
                # We check for User-Specific (BYOK) first, then fallback to Global (Platform) env vars.
                refresh_token = decrypt_secret(config.get("youtube_refresh_token"))
                
                if refresh_token:
                    client_id = decrypt_secret(config.get("youtube_client_id")) or os.getenv("GOOGLE_CLIENT_ID")
                    client_secret = decrypt_secret(config.get("youtube_client_secret")) or os.getenv("GOOGLE_CLIENT_SECRET")
                    
                    if client_id and client_secret:
                        youtube_creds = {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "refresh_token": refresh_token
                        }
                        print(f"[Log] YouTube credentials initialized for user: {args.user_id}")
                    else:
                        print(f"[Warning] Refresh token present but GOOGLE_CLIENT_ID/SECRET missing for user {args.user_id}. Skipping upload to protect admin channel.")
                        actually_skip_upload = True
                else:
                    print(f"[Log] No YouTube refresh token found for user {args.user_id}. Skipping upload (Manual triggers do not fallback to admin).")
                    actually_skip_upload = True
            else:
                print(f"[Log] No configuration found for user {args.user_id} in Supabase. Skipping upload.")
                actually_skip_upload = True
        else:
            print("[Warning] SUPABASE_URL or SERVICE_ROLE_KEY missing. Skipping user-specific upload check.")
            actually_skip_upload = True

    if not actually_skip_upload:
        print("[Log] Initializing YouTube Uploader...")
        uploader = YouTubeUploader()
        youtube_video_id = None
        if uploader.authenticate(creds_dict=youtube_creds):
            youtube_video_id = uploader.upload_video(
                final_video, 
                metadata['title'],
                metadata['description'],
                metadata['tags']
            )
        else:
            print("🚀 YouTube Auth failed or skipped.")

    # 6c. Optional Pinterest Upload
    if args.pinterest and not actually_skip_upload:
        print("[Log] Pinterest upload flag detected. Generating Pinterest-specific SEO metadata...")
        # Note: We pass the core data to ensure Pinterest gets its own optimized keywords
        pinterest_info = facts_data if mode == "FACTS" else (story_data if 'story_data' in locals() else {"title": metadata['title']})
        p_metadata = generate_pinterest_metadata(pinterest_info, mode=mode, category=category)
        
        print(f"[Log] Pinterest Title: {p_metadata['title']}")
        p_uploader = PinterestUploader()
        p_uploader.upload_video(
            final_video,
            p_metadata['title'],
            p_metadata['description'],
            link=args.pinterest_link
        )

    # 6d. Optional Instagram Upload
    if args.instagram and not actually_skip_upload:
        print("[Log] Instagram uploader ready.")
        ig_uploader = InstagramUploader()
        ig_uploader.upload_reel(final_video, f"{metadata['title']}\n\n{metadata['description']}")

if actually_skip_upload:
    print("[Log] Skip Upload flag detected (or forced). Social media steps ignored.")

# 7. Permanent Storage Persistence (New Step)
if args.video_id and args.user_id:
    os.environ["USER_ID"] = args.user_id
    print(f"[Log] Persisting video and thumbnail to cloud storage for user {args.user_id}...")
    from engine.storage import upload_to_storage
    
    # 7a. Extract thumbnail first
    thumbnail_file = f"thumb_{session_id}.jpg"
    thumbnail_path = None
    try:
        import subprocess
        print(f"[Log] Extracting thumbnail from {final_video}...")
        subprocess.run([
            'ffmpeg', '-y', '-i', final_video, 
            '-ss', '00:00:01', '-vframes', '1', 
            thumbnail_file
        ], check=True, capture_output=True)
        thumbnail_path = upload_to_storage(thumbnail_file, args.video_id, is_video=False)
        try: os.remove(thumbnail_file)
        except: pass
    except Exception as te:
        print(f"[Warning] Thumbnail extraction/upload failed: {te}")

    # 7b. Upload video
    storage_path = upload_to_storage(final_video, args.video_id, is_video=True)

    # 8. Report Success to Dashboard
    print(f"[Log] Reporting success to dashboard for Job {args.video_id}...")
    report_status(
        args.video_id, 
        args.user_id, 
        metadata['title'], 
        "Published", 
        None, 
        args.mode or mode,
        youtube_video_id,
        storage_path,
        thumbnail_path
    )

with open(f"{output_filename}.txt", "w", encoding="utf-8") as f:
    f.write(f"Title: {metadata['title']}\n")
    f.write(f"Description: {metadata['description']}\n")
    f.write(f"Tags: {', '.join(metadata['tags'])}\n")

if __name__ == "__main__":
    pass # Script runs globally
