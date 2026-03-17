import json
import os
import numpy as np
import random
from moviepy import VideoFileClip, AudioFileClip, ColorClip, ImageClip, CompositeVideoClip, CompositeAudioClip, vfx, afx
from PIL import Image, ImageDraw, ImageFont

def create_text_image(text, size=(1080, 1920), font_size=50, color="white", stroke_color="black", stroke_width=6, y_pos=None):
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
        sw = int(stroke_width)
        if sw > 0:
            for ox in range(-sw, sw + 1):
                for oy in range(-sw, sw + 1):
                    if ox != 0 or oy != 0:
                        draw.text((x + ox, start_y + oy), line, font=font, fill=stroke_color)

        draw.text((x, start_y), line, font=font, fill=color)
        start_y += int(h + line_spacing)

    return np.array(img)

def create_shorts_video(audio_path, subs_path, video_paths, output_path="final_short.mp4", music_path=None, is_story=False):
    """
    Composes the final video with dynamic multi-backgrounds and word-by-word animations.
    """
    audio_clip = AudioFileClip(audio_path)
    # Extension for "Suspense Reveal" - add 2.5 seconds of silence/music at the end
    duration = audio_clip.duration + 2.5 
    
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
            print(f"[Warning] Error processing background {path}: {e}")
    
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
    
    if not is_story:
        # 1. TOP HEADER: SPOT THE LIE!
        header_img = create_text_image("SPOT THE LIE! 🔍", font_size=110, color="yellow", y_pos=150)
        top_header = ImageClip(header_img).with_start(0).with_duration(duration)
        persistent_clips.append(top_header)
        
        # 2. BOTTOM FOOTER: 👇 COMMENT YOUR GUESS
        footer_img = create_text_image("👇 COMMENT YOUR GUESS", font_size=85, color="white", y_pos=1700)
        bottom_footer = ImageClip(footer_img).with_start(0).with_duration(duration)
        persistent_clips.append(bottom_footer)
    else:
        # STORY MODE HEADER
        header_img = create_text_image("UNBELIEVABLE BUT TRUE 🤯", font_size=110, color="orange", y_pos=150)
        top_header = ImageClip(header_img).with_start(0).with_duration(duration)
        persistent_clips.append(top_header)

    if subtitles:
        # 1. Fact Indicators (e.g., FACT 1/3) - Only for FACT Mode
        fact_header_times = []
        if not is_story:
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
            h_img = create_text_image(txt, font_size=100, color="cyan", y_pos=280)
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
                
                dynamic_font_size = 130
                if len(text) > 50: dynamic_font_size = 110
                if len(text) > 80: dynamic_font_size = 90
                
                c_img = create_text_image(text, font_size=dynamic_font_size, color="white")
                c_clip = ImageClip(c_img).with_start(sentence_start).with_duration(end - sentence_start).with_position((0, 0))
                
                # Add POP-IN effect (Scale from 0.8 to 1.0 quickly)
                c_clip = c_clip.with_effects([
                    vfx.Resize(lambda t: min(1.0, 0.8 + 2.0 * t))
                ])
                
                word_clips.append(c_clip)
                current_sentence = []
                sentence_start = None

        # 3. FINAL REVEAL OVERLAY (Only for FACTS)
        if not is_story:
            reveal_img = create_text_image("REVEALING IN COMMENTS... 🤫", font_size=110, color="orange", y_pos=900)
            reveal_clip = ImageClip(reveal_img).with_start(audio_clip.duration).with_duration(2.5).with_position((0, 0))
            word_clips.append(reveal_clip.with_effects([vfx.CrossFadeIn(0.5)]))
        else:
            # Story Mode Outro
            reveal_img = create_text_image("LIKE & SUBSCRIBE! 🔔", font_size=120, color="yellow", y_pos=900)
            reveal_clip = ImageClip(reveal_img).with_start(audio_clip.duration).with_duration(2.5).with_position((0, 0))
            word_clips.append(reveal_clip.with_effects([vfx.CrossFadeIn(0.5)]))

    # Final Composition
    final_video = CompositeVideoClip([bg_clip, dark_overlay, bg_bar, progress_bar] + persistent_clips + header_clips + word_clips)
    
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.18)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    
    print(f"[Log] Exporting polished eye-candy short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="6000k")
    
    return output_path

def create_game_video(audio_path, subs_path, target_path, object_paths, output_path="game_short.mp4", target_name="Cat", music_path=None):
    """
    Composes an EXTREMELY CHALLENGING "Find the Target" game video.
    Uses circular masking and a solid background (greenscreen).
    """
    audio_clip = AudioFileClip(audio_path)
    # Give it a 3-second reveal window at the end
    duration = audio_clip.duration + 3.0
    
    # 1. Background - Solid Green (Greenscreen) as requested
    bg_clip = ColorClip(size=(1080, 1920), color=(0, 177, 64)).with_duration(duration)
    
    # 2. Progress Bar
    bar_height = 20
    bg_bar = ColorClip(size=(1080, bar_height), color=(30, 30, 30)).with_duration(duration).with_position(("center", 1880))
    progress_bar = ColorClip(size=(1080, bar_height), color=(255, 230, 0)).with_duration(duration).with_position(("center", 1880))
    progress_bar = progress_bar.with_effects([vfx.Resize(lambda t: (max(1, int(1080 * t / duration)), bar_height))])
    
    # 3. Persistent UI - HUMOROUS HOOKS
    header_titles = [
        f"SPOT THE {target_name.upper()}!",
        f"WHERE IS {target_name.upper()}??",
        f"FIND {target_name.upper()} = GIGACHAD 🗿",
        f"BRO HIDING FROM THE IRS 🤫",
        f"99% FAIL TO FIND {target_name.upper()}"
    ]
    header_img = create_text_image(random.choice(header_titles), font_size=95, color="white", stroke_color="#1a1a1a", y_pos=150)
    top_header = ImageClip(header_img).with_start(0).with_duration(duration)
    
    footer_texts = [
        "ONLY 1% CAN FIND IT! 🕵️‍♂️",
        "STOP THE VIDEO WHEN FOUND! 🛑",
        "FAILED? YOU OWE ME A SUB! 🤝",
        "I BET YOU CAN'T SPOT HIM 💀"
    ]
    footer_img = create_text_image(random.choice(footer_texts), font_size=70, color="yellow", stroke_color="#1a1a1a", y_pos=1700)
    bottom_footer = ImageClip(footer_img).with_start(0).with_duration(duration)
    
    # 4. Scatter Objects (EXERTME Density)
    game_clips = []
    
    # Random spawning in the middle 70% of the screen
    num_total_slots = 150 
    positions = []
    for _ in range(num_total_slots):
        x = random.randint(50, 930)
        y = random.randint(300, 1600)
        positions.append((x, y))
    
    # Sort positions by Y to get some pseudo-depth if we wanted, but random is better for challenge
    random.shuffle(positions)
    
    # Target: The Object (Place it somewhere randomly among the pack)
    target_idx = random.randint(50, 120)
    target_pos = positions[target_idx]
    
    def prepare_sticker(path, width=100):
        clip = ImageClip(path).resized(width=width)
        return clip.with_duration(duration)

    # Place Distractors
    num_distractors = len(object_paths)
    for i in range(num_total_slots):
        pos = positions[i]
        
        if i == target_idx:
            # Place Target
            obj_clip = prepare_sticker(target_path, width=85) # Tiny target
        else:
            # Place Distractor
            obj_path = object_paths[i % num_distractors]
            obj_clip = prepare_sticker(obj_path, width=95)
            
            # More intense randomization
            if random.random() > 0.5:
                obj_clip = obj_clip.with_effects([vfx.MirrorX()])
            
            rotation = random.randint(-45, 45)
            if rotation != 0:
                obj_clip = obj_clip.with_effects([vfx.Rotate(rotation)])

        if i == target_idx:
            target_clip_for_reveal = obj_clip # Store for coordinate calculation
        
        obj_clip = (obj_clip.with_start(0)
                    .with_position(pos))
        game_clips.append(obj_clip)
    # 5. Result Pop-up (at the end)
    reveal_start = audio_clip.duration
    
    found_text_img = create_text_image("FOUND IT! 🎯", font_size=120, color="lime", stroke_color="black", y_pos=900)
    found_clip = (ImageClip(found_text_img)
                  .with_start(reveal_start)
                  .with_duration(3.0)
                  .with_effects([vfx.CrossFadeIn(0.3)]))
    
    # Final Composition
    final_video = CompositeVideoClip([bg_clip] + game_clips + [bg_bar, progress_bar, top_header, bottom_footer, found_clip])
    
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.18)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    
    print(f"[Log] Exporting EXTREME Challenge: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="8000k")
    
    return output_path

if __name__ == "__main__":
    # Test call
    # create_shorts_video("assets/voice.mp3", "assets/subs.json", ["assets/bg.mp4"])
    pass
