import json
import os
import numpy as np
import random
import subprocess
import time
import importlib
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# moviepy 2.2.1 Bulletproof Imports via importlib
def safe_import(module_name, class_name):
    try:
        mod = importlib.import_module(module_name)
        return getattr(mod, class_name)
    except Exception as e:
        print(f"[Critical] Failed to import {class_name} from {module_name}: {e}")
        return None

VideoFileClip = safe_import("moviepy.video.io.VideoFileClip", "VideoFileClip")
AudioFileClip = safe_import("moviepy.audio.io.AudioFileClip", "AudioFileClip")
ColorClip = safe_import("moviepy.video.VideoClip", "ColorClip")
ImageClip = safe_import("moviepy.video.VideoClip", "ImageClip")
CompositeVideoClip = safe_import("moviepy.video.compositing.CompositeVideoClip", "CompositeVideoClip")
concatenate_videoclips = safe_import("moviepy.video.compositing.CompositeVideoClip", "concatenate_videoclips")
CompositeAudioClip = safe_import("moviepy.audio.AudioClip", "CompositeAudioClip")

# --- DYNAMIC SAFE ZONES (Prevents UI overlap) ---
def get_safe_zones(size=(1080, 1920)):
    w, h = size
    return (int(h * 0.11), int(h * 0.39), int(h * 0.83))

def apply_audio_ducking(audio_clip, music_path, duration, duck_vol=0.12):
    """Simplified audio ducking without effects classes."""
    if not music_path or not os.path.exists(music_path):
        return audio_clip
    try:
        music = AudioFileClip(music_path).with_duration(duration)
        return CompositeAudioClip([audio_clip, music]).with_duration(duration)
    except Exception as e:
        print(f"[Warning] Audio ducking failed: {e}")
        return audio_clip

def apply_handheld_jitter(clip, intensity=1.5):
    """Handheld jitter using position transform."""
    def jitter_pos(t):
        x = int(intensity * np.sin(t * 7) * np.cos(t * 3))
        y = int(intensity * np.cos(t * 8))
        return (x, y)
    return clip.with_position(jitter_pos)

def apply_progress_bar(clip, duration, color=(0, 255, 0), height=40):
    """Adds a dynamic filling progress bar at the bottom of the clip."""
    # Background bar (dark)
    bg_bar = ColorClip(size=(int(clip.w * 0.8), height), color=(50, 50, 50)).with_duration(duration).with_position(("center", clip.h - 250)).with_opacity(0.6)
    
    # Filling bar
    fill_bar = ColorClip(size=(int(clip.w * 0.8), height), color=color).with_duration(duration)
    # Slide in from left within the 80% width container
    fill_bar = fill_bar.with_position(lambda t: (int((t/duration)*clip.w*0.8) - int(clip.w*0.8) + (clip.w - int(clip.w*0.8))//2, clip.h - 250))
    
    return [bg_bar, fill_bar]

def create_text_image(text, size=(1080, 1920), font_size=50, color="white", y_pos=None):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font_paths = ["C:/Windows/Fonts/Montserrat-Bold.ttf", "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arial.ttf"]
        font = None
        for p in font_paths:
            if os.path.exists(p):
                font = ImageFont.truetype(p, font_size)
                break
        if not font: font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    w, h = draw.textbbox((0, 0), text, font=font)[2:]
    x = (size[0] - w) // 2
    y = y_pos if y_pos is not None else (size[1] - h) // 2
    draw.text((x-3, y-3), text, font=font, fill="black"); draw.text((x+3, y+3), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill=color)
    return np.array(img)

def apply_influencer_subtitles(clip, transcript_data, start_offset, end_offset, size=(1920, 1080), y_pos=850):
    word_clips = []
    viral_colors = ["yellow", "#00FF00", "cyan", "white", "orange"]
    relevant_words = []
    for segment in transcript_data.get('segments', []):
        if segment['end'] < start_offset or segment['start'] > end_offset: continue
        for word in segment.get('words', []):
            if word['start'] >= start_offset and word['end'] <= end_offset:
                relevant_words.append({"word": word['word'].strip(), "start": word['start'] - start_offset, "end": word['end'] - start_offset, "duration": word['end'] - word['start']})
    for j, word in enumerate(relevant_words):
        color = viral_colors[j % len(viral_colors)] if j % 4 == 0 else "white"
        img = create_text_image(word["word"].upper(), size=size, font_size=115, color=color, y_pos=y_pos)
        c = ImageClip(img).with_start(word["start"]).with_duration(max(0.1, word["duration"])).with_position("center")
        word_clips.append(c)
    return word_clips

def create_shorts_video(audio_path, subs_path, video_paths, output_path, music_path=None, mode="FACTS", bitrate="25M", preset="medium"):
    audio = AudioFileClip(audio_path); duration = audio.duration
    bg = VideoFileClip(video_paths[0]).with_duration(duration)
    final = CompositeVideoClip([bg]).with_audio(audio)
    final.write_videofile(output_path, fps=24, codec="libx264", bitrate=bitrate, preset=preset, threads=8)
    return output_path

def extract_segments(source_path, highlights, transcript_data, output_dir, mode="shorts", bitrate="12M", preset="slow", codec="libx264", is_challenge=False):
    """Parallel extraction of segments."""
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    
    # Filter short segments
    valid_highlights = [h for h in highlights if (h['end'] - h['start']) >= 0.5]
    if len(valid_highlights) < len(highlights):
        print(f"[Log] Filtered out {len(highlights) - len(valid_highlights)} ultra-short segments.")
        highlights = valid_highlights

    target_res = (1920, 1080) if mode == "long" else (1080, 1920)
    w, h = target_res
    
    scaling_alg = "lanczos"
    final_bitrate = bitrate or ("25M" if mode == "long" else "12M")
    final_preset = preset or ("medium" if mode == "long" else "slow")
    segment_crf = "16" 
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.join(output_dir, "temp_segments"), exist_ok=True)
    
    print(f"[Log] Robust Parallel Extraction: {len(highlights)} segments...")
    
    processes = []
    POOL_SIZE = 8
    
    # 🟢 HARDWARE DETECTION: Check for NVENC once per extraction session
    def _check_nvenc():
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            res = subprocess.run([ffmpeg_exe, '-encoders'], capture_output=True, text=True, timeout=5)
            return 'h264_nvenc' in res.stdout
        except: return False
    
    _has_nvenc = _check_nvenc()
    if _has_nvenc: print("[Log] NVIDIA GPU Detected: Using NVENC for ultra-fast encoding 🚀")
    else: print("[Log] No NVIDIA GPU found: Using CPU (libx264) fallback.")

    for i, hi in enumerate(highlights):
        target = os.path.join(output_dir, "temp_segments", f"seg_{i}.mp4")
        duration = hi['end'] - hi['start']
        
        # 🟢 TEXT BURN
        font_file = "C\\:/Windows/Fonts/impact.ttf"
        reason_text = hi.get('reason', '').replace("'", "").replace(":", "").replace('"', "")
        
        text_filter = ""
        if mode == "long" and reason_text:
            draw_text = f"drawtext=fontfile='{font_file}':text='{reason_text}':fontcolor=cyan:fontsize=45:x=(w-text_w)/2:y=100:enable='between(t,0,3.5)':box=1:boxcolor=black@0.5:boxborderw=5"
            text_filter = f",{draw_text}"

        # 🟢 OPUS-STYLE RE-FRAMING (Auto-Crop 16:9 to 9:16)
        if mode == "shorts":
            crop_filter = "crop=ih*9/16:ih:(iw-ow)/2:0"
            vf_filter = f"tonemap=mobius:desat=2,{crop_filter},scale={w}:{h}:flags={scaling_alg},format=yuv420p"
        else:
            vf_filter = f"tonemap=mobius:desat=2,scale={w}:{h}:force_original_aspect_ratio=decrease:flags={scaling_alg},pad={w}:{h}:(ow-iw)/2:(oh-ih)/2{text_filter},format=yuv420p"
        
        # 🟢 HARDWARE ACCELERATION: Use NVENC (NVIDIA) only if supported
        use_gpu = _has_nvenc and codec == 'libx264'
        target_codec = 'h264_nvenc' if use_gpu else codec
        target_preset = 'p1' if use_gpu else 'ultrafast'
        
        cmd = [
            ffmpeg_exe, '-y', '-ss', str(hi['start']), '-i', source_path,
            '-t', str(duration), '-vf', vf_filter,
            '-c:v', target_codec, '-preset', target_preset,
            '-pix_fmt', 'yuv420p', # Force compatibility
            '-c:a', 'aac', '-b:a', '192k',
            target
        ]
        
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        processes.append(p)
        
        if len(processes) >= POOL_SIZE:
            for proc in processes: proc.communicate()
            processes = []

    for proc in processes: proc.communicate()

    extracted_files = []
    if mode == "long":
        print(f"[Log] Streamlined Long-Form Render: {len(highlights)} clips (Memory Optimized)")
        clips = []
        for i, hi in enumerate(highlights):
            task_path = os.path.join(output_dir, "temp_segments", f"seg_{i}.mp4")
            if not os.path.exists(task_path) or os.path.getsize(task_path) < 1000: continue
            
            try:
                # No more CompositeVideoClip needed! Burning directly into the MP4.
                clip = VideoFileClip(task_path)
                _ = clip.get_frame(0)
                clips.append(clip)
            except Exception as e:
                print(f"[Warning] Skipping corrupted segment {i}: {e}")
                continue
            
        if not clips: return []
            
        final_reel = concatenate_videoclips(clips, method="chain")
        out = os.path.join(output_dir, "highlight_reel.mp4")
        print(f"[Log] Encoding Final Reel (NVENC/GPU Optimized)...")
        final_reel.write_videofile(out, fps=24, bitrate=final_bitrate, preset=target_preset, threads=8, codec=target_codec)
        extracted_files.append(out)
        for clip in clips: clip.close()
    else:
        # Shorts mode: Still uses compositing but for much shorter clips
        for i, hi in enumerate(highlights):
            task_path = os.path.join(output_dir, "temp_segments", f"seg_{i}.mp4")
            if not os.path.exists(task_path) or os.path.getsize(task_path) < 1000: continue
            sub = VideoFileClip(task_path).with_position("center")
            sub = apply_handheld_jitter(sub)
            subs = apply_influencer_subtitles(sub, transcript_data, hi['start'], hi['end'], size=(1080, 1920), y_pos=960)
            
            # 🟢 DYNAMIC CHALLENGE OVERLAY (Progress Bar)
            overlays = subs
            if is_challenge:
                from engine.video_gen import apply_progress_bar
                overlays += apply_progress_bar(sub, sub.duration)
                
            final = CompositeVideoClip([sub] + overlays)
            out = os.path.join(output_dir, f"video_clip_{i+1}.mp4")
            final.write_videofile(out, fps=24, bitrate=final_bitrate, preset=target_preset, threads=8, codec=target_codec)
            extracted_files.append(out)
            sub.close()
            
    return extracted_files
