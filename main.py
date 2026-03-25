import os
import sys
import io
import random
import argparse
import json
import subprocess
from dotenv import load_dotenv

# 🟢 Force UTF-8 for all standard streams (fixes CP1252/Emoji crashes on Windows)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from supabase import create_client, Client
from engine.utils import decrypt_secret

load_dotenv()

from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx
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
    parser = argparse.ArgumentParser(description="Generate either FACTS, STORY, FIND_IT, WYR, REDDIT, TRIVIA, QUOTE, or ODD_ONE_OUT shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "WYR", "REDDIT", "TRIVIA", "QUOTE", "ODD_ONE_OUT", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "TREND", "CHALLENGE", "AUTO"], help="Force a specific mode.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat"], default="suspense", help="Select background music vibe.")
    parser.add_argument("--user_id", help="The Supabase user ID triggering the generation.")
    parser.add_argument("--video_id", help="The unique ID for this video job.")
    parser.add_argument("--skip-upload", "--skip_upload", action="store_true", dest="skip_upload", help="Generate video but do not upload to social media.")
    parser.add_argument("--recap_title", help="Movie/Story title for MOVIE_RECAP mode.")
    
    # AI Extraction Flags (Long-form to Short-form)
    parser.add_argument("--source_video", help="Path to long-form source video for AI extraction")
    parser.add_argument("--extract_mode", choices=["shorts", "long"], default="shorts")
    parser.add_argument("--clip_count", type=int, default=5)
    parser.add_argument("--target_duration", type=int, default=30)
    parser.add_argument("--session_dir", help="Reuse session for transcription.")
    parser.add_argument("--use_audio_detect", action="store_true", help="Use audio signals (energy/delta) for extraction.")
    parser.add_argument("--hq", action="store_true", help="Enable High-Quality (Premium) enhancements (sharpening, denoising).")
    
    parser.add_argument("--use_comfy", action="store_true", help="Use local ComfyUI for premium AI backgrounds.")
    parser.add_argument("--use_ai_audio", action="store_true", help="Use local ComfyUI for premium AI music & SFX.")
    parser.add_argument("--bitrate", type=str, help="Manual bitrate override (e.g. 12000k)")
    parser.add_argument("--preset", type=str, help="Manual preset override (e.g. medium)")
    parser.add_argument("--quality", type=str, default="medium", choices=["low", "medium", "high", "ultra"], help="Output quality preset")
    
    # Cartoon/Persona Flags
    parser.add_argument("--cartoon", action="store_true", help="Enable cartoon-style news persona.")
    parser.add_argument("--persona", help="Select a specific cartoon persona (rabbit, robot, squirrel, superhero).")
    
    args = parser.parse_args()
    return args

args = parse_args()

# Quality Mapping (Overridden by manual flags if present)
bitrate_map = {"low": "4M", "medium": "12M", "high": "25M", "ultra": "50M"}
preset_map = {"low": "ultrafast", "medium": "medium", "high": "slow", "ultra": "slower"}

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

# Force UTF-8 encoding for Windows terminals to handle emojis if possible, 
# but we'll also remove them to be safe.
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 🟢 PHASE 13: AI Extraction (High-Speed FFmpeg path)
if getattr(args, "source_video", None):
    import time
    from engine.video_gen import extract_segments
    from engine.analysis import process_source_video
    from engine.social_gen import generate_viral_metadata
    
    print(f"--- Starting AI Extraction: {args.source_video} ---")
    
    session_dir = args.session_dir if args.session_dir else f"sessions/extraction_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    
    print("[Log] Running Transcript-based Highlight Analysis...")
    highlights, transcript_path = process_source_video(
        args.source_video, session_dir, mode=args.extract_mode, 
        clip_count=args.clip_count, target_duration=args.target_duration,
        use_audio_detect=args.use_audio_detect
    )
    
    if not highlights:
        print("[Error] No highlights identified.")
        sys.exit(1)
        
    print(f"[Log] Extracting {len(highlights)} segments in parallel via FFmpeg...")
    extracted_files = extract_segments(
        args.source_video, highlights, transcript_path, session_dir, 
        mode=args.extract_mode, bitrate=target_bitrate, preset=target_preset, codec="libx264",
        is_challenge=(args.mode == "CHALLENGE"), use_hq=args.hq
    )
    
    # Generate viral metadata for Highlights
    print("[Log] Generating viral metadata for extracted clips...")
    highlights_meta = []
    
    if args.extract_mode == "long":
        summary_context = " ".join([h.get('context', h.get('reason', '')) for h in highlights[:5]])
        meta = generate_viral_metadata(summary_context, mode="STORY", category="gaming")
        highlights_meta.append({
            "file": "highlight_reel.mp4",
            "title": meta.get('title', 'Viral Highlight Reel'),
            "description": meta.get('description', ''),
            "tags": meta.get('tags', [])
        })
    else:
        for i, h in enumerate(highlights):
            if i >= len(extracted_files): break
            meta = generate_viral_metadata(h.get('context', h.get('reason', 'Gamer Highlight')), mode="STORY", category="gaming")
            highlights_meta.append({
                "file": os.path.basename(extracted_files[i]),
                "title": meta.get('title', 'Viral Moment'),
                "description": meta.get('description', ''),
                "tags": meta.get('tags', [])
            })
        
    with open(os.path.join(session_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(highlights_meta, f, indent=4)
        
    print(f"[Log] SUCCESS! Extracted videos to {session_dir}")
    sys.exit(0)

print("--- Starting Shorts Generator ---", flush=True)
    
# 0. Manual Script Override
youtube_video_id = None
if args.script:
    print("[Log] Manual script detected. Skipping generation...")
    full_script = args.script
    mode = "STORY" # Default to story-style branding for manual scripts
    category = "general"
    story_data = {"title": "Manual Upload", "story": full_script}
    facts_data = [] # Not used in story mode but kept for metadata function compatibility
else:
    # 1. Choose Mode (Manual override or random)
    # GROWTH UPDATE: Favoring high-engagement "Challenge" modes based on analytics (FACTS, FIND_IT, WYR)
    if args.mode and args.mode != "AUTO":
        mode = args.mode
    else:
        mode = random.choices(
            ["FACTS", "FIND_IT", "WYR", "ODD_ONE_OUT", "STORY", "TRIVIA", "REDDIT", "QUOTE", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND"],
            weights=[20, 0, 0, 20, 15, 5, 0, 5, 20, 15, 0]
        )[0]
    if args.recap_title: mode = "MOVIE_RECAP"
    
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
    categories = ["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks", "world", "politics", "celebrities", "tech", "sports"]
    category = args.category if args.category and args.category in categories else random.choice(categories)
    print(f"[Log] Generating content for category: {category}...", flush=True)
    
    try:
        if mode == "FACTS":
            facts_res = generate_mixed_facts(category)
            hook = facts_res["hook"]
            facts_data = facts_res["facts"]
            
            # Construct the script: Hook -> Challenge Intro -> Fact 1, 2, 3 -> Loop Outro
            full_script = f"{hook} ... One of these facts is a LIE! ... "
            full_script += f"1: {facts_data[0]['fact']} ... "
            full_script += f"2: {facts_data[1]['fact']} ... "
            full_script += f"3: {facts_data[2]['fact']} ... "
            # 🟢 UPGRADE: Seamless Viral Loop
            full_script += f"The real answer is ... wait... {facts_res.get('loop_lead', 'Go back and check again.')}"
        elif mode == "MOVIE_RECAP":
            from engine.script_gen import generate_movie_recap
            recap_data = generate_movie_recap(args.recap_title)
            full_script = recap_data.get("story") or recap_data.get("script", "")
            facts_data = []
            story_data = {"title": args.recap_title, "story": full_script}
        elif mode == "STORY":
            story_data = generate_story(category)
            if not story_data: sys.exit(0)
            
            # Construct script with strategic viral pauses
            # 🟢 UPGRADE: Removed "Bot-like" title and added Seamless Loop
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
            full_script = "Spot the odd one out! 🧐 99% of people fail this test... You have 5 seconds... ... ... ... ... Did you find it? Like and subscribe!"
            facts_data = []
            print(f"[Log] ODD_ONE_OUT Selected")
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
    search_query = f"{category} {story_data['title']}"
    for i in range(2):
        bg_filename = os.path.join(session_dir, f"bg_story_{i}.mp4")
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
elif mode in ["CHALLENGE", "TREND"]:
    bg_filename = os.path.join(session_dir, "bg_gen.mp4")
    path = get_bg_path(category + " satisfying", bg_filename)
    if path: bg_video_paths.append(path)

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
from engine.social_gen import generate_viral_metadata, YouTubeUploader, InstagramUploader
    
if mode == "FACTS":
    metadata = generate_viral_metadata(facts_data, category=category)
elif mode == "FIND_IT" or mode == "FIND_CAT":
    metadata = generate_viral_metadata({"target_name": target_name}, mode="FIND_IT")
elif mode == "WYR":
    metadata = generate_viral_metadata(f"Would You Rather: {wyr_data['option_a']} OR {wyr_data['option_b']}", mode="STORY", category=category)
elif mode == "REDDIT":
    metadata = generate_viral_metadata(reddit_data['story'], mode="STORY", category=category)
    # Use reddit title but enforce YouTube's length limit (100 chars max, use 95 for safety)
    metadata['title'] = reddit_data['title'][:95]
elif mode == "TRIVIA":
    metadata = generate_viral_metadata(f"Trivia: {trivia_data['question']} Did you guess right?", mode="STORY", category=category)
elif mode == "QUOTE":
    metadata = generate_viral_metadata(f"Deep Quote: {quote_data['quote']}", mode="STORY", category=category)
elif mode == "ODD_ONE_OUT":
    metadata = generate_viral_metadata({"target_name": f"Odd {target_name}"}, mode="FIND_IT")
elif mode in ("NEWS", "NEWS_SERIOUS"):
    metadata = generate_viral_metadata(news_data.get('story', 'Breaking News'), mode="NEWS", category=category)
    # Append source credit to description
    source_credit = news_data.get('source', '')
    if source_credit:
        metadata['description'] = metadata.get('description', '') + f"\n\n📰 Source: {source_credit}"
elif mode == "GUESS_SOUND":
    metadata = generate_viral_metadata(f"Can you guess this sound? It's a {sound_data['object']}", mode="STORY", category=category)
else:
    # For STORY or other modes
    story_content = story_data['story'] if 'story_data' in locals() and story_data else "Viral Story"
    metadata = generate_viral_metadata(story_content, mode=mode, category=category)

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

        print("[Log] Instagram uploader ready.")
        ig_uploader = InstagramUploader()
        # ig_uploader.upload_reel(final_video, f"{metadata['title']}\n\n{metadata['description']}")

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
