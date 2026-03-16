import json
import os
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, ColorClip, ImageClip, CompositeVideoClip, CompositeAudioClip, vfx, afx
from PIL import Image, ImageDraw, ImageFont

def create_text_image(text, size=(1080, 1920), font_size=50, color="white", stroke_color="black", stroke_width=4, y_pos=None):
    """
    Creates a transparent PNG with text using Pillow.
    Optimized for readability with a premium, clean feel.
    """
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try to load Arial Black for that "Shorts" look
    try:
        font_path = "C:/Windows/Fonts/ariblk.ttf"
        if not os.path.exists(font_path):
            font_path = "C:/Windows/Fonts/impact.ttf"
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    max_width = size[0] - 200 
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width:
            if len(current_line) > 1:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(" ".join(current_line))
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))

    line_spacing = 10
    total_h = sum([draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]) + (len(lines)-1) * line_spacing
    
    if y_pos is None:
        start_y = (size[1] - total_h) / 2 # Vertically centered by default
    else:
        start_y = y_pos

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (size[0] - w) / 2
        
        # Cleaner stroke
        if stroke_width > 0:
            for ox in range(-stroke_width, stroke_width + 1):
                for oy in range(-stroke_width, stroke_width + 1):
                    if ox != 0 or oy != 0:
                        draw.text((x + ox, start_y + oy), line, font=font, fill=stroke_color)

        draw.text((x, start_y), line, font=font, fill=color)
        start_y += int(h + line_spacing)

    return np.array(img)

def create_shorts_video(audio_path, subs_path, video_paths, output_path="final_short.mp4", music_path=None):
    """
    Composes the final video with dynamic multi-backgrounds and word-by-word animations.
    """
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration + 0.3
    
    # 1. Multi-Background Stitching
    if isinstance(video_paths, str): video_paths = [video_paths]
    
    bg_segments = []
    segment_duration = duration / len(video_paths)
    
    for i, path in enumerate(video_paths):
        try:
            clip = VideoFileClip(path)
            # Ensure clip is long enough for its segment
            n_loops = int(np.ceil(segment_duration / clip.duration)) if clip.duration > 0 else 1
            clip = clip.with_effects([vfx.Loop(n=n_loops)]).with_duration(segment_duration)
            
            # High-quality resize and crop
            clip = clip.resized(height=1920)
            w, h = clip.size
            clip = clip.cropped(x_center=w/2, width=1080)
            
            clip = clip.with_start(i * segment_duration)
            bg_segments.append(clip)
        except Exception as e:
            print(f"⚠️ Error processing background {path}: {e}")
    
    if not bg_segments:
        bg_clip = ColorClip(size=(1080, 1920), color=(20, 20, 30)).with_duration(duration)
    else:
        bg_clip = CompositeVideoClip(bg_segments).with_duration(duration)
    
    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.25).with_duration(duration)
    
    # 2. Process Subtitles: Word-by-Word Animation
    with open(subs_path, "r") as f:
        subtitles = json.load(f)
    
    persistent_clips = []
    header_clips = []
    word_clips = []
    
    # Progress Bar (Interactive Element)
    bar_height = 20
    bg_bar = ColorClip(size=(1080, bar_height), color=(50, 50, 50)).with_duration(duration).with_position(("center", 1880))
    progress_bar = ColorClip(size=(1080, bar_height), color=(255, 255, 0)).with_duration(duration).with_position(("center", 1880))
    progress_bar = progress_bar.with_effects([vfx.Resize(lambda t: (max(1, int(1080 * t / duration)), bar_height))])
    
    # viral_color = (255, 230, 0) # Bright Yellow
    
    # 1. TOP HEADER: SPOT THE LIE!
    header_img = create_text_image("SPOT THE LIE! 🔍", font_size=90, color="yellow", y_pos=150)
    top_header = ImageClip(header_img).with_start(0).with_duration(duration)
    persistent_clips.append(top_header)
    
    # 2. BOTTOM FOOTER: 👇 COMMENT YOUR GUESS
    footer_img = create_text_image("👇 COMMENT YOUR GUESS", font_size=70, color="white", y_pos=1700)
    bottom_footer = ImageClip(footer_img).with_start(0).with_duration(duration)
    persistent_clips.append(bottom_footer)

    if subtitles:
        # 1. Fact Indicators (e.g., FACT 1/3)
        fact_header_times = []
        for j, entry in enumerate(subtitles):
            word = entry["word"].upper()
            if "FACT" in word and j + 1 < len(subtitles):
                next_word = subtitles[j+1]["word"].strip(":,.")
                if "1" == next_word: fact_header_times.append((entry["start"], "FACT 1/3"))
                elif "2" == next_word: fact_header_times.append((entry["start"], "FACT 2/3"))
                elif "3" == next_word: fact_header_times.append((entry["start"], "FACT 3/3"))

        for start, txt in fact_header_times:
            next_header_start = fact_header_times[fact_header_times.index((start, txt)) + 1][0] if fact_header_times.index((start, txt)) + 1 < len(fact_header_times) else duration
            h_duration = next_header_start - start
            h_img = create_text_image(txt, font_size=80, color="cyan", y_pos=280)
            h_clip = ImageClip(h_img).with_start(start).with_duration(h_duration).with_position((0, 0))
            header_clips.append(h_clip.with_effects([vfx.CrossFadeIn(0.1)]))

        # 2. SENTENCE-BASED Captions with Pop-In Effect
        current_sentence = []
        sentence_start = None
        
        for i, entry in enumerate(subtitles):
            word = entry["word"]
            if sentence_start is None:
                sentence_start = entry["start"]
            
            current_sentence.append(word.upper())
            is_end = any(p in word for p in [".", "!", "?"])
            
            if is_end or i == len(subtitles) - 1:
                text = " ".join(current_sentence)
                end = entry["start"] + entry["duration"]
                
                dynamic_font_size = 90
                if len(text) > 50: dynamic_font_size = 80
                if len(text) > 80: dynamic_font_size = 70
                
                c_img = create_text_image(text, font_size=dynamic_font_size, color="white")
                c_clip = ImageClip(c_img).with_start(sentence_start).with_duration(end - sentence_start).with_position((0, 0))
                
                # Add POP-IN effect (Scale from 0.8 to 1.0 quickly)
                c_clip = c_clip.with_effects([
                    vfx.Resize(lambda t: min(1.0, 0.8 + 2.0 * t))
                ])
                
                word_clips.append(c_clip)
                current_sentence = []
                sentence_start = None

    # Final Composition
    final_video = CompositeVideoClip([bg_clip, dark_overlay, bg_bar, progress_bar] + persistent_clips + header_clips + word_clips)
    
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.18)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    
    print(f"🎬 Exporting polished eye-candy short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="6000k")
    
    return output_path

if __name__ == "__main__":
    # Test call
    create_shorts_video("assets/voice.mp3", "assets/subs.json", ["assets/bg.mp4"])
