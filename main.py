import os
import random
from engine.script_gen import generate_mixed_facts
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video
from engine.video_gen import create_shorts_video

def main():
    print("🚀 Starting 2 Truths & 1 Lie Generator...")
    
    # 1. Generate Interactive Content
    category = random.choice(["science", "space", "animals", "history", "anime", "superheroes"])
    print(f"📝 Generating facts for category: {category}...")
    facts_data = generate_mixed_facts(category)
    
    # Construct the script
    script_parts = ["Here are three shocking facts. But be careful... one of them is a total lie!"]
    for i, f in enumerate(facts_data):
        script_parts.append(f"Fact {i+1}: {f['fact']}")
    
    script_parts.append("Which one is the lie? Comment your guess below!")
    
    full_script = " ".join(script_parts)
    print(f"✅ Script: \"{full_script}\"")
    
    # 2. Generate Voice & Timings
    print("🎙️ Generating voiceover and timing data...")
    audio_path, subs_path = generate_voice(full_script)
    
    if not audio_path or not subs_path:
        print("❌ Voice generation failed.")
        return
        
    # 3. Source Media
    print("🎬 Searching for relevant background video...")
    bg_filename = f"assets/bg_{random.randint(1000,9999)}.mp4"
    bg_video_path = download_background_video(facts_data[0]['fact'], output_path=bg_filename)
    
    if not bg_video_path:
        print("❌ Failed to download background video.")
        return

    # 4. Compose Video
    print("🎞️ Composing final interactive video with background music...")
    output_filename = f"interactive_short_{random.randint(100,999)}.mp4"
    bg_music = "music/bg_music.mp3" if os.path.exists("music/bg_music.mp3") else None
    
    final_video = create_shorts_video(
        audio_path, 
        subs_path, 
        bg_video_path, 
        output_filename,
        music_path=bg_music
    )
    
    print(f"✨ SUCCESS! Interactive video created: {final_video}")
    
    # 5. Social Media Automation
    print("📱 Generating viral metadata...")
    from engine.social_gen import generate_viral_metadata, YouTubeUploader
    
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
        print("💡 Automation ready. Metadata saved. Skipping upload as secrets not found.")
        with open(f"{output_filename}.txt", "w", encoding="utf-8") as f:
            f.write(f"Title: {metadata['title']}\n")
            f.write(f"Description: {metadata['description']}\n")
            f.write(f"Tags: {', '.join(metadata['tags'])}\n")

if __name__ == "__main__":
    main()
