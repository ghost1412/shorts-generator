import os
import requests
import json
import re
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

def generate_pinterest_metadata(content_info, mode="FACTS", category="science"):
    """
    Generates Pinterest-optimized metadata focusing on long-term search SEO.
    Pinterest metadata prioritizes keywords in titles and clear, helpful descriptions.
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    if mode == "FACTS":
        input_text = "\n".join([f"- {f['fact']}" for f in content_info])
        task_desc = f"interesting facts about {category}."
    elif mode == "FIND_IT":
        input_text = f"Target: {content_info['target_name']}"
        task_desc = f"a visual puzzle/game to find the {content_info['target_name']}."
    elif mode == "RIDDLE":
        input_text = str(content_info)
        task_desc = f"a brain-teasing riddle about {category}."
    elif mode == "QUOTE":
        input_text = str(content_info)
        task_desc = f"a deep motivational quote about {category}."
    else:
        input_text = str(content_info)
        task_desc = f"a video about {category}."

    prompt = f"""You are a Pinterest SEO Expert. 
Generate a search-optimized title and a detailed, helpful description for a Pin about {task_desc}:
{input_text}

PINTEREST SEO RULES:
1. Title: Must be keyword-rich and descriptive (max 100 chars). 
   - E.g., "3 Mind-Blowing Science Facts You Didn't Know" or "Can You Find the Hidden Cat? Visual Puzzle".
2. Description: 
   - Write a compelling 2-3 sentence summary that naturally includes keywords.
   - Include a Call to Action (e.g., "Check out our channel for more!").
   - Include 5-10 niche-specific hashtags (e.g., #sciencefacts #education #trivia).
3. Pinterest does not use a separate 'tags' field like YouTube, so include them in the description.

Format as JSON ONLY:
{{
  "title": "...",
  "description": "..."
}}
"""
    from engine.script_gen import get_llm_response, robust_json_parse

    for attempt in range(2):
        try:
            output = get_llm_response(prompt, temperature=0.7, max_tokens=800)
            metadata = robust_json_parse(output)
            if not metadata or not metadata.get("title"):
                raise ValueError("Invalid Pinterest metadata")
            return metadata
        except Exception as e:
            print(f"[Warning] Pinterest metadata attempt {attempt+1} failed: {e}")
    
    # Generic Fallback
    return {
        "title": f"Amazing {category.title()} Challenge! ✨",
        "description": f"Don't miss this incredible {category} video. Like and follow for more daily inspiration! #pinterest #viral #{category}"
    }
def generate_expanded_music_prompt(user_prompt):
    """
    Enriches a simple user music description into a highly detailed, professional prompt
    for audio generation models like Stable Audio or AudioLDM.
    """
    from engine.script_gen import get_llm_response, robust_json_parse
    
    system_instruction = """You are a professional Music Producer and Audio Engineering Prompt Expert.
Your job is to expand a simple, basic music or sound effect query into a highly descriptive, detailed prompt suitable for professional Text-to-Audio (T2A) models.

Respond ONLY with a JSON object in this format:
{
  "expanded_prompt": "<expanded prompt here>"
}

Guidelines:
1. Describe the genre, mood, tempo (BPM), and primary instruments (e.g. Rhodes piano, sub-bass, sidechained drums, synthesized pads).
2. If the input specifies vocals, singing, or voice, put the vocals front-and-center in the description (e.g., "clear female lead vocals singing", "expressive vocals") and make sure they are prominent.
3. Use professional production and audio quality terms (e.g. "warm vinyl crackle", "reverb-drenched", "analog warmth", "low-pass filter", "high-fidelity studio recording").
4. Avoid vague marketing buzzwords like "amazing", "beautiful", "epic". Describe the sonic texture instead.
5. Keep the output relatively concise but dense with descriptive words (max 60-70 words).

Examples:
- Input: "lofi hiphop"
  Output: {"expanded_prompt": "chill lofi hip hop track, warm dusty rhodes keys, sidechained boom-bap drum loop, nostalgic vinyl crackle, mellow sub-bass, 85 bpm, relaxed cozy mood, studio master"}
- Input: "heavy rock"
  Output: {"expanded_prompt": "energetic hard rock, distorted electric guitar riff, punchy acoustic drums, heavy driving bassline, high energy, fast tempo, garage rock style, raw stereo recording"}
- Input: "pop song with female vocals"
  Output: {"expanded_prompt": "clear female lead vocals singing a melodic line, upbeat pop track, shimmering electric piano, driving drums, warm analog bassline, 120 bpm, polished radio production, studio master"}
"""
    
    full_prompt = f"{system_instruction}\n\nInput: \"{user_prompt}\"\nOutput:"
    
    try:
        output = get_llm_response(
            full_prompt,
            system_prompt="You are a professional music prompt engineer. Output raw JSON only.",
            temperature=0.7,
            max_tokens=4000
        )
        data = robust_json_parse(output)
        if data and "expanded_prompt" in data:
            expanded = data["expanded_prompt"].strip()
            print(f"[SocialGen] Expanded prompt: '{user_prompt}' -> '{expanded}'")
            return expanded
        
        # Fallback if parse failed
        cleaned = output.strip().strip('"').strip("'")
        if cleaned:
            return cleaned
        return user_prompt
    except Exception as e:
        print(f"[Warning] Prompt expansion failed: {e}. Using original user prompt.")
        return user_prompt

def generate_viral_metadata(content_info, mode="FACTS", category="science"):
    """
    Generates viral, humorous metadata for YouTube Shorts as a "Channel Manager".
    """
    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    model = "meta-llama/Llama-3.1-8B-Instruct"
    
    if mode == "FACTS":
        input_text = "\n".join([f"- {f['fact']}" for f in content_info]) if isinstance(content_info, list) else str(content_info)
        task_desc = f"a '2 Truths and 1 Lie' challenge about {category}."
    elif mode == "FIND_IT":
        target = content_info.get('target_name', 'target') if isinstance(content_info, dict) else 'target'
        input_text = f"Target: {target}"
        task_desc = f"a 'Find the {target}' visual challenge game about {category}."
    elif mode == "RIDDLE":
        input_text = str(content_info)
        task_desc = f"a brain-teasing lateral-thinking riddle about {category}."
    elif mode == "EXPLAINER":
        input_text = str(content_info)
        task_desc = f"an educational visualization and explainer about {category}."
    elif mode == "TRIVIA":
        input_text = str(content_info)
        task_desc = f"a trivia quiz challenge about {category}."
    elif mode == "QUOTE":
        input_text = str(content_info)
        task_desc = f"a deep motivational quote about {category}."
    elif mode == "WYR":
        input_text = str(content_info)
        task_desc = f"a 'Would You Rather' dilemma about {category}."
    elif mode.startswith("NEWS"):
        input_text = str(content_info)
        task_desc = f"a news report about {category}."
    elif mode == "JWST":
        input_text = str(content_info)
        task_desc = "a space exploration video featuring James Webb Telescope images."
    elif mode == "MUSIC":
        input_text = str(content_info)
        task_desc = "a viral AI generated music video showcase."
    elif category == "gaming":
        if isinstance(content_info, dict):
            game_name = content_info.get("game_name", "Game")
            scene = content_info.get("scene_description", "")
            input_text = f"Game: {game_name}\nHighlight: {scene}"
            task_desc = f"a gaming highlight clip of {game_name}."
        else:
            input_text = str(content_info)
            task_desc = "a gaming highlight clip."
    else:
        input_text = str(content_info)
        task_desc = f"a video about {category}."

    prompt = f"""You are a top-tier YouTube Shorts Growth Expert and Channel Manager. 
Generate a VIRAL title, high-retention description, and trending SEO tags for {task_desc}:
Content Summary: {input_text}

CRITICAL SEO RULES:
1. Title: Must be pattern-interrupting, under 60 chars, and strictly relevant to the actual content:
   - For RIDDLE: Use brain-teaser hooks like "99% FAIL THIS RIDDLE! 🧠", "CAN YOU SOLVE THIS? 💡", or "ONLY A GENIUS GETS THIS! 🤯".
   - For EXPLAINER / SCIENCE / MATH: Use curiosity hooks like "How [Topic] ACTUALLY Works! 🤯" or "The Secret of [Topic] ⚡".
   - For FACTS / CHALLENGE: Use "99% MISS THIS! 🛑" or "Can You Spot the Lie? 🤯".
   - For NEWS: Start with "BREAKING: [Topic] 🚨" or "DEVELOPING: [Topic] 🚨".
   - For MUSIC: Use "Rate this track 1-10! 🎧" or "This beat goes hard! 🔥".
   - For GAMING: Include the specific game name and highlight moment (e.g., "[Game Name] Final Boss Fight! ⚔️").

2. Description: 
   - First line must be a high-retention CTA asking viewers a relevant question about the video (e.g. for RIDDLE: "Can you guess the answer before the timer ends? Comment your answer below! 👇").
   - Include 2-3 short paragraphs: The Hook, The Details, and a Call to Action (like/subscribe/comment).
   - Use emojis strategically.
   - Include relevant hashtags at the bottom: #shorts #trending #viral + 3 specific to the category (e.g., #{category} #riddle #brainteaser for RIDDLES, or #{category} #science #education for EXPLAINER).

3. Tags: 15-20 highly relevant SEO keywords matching the category and content topic.

Format as JSON ONLY:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}
"""


    def clean_json_string(s):
        # Remove control characters that break JSON
        s_clean = str(re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', s))
        # Try to find the JSON block
        start = s_clean.find("{")
        end = s_clean.rfind("}") + 1
        if start != -1 and end != 0:
            return s_clean[start:end]
        return s_clean

    from engine.script_gen import get_llm_response, robust_json_parse

    for attempt in range(2): # 🟢 Reduced to 2 attempts for faster failover
        try:
            temp = 0.7 + (attempt * 0.1)
            # 🟢 Short timeout (30s) for metadata since it's a small JSON
            output = get_llm_response(prompt, temperature=temp, max_tokens=1000, timeout=30)
            metadata = robust_json_parse(output)
            
            # Validation
            if not metadata or not isinstance(metadata, dict) or not metadata.get("title"):
                raise ValueError("Empty or invalid title in LLM response")
                
            # YouTube title limit is 100
            metadata["title"] = metadata["title"][:95]
            return metadata
            
        except Exception as e:
            print(f"[Warning] Metadata attempt {attempt+1} failed ({e}).")
            if attempt == 2:
                print(f"[Log] Metadata API failed after 3 attempts. Using generic fallback.")
        
    # Improved fallback based on mode
    if mode == "FIND_IT":
        target = content_info.get('target_name', 'Meme').upper()
        return {
            "title": f"WHERE IS {target}?!! 🕵️‍♂️ (99% FAIL) #shorts #challenge",
            "description": f"Can you spot the {target} in 5 seconds? Comment 'DONE' or you owe me a sub! 🗿\n\n#game #findit #trending",
            "tags": ["shorts", "challenge", "game", "meme", "trending", target.lower()]
        }
    
    if mode == "STORY":
        return {
            "title": f"You won't believe this STORY! 😱 #shorts #storytime",
            "description": f"This is one of the most incredible stories I've ever heard. Stay until the end for the twist! 🗿\n\n#storytelling #mystery #trending",
            "tags": [category, "shorts", "story", "mystery", "storytime", "wow"]
        }

    if mode.startswith("NEWS"):
        return {
            "title": f"BREAKING NEWS: {category.upper()} UPDATE! 🚨 #shorts #news",
            "description": f"New developing story. Make sure you're following for more daily updates on this! 🚨\n\n#breakingnews #latest #updates",
            "tags": [category, "shorts", "news", "breaking", "latest", "update"]
        }
    
    if mode == "MUSIC":
        return {
            "title": "This AI music is out of this world! 🎧 #shorts #music",
            "description": "Check out this incredible AI generated music track! Let me know what you think in the comments. 🗿\n\n#aimusic #beats #trending",
            "tags": ["music", "aimusic", "shorts", "beats", "trending", category]
        }
    
    # Default for FACTS or unknown
    return {
        "title": f"The SHOCKING truth! 😱 #shorts #facts",
        "description": f"Can you spot the lie? One of these is a fake! \n\n#trivia #challenge #interesting",
        "tags": [category, "shorts", "challenge", "facts", "trivia", "didyouknow"]
    }

class YouTubeUploader:
    def __init__(self, secrets_file="client_secrets.json", token_file="token.json"):
        self.secrets_file = secrets_file
        self.token_file = token_file
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.youtube = None

    def authenticate(self, creds_dict=None):
        """
        Authenticates with YouTube API using either a creds_dict (SaaS mode)
        or local json files (test/local mode).
        """
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = None

        # 1. SAAS MODE: Use credentials provided from Supabase
        if creds_dict and all(k in creds_dict for k in ["client_id", "client_secret", "refresh_token"]):
            print(f"[Log] Authenticating with user-provided credentials (BYOK Mode)")
            creds = Credentials(
                None,  # access_token is None, will be refreshed
                refresh_token=creds_dict["refresh_token"],
                client_id=creds_dict["client_id"],
                client_secret=creds_dict["client_secret"],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=self.scopes
            )
        
        # 2. LOCAL/LEGACY MODE: Use files
        if not creds:
            if os.path.exists(self.token_file):
                try:
                    creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
                except Exception as e:
                    print(f"[Log] Could not load existing token: {e}")

        # Refresh if needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[Log] Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                # Manual flow as a last resort
                if not os.path.exists(self.secrets_file):
                    print(f"[Error] No valid credentials found for YouTube upload.")
                    return False
                
                try:
                    from google_auth_oauthlib.flow import InstalledAppFlow
                    flow = InstalledAppFlow.from_client_secrets_file(self.secrets_file, self.scopes)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"[Error] Manual authentication failed: {e}")
                    return False
                    print(f"[Error] Auth failed (Browser might be missing): {e}")
                    print("[Log] Tip: If running on GitHub, make sure to provide GOOGLE_YOUTUBE_TOKEN secret.")
                    return False

            # Save the credentials for the next run
            with open(self.token_file, 'w', encoding="utf-8") as token:
                token.write(creds.to_json())

        try:
            self.youtube = build("youtube", "v3", credentials=creds)
            return True
        except Exception as e:
            print(f"[Error] YouTube API build failed: {e}")
            return False

    def upload_video(self, file_path, title, description, tags, category_id="27", privacy="public"):
        if not self.youtube:
            print("[Error] Not authenticated.")
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
        
        print(f"[Log] Uploading {file_path} as {privacy}...")
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

        print(f"[Log] Upload successful! Video ID: {response.get('id')}")
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
            print("[Log] Instagram credentials missing. Skipping IG upload.")
            return None

        print(f"[Log] Preparing Instagram Reel (Temporary Hosting)...")
        
        try:
            # Step 0: Upload to Supabase Storage (Stable Hosting)
            from engine.storage import upload_to_storage, get_public_url
            import uuid
            
            print(f"[Log] Uploading to Supabase Storage for stable hosting...")
            temp_id = str(uuid.uuid4())[:8]
            storage_path = upload_to_storage(video_file_path, f"ig_temp_{temp_id}")
            
            if not storage_path:
                print(f"[Error] Storage upload failed. Falling back to file.io (unreliable)...")
                with open(video_file_path, "rb") as f:
                    host_res = requests.post("https://file.io", files={"file": f}, timeout=60)
                    if host_res.ok:
                        video_url = host_res.json().get("link")
                    else:
                        print(f"[Error] file.io fallback also failed.")
                        return None
            else:
                video_url = get_public_url(storage_path)
            
            if not video_url:
                print(f"[Error] No public URL generated for Instagram.")
                return None

            print(f"[Log] Stable URL generated: {video_url}")

            # Step 1: Create Media Container
            container_url = f"{self.base_url}/{self.page_id}/media"
            payload = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": self.access_token
            }
            
            print(f"[Log] Creating Instagram Media Container...")
            res = requests.post(container_url, data=payload, timeout=30)
            print(f"[Log] Container Creation Status: {res.status_code}")
            
            if not res.ok:
                print(f"[Error] Instagram Container Check failed: {res.text}")
                return None

            try:
                container_data = res.json()
            except Exception as je:
                print(f"[Error] Instagram JSON decode error (Step 1): {je}. Raw: {res.text}")
                return None
                
            container_id = container_data.get("id")
            print(f"[Log] Container created: {container_id}. Publishing (can take 30-60s)...")
            
            # Step 2: Publish
            publish_url = f"{self.base_url}/{self.page_id}/media_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": self.access_token
            }
            pub_res = requests.post(publish_url, data=publish_payload)
            
            if not pub_res.ok:
                print(f"[Error] Instagram Publish failed: {pub_res.text}")
                pub_res.raise_for_status()
            
            pub_data = pub_res.json()
            print("[Log] Successfully published to Instagram!")
            return pub_data
            
        except Exception as e:
            print(f"[Error] Instagram Error: {e}")
            return None

class PinterestUploader:
    """
    Handles video uploads to Pinterest using REST API v5.
    Requires: PINTEREST_ACCESS_TOKEN and PINTEREST_BOARD_ID
    """
    def __init__(self):
        self.access_token = os.getenv("PINTEREST_ACCESS_TOKEN")
        self.board_id = os.getenv("PINTEREST_BOARD_ID")
        self.base_url = "https://api.pinterest.com/v5"

    def upload_video(self, video_file_path, title, description, link=None):
        if not self.access_token or not self.board_id:
            print("[Log] Pinterest credentials missing. Skipping Pinterest upload.")
            return None

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        try:
            # Step 1: Register Media
            print(f"[Log] Registering Pinterest Media...")
            reg_res = requests.post(
                f"{self.base_url}/media",
                json={"media_type": "video"},
                headers=headers,
                timeout=30
            )
            reg_res.raise_for_status()
            reg_data = reg_res.json()
            
            media_id = reg_data["media_id"]
            upload_url = reg_data["upload_url"]
            upload_params = reg_data["upload_parameters"]

            # Step 2: Upload to S3
            print(f"[Log] Uploading video to Pinterest S3 storage...")
            with open(video_file_path, "rb") as f:
                upload_res = requests.post(
                    upload_url,
                    data=upload_params,
                    files={"file": f},
                    timeout=120
                )
            
            if upload_res.status_code not in [201, 204]:
                print(f"[Error] Pinterest S3 upload failed: {upload_res.text}")
                return None

            # Step 3: Poll for Media Status (Must be 'succeeded' before creating Pin)
            import time
            print(f"[Log] Waiting for Pinterest to process video (media_id: {media_id})...")
            for _ in range(10): # Max 100s wait
                status_res = requests.get(f"{self.base_url}/media/{media_id}", headers=headers)
                if status_res.ok and status_res.json().get("status") == "succeeded":
                    print("[Log] Media processing complete.")
                    break
                time.sleep(10)
            else:
                print("[Warning] Media processing timed out. Pin creation might fail.")

            # Step 4: Create Pin
            pin_payload = {
                "title": title[:100],
                "description": description[:500],
                "board_id": self.board_id,
                "media_source": {
                    "source_type": "video_id",
                    "media_id": media_id
                }
            }
            if link:
                pin_payload["link"] = link

            print(f"[Log] Creating Pinterest Pin...")
            pin_res = requests.post(
                f"{self.base_url}/pins",
                json=pin_payload,
                headers=headers,
                timeout=30
            )
            pin_res.raise_for_status()
            
            print("[Log] Successfully created Pinterest Pin!")
            return pin_res.json()

        except Exception as e:
            print(f"[Error] Pinterest Upload Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[Log] Response: {e.response.text}")
            return None
