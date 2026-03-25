import os
import json
import time
import subprocess
import numpy as np

def extract_audio_mono(video_path, output_dir):
    """
    Extracts mono 16kHz audio from video using FFmpeg.
    Returns path to the WAV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "audio_mono.wav")
    
    if os.path.exists(audio_path):
        return audio_path
        
    print(f"[Log] Extracting mono audio for analysis: {audio_path}")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ac", "1", "-ar", "16000", "-vn",
        audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path

def compute_audio_score(chunk, sr, prev_energy=None):
    """
    Computes a heuristic audio score based on energy, pitch variation, and silence.
    chunk: numpy array of audio samples
    """
    import librosa
    if len(chunk) == 0: return 0
    
    # 1. Energy (Loudness)
    energy = np.mean(chunk ** 2)
    
    # 2. Pitch variation (Emotion/Intensity)
    # Using a smaller window for speed
    try:
        pitches, magnitudes = librosa.piptrack(y=chunk, sr=sr, fmin=75, fmax=1600)
        pitch_var = np.var(pitches[pitches > 0]) if np.any(pitches > 0) else 0
    except:
        pitch_var = 0
        
    # 3. Silence Ratio
    try:
        non_silent = librosa.effects.split(y=chunk, top_db=25)
        active_len = sum(e - s for s, e in non_silent)
        silence_ratio = 1 - (active_len / len(chunk))
    except:
        silence_ratio = 0.5 # Default if split fails
        
    # 4. Energy Delta (Sudden shifts)
    delta = abs(energy - prev_energy) if prev_energy is not None else 0
    
    # Combined Audio Score (Weighted)
    # Rewards energy spikes, pitch variation, and contrast; penalizes silence.
    score = (energy * 50) + (pitch_var * 0.01) + (delta * 100) - (silence_ratio * 5)
    return max(0, score), energy

def score_segment(text, mode="shorts", start=None, end=None):
    """
    Heuristic scoring to identify high-potential highlights.
    - 'shorts': Focuses on intensity (shouting, punctuation) and viral keywords.
    - 'long': Focuses on narrative weight and sentence density.
    """
    score = 0
    text_lower = text.lower()
    word_count = len(text.split())
    duration = (end - start) if start is not None and end is not None else 0
    
    if mode == "shorts":
        # Intensity signals (Spikes)
        score += text.count("!") * 8
        score += sum(1 for w in text.split() if w.isupper() and len(w) > 3) * 5
        # Viral keywords
        keywords = ["no way", "wait", "what", "crazy", "insane", "oh my god", "unbelievable", "shocking", "finally"]
        for k in keywords:
            if k in text_lower: score += 12
        # Pacing
        if 5 < word_count < 25: score += 10 
        
        # 🟢 EXPERT REFINEMENT: Duration Heuristics for Shorts
        if 5 < duration < 15:
            score += 12  # Ideal punchy length
        elif duration > 40:
            score -= 10  # Too long for a single short candidate
    else:
        # Narrative signals (Density & flow)
        score += text.count(".") * 5
        score += text.count(",") * 2
        
        # 🟢 EXPERT REFINEMENT: Conflict & Tension Signals
        conflict_words = ["but", "however", "problem", "issue", "failed", "wrong", "mistake", "challenge", "unbelievable"]
        for k in conflict_words:
            if k in text_lower: score += 10
            
        story_keys = ["because", "then", "after", "finally", "decided", "discovered", "realized"]
        for k in story_keys:
            if k in text_lower: score += 8
            
        if 20 < word_count < 60: score += 10
        
        # 🟢 EXPERT REFINEMENT: Payoff Keywords (Narrative Weight)
        story_peaks = ["finally", "in the end", "turns out", "the result", "this is why", "because of that"]
        for k in story_peaks:
            if k in text_lower:
                score += 20
                
        # 🟢 EXPERT REFINEMENT: Duration Penalty/Bonus
        if duration > 60:
            score -= 10
        elif 15 < duration < 45:
            score += 10  # Sweet spot for engagement

    return score

def compress_transcript(segments, window=15.0):
    """
    Merges tiny Whisper fragments into larger context-rich windows.
    This prevents the LLM from seeing fragmented noise and provides 
    better story/peak detection.
    """
    if not segments: return []
    merged = []
    # Initialize with first segment
    curr = {
        "start": segments[0]["start"], 
        "end": segments[0]["end"], 
        "text": segments[0]["text"]
    }
    
    for seg in segments[1:]:
        # If adding this segment keeps us within the window, merge it
        if seg["end"] - curr["start"] <= window:
            curr["end"] = seg["end"]
            curr["text"] += " " + seg["text"]
        else:
            # Otherwise, push current and start fresh
            merged.append(curr)
            curr = {
                "start": seg["start"], 
                "end": seg["end"], 
                "text": seg["text"]
            }
    merged.append(curr)
    return merged

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
        
    print(f"[Log] Starting AI Transcription (GPU Optimized - MEDIUM Model)...")
    start_time = time.time()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # 🟢 UPGRADE: 'medium' model provides significantly better punctuation and nuance
    model = whisper.load_model("medium", device=device) 
    result = model.transcribe(video_path, language="en")
    
    # Save the full result for debugging and reuse
    print(f"[Log] Saving transcript to {transcript_path}...")
    result.save_as_json(transcript_path)
    print(f"[Log] Transcript saved successfully.")
    
    print(f"[Log] Transcription completed in {time.time() - start_time:.1f}s")
    return transcript_path

def merge_segments(segments, min_gap=6.0, max_dur=95.0, score_sensitive=False):
    """
    Merges segments that are close together.
    If score_sensitive=True, prevents merging high-viral moments with low-quality filler.
    """
    if not segments: return []
    sorted_segs = sorted(segments, key=lambda x: x['start'])
    merged = []
    curr = sorted_segs[0].copy()
    
    for next_seg in sorted_segs[1:]:
        gap = next_seg['start'] - curr['end']
        combined_dur = next_seg['end'] - curr['start']
        
        # 🟢 Phase 2: Score-aware merge to prevent peak dilution
        score_diff = abs(curr.get('viral_score', 0) - next_seg.get('viral_score', 0))
        similarity_gate = score_diff < 20 if score_sensitive else True
        
        # Merge if gap is small, total duration is under max, and scores are compatible
        if gap < min_gap and combined_dur <= max_dur and similarity_gate:
            curr['end'] = max(curr['end'], next_seg['end'])
            if len(curr.get('reason', '')) < 150:
                curr['reason'] = f"{curr.get('reason', 'Segment')} & {next_seg.get('reason', 'Clip')}"
            # Keep the highest viral score if merging
            curr['viral_score'] = max(curr.get('viral_score', 0), next_seg.get('viral_score', 0))
        else:
            merged.append(curr)
            curr = next_seg.copy()
    merged.append(curr)
    return merged

def identify_highlights(transcript_path, video_path=None, clip_count=5, mode="shorts", target_duration=None, use_audio_detect=False):
    from engine.script_gen import robust_json_parse, get_llm_response
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    
    segments = transcript_data.get('segments', [])
    if not segments:
        print("[Warning] Empty transcript. Cannot identify highlights.")
        return []
        
    total_duration = segments[-1]['end'] if segments else 0
    
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

    # 🟢 ADAPTIVE COMPRESSION: Tighter windows for shorts to keep spikes focused
    window_size = 15.0 if mode == "shorts" else 40.0
    print(f"[Log] Compressing {len(segments)} fragments into {window_size}s context windows...")
    compressed_segments = compress_transcript(segments, window=window_size)
    
    # 🟢 PHASE 13: Optional Audio Signal Detection
    audio_full = None
    sr = 16000
    if use_audio_detect and video_path:
        try:
            import librosa
            wav_path = extract_audio_mono(video_path, os.path.dirname(transcript_path))
            print(f"[Log] Loading audio for signal analysis...")
            audio_full, sr = librosa.load(wav_path, sr=sr)
        except Exception as e:
            print(f"[Warning] Audio analysis initialization failed: {e}. Falling back to text-only.")
            use_audio_detect = False

    # 🟢 PHASE 2: Signal Pre-Ranking & Delta (Contrast) Detection
    prev_energy = None
    for i, seg in enumerate(compressed_segments):
        seg['score'] = score_segment(seg['text'], mode=mode, start=seg['start'], end=seg['end'])
        
        # Audio Hybrid Signal
        seg['audio_score'] = 0
        if use_audio_detect and audio_full is not None:
            s_idx = int(seg['start'] * sr)
            e_idx = int(seg['end'] * sr)
            chunk = audio_full[s_idx:e_idx]
            a_score, energy = compute_audio_score(chunk, sr, prev_energy=prev_energy)
            seg['audio_score'] = round(a_score, 3)
            prev_energy = energy
            
        # Change in intensity (Delta) captures "moments" better than static high volume
        if i > 0:
            seg['delta'] = abs(seg['score'] - compressed_segments[i-1]['score'])
        else:
            seg['delta'] = 0

    # 🟢 EXPERT REFINEMENT: Signal Normalization
    max_orig_score = max(s['score'] for s in compressed_segments) if compressed_segments else 1
    max_audio_score = max(s['audio_score'] for s in compressed_segments) if compressed_segments else 1
    
    if max_orig_score == 0: max_orig_score = 1
    if max_audio_score == 0: max_audio_score = 1
    
    for seg in compressed_segments:
        seg['norm_score'] = round(seg['score'] / max_orig_score, 2)
        seg['norm_audio'] = round(seg['audio_score'] / max_audio_score, 2)
        
        # Combined Final Ranking Score for Pruning
        # 60% Text Signal, 40% Audio Signal (Expert Weighting)
        seg['pruning_score'] = (seg['norm_score'] * 0.6) + (seg['norm_audio'] * 0.4) + (seg['delta'] * 0.2)
            
    # 🟢 EXPERT REFINEMENT: Dynamic Context Pruning
    context_window = 2 if mode == "shorts" else 4
    limit = 25 if mode == "shorts" else 50
    if len(compressed_segments) > limit:
        # Long mode needs narrative flow, so we include buildup/aftermath
        top_indices = sorted(range(len(compressed_segments)), key=lambda i: compressed_segments[i]['pruning_score'], reverse=True)[:limit//2]
        
        selected_indices = set()
        for i in top_indices:
            # Include dynamic context window based on mode
            for offset in range(-context_window, context_window + 1):
                idx = i + offset
                if 0 <= idx < len(compressed_segments):
                    selected_indices.add(idx)
        
        compressed_segments = [compressed_segments[i] for i in sorted(list(selected_indices))]
    
    full_text_with_ts = ""
    for segment in compressed_segments:
        # Pass signal context directly to LLM for better ranking
        sigs = f"t_signal={segment['norm_score']} d_signal={segment['delta']}"
        if use_audio_detect:
            sigs += f" a_signal={segment['norm_audio']}"
        full_text_with_ts += f"[{segment['start']:.2f}s - {segment['end']:.2f}s | {sigs}]: {segment['text']}\n"
    
    if mode == "shorts":
        system_prompt = "You are a professional social media manager. Identify high-impact viral moments. YOU MUST PROVIDE TIMESTAMPS FOR EVERY CLIP."
        prompt = f"""Objective: Identify viral moments for YouTube Shorts.
        
        VIRALITY SIGNALS (Look for high 'signal' or high 'delta' in the log):
        1. High Signal: Intense yelling, punctuation, or shock keywords.
        2. High Delta: Sudden shifts in tone or intensity (very viral!).
        3. Emotional spikes (shocking, funny, intense action).
        
        STRICT RULES:
        1. Each moment MUST be between 8 and 45 seconds long.
        2. MANDATORY: 'start' and 'end' timestamps MUST be provided.
        3. REJECT: slow setups, generic intros, filler conversation.
        4. Wrap JSON array in START_JSON and END_JSON markers.
        
        Log Data (Signal/Delta marked): 15-30 segments provided:
        {full_text_with_ts}"""
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
        Identify UP TO {segment_target} key segments. Only include segments that are meaningful story beats.
        MANDATORY: include 'start' and 'end' timestamps.
        
        STRICT RULES:
        1. Wrap JSON in START_JSON and END_JSON.
        2. Provide 'viral_score' (0-100) and 'hook_text' for each.
        3. RAW JSON ONLY. NO EXTRA TEXT.
        
        Log Data (Signal/Delta marked):
        {full_text_with_ts}
        
        MANDATORY: Return a JSON LIST of objects. Even if only one moment is found, wrap it in []."""

    try:
        print(f"[Log] Sending {len(compressed_segments)} high-signal candidates to LLM for viral analysis...")
        response_text = get_llm_response(prompt, system_prompt, 4096)
        print(f"[Log] LLM analysis received ({len(response_text)} chars).")
        res_data = robust_json_parse(response_text)
        
        highlights = []
        if isinstance(res_data, list):
            highlights = res_data
        elif isinstance(res_data, dict):
            for key in ["highlights", "segments", "data", "clips"]:
                if key in res_data:
                    highlights = res_data[key]
                    break
            if not highlights and 'start' in res_data:
                # 🟢 RECOVERY: LLM returned a single object instead of a list
                highlights = [res_data]
        
        if not highlights:
            print(f"[DEBUG] Raw LLM output failed to parse: {response_text[:300]}...")

        # 🟢 QUALITY FILTER, MERGING & SORTING
        valid_highlights = []
        min_floor = 8.0 if mode == "shorts" else 25.0 
        
        if isinstance(highlights, list) and highlights:
            for h in highlights:
                if isinstance(h, dict) and 'start' in h and 'end' in h:
                    v_score = h.get('viral_score', 0)
                    if isinstance(v_score, str): v_score = int(''.join(filter(str.isdigit, v_score)) or 0)
                    h['viral_score'] = v_score
                    
                    # 🟢 EXPERT REFINEMENT: Hybrid Signal Ranking
                    # Instead of strict containment, include anything that overlaps the highlight window
                    contribution = [s['norm_score'] for s in compressed_segments if not (s['end'] < h['start'] or s['start'] > h['end'])]
                    heuristic_component = (sum(contribution) / len(contribution)) if contribution else 0
                    
                    if use_audio_detect:
                        a_contribution = [s.get('norm_audio', 0) for s in compressed_segments if not (s['end'] < h['start'] or s['start'] > h['end'])]
                        a_heuristic = (sum(a_contribution) / len(a_contribution)) if a_contribution else 0
                        heuristic_component = (heuristic_component * 0.6) + (a_heuristic * 0.4)
                    
                    # Hybrid score: 70% LLM viral confidence + 30% heuristic signal (text + audio)
                    h['final_score'] = (v_score * 0.7) + (heuristic_component * 100 * 0.3)
                    valid_highlights.append(h)
                elif isinstance(h, (list, tuple)) and len(h) >= 2:
                    valid_highlights.append({"start": float(h[0]), "end": float(h[1]), "viral_score": 50, "final_score": 50, "reason": "Recovered"})
            
            # 🟢 NEW FLOW: Merge adjacent parts BEFORE trimming to count
            max_merge_dur = 50.0 if mode == "shorts" else 180.0
            print(f"[Log] Merging adjacent highlights (score-aware)...")
            valid_highlights = merge_segments(valid_highlights, min_gap=8.0, max_dur=max_merge_dur, score_sensitive=True)
            
            # 🟢 OPUS-STYLE SORTING: Prioritize high hybrid scores
            valid_highlights.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            
            # Limit segments for shorts mode AFTER merge to keep only the best substantial clips
            if mode == "shorts":
                valid_highlights = valid_highlights[:clip_count]
            
            # 🟢 MANDATORY: Re-sort chronologically to ensure narrative flow and fix timing mismatch
            # This ensures that even if we picked top scores, they play back in order.
            valid_highlights.sort(key=lambda x: x['start'])
            
            # Final filter by floor
            valid_highlights = [h for h in valid_highlights if (h['end'] - h['start']) >= min_floor]
        
        if not valid_highlights:
            print("[Warning] LLM analysis failed. Using Heuristic Signal Fallback (Top Peaks)...")
            # 🟢 DYNAMIC RECOVERY: Use top heuristic signal peaks (Text + Audio)
            fallback_candidates = sorted(compressed_segments, key=lambda x: x['norm_score'] + x.get('norm_audio', 0), reverse=True)
            
            for f in fallback_candidates[:clip_count]:
                valid_highlights.append({
                    "start": f['start'],
                    "end": f['end'],
                    "viral_score": int(f['norm_score'] * 100),
                    "final_score": int(f['norm_score'] * 100),
                    "reason": "High-Signal Moment (Heuristic Fallback)"
                })
            
            # Sort chronologically for playback reliability
            valid_highlights.sort(key=lambda x: x['start'])

        if not valid_highlights:
            # 🟢 ABSOLUTE FAILSAFE: Simple duration-based slice
            fallback_start = min(45.0, total_duration * 0.1)
            fallback_duration = 35.0 if mode == "shorts" else (target_duration or 180.0)
            return [{"start": fallback_start, "end": fallback_start + fallback_duration, "viral_score": 85, "reason": "Draft Extraction (Failsafe)"}]
        
        return valid_highlights
            
        print(f"[Log] Curation complete: Selected {len(valid_highlights)} high-viral segments.")
        return valid_highlights
    except Exception as e:
        print(f"[Error] Highlight identification failed: {e}")
        import traceback
        traceback.print_exc()
        return [{"start": 10.0, "end": 40.0, "reason": "Emergency Fallback Moment"}]

def process_source_video(video_path, output_dir, mode="shorts", clip_count=5, target_duration=None, use_audio_detect=False):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video Not Found: {video_path}")
    
    transcript_path = transcribe_video(video_path, output_dir)
    highlights = identify_highlights(
        transcript_path, video_path=video_path, clip_count=clip_count, 
        mode=mode, target_duration=target_duration, use_audio_detect=use_audio_detect
    )
    return highlights, transcript_path
