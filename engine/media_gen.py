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
    print(f"🔍 Searching Pexels for: '{query}'")
    
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
        
    return None

if __name__ == "__main__":
    download_background_video("A day on Venus is longer than a year on Venus.")
