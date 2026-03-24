import os
import json
import time

def transcribe_video(video_path, output_dir):
    """
    Lazy-loads Whisper and transcribes the video.
    Returns path to transcript.json.
    """
    import stable_whisper as whisper
    import torch
    
    os.makedirs(output_dir, exist_ok=True)
    transcript_path = os.path.join(output_dir, "transcript.json")
    
    if os.path.exists(transcript_path):
        print(f"[Log] Using cached transcript: {transcript_path}")
        return transcript_path
        
    print(f"[Log] Starting AI Transcription (GPU Optimized)...")
    start_time = time.time()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model("base", device=device) 
    result = model.transcribe(video_path, language="en")
    
    # Save the full result for debugging and reuse
    result.save_as_json(transcript_path)
    
    print(f"[Log] Transcription completed in {time.time() - start_time:.1f}s")
    return transcript_path

def merge_segments(segments, min_gap=6.0, max_dur=95.0):
    """Merges segments that are close together to form substantial story arcs."""
    if not segments: return []
    sorted_segs = sorted(segments, key=lambda x: x['start'])
    merged = []
    curr = sorted_segs[0].copy()
    
    for next_seg in sorted_segs[1:]:
        gap = next_seg['start'] - curr['end']
        combined_dur = next_seg['end'] - curr['start']
        
        # Merge if gap is small and total duration is under max
        if gap < min_gap and combined_dur <= max_dur:
            curr['end'] = max(curr['end'], next_seg['end'])
            if len(curr.get('reason', '')) < 150:
                curr['reason'] = f"{curr.get('reason', 'Segment')} & {next_seg.get('reason', 'Clip')}"
        else:
            merged.append(curr)
            curr = next_seg.copy()
    merged.append(curr)
    return merged

def identify_highlights(transcript_path, clip_count=5, mode="shorts", target_duration=None):
    from engine.script_gen import robust_json_parse, get_llm_response
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    
    full_text_with_ts = ""
    for segment in transcript_data.get('segments', []):
        full_text_with_ts += f"[{segment['start']:.2f}s - {segment['end']:.2f}s]: {segment['text']}\n"
    
    if mode == "shorts":
        system_prompt = "You are a professional social media manager. Identify high-impact viral moments. YOU MUST PROVIDE TIMESTAMPS FOR EVERY CLIP."
        prompt = f"""Objective: Identify viral moments for YouTube Shorts.
        
        STRICT RULES:
        1. Each moment MUST be between 15 and 45 seconds long.
        2. MANDATORY: provide 'start' and 'end' timestamps for every segment.
        3. SKIP generic introductions or setups. Focus on peak action.
        4. Wrap JSON array in START_JSON and END_JSON markers.
        5. Provide 'viral_score' (0-100) and 'hook_text' for each.
        
        Log Data: {full_text_with_ts}"""
    else: # Long-Form Highlight Reel
        system_prompt = "You are a narrative editor. Provide TIMESTAMPS for all story beats."
        if target_duration and target_duration > 1200:
            avg_seg_dur = 65 
            segment_target = int(target_duration / avg_seg_dur)
            dur_msg = "Each segment MUST be between 45 and 95 seconds."
        else:
            avg_seg_dur = 45
            segment_target = int((target_duration or 300) / avg_seg_dur)
            dur_msg = "Each segment SHOULD be between 30 and 70 seconds."
        
        segment_target = max(5, min(segment_target, 250))
        prompt = f"""Objective: Generate a cohesive narrative summary reel.
        Identify EXACTLY {segment_target} key segments. MANDATORY: include 'start' and 'end' timestamps.
        
        STRICT RULES:
        1. Wrap JSON in START_JSON and END_JSON.
        2. Provide 'viral_score' (0-100) and 'hook_text' for each.
        3. RAW JSON ONLY. NO EXTRA TEXT.
        
        Log Data: {full_text_with_ts}"""

    try:
        response_text = get_llm_response(prompt, system_prompt, 4096)
        res_data = robust_json_parse(response_text)
        
        highlights = []
        if isinstance(res_data, list):
            highlights = res_data
        elif isinstance(res_data, dict):
            for key in ["highlights", "segments", "data", "clips"]:
                if key in res_data:
                    highlights = res_data[key]
                    break
        
        # 🟢 QUALITY FILTER, MERGING & SORTING
        valid_highlights = []
        min_floor = 12.0 if mode == "shorts" else 25.0 
        
        # 🟢 PHASE 15: BREATHING CHALLENGE Logic
        # Challenges don't need "viral analysis" of the background. They just need a nice backdrop.
        if mode == "CHALLENGE":
            print("[Log] Mode: CHALLENGE. Skipping viral analysis, extracting a high-quality backdrop.")
            # Pick a segment starting at 60s (to avoid intros) for the required duration
            start_pt = min(60.0, total_duration * 0.1)
            return [{
                "start": start_pt, 
                "end": start_pt + (target_duration or 60), 
                "viral_score": 100, 
                "reason": "Challenge Backdrop"
            }]

        if isinstance(highlights, list) and highlights:
            for h in highlights:
                if isinstance(h, dict) and 'start' in h and 'end' in h:
                    v_score = h.get('viral_score', 0)
                    if isinstance(v_score, str): v_score = int(''.join(filter(str.isdigit, v_score)) or 0)
                    h['viral_score'] = v_score
                    valid_highlights.append(h)
                elif isinstance(h, (list, tuple)) and len(h) >= 2:
                    valid_highlights.append({"start": float(h[0]), "end": float(h[1]), "viral_score": 50, "reason": "Recovered"})
            
            # 🟢 OPUS-STYLE SORTING: Prioritize high viral scores
            valid_highlights.sort(key=lambda x: x.get('viral_score', 0), reverse=True)
            
            # Limit segments for shorts mode AFTER sorting to keep only the best
            if mode == "shorts":
                valid_highlights = valid_highlights[:clip_count]
                # Re-sort chronologically for extraction flow
                valid_highlights.sort(key=lambda x: x['start'])
            
            # Merge adjacent segments and filter by floor
            max_merge_dur = 50.0 if mode == "shorts" else 180.0
            valid_highlights = merge_segments(valid_highlights, min_gap=8.0, max_dur=max_merge_dur)
            valid_highlights = [h for h in valid_highlights if (h['end'] - h['start']) >= min_floor]
        
        if not valid_highlights:
            print("[Warning] No high-impact highlights found. Using quality fallback.")
            return [{"start": 30.0, "end": 65.0, "viral_score": 85, "reason": "High-Impact Peak Moment"}]
            
        print(f"[Log] Curation complete: Selected {len(valid_highlights)} high-viral segments.")
        return valid_highlights
    except Exception as e:
        print(f"[Error] Highlight identification failed: {e}")
        return [{"start": 10.0, "end": 40.0, "reason": "Fallback Moment"}]

def process_source_video(video_path, output_dir, mode="shorts", clip_count=5, target_duration=None):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video Not Found: {video_path}")
    
    transcript_path = transcribe_video(video_path, output_dir)
    highlights = identify_highlights(transcript_path, clip_count=clip_count, mode=mode, target_duration=target_duration)
    return highlights, transcript_path
