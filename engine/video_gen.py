import json
import os
import numpy as np
import random
from moviepy import VideoFileClip, AudioFileClip, ColorClip, ImageClip, CompositeVideoClip, CompositeAudioClip, vfx, afx
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- VIRAL SAFE ZONES (Prevents UI overlap) ---
SAFE_TOP = 150
SAFE_MID = 800
SAFE_BOTTOM = 1600

def add_pattern_interrupt(duration):
    """Adds a mid-video 'pattern interrupt' flash to regain attention."""
    interrupt_time = duration * 0.5
    flash = ColorClip(size=(1080, 1920), color=(255, 255, 255))\
        .with_start(interrupt_time)\
        .with_duration(0.1)\
        .with_opacity(0.4)
    return flash

def bounce_scale(t):
    """TikTok-style pop/bounce animation for captions."""
    if t < 0.1:
        return 0.5 + 8 * t
    elif t < 0.2:
        return 1.1 - 0.5 * (t - 0.1)
    return 1.0

def apply_blur(image, radius=2):
    """Applies Gaussian Blur to a numpy image array using Pillow."""
    pil_img = Image.fromarray(image)
    blurred_pil = pil_img.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(blurred_pil)

def color_shift_green_kill(get_frame, t, duration):
    """Gradually kills the green channel to transition Yellow (255,255,0) -> Red (255,0,0)."""
    frame = get_frame(t)
    factor_g = max(0, 1 - (t / duration))
    new_frame = frame.copy()
    new_frame[:, :, 1] = (new_frame[:, :, 1] * factor_g).astype("uint8")
    return new_frame

def create_text_image(text, size=(1080, 1920), font_size=50, color="white", stroke_color="black", stroke_width=6, y_pos=None, add_box=True):
    """
    Creates a transparent PNG with text using Pillow.
    Optimized for readability with viral shorts-style background boxes.
    Strips emojis to avoid "tofu" boxes on systems without full emoji font support.
    """
    # 1. Clean emojis from visual text
    result = []
    for char in text:
        c = str(char)
        if ord(c) < 127 or c.isalnum() or c.isspace() or c in ".,!?;:()-'\"":
            result.append(c)
    clean_text = "".join(result)
    if not clean_text.strip(): 
        return np.zeros((size[1], size[0], 4), dtype=np.uint8)

    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Robust font loading
    try:
        font_paths = [
            "C:/Windows/Fonts/ariblk.ttf", # Arial Black
            "C:/Windows/Fonts/impact.ttf", # Impact
            "C:/Windows/Fonts/arialbd.ttf", # Arial Bold
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        font_path = None
        for path in font_paths:
            if os.path.exists(path):
                font_path = path
                break
        
        if font_path:
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.load_default()
    except Exception as e:
        print(f"[Warning] Font loading error: {e}")
        font = ImageFont.load_default()

    max_width = size[0] - 160 
    words = clean_text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font, anchor="lt")
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

    # Significant spacing to prevent any overlap
    # Tight spacing for shorts style
    line_spacing = 30
    line_infos = []
    total_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, anchor="lt")
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_infos.append((line, w, h))
        total_h += h + line_spacing
    total_h -= line_spacing

    if y_pos is None:
        start_y = (size[1] - total_h) / 2
    else:
        start_y = y_pos

    for line, w, h in line_infos:
        x = (size[0] - w) / 2
        if add_box:
            px, py = 40, 15
            draw.rectangle([x - px, start_y - py, x + w + px, start_y + h + py], fill=(0, 0, 0, 185))

        # Draw text using anchor="lt" for deterministic positioning
        draw.text((x, start_y), line, font=font, fill=color, anchor="lt")
        start_y += h + line_spacing

    return np.array(img)

def cover_resize(clip, target_size=(1080, 1920)):
    """
    Resizes and crops a clip to cover the target size while maintaining aspect ratio.
    Equivalent to CSS 'background-size: cover'.
    """
    w, h = clip.size
    target_w, target_h = target_size
    
    # Calculate scale factor to cover the target area
    scale = max(target_w / w, target_h / h)
    
    # Resize and then center crop
    new_w, new_h = int(w * scale), int(h * scale)
    # Use a small buffer if needed, but int should be fine
    clip = clip.resized(width=new_w, height=new_h)
    
    return clip.cropped(x_center=new_w/2, y_center=new_h/2, width=target_w, height=target_h)

def apply_ken_burns(clip, duration):
    """
    Applies a subtle, static camera zoom (Ken Burns effect) to a clip.
    Removed per-frame lambda resize for performance.
    """
    # Just a small static zoom-in (1.1x) is much faster and still looks premium
    return clip.with_effects([vfx.Resize(1.1)])

def create_shorts_video(audio_path, subs_path, video_paths, output_path="final_short.mp4", music_path=None, mode="FACTS"):
    """
    Composes the final video with dynamic multi-backgrounds and word-by-word animations.
    """
    audio_clip = AudioFileClip(audio_path)
    # Extension for "Suspense Reveal" - Tighten to 1.5s for retention
    duration = audio_clip.duration + 1.5 
    
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
            
            # Robust resize to cover 1080x1920
            clip = cover_resize(clip, (1080, 1920))
            
            clip = clip.with_start(i * segment_duration)
            bg_segments.append(clip)
        except Exception as e:
            print(f"[Warning] Error processing background {path}: {e}")
    
    # Force size=(1080, 1920) on all composites to avoid aspect ratio drifting
    if not bg_segments:
        bg_clip = ColorClip(size=(1080, 1920), color=(20, 20, 30)).with_duration(duration)
    else:
        # Apply Ken Burns to the combined background for extra energy
        bg_clip = CompositeVideoClip(bg_segments, size=(1080, 1920)).with_duration(duration)
        bg_clip = apply_ken_burns(bg_clip, duration)
        # 3. STATIC ZOOM: One-time resize is much faster than per-frame lambda
        bg_clip = bg_clip.with_effects([vfx.Resize(1.05)])
    
    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.25).with_duration(duration)
    
    # 2. Process Subtitles: Word-by-Word Animation
    with open(subs_path, "r", encoding="utf-8") as f:
        subtitles = json.load(f)
    
    persistent_clips = []
    header_clips = []
    word_clips = []
    
    # Progress Bar (Urgency Curve)
    bar_height = 20
    # Progress Bar (Urgency Curve + Color Shift)
    bg_bar = ColorClip(size=(1080, bar_height), color=(50, 50, 50)).with_duration(duration).with_position(("center", 1880))
    progress_bar = ColorClip(size=(1080, bar_height), color=(255, 255, 0)).with_duration(duration).with_position(("center", 1880))
    # Faster near end + Transition Yellow -> Red
    progress_bar = progress_bar.with_effects([
        vfx.Resize(lambda t: (max(1, int(1080 * (t / duration) ** 0.7)), bar_height))
    ])
    progress_bar = progress_bar.transform(lambda gf, t: color_shift_green_kill(gf, t, duration))
    
    if mode.startswith("NEWS"):
        # 1. TOP HEADER: BREAKING NEWS!
        header_img = create_text_image("BREAKING NEWS!", font_size=110, color="red", y_pos=SAFE_TOP)
        top_header = ImageClip(header_img).with_start(0).with_duration(duration)
        
        # LIVE Badge
        live_img = create_text_image("● LIVE", font_size=60, color="red", y_pos=SAFE_TOP + 120)
        live_clip = ImageClip(live_img).with_start(0).with_duration(duration)
        persistent_clips.extend([top_header, live_clip])
        
        # 2. BOTTOM FOOTER: SCROLLING TICKER
        footer_img = create_text_image(" " * 50 + "BREAKING: " + mode.replace("_", " ") + " - FOLLOW FOR MORE UPDATES! " + " " * 50, font_size=65, color="white", y_pos=SAFE_BOTTOM + 150, add_box=True)
        ticker_clip = ImageClip(footer_img).with_start(0).with_duration(duration)
        
        ticker_width = ticker_clip.size[0]
        ticker_clip = ticker_clip.with_position(lambda t: (1080 - (t * 400) % (ticker_width + 1080), SAFE_BOTTOM + 150))
        persistent_clips.append(ticker_clip)
        
        # 3. URGENCY SHAKE (Synced to intense broadcast vibe) - Positional is much faster than Resize
        top_header = top_header.with_position(lambda t: (int(0.01 * np.sin(t * 15) * 1080), SAFE_TOP))
    elif mode == "STORY":
        header_img = create_text_image("UNBELIEVABLE BUT TRUE", font_size=110, color="orange", y_pos=SAFE_TOP)
        top_header = ImageClip(header_img).with_start(0).with_duration(duration)
        persistent_clips.append(top_header)
    else: # FACTS mode
        header_img = create_text_image("SPOT THE LIE!", font_size=110, color="yellow", y_pos=SAFE_TOP)
        top_header = ImageClip(header_img).with_start(0).with_duration(duration)
        
        footer_img = create_text_image("COMMENT YOUR GUESS", font_size=60, color="white", y_pos=SAFE_BOTTOM + 100)
        bottom_footer = ImageClip(footer_img).with_start(0).with_duration(duration)
        persistent_clips.extend([top_header, bottom_footer])

    if subtitles:
        # 1. Fact Indicators
        fact_header_times = []
        if mode == "FACTS":
            for j, entry in enumerate(subtitles):
                word = entry["word"].upper()
                if "FACT" in word and j + 1 < len(subtitles):
                    next_word = subtitles[j+1]["word"].strip(":,.")
                    if "1" == next_word: fact_header_times.append((entry["start"], "FACT 1/3"))
                    elif "2" == next_word: fact_header_times.append((entry["start"], "FACT 2/3"))
                    elif "3" == next_word: fact_header_times.append((entry["start"], "FACT 3/3"))

        for start, txt in fact_header_times:
            idx = fact_header_times.index((start, txt))
            next_header_start = fact_header_times[idx + 1][0] if idx + 1 < len(fact_header_times) else duration
            h_duration = next_header_start - start
            h_img = create_text_image(txt, font_size=110, color="cyan", y_pos=SAFE_TOP + 200, add_box=True)
            h_clip = ImageClip(h_img).with_start(start).with_duration(h_duration).with_position((0, 0))
            header_clips.append(h_clip.with_effects([vfx.CrossFadeIn(0.1)]))

        # 2. Captions with Bounce Effect
        for i, entry in enumerate(subtitles):
            text = entry["word"].upper()
            start = entry["start"]
            end = start + entry["duration"]
            
            c_img = create_text_image(text, font_size=120, color="white", y_pos=SAFE_MID)
            # Minimum display duration for readability
            c_duration = max(0.6, entry["duration"])
            c_clip = ImageClip(c_img).with_start(start).with_duration(c_duration).with_position((0, 0))
            
            # Bounce effect using position instead of expensive Resize
            def make_bounce_pos(st):
                return lambda t: ("center", SAFE_MID + int(15 * np.sin((t - st) * 12)))
            
            c_clip = c_clip.with_position(make_bounce_pos(start))
            word_clips.append(c_clip)

        # 3. FINAL REVEAL OVERLAY
        reveal_y = SAFE_MID + 100
        if mode == "FACTS":
            reveal_img = create_text_image("Comment your guess... answer below 👇", font_size=110, color="orange", y_pos=reveal_y)
            reveal_clip = ImageClip(reveal_img).with_start(audio_clip.duration).with_duration(2.5).with_position((0, 0))
            word_clips.append(reveal_clip.with_effects([vfx.CrossFadeIn(0.5)]))
        elif mode.startswith("NEWS"):
            reveal_img = create_text_image("STAY TUNED FOR MORE! 🚨", font_size=110, color="red", y_pos=reveal_y)
            reveal_clip = ImageClip(reveal_img).with_start(audio_clip.duration).with_duration(2.5).with_position((0, 0))
            word_clips.append(reveal_clip.with_effects([vfx.CrossFadeIn(0.5)]))
        else: # STORY mode
            reveal_img = create_text_image("LIKE & SUBSCRIBE! 🔔", font_size=120, color="yellow", y_pos=reveal_y)
            reveal_clip = ImageClip(reveal_img).with_start(audio_clip.duration).with_duration(2.5).with_position((0, 0))
            word_clips.append(reveal_clip.with_effects([vfx.CrossFadeIn(0.5)]))

    # 3. Performance Optimization: Pre-flatten static layers
    static_layer = CompositeVideoClip(
        [bg_clip, dark_overlay, add_pattern_interrupt(duration), bg_bar],
        size=(1080, 1920)
    ).with_duration(duration)

    final_video = CompositeVideoClip(
        [static_layer, progress_bar] + 
        persistent_clips + header_clips + word_clips, 
        size=(1080, 1920)
    )
    
    # Loopability Zoom Effect
    final_video = final_video.with_effects([
        vfx.Resize(lambda t: 1 + 0.03 * np.sin(t / duration * np.pi))
    ])
    
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.18)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    final_video = final_video.with_fps(24).with_duration(duration)
    
    print(f"[Log] Exporting polished eye-candy short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="6000k", threads=4)
    
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
    
    # 2. Progress Bar & Countdown Timer
    bar_height = 25
    bg_bar = ColorClip(size=(1080, bar_height), color=(30, 30, 30)).with_duration(duration).with_position(("center", 1880))
    progress_bar = ColorClip(size=(1080, bar_height), color=(255, 230, 0)).with_duration(duration).with_position(("center", 1880))
    progress_bar = progress_bar.with_effects([vfx.Resize(lambda t: (max(1, int(1080 * t / duration)), bar_height))])
    
    # Visual Countdown Timer (Center of screen, shrinking circle or bar)
    timer_w = 400
    timer_bg = ColorClip(size=(timer_w, 40), color=(0, 0, 0, 100)).with_duration(audio_clip.duration).with_position(("center", 1600))
    timer_fg = ColorClip(size=(timer_w, 40), color=(255, 0, 0)).with_duration(audio_clip.duration).with_position(("center", 1600))
    timer_fg = timer_fg.with_effects([
        vfx.Resize(lambda t: (max(1, int(timer_w * (1 - t / audio_clip.duration))), 40))
    ])
    
    # "HURRY!" text at 3s mark
    hurry_img = create_text_image("ONLY 3 SECONDS LEFT! ⏳", font_size=80, color="red", y_pos=1400, add_box=True)
    hurry_clip = ImageClip(hurry_img).with_start(audio_clip.duration - 3).with_duration(3).with_effects([vfx.CrossFadeIn(0.2)])
    
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
    
    # 4. Scatter Objects (Smart Grid with Jitter)
    distractor_clips = []
    target_sticker = None
    
    # 8 columns x 12 rows = 96 slots
    cols, rows = 8, 12
    slot_w, slot_h = 950 // cols, 1300 // rows
    
    positions = []
    for r in range(rows):
        for c in range(cols):
            x = 50 + c * slot_w + random.randint(0, 20)
            y = 300 + r * slot_h + random.randint(0, 20)
            positions.append((x, y))
    
    random.shuffle(positions)
    num_to_place = min(len(positions), 90)
    target_idx = random.randint(5, int(num_to_place * 0.7))
    target_pos = positions[target_idx]
    
    def prepare_sticker(path, width=110):
        # Create a basic image clip
        img_clip = ImageClip(path).resized(width=width).with_duration(duration)
        return img_clip

    num_distractors = len(object_paths)
    for i in range(num_to_place):
        pos = positions[i]
        if i == target_idx:
            # CAMOUFLAGE: Slight transparency + perfectly centered + target blur
            target_sticker = prepare_sticker(target_path, width=105)\
                .with_position(pos)\
                .with_start(0)\
                .with_opacity(0.92)\
                .image_transform(lambda img: apply_blur(img, radius=2)) # Harder to find
        else:
            obj_path = object_paths[i % num_distractors]
            obj_clip = prepare_sticker(obj_path, width=115).with_position(pos).with_start(0)
            
            # Pattern interrupts/noise: Slight mirror and rotate
            if random.random() > 0.5: obj_clip = obj_clip.with_effects([vfx.MirrorX()])
            rotation = random.randint(-30, 30)
            if rotation != 0: obj_clip = obj_clip.with_effects([vfx.Rotate(rotation)])
            
            # Distractors CLEAR to mask the target
            distractor_clips.append(obj_clip)

    # 5. Result Pop-up & Highlight
    reveal_start = audio_clip.duration
    
    # Simple Reveal Highlight (Red box/ring)
    reveal_ring_img = create_text_image("○", font_size=180, color="red", y_pos=50)
    reveal_highlight = (ImageClip(reveal_ring_img)
                       .with_start(reveal_start)
                       .with_duration(3.0)
                       .with_position((target_pos[0]-35, target_pos[1]-35))
                       .with_effects([vfx.CrossFadeIn(0.2)]))
    
    found_text_img = create_text_image("FOUND IT! 🎯", font_size=120, color="lime", stroke_color="black", y_pos=900)
    found_clip = (ImageClip(found_text_img)
                  .with_start(reveal_start)
                  .with_duration(3.0)
                  .with_effects([vfx.CrossFadeIn(0.3)]))
    
    # Final Composition - Force (1080, 1920) size
    # Final Composition - Target is added AFTER distractors to be on top
    final_video = CompositeVideoClip(
        [bg_clip] + distractor_clips + [target_sticker] + 
        [bg_bar, progress_bar, top_header, bottom_footer, timer_bg, timer_fg, hurry_clip, reveal_highlight, found_clip], 
        size=(1080, 1920)
    )
    
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.18)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    final_video = final_video.with_duration(duration)
    
    print(f"[Log] Exporting EXTREME Challenge: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="8000k", threads=4)
    
    return output_path

def create_wyr_video(audio_path, wyr_data, video_paths, output_path="wyr_short.mp4", music_path=None):
    """
    Composes a split-screen Would You Rather video.
    """
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration + 3.0 # Extra time for reveal
    
    # 1. Backgrounds (Split screen)
    if isinstance(video_paths, str): video_paths = [video_paths]
    if len(video_paths) < 2:
        # duplicate if only 1 to prevent errors
        video_paths.append(video_paths[0])
        
    try:
        # Top half
        clip1 = VideoFileClip(video_paths[0])
        n_loops1 = int(np.ceil(duration / clip1.duration)) if clip1.duration > 0 else 1
        clip1 = clip1.with_effects([vfx.Loop(n=n_loops1)]).with_duration(duration)
        clip1 = cover_resize(clip1, (1080, 960)).with_position((0, 0))
        
        # Bottom half
        clip2 = VideoFileClip(video_paths[1])
        n_loops2 = int(np.ceil(duration / clip2.duration)) if clip2.duration > 0 else 1
        clip2 = clip2.with_effects([vfx.Loop(n=n_loops2)]).with_duration(duration)
        clip2 = cover_resize(clip2, (1080, 960)).with_position((0, 960))
    except Exception as e:
        print(f"[Warning] Error processing WYR backgrounds: {e}")
        clip1 = ColorClip(size=(1080, 960), color=(50, 0, 0)).with_duration(duration).with_position((0, 0))
        clip2 = ColorClip(size=(1080, 960), color=(0, 0, 50)).with_duration(duration).with_position((0, 960))

    # Center divider
    divider = ColorClip(size=(1080, 15), color=(255, 255, 255)).with_duration(duration).with_position(("center", 952))

    # Dark overlays for text readability
    dark1 = ColorClip(size=(1080, 960), color=(0,0,0)).with_opacity(0.4).with_duration(duration).with_position((0, 0))
    dark2 = ColorClip(size=(1080, 960), color=(0,0,0)).with_opacity(0.4).with_duration(duration).with_position((0, 960))

    # Header
    header_img = create_text_image("WOULD YOU RATHER?", font_size=90, color="yellow", y_pos=SAFE_TOP)
    top_header = ImageClip(header_img).with_start(0).with_duration(duration)

    # Options Text with motion
    opt_a_img = create_text_image(wyr_data.get("option_a", "A").upper(), font_size=80, color="white", y_pos=450)
    opt_a_clip = ImageClip(opt_a_img).with_start(0).with_duration(duration).with_effects([
        vfx.CrossFadeIn(0.5),
        vfx.Resize(lambda t: 1 + 0.02 * np.sin(t * 3))
    ])
    
    opt_b_img = create_text_image(wyr_data.get("option_b", "B").upper(), font_size=80, color="white", y_pos=1400)
    opt_b_clip = ImageClip(opt_b_img).with_start(0).with_duration(duration).with_effects([
        vfx.CrossFadeIn(0.5),
        vfx.Resize(lambda t: 1 + 0.02 * np.cos(t * 3))
    ])

    # "Comment your pick" CTA
    reveal_start = audio_clip.duration
    cta_img = create_text_image("💬 COMMENT YOUR PICK!", font_size=90, color="yellow", y_pos=SAFE_MID + 100, add_box=True)
    cta_clip = ImageClip(cta_img).with_start(reveal_start).with_duration(3.0).with_effects([vfx.CrossFadeIn(0.3)])

    # Progress bar for the think time
    bar_height = 20
    bg_bar = ColorClip(size=(1080, bar_height), color=(30, 30, 30)).with_duration(duration).with_position(("center", 1880))
    progress_bar = ColorClip(size=(1080, bar_height), color=(255, 0, 0)).with_duration(duration).with_position(("center", 1880))
    progress_bar = progress_bar.with_effects([vfx.Resize(lambda t: (max(1, int(1080 * t / duration)), bar_height))])

    final_video = CompositeVideoClip([clip1, clip2, dark1, dark2, divider, bg_bar, progress_bar, top_header, opt_a_clip, opt_b_clip, cta_clip], size=(1080, 1920))

    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.18)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    final_video = final_video.with_duration(duration)
    
    print(f"[Log] Exporting WYR short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="8000k", threads=4)
    
    return output_path

def create_reddit_video(audio_path, subs_path, reddit_data, video_paths, output_path="reddit_short.mp4", music_path=None):
    """
    Composes a Reddit Story video with a static title overlay and dynamic subtitles.
    """
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration + 1.0 # Buffer

    # 1. Background (Satisfying video)
    if isinstance(video_paths, str): video_paths = [video_paths]
    
    bg_segments = []
    segment_duration = duration / max(1, len(video_paths))
    for i, path in enumerate(video_paths):
        try:
            clip = VideoFileClip(path)
            n_loops = int(np.ceil(segment_duration / clip.duration)) if clip.duration > 0 else 1
            clip = clip.with_effects([vfx.Loop(n=n_loops)]).with_duration(segment_duration)
            clip = cover_resize(clip, (1080, 1920)).with_start(i * segment_duration)
            bg_segments.append(clip)
        except Exception as e:
            print(f"[Warning] Error processing Reddit bg {path}: {e}")
            
    if not bg_segments:
        bg_clip = ColorClip(size=(1080, 1920), color=(20, 20, 30)).with_duration(duration)
    else:
        bg_clip = CompositeVideoClip(bg_segments, size=(1080, 1920)).with_duration(duration)
        bg_clip = apply_ken_burns(bg_clip, duration)

    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.3).with_duration(duration)

    # 2. Reddit Header Overlay
    reddit_tag_img = create_text_image("🟠 REDDIT STORY", font_size=65, color="white", y_pos=SAFE_TOP - 50, add_box=True)
    reddit_tag_clip = ImageClip(reddit_tag_img).with_start(0).with_duration(duration)

    header_img = create_text_image(reddit_data.get("title", "r/TrueOffMyChest").upper(), font_size=80, color="orange", y_pos=SAFE_TOP + 100, add_box=True)
    post_header = ImageClip(header_img).with_start(0).with_duration(duration)

    # 3. Dynamic Subtitles (Word-by-word with Bounce)
    word_clips = []
    try:
        with open(subs_path, "r", encoding="utf-8") as f:
            subtitles = json.load(f)
            
        for i, entry in enumerate(subtitles):
            text = entry["word"].upper()
            start = entry["start"]
            c_img = create_text_image(text, font_size=120, color="white", y_pos=SAFE_MID)
            c_dur = max(0.6, entry["duration"])
            c_clip = ImageClip(c_img).with_start(start).with_duration(c_dur).with_position((0, 0))
            
            # Bounce scale effect
            c_clip = c_clip.with_effects([vfx.Resize(bounce_scale)])
            word_clips.append(c_clip)
    except Exception as e:
        print(f"[Warning] Failed to render Reddit subtitles: {e}")

    # Composition
    final_video = CompositeVideoClip([bg_clip, dark_overlay, add_pattern_interrupt(duration), reddit_tag_clip, post_header] + word_clips, size=(1080, 1920))

    # Loopability Zoom Effect
    final_video = final_video.with_effects([
        vfx.Resize(lambda t: 1 + 0.03 * np.sin(t / duration * np.pi))
    ])

    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.15)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    final_video = final_video.with_duration(duration)
    
    print(f"[Log] Exporting Reddit short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="7000k", threads=4)
    
    return output_path

def create_trivia_video(audio_path, trivia_data, video_paths, output_path="trivia_short.mp4", music_path=None):
    """
    Composes a Trivia Quiz video with timer and answer reveal.
    """
    audio_clip = AudioFileClip(audio_path)
    reveal_duration = 3.0
    duration = audio_clip.duration + reveal_duration
    
    # 1. Background
    if isinstance(video_paths, str): video_paths = [video_paths]
    
    try:
        bg_clip = VideoFileClip(video_paths[0])
        n_loops = int(np.ceil(duration / bg_clip.duration)) if bg_clip.duration > 0 else 1
        bg_clip = bg_clip.with_effects([vfx.Loop(n=n_loops)]).with_duration(duration)
        bg_clip = cover_resize(bg_clip, (1080, 1920))
        bg_clip = apply_ken_burns(bg_clip, duration)
    except Exception as e:
        print(f"[Warning] Error processing TRIVIA bg: {e}")
        bg_clip = ColorClip(size=(1080, 1920), color=(10, 20, 40)).with_duration(duration)

    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.6).with_duration(duration)
    
    # 2. Text Elements
    # Question
    # Dynamic font size based on length
    q_len = len(trivia_data.get("question", ""))
    q_font = 85 if q_len < 40 else (75 if q_len < 80 else 65)
    
    q_text = trivia_data.get("question", "Question?").upper()
    q_img = create_text_image(q_text, font_size=q_font, color="yellow", y_pos=SAFE_TOP, add_box=True)
    q_clip = ImageClip(q_img).with_start(0).with_duration(duration)
    
    # Calculate question height to avoid overlapping options
    chars_per_line_q = 920 // max(1, int(0.6 * q_font))
    lines_q = (len(q_text) // max(1, chars_per_line_q)) + 1
    q_height = lines_q * (q_font + 30) # Using 30 as new spacing
    
    # Options
    boxes = []
    # Start either at 750 or below the question, whichever is lower
    current_y = max(750, 150 + q_height + 60)
    
    opt_a = f"A) {trivia_data.get('opt_a', 'Opt A').upper()}"
    opt_b = f"B) {trivia_data.get('opt_b', 'Opt B').upper()}"
    opt_c = f"C) {trivia_data.get('opt_c', 'Opt C').upper()}"
    options = [opt_a, opt_b, opt_c]
    
    opt_positions = []
    opt_fonts = []
    
    for i, opt_text in enumerate(options):
        # Dynamic font based on option length
        char_count = len(opt_text)
        o_font = 65 if char_count < 30 else (55 if char_count < 80 else 45)
        
        # Estimate height based on simple character wrapping math
        chars_per_line = 920 // max(1, int(0.6 * o_font))
        lines_estimate = (char_count // max(1, chars_per_line)) + 1
        
        opt_positions.append(current_y)
        opt_fonts.append(o_font)
        
        # Base option
        opt_img = create_text_image(opt_text, font_size=o_font, color="white", y_pos=current_y, add_box=True)
        opt_clip = ImageClip(opt_img).with_start(0).with_duration(duration)
        boxes.append(opt_clip)
        
        # Advance y position for next option
        current_y += int(lines_estimate * (o_font + 30)) + 40
        
    # --- ANS REVEAL ---
    timer_duration = 3.0
    reveal_duration = duration - audio_clip.duration
    
    # Progress Bar Timer (Minecraft style)
    bar_height = 30
    timer_bg = ColorClip(size=(900, bar_height), color=(50, 50, 50)).with_duration(timer_duration).with_position(("center", 1650)).with_start(audio_clip.duration - timer_duration)
    
    timer_fg = ColorClip(size=(900, bar_height), color=(255, 255, 0)).with_position(("center", 1650)).with_start(audio_clip.duration - timer_duration)
    timer_fg = timer_fg.with_duration(timer_duration).with_effects([
        vfx.Resize(lambda t: (max(1, int(900 * (1 - min(t / timer_duration, 1.0)))), bar_height))
    ])
    
    ans = trivia_data.get("answer", "A").upper()
    ans_idx = 0 if ans == "A" else (1 if ans == "B" else 2)
    
    ans_text = options[ans_idx]
    ans_font = opt_fonts[ans_idx]
    ans_y = opt_positions[ans_idx]
    
    # Highlighted answer in Green
    ans_img = create_text_image(ans_text, font_size=ans_font, color="lime", y_pos=ans_y, add_box=True)
    ans_clip = ImageClip(ans_img).with_start(audio_clip.duration).with_duration(reveal_duration)
    
    # Sound effect or flashing could happen here
    reveal_splash = create_text_image("CORRECT!", font_size=110, color="lime", y_pos=1650)
    splash_clip = ImageClip(reveal_splash).with_start(audio_clip.duration).with_duration(reveal_duration).with_effects([vfx.CrossFadeIn(0.2)])
    
    final_video = CompositeVideoClip([bg_clip, dark_overlay, add_pattern_interrupt(duration), q_clip] + boxes + [timer_bg, timer_fg, ans_clip, splash_clip], size=(1080, 1920))

    # Loopability Zoom Effect
    final_video = final_video.with_effects([
        vfx.Resize(lambda t: 1 + 0.03 * np.sin(t / duration * np.pi))
    ])

    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        music = music.with_volume_scaled(0.15)
        audio_clip = CompositeAudioClip([audio_clip, music])
    
    final_video = final_video.with_audio(audio_clip)
    
    print(f"[Log] Exporting TRIVIA short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="7000k", threads=4)
    
    return output_path

def create_quote_video(audio_path, quote_data, video_paths, output_path="quote_short.mp4", music_path=None):
    """
    Composes a moody Quote video with elegant fading text.
    """
    audio_clip = AudioFileClip(audio_path)
    # Add a bit of silence at the end for the lingering quote
    duration = audio_clip.duration + 2.0
    
    # 1. Background (Dark/Moody)
    if isinstance(video_paths, str): video_paths = [video_paths]
    
    try:
        bg_clip = VideoFileClip(video_paths[0])
        n_loops = int(np.ceil(duration / bg_clip.duration)) if bg_clip.duration > 0 else 1
        bg_clip = bg_clip.with_effects([vfx.Loop(n=n_loops)]).with_duration(duration)
        bg_clip = cover_resize(bg_clip, (1080, 1920))
        # Super slow moody ken burns
        bg_clip = apply_ken_burns(bg_clip, duration * 2.0) 
    except Exception as e:
        print(f"[Warning] Error processing QUOTE bg: {e}")
        bg_clip = ColorClip(size=(1080, 1920), color=(5, 5, 10)).with_duration(duration)

    # Heavy dark vignette/overlay
    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.6).with_duration(duration)
    
    # 2. Text (Quote & Author)
    quote_text = f"\"{quote_data.get('quote', 'Silent waters run deep.')}\""
    author_text = f"- {quote_data.get('author', 'Unknown')}"
    
    # We will do a simple slow fade in for the whole quote to keep it elegant, 
    # instead of aggressive word-by-word popping
    
    # Quote
    q_img = create_text_image(quote_text, font_size=75, color="white", y_pos=SAFE_MID - 200)
    q_clip = ImageClip(q_img).with_start(0).with_duration(duration).with_effects([vfx.CrossFadeIn(2.0)])
    
    # Author
    a_img = create_text_image(author_text, font_size=65, color="gray", y_pos=SAFE_BOTTOM - 100)
    a_clip = ImageClip(a_img).with_start(1.0).with_duration(duration - 1.0).with_effects([vfx.CrossFadeIn(2.0)])
    
    final_video = CompositeVideoClip([bg_clip, dark_overlay, add_pattern_interrupt(duration), q_clip, a_clip], size=(1080, 1920))

    # Loopability Zoom Effect
    final_video = final_video.with_effects([
        vfx.Resize(lambda t: 1 + 0.03 * np.sin(t / duration * np.pi))
    ])

    if music_path and os.path.exists(music_path):
        bg_music_clip = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        bg_music_clip = bg_music_clip.with_volume_scaled(0.2)
        audio_clip = CompositeAudioClip([audio_clip, bg_music_clip])
    
    final_video = final_video.with_audio(audio_clip)
    final_video = final_video.with_duration(duration)
    
    print(f"[Log] Exporting QUOTE short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="6000k", threads=4)
    
    return output_path

def create_odd_one_out_video(audio_path, base_img_path, output_path="odd_one_out.mp4", music_path=None):
    """
    Composes an Odd One Out puzzle video.
    Builds a 5x6 grid of the base image, but modifies one (the odd one) to be slightly rotated/flipped.
    """
    audio_clip = AudioFileClip(audio_path)
    timer_duration = 5.0
    duration = audio_clip.duration + timer_duration + 2.0
    
    # 1. Background
    bg_clip = ColorClip(size=(1080, 1920), color=(30, 30, 40)).with_duration(duration)
    
    # 2. Prepare the Grid Source Images
    base_pil = Image.open(base_img_path).convert("RGBA")
    # Make it square
    size = min(base_pil.size)
    # Make it square and slightly smaller for denser grid
    base_pil = base_pil.crop((0, 0, size, size)).resize((120, 120))
    
    # Create the odd one with a random subtle modification
    effect = random.choice(["rotate", "flip", "color"])
    hint = "ONE IS DIFFERENT..."
    
    if effect == "rotate":
        odd_pil = base_pil.rotate(3, expand=False, fillcolor=(0,0,0,0))
    elif effect == "flip":
        odd_pil = base_pil.transpose(Image.FLIP_LEFT_RIGHT)
    else: # color
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(base_pil)
        odd_pil = enhancer.enhance(0.92) # Slightly darker is very hard to spot
    
    
    # 3. Build the Grid Image (Denser grid: 6x8 instead of 5x6)
    grid_cols = 6
    grid_rows = 8
    spacing = 145
    
    grid_w = grid_cols * spacing
    grid_h = grid_rows * spacing
    grid_img = Image.new("RGBA", (grid_w, grid_h), (0,0,0,0))
    
    odd_col = random.randint(0, grid_cols - 1)
    odd_row = random.randint(0, grid_rows - 1)
    
    for r in range(grid_rows):
        for c in range(grid_cols):
            x = c * spacing
            y = r * spacing
            img_to_paste = odd_pil if (r == odd_row and c == odd_col) else base_pil
            grid_img.paste(img_to_paste, (x, y), img_to_paste)

    # 4. Animated Grid Clip
    grid_clip = ImageClip(np.array(grid_img)).with_start(0).with_duration(duration)
    # Center grid
    gx = (1080 - grid_w) // 2
    gy = 600
    grid_clip = grid_clip.with_position((gx, gy))

    # 5. Text Elements
    top_text = create_text_image("SPOT THE ODD ONE OUT!", font_size=80, color="yellow", y_pos=180, add_box=True)
    top_clip = ImageClip(top_text).with_start(0).with_duration(duration)
    
    hint_text = create_text_image(f"HINT: {hint}", font_size=55, color="white", y_pos=340, add_box=True)
    hint_clip = ImageClip(hint_text).with_start(0).with_duration(duration)
    
    # 6. Timer
    timer_h = 40
    timer_start_time = audio_clip.duration - 2.0 # Start timer a bit before audio ends
    timer_bg = ColorClip(size=(900, timer_h), color=(50, 50, 50)).with_duration(timer_duration).with_position(("center", 1750)).with_start(timer_start_time)
    
    timer_fg = ColorClip(size=(900, timer_h), color=(255, 50, 50)).with_position(("center", 1750)).with_start(timer_start_time)
    timer_fg = timer_fg.with_duration(timer_duration).with_effects([
        vfx.Resize(lambda t: (max(1, int(900 * (1 - min(t / timer_duration, 1.0)))), timer_h))
    ])
    
    # 7. Reveal (Replaced answer reveal with a final CTA)
    reveal_start = timer_start_time + timer_duration
    cta_text = create_text_image("DID YOU FIND IT?", font_size=100, color="yellow", y_pos=350, add_box=True)
    cta_clip = ImageClip(cta_text).with_start(reveal_start).with_duration(duration - reveal_start)
    
    # Final comp (Removed ans_clip and ans_text, added hint_clip)
    final_video = CompositeVideoClip([bg_clip, grid_clip, top_clip, hint_clip, timer_bg, timer_fg, cta_clip], size=(1080, 1920))
    
    # Ensure audio lasts for the entire duration by combining voice with (optional) music or silence
    audio_clips = [audio_clip.with_start(0)]
    
    if music_path and os.path.exists(music_path):
        bg_music_clip = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)])
        bg_music_clip = bg_music_clip.with_volume_scaled(0.15)
        audio_clips.append(bg_music_clip)
    
    # Using CompositeAudioClip automatically handles different durations correctly
    final_audio = CompositeAudioClip(audio_clips).with_duration(duration)
    final_video = final_video.with_audio(final_audio)
    
    print(f"[Log] Exporting ODD_ONE_OUT short: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="5000k")
    
    return output_path

def create_sound_challenge_video(audio_path, subs_path, sfx_path, obj_path, video_paths, output_path="sound_short.mp4", music_path=None):
    """
    Composes a 'Guess the Sound' challenge video.
    """
    # 1. Load Audio
    voice_clip = AudioFileClip(audio_path)
    sfx_clip = AudioFileClip(sfx_path).with_volume_scaled(1.5)
    
    # We need to find the gap in the voice for the SFX
    # The script is: [Hook] ... [Reveal]
    with open(subs_path, "r", encoding="utf-8") as f:
        subtitles = json.load(f)
    
    # Simple heuristic: The first chunk is the hook, the rest is the reveal
    hook_end = subtitles[0]["start"] + subtitles[0]["duration"]
    reveal_start = subtitles[1]["start"] if len(subtitles) > 1 else voice_clip.duration
    
    # The gap should be around 5s for the challenge
    sfx_start = hook_end + 0.5
    sfx_duration = min(5.0, sfx_clip.duration)
    sfx_clip = sfx_clip.with_duration(sfx_duration).with_start(sfx_start)
    
    duration = voice_clip.duration + 2.0
    
    # 2. Background
    if isinstance(video_paths, str): video_paths = [video_paths]
    try:
        bg_clip = VideoFileClip(video_paths[0])
        n_loops = int(np.ceil(duration / bg_clip.duration)) if bg_clip.duration > 0 else 1
        bg_clip = bg_clip.with_effects([vfx.Loop(n=n_loops)]).with_duration(duration)
        bg_clip = cover_resize(bg_clip, (1080, 1920))
        bg_clip = bg_clip.with_effects([vfx.Resize(lambda t: 1 + 0.01 * np.sin(t * 2))])
    except Exception as e:
        bg_clip = ColorClip(size=(1080, 1920), color=(10, 10, 20)).with_duration(duration)

    dark_overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.4).with_duration(duration)
    
    # 3. UI Elements
    header_img = create_text_image("GUESS THE SOUND! 🎧", font_size=100, color="yellow", y_pos=SAFE_TOP)
    top_header = ImageClip(header_img).with_start(0).with_duration(duration)
    
    footer_img = create_text_image("COMMENT YOUR GUESS 👇", font_size=65, color="white", y_pos=SAFE_BOTTOM)
    bottom_footer = ImageClip(footer_img).with_start(0).with_duration(duration)
    
    # 4. Timer Bar (During sfx)
    bar_height = 25
    timer_bg = ColorClip(size=(800, bar_height), color=(50, 50, 50)).with_start(sfx_start).with_duration(sfx_duration).with_position(("center", 1600))
    timer_fg = ColorClip(size=(800, bar_height), color=(255, 0, 0)).with_start(sfx_start).with_duration(sfx_duration).with_position(("center", 1600))
    timer_fg = timer_fg.with_effects([vfx.Resize(lambda t: (max(1, int(800 * (1 - t / sfx_duration))), bar_height))])
    
    # 5. Reveal Object
    reveal_audio_start = reveal_start 
    try:
        obj_clip = ImageClip(obj_path).resized(width=600).with_start(reveal_audio_start).with_duration(duration - reveal_audio_start).with_position(("center", "center"))
        obj_clip = obj_clip.with_effects([vfx.Resize(bounce_scale)])
    except:
        obj_clip = ColorClip(size=(1,1), color=(0,0,0,0)).with_duration(0.1)

    # 6. Captions
    word_clips = []
    for entry in subtitles:
        text = entry["word"].upper()
        c_img = create_text_image(text, font_size=110, color="cyan", y_pos=SAFE_MID + 300)
        c_dur = max(0.6, entry["duration"])
        c_clip = ImageClip(c_img).with_start(entry["start"]).with_duration(c_dur).with_position((0, 0)).with_effects([vfx.Resize(bounce_scale)])
        word_clips.append(c_clip)

    # Progress Bar (Urgency)
    bg_bar = ColorClip(size=(1080, 20), color=(40, 40, 40)).with_duration(duration).with_position(("center", 1880))
    progress_bar = ColorClip(size=(1080, 20), color=(255, 255, 0)).with_duration(duration).with_position(("center", 1880))
    progress_bar = progress_bar.with_effects([
        vfx.Resize(lambda t: (max(1, int(1080 * (t / duration) ** 0.7)), 20))
    ])
    progress_bar = progress_bar.transform(lambda gf, t: color_shift_green_kill(gf, t, duration))

    final_audio = CompositeAudioClip([voice_clip, sfx_clip])
    if music_path and os.path.exists(music_path):
        music = AudioFileClip(music_path).with_effects([afx.AudioLoop(duration=duration)]).with_volume_scaled(0.15)
        final_audio = CompositeAudioClip([final_audio, music])

    final_video = CompositeVideoClip(
        [bg_clip, dark_overlay, bg_bar, progress_bar, top_header, bottom_footer, timer_bg, timer_fg, obj_clip] + word_clips,
        size=(1080, 1920)
    )
    
    final_video = final_video.with_audio(final_audio).with_duration(duration).with_fps(24)
    print(f"[Log] Exporting GUESS SOUND challenge: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="7000k", threads=4)
    
    return output_path

if __name__ == "__main__":
    # Test call
    # create_shorts_video("assets/voice.mp3", "assets/subs.json", ["assets/bg.mp4"])
    pass
