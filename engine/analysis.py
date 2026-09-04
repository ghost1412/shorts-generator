import os
import json
import time
import subprocess
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# VIDEO SOURCE INTELLIGENCE UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def detect_letterbox(video_path):
    """
    Detects letterbox/pillarbox black bars using FFmpeg cropdetect.
    Returns an FFmpeg crop filter string (e.g. 'crop=1920:800:0:140') or None.
    """
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        # Sample 5 frames evenly across the video for cropdetect
        cmd = [
            ffmpeg_exe, '-skip_frame', 'noref', '-i', video_path,
            '-vf', 'cropdetect=24:16:0', '-frames:v', '30',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # Parse crop= lines from stderr
        crop_values = []
        for line in result.stderr.split('\n'):
            if 'crop=' in line:
                part = [p for p in line.split() if p.startswith('crop=')]
                if part:
                    crop_values.append(part[-1])
        if not crop_values:
            return None
        # Use the most common value (mode)
        from collections import Counter
        most_common = Counter(crop_values).most_common(1)[0][0]
        # Check if this actually removes bars (skip if it's the full frame)
        try:
            parts = most_common.replace('crop=', '').split(':')
            cw, ch = int(parts[0]), int(parts[1])
            # Probe original dimensions
            probe = subprocess.run(
                [ffmpeg_exe, '-i', video_path], capture_output=True, text=True, timeout=10
            )
            for pline in probe.stderr.split('\n'):
                if 'Video:' in pline and 'x' in pline:
                    import re
                    m = re.search(r'(\d{3,})x(\d{3,})', pline)
                    if m:
                        ow, oh = int(m.group(1)), int(m.group(2))
                        if cw >= ow * 0.98 and ch >= oh * 0.98:
                            return None  # No meaningful crop needed
                        break
        except Exception:
            pass
        print(f"[Log] Letterbox detected — applying auto-strip: {most_common}")
        return most_common
    except Exception as e:
        print(f"[Warning] Letterbox detection failed: {e}")
        return None


def detect_orientation(video_path):
    """
    Returns 'portrait' if h > w (already 9:16), else 'landscape'.
    Skips the 9:16 crop filter for portrait sources to avoid quality loss.
    """
    import imageio_ffmpeg, re
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        result = subprocess.run(
            [ffmpeg_exe, '-i', video_path], capture_output=True, text=True, timeout=10
        )
        for line in result.stderr.split('\n'):
            if 'Video:' in line:
                m = re.search(r'(\d{3,})x(\d{3,})', line)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    orientation = 'portrait' if h > w else 'landscape'
                    print(f"[Log] Source orientation detected: {orientation} ({w}x{h})")
                    return orientation
    except Exception as e:
        print(f"[Warning] Orientation detection failed: {e}")
    return 'landscape'


def extract_youtube_chapters(info_json_path):
    """
    Reads YouTube chapter markers from a yt-dlp info.json file.
    Returns list of {title, start, end} dicts, or empty list.
    """
    if not info_json_path or not os.path.exists(info_json_path):
        return []
    try:
        with open(info_json_path, 'r', encoding='utf-8') as f:
            info = json.load(f)
        chapters_raw = info.get('chapters', [])
        if not chapters_raw:
            return []
        chapters = []
        for ch in chapters_raw:
            chapters.append({
                'title': ch.get('title', 'Chapter'),
                'start': float(ch.get('start_time', 0)),
                'end': float(ch.get('end_time', ch.get('start_time', 0) + 60))
            })
        print(f"[Log] Loaded {len(chapters)} YouTube chapters from info.json")
        return chapters
    except Exception as e:
        print(f"[Warning] Failed to load chapters: {e}")
        return []


def llm_score_highlights(highlights, transcript_data, top_n=5):
    """
    Uses Gemini to rate the top N highlight candidates for viral potential (1-10).
    Merges LLM score (60%) with existing heuristic score (40%) for final ranking.
    """
    if not highlights:
        return highlights
    try:
        from engine.script_gen import get_llm_response, robust_json_parse
    except ImportError:
        return highlights

    # Only score the top candidates to save API quota
    sorted_h = sorted(highlights, key=lambda x: float(x.get('score', 0)), reverse=True)
    to_score = sorted_h[:top_n]

    # Build segment text map from transcript
    seg_texts = {}
    for seg in transcript_data.get('segments', []):
        seg_texts[seg['start']] = seg.get('text', '')

    def get_segment_text(h):
        s, e = float(h['start']), float(h['end'])
        parts = [v for k, v in seg_texts.items() if s - 1 <= k <= e + 1]
        return ' '.join(parts).strip() or h.get('reason', 'No transcript')

    print(f"[Log] LLM Virality Scoring: rating top {len(to_score)} candidate clips...")
    for h in to_score:
        text_snippet = get_segment_text(h)[:500]
        prompt = (
            f"You are a viral YouTube Shorts editor. Rate this video segment's viral potential on a scale of 1-10 "
            f"(10 = guaranteed viral, 1 = boring). Consider hook strength, emotional intensity, pacing, and re-watchability.\n\n"
            f"Segment transcript ({h['start']:.1f}s - {h['end']:.1f}s):\n{text_snippet}\n\n"
            f"Reply ONLY with valid JSON: {{\"score\": <integer 1-10>, \"reason\": \"<one sentence why>\"}}"
        )
        try:
            raw = get_llm_response(prompt, "You are a viral video scoring expert.", max_tokens=120)
            parsed = robust_json_parse(raw)
            if parsed and isinstance(parsed, dict) and 'score' in parsed:
                llm_score = float(parsed['score'])
                heuristic_score = float(h.get('score', 5))
                # Weighted blend: 60% LLM + 40% heuristic (normalised to 0-100 range)
                h['llm_score'] = round(llm_score, 1)
                h['llm_reason'] = parsed.get('reason', '')
                h['score'] = round((llm_score / 10.0 * 100) * 0.6 + heuristic_score * 0.4, 1)
                print(f"  Clip {h['start']:.1f}s-{h['end']:.1f}s → LLM:{llm_score}/10 — {h['llm_reason']}")
        except Exception as e:
            print(f"  [Warning] LLM scoring failed for clip {h['start']:.1f}s: {e}")
            h['llm_score'] = None
            h['llm_reason'] = 'LLM unavailable'

    # Re-sort by updated combined score
    highlights = sorted(highlights, key=lambda x: float(x.get('score', 0)), reverse=True)
    return highlights


def extract_audio_mono(video_path, output_dir):
    """
    Extracts mono 16kHz audio from video using FFmpeg.
    Returns path to the WAV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "audio_mono.wav")
    
    if os.path.exists(audio_path):
        # Optional: check if file is too small or corrupt, but usually cache is fine
        return audio_path
        
    print(f"[Log] Extracting mono audio for analysis: {audio_path}")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ac", "1", "-ar", "16000", "-vn",
        audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path

def detect_silence_intervals(audio_path, threshold_db=25, min_silence_len=0.5, margin=0.1):
    """
    Returns a list of (start, end) intervals of 'keep' (non-silent) segments.
    threshold_db: volume below this is considered silence.
    min_silence_len: minimum duration (seconds) of silence to be cut.
    margin: breathing room added before/after cuts.
    """
    import librosa
    audio, sr = librosa.load(audio_path, sr=16000)
    
    # librosa.effects.split returns non-silent intervals
    # frame_length=2048, hop_length=512 are defaults
    non_silent_intervals = librosa.effects.split(y=audio, top_db=threshold_db)
    
    keep_intervals = []
    total_samples = len(audio)
    
    for start_idx, end_idx in non_silent_intervals:
        start_sec = max(0, start_idx / sr - margin)
        end_sec = min(total_samples / sr, end_idx / sr + margin)
        keep_intervals.append((start_sec, end_sec))
        
    # Merge overlapping intervals after margin expansion
    if not keep_intervals: return []
    
    merged = []
    curr_start, curr_end = keep_intervals[0]
    for next_start, next_end in keep_intervals[1:]:
        if next_start < curr_end:
            curr_end = max(curr_end, next_end)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end
    merged.append((curr_start, curr_end))
    
    return merged

def detect_motion_intervals(video_path, threshold=0.03, skip_frames=15, candidate_intervals=None):
    """
    Identifies 'keep' intervals based on visual motion.
    🟢 OPTIMIZED: Support for candidate-only scanning and increased skip_frames.
    """
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return []
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    ret, prev_frame = cap.read()
    if not ret: return []
    
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)
    
    motion_frames = []
    
    def scan_range(cap_obj, start_sec, end_sec):
        res = []
        cap_obj.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)
        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)
        
        ret, prev_f = cap_obj.read()
        if not ret: return []
        p_gray = cv2.cvtColor(prev_f, cv2.COLOR_BGR2GRAY)
        p_gray = cv2.GaussianBlur(p_gray, (21, 21), 0)
        
        f_idx = start_frame + 1
        m_values = []
        while f_idx < end_frame:
            for _ in range(skip_frames): 
                cap_obj.grab()
                f_idx += 1
            ret, frame = cap_obj.read()
            f_idx += 1
            if not ret: break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            diff = cv2.absdiff(p_gray, gray)
            thr = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
            thr = cv2.dilate(thr, None, iterations=2)
            m_pct = np.sum(thr) / (thr.shape[0] * thr.shape[1] * 255)
            m_values.append((f_idx, m_pct))
            p_gray = gray
        return m_values

    def worker_job(intervals):
        import cv2
        c = cv2.VideoCapture(video_path)
        data = []
        for s, e in intervals:
            data.extend(scan_range(c, s, e))
        c.release()
        return data

    raw_motion_data = []
    if candidate_intervals:
        from concurrent.futures import ThreadPoolExecutor
        import os
        # 🟢 OPTIMIZED: Adaptive worker count using CPU core count
        num_workers = min(os.cpu_count() or 4, len(candidate_intervals), 6)
        if num_workers > 1:
            chunks = [candidate_intervals[i::num_workers] for i in range(num_workers)]
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(worker_job, chunks))
                for r in results: raw_motion_data.extend(r)
        else:
            raw_motion_data = worker_job(candidate_intervals)
    else:
        raw_motion_data = worker_job([(0, total_frames / fps)])

    if not raw_motion_data: 
        cap.release()
        return []
        
    # 🟢 ADAPTIVE THRESHOLDING: Use 75th percentile to handle different video levels
    all_pcts = [x[1] for x in raw_motion_data]
    dynamic_threshold = max(threshold, np.percentile(all_pcts, 75))
    motion_frames = [f for f, p in raw_motion_data if p >= dynamic_threshold]
    
    cap.release()
    
    if not motion_frames: return []
    
    # Convert frames to time intervals
    keep_intervals = []
    start_frame = motion_frames[0]
    last_frame = motion_frames[0]
    
    # Margin of 1 second for motion continuity
    frame_margin = int(fps * 1.0)
    
    for f in motion_frames[1:]:
        if f - last_frame > frame_margin:
            keep_intervals.append((max(0, start_frame/fps), min(total_frames/fps, last_frame/fps)))
            start_frame = f
        last_frame = f
    keep_intervals.append((max(0, start_frame/fps), min(total_frames/fps, last_frame/fps)))
    
    return keep_intervals

def detect_interest_points(video_path, skip_frames=10, segments=None):
    """
    Detects the 'center of interest' (e.g., face position) using OpenCV Haar Cascades.
    Uses IoU-based speaker identity lock so the camera doesn't jump between multiple faces.
    Returns dict of {timestamp: x_center_percentage}.
    """
    import cv2

    face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(face_cascade_path)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    interest_points = {}

    frame_idx = 0
    last_x = 0.5
    ema_alpha = 0.15

    # IoU speaker lock — track the primary speaker's bounding box between frames
    locked_face = None  # (x, y, w, h) in small_frame coordinates
    iou_reset_threshold = 0.10  # Below this, assume new scene and pick largest face

    def compute_iou(a, b):
        ax1, ay1, ax2, ay2 = a[0], a[1], a[0]+a[2], a[1]+a[3]
        bx1, by1, bx2, by2 = b[0], b[1], b[0]+b[2], b[1]+b[3]
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2-ix1) * max(0, iy2-iy1)
        union = a[2]*a[3] + b[2]*b[3] - inter
        return inter / union if union > 0 else 0.0

    def pick_primary_face(faces, locked):
        if len(faces) == 0:
            return None
        if locked is None:
            return max(faces, key=lambda f: f[2] * f[3])
        best, best_iou = None, 0.0
        for face in faces:
            iou = compute_iou(locked, tuple(face))
            if iou > best_iou:
                best_iou = iou
                best = face
        # If match is too poor, reset to largest face (new scene or cut)
        if best_iou < iou_reset_threshold:
            return max(faces, key=lambda f: f[2] * f[3])
        return best

    def process_frame(frame):
        nonlocal last_x, locked_face
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        if len(faces) > 0:
            primary = pick_primary_face(list(faces), locked_face)
            if primary is not None:
                locked_face = tuple(primary)
                x_center = (primary[0] + primary[2] / 2) / small_frame.shape[1]
                last_x = last_x * (1 - ema_alpha * 2) + x_center * (ema_alpha * 2)
        else:
            last_x = last_x * (1 - ema_alpha) + 0.5 * ema_alpha

    if segments:
        for start, end in segments:
            cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
            frame_idx = int(start * fps)
            locked_face = None  # Reset lock at each new segment
            while frame_idx / fps < end:
                for _ in range(skip_frames):
                    cap.grab()
                    frame_idx += 1
                ret, frame = cap.read()
                frame_idx += 1
                if not ret: break
                process_frame(frame)
                interest_points[round(frame_idx / fps, 2)] = round(last_x, 3)
    else:
        while True:
            for _ in range(skip_frames):
                cap.grab()
                frame_idx += 1
            ret, frame = cap.read()
            frame_idx += 1
            if not ret: break
            process_frame(frame)
            interest_points[round(frame_idx / fps, 2)] = round(last_x, 3)

    cap.release()
    return interest_points



def extract_video_outline(transcript_path):
    """
    Generates a high-level outline of the video for structured analysis.
    """
    from engine.script_gen import get_llm_response
    with open(transcript_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    segments = data.get('segments', [])
    if not segments: return "Empty video."
    
    # Take samples from start, middle, end to summarize
    samples = []
    step = max(1, len(segments) // 15)
    for i in range(0, len(segments), step):
        s = segments[i]
        samples.append(f"[{s['start']:.1f}s]: {s['text']}")
    
    text_sample = "\n".join(samples)
    prompt = f"Summarize this video content into a high-level outline (topics and themes):\n\n{text_sample}"
    try:
        outline = get_llm_response(prompt, "You are a video analyst.")
    except Exception as e:
        print(f"[Warning] LLM Analysis for outline failed: {e}. Using fallback.")
        outline = "No outline available (LLM Offline)."
    return outline

def compute_global_audio_features(audio, sr):
    """
    🟢 PERFORMANCE: Computes heavy audio features (RMSE + Silence) once per video.
    """
    import librosa
    print("[Log] Computing global audio features (Energy + Silence)...")
    
    hop_length = 512
    rmse = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
    total_frames = len(rmse)
    
    # Frame-level silence mask for memory efficiency
    non_silent_intervals = librosa.effects.split(y=audio, top_db=25)
    silence_mask_frames = np.ones(total_frames, dtype=bool)  # True = Silent
    for start_idx, end_idx in non_silent_intervals:
        s_frame = start_idx // hop_length
        e_frame = min(end_idx // hop_length, total_frames)
        silence_mask_frames[s_frame:e_frame] = False
        
    return {
        "rmse": rmse,
        "hop_length": hop_length,
        "silence_mask_frames": silence_mask_frames,
        "total_frames": total_frames
    }

def compute_audio_score(chunk, sr, prev_energy=None, global_features=None, start_sec=0, end_sec=0, energy_baseline=None):
    """
    Computes a heuristic audio score, reusing global features if available.
    """
    import librosa
    if len(chunk) == 0: return 0, 0, 0, False
    
    # 1. Energy (Loudness)
    if global_features:
        hop = global_features["hop_length"]
        total_frames = global_features["total_frames"]
        s_idx = int(start_sec * sr / hop)
        e_idx = int(end_sec * sr / hop)
        s_idx = max(0, min(s_idx, total_frames - 1))
        e_idx = max(s_idx + 1, min(e_idx, total_frames))
        energy_slice = global_features["rmse"][s_idx:e_idx]
        energy = np.mean(energy_slice**2) if len(energy_slice) > 0 else 0
    else:
        energy = np.mean(chunk ** 2)
    
    # 2. Pitch variation
    # 🟢 PERFORMANCE: Pitch tracking is slow. Skip if using global features for speed.
    if global_features:
        pitch_var = 0 # Sacrifice pitch for massive speedup on long videos
    else:
        safe_n_fft = 2048
        if len(chunk) < 2048:
            safe_n_fft = 1024 if len(chunk) >= 1024 else (512 if len(chunk) >= 512 else 256)

        try:
            if len(chunk) < safe_n_fft:
                pitch_var = 0
            else:
                pitches, _ = librosa.piptrack(y=chunk, sr=sr, fmin=75, fmax=1600, n_fft=safe_n_fft)
                pitches = pitches[pitches > 0]
                pitch_var = np.var(pitches) if len(pitches) > 0 else 0
        except:
            pitch_var = 0
        
    # 3. Silence Ratio
    if global_features:
        hop = global_features["hop_length"]
        total_frames = global_features["total_frames"]
        s_idx = int(start_sec * sr / hop)
        e_idx = int(end_sec * sr / hop)
        s_idx = max(0, min(s_idx, total_frames - 1))
        e_idx = max(s_idx + 1, min(e_idx, total_frames))
        silence_slice = global_features["silence_mask_frames"][s_idx:e_idx]
        silence_ratio = np.mean(silence_slice) if len(silence_slice) > 0 else 0
        valid_silence = True
    else:
        try:
            split_frame = safe_n_fft
            while split_frame > len(chunk) and split_frame > 128: split_frame //= 2
            non_silent = librosa.effects.split(y=chunk, top_db=25, frame_length=split_frame)
            active_len = sum(e - s for s, e in non_silent)
            silence_ratio = 1 - (active_len / len(chunk))
        except:
            silence_ratio = 0.5
            valid_silence = False
        else:
            valid_silence = True
        
    # 🟢 Energy Delta (Sudden shifts)
    raw_energy = energy
    # Compare against EMA baseline for stability
    if energy_baseline is not None:
        delta = abs(raw_energy - energy_baseline)
    elif prev_energy is not None:
        delta = abs(raw_energy - prev_energy)
    else:
        delta = 0
    
    # Log-Normalization
    norm_energy = np.log1p(raw_energy)
    norm_delta = np.log1p(delta)
    # Pitch variation is only used if calculated (low CPU mode skips it)
    norm_pitch = np.log1p(pitch_var) if pitch_var > 0 else 0
    
    score = (norm_energy * 2.0) + (norm_delta * 3.0) + (norm_pitch * 1.5) - (silence_ratio * 2.0)
    return max(0, score), raw_energy, silence_ratio, valid_silence

def score_segment(text, mode="shorts", start=None, end=None, target_duration=None):
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
        # Adaptive scoring based on target_duration
        if target_duration and target_duration < 60:
            target = target_duration
            if abs(duration - target) < 5:
                score += 15  # Very close to user target
            elif duration > 60:
                score -= 30  # YouTube Short physical limit
            elif duration < 10:
                score -= 5   # A bit too punchy if they asked for something specific
        else:
            # Default legacy behavior if no target or target is weird
            if 5 < duration < 25:
                score += 12  # Ideal punchy length
            elif duration > 50:
                score -= 15  # Getting risky for shorts
    else:
        # Narrative signals (Density & flow)
        score += text.count(".") * 6
        score += text.count(",") * 2
        
        # 🟢 EXPERT REFINEMENT: Narrative Arc & Story Beats
        narrative_keywords = [
            "finally", "however", "consequently", "resolved", "conclusion", 
            "ending", "solved", "discovered", "because", "revealed",
            "kratos", "athena", "zeus", "pandora", "god", "revenge", "hope" # Content specific but effective
        ]
        for k in narrative_keywords:
            if k in text_lower: score += 15

        # Dialogue density (Short sentences often imply back-and-forth narrative)
        if word_count > 10:
            avg_word_len = sum(len(w) for w in text.split()) / word_count
            if 4 < avg_word_len < 7: # Standard conversational English
                score += 8

        # Length normalization for narrative flow
        if 20 < duration < 60:
            score += 10
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
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 🟢 EXPERT CACHE VALIDATION: Prevent using old transcript for new video
                cached_source = data.get('source_video_path')
                if cached_source == os.path.abspath(video_path):
                    print(f"[Log] Using valid cached transcript for: {video_path}")
                    return transcript_path
                else:
                    print(f"[Warning] Session Cache Mismatch: Old={cached_source}, New={os.path.abspath(video_path)}. Re-transcribing...")
        except:
            pass
        
    print(f"[Log] Starting AI Transcription (GPU Optimized - MEDIUM Model)...")
    start_time = time.time()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # 🟢 UPGRADE: 'medium' model provides significantly better punctuation and nuance
    model = whisper.load_model("medium", device=device) 
    result = model.transcribe(video_path, language="en")
    
    # Save the full result with source metadata
    print(f"[Log] Saving transcript to {transcript_path}...")
    # Add metadata to the whisper result before saving
    result_dict = result.to_dict() if hasattr(result, 'to_dict') else result
    if isinstance(result_dict, dict):
        result_dict['source_video_path'] = os.path.abspath(video_path)
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2)
    else:
        # Fallback if stable_whisper result is weird
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
        score_diff = abs(curr.get('final_score', 0) - next_seg.get('final_score', 0))
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

def identify_highlights(transcript_path, video_path=None, clip_count=5, mode="shorts", target_duration=None, use_audio_detect=False, style=None, user_context=None, style_context=None):
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

    if mode == "EXPLAINER":
        print("[Log] Mode: EXPLAINER. Extracting topic segment for Manim animation.")
        return [{
            "start": 0.0, 
            "end": min(total_duration, target_duration or 60), 
            "viral_score": 100, 
            "reason": "Explainer Animation Block"
        }]

    # 🟢 EXPERT REFINEMENT: transcript compression logic
    if mode == "shorts":
        # Shorts: Small windows (25-60s) for punchy peaks
        window_size = float(max(25.0, min(60.0, (target_duration or 15.0) * 1.5)))
    else:
        # Long-form: Narrative windows (45-120s) to allow for story flow
        # Capping at 120s prevents the AI from being forced into picking massive blocks
        window_size = float(max(45.0, min(120.0, (target_duration or 300.0) / 5.0)))
        
    print(f"[Log] Mode: {mode} | Target: {target_duration}s | Window: {window_size}s")
    print(f"[Log] Compressing {len(segments)} fragments into {window_size}s context windows...")
    compressed_segments = compress_transcript(segments, window=window_size)
    
    # 🟢 PHASE 0: Parallel Analysis (Outline + Audio)
    from concurrent.futures import ThreadPoolExecutor
    video_outline = ""
    audio_full = None
    sr = 16000
    global_audio_features = None

    def get_outline():
        if video_path:
            try:
                print("[Log] Generating video outline (Parallel)...")
                return extract_video_outline(transcript_path)
            except: return ""
        return ""

    def get_audio():
        nonlocal use_audio_detect
        if use_audio_detect and video_path:
            try:
                wav_path = extract_audio_mono(video_path, os.path.dirname(transcript_path))
                print(f"[Log] Loading audio for analysis (Parallel)...")
                import librosa
                a, s = librosa.load(wav_path, sr=sr)
                g = compute_global_audio_features(a, s)
                return a, s, g
            except Exception as e:
                print(f"[Warning] Audio analysis failed: {e}")
                use_audio_detect = False
        return None, 16000, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_outline = executor.submit(get_outline)
        f_audio = executor.submit(get_audio)
        
        video_outline = f_outline.result()
        audio_full, sr, global_audio_features = f_audio.result()

    # 🟢 PHASE 2: Signal Pre-Ranking (Text + Audio)
    ENERGY_ALPHA = 0.3
    energy_baseline = None
    prev_energy = None
    for i, seg in enumerate(compressed_segments):
        seg['score'] = score_segment(seg['text'], mode=mode, start=seg['start'], end=seg['end'], target_duration=target_duration)
        seg['audio_score'] = 0
        if use_audio_detect and audio_full is not None:
            s_idx = int(seg['start'] * sr)
            e_idx = int(seg['end'] * sr)
            chunk = audio_full[s_idx:e_idx]
            a_score, raw_energy, s_ratio, v_silence = compute_audio_score(
                chunk, sr, prev_energy=prev_energy, 
                global_features=global_audio_features, start_sec=seg['start'], 
                end_sec=seg['end'], energy_baseline=energy_baseline
            )
            seg['audio_score'] = round(a_score, 3)
            seg['silence_ratio'] = s_ratio
            seg['valid_silence'] = v_silence
            if energy_baseline is None: energy_baseline = raw_energy
            else: energy_baseline = ENERGY_ALPHA * raw_energy + (1 - ENERGY_ALPHA) * energy_baseline
            prev_energy = raw_energy

    # 🟢 PHASE 16: Motion Analysis (on Pre-Ranked Candidates)
    if video_path:
        try:
            print("[Log] Analyzing visual motion on candidate segments...")
            candidates = sorted(compressed_segments, key=lambda x: x.get('score', 0) + x.get('audio_score', 0), reverse=True)[:100]
            candidate_intervals = [(c['start'], c['end']) for c in candidates]
            
            motion_intervals = detect_motion_intervals(video_path, candidate_intervals=candidate_intervals)
            for seg in compressed_segments:
                seg['motion_score'] = 0
                for m_start, m_end in motion_intervals:
                    overlap_s = max(seg['start'], m_start)
                    overlap_e = min(seg['end'], m_end)
                    if overlap_e > overlap_s:
                        seg['motion_score'] += (overlap_e - overlap_s) / (seg['end'] - seg['start'])
                seg['motion_score'] = min(1.0, seg['motion_score'])
        except Exception as e:
            print(f"[Warning] Outline/Motion analysis failed: {e}")

    # 🟢 PHASE 2: Final Signal & Delta (Contrast) Detection
    # Now that we have all signals (Text, Audio, Motion), we calculate context-aware deltas.
    for i, seg in enumerate(compressed_segments):
        # 🟢 NEW: Silence Delta (Viral signal for sudden sound after pause)
        if i > 0:
            seg['delta'] = abs(seg['score'] - compressed_segments[i-1]['score'])
            prev_audio = compressed_segments[i-1].get('audio_score', 0)
            seg['audio_delta'] = abs(seg['audio_score'] - prev_audio)
            
            # Robust silence delta check
            if seg.get('valid_silence', True):
                prev_silence = compressed_segments[i-1].get('silence_ratio', 0)
                seg['silence_delta'] = abs(seg.get('silence_ratio', 0) - prev_silence)
            else:
                seg['silence_delta'] = 0
        else:
            seg['delta'] = 0
            seg['audio_delta'] = 0
            seg['silence_delta'] = 0

    # 🟢 EXPERT REFINEMENT: Robust Signal Normalization (v2)
    def get_robust_max(values):
        if not values: return 1.0
        p95 = np.percentile(values, 95)
        p50 = np.percentile(values, 50)
        return max(0.1, p95, p50 * 2)

    max_orig_score = get_robust_max([s['score'] for s in compressed_segments])
    max_audio_score = get_robust_max([s['audio_score'] for s in compressed_segments])
    max_delta = get_robust_max([s['delta'] for s in compressed_segments])
    max_motion = get_robust_max([s.get('motion_score', 0) for s in compressed_segments])
    max_audio_delta = get_robust_max([s.get('audio_delta', 0) for s in compressed_segments])
    max_silence_delta = get_robust_max([s.get('silence_delta', 0) for s in compressed_segments])
    
    # 🟢 ADAPTIVE WEIGHTING: Motion can overpower dialogue in non-action videos (Moved out of loop)
    avg_motion = sum(s.get('motion_score', 0) for s in compressed_segments) / len(compressed_segments) if compressed_segments else 0
    motion_weight = 0.25 if avg_motion > 0.3 else 0.15
    audio_weight = 0.30 if motion_weight == 0.15 else 0.20

    for seg in compressed_segments:
        seg['norm_score'] = round(min(1.0, seg['score'] / max_orig_score), 2)
        seg['norm_audio'] = round(min(1.0, seg['audio_score'] / max_audio_score), 2)
        seg['norm_delta'] = round(min(1.0, seg['delta'] / max_delta), 2)
        seg['norm_motion'] = round(min(1.0, seg.get('motion_score', 0) / max_motion), 2)
        seg['norm_audio_delta'] = round(min(1.0, seg.get('audio_delta', 0) / max_audio_delta), 2)
        
        if seg.get('valid_silence', True):
            seg['norm_silence_delta'] = round(min(1.0, seg.get('silence_delta', 0) / max_silence_delta), 2) if max_silence_delta > 0 else 0
        else:
            seg['norm_silence_delta'] = 0

        # combined_signal: Text(35%) + Audio(Adaptive) + Motion(Adaptive) + Deltas(20%)
        combined_signal = (
            seg['norm_score'] * 0.35 + 
            seg['norm_audio'] * audio_weight + 
            seg['norm_motion'] * motion_weight +
            seg['norm_delta'] * 0.10 + 
            seg['norm_audio_delta'] * 0.10
        )
        pos = round(seg['start'] / total_duration, 2) if total_duration > 0 else 0
        seg['pruning_score'] = combined_signal * (0.8 + 0.4 * pos)
            
    # 🟢 PHASE 15: Peak Sharpening (Local Maxima Boost)
    for i in range(1, len(compressed_segments)-1):
        prev_p = compressed_segments[i-1]['pruning_score']
        curr_p = compressed_segments[i]['pruning_score']
        nxt_p  = compressed_segments[i+1]['pruning_score']
        if curr_p > prev_p and curr_p > nxt_p:
            compressed_segments[i]['pruning_score'] *= 1.2
            
    # 🟢 EXPERT REFINEMENT: Updated Context Window & Limit
    context_window = 3 
    limit = 100 
    
    if len(compressed_segments) > limit:
        if mode == "long":
            # 🟢 NEW: Ensure representation across the entire timeline
            # Instead of top 75 absolute peaks, take top N from every 10% of video
            seeds_per_decile = max(4, (limit // 2) // 10)
            chunk_size = len(compressed_segments) // 10
            distributed_indices = []
            
            for d in range(10):
                start_bin = d * chunk_size
                end_bin = (d + 1) * chunk_size if d < 9 else len(compressed_segments)
                if start_bin >= end_bin: continue
                
                # 🟢 NARRATIVE: Remove absolute quality threshold to prevent story gaps
                bin_candidates = range(start_bin, end_bin)
                
                # Best peaks in this 10% of the video
                bin_indices = sorted(bin_candidates, key=lambda i: compressed_segments[i]['pruning_score'], reverse=True)
                distributed_indices.extend(bin_indices[:seeds_per_decile])
            
            top_indices = sorted(list(set(distributed_indices)))
        else:
            top_indices = sorted(range(len(compressed_segments)), key=lambda i: compressed_segments[i]['pruning_score'], reverse=True)[:limit//2]
        
        selected_indices = set()
        for i in top_indices:
            # Include context window 
            for offset in range(-context_window, context_window + 1):
                idx = i + offset
                if 0 <= idx < len(compressed_segments):
                    selected_indices.add(idx)
        
        compressed_segments = [compressed_segments[i] for i in sorted(list(selected_indices))]
    
    full_text_with_ts = ""
    for segment in compressed_segments:
        # 🟢 UPGRADE: Enriched signal richness for LLM
        # pos=timeline position, t=text, d=text_delta, a=audio, ad=audio_delta, sd=silence_delta
        pos = round(segment['start'] / total_duration, 2) if total_duration > 0 else 0
        sigs = f"pos={pos} t={segment['norm_score']} d={segment['norm_delta']} a={segment['norm_audio']} ad={segment['norm_audio_delta']} sd={segment['norm_silence_delta']}"
        full_text_with_ts += f"[{segment['start']:.2f}s - {segment['end']:.2f}s | {sigs}]: {segment['text']}\n"
    
    # Style-specific injections (Handle list or string)
    styles_list = style if isinstance(style, list) else ([style] if style else [])
    
    style_instr_parts = []
    if "sarcastic" in styles_list:
        style_instr_parts.append("FOCUS: Identify moments that are ironic, eye-rolling, or 'facepalm' fails.")
    if "action" in styles_list:
        style_instr_parts.append("FOCUS: Identify 'Action Peaks'—climactic battles, boss fights, or high-intensity gameplay moments.")
    if "meme" in styles_list:
        style_instr_parts.append("FOCUS: Identify moments with high meme potential—funny reactions or bizarre occurrences.")
    if "funny" in styles_list:
        style_instr_parts.append("FOCUS: Identify funny dialogue, situational comedy, or humorous fails.")
    
    style_instructions = " ".join(style_instr_parts)

    context_injection = ""
    if user_context:
        context_injection = f"\nUSER EXTRA CONTEXT: {user_context}\n(PRIORITIZE moments that match this context while maintaining virality rules.)"
        
    style_injection = ""
    if style_context:
        style_injection = f"\nEDITING STYLE CONTEXT: {style_context}\n(Follow this editing/pacing style for the selected moments.)"

    outline_injection = ""
    # 🟢 ADAPTIVE OUTLINE: Only include for long videos and label as low priority
    if video_outline and total_duration > 1800: # > 30 mins
        outline_injection = f"\n[LOW PRIORITY CONTEXT - MAY BE NOISY]:\n{video_outline}\n"

    if mode == "shorts":
        system_prompt = f"You are a professional social media manager. Identify high-impact viral moments. {style_instructions} {context_injection} {style_injection} {outline_injection} YOU MUST PROVIDE TIMESTAMPS FOR EVERY CLIP."
        prompt = f"""Objective: Identify up to {clip_count} distinct viral moments for YouTube Shorts.
        
        {context_injection}
        {style_injection}
        {outline_injection}
        
        VIRALITY SIGNALS (Look for high 'signal' or high 'delta' in the log):
        1. High Signal: Intense yelling, punctuation, or shock keywords.
        2. High Delta (d_signal): Sudden shifts in intensity/tone (very viral!).
        3. Audio Spikes (a_signal): Emotional peaks even if text is neutral.
        
        CRITICAL RULES FOR WATCHABILITY:
        - **CLIP COUNT**: You MUST identify and extract exactly {clip_count} distinct viral clips (or as close to {clip_count} as possible, aiming for at least 12-15) covering different parts of the video. If the USER EXTRA CONTEXT mentions multiple scenes, timestamps, or parts, you MUST extract multiple separate, distinct clips for EACH requested scene/timestamp to meet the requested count. Do not be overly selective; include all moments of action, humor, or banter.
        - **HOOK FIRST**: The first 2 seconds of each clip MUST have a visual or audio 'hook'. Look for segments where 'ad' (audio delta) or 'd' (text delta) is high right at the 'start' timestamp.
        - **VIRALITY**: Prioritize high-energy, funny, or shocking moments. {style_instructions}
        - **ENGAGEMENT**: Each moment MUST be between {max(5, (target_duration or 15)-15)} and {min(59, (target_duration or 45)+15)} seconds long.
        - **TARGET**: Specifically aim for moments around {min(58, target_duration or 30)}s each for maximum flow. NEVER exceed 60 seconds.
        - **MANDATORY**: 'start' and 'end' timestamps MUST be provided as numbers (float/seconds).
        - **MANDATORY**: For each clip, provide a 'hook_text' (under 10 words).
        - **MANDATORY**: For each clip, identify the 'tone' (one of: action_peak, funny, fail, tense, educational, neutral).
        - **MANDATORY**: For each clip, provide a 'viral_score' (integer between 1 and 100, representing virality/engagement potential).
        - REJECT: slow setups, generic intros, filler conversation.
        - Wrap JSON array in START_JSON and END_JSON markers.
        
        Log Data (Signal/Delta marked):
        {full_text_with_ts}"""
    else: # Long-Form Highlight Reel
        context_injection = ""
        if user_context:
            context_injection = f"\nUSER EXTRA CONTEXT: {user_context}\n(ENSURE these specific parts/styles are included in the summary reel.)"
            
        style_injection = ""
        if style_context:
            style_injection = f"\nEDITING STYLE CONTEXT: {style_context}\n(Ensure the summary reel follows this specific narrative/pacing vibe.)"

        system_prompt = f"You are a narrative editor. Provide TIMESTAMPS for all story beats. {context_injection} {style_injection}"
        if target_duration and target_duration > 1200:
            avg_seg_dur = 65 
            segment_target = int(target_duration / avg_seg_dur)
            dur_msg = "Each segment MUST be between 45 and 95 seconds."
        else:
            avg_seg_dur = 35  # More segments → better chance of reaching target duration
            segment_target = int((target_duration or 300) / avg_seg_dur)
            dur_msg = f"Each segment MUST be between 20 and 90 seconds. Do NOT return segments shorter than 20 seconds. You MUST reach {target_duration}s total."
        
        segment_target = max(8, min(segment_target, 250))
        prompt = f"""Objective: Generate a cohesive narrative summary reel.
        {context_injection}
        {style_injection}
        
        Aim to identify approximately {segment_target} key segments to reach the target duration of {target_duration}s.
        Ensure you cover the story comprehensively. Do not be overly selective; include all meaningful story beats and reactions.
        
        WATCHABILITY & RETENTION:
        - **REACTION HOOKS**: Include segments with high 'ad' (audio delta) as these often represent the most watchable reactions.
        - **NARRATIVE FLOW**: Ensure the 'start' of each segment feels like a fresh beat or hook.
        - **MANDATORY**: For each clip, provide a 'hook_text' (short teaser for the clip).

        SIGNAL GUIDE:
        - t: Narrative density / flow
        - d: Signal change (important beat)
        - a: Audio intensity
        - ad: Sudden audio spike (VERY important for reactions/hooks)
        - sd: Silence to sound transition (highly viral hook potential)
        
        STRICT RULES:
        1. Wrap JSON in START_JSON and END_JSON.
        2. Provide 'viral_score' (0-100) and 'hook_text' for each.
        3. MANDATORY: include 'start' and 'end' timestamps.
        4. RAW JSON ONLY. NO EXTRA TEXT.
        
        Log Data (Signal/Delta marked):
        [OUTLINE]: {video_outline}
        
        {full_text_with_ts}
        
        MANDATORY: Return a JSON LIST of objects. Even if only one moment is found, wrap it in []."""

    try:
        # 🟢 HEARTBEAT: Clear logging for user visibility on long runs
        print(f"[Log] Sending {len(compressed_segments)} logic-filtered segments to LLM for viral curation...")
        print(f"[Log] This may take up to 2-3 minutes for large 60+ min videos. Please wait...")
        
        # 🟢 PERFORMANCE: Set dynamic_max to 8192 to prevent Gemini token truncation
        dynamic_max = 8192
        
        response_text = get_llm_response(prompt, system_prompt, max_tokens=dynamic_max)
        print(f"[DEBUG] Raw LLM Response: {response_text}")
        print(f"[Log] LLM analysis received ({len(response_text)} chars). Processing results...")
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
        min_floor = 8.0 if mode == "shorts" else 15.0 # Lowered for narrative flexibility
        
        if isinstance(highlights, list) and highlights:
            for h in highlights:
                if isinstance(h, dict) and 'start' in h and 'end' in h:
                    try:
                        h['start'] = float(h['start'])
                        h['end'] = float(h['end'])
                    except (ValueError, TypeError):
                        continue
                    v_score = h.get('viral_score', 0)
                    if isinstance(v_score, str): v_score = int(''.join(filter(str.isdigit, v_score)) or 0)
                    h['viral_score'] = v_score
                    
                    # 🟢 EXPERT REFINEMENT: Hybrid Signal Ranking (v3)
                    # Align with pruning logic signals for consistency
                    relevant_segs = [s for s in compressed_segments if not (s['end'] < h['start'] or s['start'] > h['end'])]
                    if relevant_segs:
                        avg_norm_score = sum(s['norm_score'] for s in relevant_segs) / len(relevant_segs)
                        avg_norm_audio = sum(s['norm_audio'] for s in relevant_segs) / len(relevant_segs)
                        avg_norm_motion = sum(s['norm_motion'] for s in relevant_segs) / len(relevant_segs)
                        avg_norm_delta = sum(s['norm_delta'] for s in relevant_segs) / len(relevant_segs)
                        avg_norm_ad    = sum(s['norm_audio_delta'] for s in relevant_segs) / len(relevant_segs)
                        avg_norm_sd    = sum(s['norm_silence_delta'] for s in relevant_segs) / len(relevant_segs)
                        
                        combined_signal = (
                            avg_norm_score * 0.35 + 
                            avg_norm_audio * 0.20 + 
                            avg_norm_motion * 0.25 +
                            avg_norm_delta * 0.10 + 
                            avg_norm_ad    * 0.10
                        )
                        h['final_score'] = (v_score * 0.7) + (combined_signal * 100 * 0.3)
                    else:
                        h['final_score'] = v_score
                    
                    valid_highlights.append(h)
                elif isinstance(h, (list, tuple)) and len(h) >= 2:
                    valid_highlights.append({"start": float(h[0]), "end": float(h[1]), "viral_score": 50, "final_score": 50, "reason": "Action Sequence"})
            
            # 🟢 NEW FLOW: Merge adjacent parts BEFORE trimming to count
            effective_target = target_duration if target_duration else 60.0
            max_merge_dur = min(59.9, effective_target) if mode == "shorts" else 150.0 # Strict cap for shorts
            print(f"[Log] Merging adjacent highlights (score-aware, max={max_merge_dur}s)...")
            valid_highlights = merge_segments(valid_highlights, min_gap=8.0, max_dur=max_merge_dur, score_sensitive=True)
            
            # 🟢 STABILITY: Strict Duration Truncation for Shorts
            if mode == "shorts":
                for h in valid_highlights:
                    actual_dur = h['end'] - h['start']
                    if actual_dur > max_merge_dur:
                        print(f"[Warning] Truncating segment from {actual_dur:.1f}s to {max_merge_dur}s")
                        h['end'] = h['start'] + max_merge_dur
            
            # 🟢 OPUS-STYLE SORTING: Prioritize high hybrid scores
            valid_highlights.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            
            # Limit segments for shorts mode AFTER merge to keep only the best substantial clips
            if mode == "shorts":
                valid_highlights = valid_highlights[:clip_count]
            elif mode == "long" and target_duration:
                # 🟢 EXPERT REFINEMENT: Soft Duration Capping for Highlight Reels
                valid_highlights.sort(key=lambda x: x.get('final_score', 0), reverse=True)
                capped_highlights = []
                current_total = 0
                for h in valid_highlights:
                    dur = h['end'] - h['start']
                    if current_total < target_duration * 1.3: # Allow 30% overage for impact
                        capped_highlights.append(h)
                        current_total += dur
                    else:
                        break
                valid_highlights = capped_highlights
                
                # 🟢 FILL-UP: Backfill from pruned segments if LLM under-delivered
                current_total = sum(h['end'] - h['start'] for h in valid_highlights)
                if current_total < target_duration * 0.95:
                    print(f"[Log] Duration shortfall ({current_total:.0f}s < {target_duration}s). Backfilling from signal peaks...")
                    used_ranges = [(h['start'], h['end']) for h in valid_highlights]
                    for seg in sorted(compressed_segments, key=lambda x: x['pruning_score'], reverse=True):
                        overlaps = any(not (seg['end'] < u[0] or seg['start'] > u[1]) for u in used_ranges)
                        seg_dur = seg['end'] - seg['start']
                        if overlaps or seg_dur < 15: continue
                        valid_highlights.append({'start': seg['start'], 'end': seg['end'],
                            'viral_score': int(seg['pruning_score'] * 100),
                            'final_score': int(seg['pruning_score'] * 100), 'reason': 'Signal Peak (Backfill)'})
                        used_ranges.append((seg['start'], seg['end']))
                        current_total += seg_dur
                        if current_total >= target_duration * 1.05: break
                    print(f"[Log] After backfill: {current_total:.0f}s, {len(valid_highlights)} segments")
            
            # 🟢 MANDATORY: Re-sort chronologically to ensure narrative flow and fix timing mismatch
            # This ensures that even if we picked top scores, they play back in order.
            valid_highlights.sort(key=lambda x: x['start'])
            
            # Final filter by floor
            valid_highlights = [h for h in valid_highlights if (h['end'] - h['start']) >= min_floor]
        
        if not valid_highlights:
            print("[Warning] LLM analysis failed. Using Heuristic Signal Fallback (Top Peaks)...")
            # 🟢 DYNAMIC RECOVERY: Use top heuristic signal peaks (Text + Audio)
            fallback_candidates = sorted(compressed_segments, key=lambda x: x['norm_score'] + x.get('norm_audio', 0), reverse=True)
            
            if mode == "long" and target_duration:
                accumulated_duration = 0
                for f in fallback_candidates:
                    seg_dur = f['end'] - f['start']
                    if accumulated_duration >= target_duration:
                        break
                    valid_highlights.append({
                        "start": f['start'],
                        "end": f['end'],
                        "viral_score": int(f['norm_score'] * 100),
                        "final_score": int(f['norm_score'] * 100),
                        "reason": "High-Signal Moment (Heuristic Fallback)"
                    })
                    accumulated_duration += seg_dur
            else:
                for f in fallback_candidates[:clip_count]:
                    valid_highlights.append({
                        "start": f['start'],
                        "end": f['end'],
                        "viral_score": int(f['norm_score'] * 100),
                        "final_score": int(f['norm_score'] * 100),
                        "reason": "High-Signal Moment (Heuristic Fallback)"
                    })
            
            valid_highlights.sort(key=lambda x: x['start'])
            valid_highlights = deduplicate_highlights(valid_highlights)

        if not valid_highlights:
            # 🟢 ABSOLUTE FAILSAFE: Simple duration-based slice
            fallback_start = min(45.0, total_duration * 0.1)
            fallback_duration = 35.0 if mode == "shorts" else (target_duration or 180.0)
            return [{"start": fallback_start, "end": fallback_start + fallback_duration, "viral_score": 85, "hook_text": "Check this out!", "reason": "Draft Extraction (Failsafe)"}]
        
        # Final deduplication check
        valid_highlights = deduplicate_highlights(valid_highlights)
        print(f"[Log] Curation complete: Selected {len(valid_highlights)} high-viral deduplicated segments.")
        return valid_highlights
    except Exception as e:
        print(f"[Error] Highlight identification failed: {e}")
        import traceback
        traceback.print_exc()
        return [{"start": 10.0, "end": 40.0, "viral_score": 80, "hook_text": "Epic Moment", "reason": "Epic Highlight"}]

def deduplicate_highlights(highlights, min_overlap_sec=5.0):
    """
    Deduplicates overlapping highlight clips by comparing time ranges.
    When two clips overlap significantly (>= min_overlap_sec),
    keeps the candidate with the higher viral_score / final_score.
    """
    if not highlights or len(highlights) <= 1:
        return highlights

    # Sort by score descending so higher-rated clips take priority
    sorted_highlights = sorted(
        highlights, 
        key=lambda x: float(x.get('viral_score', x.get('final_score', 80)) or 80), 
        reverse=True
    )
    
    kept = []
    for candidate in sorted_highlights:
        cand_start = float(candidate['start'])
        cand_end = float(candidate['end'])
        
        is_overlapping = False
        for existing in kept:
            ex_start = float(existing['start'])
            ex_end = float(existing['end'])
            
            # Calculate overlap duration
            overlap_start = max(cand_start, ex_start)
            overlap_end = min(cand_end, ex_end)
            overlap_duration = max(0.0, overlap_end - overlap_start)
            
            if overlap_duration >= min_overlap_sec:
                is_overlapping = True
                break
                
        if not is_overlapping:
            kept.append(candidate)
            
    # Re-sort chronologically by start time for natural playback order
    kept.sort(key=lambda x: float(x['start']))
    return kept

def process_source_video(video_path, output_dir, mode="shorts", clip_count=5, target_duration=None, use_audio_detect=False, style=None, user_context=None, style_context=None, smart_crop=False, tighten=False, use_cache=False, chapters_path=None, use_llm_scoring=True):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video Not Found: {video_path}")

    transcript_path = transcribe_video(video_path, output_dir)

    # Load YouTube chapters if available
    chapters = []
    if chapters_path:
        chapters = extract_youtube_chapters(chapters_path)

    highlights_cache_path = os.path.join(output_dir, "highlights.json")
    highlights = None
    if use_cache and os.path.exists(highlights_cache_path):
        try:
            with open(highlights_cache_path, "r", encoding="utf-8") as f:
                highlights = json.load(f)
            print(f"[Log] Loaded cached highlights from {highlights_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to load cached highlights: {e}")

    if highlights is None:
        highlights = identify_highlights(
            transcript_path, video_path=video_path, clip_count=clip_count,
            mode=mode, target_duration=target_duration, use_audio_detect=use_audio_detect,
            style=style, user_context=user_context, style_context=style_context
        )

        # Boost chapter-overlapping segments
        if chapters:
            print(f"[Log] Applying chapter-based score boosting to {len(highlights)} candidates...")
            for h in highlights:
                hs, he = float(h['start']), float(h['end'])
                for ch in chapters:
                    cs, ce = ch['start'], ch['end']
                    overlap = max(0, min(he, ce) - max(hs, cs))
                    if overlap > 2.0:  # At least 2s overlap with a chapter
                        h['score'] = float(h.get('score', 0)) + 25
                        h['reason'] = h.get('reason', '') + f" [Chapter: {ch['title']}]"
                        break
            highlights.sort(key=lambda x: float(x.get('score', 0)), reverse=True)

        # LLM virality scoring
        if use_llm_scoring:
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript_data = json.load(f)
                highlights = llm_score_highlights(highlights, transcript_data)
            except Exception as e:
                print(f"[Warning] LLM scoring skipped: {e}")

        try:
            with open(highlights_cache_path, "w", encoding="utf-8") as f:
                json.dump(highlights, f, indent=4)
            print(f"[Log] Saved highlights to cache: {highlights_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache highlights: {e}")

    interest_points_cache_path = os.path.join(output_dir, "interest_points.json")
    interest_points = {}
    interest_points_loaded = False
    if use_cache and smart_crop and os.path.exists(interest_points_cache_path):
        try:
            with open(interest_points_cache_path, "r", encoding="utf-8") as f:
                raw_pts = json.load(f)
                interest_points = {float(k): v for k, v in raw_pts.items()}
            interest_points_loaded = True
            print(f"[Log] Loaded cached interest points from {interest_points_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to load cached interest points: {e}")

    if smart_crop and not interest_points_loaded:
        highlight_intervals = [(h['start'], h['end']) for h in highlights]
        print(f"[Log] Extracting interest points for {len(highlights)} segments (Auto-Crop with IoU Speaker Lock)...")
        interest_points = detect_interest_points(video_path, segments=highlight_intervals)
        try:
            with open(interest_points_cache_path, "w", encoding="utf-8") as f:
                json.dump(interest_points, f, indent=4)
            print(f"[Log] Saved interest points to cache: {interest_points_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache interest points: {e}")
    elif not smart_crop:
        print("[Log] Smart crop disabled. Skipping interest point detection to speed up extraction.")

    silence_intervals_cache_path = os.path.join(output_dir, "silence_intervals.json")
    silence_intervals = []
    silence_intervals_loaded = False
    if use_cache and tighten and os.path.exists(silence_intervals_cache_path):
        try:
            with open(silence_intervals_cache_path, "r", encoding="utf-8") as f:
                raw_silence = json.load(f)
                silence_intervals = [tuple(item) for item in raw_silence]
            silence_intervals_loaded = True
            print(f"[Log] Loaded cached silence intervals from {silence_intervals_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to load cached silence intervals: {e}")

    if tighten and not silence_intervals_loaded:
        print("[Log] Extracting silence intervals for Auto-Edit...")
        audio_path = os.path.join(output_dir, "audio_mono.wav")
        if not os.path.exists(audio_path):
            audio_path = extract_audio_mono(video_path, output_dir)
        silence_intervals = detect_silence_intervals(audio_path)
        try:
            with open(silence_intervals_cache_path, "w", encoding="utf-8") as f:
                json.dump(silence_intervals, f, indent=4)
            print(f"[Log] Saved silence intervals to cache: {silence_intervals_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache silence intervals: {e}")
    elif not tighten:
        print("[Log] Tighten (silence removal) disabled. Skipping silence interval detection to speed up extraction.")

    return highlights, transcript_path, interest_points, silence_intervals

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video Not Found: {video_path}")
    
    transcript_path = transcribe_video(video_path, output_dir)
    
    highlights_cache_path = os.path.join(output_dir, "highlights.json")
    highlights = None
    if use_cache and os.path.exists(highlights_cache_path):
        try:
            with open(highlights_cache_path, "r", encoding="utf-8") as f:
                highlights = json.load(f)
            print(f"[Log] Loaded cached highlights from {highlights_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to load cached highlights: {e}")
            
    if highlights is None:
        highlights = identify_highlights(
            transcript_path, video_path=video_path, clip_count=clip_count, 
            mode=mode, target_duration=target_duration, use_audio_detect=use_audio_detect,
            style=style, user_context=user_context, style_context=style_context
        )
        try:
            with open(highlights_cache_path, "w", encoding="utf-8") as f:
                json.dump(highlights, f, indent=4)
            print(f"[Log] Saved highlights to cache: {highlights_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache highlights: {e}")
    
    # 🟢 UPGRADE: Extra AI Signals for Auto-Edit & Auto-Crop (Optimized)
    interest_points_cache_path = os.path.join(output_dir, "interest_points.json")
    interest_points = {}
    interest_points_loaded = False
    if use_cache and smart_crop and os.path.exists(interest_points_cache_path):
        try:
            with open(interest_points_cache_path, "r", encoding="utf-8") as f:
                raw_pts = json.load(f)
                interest_points = {float(k): v for k, v in raw_pts.items()}
            interest_points_loaded = True
            print(f"[Log] Loaded cached interest points from {interest_points_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to load cached interest points: {e}")
            
    if smart_crop and not interest_points_loaded:
        highlight_intervals = [(h['start'], h['end']) for h in highlights]
        print(f"[Log] Extracting interest points for {len(highlights)} segments (Auto-Crop)...")
        interest_points = detect_interest_points(video_path, segments=highlight_intervals)
        try:
            with open(interest_points_cache_path, "w", encoding="utf-8") as f:
                json.dump(interest_points, f, indent=4)
            print(f"[Log] Saved interest points to cache: {interest_points_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache interest points: {e}")
    elif not smart_crop:
        print("[Log] Smart crop disabled. Skipping interest point detection to speed up extraction.")
    
    silence_intervals_cache_path = os.path.join(output_dir, "silence_intervals.json")
    silence_intervals = []
    silence_intervals_loaded = False
    if use_cache and tighten and os.path.exists(silence_intervals_cache_path):
        try:
            with open(silence_intervals_cache_path, "r", encoding="utf-8") as f:
                raw_silence = json.load(f)
                silence_intervals = [tuple(item) for item in raw_silence]
            silence_intervals_loaded = True
            print(f"[Log] Loaded cached silence intervals from {silence_intervals_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to load cached silence intervals: {e}")
            
    if tighten and not silence_intervals_loaded:
        print("[Log] Extracting silence intervals for Auto-Edit...")
        audio_path = os.path.join(output_dir, "audio_mono.wav")
        if not os.path.exists(audio_path): 
            audio_path = extract_audio_mono(video_path, output_dir)
        silence_intervals = detect_silence_intervals(audio_path)
        try:
            with open(silence_intervals_cache_path, "w", encoding="utf-8") as f:
                json.dump(silence_intervals, f, indent=4)
            print(f"[Log] Saved silence intervals to cache: {silence_intervals_cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache silence intervals: {e}")
    elif not tighten:
        print("[Log] Tighten (silence removal) disabled. Skipping silence interval detection to speed up extraction.")
    
    return highlights, transcript_path, interest_points, silence_intervals
