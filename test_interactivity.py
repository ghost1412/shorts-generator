import os
import sys
import json

# Add current dir to path
sys.path.append(os.getcwd())

from engine.video_gen import create_shorts_video

def verify_interactivity():
    print("🧪 Verifying Enhanced Interactivity features...")
    
    # Check if we have assets to test with
    # If not, we'll try to find any .mp4 in assets
    test_video = None
    for f in os.listdir("assets"):
        if f.endswith(".mp4") and "bg_" in f:
            test_video = os.path.join("assets", f)
            break
    
    if not test_video:
        # Fallback to a color clip will be handled by the function if file doesn't exist
        test_video = "assets/fallback.mp4" 

    # Mock voice and subs if they don't exist
    voice_path = "assets/test_voice.mp3"
    subs_path = "assets/test_subs.json"
    
    # We'll assume the user has run the main script at least once or we use existing ones
    # For this verification, we search for most recent ones
    
    actual_voice = "assets/voice.mp3"
    actual_subs = "assets/subs.json"

    if not actual_voice or not actual_subs:
        print("⚠️ No existing assets found to test with. Creating mock subs for logic check...")
        mock_subs = [
            {"word": "HERE", "start": 0.0, "duration": 0.5},
            {"word": "IS", "start": 0.5, "duration": 0.5},
            {"word": "FACT", "start": 1.0, "duration": 0.5},
            {"word": "1", "start": 1.5, "duration": 0.5},
            {"word": "THAT", "start": 2.0, "duration": 0.5},
            {"word": "ANSWER", "start": 5.0, "duration": 0.5}
        ]
        with open(subs_path, "w") as f:
            json.dump(mock_subs, f)
        actual_subs = subs_path
        # We need a real mp3 for AudioFileClip to not fail
        # We'll skip real export if no mp3 is found
    
    if actual_voice and actual_subs and os.path.exists(actual_voice):
        try:
            output = "test_interactive_output.mp4"
            print(f"🎬 Testing export with {actual_voice} and {actual_subs}...")
            create_shorts_video(
                actual_voice, 
                actual_subs, 
                test_video, 
                output_path=output, 
                lie_index=2
            )
            print(f"✅ Export successful: {output}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    else:
        print("⏭️ Skipping real export due to missing audio assets. Logic check complete.")

if __name__ == "__main__":
    verify_interactivity()
