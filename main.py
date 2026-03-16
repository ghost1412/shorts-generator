import os
import random
from engine.script_gen import generate_mixed_facts
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video
from engine.video_gen import create_shorts_video

def main():
    print("🚀 Starting 2 Truths & 1 Lie Generator...")
    
    # 1. Generate Interactive Content
    category = random.choice(["science", "space", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks"])
    print(f"📝 Generating facts for category: {category}...")
    facts_data = generate_mixed_facts(category)
    
    # Construct the script with strategic pauses
    script_parts = ["SPOT THE LIE! 🔍 One of these facts is a fake. Can you find it? ... ..."]
    for i, f in enumerate(facts_data):
        script_parts.append(f"Fact {i+1}: {f['fact']} ...")
    
    script_parts.append("... CAN YOU FIND IT? 👇 Comment your guess!")
    
    full_script = " ".join(script_parts)
    print(f"✅ Script: \"{full_script}\"")
    
    # 2. Generate Voice & Timings
    print("🎙️ Generating voiceover and timing data...")
    audio_path, subs_path = generate_voice(full_script)
    
    if not audio_path or not subs_path:
        print("❌ Voice generation failed.")
        return
        
    # 3. Source Media (Dynamic Backgrounds)
    print("🎬 Searching for relevant background videos for each fact...")
    bg_video_paths = []
    
    # Download 3 different clips for variety
    for i, fact in enumerate(facts_data):
        bg_filename = f"assets/bg_fact_{i+1}_{random.randint(1000,9999)}.mp4"
        path = download_background_video(fact['fact'], output_path=bg_filename)
        if path:
            bg_video_paths.append(path)
        else:
            # Fallback to a general one if specific download fails
            bg_video_paths.append(download_background_video("nature", output_path=f"assets/bg_fallback_{i}.mp4"))

    if not any(bg_video_paths):
        print("❌ Failed to download any background videos.")
        return

    # 4. Compose Video
    print("🎞️ Composing final interactive video with background music...")
    output_filename = f"interactive_short_{random.randint(100,999)}.mp4"
    bg_music = "music/bg_music.mp3" if os.path.exists("music/bg_music.mp3") else None
    
    final_video = create_shorts_video(
        audio_path, 
        subs_path, 
        bg_video_paths, # Now a list
        output_filename,
        music_path=bg_music
    )
    
    print(f"✨ SUCCESS! Interactive video created: {final_video}")
    
    # 5. Social Media Automation
    print("📱 Generating viral metadata...")
    from engine.social_gen import generate_viral_metadata, YouTubeUploader, InstagramUploader
    
    metadata = generate_viral_metadata(facts_data, category)
    print(f"🔥 Viral Title: {metadata['title']}")
    
    print("☁️ Would you like to upload this to YouTube? (Requires client_secrets.json)")
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

    print("📸 Checking Instagram...")
    ig_uploader = InstagramUploader()
    ig_uploader.upload_reel(final_video, f"{metadata['title']}\n\n{metadata['description']}")
        with open(f"{output_filename}.txt", "w", encoding="utf-8") as f:
            f.write(f"Title: {metadata['title']}\n")
            f.write(f"Description: {metadata['description']}\n")
            f.write(f"Tags: {', '.join(metadata['tags'])}\n")

if __name__ == "__main__":
    main()
