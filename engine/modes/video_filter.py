"""video_filter pipeline, moved verbatim from main.py (runs when: getattr(args, "mode", None) == "FILTER")."""
import os
import sys
import io
import time
import random
import argparse
import json
import re
import subprocess
from dotenv import load_dotenv
from supabase import create_client, Client
from engine.utils import decrypt_secret, find_fact_start_times
from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge, generate_odd_one_out_script, generate_riddle, generate_jwst_script
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx, fetch_jwst_images, is_url, download_source_video_from_url
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage



def run(args, target_bitrate, target_preset):
    from engine.video_gen import apply_standalone_video_filter
    from engine.script_gen import auto_detect_video_filter, generate_dynamic_filter_timeline
    
    if not getattr(args, "source_video", None):
        print("[Error] Standalone FILTER mode requires --source_video parameter.")
        sys.exit(1)
        
    session_dir = args.session_dir if args.session_dir else f"sessions/filtered_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    
    if is_url(args.source_video):
        print(f"[Log] Detected Video URL: '{args.source_video}'. Downloading stream...")
        args.source_video = download_source_video_from_url(args.source_video, session_dir)
        
    target_filter = getattr(args, "video_filter", "none")
    timeline_cuts = None
    if target_filter == "auto":
        target_filter = auto_detect_video_filter(user_context=args.user_context, style_context=args.style_context, category=args.category, prompt=args.prompt)
        print(f"[Log] 🎨 Auto-detected visual filter: '{target_filter}'")
    elif target_filter == "dynamic":
        from moviepy import VideoFileClip
        try:
            with VideoFileClip(args.source_video) as clip:
                dur = clip.duration
        except Exception:
            dur = 30.0
            
        scene_desc = f"Video clip: {os.path.basename(args.source_video)}"
        transcript_data = None
        
        src_dir = os.path.dirname(os.path.abspath(args.source_video))
        meta_file = os.path.join(src_dir, "metadata.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r', encoding='utf-8') as mf:
                    meta_list = json.load(mf)
                    if isinstance(meta_list, list):
                        fn = os.path.basename(args.source_video)
                        for m in meta_list:
                            if m.get("file") == fn:
                                scene_desc = f"Title: {m.get('title', '')} | Desc: {m.get('description', '')}"
                                break
            except Exception:
                pass
                
        trans_file = os.path.join(src_dir, "transcript.json")
        if os.path.exists(trans_file):
            try:
                with open(trans_file, 'r', encoding='utf-8') as tf:
                    transcript_data = json.load(tf)
            except Exception:
                pass
                
        timeline_cuts = generate_dynamic_filter_timeline(
            dur, 
            user_context=args.user_context, 
            transcript_data=transcript_data,
            scene_description=scene_desc
        )
        
    out_filename = os.path.basename(args.source_video).rsplit('.', 1)[0] + f"_{target_filter}.mp4"
    output_video = os.path.join(session_dir, out_filename)
    
    print(f"--- Starting Standalone Filter Application ---")
    apply_standalone_video_filter(args.source_video, output_video, filter_name=target_filter, use_hq=args.hq, timeline_cuts=timeline_cuts)
    print(f"[Success] 🎨 Filtered video ready at: {output_video}")
    sys.exit(0)
