import os
import json
import shutil
import subprocess
import time
import uuid

def copy_to_public(src_path, dest_dir, public_base="temp_assets"):
    """
    Copies a local file to the Remotion public directory and returns the path relative to public/.
    """
    if not src_path or not os.path.exists(src_path):
        return None
    
    filename = os.path.basename(src_path)
    # Sanitize filename to prevent path traversal
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    if not filename:
        filename = f"asset_{uuid.uuid4().hex[:8]}"
        
    dest_path = os.path.join(dest_dir, filename)
    shutil.copy2(src_path, dest_path)
    
    # Return path relative to public/
    rel_path = os.path.join(public_base, os.path.basename(dest_dir), filename).replace("\\", "/")
    return rel_path

def render_with_remotion(
    audio_path,
    subs_path,
    output_path,
    mode,
    bg_music_path=None,
    title_text=None,
    background_paths=None,
    this_or_that=None,  # dict: {"option_a": str, "option_b": str, "path_a": str, "path_b": str}
    rank_it=None,       # dict: {"items": list of str, "paths": list of str}
    caption_this=None,  # dict: {"image_path": str, "prompt_text": str}
    duration=None,
    start_offset=0.0,
    caption_style="HORMOZI",
    subtitle_y_pos=1150
):
    """
    Renders a Short using Remotion by preparing assets, creating props, and running npx remotion render.
    """
    print(f"\n[RemotionRenderer] Initiating modern render pipeline for mode: {mode} (Caption Preset: {caption_style})...")
    
    # 1. Establish directory paths
    current_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    remotion_dir = os.path.join(project_root, "remotion-video")
    public_dir = os.path.join(remotion_dir, "public")
    
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_assets_dir = os.path.join(public_dir, "temp_assets", run_id)
    os.makedirs(run_assets_dir, exist_ok=True)
    
    try:
        # 2. Copy core audio/voice
        rel_audio_path = copy_to_public(audio_path, run_assets_dir)
        if not rel_audio_path:
            raise FileNotFoundError(f"Voice audio path not found: {audio_path}")
            
        # Copy background music
        rel_music_path = copy_to_public(bg_music_path, run_assets_dir) if bg_music_path else None
        
        # 3. Parse words from subtitles file
        words = []
        if subs_path and os.path.exists(subs_path):
            with open(subs_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)
            
            raw_words = []
            if isinstance(transcript_data, list):
                raw_words = transcript_data
            elif isinstance(transcript_data, dict):
                segments = transcript_data.get('segments', [])
                for seg in segments:
                    raw_words.extend(seg.get('words', []))
                    
            for w in raw_words:
                w_start = float(w['start']) - start_offset
                if 'end' in w:
                    w_end = float(w['end']) - start_offset
                elif 'duration' in w:
                    w_end = float(w['start']) + float(w['duration']) - start_offset
                else:
                    w_end = float(w['start']) + 0.5 - start_offset
                    
                words.append({
                    "word": w['word'].strip(),
                    "start": max(0.0, w_start),
                    "end": w_end
                })
        
        # Determine total duration in seconds
        if not duration:
            if words:
                duration = max(w['end'] for w in words) + 1.0
            else:
                duration = 30.0  # default fallback
                
        # Filter words to only those starting before video ends
        words = [w for w in words if w['start'] < duration]
                
        # 4. Mode-specific assets
        remotion_tot = None
        remotion_rank = None
        remotion_cap = None
        remotion_bg = []
        
        if mode == "THIS_OR_THAT" and this_or_that:
            path_a = copy_to_public(this_or_that.get("path_a"), run_assets_dir)
            path_b = copy_to_public(this_or_that.get("path_b"), run_assets_dir)
            remotion_tot = {
                "optionA": this_or_that.get("option_a", "Option A"),
                "optionB": this_or_that.get("option_b", "Option B"),
                "imageA": path_a,
                "imageB": path_b
            }
        elif mode == "RANK_IT" and rank_it:
            items_list = []
            item_names = rank_it.get("items", [])
            item_paths = rank_it.get("paths", [])
            tiers = ["D", "C", "B", "A", "S"]
            
            # Distribute time among rank items
            item_dur = (duration - 2.0) / max(1, len(item_paths))
            for i, p in enumerate(item_paths):
                rel_p = copy_to_public(p, run_assets_dir)
                start = 1.0 + (i * item_dur)
                end = start + item_dur
                items_list.append({
                    "name": item_names[i] if i < len(item_names) else f"Item {i+1}",
                    "image": rel_p,
                    "tier": tiers[min(i, len(tiers)-1)],
                    "start": start,
                    "end": end
                })
            remotion_rank = {"items": items_list}
        elif mode == "CAPTION_THIS" and caption_this:
            rel_image = copy_to_public(caption_this.get("image_path"), run_assets_dir)
            remotion_cap = {
                "image": rel_image,
                "promptText": caption_this.get("prompt_text", "CAPTION THIS!")
            }
        else:
            # Standard background stitching
            bg_paths = background_paths if isinstance(background_paths, list) else ([background_paths] if background_paths else [])
            seg_dur = duration / max(1, len(bg_paths))
            for i, bp in enumerate(bg_paths):
                rel_bp = copy_to_public(bp, run_assets_dir)
                bg_type = "image" if bp.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) else "video"
                remotion_bg.append({
                    "path": rel_bp,
                    "start": i * seg_dur,
                    "end": (i + 1) * seg_dur,
                    "type": bg_type
                })
                
        # 5. Build props JSON
        props = {
          "audioUrl": rel_audio_path,
          "bgMusicUrl": rel_music_path if rel_music_path else None,
          "bgMusicVolume": 0.15,
          "words": words,
          "mode": mode,
          "category": "general",
          "titleText": title_text,
          "subtitleYPos": subtitle_y_pos,
          "captionStyle": caption_style,
          "backgrounds": remotion_bg
        }
        
        if remotion_tot: props["thisOrThat"] = remotion_tot
        if remotion_rank: props["rankIt"] = remotion_rank
        if remotion_cap: props["captionThis"] = remotion_cap
        
        # Write props to a JSON file inside remotion-video folder
        props_filename = f"temp_props_{run_id}.json"
        props_path = os.path.join(remotion_dir, props_filename)
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f, indent=2)
            
        # Calculate duration in frames (30fps)
        duration_frames = int(duration * 30)
        
        # 6. Execute Remotion render
        render_output = os.path.join(remotion_dir, "out.mp4")
        if os.path.exists(render_output):
            os.remove(render_output)
            
        print(f"[RemotionRenderer] Rendering {duration:.2f}s ({duration_frames} frames) to out.mp4...")
        
        # Check if GPU encoding (h264-nvenc) is available
        import imageio_ffmpeg
        use_nvenc = False
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            res = subprocess.run([ffmpeg_exe, '-encoders'], capture_output=True, text=True, timeout=5)
            use_nvenc = 'h264_nvenc' in res.stdout
        except:
            pass

        if use_nvenc:
            print("[RemotionRenderer] NVIDIA GPU Detected: Enabling NVENC hardware-accelerated video encoding.")
        else:
            print("[RemotionRenderer] No NVIDIA GPU detected: Using standard CPU-based encoding.")

        # Trigger npx remotion render
        cmd = [
            "npx", "remotion", "render",
            "ShortFlow",
            "out.mp4",
            f"--props={props_filename}",
            f"--frames=0-{duration_frames - 1}",
            "--codec=h264",
            "--hardware-acceleration=if-possible",
            "--concurrency=4"
        ]
        
        # Run process
        result = subprocess.run(
            cmd,
            cwd=remotion_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True # Required on Windows to locate npx globally
        )
        
        if result.returncode != 0:
            print("[RemotionRenderer] Remotion CLI Error Output:")
            print(result.stderr)
            raise RuntimeError(f"Remotion render failed with code {result.returncode}")
            
        # 7. Move output to final location
        if os.path.exists(render_output):
            shutil.move(render_output, output_path)
            print(f"[RemotionRenderer] SUCCESS! Rendered video saved to: {output_path}")
            return output_path
        else:
            raise FileNotFoundError("Render succeeded but output out.mp4 was not found.")
            
    finally:
        # Clean up temporary public assets directory to save disk space
        if os.path.exists(run_assets_dir):
            shutil.rmtree(run_assets_dir)
        # Clean up props file
        if 'props_path' in locals() and os.path.exists(props_path):
            os.remove(props_path)
