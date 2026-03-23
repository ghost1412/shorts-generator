import sys
import os
import platform

# 🟢 WMI HANG FIX: Bypass slow/broken platform.system() on Windows
if os.name == 'nt':
    platform.system = lambda: "Windows"

print("--- Initializing Shorts-Generator CLI ---") # Instant feedback

# Moved heavy imports inside main() for instant startup:
# from supabase import ...
# from engine.utils import ...

# Moved heavy imports inside main() for instant startup
# from engine.script_gen import ...
# from engine.voice_gen import generate_voice
# from engine.media_gen import ...
# from engine.video_gen import ...
# from engine.storage import ...
# from engine.social_gen import ...

VIBE_VOICE_MAP = {
    "suspense": "en-US-ChristopherNeural", # Deep, intense
    "spooky": "en-US-AndrewNeural",       # Atmospheric
    "cinematic": "en-GB-SoniaNeural",      # Sophisticated narrator
    "upbeat": "en-US-AvaNeural"             # Energetic, modern
}

def report_status(video_id, user_id, title="Shorts Video", status="Processing", download_url=None, mode="AUTO", youtube_video_id=None, storage_path=None, thumbnail_path=None):
    """Updates video generation status directly in Supabase (no webhook needed)."""
    from supabase import create_client
    
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
        db.table("video_logs").update(update_data).eq("id", video_id).execute()
        
        if status == "Published" and user_id:
            config_res = db.table("user_configs").select("generations_used").eq("user_id", user_id).single().execute()
            if config_res.data:
                current = config_res.data.get("generations_used", 0) or 0
                db.table("user_configs").update({"generations_used": current + 1}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"[Error] Failed to update Supabase directly: {e}")

def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    import argparse
    import time
    import random
    import json
    
    from engine.video_gen import extract_segments # Lightweight wrapper
    from engine.voice_gen import generate_voice   # Fast edge-tts
    
    parser = argparse.ArgumentParser(description="Generate either FACTS, STORY, FIND_IT, WYR, REDDIT, TRIVIA, QUOTE, or ODD_ONE_OUT shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "WYR", "REDDIT", "TRIVIA", "QUOTE", "ODD_ONE_OUT", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "TREND", "CHALLENGE", "AUTO"], help="Force a specific mode.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat"], default="suspense", help="Select background music vibe.")
    parser.add_argument("--user_id", help="The Supabase user ID triggering the generation.")
    parser.add_argument("--video_id", help="The unique ID for this video job.")
    parser.add_argument("--skip_upload", action="store_true", help="Generate video but do not upload to social media.")
    parser.add_argument("--recap_title", help="Movie/Story title for MOVIE_RECAP mode.")
    
    # AI Extraction Flags (Long-form to Short-form)
    parser.add_argument("--source_video", help="Path to long-form source video for AI extraction")
    parser.add_argument("--extract_mode", choices=["shorts", "long"], default="shorts")
    parser.add_argument("--clip_count", type=int, default=5)
    parser.add_argument("--target_duration", type=int, default=30)
    parser.add_argument("--session_dir", help="Reuse session for transcription.")
    
    # QUALITY CONTROLS
    parser.add_argument("--quality", type=str, default="medium", choices=["low", "medium", "high", "ultra"], help="Output quality preset")
    parser.add_argument("--codec", type=str, default="libx264", choices=["libx264", "libx265"], help="Video codec (x264 or x265/HEVC)")
    
    args = parser.parse_args()

    # Quality Mapping
    bitrate_map = {"low": "4M", "medium": "12M", "high": "25M", "ultra": "50M"}
    preset_map = {"low": "ultrafast", "medium": "medium", "high": "slow", "ultra": "slower"}
    target_bitrate = bitrate_map.get(args.quality)
    target_preset = preset_map.get(args.quality)

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # Initializations to prevent UnboundLocalError
    facts_data = []
    story_data = None
    mode = "FACTS"
    category = "general"
    youtube_video_id = None
    
    if getattr(args, "source_video", None):
        print(f"--- Starting AI Extraction: {args.source_video} ---")
        print("[Log] Initializing AI Engine (Torch/Whisper)...")
        from engine.analysis import process_source_video
        from engine.social_gen import generate_viral_metadata
        
        session_dir = args.session_dir if args.session_dir else f"sessions/extraction_{int(time.time())}"
        os.makedirs(session_dir, exist_ok=True)
        
        print("[Log] Running Transcript-based Highlight Analysis...")
        highlights, transcript_path = process_source_video(
            args.source_video, session_dir, mode=args.extract_mode, 
            clip_count=args.clip_count, target_duration=args.target_duration
        )
        
        if not highlights:
            print("[Error] No highlights identified.")
            return
            
        print(f"[Log] Extracting {len(highlights)} segments in parallel via FFmpeg (Direct-Burn)...")
        extracted_files = extract_segments(
            args.source_video, highlights, transcript_path, session_dir, 
            mode=args.extract_mode, bitrate=target_bitrate, preset=target_preset, codec=args.codec,
            is_challenge=(args.mode == "CHALLENGE")
        )
        
        # 🟢 PHASE 13: Viral Metadata for Highlights
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
        print(f"[Log] Viral metadata saved to {os.path.join(session_dir, 'metadata.json')}")
        return

    print("--- Starting Shorts Generator ---", flush=True)
    # from engine.script_gen import ... (Moved into the mode logic)
    
    youtube_video_id = None
    facts_data = []
    story_data = None
    
    if args.script:
        print("[Log] Manual script detected. Skipping generation...")
        full_script = args.script
        mode = "STORY"
        category = "general"
        story_data = {"title": "Manual Upload", "story": full_script}
        facts_data = []
    else:
        # 1. Choose Mode (Manual override or random)
        if args.mode and args.mode != "AUTO":
            mode = args.mode
        else:
            mode = random.choices(
                ["FACTS", "FIND_IT", "WYR", "ODD_ONE_OUT", "STORY", "TRIVIA", "REDDIT", "QUOTE", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND"],
                weights=[15, 0, 0, 10, 15, 5, 10, 5, 15, 15, 10]
            )[0]
        
        if args.recap_title: mode = "MOVIE_RECAP"
        print(f"[Log] Mode selected: {mode}", flush=True)
        
        # 2. Choose Category
        categories = ["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks", "world", "politics", "celebrities", "tech", "sports"]
        category = args.category if args.category and args.category in categories else random.choice(categories)
        print(f"[Log] Generating content for category: {category}...", flush=True)
        
        try:
            if mode == "FACTS":
                from engine.script_gen import generate_mixed_facts
                facts_res = generate_mixed_facts(category)
                hook = facts_res["hook"]
                facts_data = facts_res["facts"]
                full_script = f"{hook} ... One of these facts is a LIE! ... 1: {facts_data[0]['fact']} ... 2: {facts_data[1]['fact']} ... 3: {facts_data[2]['fact']} ... {facts_res.get('loop_lead', 'Go back and check again.')}"
            elif mode == "STORY":
                from engine.script_gen import generate_story
                story_data = generate_story(category)
                if not story_data: return
                full_script = f"{story_data['story']} ... {story_data.get('loop_lead', 'Hit the plus if you want more.')}"
                facts_data = []
                print(f"[Log] Story: {story_data['story']}")
            elif mode == "FIND_IT" or mode == "FIND_CAT":
                intros = ["Only GIGACHADS can find this! 🗿", "Bro is hiding from the IRS! 🤫", "99% of you will FAIL this challenge! 🧠", "POV: You are searching for your brain cells...", "If you don't find this, you owe me a sub! 🤝"]
                full_script = f"{random.choice(intros)} ... 🔍 Spot the target in 5 seconds! ... ... ... ... ... Did you find it? ... ... "
                facts_data = []
            elif mode == "WYR":
                from engine.script_gen import generate_wyr
                wyr_data = generate_wyr(category)
                full_script = f"Would you rather? 🔴 {wyr_data['option_a']} ... OR ... 🔵 {wyr_data['option_b']} ... ... What did you choose? Let me know!"
                facts_data = []
            elif mode == "REDDIT":
                from engine.script_gen import generate_reddit_story
                reddit_data = generate_reddit_story(category)
                full_script = f"{reddit_data['title']} ... {reddit_data['story']} ... Whose side are you on? Let me know!"
                facts_data = []
            elif mode == "TRIVIA":
                from engine.script_gen import generate_trivia
                trivia_data = generate_trivia(category)
                full_script = f"Are you a genius? Let's find out! ... {trivia_data['question']} ... A: {trivia_data['opt_a']} ... B: {trivia_data['opt_b']} ... C: {trivia_data['opt_c']} ... Answer is ... {trivia_data['answer']}. Did you get it right?"
                facts_data = []
            elif mode == "QUOTE":
                from engine.script_gen import generate_quote
                quote_data = generate_quote(category)
                full_script = f"Listen closely... ... {quote_data['quote']} ... ... ... ... Do you agree?"
                facts_data = []
            elif mode == "ODD_ONE_OUT":
                full_script = "Spot the odd one out! 🧐 99% of people fail this test... You have 5 seconds... ... ... ... ... Did you find it? Like and subscribe!"
                facts_data = []
            elif mode == "NEWS":
                from engine.script_gen import generate_funny_news
                news_data = generate_funny_news(category, tone="funny")
                full_script = f"{news_data['hook']} ... {news_data['story']}"
                facts_data = []
            elif mode == "NEWS_SERIOUS":
                from engine.script_gen import generate_funny_news
                news_data = generate_funny_news(category, tone="serious")
                full_script = f"{news_data['hook']} ... {news_data['story']}"
                facts_data = []
            elif mode == "GUESS_SOUND":
                from engine.script_gen import generate_sound_challenge
                sound_data = generate_sound_challenge(category)
                full_script = f"{sound_data['hook']} ... ... ... ... ... {sound_data['reveal_text']}"
                facts_data = []
            elif mode == "MOVIE_RECAP":
                from engine.script_gen import generate_movie_recap
                recap_data = generate_movie_recap(args.recap_title)
                full_script = recap_data["script"]
                facts_data = []
                story_data = {"title": args.recap_title, "story": full_script}
            elif mode == "TREND":
                print("[Log] Fetching latest trending topics...")
                from engine.trend_gen import get_random_trend
                from engine.script_gen import generate_trend_script
                trend = get_random_trend()
                if not trend:
                    print("[Error] No trends found. Falling back to FACTS.")
                    # mode = "FACTS"
                    return # Skip recursion for safety
                
                print(f"[Log] Generating script for trend: {trend['title']} ({trend['traffic']} searches)")
                trend_data = generate_trend_script(trend["title"])
                if not trend_data: return
                full_script = trend_data["script"]
                story_data = {"title": trend_data["title"], "story": full_script}
                facts_data = []
            elif mode == "CHALLENGE":
                from engine.script_gen import generate_breath_challenge
                challenge_data = generate_breath_challenge()
                full_script = challenge_data["script"]
                story_data = {"title": challenge_data["title"], "story": full_script}
                facts_data = []
        except RuntimeError as e:
            print(f"[Error] Generation failed: {e}")
            return

    print(f"[Log] Full Script: \"{full_script}\"", flush=True)
    
    # 2. Generate Voice & Timings
    session_id = random.randint(100000, 999999)
    session_dir = f"assets/temp_{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    voice_file = os.path.join(session_dir, "voice.mp3")
    subs_file = os.path.join(session_dir, "subs.json")
    selected_voice = VIBE_VOICE_MAP.get(args.vibe, "en-US-AriaNeural")
    add_cta = mode in ["FACTS", "WYR", "FIND_IT", "ODD_ONE_OUT", "TRIVIA", "GUESS_SOUND"]
    audio_path, subs_path = generate_voice(full_script, output_audio=voice_file, output_subs=subs_file, voice_name=selected_voice, add_cta=add_cta)
    
    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, "In-Progress Video", "Processing", None, mode)
    
    if not audio_path or not subs_path:
        print("[Error] Voice generation failed.")
        return
        
    # 3. Source Media (Dynamic Backgrounds)
    from engine.media_gen import download_background_video, download_image, download_sfx
    bg_video_paths = []
    if mode == "FACTS":
        for i, fact in enumerate(facts_data):
            bg_filename = os.path.join(session_dir, f"bg_fact_{i+1}.mp4")
            path = download_background_video(fact['fact'], output_path=bg_filename)
            if not path: path = download_background_video("nature", output_path=os.path.join(session_dir, f"bg_fallback_{i}.mp4"))
            if path: bg_video_paths.append(path)
    elif mode == "STORY" or mode == "MOVIE_RECAP":
        search_query = f"{category} {story_data.get('title', 'story')}"
        for i in range(2):
            bg_filename = os.path.join(session_dir, f"bg_story_{i}.mp4")
            path = download_background_video(search_query, output_path=bg_filename)
            if not path: path = download_background_video("cinematic", output_path=os.path.join(session_dir, f"bg_fallback_{i}.mp4"))
            if path: bg_video_paths.append(path)
    elif mode == "FIND_IT" or mode == "FIND_CAT":
        from engine.media_gen import get_game_assets
        game_assets = get_game_assets(50, output_dir=session_dir)
        target_path, target_name, obj_paths = game_assets["target_path"], game_assets["target_name"], game_assets["objects"]
        if not target_path: return
    elif mode == "WYR":
        search_query = f"{category} satisfying"
        for i in range(2):
            bg_filename = os.path.join(session_dir, f"bg_wyr_{i}.mp4")
            path = download_background_video(search_query if i == 0 else "minecraft parkour", output_path=bg_filename)
            if path: bg_video_paths.append(path)
    elif mode == "REDDIT" or mode == "TRIVIA" or mode == "QUOTE" or mode == "GUESS_SOUND":
        bg_filename = os.path.join(session_dir, "bg_gen.mp4")
        path = download_background_video(category + " satisfying", output_path=bg_filename)
        if path: bg_video_paths.append(path)
        if mode == "GUESS_SOUND":
            download_image(sound_data["object"], output_path=os.path.join(session_dir, "reveal_obj.png"))
            download_sfx(sound_data["sound_query"], output_path=os.path.join(session_dir, "challenge_sfx.mp3"))

    if mode not in ["FIND_IT", "FIND_CAT", "ODD_ONE_OUT"] and not any(bg_video_paths):
        print("[Error] Failed to download any background videos.")
        return

    # 4. Compose Video
    from engine.video_gen import create_shorts_video
    output_filename = f"interactive_short_{session_id}.mp4"
    bg_music = "music/bg_music.mp3"
    
    if mode == "FIND_IT" or mode == "FIND_CAT":
        from engine.video_gen import create_game_video
        final_video = create_game_video(audio_path, subs_path, target_path, obj_paths, output_filename, target_name=target_name, music_path=bg_music)
    elif mode == "WYR":
        from engine.video_gen import create_wyr_video
        final_video = create_wyr_video(audio_path, wyr_data, bg_video_paths, output_filename, music_path=bg_music)
    elif mode == "REDDIT":
        from engine.video_gen import create_reddit_video
        final_video = create_reddit_video(audio_path, subs_path, reddit_data, bg_video_paths, output_filename, music_path=bg_music)
    elif mode == "TRIVIA":
        from engine.video_gen import create_trivia_video
        final_video = create_trivia_video(audio_path, trivia_data, bg_video_paths, output_filename, music_path=bg_music)
    elif mode == "QUOTE":
        from engine.video_gen import create_quote_video
        final_video = create_quote_video(audio_path, quote_data, bg_video_paths, output_filename, music_path=bg_music)
    elif mode == "ODD_ONE_OUT":
        from engine.video_gen import create_odd_one_out_video
        final_video = create_odd_one_out_video(audio_path, target_path, output_filename, music_path=bg_music)
    elif mode == "GUESS_SOUND":
        from engine.video_gen import create_sound_challenge_video
        final_video = create_sound_challenge_video(audio_path, subs_path, os.path.join(session_dir, "challenge_sfx.mp3"), os.path.join(session_dir, "reveal_obj.png"), bg_video_paths, output_filename, music_path=bg_music)
    else:
        final_video = create_shorts_video(audio_path, subs_path, bg_video_paths, output_filename, music_path=bg_music, mode=mode, bitrate=target_bitrate, preset=target_preset)

    # 5. Social Media Automation
    # 5. Viral Metadata Generation (Required for both Upload and Local Report)
    print("[Log] Generating viral metadata...")
    from engine.social_gen import generate_viral_metadata
        
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
        from engine.social_gen import YouTubeUploader, InstagramUploader, decrypt_secret
        from supabase import create_client
        
        youtube_creds = None
        if args.user_id:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Use Service Role for backend
            
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)
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
                print("💡 YouTube Auth failed or skipped.")

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

    print(f"[Log] SUCCESS! Interactive video created: {final_video}")

if __name__ == "__main__":
    main()
