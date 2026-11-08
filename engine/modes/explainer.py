"""explainer pipeline, moved verbatim from main.py (runs when: getattr(args, "mode", None) == "EXPLAINER")."""
import os
import sys
from engine.pipeline import report_status


def run(args, target_bitrate, target_preset):
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
    
    # The model writes the animation code, and its code can crash when rendered, so a failed render gets a fresh script
    # (up to 3 tries) instead of ending the run. The voiceover is made once a script has rendered.
    script_data, manim_output_path, last_error = None, None, None
    for attempt in range(1, 4):
        script_data = generate_manim_script(topic, extract_mode=extract_mode)
        print(f"[Log] LLM Script Generated (attempt {attempt}). Title: {script_data.get('title', topic)}")
        try:
            manim_output_path = render_manim_scene(script_data['code'], session_dir, extract_mode=extract_mode)
            break
        except Exception as e:
            last_error = e
            print(f"[Warning] Manim render failed on attempt {attempt}/3: {str(e)[-300:]}")
    if manim_output_path is None and last_error is not None:
        raise last_error
    title = script_data.get('title', f"Explainer: {topic}")

    # 1. Generate Voiceover
    from engine.voice_gen import generate_voice
    voiceover_text = script_data.get('voiceover_text', f"Today we are explaining {topic}.")
    audio_path, subs_path = generate_voice(
        voiceover_text,
        output_audio=os.path.join(session_dir, "voice.mp3"),
        output_subs=os.path.join(session_dir, "subs.json"),
        add_cta=False
    )

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
                except Exception: return 0.1
                
            v_dur = get_dur(manim_output_path)
            a_dur = get_dur(audio_path)
            # Cap speed factor to prevent insane warping (0.6x to 1.5x)
            raw_speed = a_dur / v_dur if v_dur > 0 else 1.0
            speed_factor = max(0.6, min(1.5, raw_speed))
            print(f"[Log] Synchronizing Explainer Timing... Video: {v_dur:.2f}s, Audio: {a_dur:.2f}s (Raw Stretch: {raw_speed:.2f}x, Capped: {speed_factor:.2f}x)")

            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", manim_output_path,
                "-i", audio_path,
                # stop_duration=60 ensures an indefinite freeze frame so -shortest can cleanly cut at audio length
                "-vf", f"setpts={speed_factor}*PTS,tpad=stop_mode=clone:stop_duration=60",
                "-c:v", "libx264",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{a_dur:.3f}", merged_path
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
