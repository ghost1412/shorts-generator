import os
import requests
import random
import re
import numpy as np
from dotenv import load_dotenv
from engine.comfy_bridge import generate_cinematic_backgrounds

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Viral high-retention background types
HIGH_RETENTION_QUERIES = [
    "minecraft parkour", 
    "gta 5 ramp jump", 
    "satisfying sand", 
    "hydraulic press", 
    "kinetic sand", 
    "slime asmr", 
    "subway surfers gameplay", 
    "soap cutting"
]

def extract_keywords(text):
    """
    Simple keyword extraction by removing common words.
    """
    stopwords = {"did", "you", "know", "that", "the", "is", "of", "and", "a", "in", "to", "it", "with", "have", "for", "are", "on", "shocking", "interesting", "fact"}
    words = re.findall(r'\w+', text.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    return keywords[:3] # Return top 3 keywords

def download_background_video(fact_text, fallback_query="nature", output_path="assets/bg.mp4", orientation="portrait"):
    """
    downloads a background video based on keywords from the fact.
    Higher priority given to high-retention gameplay/satisfying clips to boost AVD.
    """
    # 50% chance to force a high-retention background instead of a literal one
    if random.random() > 0.5:
        query = random.choice(HIGH_RETENTION_QUERIES)
        print(f"[Log] Forcing HIGH-RETENTION background: '{query}'")
    else:
        keywords = extract_keywords(fact_text)
        query = " ".join(keywords) if keywords else fallback_query
        print(f"[Log] Searching Pexels for: '{query}'")
    
    # Check if we already have this query in assets (caching)
    safe_query = re.sub(r'[^a-zA-Z0-9]', '_', query).lower()
    cached_path = f"assets/bg_{safe_query}.mp4"
    if os.path.exists(cached_path):
        print(f"[Log] Cache Hit: Using existing video for '{query}'")
        import shutil
        shutil.copy(cached_path, output_path)
        return output_path

    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation={orientation}"

    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        videos = r.json().get("videos", [])
        
        if not videos:
            print(f"No videos found for query '{query}', falling back to '{fallback_query}'")
            return download_background_video("", fallback_query, output_path)
            
        video_data = random.choice(videos)
        video_files = video_data.get("video_files", [])
        
        best_link = None
        for vfile in video_files:
            if vfile.get("quality") == "hd" and vfile.get("width") == 1080:
                best_link = vfile.get("link")
                break
        
        if not best_link and video_files:
            best_link = video_files[0].get("link")
            
        if best_link:
            print(f"Downloading video: {best_link}")
            video_content = requests.get(best_link, timeout=30).content
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(video_content)
            
            # Save to cache as well
            with open(cached_path, "wb") as f:
                f.write(video_content)
                
            return output_path
            
    except Exception as e:
        print(f"Error downloading video: {e}")

def generate_ai_background(prompt, output_path="assets/bg.png", width=1024, height=1024):
    """
    Generates a premium AI background using the ComfyUI bridge.
    """
    results = generate_cinematic_backgrounds(prompt, width=width, height=height)
    if results:
        import shutil
        shutil.copy(results[0], output_path)
        return output_path
    return None
        
def download_image(query, output_path="assets/obj.png"):
    """
    Downloads an image based on a query from Pexels.
    """
    print(f"[Log] Searching Pexels Image for: '{query}'")
    
    # Cache Check
    safe_query = re.sub(r'[^a-zA-Z0-9]', '_', query).lower()
    cached_path = f"assets/img_{safe_query}.png"
    if os.path.exists(cached_path):
        print(f"[Log] Cache Hit: Using existing image for '{query}'")
        import shutil
        shutil.copy(cached_path, output_path)
        return output_path

    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"

    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        photos = r.json().get("photos", [])
        
        if photos:
            img_url = photos[0].get("src", {}).get("large")
            if img_url:
                print(f"Downloading image: {img_url}")
                img_content = requests.get(img_url, timeout=30).content
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(img_content)
                
                # Save to cache
                with open(cached_path, "wb") as f:
                    f.write(img_content)
                    
                return output_path
    except Exception as e:
        print(f"Error downloading image: {e}")
    return None

def get_game_assets(num_objects=30, target_query=None, output_dir="assets/game"):
    """
    Fetches one target (meme, figure, object) and a set of similar distractors for the game.
    """
    os.makedirs(output_dir, exist_ok=True)
    assets = {"target_name": "cat", "target_path": None, "objects": []}
    
    # 1. Define funny targets if none provided
    targets = [
        {"name": "Doge", "query": "doge meme"},
        {"name": "Gigachad", "query": "gigachad"},
        {"name": "Shrek", "query": "shrek"},
        {"name": "Crying Jordan", "query": "crying jordan meme"},
        {"name": "Meme Cat", "query": "funny cat meme"},
        {"name": "Hasbulla", "query": "hasbulla"},
        {"name": "Among Us Red", "query": "among us character red"},
        {"name": "Pepe", "query": "pepe the frog"},
        {"name": "Cheems", "query": "cheems meme"},
        {"name": "SpongeBob", "query": "spongebob mockup"},
        {"name": "Patrick", "query": "patrick star meme"},
        {"name": "Spider-Man", "query": "spider man pointing meme"}
    ]
    
    selected_target = random.choice(targets) if not target_query else {"name": "Object", "query": target_query}
    assets["target_name"] = selected_target["name"]
    
    # Download Target
    target_path = download_image(selected_target["query"], output_path=os.path.join(output_dir, f"target_{random.randint(100,999)}.png"))
    assets["target_path"] = target_path
    
    # 2. Get Similar Distractors (Context Aware)
    if any(m in assets["target_name"].lower() for m in ["doge", "meme", "cat", "shrek", "pepe", "hasbulla", "cheems", "spongebob", "patrick", "spider"]):
        distractor_query = random.choice(["funny meme sticker", "cartoon characters", "funny animal drawing", "famous memes bundle"])
    else:
        distractor_query = random.choice(["sketch face", "line art portrait", "cartoon face drawing", "human avatar"])
    
    print(f"[Log] Fetching {num_objects} distractors for query: '{distractor_query}'")
    
    url = f"https://api.pexels.com/v1/search?query={distractor_query}&per_page={num_objects}"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        photos = r.json().get("photos", [])
        
        for i, photo in enumerate(photos):
            img_url = photo.get("src", {}).get("large")
            if img_url:
                obj_path = os.path.join(output_dir, f"obj_{i}_{random.randint(100,999)}.png")
                img_content = requests.get(img_url, timeout=30).content
                with open(obj_path, "wb") as f:
                    f.write(img_content)
                if "objects" not in assets or not isinstance(assets["objects"], list):
                    assets["objects"] = []
                assets["objects"].append(obj_path)
    except Exception as e:
        print(f"Error downloading distractors: {e}")
            
    return assets

SFX_LIBRARY = {
    "lion": "https://upload.wikimedia.org/wikipedia/commons/4/47/Lion_roar.ogg",
    "jet": "https://upload.wikimedia.org/wikipedia/commons/e/e0/F-14_Tomcat_Takeoff.ogg",
    "police": "https://upload.wikimedia.org/wikipedia/commons/4/48/Police_siren.ogg",
    "car crash": "https://upload.wikimedia.org/wikipedia/commons/0/07/Car_crash_sound_effect.ogg",
    "thunder": "https://upload.wikimedia.org/wikipedia/commons/1/13/Thunder_sound_effect.ogg",
    "rain": "https://upload.wikimedia.org/wikipedia/commons/9/91/Rain_in_woods.ogg",
    "whoosh": "https://upload.wikimedia.org/wikipedia/commons/1/1b/Whoosh.ogg"
}

# moviepy 2.2.1 surgical import
import moviepy.audio.AudioClip
AudioClip = moviepy.audio.AudioClip.AudioClip

def generate_local_sfx(kind, output_path):
    """Synthesizes basic Foley sound effects mathematically (100% reliable, 0 server downtime)."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if kind == "whoosh":
        def make_whoosh(t):
            t = np.atleast_1d(t)
            noise = np.random.normal(0, 0.5, len(t))
            # Sharp bell curve envelope
            envelope = np.exp(-((t - 0.5) ** 2) / 0.02)
            frame = noise * envelope
            return np.vstack([frame, frame]).T
        clip = AudioClip(make_whoosh, duration=1.0)
        clip.write_audiofile(output_path, fps=44100, bitrate="192k", logger=None)
        return output_path
    elif kind == "rain" or kind == "static":
        def make_rain(t):
            t = np.atleast_1d(t)
            # Low volume white noise acts as a great base for rain/static ambiance
            noise = np.random.normal(0, 0.1, len(t))
            return np.vstack([noise, noise]).T
        clip = AudioClip(make_rain, duration=5.0)
        clip.write_audiofile(output_path, fps=44100, bitrate="192k", logger=None)
        return output_path
    return None

def download_sfx(query, output_path="assets/sfx.mp3"):
    """
    Downloads a sound effect from the curated library or a fallback.
    """
    query_lower = query.lower()
    
    # 🌟 OFFLINE SYNTHESIS: 100% reliable Foley generation
    if "whoosh" in query_lower or "wind" in query_lower:
        print(f"[Log] Synthesizing '{query_lower}' SFX locally (0 network dependency)...")
        return generate_local_sfx("whoosh", output_path)
    elif "rain" in query_lower or "water" in query_lower or "static" in query_lower:
        print(f"[Log] Synthesizing '{query_lower}' SFX locally...")
        return generate_local_sfx("rain", output_path)
        
    selected_url = None
    
    # Try to find a match in the library
    for key in SFX_LIBRARY:
        if key in query_lower:
            selected_url = SFX_LIBRARY[key]
            break
            
    if not selected_url:
        print(f"[Warning] No SFX found for '{query}', using synthesized fallback (Rain)")
        return generate_local_sfx("rain", output_path)
        
    try:
        print(f"[Log] Downloading SFX: {selected_url}")
        r = requests.get(selected_url, timeout=20, stream=True)
        r.raise_for_status()
        
        # Basic validation: ensure it's not an HTML error page or empty
        if 'text/html' in r.headers.get('Content-Type', ''):
            print(f"[Error] SFX URL returned HTML instead of audio: {selected_url}")
            return generate_local_sfx("rain", output_path)
            
        content = r.content
        if len(content) < 1000: # Less than 1KB is likely not a valid MP3
            print(f"[Error] SFX download is too small to be valid ({len(content)} bytes)")
            return None

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(content)
        return output_path
    except Exception as e:
        print(f"[Error] Failed to download SFX: {e}")
        return None

if __name__ == "__main__":
    # download_background_video("A day on Venus is longer than a year on Venus.")
    print(get_game_assets(3))
