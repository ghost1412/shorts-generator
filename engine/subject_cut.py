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

# Looks of the bridge. glow: strength of the bright outline round the person (0 = none); sweep: a light band running over the outline;
# dim: how much the old background darkens so the person stands out; lead: seconds of build-up BEFORE the background starts to change.
LOOKS = {
    "plain": {"glow": 0.0, "sweep": False, "dim": 0.0, "lead": 0.0},
    "glow": {"glow": 1.0, "sweep": False, "dim": 0.0, "lead": 0.25},
    "glow_sweep": {"glow": 1.0, "sweep": True, "dim": 0.25, "lead": 0.3},
    "spotlight": {"glow": 0.6, "sweep": False, "dim": 0.5, "lead": 0.3},
}
LOOK_LABELS = [("Auto (follows the edit style)", "auto"), ("Plain (no outline)", "plain"), ("Bright outline", "glow"),
               ("Bright outline + light sweep", "glow_sweep"), ("Spotlight (dark background, soft outline)", "spotlight")]
LOOK_DEFAULTS = {"hype": "glow_sweep", "vlog": "glow"}          # other edit styles: plain
COLORS = {"white": (255, 255, 255), "gold": (255, 196, 64), "cyan": (70, 220, 255), "pink": (255, 80, 170)}
COLOR_CHOICES = ["auto", *COLORS]


def resolve_style(look="auto", color="auto", edit=None):
    """The bridge style as a dict (glow, sweep, dim, lead, color as RGB): `look` itself, or for "auto" the default of the Auto-edit style `edit`.
    `color` is a name from COLORS, "#rrggbb", or "auto" (white). Raises ValueError for an unknown look or colour."""
    look = (look or "auto").strip().lower()
    if look == "auto":
        look = LOOK_DEFAULTS.get((edit or "").strip().lower(), "plain")
    if look not in LOOKS:
        raise ValueError(f"Unknown subject look {look!r}. Choose one of: auto, {', '.join(LOOKS)}")
    c = (color or "auto").strip().lower()
    bad = ValueError(f"Unknown outline colour {color!r}. Use auto, {', '.join(COLORS)} or #rrggbb")
    if c == "auto":
        rgb = COLORS["white"]
    elif c in COLORS:
        rgb = COLORS[c]
    elif len(c) == 7 and c[0] == "#":
        try:
            rgb = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            raise bad
    else:
        raise bad
    return {**LOOKS[look], "look": look, "color": rgb}


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


def letterbox_box(src_size, out_size):
    """(y0, y1, x0, x1) of the sharp picture when a shot of `src_size` (w, h) is fitted inside `out_size` with a blurred copy of itself filling
    the bars (the recap's letterbox layout). The person has to be looked for only in this part: the blurred bars show them too."""
    ow, oh = out_size
    w, h = src_size
    if not w or not h:
        return (0, oh, 0, ow)
    s = min(ow / w, oh / h)
    pw, ph = min(ow, round(w * s)), min(oh, round(h * s))
    y0, x0 = (oh - ph) // 2, (ow - pw) // 2
    return (y0, y0 + ph, x0, x0 + pw)


def masks_for(frames, box=None):
    """Person masks for rendered frames, looked for inside `box` = (y0, y1, x0, x1) only (default: the whole frame); zero outside it."""
    import numpy as np
    h, w = frames[0].shape[:2]
    y0, y1, x0, x1 = box or (0, h, 0, w)
    out = []
    for f in frames:
        m = np.zeros(f.shape[:2], np.float32)
        m[y0:y1, x0:x1] = person_mask(np.ascontiguousarray(f[y0:y1, x0:x1]))
        out.append(m)
    return out


def text_mask(pngs, size):
    """Where the recap's own titles and captions sit (alpha of their overlay PNGs, grown a little), as a uint8 mask of `size` (w, h); None if none."""
    try:
        import cv2
        import numpy as np
        w, h = size
        acc = np.zeros((h, w), np.uint8)
        for png in pngs or []:
            img = cv2.imread(png, cv2.IMREAD_UNCHANGED)
            if img is None or img.ndim != 3 or img.shape[2] < 4:
                continue
            a = cv2.resize(img[:, :, 3], (w, h), interpolation=cv2.INTER_AREA)
            acc = np.maximum(acc, (a > 20).astype(np.uint8) * 255)
        if not acc.any():
            return None
        return cv2.dilate(acc, np.ones((9, 9), np.uint8))
    except Exception:
        return None


def without_text(frame, mask):
    """`frame` with the pixels under `mask` filled in from their surroundings (only the text's bounding box is worked on, to stay fast)."""
    import cv2
    import numpy as np
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return frame
    pad = 12
    y0, y1, x0, x1 = max(0, ys.min() - pad), ys.max() + pad, max(0, xs.min() - pad), xs.max() + pad
    out = frame.copy()
    out[y0:y1, x0:x1] = cv2.inpaint(np.ascontiguousarray(frame[y0:y1, x0:x1]), np.ascontiguousarray(mask[y0:y1, x0:x1]), 3, cv2.INPAINT_TELEA)
    return out


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


def _glow_layer(alpha, strength, sweep_pos=None):
    """Bright halo round a (float 0..1) person mask: a tight rim plus a wide soft glow, 0..1 (HxW); a light band at `sweep_pos` (0..1 across the
    picture, diagonal) strengthens it as it passes. Done at half size, the halo is soft anyway."""
    import cv2
    import numpy as np
    h, w = alpha.shape
    small = cv2.resize(alpha, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    k = max(3, (w // 2) // 90) | 1
    grown = cv2.dilate(small, np.ones((k, k), np.uint8))
    tight = np.clip(cv2.GaussianBlur(grown, (0, 0), max(1.5, w / 400.0)) - small, 0.0, 1.0)
    wide = np.clip(cv2.GaussianBlur(grown, (0, 0), max(4.0, w / 40.0)) - small, 0.0, 1.0)
    halo = np.clip(tight * 1.3 + wide * 0.6, 0.0, 1.0)
    if sweep_pos is not None:
        gx, gy = np.meshgrid(np.linspace(0.0, 1.0, halo.shape[1], dtype=np.float32), np.linspace(0.0, 1.0, halo.shape[0], dtype=np.float32))
        band = np.exp(-(((gx + 0.35 * gy) / 1.35 - sweep_pos) / 0.10) ** 2)
        halo = np.clip(halo * (1.0 + 2.5 * band), 0.0, 1.0)
    return cv2.resize(halo * float(strength), (w, h), interpolation=cv2.INTER_LINEAR)


def compose(a_frames, b_frames, masks, fg_frames=None, style=None):
    """The bridge frames: wipe A's background to B's, person (from A, with its mask) in front, growing and fading out. Lists of HxWx3 uint8.
    `fg_frames` = A's frames without burned-in text, used for the person layer (default: A's frames).
    `style` (see resolve_style): the first `lead` seconds are build-up on A only (outline glows up, background dims, light sweeps), then
    the background wipes to B while the outline fades with the person. So `a_frames` / `masks` are `lead` frames longer than `b_frames`."""
    import cv2
    import numpy as np
    st = style or LOOKS["plain"]
    n = len(b_frames)
    nl = len(a_frames) - n
    fg_frames = fg_frames or a_frames
    h, w = a_frames[0].shape[:2]
    gx, gy = np.meshgrid(np.linspace(0.0, 1.0, w, dtype=np.float32), np.linspace(0.0, 1.0, h, dtype=np.float32))
    diag = (gx + 0.35 * gy) / 1.35                                   # 0 at the top left, 1 at the bottom right
    col = np.array(st.get("color", COLORS["white"]), np.float32)
    glow_on = st.get("glow", 0.0) > 0
    out = []
    for i in range(len(a_frames)):
        in_lead = i < nl
        ramp = (i + 1) / max(1, nl) if in_lead else 1.0              # build-up 0 -> 1
        p = 0.0 if in_lead else (i - nl + 0.5) / n                   # wipe progress 0 -> 1
        a_img = a_frames[i].astype(np.float32) * (1.0 - st.get("dim", 0.0) * ramp)
        if in_lead:
            bg = a_img
        else:
            edge = p * 1.3 - 0.15                                      # the wipe front, from before the picture to after it
            reveal = np.clip((edge - diag) / 0.12 + 0.5, 0.0, 1.0)[..., None]
            bg = a_img * (1.0 - reveal) + b_frames[i - nl].astype(np.float32) * reveal
        m = masks[i]
        ys, xs = np.nonzero(m > 0.5)
        cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (w / 2.0, h / 2.0)
        s = 1.0 + 0.18 * p
        mat = np.array([[s, 0.0, cx - s * cx], [0.0, s, cy - s * cy]], dtype=np.float32)
        fg = cv2.warpAffine(fg_frames[i], mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
        mw = cv2.warpAffine(m, mat, (w, h), flags=cv2.INTER_LINEAR)
        fade = 1.0 - max(0.0, (p - 0.6) / 0.4)
        alpha = (mw * fade)[..., None]
        frame = fg * alpha + bg * (1.0 - alpha)
        if glow_on:
            level = st["glow"] * ramp * fade
            pos = (i + 0.5) / len(a_frames) * 1.6 - 0.3 if st.get("sweep") else None      # the light band crosses the picture once
            halo = _glow_layer(mw, min(1.0, level), pos)[..., None]
            frame = 255.0 - (255.0 - frame) * (1.0 - halo * (col / 255.0))                 # screen blend: the outline only ever brightens
        out.append(np.clip(frame, 0, 255).astype(np.uint8))
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


def make_bridge(ffmpeg, a_path, b_path, out, size, enc, seconds=BRIDGE_S, fps=FPS, masks_fn=None, a_overlays=None, a_box=None, style=None):
    """Build the bridge clip `out` from the end of A and the start of B. Returns True, or False when there is no clear person
    (nothing is written then) or anything fails. `enc` = the encoder arguments of the recap; `masks_fn(frames) -> masks` is for tests;
    `style` = resolve_style(...) (default: plain, as before); `a_box` = where A's sharp picture is (letterboxed shots, see letterbox_box);
    `a_overlays` = the title/caption PNGs burned into A, which are taken out of the person layer so they do not ghost over the next shot."""
    try:
        import numpy as np  # noqa: F401
        lead = (style or {}).get("lead", 0.0)
        nl = round(lead * fps)
        da = _duration(ffmpeg, a_path)
        a = read_frames(ffmpeg, a_path, da - seconds - lead, seconds + lead, size, fps)
        b = read_frames(ffmpeg, b_path, 0.0, seconds, size, fps)
        n = min(len(a) - nl, len(b))
        if n < 6:
            return False
        a, b = a[len(a) - n - nl:], b[:n]
        masks = masks_fn(a) if masks_fn else masks_for(a, a_box)
        if not clear_subject(masks):
            return False
        tm = text_mask(a_overlays, size)
        clean = [without_text(f, tm) for f in a] if tm is not None else None
        frames = compose(a, b, masks, clean, style)
        w, h = size
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
               "-ss", f"{max(0.0, da - seconds - lead):.3f}", "-t", f"{seconds + lead:.3f}", "-i", a_path, "-t", f"{seconds:.3f}", "-i", b_path,
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


def apply(ffmpeg, parts, pairs, size, enc, workdir, seconds=BRIDGE_S, masks_fn=None, overlays=None, boxes=None, style=None):
    """Return a new parts list with the subject cut-out between the pairs of ADJACENT parts in `pairs` (a set of (path_a, path_b)).
    `overlays` maps a shot's path to the PNGs burned into it, `boxes` to the part of its frame holding the sharp picture,
    `style` = resolve_style(...) (the outline build-up `lead` makes the bridge, and the end of A that it replaces, that much longer).
    A pair whose bridge cannot be made (no clear person, a shot too short) stays a plain cut. Returns (parts, bridges made); raises when a
    shot cannot be trimmed."""
    os.makedirs(workdir, exist_ok=True)
    lead = (style or {}).get("lead", 0.0)
    bridges, made = {}, 0
    for i in range(len(parts) - 1):
        a, b = parts[i], parts[i + 1]
        if (a, b) not in pairs or min(_duration(ffmpeg, a), _duration(ffmpeg, b)) < 2 * seconds + lead + 0.4:
            continue
        out = os.path.join(workdir, f"bridge_{i}.mp4")
        if make_bridge(ffmpeg, a, b, out, size, enc, seconds, masks_fn=masks_fn, a_overlays=(overlays or {}).get(a), a_box=(boxes or {}).get(a), style=style):
            bridges[i] = out
            made += 1
    if not bridges:
        return list(parts), 0
    result = []
    for i, p in enumerate(parts):
        tail, head = i in bridges, (i - 1) in bridges
        if tail or head:
            trimmed = os.path.join(workdir, f"trim_{i}_" + os.path.basename(p))
            if not trim(ffmpeg, p, trimmed, seconds if head else 0.0, seconds + lead if tail else 0.0, enc):
                raise RuntimeError("Could not trim a shot for the subject cut-out")      # the caller keeps the plain cuts
            p = trimmed
        result.append(p)
        if tail:
            result.append(bridges[i])
    return result, made
