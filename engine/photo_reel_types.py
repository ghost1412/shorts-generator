"""Photo reel types: from a pile of photos to a reel that has a shape.

`--mode PHOTO_REEL` cuts photos to a beat. A *type* decides what the reel is: how the photos are ordered, how long each is held,
what the captions say, the title and the closing line, and the look (flash, motion, colour grade). Six types:

    memories   chronological, warm, dates as captions            travel     chronological, "Day 1 / Day 2", punchy cuts
    product    features one by one, clean and calm               then_now   "THEN" / "NOW" pairs
    countdown  "#5 ... #1" with the best last                     tribute    slow, warm, for a person ("For Mum")

Everything here is plain Python (PIL + numpy), runs offline, and is tested without rendering. `plan_reel` returns a dict the
renderer consumes: ordered photo paths, per-photo captions, start times, total duration, title and style.
"""
import os
import re
from datetime import datetime

import numpy as np

PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".heic")
MIN_SECONDS_PER_PHOTO = 1.6

REEL_TYPES = {
    "memories": {
        "label": "Memories", "pace": 2.8, "order": "chronological", "captions": "dates",
        "title": "Memories I'll never forget", "outro": "Make more of them",
        "style": {"flash": 0.45, "motion": 0.8, "grade": "sepia(0.18) saturate(1.1) contrast(1.05)", "accent": "#ffb347", "captionScale": 1.1},
    },
    "travel": {
        "label": "Travel recap", "pace": 2.2, "order": "chronological", "captions": "days",
        "title": "Trip recap", "outro": "Where to next?",
        "style": {"flash": 0.9, "motion": 1.2, "grade": "saturate(1.25) contrast(1.08)", "accent": "#00d4ff", "captionScale": 1.15},
    },
    "product": {
        "label": "Product showcase", "pace": 2.6, "order": "given", "captions": "features",
        "title": "Meet the {name}", "outro": "Link in bio",
        "style": {"flash": 0.25, "motion": 0.6, "grade": "contrast(1.1) saturate(1.05) brightness(1.03)", "accent": "#ffffff", "captionScale": 1.0},
    },
    "then_now": {
        "label": "Then vs now", "pace": 3.0, "order": "chronological", "captions": "then_now",
        "title": "Then vs now", "outro": "Time flies",
        "style": {"flash": 1.0, "motion": 0.5, "grade": "", "accent": "#ff4d6d", "captionScale": 1.7},
    },
    "countdown": {
        "label": "Top N countdown", "pace": 2.8, "order": "given", "captions": "countdown",
        "title": "Top {n}", "outro": "Which is your favourite?",
        "style": {"flash": 1.0, "motion": 1.0, "grade": "saturate(1.15) contrast(1.05)", "accent": "#ffd400", "captionScale": 2.0},
    },
    "tribute": {
        "label": "Tribute / birthday", "pace": 3.2, "order": "chronological", "captions": "texts",
        "title": "For {name}", "outro": "Love you",
        "style": {"flash": 0.3, "motion": 0.7, "grade": "sepia(0.1) saturate(1.1) brightness(1.04)", "accent": "#ffcc66", "captionScale": 1.2},
    },
}


def type_names():
    return list(REEL_TYPES)


def type_labels():
    return [(spec["label"], key) for key, spec in REEL_TYPES.items()]


# ---- photo analysis ------------------------------------------------------------------------------------------------------------
def list_photos(folder):
    """Photo files of a folder, in file-name order."""
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(PHOTO_EXTS))


def _gray(path, size=256):
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("L")
        im.thumbnail((size, size))
        return np.asarray(im, dtype=np.float32)


def sharpness(gray):
    """Variance of a Laplacian: high = detailed, low = blurry (comparable between photos of the same shooting conditions)."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    lap = (-4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:])
    return float(lap.var())


def average_hash(gray, size=8):
    """64-bit perceptual hash as an int: two shots of the same scene differ in only a few bits."""
    from PIL import Image
    small = np.asarray(Image.fromarray(gray.astype(np.uint8)).resize((size, size)), dtype=np.float32)
    bits = (small > small.mean()).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def difference_hash(gray, size=8):
    """64-bit gradient hash (left-to-right brightness changes): a second opinion next to average_hash, because smooth
    gradients can make unrelated pictures share an average hash."""
    from PIL import Image
    small = np.asarray(Image.fromarray(gray.astype(np.uint8)).resize((size + 1, size)), dtype=np.float32)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a, b):
    return bin(a ^ b).count("1")


def exif_date(path):
    """datetime the photo was taken (EXIF), else None."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            ex = im.getexif()
            raw = None
            try:
                raw = ex.get_ifd(0x8769).get(36867)        # DateTimeOriginal
            except Exception:
                pass
            raw = raw or ex.get(306)                        # DateTime
            if raw:
                return datetime.strptime(str(raw)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def analyse(path):
    """{path, sharp, hash, date, mtime}; unreadable images get sharp=0 so they are dropped first."""
    info = {"path": path, "sharp": 0.0, "hash": 0, "dhash": 0, "date": None, "mtime": os.path.getmtime(path) if os.path.exists(path) else 0.0}
    try:
        g = _gray(path)
        info.update({"sharp": sharpness(g), "hash": average_hash(g), "dhash": difference_hash(g), "date": exif_date(path)})
    except Exception:
        info["unreadable"] = True
    return info


# ---- selection and order ---------------------------------------------------------------------------------------------------------
def _same_shot(a, b, dup_bits):
    """Both hashes agree: the same scene (a burst, an exact copy)."""
    return hamming(a["hash"], b["hash"]) <= dup_bits and hamming(a.get("dhash", 0), b.get("dhash", 0)) <= dup_bits + 3


def select_photos(infos, max_n, min_keep=3, dup_bits=5, blur_ratio=0.35):
    """Photos to use, in the input order: unreadable ones, near-duplicates (keep the sharper) and very blurry ones are dropped
    while at least `min_keep` remain; then, when still above `max_n`, the sharpest `max_n` are kept."""
    keep = [i for i in infos if not i.get("unreadable")]
    kept = []
    for info in keep:                                           # near-duplicates: the sharper of the pair stays
        twin = next((k for k in kept if _same_shot(k, info, dup_bits)), None)
        if twin is None:
            kept.append(info)
        elif info["sharp"] > twin["sharp"]:
            kept[kept.index(twin)] = info
    keep = kept if len(kept) >= min_keep else keep
    if len(keep) > min_keep:
        median = float(np.median([i["sharp"] for i in keep])) or 1.0
        sharp_enough = [i for i in keep if i["sharp"] >= blur_ratio * median]
        keep = sharp_enough if len(sharp_enough) >= min_keep else keep
    if len(keep) > max_n:
        best = sorted(keep, key=lambda i: i["sharp"], reverse=True)[:max_n]
        keep = [i for i in keep if i in best]
    order = {id(i): n for n, i in enumerate(infos)}
    return sorted(keep, key=lambda i: order[id(i)])


def order_photos(infos, how):
    """'chronological': by EXIF date, else file time, else name. 'given': as listed."""
    if how != "chronological":
        return list(infos)
    return sorted(infos, key=lambda i: (i["date"] or datetime.fromtimestamp(i["mtime"] or 0), os.path.basename(i["path"])))


# ---- timing ----------------------------------------------------------------------------------------------------------------------
def photo_budget(target, pace):
    """(ideal count, hard maximum) of photos for a reel of `target` seconds."""
    return max(3, round(target / pace)), max(3, int(target / MIN_SECONDS_PER_PHOTO))


def plan_times(n, target, hero=True):
    """Start time of every photo: first and last are held a little longer (hook and ending), the rest evenly."""
    weights = [1.0] * n
    if hero and n >= 4:
        weights[0] = weights[-1] = 1.3
    total = sum(weights)
    starts, t = [], 0.0
    for w in weights:
        starts.append(round(t, 2))
        t += target * w / total
    return starts


# ---- captions --------------------------------------------------------------------------------------------------------------------
def _month_year(d):
    return d.strftime("%B %Y") if d else ""


def make_captions(kind, infos, texts=None):
    """One caption per photo ('' for none). `texts` (the user's own lines) always win over generated captions."""
    n = len(infos)
    texts = [t.strip() for t in (texts or []) if t and t.strip()]
    out = [""] * n
    if kind == "dates":
        out = [_month_year(i["date"]) for i in infos]
    elif kind == "days":
        days, seen = [], {}
        for i in infos:
            key = i["date"].date() if i["date"] else None
            if key is not None and key not in seen:
                seen[key] = len(seen) + 1
            days.append(seen.get(key))
        if any(days):
            out = [f"Day {d}" if d else "" for d in days]
        else:
            out = [f"Stop {k + 1}" for k in range(n)]
    elif kind == "features":
        out = [f"Feature {k + 1}" for k in range(n)]
    elif kind == "then_now":
        out = []
        for k, i in enumerate(infos):
            label = "THEN" if k < (n + 1) // 2 else "NOW"
            year = i["date"].year if i["date"] else ""
            out.append(f"{label} {year}".strip())
    elif kind == "countdown":
        out = [f"#{n - k}" for k in range(n)]
    for k, t in enumerate(texts[:n]):
        if kind in ("countdown", "then_now", "days", "dates") and out[k]:
            out[k] = f"{out[k]} {t}" if kind == "countdown" else f"{out[k]} · {t}"       # the label stays, your words follow
        else:
            out[k] = t                                                                    # features / tribute: your words replace it
    return out


# ---- the plan --------------------------------------------------------------------------------------------------------------------
def plan_reel(files, reel_type, target_duration=30.0, name=None, texts=None, analysed=None):
    """Plan for the renderer, or ValueError for an unknown type / too few usable photos.

    Returns {type, label, photos, captions, starts, duration, title, outro, style, dropped}."""
    if reel_type not in REEL_TYPES:
        raise ValueError(f"Unknown reel type {reel_type!r}. Choose one of: {', '.join(REEL_TYPES)}")
    spec = REEL_TYPES[reel_type]
    infos = analysed if analysed is not None else [analyse(f) for f in files]
    ideal, hard_max = photo_budget(target_duration, spec["pace"])
    max_n = min(hard_max, max(ideal + ideal // 2, 3))
    chosen = select_photos(infos, max_n)
    if len(chosen) < 3:
        raise ValueError("A reel needs at least 3 usable photos (blurry, duplicate and unreadable ones are skipped).")
    ordered = order_photos(chosen, spec["order"])
    captions = make_captions(spec["captions"], ordered, texts)
    n = len(ordered)
    nm = (name or "").strip()
    title = spec["title"].format(name=nm or "this", n=n) if "{" in spec["title"] else spec["title"]
    if reel_type in ("tribute", "product") and not nm:
        title = "For you" if reel_type == "tribute" else "Take a look"
    if nm and reel_type not in ("tribute", "product"):
        title = f"{nm}: {title}"
    # the closing line sits on the last photo (after its own caption, if it has one)
    captions[-1] = f"{captions[-1]} · {spec['outro']}" if captions[-1] else spec["outro"]
    return {"type": reel_type, "label": spec["label"], "photos": [i["path"] for i in ordered], "captions": captions,
            "starts": plan_times(n, target_duration), "duration": float(target_duration), "title": title,
            "outro": spec["outro"], "style": dict(spec["style"]),
            "dropped": len(infos) - n}


def parse_texts(raw):
    """User lines from a '|' or newline separated string (or a list)."""
    if isinstance(raw, (list, tuple)):
        return [str(t).strip() for t in raw if str(t).strip()]
    return [t.strip() for t in re.split(r"[|\n]", raw or "") if t.strip()]
