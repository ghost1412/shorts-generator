"""photo_reel pipeline, moved verbatim from main.py (runs when: getattr(args, "mode", None) == "PHOTO_REEL")."""
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
from engine.utils import decrypt_secret, find_fact_start_times
from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge, generate_odd_one_out_script, generate_riddle, generate_jwst_script
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx, fetch_jwst_images, is_url, download_source_video_from_url
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage



def default_music_or_silence(session_dir, seconds):
    """A track for a photo reel made without --music: the bundled background music, else a silent file. The Remotion
    renderer needs an audio file, and used to stop with 'Voice audio path not found' when there was none."""
    from engine.paths import project_root
    bundled = os.path.join(project_root(), "music", "bg_music.mp3")
    if os.path.isfile(bundled):
        return bundled
    silent = os.path.join(session_dir, "silence.mp3")
    try:
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-t", str(max(1.0, float(seconds))), "-q:a", "9", silent], capture_output=True, check=True)
        return silent
    except Exception as e:
        print(f"[Warning] Could not create a silent track ({e}).")
        return None


def run(args, target_bitrate, target_preset):
    from engine.beat_sync import detect_beats
    from engine.video_gen import create_photo_reel_video
    from engine.remotion_renderer import render_with_remotion
    from engine.media_gen import is_url, download_source_video_from_url

    photos_dir = getattr(args, "photos_dir", None)
    music_path = getattr(args, "music", None)

    if not photos_dir or not os.path.exists(photos_dir):
        print("[Error] Standalone PHOTO_REEL mode requires valid --photos_dir parameter.")
        sys.exit(1)

    session_dir = args.session_dir if args.session_dir else f"sessions/photoreel_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)

    # Automatically download music if a YouTube URL is provided
    if music_path and is_url(music_path):
        print(f"[Log] 🎵 Detected URL for music: '{music_path}'. Downloading audio track...")
        music_path = download_source_video_from_url(music_path, session_dir, filename="youtube_music.mp4")

    # Extract audio to MP3 if music_path is a video container for HTML5/Remotion compatibility
    if music_path and os.path.exists(music_path):
        ext = os.path.splitext(music_path)[1].lower()
        if ext in ['.mp4', '.mov', '.mkv', '.webm', '.avi']:
            mp3_out = os.path.join(session_dir, "clean_music.mp3")
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                subprocess.run([
                    ffmpeg_exe, "-y", "-i", music_path,
                    "-vn", "-acodec", "libmp3lame", "-q:a", "2", mp3_out
                ], capture_output=True, check=True)
                music_path = mp3_out
                print(f"[Log] 🎵 Converted music track to clean MP3 for Remotion compatibility: {music_path}")
            except Exception as e:
                print(f"[Warning] MP3 extraction failed: {e}. Using original audio file.")

    valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.heic')
    photo_files = sorted([
        os.path.join(photos_dir, f) for f in os.listdir(photos_dir)
        if f.lower().endswith(valid_exts)
    ])

    if not photo_files:
        print(f"[Error] No image files ({valid_exts}) found in directory: {photos_dir}")
        sys.exit(1)

    photo_captions = None
    plan = None
    reel_type = getattr(args, "reel_type", None)
    if reel_type:
        # A reel TYPE decides which photos are used (blurry / duplicate ones are dropped), their order, how long each is held,
        # the captions, the title and the look. Without a type the original behaviour below is unchanged.
        from engine.photo_reel_types import parse_texts, plan_reel
        try:
            plan = plan_reel(photo_files, reel_type, target_duration=float(getattr(args, "target_duration", 30) or 30),
                             name=getattr(args, "prompt", None), texts=parse_texts(getattr(args, "reel_text", None)))
        except ValueError as e:
            print(f"[Error] {e}")
            sys.exit(2)
        photo_files, photo_captions = plan["photos"], plan["captions"]
        args.use_remotion = True       # captions, titles and the look are drawn by the animated renderer
        print(f"[Log] 🎞️ Reel type '{plan['label']}': {len(photo_files)} photo(s) used"
              + (f", {plan['dropped']} skipped (blurry, duplicate or unreadable)" if plan["dropped"] else "") + f"; title: {plan['title']!r}")

    # 🧠 Vision LLM Story Arc Analysis (if --smart_story flag is set)
    if getattr(args, "smart_story", False) and not plan:
        from engine.script_gen import analyze_photo_story_with_vision
        vision_res = analyze_photo_story_with_vision(photo_files, user_prompt=getattr(args, "prompt", None))
        ordered_indices = vision_res.get("ordered_indices", [])
        photo_captions = vision_res.get("captions", [])
        if ordered_indices and len(ordered_indices) == len(photo_files):
            try:
                photo_files = [photo_files[idx] for idx in ordered_indices]
                if photo_captions and len(photo_captions) == len(photo_files):
                    photo_captions = [photo_captions[idx] for idx in ordered_indices]
                print(f"[Log] 🧠 Re-ordered {len(photo_files)} photos into a narrative story arc!")
            except Exception as e:
                print(f"[Warning] Could not reorder photos: {e}")

    session_dir = args.session_dir if args.session_dir else f"sessions/photoreel_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    out_video = os.path.join(session_dir, "photo_reel.mp4")

    target_dur = getattr(args, "target_duration", 30) or 30

    if not music_path and getattr(args, "use_remotion", False):
        music_path = default_music_or_silence(session_dir, target_dur)
        if music_path:
            print(f"[Log] No --music given: using {os.path.basename(music_path)} under the photos.")

    # Detect beats in input audio if provided (capped at target_duration)
    # Music the user chose: cut to its beat. A reel type without their music uses its own timing (hero photos held longer).
    beat_timestamps = detect_beats(music_path, target_count=len(photo_files), max_duration=target_dur)         if music_path and (not plan or getattr(args, "music", None)) else None
    if plan and not (beat_timestamps and len(beat_timestamps) == len(photo_files)):
        beat_timestamps = plan["starts"]
    print(f"[Log] 📸 Loaded {len(photo_files)} photos for PHOTO_REEL mode.")
    if beat_timestamps and plan and beat_timestamps == plan["starts"]:
        print(f"[Log] ⏱️ Timing from the reel type: {len(beat_timestamps)} photos over {target_dur}s (first and last held longer).")
    elif beat_timestamps:
        print(f"[Log] 🎵 Beat detection completed: {len(beat_timestamps)} timestamps extracted over {target_dur}s.")

    if plan and not getattr(args, "use_remotion", False):
        print("[Log] Reel types need the animated renderer: turning on --use_remotion.")
        args.use_remotion = True

    if getattr(args, "use_remotion", False):
        print("[Log] 🎬 Rendering Photo Reel using Remotion React engine...")
        render_with_remotion(
            audio_path=music_path if music_path else None,
            subs_path=None,
            output_path=out_video,
            mode="PHOTO_REEL",
            bg_music_path=music_path,
            title_text=plan["title"] if plan else getattr(args, "prompt", None), # Only show title if --prompt is explicitly set
            duration=plan["duration"] if plan else None, reel_style=plan["style"] if plan else None,
            background_paths=photo_files,
            beat_timestamps=beat_timestamps,
            captions=photo_captions,
            caption_style=getattr(args, "caption_style", "HORMOZI")
        )
    else:
        print("[Log] 🎬 Rendering Photo Reel using FFmpeg/MoviePy pipeline...")
        create_photo_reel_video(
            photo_paths=photo_files,
            music_path=music_path,
            output_path=out_video,
            beat_timestamps=beat_timestamps,
            target_duration=getattr(args, "target_duration", 30)
        )

    print(f"[Success] 🎉 Photo Reel rendered successfully: {out_video}")
    sys.exit(0)
