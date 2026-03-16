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
