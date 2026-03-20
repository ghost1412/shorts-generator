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
        expiry_limit = now - timedelta(minutes=30)

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

def upload_video_to_storage(file_path: str, video_id: str) -> tuple:
    """
    Uploads a video to Supabase Storage and returns (storage_path, signed_url).
    Bucket name: 'videos'
    """
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    user_id = os.getenv("USER_ID", "default_user")

    if not supabase_url or not supabase_key:
        print("[Error] Supabase credentials missing for storage upload.")
        return None, None

    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        bucket_name = 'videos'
        storage_path = f"{user_id}/{video_id}.mp4"

        # 1. Run cleanup first to keep bucket clean
        cleanup_old_videos(supabase, user_id)

        # 2. Perform upload
        with open(file_path, 'rb') as f:
            supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": "video/mp4"}
            )
        
        # 3. Get INITIAL SIGNED URL (30-minute expiry)
        signed_url_res = supabase.storage.from_(bucket_name).create_signed_url(
            path=storage_path,
            expires_in=1800
        )
        
        signed_url = None
        if isinstance(signed_url_res, dict):
            signed_url = signed_url_res.get('signedURL') or signed_url_res.get('signed_url')
        else:
            signed_url = str(signed_url_res)

        print(f"[Log] Video uploaded to cloud storage: {storage_path}")
        return storage_path, signed_url

    except Exception as e:
        print(f"[Error] Storage upload failed: {e}")
        return None, None
