"""music pipeline, moved verbatim from main.py (runs when: getattr(args, "mode", None) == "MUSIC")."""
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
from supabase import create_client, Client
from engine.utils import decrypt_secret, find_fact_start_times
from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge, generate_odd_one_out_script, generate_riddle, generate_jwst_script
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx, fetch_jwst_images, is_url, download_source_video_from_url
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage
from engine.pipeline import report_status


def run(args, target_bitrate, target_preset):
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
