import os
import time
from datetime import datetime, timedelta
from supabase import create_client, Client

def cleanup_old_videos(supabase: Client, user_id: str):
    """Deletes videos older than 30 minutes in the user's storage folder."""
    bucket_name = 'videos'
    try:
        # List files in the user's folder
        res = supabase.storage.from_(bucket_name).list(user_id)
        if not res:
            return

        now = datetime.utcnow()
        expiry_limit = now - timedelta(hours=1)

        for file in res:
            # Supabase 'list' returns metadata including 'created_at'
            created_at_str = file.get('created_at')
            if created_at_str:
                # Format: 2024-03-20T12:34:56.789123+00:00 or similar
                try:
                    # Strip 'Z' if present and convert to datetime
                    clean_ts = created_at_str.replace('Z', '+00:00')
                    # fromisoformat handles +00:00 but might struggle with some sub-second variants in older python
                    # but usually it's fine for Supabase timestamps.
                    created_at = datetime.fromisoformat(clean_ts).replace(tzinfo=None)
                    if created_at < expiry_limit:
                        file_path = f"{user_id}/{file['name']}"
                        print(f"[Cleanup] Deleting expired video: {file_path}")
                        supabase.storage.from_(bucket_name).remove([file_path])
                except Exception as ex:
                    print(f"[Warning] Failed to parse timestamp {created_at_str}: {ex}")
    except Exception as e:
        print(f"[Warning] Cleanup failed: {e}")

def upload_to_storage(file_path: str, video_id: str, is_video: bool = True) -> str:
    """
    Uploads a file to Supabase Storage and returns the relative storage_path.
    Bucket name: 'videos'
    """
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    user_id = os.getenv("USER_ID")
    if not user_id or user_id == "":
        user_id = "default_user"

    if not supabase_url or not supabase_key:
        print("[Error] Supabase credentials missing for storage upload.")
        return None

    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        bucket_name = 'videos'
        ext = "mp4" if is_video else "jpg"
        content_type = "video/mp4" if is_video else "image/jpeg"
        storage_path = f"{user_id}/{video_id}.{ext}"

        # 1. Run cleanup if it's a video (prevent clutter)
        if is_video:
            cleanup_old_videos(supabase, user_id)

        # 2. Perform upload
        with open(file_path, 'rb') as f:
            supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": content_type, "upsert": "true"}
            )
        
        print(f"[Log] File uploaded to cloud storage: {storage_path}")
        return storage_path

    except Exception as e:
        print(f"[Error] Storage upload failed ({file_path}): {e}")
        return None

def get_public_url(storage_path: str) -> str:
    """Returns the public URL for a file in Supabase Storage."""
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    if not supabase_url:
        return None
    
    # Construct the public URL (Standard Supabase format)
    # https://<project_id>.supabase.co/storage/v1/object/public/<bucket>/<path>
    return f"{supabase_api_url(supabase_url)}/storage/v1/object/public/videos/{storage_path}"

def supabase_api_url(url: str) -> str:
    """Ensures the URL is clean."""
    return url.rstrip('/')
