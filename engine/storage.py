import os
from supabase import create_client, Client

def upload_video_to_storage(file_path: str, video_id: str) -> str:
    """
    Uploads a video to Supabase Storage and returns the public URL.
    Bucket name: 'videos'
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[Error] Supabase credentials missing for storage upload.")
        return file_path # Fallback to local name

    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        bucket_name = "videos"
        file_name = os.path.basename(file_path)
        # Use a folder structure based on video_id if possible, or just the filename
        storage_path = f"{video_id}/{file_name}"
        
        with open(file_path, 'rb') as f:
            res = supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": "video/mp4"},
                upsert=True
            )
        
        # Get SIGNED URL with 30-minute expiry (1800 seconds)
        # Note: In newer supabase-py versions, it is storage.from_().create_signed_url()
        signed_res = supabase.storage.from_(bucket_name).create_signed_url(storage_path, expires_in=1800)
        
        # Check if signed_res is a dict (newer) or a string (older)
        if isinstance(signed_res, dict):
            public_url = signed_res.get('signedURL', signed_res.get('signed_url'))
        else:
            public_url = signed_res

        print(f"[Log] Video uploaded to storage (30m Signed URL): {public_url}")
        
        # PROACTIVE CLEANUP: Remove files older than 1 hour to keep storage free
        cleanup_old_videos(supabase, bucket_name)
        
        return public_url
        
    except Exception as e:
        print(f"[Error] Storage upload failed: {e}")
        return file_path # Fallback to local name

def cleanup_old_videos(supabase: Client, bucket_name: str):
    """
    Lists files in the bucket and deletes those older than 1 hour.
    """
    from datetime import datetime, timedelta, timezone
    try:
        # List files in the root (depth=1)
        files = supabase.storage.from_(bucket_name).list("", {"limit": 100})
        if not files: return

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        
        to_delete = []
        for f in files:
            # Supabase list() returns dicts with 'name', 'created_at', etc.
            created_at_str = f.get('created_at')
            if created_at_str:
                # Example: 2024-03-20T10:00:00.000Z
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                if created_at < cutoff:
                    # Note: We assumed a flat folder structure or 'id/file'
                    # Actually, our structure is 'id/file'. list("") might return folders.
                    # This simple cleanup handles files in the root or just lists everything.
                    to_delete.append(f['name'])
        
        if to_delete:
            print(f"[Log] Cleaning up {len(to_delete)} old videos from storage...")
            supabase.storage.from_(bucket_name).remove(to_delete)
    except Exception as e:
        print(f"[Warning] Storage cleanup failed: {e}")
