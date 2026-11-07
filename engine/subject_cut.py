"""Subject cut-out transition: the person stays in front while the background changes to the next shot.

For one cut between shot A and shot B (both already rendered at the same size) a short "bridge" clip is built:
  * the background wipes (soft diagonal edge) from A's last frames to B's first frames,
  * the person cut out of A stays in front, grows a little and fades out at the end,
  * A's sound crossfades into B's.
The bridge overlaps the end of A and the start of B (like a crossfade): A loses its last `BRIDGE_S` seconds and B its first `BRIDGE_S`
seconds, so every bridge makes the edit `BRIDGE_S` seconds shorter.

The person mask comes from a small segmentation model (torchvision LRASPP MobileNetV3, ~13 MB, downloaded once by torch and kept in its cache;
runs on the CPU so it never competes with a game for the GPU). Everything runs on this PC. torch/torchvision are optional: without them
`available()` is False and callers use a normal transition.
"""
import os
import subprocess

BRIDGE_S = 0.5
FPS = 30
PERSON_CLASS = 15                  # 'person' in the VOC label set used by the model
MIN_COVER, MAX_COVER = 0.012, 0.80  # share of the (rendered) frame the person fills: smaller = no clear subject, larger = nothing to reveal behind
_MODEL = []


def available():
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def _model():
    if not _MODEL:
        from torchvision.models.segmentation import LRASPP_MobileNet_V3_Large_Weights as Weights, lraspp_mobilenet_v3_large
        _MODEL.append(lraspp_mobilenet_v3_large(weights=Weights.DEFAULT).eval())
    return _MODEL[0]


def person_mask(rgb, long_side=480):
    """Soft person mask (float32, 0..1, same height and width as `rgb`, an HxWx3 uint8 array)."""
    import cv2
    import numpy as np
    import torch
    h, w = rgb.shape[:2]
    scale = long_side / float(max(h, w))
    small = cv2.resize(rgb, (max(32, int(w * scale) // 8 * 8), max(32, int(h * scale) // 8 * 8)), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(small).permute(2, 0, 1).float().div(255.0)
    x = (x - torch.tensor([0.485, 0.456, 0.406])[:, None, None]) / torch.tensor([0.229, 0.224, 0.225])[:, None, None]
    with torch.no_grad():
        prob = torch.softmax(_model()(x[None])["out"], dim=1)[0, PERSON_CLASS].numpy()
    prob = cv2.resize(prob.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    prob = cv2.GaussianBlur(prob, (0, 0), max(1.0, w / 300.0))
    return np.clip((prob - 0.35) / 0.4, 0.0, 1.0).astype(np.float32)          # firm inside, soft edge


def coverage(mask):
    return float((mask > 0.5).mean())


def clear_subject(masks):
    """True when a person fills a sensible part of the frame on average and is there in at least 80 % of the frames (the mask can miss a frame)."""
    covers = [coverage(m) for m in masks]
    if not covers:
        return False
    present = sum(1 for c in covers if c >= MIN_COVER * 0.6) / len(covers)
    return present >= 0.8 and MIN_COVER <= sum(covers) / len(covers) <= MAX_COVER


def frame_like_render(img, out_size, crop):
    """`img` (HxWx3 uint8) laid out the way the recap renders it at out_size = (w, h): centre-cropped to fill (crop=True) or fitted on a
    dark canvas (crop=False, the letterbox layout), so the person's share of the frame matches the rendered shot."""
    import cv2
    import numpy as np
    ow, oh = out_size
    h, w = img.shape[:2]
    if crop:
        s = max(ow / w, oh / h)
        r = cv2.resize(img, (max(ow, round(w * s)), max(oh, round(h * s))), interpolation=cv2.INTER_AREA)
        y, x = (r.shape[0] - oh) // 2, (r.shape[1] - ow) // 2
        return r[y:y + oh, x:x + ow]
    s = min(ow / w, oh / h)
    r = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((oh, ow, 3), np.uint8)
    y, x = (oh - r.shape[0]) // 2, (ow - r.shape[1]) // 2
    canvas[y:y + r.shape[0], x:x + r.shape[1]] = r
    return canvas


def has_person_jpegs(jpegs, out_size=None, crop=True):
    """Check on several JPEG frames from the end of a shot: is a clear person in all of them? With out_size the frames are laid out like the
    rendered shot first. False on any failure or when there are no frames."""
    try:
        import cv2
        import numpy as np
        masks = []
        for jpeg in jpegs:
            img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return False
            img = img[:, :, ::-1].copy()
            masks.append(person_mask(frame_like_render(img, out_size, crop) if out_size else img))
        return clear_subject(masks)
    except Exception:
        return False


def compose(a_frames, b_frames, masks):
    """The bridge frames: wipe A's background to B's, person (from A, with its mask) in front, growing and fading out. Lists of HxWx3 uint8."""
    import cv2
    import numpy as np
    n = len(a_frames)
    h, w = a_frames[0].shape[:2]
    gx, gy = np.meshgrid(np.linspace(0.0, 1.0, w, dtype=np.float32), np.linspace(0.0, 1.0, h, dtype=np.float32))
    diag = (gx + 0.35 * gy) / 1.35                                   # 0 at the top left, 1 at the bottom right
    out = []
    for i in range(n):
        p = (i + 0.5) / n
        edge = p * 1.3 - 0.15                                          # the wipe front, from before the picture to after it
        reveal = np.clip((edge - diag) / 0.12 + 0.5, 0.0, 1.0)[..., None]
        bg = a_frames[i] * (1.0 - reveal) + b_frames[i] * reveal
        m = masks[i]
        ys, xs = np.nonzero(m > 0.5)
        cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (w / 2.0, h / 2.0)
        s = 1.0 + 0.18 * p
        mat = np.array([[s, 0.0, cx - s * cx], [0.0, s, cy - s * cy]], dtype=np.float32)
        fg = cv2.warpAffine(a_frames[i], mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        alpha = cv2.warpAffine(m, mat, (w, h), flags=cv2.INTER_LINEAR) * (1.0 - max(0.0, (p - 0.6) / 0.4))
        alpha = alpha[..., None]
        out.append(np.clip(fg * alpha + bg * (1.0 - alpha), 0, 255).astype(np.uint8))
    return out


def read_frames(ffmpeg, path, start, seconds, size, fps=FPS):
    """Raw RGB frames [start, start + seconds) of `path` scaled to `size` (w, h): a list of HxWx3 uint8 arrays."""
    import numpy as np
    w, h = size
    r = subprocess.run([ffmpeg, "-loglevel", "error", "-ss", f"{max(0.0, start):.3f}", "-t", f"{seconds:.3f}", "-i", path, "-vf", f"fps={fps},scale={w}:{h}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    frame = w * h * 3
    n = len(r.stdout) // frame
    return [np.frombuffer(r.stdout, np.uint8, frame, i * frame).reshape(h, w, 3).copy() for i in range(n)]


def _duration(ffmpeg, path):
    import re
    err = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def make_bridge(ffmpeg, a_path, b_path, out, size, enc, seconds=BRIDGE_S, fps=FPS, masks_fn=None):
    """Build the bridge clip `out` from the end of A and the start of B. Returns True, or False when there is no clear person
    (nothing is written then) or anything fails. `enc` = the encoder arguments of the recap; `masks_fn(frames) -> masks` is for tests."""
    try:
        import numpy as np  # noqa: F401
        da = _duration(ffmpeg, a_path)
        a = read_frames(ffmpeg, a_path, da - seconds, seconds, size, fps)
        b = read_frames(ffmpeg, b_path, 0.0, seconds, size, fps)
        n = min(len(a), len(b))
        if n < 6:
            return False
        a, b = a[:n], b[:n]
        masks = (masks_fn or (lambda fr: [person_mask(f) for f in fr]))(a)
        if not clear_subject(masks):
            return False
        frames = compose(a, b, masks)
        w, h = size
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
               "-ss", f"{max(0.0, da - seconds):.3f}", "-t", f"{seconds:.3f}", "-i", a_path, "-t", f"{seconds:.3f}", "-i", b_path,
               "-filter_complex", f"[1:a][2:a]acrossfade=d={n / fps - 0.02:.3f}:c1=tri:c2=tri,aresample=44100[a]",
               "-map", "0:v", "-map", "[a]", *enc, "-shortest", out]
        r = subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), capture_output=True)
        return r.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 1000
    except Exception:
        return False


def trim(ffmpeg, path, out, cut_head, cut_tail, enc):
    """Re-encode `path` without its first `cut_head` and last `cut_tail` seconds. Returns True on success."""
    d = _duration(ffmpeg, path)
    keep = d - cut_head - cut_tail
    if keep < 0.4:
        return False
    r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", path, "-ss", f"{cut_head:.3f}", "-t", f"{keep:.3f}", *enc, out], capture_output=True, text=True)
    return r.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 1000


def apply(ffmpeg, parts, pairs, size, enc, workdir, seconds=BRIDGE_S, masks_fn=None):
    """Return a new parts list with the subject cut-out between the pairs of ADJACENT parts in `pairs` (a set of (path_a, path_b)).
    A pair whose bridge cannot be made (no clear person, a shot too short) stays a plain cut. Returns (parts, bridges made); raises when a
    shot cannot be trimmed."""
    os.makedirs(workdir, exist_ok=True)
    bridges, made = {}, 0
    for i in range(len(parts) - 1):
        a, b = parts[i], parts[i + 1]
        if (a, b) not in pairs or min(_duration(ffmpeg, a), _duration(ffmpeg, b)) < 2 * seconds + 0.4:
            continue
        out = os.path.join(workdir, f"bridge_{i}.mp4")
        if make_bridge(ffmpeg, a, b, out, size, enc, seconds, masks_fn=masks_fn):
            bridges[i] = out
            made += 1
    if not bridges:
        return list(parts), 0
    result = []
    for i, p in enumerate(parts):
        tail, head = i in bridges, (i - 1) in bridges
        if tail or head:
            trimmed = os.path.join(workdir, f"trim_{i}_" + os.path.basename(p))
            if not trim(ffmpeg, p, trimmed, seconds if head else 0.0, seconds if tail else 0.0, enc):
                raise RuntimeError("Could not trim a shot for the subject cut-out")      # the caller keeps the plain cuts
            p = trimmed
        result.append(p)
        if tail:
            result.append(bridges[i])
    return result, made
