"""Picture and sound checks on finished clips (the other half of the clip quality report; engine.clip_quality reads the transcript).

For each clip video it measures, without any LLM or network:

* face_found   share of sampled frames with a face (a talking-head clip with few faces means the crop lost the speaker)
* centered     share of the faces whose centre is in the middle half of the frame (sideways = the crop is late or wrong)
* jitter       median jump of the face centre between samples, as a share of the frame width (high = a shaky crop)
* silence      share of the clip that is silent (dead air the cutter left in)

Faces come from the detector the active-speaker crop uses (engine.speaker_focus: YuNet, else Haar); silence from ffmpeg's silencedetect.
"""
import re
import subprocess

SAMPLES = 24
SILENCE_DB = -35
SILENCE_MIN_S = 0.6


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def face_track(video, samples=SAMPLES):
    """[(cx, cy, size) or None] for `samples` evenly spaced frames: the largest face's centre and height as shares of the frame."""
    import cv2
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return []
    from engine.speaker_focus import _detect_faces, _make_detector
    det = _make_detector()          # the same detector the crop uses (YuNet; Haar frontal + profile when it is missing)
    out = []
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((i + 0.5) * total / samples))
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = [f for f in _detect_faces(frame, gray, det) if f[2] >= w // 12]     # ignore tiny faces in the background
        if not faces:
            out.append(None)
            continue
        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        out.append(((x + fw / 2) / w, (y + fh / 2) / h, fh / h))
    cap.release()
    return out


def track_stats(track):
    """{'face_found', 'centered', 'jitter'} from a face_track list (None values when nothing was sampled / found)."""
    if not track:
        return {"face_found": None, "centered": None, "jitter": None}
    faces = [f for f in track if f]
    found = round(len(faces) / len(track), 2)
    if not faces:
        return {"face_found": found, "centered": None, "jitter": None}
    centered = round(sum(1 for cx, _cy, _s in faces if 0.25 <= cx <= 0.75) / len(faces), 2)
    jumps = sorted(abs(b[0] - a[0]) for a, b in zip(track, track[1:]) if a and b)
    jitter = round(jumps[len(jumps) // 2], 3) if jumps else None
    return {"face_found": found, "centered": centered, "jitter": jitter}


def parse_silence(stderr_text, duration):
    """Share of `duration` covered by ffmpeg silencedetect output (an open silence at the end runs to the end)."""
    if not duration:
        return None
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", stderr_text)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", stderr_text)]
    total = 0.0
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration
        total += max(0.0, min(e, duration) - max(0.0, s))
    return round(min(1.0, total / duration), 2)


def silence_share(video):
    """Share of the clip that is silent, None when it has no sound or ffmpeg fails."""
    r = subprocess.run([_ffmpeg(), "-hide_banner", "-nostdin", "-i", video, "-af",
                        f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN_S}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if r.returncode != 0 or not m or "Audio:" not in r.stderr:
        return None
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return parse_silence(r.stderr, duration)


def _median(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    mid = len(v) // 2
    return round(v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2, 3)


def measure_videos(videos):
    """Medians over the clips: {'face_found', 'centered', 'jitter', 'silence'}."""
    per = []
    for v in videos:
        stats = track_stats(face_track(v))
        stats["silence"] = silence_share(v)
        per.append(stats)
    return {k: _median(p[k] for p in per) for k in ("face_found", "centered", "jitter", "silence")}
