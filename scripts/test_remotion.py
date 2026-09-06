import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

from engine.remotion_renderer import render_with_remotion

def test_remotion_run():
    print("Testing Remotion Renderer...")
    audio_path = "assets/voice.mp3"
    subs_path = "assets/subs.json"
    output_path = "test_remotion_output.mp4"
    bg_paths = ["assets/bg.mp4"]
    
    if not os.path.exists(audio_path):
        print(f"Error: {audio_path} does not exist.")
        sys.exit(1)
        
    if not os.path.exists(subs_path):
        print(f"Error: {subs_path} does not exist.")
        sys.exit(1)

    print("Running render_with_remotion...")
    try:
        render_with_remotion(
            audio_path=audio_path,
            subs_path=subs_path,
            output_path=output_path,
            mode="FACTS",
            background_paths=bg_paths,
            duration=40.0
        )
        print("Success! Output generated:", output_path)
    except Exception as e:
        print("Failed to run Remotion render:", e)
        sys.exit(1)

if __name__ == "__main__":
    test_remotion_run()
