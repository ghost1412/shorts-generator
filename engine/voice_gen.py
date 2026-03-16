import subprocess
import json
import os
import re

def parse_vtt(vtt_content):
    """
    Parses a VTT file content into a list of word-level timings.
    Handles both . and , as decimal separators.
    """
    subs = []
    # Standard VTT blocks are separated by double newlines or single newlines with indices
    # We'll use a more robust regex for the timestamp line
    timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[\.,]\d{3}) --> (\d{2}:\d{2}:\d{2}[\.,]\d{3})')
    
    lines = vtt_content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = timestamp_pattern.search(line)
        if match:
            start_str = match.group(1).replace(',', '.')
            end_str = match.group(2).replace(',', '.')
            
            def to_sec(s):
                h, m, s = s.split(':')
                return int(h)*3600 + int(m)*60 + float(s)
            
            start = to_sec(start_str)
            end = to_sec(end_str)
            
            # The next line should be the text
            if i + 1 < len(lines):
                word = lines[i+1].strip()
                if word:
                    subs.append({
                        "word": word,
                        "start": start,
                        "duration": max(0.1, end - start)
                    })
                i += 1
        i += 1
    return subs

def generate_voice(text, output_audio="assets/voice.mp3", output_subs="assets/subs.json"):
    """
    Generates voice and subtitles using edge-tts CLI for maximum reliability.
    """
    os.makedirs(os.path.dirname(output_audio), exist_ok=True)
    vtt_path = output_audio.replace(".mp3", ".vtt")
    
    # Use CLI to generate both media and subtitles
    # --words-per-minute or specifically for word-level timing
    voice = "en-US-AndrewNeural"
    try:
        subprocess.run([
            "edge-tts", 
            "--text", text, 
            "--voice", voice, 
            "--write-media", output_audio, 
            "--write-subtitles", vtt_path
        ], check=True, capture_output=True)
        
        if os.path.exists(vtt_path):
            with open(vtt_path, "r", encoding="utf-8") as f:
                vtt_content = f.read()
            
            subtitles = parse_vtt(vtt_content)
            
            with open(output_subs, "w") as f:
                json.dump(subtitles, f, indent=2)
                
            return output_audio, output_subs
    except Exception as e:
        print(f"Error in generate_voice: {e}")
        
    return None, None

if __name__ == "__main__":
    text = "Did you know? Octopuses have three hearts and blue blood."
    a, s = generate_voice(text)
    print(f"Voice: {a}, Subs: {s}")
