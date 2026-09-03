import os
from engine.script_gen import generate_manim_script
from engine.video_gen import render_manim_scene

print("Testing generate_manim_script...")
try:
    script_data = generate_manim_script("Pythagorean theorem")
    print("Script Title:", script_data.get('title'))
    print("Code length:", len(script_data.get('code', '')))
    print("Voiceover:", script_data.get('voiceover_text'))
    
    print("\nTesting render_manim_scene...")
    output_path = render_manim_scene(script_data['code'], "test_manim_output")
    print(f"Output saved to: {output_path}")
except Exception as e:
    print(f"Error: {e}")
