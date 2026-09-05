import os
import json
import requests
import random
import re
import numpy as np
from dotenv import load_dotenv
from engine.comfy_bridge import generate_cinematic_backgrounds

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
JWST_API_KEY = os.getenv("JWST_API_KEY")


# Viral high-retention background types
HIGH_RETENTION_QUERIES = [
    "minecraft parkour", 
    "gta 5 ramp jump", 
    "satisfying sand", 
    "hydraulic press", 
    "kinetic sand", 
    "slime asmr", 
    "subway surfers gameplay", 
    "soap cutting",
    "minecraft dropper",
    "satisfying industrial machine",
    "paint mixing asmr",
    "deep sea satisfying"
]

def extract_keywords(text):
    """
    Simple keyword extraction by removing common words.
    """
    stopwords = {"did", "you", "know", "that", "the", "is", "of", "and", "a", "in", "to", "it", "with", "have", "for", "are", "on", "shocking", "interesting", "fact"}
    words = re.findall(r'\w+', text.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    return keywords[:3] # Return top 3 keywords

def download_background_video(fact_text, fallback_query="nature", output_path="assets/bg.mp4", orientation="portrait", custom_bg=None):
    """
    downloads a background video based on keywords from the fact or custom background media.
    """
    if custom_bg and os.path.exists(custom_bg):
        print(f"[Log] Using CUSTOM background media: {custom_bg}")
        ext = os.path.splitext(custom_bg)[1].lower()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
            try:
                from moviepy.editor import ImageClip
                clip = ImageClip(custom_bg).set_duration(60)
                clip.write_videofile(output_path, fps=30, codec="libx264")
                clip.close()
                return output_path
            except Exception as e:
                print(f"[Warning] Failed to render image background: {e}")
        import shutil
        shutil.copy(custom_bg, output_path)
        return output_path
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
        {"name": "Spider-Man", "query": "spider man pointing meme"},
        {"name": "Grinch", "query": "the grinch funny"},
        {"name": "Thanos", "query": "thanos meme"},
        {"name": "Batman", "query": "batman funny"},
        {"name": "Skibidi", "query": "skibidi toilet"},
        {"name": "Minion", "query": "funny minion"},
        {"name": "Rick Sanchez", "query": "rick and morty rick"},
        {"name": "Walter White", "query": "breaking bad walter white"}
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

def fetch_jwst_images(num_images=5, output_dir="assets/jwst"):
    """
    Fetches random high-quality images from the James Webb Space Telescope API.
    Implements repetition avoidance via a local history file.
    """
    if not JWST_API_KEY:
        print("[Error] JWST_API_KEY is missing in .env")
        return []

    os.makedirs(output_dir, exist_ok=True)
    history_file = os.path.join(output_dir, "history.json")
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except:
            history = []

    # JWESTAPI.com endpoint
    url = "https://api.jwstapi.com/all/type/jpg"
    headers = {"X-API-KEY": JWST_API_KEY}
    
    try:
        # 1. Get total count or a large page to randomize
        print("[Log] Fetching JWST image list...")
        # Note: We use a random page to get different images each time
        random_page = random.randint(1, 10)
        r = requests.get(f"{url}?page={random_page}&perPage=50", headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        items = data.get("body", [])
        if not items:
            return []

        # Filter out already seen images
        available = [item for item in items if item.get("id") not in history]
        
        # If we ran out of new images, clear history and restart
        if len(available) < num_images:
            history = []
            available = items

        selected = random.sample(available, min(num_images, len(available)))
        downloaded_paths = []

        for i, item in enumerate(selected):
            img_id = item.get("id")
            img_url = item.get("location")
            if not img_url: continue

            ext = os.path.splitext(img_url)[1] or ".jpg"
            path = os.path.join(output_dir, f"jwst_{img_id}{ext}")
            
            if not os.path.exists(path):
                print(f"[Log] Downloading JWST Image: {img_url}")
                img_data = requests.get(img_url, timeout=30).content
                with open(path, "wb") as f:
                    f.write(img_data)
            
            downloaded_paths.append(path)
            history.append(img_id)

        # Update history (keep last 200 IDs)
        with open(history_file, "w") as f:
            json.dump(history[-200:], f)

        return downloaded_paths

    except Exception as e:
        print(f"[Error] JWST Fetch failed: {e}")
        return []

def is_url(path_or_url):
    """Returns True if the input is an HTTP/HTTPS URL."""
    if not isinstance(path_or_url, str):
        return False
    clean = path_or_url.strip()
    return clean.startswith("http://") or clean.startswith("https://") or clean.startswith("www.")

def download_source_video_from_url(url, output_dir, filename="source_video.mp4"):
    """
    Downloads a video from a URL (YouTube, Twitch, Twitter, TikTok, direct video links, etc.)
    using yt-dlp or direct requests streaming fallback. Caches downloaded files to prevent re-downloading.
    Returns path to the downloaded video file.
    """
    import hashlib
    import shutil

    url = url.strip()
    if url.startswith("www."):
        url = "https://" + url

    os.makedirs(output_dir, exist_ok=True)
    
    # 🟢 Global URL cache directory
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    global_cache_dir = os.path.join("sessions", "url_cache")
    os.makedirs(global_cache_dir, exist_ok=True)
    cached_video_path = os.path.join(global_cache_dir, f"{url_hash}.mp4")
    target_path = os.path.join(output_dir, filename)

    # If already cached globally, copy and return immediately
    if os.path.exists(cached_video_path) and os.path.getsize(cached_video_path) > 1024:
        print(f"[Log] Found cached video for URL: '{url}'")
        print(f"[Log] Reusing cached file: {cached_video_path}")
        if os.path.abspath(cached_video_path) != os.path.abspath(target_path):
            shutil.copy2(cached_video_path, target_path)
        return target_path

    print(f"[Log] Downloading video from URL: {url}")
    
    # 1. Try yt-dlp first (handles YouTube, Twitch, Vimeo, Twitter, TikTok, and direct stream links)
    try:
        import yt_dlp
        
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(global_cache_dir, f'{url_hash}.%(ext)s'),
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': True,
            'nocheckcertificate': True,
            'writeinfojson': True,  # Save chapters + metadata alongside video
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            base, _ = os.path.splitext(downloaded_file)
            possible_mp4 = base + ".mp4"
            if os.path.exists(possible_mp4):
                final_file = possible_mp4
            elif os.path.exists(downloaded_file):
                final_file = downloaded_file
            else:
                files = [os.path.join(global_cache_dir, f) for f in os.listdir(global_cache_dir) if f.startswith(url_hash)]
                if files:
                    final_file = files[0]
                else:
                    raise FileNotFoundError("yt-dlp completed but output file was not found.")

            print(f"[Log] Successfully downloaded video via yt-dlp: {final_file}")
            # Ensure cached file is copied to session target_path
            if os.path.abspath(final_file) != os.path.abspath(target_path):
                shutil.copy2(final_file, target_path)
            return target_path

    except Exception as e:
        print(f"[Warning] yt-dlp download failed: {e}. Attempting direct HTTP fallback...")
        
    # 2. Fallback to direct HTTP request streaming if yt-dlp failed (e.g. direct mp4 link)
    try:
        import requests
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(cached_video_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"[Log] Successfully downloaded video via direct HTTP fallback: {cached_video_path}")
        if os.path.abspath(cached_video_path) != os.path.abspath(target_path):
            shutil.copy2(cached_video_path, target_path)
        return target_path
    except Exception as e2:
        raise RuntimeError(f"Failed to download video from URL '{url}': {e2}")


def get_chapters_json_path(url, output_dir=None):
    """
    Returns the path to the info.json saved by yt-dlp for a given URL, or None.
    This file contains chapter markers, description, and full metadata.
    """
    import hashlib
    url_hash = hashlib.md5(url.strip().encode('utf-8')).hexdigest()
    cache_dir = os.path.join("sessions", "url_cache")
    info_path = os.path.join(cache_dir, f"{url_hash}.info.json")
    if os.path.exists(info_path):
        return info_path
    if output_dir:
        alt = os.path.join(output_dir, "video_info.json")
        if os.path.exists(alt):
            return alt
    return None


BROLL_QUERIES = [
    "minecraft parkour",
    "satisfying sand cutting",
    "soap cutting asmr",
    "kinetic sand",
    "hydraulic press satisfying",
    "gta 5 stunt",
    "subway surfers gameplay",
    "paint mixing asmr",
    "slime satisfying",
    "deep sea creatures",
]

def download_broll_clips(output_dir="assets/broll", count=8, force_refresh=False):
    """
    Downloads a curated set of high-retention B-roll clips from Pexels.
    Clips are cached permanently in assets/broll/ and reused across runs.
    """
    os.makedirs(output_dir, exist_ok=True)
    existing = [f for f in os.listdir(output_dir) if f.endswith('.mp4')]

    if len(existing) >= count and not force_refresh:
        print(f"[Log] B-roll library ready: {len(existing)} clips in {output_dir}")
        return [os.path.join(output_dir, f) for f in existing[:count]]

    if not PEXELS_API_KEY:
        print("[Warning] PEXELS_API_KEY not set — B-roll download skipped.")
        return []

    print(f"[Log] Downloading {count} B-roll clips for cutaway library...")
    downloaded = []
    queries = (BROLL_QUERIES * 3)[:count]  # Repeat list if fewer queries than count

    for i, query in enumerate(queries):
        safe_q = re.sub(r'[^a-zA-Z0-9]', '_', query).lower()
        out_path = os.path.join(output_dir, f"broll_{safe_q}.mp4")
        if os.path.exists(out_path):
            downloaded.append(out_path)
            continue

        try:
            url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=portrait"
            headers = {"Authorization": PEXELS_API_KEY}
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            videos = r.json().get("videos", [])
            if not videos:
                continue
            video_data = videos[0]
            video_files = video_data.get("video_files", [])
            best_link = next(
                (vf["link"] for vf in video_files if vf.get("quality") == "hd" and vf.get("height", 0) >= 720),
                video_files[0].get("link") if video_files else None
            )
            if not best_link:
                continue
            content = requests.get(best_link, timeout=30).content
            with open(out_path, "wb") as f:
                f.write(content)
            downloaded.append(out_path)
            print(f"  [{i+1}/{count}] Downloaded B-roll: {query}")
        except Exception as e:
            print(f"  [Warning] B-roll download failed for '{query}': {e}")

    print(f"[Log] B-roll library: {len(downloaded)} clips ready in {output_dir}")
    return downloaded



if __name__ == "__main__":
    # download_background_video("A day on Venus is longer than a year on Venus.")
    print(get_game_assets(3))
