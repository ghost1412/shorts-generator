import os
import requests
import random
import re
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

def extract_keywords(text):
    """
    Simple keyword extraction by removing common words.
    """
    stopwords = {"did", "you", "know", "that", "the", "is", "of", "and", "a", "in", "to", "it", "with", "have", "for", "are", "on", "shocking", "interesting", "fact"}
    words = re.findall(r'\w+', text.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    return keywords[:3] # Return top 3 keywords

def download_background_video(fact_text, fallback_query="nature", output_path="assets/bg.mp4"):
    """
    Downloads a background video based on keywords from the fact.
    """
    keywords = extract_keywords(fact_text)
    query = " ".join(keywords) if keywords else fallback_query
    print(f"[Log] Searching Pexels for: '{query}'")
    
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait"
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
            return output_path
            
    except Exception as e:
        print(f"Error downloading video: {e}")
        
def download_image(query, output_path="assets/obj.png"):
    """
    Downloads an image based on a query from Pexels.
    """
    print(f"[Log] Searching Pexels Image for: '{query}'")
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
        {"name": "Pepe", "query": "pepe the frog"}
    ]
    
    selected_target = random.choice(targets) if not target_query else {"name": "Object", "query": target_query}
    assets["target_name"] = selected_target["name"]
    
    # Download Target
    target_path = download_image(selected_target["query"], output_path=os.path.join(output_dir, f"target_{random.randint(100,999)}.png"))
    assets["target_path"] = target_path
    
    # 2. Get Similar Distractors (Sketch faces/Portraits)
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
                if not isinstance(assets["objects"], list):
                    assets["objects"] = []
                assets["objects"].append(obj_path)
    except Exception as e:
        print(f"Error downloading distractors: {e}")
            
    return assets

if __name__ == "__main__":
    # download_background_video("A day on Venus is longer than a year on Venus.")
    print(get_game_assets(3))
