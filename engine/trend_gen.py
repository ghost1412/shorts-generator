import requests
import xml.etree.ElementTree as ET
import random

def get_trending_topics(geo="US"):
    """
    Fetches the latest trending searches from Google Trends RSS.
    Returns a list of titles (topics).
    """
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 🟢 Use namespace handling for ht:approx_traffic
        namespaces = {'ht': 'https://trends.google.com/trending/rss'}
        root = ET.fromstring(response.text)
        
        topics = []
        for item in root.findall(".//item"):
            title = item.find("title").text
            approx_traffic = item.find("ht:approx_traffic", namespaces)
            if approx_traffic is not None:
                traffic = approx_traffic.text
            else:
                traffic = "Unknown"
            
            topics.append({
                "title": title,
                "traffic": traffic
            })
            
        print(f"[Log] Found {len(topics)} trending topics for {geo}.")
        return topics
    except Exception as e:
        print(f"[Error] Failed to fetch trends: {e}")
        return []

def get_random_trend(geo="US"):
    topics = get_trending_topics(geo)
    if not topics: return None
    # Pick one of the top 10 trends randomly
    return random.choice(topics[:10])

if __name__ == "__main__":
    trend = get_random_trend()
    print(f"Selected Trend: {trend}")
