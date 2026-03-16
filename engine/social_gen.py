import os
import requests
import json
from dotenv import load_dotenv
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

load_dotenv()
HF_API_KEY = os.getenv("HF_API_KEY")

def generate_viral_metadata(facts_list, category="science"):
    """
    Generates viral metadata for YouTube Shorts using LLM.
    Returns: { "title": str, "description": str, "tags": list }
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    model = "meta-llama/Llama-3.2-1B-Instruct"
    facts_text = "\n".join([f"- {f['fact']}" for f in facts_list])
    
    prompt = f"""You are a viral YouTube Shorts creator. 
Generate a title, description, and tags for a video about these 3 facts (one is a lie):
{facts_text}

Video Format: Interactive "2 Truths and 1 Lie" challenge.
Requirements:
1. Title: Catchy, under 50 characters, includes emojis, mentions the challenge.
2. Description: Engaging, includes timestamps for each fact, hashtags like #shorts #challenge #facts.
3. Tags: 10 relevant SEO tags.

Format as JSON ONLY:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        output = response.json()["choices"][0]["message"]["content"]
        
        start = output.find("{")
        end = output.rfind("}") + 1
        metadata = json.loads(output[start:end])
        return metadata
    except Exception as e:
        print(f"💡 Metadata API failed ({e}). Using generic viral metadata.")
        
    return {
        "title": f"The SHOCKING truth about {category.upper()}! 😱 #shorts",
        "description": f"Can you spot the lie? One of these 3 {category} facts is a fake! \n\n#trivia #challenge #interesting",
        "tags": [category, "shorts", "challenge", "facts", "trivia", "didyouknow"]
    }

class YouTubeUploader:
    def __init__(self, secrets_file="client_secrets.json", token_file="token.json"):
        self.secrets_file = secrets_file
        self.token_file = token_file
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.youtube = None

    def authenticate(self):
        creds = None
        # token.json stores the user's access and refresh tokens
        if os.path.exists(self.token_file):
            try:
                from google.oauth2.credentials import Credentials
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            except Exception as e:
                print(f"💡 Could not load existing token: {e}")

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"💡 Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.secrets_file):
                    print(f"❌ Error: {self.secrets_file} not found and no valid token available.")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.secrets_file, self.scopes)
                    # This will attempt to open a browser
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"❌ Auth failed (Browser might be missing): {e}")
                    print("💡 Tip: If running on GitHub, make sure to provide GOOGLE_YOUTUBE_TOKEN secret.")
                    return False

            # Save the credentials for the next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

        try:
            self.youtube = build("youtube", "v3", credentials=creds)
            return True
        except Exception as e:
            print(f"❌ YouTube API build failed: {e}")
            return False

    def upload_video(self, file_path, title, description, tags, category_id="27", privacy="private"):
        if not self.youtube:
            print("❌ Not authenticated.")
            return None

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        
        print(f"🚀 Uploading {file_path} as {privacy}...")
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  Progress: {int(status.progress() * 100)}%")

        print(f"✅ Upload successful! Video ID: {response.get('id')}")
        return response.get("id")

class InstagramUploader:
    """
    Handles uploads to Instagram Business using the Graph API.
    Requires: FACEBOOK_PAGE_ID and INSTAGRAM_ACCESS_TOKEN
    """
    def __init__(self):
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.base_url = "https://graph.facebook.com/v19.0"

    def upload_reel(self, video_file_path, caption):
        """
        Instagram requires the video to be publicly hosted.
        We use file.io as a temporary host for the Instagram API to pull from.
        """
        if not self.page_id or not self.access_token:
            print("💡 Instagram credentials missing. Skipping IG upload.")
            return None

        print(f"📸 Preparing Instagram Reel (Temporary Hosting)...")
        
        try:
            # Step 0: Upload to temporary host
            with open(video_file_path, "rb") as f:
                host_res = requests.post("https://file.io", files={"file": f})
                host_res.raise_for_status()
                video_url = host_res.json().get("link")
            
            print(f"✅ Temporary URL generated: {video_url}")

            # Step 1: Create Media Container
            container_url = f"{self.base_url}/{self.page_id}/media"
            payload = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": self.access_token
            }
            
            res = requests.post(container_url, data=payload)
            res.raise_for_status()
            container_id = res.json().get("id")
            
            print(f"✅ Container created: {container_id}. Publishing (can take 30-60s)...")
            
            # Step 2: Publish
            publish_url = f"{self.base_url}/{self.page_id}/media_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": self.access_token
            }
            pub_res = requests.post(publish_url, data=publish_payload)
            pub_res.raise_for_status()
            
            print("🚀 Successfully published to Instagram!")
            return pub_res.json()
            
        except Exception as e:
            print(f"❌ Instagram Error: {e}")
            return None
