"""
Active-speaker reframing for 2-person clips (podcasts, interviews) - issue #27.

Pipeline per clip:
  1. Sample frames (~5 fps), detect faces with OpenCV and assign them to a LEFT / RIGHT slot.
  2. Mouth-motion energy per slot (frame difference in the lower part of the face box),
     weighted by the clip's audio loudness envelope so nodding/chewing during silence doesn't count.
  3. Decide who is talking per sample; low confidence means "both" (stacked split).
  4. Turn that into shots with a minimum dwell time so the camera never flip-flops.

Each shot uses a static crop, so there is no camera shake; cuts happen only between shots.
"""

import os
import subprocess

import numpy as np

MIN_DWELL = 2.5          # seconds a shot must last before the camera may cut
SWITCH_PERSIST = 0.6     # seconds a new speaker must be consistently detected before cutting to them
CONFIDENCE = 0.25        # (top - second) / (top + second) mouth-score margin needed to trust a speaker
SAMPLE_FPS = 5.0
SINGLE_ZOOM = 1.25       # slight push-in on the active speaker
SPLIT_ZOOM = 1.8         # tighter crop per half in the stacked view so faces aren't tiny


def _audio_envelope(video_path, start, end, sample_fps, ffmpeg_exe):
    """RMS loudness per sample interval, normalised to 0..1."""
    sr = 16000
    cmd = [ffmpeg_exe, "-v", "error", "-ss", str(start), "-t", str(end - start), "-i", video_path,
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    try:
        raw = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120).stdout
    except Exception:
        return None
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if pcm.size == 0:
        return None
    hop = int(sr / sample_fps)
    n = max(1, pcm.size // hop)
    rms = np.array([np.sqrt(np.mean(pcm[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    peak = np.percentile(rms, 95) or 1.0
    return np.clip(rms / peak, 0, 1)


ANALYSIS_WIDTH = 1280   # podcast wide shots have small faces; detect near full resolution
ANCHOR_TOLERANCE = 0.12 # max horizontal distance (fraction of width) from a speaker's anchor position


def _detect_faces(gray, cascades):
    """Frontal + profile (both directions) Haar detections - people in podcasts face each other."""
    import cv2
    frontal, profile = cascades
    w = gray.shape[1]
    boxes = [tuple(b) for b in frontal.detectMultiScale(gray, 1.08, 5, minSize=(24, 24))]
    boxes += [tuple(b) for b in profile.detectMultiScale(gray, 1.08, 5, minSize=(24, 24))]
    boxes += [(w - x - bw, y, bw, bh) for x, y, bw, bh in profile.detectMultiScale(cv2.flip(gray, 1), 1.08, 5, minSize=(24, 24))]
    return boxes


def _speaker_anchors(frames_boxes, width):
    """Two most frequent horizontal face positions across the clip (left speaker, right speaker)."""
    centers = [(x + w / 2) / width for boxes in frames_boxes for x, y, w, h in boxes]
    if not centers:
        return None
    hist, edges = np.histogram(centers, bins=20, range=(0, 1))
    order = np.argsort(hist)[::-1]
    first = order[0]
    second = next((b for b in order[1:] if abs(b - first) >= 4 and hist[b] > 0), None)  # >= 0.2 apart
    if second is None:
        return None
    peaks = sorted([first, second])
    anchors = []
    for b in peaks:
        near = [c for c in centers if abs(c - (edges[b] + 0.025)) <= ANCHOR_TOLERANCE]
        anchors.append(float(np.median(near)))
    return {"L": anchors[0], "R": anchors[1]}


def _sample_faces(video_path, start, end, sample_fps):
    """
    Returns (samples, anchors). samples: [{"t": seconds from clip start, "faces": {"L"/"R": mouth_energy}}],
    anchors: {"L": cx, "R": cx} in 0..1, or None if the clip doesn't show two people.
    """
    import cv2

    cascades = (cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")),
                cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_profileface.xml")))
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / sample_fps)))
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)

    # Pass 1: detect faces on sampled frames
    frames, frame_idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if t > end:
            break
        frame_idx += 1
        if (frame_idx - 1) % step:
            continue
        h, w = frame.shape[:2]
        if w > ANALYSIS_WIDTH:
            frame = cv2.resize(frame, (ANALYSIS_WIDTH, int(h * ANALYSIS_WIDTH / w)))
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        frames.append((t - start, gray, _detect_faces(gray, cascades)))
    cap.release()
    if not frames:
        return [], None

    width = frames[0][1].shape[1]
    anchors = _speaker_anchors([boxes for _, _, boxes in frames], width)
    if not anchors:
        return [], None

    # Pass 2: per speaker, take the detection nearest its anchor and measure mouth motion.
    # Boxes are smoothed so detector jitter (frontal vs profile boxes) doesn't read as mouth movement.
    samples, prev_mouths, smooth_box, face_y = [], {}, {}, {"L": [], "R": []}
    for t, gray, boxes in frames:
        entry = {}
        for slot, anchor in anchors.items():
            cands = [b for b in boxes if abs((b[0] + b[2] / 2) / width - anchor) <= ANCHOR_TOLERANCE]
            if not cands:
                continue
            box = np.array(min(cands, key=lambda b: abs((b[0] + b[2] / 2) / width - anchor)), dtype=np.float32)
            smooth_box[slot] = box if slot not in smooth_box else 0.3 * box + 0.7 * smooth_box[slot]
            fx, fy, fw, fh = (int(v) for v in smooth_box[slot])
            face_y[slot].append((fy + fh / 2) / gray.shape[0])
            mouth = gray[fy + int(fh * 0.6): fy + fh, fx + int(fw * 0.15): fx + int(fw * 0.85)]
            if mouth.size == 0:
                continue
            mouth = cv2.resize(mouth, (32, 16)).astype(np.float32)
            entry[slot] = float(np.mean(np.abs(mouth - prev_mouths[slot]))) if slot in prev_mouths else 0.0
            prev_mouths[slot] = mouth
        samples.append({"t": t, "faces": entry})
    # Vertical face centre per speaker, used to zoom the stacked split view onto faces
    anchors["y"] = {slot: float(np.median(ys)) if ys else 0.4 for slot, ys in face_y.items()}
    return samples, anchors


def plan_speaker_shots(video_path, start, end, ffmpeg_exe=None):
    """
    Returns a list of shots [{"start", "end", "target": "L"|"R"|"split", "cx": {"L": x, "R": x}}]
    with times relative to the clip start, or None when the clip doesn't look like a 2-person shot.
    """
    if ffmpeg_exe is None:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    samples, cx = _sample_faces(video_path, start, end, SAMPLE_FPS)
    if not samples or not cx:
        return None
    two_face_ratio = sum(1 for s in samples if len(s["faces"]) == 2) / len(samples)
    if two_face_ratio < 0.4:
        return None  # mostly single-speaker framing; the regular smart crop handles this better

    env = _audio_envelope(video_path, start, end, SAMPLE_FPS, ffmpeg_exe)

    # Normalise each speaker by their own typical motion, so a face that always looks "busier"
    # (angle, beard, detector jitter) doesn't win every comparison.
    for slot in ("L", "R"):
        vals = [s["faces"][slot] for s in samples if slot in s["faces"] and s["faces"][slot] > 0]
        base = float(np.median(vals)) if vals else 1.0
        for s in samples:
            if slot in s["faces"]:
                s["faces"][slot] /= base or 1.0

    # 1. Raw per-sample decision
    decisions = []
    for i, s in enumerate(samples):
        loud = float(env[min(i, len(env) - 1)]) if env is not None else 1.0
        scores = {slot: s["faces"][slot] * loud for slot in ("L", "R") if slot in s["faces"]}
        # One missing detection is usually a detector miss, not the person leaving - hold the shot
        if len(scores) == 2 and loud > 0.15:
            hi, lo = sorted(scores.values(), reverse=True)
            margin = (hi - lo) / (hi + lo + 1e-6)
            decisions.append(max(scores, key=scores.get) if margin >= CONFIDENCE else "split")
        else:
            decisions.append(None)  # silence / no faces: keep whatever is on screen

    # 2. Shots with minimum dwell and switch persistence
    shots = shots_from_decisions([s["t"] for s in samples], decisions, end - start)
    for shot in shots:
        shot["cx"] = cx
    return shots


def shots_from_decisions(times, decisions, duration, min_dwell=MIN_DWELL, switch_persist=SWITCH_PERSIST):
    """
    Turn per-sample speaker decisions ("L" / "R" / "split" / None = no opinion) into shots.
    Every shot lasts at least min_dwell seconds, and a new target must be seen consistently
    for switch_persist seconds before the camera cuts to it.
    """
    first = next((d for d in decisions if d), "split")
    shots = [{"start": 0.0, "target": first}]
    candidate, candidate_since = None, None
    for t, d in zip(times, decisions):
        current = shots[-1]
        if d is None or d == current["target"]:
            candidate = None
            continue
        if d != candidate:
            candidate, candidate_since = d, t
        if t - candidate_since >= switch_persist:
            cut = max(candidate_since, current["start"] + min_dwell)
            if cut <= t:
                shots.append({"start": cut, "target": d})
                candidate = None

    # Merge a too-short final shot into the previous one
    if len(shots) > 1 and duration - shots[-1]["start"] < min_dwell:
        shots.pop()
    for i, shot in enumerate(shots):
        shot["end"] = shots[i + 1]["start"] if i + 1 < len(shots) else duration
    return shots


def _face_crop(center_x, target_w, target_h, center_y=None, zoom=1.0):
    """
    Static crop of the source around a face centre, scaled to target size.
    zoom > 1 crops tighter (used for the stacked split, where each half is short and wide).
    """
    ratio = target_w / target_h
    ch = f"ih/{zoom:.3f}"
    cw = f"ih/{zoom:.3f}*{ratio:.5f}"
    x = f"'min(max(0,{center_x:.4f}*iw-({cw})/2),iw-({cw}))'"
    # Keep the face slightly above centre (headroom), clamped to the frame
    y = "0" if center_y is None else f"'min(max(0,{center_y:.4f}*ih-({ch})*0.42),ih-({ch}))'"
    return f"crop={cw}:{ch}:{x}:{y},scale={target_w}:{target_h},setsar=1"


def build_active_speaker_filter(shots, target_w=1080, target_h=1920):
    """FFmpeg -vf filtergraph that cuts between per-shot crops (single input, single output)."""
    n = len(shots)
    half_h = target_h // 2
    parts = [f"split={n}" + "".join(f"[in{i}]" for i in range(n))] if n > 1 else []
    for i, shot in enumerate(shots):
        src = f"[in{i}]" if n > 1 else ""
        end = "" if i == n - 1 else f":end={shot['end']:.3f}"
        trim = f"{src}trim=start={shot['start']:.3f}{end},setpts=PTS-STARTPTS"
        if shot["target"] == "split":
            parts.append(
                f"{trim},split=2[t{i}][b{i}];"
                f"[t{i}]{_face_crop(shot['cx']['L'], target_w, half_h, shot['cx']['y']['L'], SPLIT_ZOOM)}[tt{i}];"
                f"[b{i}]{_face_crop(shot['cx']['R'], target_w, half_h, shot['cx']['y']['R'], SPLIT_ZOOM)}[bb{i}];"
                f"[tt{i}][bb{i}]vstack=inputs=2[s{i}]"
            )
        else:
            who = shot["target"]
            parts.append(f"{trim},{_face_crop(shot['cx'][who], target_w, target_h, shot['cx']['y'][who], SINGLE_ZOOM)}[s{i}]")
    parts.append("".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,format=yuv420p")
    return ";".join(parts)
