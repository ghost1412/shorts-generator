import json
import os
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, ColorClip, ImageClip, CompositeVideoClip, CompositeAudioClip, vfx, afx
from PIL import Image, ImageDraw, ImageFont

def create_text_image(text, size=(1080, 1920), font_size=75, color="white", stroke_color="black", stroke_width=6):
    """
    Creates a transparent PNG with text using Pillow.
    Optimized for readability and screen safety.
    """
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try to load a premium-looking font
    try:
        font_path = "C:/Windows/Fonts/impact.ttf" # Impact is great for social media/shorts
        if not os.path.exists(font_path):
            font_path = "C:/Windows/Fonts/arialbd.ttf"
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # Dynamic line wrapping with safety margins
    max_width = size[0] - 160 # Leave 80px margin on each side
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
                # Single word too long? Force it anyway but it might cut
                lines.append(" ".join(current_line))
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))

    # Calculate total height for vertical centering/positioning
    line_spacing = 15
    total_h = sum([draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]) + (len(lines)-1) * line_spacing
    
    # Position text in the lower middle area (ideal for Shorts)
    start_y = (size[1] - total_h) / 1.6 

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (size[0] - w) / 2
        
        # Thicker stroke for premium look
        if stroke_width > 0:
            for ox in range(0 - stroke_width, stroke_width + 1):
                for oy in range(0 - stroke_width, stroke_width + 1):
                    draw.text((x + ox, start_y + oy), line, font=font, fill=stroke_color)

        # Main text
        draw.text((x, start_y), line, font=font, fill=color)
        start_y += int(h + line_spacing)

    return np.array(img)

def create_shorts_video(audio_path, subs_path, video_path, output_path="final_short.mp4", music_path=None):
    """
    Composes the final video with background, audio, and synced captions.
    """
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration + 0.5
    
    bg_clip = VideoFileClip(video_path)
    
    # Check if video has a visual stream
    if bg_clip.size[0] == 0 or bg_clip.size[1] == 0:
        print(f"⚠️ WARNING: Background video {video_path} seems to have no visual stream. Using fallback color.")
        bg_clip = ColorClip(size=(1080, 1920), color=(20, 20, 30)).with_duration(duration)
    else:
        # Robust looping: Repeat the clip enough times to cover the duration
        n_loops = int(np.ceil(duration / bg_clip.duration)) if bg_clip.duration > 0 else 1
        bg_clip = bg_clip.with_effects([vfx.Loop(n=n_loops)]).with_duration(duration)
        
        # High-quality resize and crop for Shorts
        bg_clip = bg_clip.resized(height=1920)
        w, h = bg_clip.size
        bg_clip = bg_clip.cropped(x_center=w/2, width=1080)
    
    # Add subtle darkening overlay for text readability
    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.3).with_duration(duration)
    
    # Process Subtitles
    with open(subs_path, "r") as f:
        subtitles = json.load(f)
    
    caption_clips = []
    
    if subtitles:
        i = 0
        while i < len(subtitles):
            chunk = []
            chunk_start = subtitles[i]["start"]
            current_duration = 0
            while i < len(subtitles) and len(chunk) < 4 and current_duration < 2.5:
                chunk.append(subtitles[i])
                current_duration = (subtitles[i]["start"] + subtitles[i]["duration"]) - chunk_start
                i += 1
            
            text = " ".join([w["word"] for w in chunk]).upper()
            start = chunk[0]["start"]
            end = chunk[-1]["start"] + chunk[-1]["duration"]
            
            text_frame = create_text_image(text)
            txt_clip = ImageClip(text_frame).with_start(start).with_duration(max(0.2, end - start)).with_position("center")
            caption_clips.append(txt_clip)
    
    # Final Composition
    final_video = CompositeVideoClip([bg_clip, dark_overlay] + caption_clips)
    
    # Handle Background Music
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.1) # Louder than 0.1 but not overwhelming
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    
    print(f"🎬 Exporting high-quality short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="5000k")
    
    return output_path

if __name__ == "__main__":
    if os.path.exists("assets/voice.mp3") and os.path.exists("assets/subs.json") and os.path.exists("assets/bg.mp4"):
        create_shorts_video("assets/voice.mp3", "assets/subs.json", "assets/bg.mp4")
