import os
import sys
import random
import argparse
from engine.script_gen import generate_mixed_facts, generate_story
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video
from engine.video_gen import create_shorts_video

def main():
    parser = argparse.ArgumentParser(description="Generate either FACTS or STORY shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "AUTO"], help="Force a specific mode.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat"], default="suspense", help="Select background music vibe.")
    parser.add_argument("--user_id", help="The Supabase user ID triggering the generation.")
    parser.add_argument("--video_id", help="The unique ID for this video job.")
    args = parser.parse_args()

    # Force UTF-8 encoding for Windows terminals to handle emojis if possible, 
    # but we'll also remove them to be safe.
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("--- Starting Shorts Generator ---", flush=True)
    
    # 0. Manual Script Override
    if args.script:
        print("[Log] Manual script detected. Skipping generation...")
        full_script = args.script
        mode = "STORY" # Default to story-style branding for manual scripts
        category = "general"
        story_data = {"title": "Manual Upload", "story": full_script}
        facts_data = [] # Not used in story mode but kept for metadata function compatibility
    else:
        # 1. Choose Mode: FACTS or STORY (Manual override or random)
        mode = args.mode if args.mode and args.mode != "AUTO" else random.choice(["FACTS", "STORY"])
        print(f"[Log] Mode selected: {mode}", flush=True)
        
        # 2. Choose Category
        categories = ["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks"]
        category = args.category if args.category and args.category in categories else random.choice(categories)
        print(f"[Log] Generating content for category: {category}...", flush=True)
        
        if mode == "FACTS":
            facts_data = generate_mixed_facts(category)
            # Construct the script with strategic pauses
            full_script = f"SPOT THE LIE! 🔍 One of these facts is a fake. Can you find it? ... ... "
            full_script += f"Fact 1: {facts_data[0]['fact']} ... "
            full_script += f"Fact 2: {facts_data[1]['fact']} ... "
            full_script += f"Fact 3: {facts_data[2]['fact']} ... ... "
            full_script += "CAN YOU FIND IT? 👇 Comment below! ... ... "
            full_script += "Like and Subscribe for more daily facts! You just got smarter!"
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

    print(f"[Log] Full Script: \"{full_script}\"", flush=True)
    
    # 2. Generate Voice & Timings
    print("[Log] Generating voiceover and timing data...", flush=True)
    # Use a unique session ID and directory for complete isolation
    session_id = random.randint(100000, 999999)
    session_dir = f"assets/temp_{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    
    voice_file = os.path.join(session_dir, "voice.mp3")
    subs_file = os.path.join(session_dir, "subs.json")
    audio_path, subs_path = generate_voice(full_script, output_audio=voice_file, output_subs=subs_file)
    
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

    if mode not in ["FIND_IT", "FIND_CAT"] and not any(bg_video_paths):
        print("[Error] Failed to download any background videos.")
        return

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
    else:
        final_video = create_shorts_video(
            audio_path, 
            subs_path, 
            bg_video_paths, 
            output_filename,
            music_path=bg_music,
            is_story=(mode == "STORY")
        )
    
    print(f"[Log] SUCCESS! Interactive video created: {final_video}")
    
    # 5. Social Media Automation
    print("[Log] Generating viral metadata...")
    from engine.social_gen import generate_viral_metadata, YouTubeUploader, InstagramUploader
    
    if mode == "FACTS":
        metadata = generate_viral_metadata(facts_data, category=category)
    elif mode == "FIND_IT" or mode == "FIND_CAT":
        metadata = generate_viral_metadata({"target_name": target_name}, mode="FIND_IT")
    else:
        # For STORY mode
        metadata = generate_viral_metadata(story_data['story'], mode="STORY", category=category)
    print(f"[Log] Viral Title: {metadata['title']}")
    
    print("[Log] Would you like to upload this to YouTube? (Requires client_secrets.json)")
    uploader = YouTubeUploader()
    if uploader.authenticate():
        uploader.upload_video(
            final_video, 
            metadata['title'],
            metadata['description'],
            metadata['tags']
        )
    else:
        print("💡 YouTube Auth skipped.")

    print("[Log] Instagram uploader ready.")
    ig_uploader = InstagramUploader()
    # ig_uploader.upload_reel(final_video, f"{metadata['title']}\n\n{metadata['description']}")
    
    # 6. Report Success to Dashboard
    if args.video_id and args.user_id:
        print(f"[Log] Reporting success to dashboard for Job {args.video_id}...")
        report_status(
            args.video_id, 
            args.user_id, 
            metadata['title'], 
            "Published", 
            output_filename, # This would be a cloud URL in production
            args.mode or mode
        )

    with open(f"{output_filename}.txt", "w", encoding="utf-8") as f:
        f.write(f"Title: {metadata['title']}\n")
        f.write(f"Description: {metadata['description']}\n")
        f.write(f"Tags: {', '.join(metadata['tags'])}\n")

def report_status(video_id, user_id, title, status, download_url, mode):
    """Reports video generation status back to the Next.js dashboard."""
    import requests
    webhook_url = os.getenv("DASHBOARD_WEBHOOK_URL", "http://localhost:3000/api/webhook/github")
    try:
        payload = {
            "video_id": video_id,
            "user_id": user_id,
            "title": title,
            "status": status,
            "download_url": download_url,
            "mode": mode
        }
        res = requests.post(webhook_url, json=payload)
        if res.ok:
            print("[Log] Dashboard updated successfully.")
        else:
            print(f"[Warning] Failed to update dashboard: {res.text}")
    except Exception as e:
        print(f"[Error] Error reporting status: {e}")

if __name__ == "__main__":
    main()
