import os
import sys
import time
from engine.comfy_bridge import generate_ai_audio

def test_music():
    print("--- Starting AI Music Generation Test ---")
    prompt = "suspense cinematic sports background music, high quality, studio grade"
    output_dir = "assets/test"
    os.makedirs(output_dir, exist_ok=True)
    
    start_time = time.time()
    try:
        print(f"Submitting prompt: {prompt}")
        result_path = generate_ai_audio(prompt, duration=15.0, output_dir=output_dir)
        
        if result_path and os.path.exists(result_path):
            elapsed = time.time() - start_time
            print(f"SUCCESS: AI Music generated in {elapsed:.2f}s")
            print(f"Output saved to: {os.path.abspath(result_path)}")
        else:
            print("FAILED: No music file was returned by ComfyUI.")
    except Exception as e:
        print(f"EXCEPTION: {e}")
    print("--- Test Finished ---")

if __name__ == "__main__":
    test_music()
