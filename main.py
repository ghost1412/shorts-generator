import os
import sys
import random
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client
from engine.utils import decrypt_secret

load_dotenv()

from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage

VIBE_VOICE_MAP = {
    "suspense": "en-US-ChristopherNeural", # Deep, intense
    "spooky": "en-US-AndrewNeural",       # Atmospheric
    "cinematic": "en-GB-SoniaNeural",      # Sophisticated narrator
    "upbeat": "en-US-AvaNeural"             # Energetic, modern
}

def main():
    parser = argparse.ArgumentParser(description="Generate either FACTS, STORY, FIND_IT, WYR, REDDIT, TRIVIA, QUOTE, or ODD_ONE_OUT shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "WYR", "REDDIT", "TRIVIA", "QUOTE", "ODD_ONE_OUT", "NEWS", "NEWS_SERIOUS", "AUTO"], help="Force a specific mode.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat"], default="suspense", help="Select background music vibe.")
    parser.add_argument("--user_id", help="The Supabase user ID triggering the generation.")
    parser.add_argument("--video_id", help="The unique ID for this video job.")
    parser.add_argument("--skip_upload", action="store_true", help="Generate video but do not upload to social media.")
    args = parser.parse_args()

    # Force UTF-8 encoding for Windows terminals to handle emojis if possible, 
    # but we'll also remove them to be safe.
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
                ["FACTS", "FIND_IT", "WYR", "ODD_ONE_OUT", "STORY", "TRIVIA", "REDDIT", "QUOTE", "NEWS", "NEWS_SERIOUS"],
                weights=[20, 0, 0, 10, 20, 5, 10, 5, 15, 15]
            )[0]
        print(f"[Log] Mode selected: {mode}", flush=True)
        
        # 2. Choose Category
        categories = ["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks", "world", "politics", "celebrities", "tech", "sports"]
        category = args.category if args.category and args.category in categories else random.choice(categories)
        print(f"[Log] Generating content for category: {category}...", flush=True)
        
        if mode == "FACTS":
            facts_res = generate_mixed_facts(category)
            hook = facts_res["hook"]
            facts_data = facts_res["facts"]
            
            # Construct the script: Hook -> Challenge Intro -> Fact 1, 2, 3 -> Outro
            full_script = f"{hook} ... One of these facts is a fake! Can you find it? ... ... "
            full_script += f"Fact 1: {facts_data[0]['fact']} ... "
            full_script += f"Fact 2: {facts_data[1]['fact']} ... "
            full_script += f"Fact 3: {facts_data[2]['fact']} ... ... "
            full_script += "CAN YOU FIND THE LIE? 👇 Comment below! ... ... "
            full_script += "Like and Subscribe for more daily challenges! You just got smarter!"
        elif mode == "STORY":
            story_data = generate_story(category)
            if not story_data: return
            
            # Construct script with strategic viral pauses
            full_script = f"{story_data['title']}! ... {story_data['story']} ... Like and Subscribe for more true stories!"
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
            news_data = generate_funny_news(category, tone="funny")
            news_source = news_data.get('source', 'Unknown')
            full_script = f"{news_data['hook']} ... {news_data['story']}"
            facts_data = []
            print(f"[Log] NEWS (funny) Data: {news_data}")
        elif mode == "NEWS_SERIOUS":
            news_data = generate_funny_news(category, tone="serious")
            news_source = news_data.get('source', 'Unknown')
            full_script = f"{news_data['hook']} ... {news_data['story']}"
            facts_data = []
            print(f"[Log] NEWS_SERIOUS Data: {news_data}")

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
    print(f"[Log] Selected voice for '{args.vibe}' vibe: {selected_voice}")
    
    audio_path, subs_path = generate_voice(full_script, output_audio=voice_file, output_subs=subs_file, voice_name=selected_voice)
    
    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, "In-Progress Video", "Processing", None, mode)
    
    if not audio_path or not subs_path:
        print("[Error] Voice generation failed.")
        return
        
    # 3. Source Media (Dynamic Backgrounds)
    print("[Log] Searching for relevant background videos...")
    bg_video_paths = []
    
    if mode == "FACTS":
        # Download 3 different clips for facts
        for i, fact in enumerate(facts_data):
            bg_filename = os.path.join(session_dir, f"bg_fact_{i+1}.mp4")
            path = download_background_video(fact['fact'], output_path=bg_filename)
            if not path:
                path = download_background_video("nature", output_path=os.path.join(session_dir, f"bg_fallback_{i}.mp4"))
            if path: bg_video_paths.append(path)
    elif mode == "STORY":
        # For Stories, download 2 high-quality clips based on the title/category
        search_query = f"{category} {story_data['title']}"
        for i in range(2):
            bg_filename = os.path.join(session_dir, f"bg_story_{i}.mp4")
            path = download_background_video(search_query, output_path=bg_filename)
            if not path:
                path = download_background_video("cinematic", output_path=os.path.join(session_dir, f"bg_fallback_story_{i}.mp4"))
            if path: bg_video_paths.append(path)
    elif mode == "FIND_IT" or mode == "FIND_CAT":
        from engine.media_gen import get_game_assets
        # Pass a custom directory or unique prefix if possible (get_game_assets needs update)
        game_assets = get_game_assets(50, output_dir=session_dir)
        target_path = game_assets["target_path"]
        target_name = game_assets["target_name"]
        obj_paths = game_assets["objects"]
        if not target_path:
            print(f"[Error] Failed to download {target_name} image.", flush=True)
            return
    elif mode == "WYR":
        # Two backgrounds for split screen
        search_query = f"{category} satisfying"
        for i in range(2):
            bg_filename = os.path.join(session_dir, f"bg_wyr_{i}.mp4")
            path = download_background_video(search_query if i == 0 else "minecraft parkour", output_path=bg_filename)
            if not path:
                path = download_background_video("nature", output_path=os.path.join(session_dir, f"bg_fallback_wyr_{i}.mp4"))
            if path: bg_video_paths.append(path)
    elif mode == "REDDIT":
        # One high-retention satisfying video
        bg_filename = os.path.join(session_dir, "bg_reddit.mp4")
        path = download_background_video("satisfying sand", output_path=bg_filename)
        if path: bg_video_paths.append(path)
    elif mode == "TRIVIA":
        # Engaging background like Minecraft parkour
        bg_filename = os.path.join(session_dir, "bg_trivia.mp4")
        path = download_background_video("minecraft parkour", output_path=bg_filename)
        if path: bg_video_paths.append(path)
    elif mode == "QUOTE":
        # Moody dark aesthetic
        bg_filename = os.path.join(session_dir, "bg_quote.mp4")
        path = download_background_video("dark cinematic moody slow motion", output_path=bg_filename)
        if path: bg_video_paths.append(path)
    elif mode == "ODD_ONE_OUT":
        from engine.media_gen import get_game_assets
        # We reuse the logic that grabs a single target image for the Odd One Out grid
        game_assets = get_game_assets(1, output_dir=session_dir)
        target_path = game_assets["target_path"]
        target_name = game_assets["target_name"]
        if not target_path:
            print(f"[Error] Failed to download {target_name} image for ODD_ONE_OUT.", flush=True)
            return
    elif mode in ("NEWS", "NEWS_SERIOUS"):
        # Use the search_term from the news data for relevant backgrounds
        search_query = news_data.get('search_term', 'breaking news broadcast') if 'news_data' in dir() else 'breaking news broadcast'
        bg_filename = os.path.join(session_dir, "bg_news.mp4")
        path = download_background_video(search_query, output_path=bg_filename)
        if not path:
            path = download_background_video("news studio broadcast", output_path=os.path.join(session_dir, "bg_news_fallback.mp4"))
        if path: bg_video_paths.append(path)

    if mode not in ["FIND_IT", "FIND_CAT", "ODD_ONE_OUT"] and not any(bg_video_paths):
        print("[Error] Failed to download any background videos.")
        return

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
    
    if mode == "FIND_IT" or mode == "FIND_CAT":
        from engine.video_gen import create_game_video
        final_video = create_game_video(
            audio_path,
            subs_path,
            target_path,
            obj_paths,
            output_filename,
            target_name=target_name,
            music_path=bg_music
        )
    elif mode == "WYR":
        from engine.video_gen import create_wyr_video
        final_video = create_wyr_video(
            audio_path,
            wyr_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music
        )
    elif mode == "REDDIT":
        from engine.video_gen import create_reddit_video
        final_video = create_reddit_video(
            audio_path,
            subs_path,
            reddit_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music
        )
    elif mode == "TRIVIA":
        from engine.video_gen import create_trivia_video
        final_video = create_trivia_video(
            audio_path,
            trivia_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music
        )
    elif mode == "QUOTE":
        from engine.video_gen import create_quote_video
        final_video = create_quote_video(
            audio_path,
            quote_data,
            bg_video_paths,
            output_filename,
            music_path=bg_music
        )
    elif mode == "ODD_ONE_OUT":
        from engine.video_gen import create_odd_one_out_video
        final_video = create_odd_one_out_video(
            audio_path,
            target_path,
            output_filename,
            music_path=bg_music
        )
    else:
        final_video = create_shorts_video(
            audio_path, 
            subs_path, 
            bg_video_paths, 
            output_filename,
            music_path=bg_music,
            mode=mode
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
                            print("[Warning] Refresh token present but GOOGLE_CLIENT_ID/SECRET missing from env. Falling back to global/admin channel.")
                    else:
                        print(f"[Log] No YouTube refresh token found for user {args.user_id}. Falling back to global/admin channel.")
                else:
                    print(f"[Log] No configuration found for user {args.user_id} in Supabase. Falling back to global/admin channel.")
            else:
                print("[Warning] SUPABASE_URL or SERVICE_ROLE_KEY missing for secret retrieval. Falling back to global/admin channel.")

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

if __name__ == "__main__":
    main()
