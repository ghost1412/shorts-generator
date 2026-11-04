"""Trip recap: several videos (day 1, day 2, ...) -> one vertical recap with a title card per day and a written itinerary.

    python main.py --mode TRIP --trip_videos day1/ day2/ --trip_name "Almaty" --recap_length 60

* Videos are grouped into days: one folder per day, or files named "day1", "day 2", ... , else by the date they were filmed.
* From every day a few lively moments are picked (loudest stretches, spread over the whole day, so the recap covers the day and not just
  its best minute). With `--visual_context` and a vision model in Ollama each moment is also described.
* The AI writes the recap title, a title and one-line summary for each day, and a short caption per moment, from those descriptions
  and your note (`--user_context`). Without any AI it falls back to "Day 1", "Day 2" and no captions.
* The recap opens like a trailer ("hype" style, the default): a one-line hook over fast glimpses of the most beautiful shots (colour and
  contrast decide, or the vision model's pick), and only then the title and the whole trip day by day. The hook comes from `--recap_hook`,
  else from your note (`--user_context`: "woke up at 4 am for sunrise at the lake" -> "Woke up at 4 AM just for this view"), else a
  neutral line. `--recap_style plain` skips the opening.
* Output: recap.mp4 (title card + moments for each day, the clips' own sound kept), itinerary.md and itinerary.json.
"""
import json
import os
import re
import subprocess
import sys
import time

MODE = "TRIP"              # the --mode value that runs this module (see shortsflow/_main.py)
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts")
CARD_SECONDS = 2.2
CLIP_SECONDS = 5.0
GLIMPSES = 5               # quick scenic shots in the opening
GLIMPSE_SECONDS = 1.4
W, H = 1080, 1920
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "remotion-video", "public", "fonts")


def natural_key(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(text))]


def collect_videos(paths):
    """[(path, day_hint)] from files and folders. A folder given on its own is one day (or its sub-folders are days)."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            subs = sorted((d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))), key=natural_key)
            if subs:
                for d in subs:
                    out += collect_videos([os.path.join(p, d)])
                files = sorted((f for f in os.listdir(p) if f.lower().endswith(VIDEO_EXT)), key=natural_key)
                out += [(os.path.join(p, f), os.path.basename(os.path.normpath(p))) for f in files]
            else:
                hint = os.path.basename(os.path.normpath(p))
                out += [(os.path.join(p, f), hint) for f in sorted(os.listdir(p), key=natural_key) if f.lower().endswith(VIDEO_EXT)]
        elif os.path.isfile(p) and p.lower().endswith(VIDEO_EXT):
            out.append((p, None))
    return out


def group_days(videos):
    """[[path, ...], ...] one list per day, in day order.

    A day number in the folder or file name ("day2", "Day 02") wins; else the date the file was modified; videos that share neither
    form one day each in name order."""
    keyed = []
    for path, hint in videos:
        text = f"{hint or ''} {os.path.splitext(os.path.basename(path))[0]}"
        m = re.search(r"day[\s_\-]*0*(\d+)", text, re.I)
        if m:
            key = (0, f"{int(m.group(1)):08d}")
        else:
            try:
                key = (1, time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path))))
            except OSError:
                key = (2, "")
        keyed.append((key, natural_key(path), path))
    if not keyed:
        return []
    groups = {}
    for key, _nk, path in sorted(keyed, key=lambda t: (t[0], t[1])):
        groups.setdefault(key, []).append(path)
    if len(groups) == 1 and len(keyed) > 1 and next(iter(groups))[0] != 0 and not any(h for _, h in videos):
        return [[p] for p in next(iter(groups.values()))]        # nothing tells the days apart: one day per file, in name order
    return list(groups.values())


def file_seconds(path):
    """Seconds since the start of the day from a name like '083015_ab12cd34.mp4' (the album importer's names), else None."""
    m = re.match(r"(\d{2})(\d{2})(\d{2})_", os.path.basename(path))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def split_by_gaps(files, n):
    """n groups of `files` (in filming order) cut at the n-1 longest pauses between clips: the drives between places. None when the
    files carry no times, or the pauses are not clearly longer than normal gaps (then the caller splits by count)."""
    times = [file_seconds(f) for f in files]
    if n < 2 or len(files) < n or any(t is None for t in times) or times != sorted(times):
        return None
    gaps = sorted(range(1, len(files)), key=lambda i: times[i] - times[i - 1], reverse=True)[:n - 1]
    if min(times[i] - times[i - 1] for i in gaps) < 15 * 60:
        return None
    cuts = sorted(gaps)
    return [files[a:b] for a, b in zip([0] + cuts, cuts + [len(files)])]


def split_into(groups, n):
    """Re-group the videos of `groups` (in order) into exactly n stops. Used with --trip_stops, where the user names the stops in
    order and the videos are in filming order, however the files were grouped. The cuts go at the longest pauses between clips
    when the files carry times (the drive between two places), else the stops get nearly equal numbers of videos."""
    files = [f for g in groups for f in g]
    n = max(1, min(int(n), len(files)))
    by_gap = split_by_gaps(files, n)
    if by_gap:
        return by_gap
    size, extra = divmod(len(files), n)
    out, i = [], 0
    for k in range(n):
        take = size + (1 if k < extra else 0)
        out.append(files[i:i + take])
        i += take
    return out


def parse_stops(text):
    """['Kolsai Lake', 'Kaindy Lake', ...] from 'Kolsai Lake, Kaindy Lake; Charyn Canyon' (or a list)."""
    if isinstance(text, (list, tuple)):
        items = [str(x) for x in text]
    else:
        items = re.split(r"[,;\n]+", str(text or ""))
    return [s.strip() for s in items if s.strip()]


def plan_counts(n_days, total_seconds, card=CARD_SECONDS, clip=CLIP_SECONDS):
    """(clips per day, clip seconds) so that cards + clips fill `total_seconds`."""
    n_days = max(1, int(n_days))
    left = max(float(total_seconds) - n_days * card, n_days * 3.0)
    per_day = left / n_days
    n = max(1, int(round(per_day / clip)))
    return n, round(max(2.5, min(8.0, per_day / n)), 2)


def plan_days(video_counts, total_seconds, card=CARD_SECONDS, clip=CLIP_SECONDS):
    """([moments for each day], seconds per moment). Days with more footage get more time: weight = sqrt(number of videos), so a
    day with 68 videos gets about 4 times the time of a day with 4 (not 17 times), and every day keeps at least one moment."""
    n = max(1, len(video_counts))
    left = max(float(total_seconds) - n * card, n * 3.0)
    total_moments = max(n, int(round(left / clip)))
    weights = [max(1.0, float(c)) ** 0.5 for c in video_counts]
    raw = [total_moments * w / sum(weights) for w in weights]
    counts = [max(1, int(round(r))) for r in raw]
    while sum(counts) > total_moments and max(counts) > 1:          # trim the biggest day first
        counts[counts.index(max(counts))] -= 1
    while sum(counts) < total_moments:                              # give the rest to the day with the most footage
        counts[max(range(n), key=lambda i: raw[i] - counts[i])] += 1
    return counts, round(max(2.5, min(8.0, left / max(1, sum(counts)))), 2)


def loudness_per_second(video, ffmpeg=None, run=subprocess.run):
    """[rms level in dB for each second] from the video's sound, [] when it has none."""
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    r = run([ffmpeg, "-hide_banner", "-nostats", "-i", video, "-vn", "-ac", "1", "-ar", "8000",
             "-af", "astats=metadata=1:reset=8000,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"],
            capture_output=True, text=True)
    vals = []
    for m in re.finditer(r"RMS_level=(-?[\d.]+|-inf)", r.stdout or ""):
        v = m.group(1)
        vals.append(-90.0 if v == "-inf" else float(v))
    return vals


def pick_windows(duration, n, length, levels=None, skip=0.04):
    """n [start, end] windows of `length` seconds spread over the video: the video is cut into n equal zones and the loudest stretch
    of each zone is taken (the middle of the zone when the video has no sound). Never starts in the first/last 4%."""
    duration = float(duration)
    length = min(float(length), duration)
    if duration <= length + 0.5 or n <= 1 and duration <= length * 1.5:
        return [[0.0, round(min(duration, length), 2)]]
    lo, hi = duration * skip, duration * (1 - skip)
    n = max(1, min(int(n), int((hi - lo) // length) or 1))
    zone = (hi - lo) / n
    out = []
    for z in range(n):
        a, b = lo + z * zone, lo + (z + 1) * zone
        best, best_start = None, (a + b) / 2 - length / 2
        if levels:
            s = a
            while s + length <= b + 0.01:
                seg = levels[int(s):int(s + length)]
                score = sum(seg) / len(seg) if seg else -99
                if best is None or score > best:
                    best, best_start = score, s
                s += 1.0
        start = max(0.0, min(best_start, duration - length))
        out.append([round(start, 2), round(start + length, 2)])
    return out


def build_prompt(trip_name, note, days, stops=None):
    unit = "Stop" if stops else "Day"
    lines = []
    for i, d in enumerate(days, 1):
        moms = "; ".join(f"[{j}] {m.get('visual') or 'no description'}" for j, m in enumerate(d["moments"], 1))
        name = f" = {stops[i - 1]}" if stops and i <= len(stops) else ""
        lines.append(f"{unit} {i}{name}: {moms}")
    return (f"Write a travel recap itinerary for a short video.\nTrip: {trip_name or 'my trip'}\n"
            "STRICT: use only facts that are in the traveller's note, the stop names or the descriptions. Never invent places, "
            "times, weather, food or feelings. When a moment has no description, leave its caption empty (\"\").\n"
            f"Traveller's note: {note or '(none)'}\n\nWhat each day's moments show (the pictures were described automatically, "
            "some descriptions may be missing or wrong; never invent places the descriptions or note do not support):\n"
            + "\n".join(lines) + "\n\n"
            'Reply with JSON only: {"title": "<recap title, max 5 words>", "hook": "<one excited first-person line of at most 9 words '
            'that opens the video, e.g. Woke up at 4 AM just for this view. Use only facts from the traveller\'s note; with no usable note '
            'write a neutral line like You have to see this place>", "days": [{"title": "<day title, max 5 words>", '
            '"summary": "<one sentence>", "captions": ["<caption for moment 1, max 6 words>", ...]}]}. '
            f"Exactly {len(days)} {unit.lower()}s, and for each {unit.lower()} one caption per moment."
            + (" The stop names are given: use each one exactly as its title." if stops else ""))


def fallback_itinerary(trip_name, days, stops=None):
    return {"title": trip_name or "Trip recap", "hook": "",
            "days": [{"title": stops[i - 1] if stops and i <= len(stops) else f"Day {i}", "summary": "",
                      "captions": ["" for _ in d["moments"]]} for i, d in enumerate(days, 1)]}


def write_itinerary(trip_name, note, days, ask=None, stops=None):
    """The itinerary dict {title, days:[{title, summary, captions}]}; never fails (falls back to plain 'Day N')."""
    fb = fallback_itinerary(trip_name, days, stops)
    if ask is None:
        try:
            from engine.script_gen import get_llm_response
            ask = lambda p: get_llm_response(p, "You write short, honest travel captions. Reply with raw JSON only.", max_tokens=4000)  # noqa: E731
        except Exception:
            return fb
    try:
        from engine.script_gen import robust_json_parse
        data = robust_json_parse(ask(build_prompt(trip_name, note, days, stops)))
        rows = data.get("days") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            return fb
        out = {"title": (trip_name or str(data.get("title") or fb["title"]))[:60], "hook": str(data.get("hook") or "").strip()[:70], "days": []}
        for i, d in enumerate(days):
            row = rows[i] if i < len(rows) and isinstance(rows[i], dict) else {}
            caps = [str(c)[:60] for c in (row.get("captions") or []) if isinstance(c, (str, int, float))]
            caps += [""] * (len(d["moments"]) - len(caps))
            title = stops[i] if stops and i < len(stops) else str(row.get("title") or f"Day {i + 1}")
            out["days"].append({"title": title[:50], "summary": str(row.get("summary") or "")[:160],
                                "captions": caps[:len(d["moments"])]})
        return out
    except Exception as e:
        print(f"[Warning] Could not write the itinerary with AI ({str(e)[:80]}); using plain day titles.")
        return fb


def itinerary_markdown(it, days, unit="Day"):
    lines = [f"# {it['title']}", ""]
    if it.get("hook"):
        lines += [f"*{it['hook']}*", ""]
    for i, (d, row) in enumerate(zip(days, it["days"]), 1):
        lines.append(f"## {unit} {i}: {row['title']}")
        if row["summary"]:
            lines.append(row["summary"])
        for m, cap in zip(d["moments"], row["captions"]):
            lines.append(f"- {cap or os.path.basename(m['file'])} ({m['start']:.0f}s in {os.path.basename(m['file'])})")
        lines.append("")
    return "\n".join(lines)


def _font(size, text=""):
    from PIL import ImageFont
    name = "NotoSansCyrillic.ttf" if re.search(r"[Ѐ-ӿ]", text) else "Anton-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def title_card_png(path, big, title, summary=""):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (11, 16, 32))
    d = ImageDraw.Draw(img)
    size = 190
    f_big = _font(size, big)
    while d.textlength(big, font=f_big) > W - 120 and size > 70:
        size -= 10
        f_big = _font(size, big)
    f_title, f_sum = _font(88, title), _font(48, summary)
    y = H // 2 - 330
    d.text((W // 2, y), big, font=f_big, fill=(255, 209, 102), anchor="mm")
    y += 210
    for ln in _wrap(d, title, f_title, W - 160):
        d.text((W // 2, y), ln, font=f_title, fill=(255, 255, 255), anchor="mm")
        y += 100
    y += 40
    for ln in _wrap(d, summary, f_sum, W - 200):
        d.text((W // 2, y), ln, font=f_sum, fill=(190, 200, 220), anchor="mm")
        y += 62
    img.save(path)
    return path


# "cinematic" look: warm teal-orange grade, soft contrast, slow fades, small spaced place labels, quiet black title cards.
CINEMATIC_GRADE = "eq=contrast=1.06:saturation=1.1:gamma=0.98,colorbalance=rs=0.03:rm=0.04:bm=-0.04:rh=0.05:bh=-0.05"
GRADE_COOL = "eq=contrast=1.1:saturation=1.18:gamma=0.97,colorbalance=rs=-0.03:bs=0.04:gm=0.02:bh=0.03:rh=-0.02"
ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "2.35:1": (1920, 816)}


def frame_look(ffmpeg, src, t, run=subprocess.run):
    """Reads one frame of the shot a title will sit on: where it is calmest, how bright it is there, and its accent colour.
    Returns {"zone", "dark", "accent"}; any failure gives the neutral default (centre, light text, gold)."""
    default = {"zone": "center", "dark": True, "accent": (232, 200, 140)}
    try:
        import tempfile
        from PIL import Image
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, "f.png")
            r = run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=320:-2", png],
                    capture_output=True, text=True)
            if r.returncode != 0 or not os.path.isfile(png):
                return default
            im = Image.open(png).convert("RGB")
        arr = np.asarray(im).astype(np.float32)
        lum = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        h, w = lum.shape
        boxes = {"center": (0.2, 0.8, 0.35, 0.65), "left": (0.05, 0.5, 0.35, 0.65), "lower": (0.05, 0.7, 0.68, 0.9), "upper": (0.2, 0.8, 0.1, 0.3)}
        stats = {}
        for name, (x0, x1, y0, y1) in boxes.items():
            reg = lum[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
            stats[name] = (float(reg.std()) + (0.0 if name == "center" else 4.0), float(reg.mean()))      # a small bias keeps the centre when nothing is calmer
        zone = min(stats, key=lambda k: stats[k][0])
        sat = arr.max(axis=2) - arr.min(axis=2)
        mask = sat >= np.percentile(sat, 85)
        col = arr[mask].mean(axis=0) if mask.any() else np.array(default["accent"], dtype=np.float32)
        col = np.clip(col * (1.0 + (200 - col.max()) / 400.0) + 25, 0, 255)         # brighten so it reads on dark and light shots
        return {"zone": zone, "dark": stats[zone][1] < 150, "accent": tuple(int(c) for c in col)}
    except Exception:
        return default


def pick_grade(ffmpeg, files, run=subprocess.run, sample=6):
    """Warm footage (sand, rock, sunset: red above blue) gets the warm grade, cool footage (water, ice, forest) the cool one."""
    try:
        import tempfile
        from PIL import Image
        import numpy as np
        reds = blues = 0.0
        step = max(1, len(files) // sample)
        with tempfile.TemporaryDirectory() as tmp:
            for i, f in enumerate(files[::step][:sample]):
                png = os.path.join(tmp, f"{i}.png")
                dur = video_info(f)[0]
                r = run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{dur / 2:.1f}", "-i", f, "-frames:v", "1", "-vf", "scale=96:-2", png],
                        capture_output=True, text=True)
                if r.returncode == 0 and os.path.isfile(png):
                    arr = np.asarray(Image.open(png).convert("RGB")).astype(np.float32)
                    reds += float(arr[..., 0].mean())
                    blues += float(arr[..., 2].mean())
        if reds + blues == 0:
            return CINEMATIC_GRADE
        return CINEMATIC_GRADE if reds >= blues * 1.08 else GRADE_COOL
    except Exception:
        return CINEMATIC_GRADE


def cinematic_layers(path_base, title, line="", small="", look=None, index=0):
    """Title over the footage as separate transparent layers that fade in one after another: [(png, start second), ...].
    The look comes from the shot: text goes where the picture is calmest, light or dark text by brightness, accent colour from the shot,
    and the layout rotates (centred / left-aligned / stacked words) so the cards are not all the same."""
    from PIL import Image, ImageDraw, ImageFont
    look = look or {"zone": "center", "dark": True, "accent": (232, 200, 140)}
    u = min(W, H) / 1080.0
    zone = look["zone"]
    ink = (255, 255, 255, 255) if look["dark"] else (22, 18, 14, 255)
    shadow = (0, 0, 0, 90) if look["dark"] else (255, 255, 255, 70)
    accent = tuple(look["accent"]) + (255,)
    left = zone in ("left", "lower")
    words = str(title).split()
    stacked = left and index % 2 == 1 and len(words) > 1 and all(len(w) >= 3 for w in words)
    cx = int(W * 0.08) if left else W // 2
    cy = {"center": H // 2, "left": H // 2, "lower": int(H * 0.78), "upper": int(H * 0.22)}[zone]
    anchor = "lm" if left else "mm"

    def font(size):
        try:
            return ImageFont.truetype(os.path.join(FONT_DIR, "NotoSansCyrillic.ttf"), max(12, int(size * u)))
        except OSError:
            return ImageFont.load_default()

    def layer(draw_fn, name):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(img))
        out = f"{path_base}_{name}.png"
        img.save(out)
        return out

    def title_fn(d):
        if stacked:
            f, y = font(120), cy - int(120 * u) * (len(title.split()) - 1) // 2
            for wd in title.upper().split():
                d.text((cx, y), wd, font=f, fill=ink, anchor=anchor, stroke_width=2, stroke_fill=shadow)
                y += int(125 * u)
        else:
            d.text((cx, cy), spaced(title), font=font(86), fill=ink, anchor=anchor, stroke_width=2, stroke_fill=shadow)

    rows = len(title.split()) if stacked else 1
    below = cy + (int(125 * u) * rows) // 2 + int(30 * u) if stacked else cy + int(90 * u)
    layers = []
    if small:
        layers.append((layer(lambda d: d.text((cx, cy - int(130 * u)), spaced(small), font=font(34), fill=ink, anchor=anchor), "a"), 0.3))
    layers.append((layer(title_fn, "b"), 0.9))
    if line:
        def sub(d):
            x0, x1 = (cx, cx + int(120 * u)) if left else (cx - int(60 * u), cx + int(60 * u))
            d.line([(x0, below), (x1, below)], fill=accent, width=max(2, int(3 * u)))
            d.text((cx, below + int(60 * u)), spaced(line), font=font(40), fill=accent, anchor=anchor)
        layers.append((layer(sub, "c"), 1.7))
    return layers


def beat_length(music, length, bars=2):
    """Clip length rounded to a whole number of `bars` beats of the music so cuts land on the beat; unchanged if no tempo is found."""
    try:
        from engine.beat_sync import detect_beats
        beats = detect_beats(music, max_duration=90, min_interval=0.3, max_interval=1.5)
        gaps = sorted(b - a for a, b in zip(beats, beats[1:]) if 0.25 < b - a < 1.6)
        if len(gaps) < 6:
            return length
        beat = gaps[len(gaps) // 2]
        unit = beat * bars
        snapped = max(1, round(length / unit)) * unit
        return snapped if 0.6 * length <= snapped <= 1.5 * length else length
    except Exception:
        return length


def spaced(text):
    """'Petra' -> 'P E T R A' (wide letter spacing reads as cinematic)."""
    text = str(text)
    if len(text) > 24:
        return text.upper()
    return "   ".join(" ".join(w.upper()) for w in text.split())


def cinematic_card_png(path, title, line="", small=""):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    f_t, f_l, f_s = _font(96, title), _font(46, line), _font(36, small)
    y = H // 2 - 60
    for ln in _wrap(d, title.upper(), f_t, W - 200):
        d.text((W // 2, y), ln, font=f_t, fill=(240, 232, 216), anchor="mm")
        y += 112
    d.line([(W // 2 - 70, y + 10), (W // 2 + 70, y + 10)], fill=(200, 170, 120), width=3)
    y += 60
    for ln in _wrap(d, line.upper(), f_l, W - 240):
        d.text((W // 2, y), ln, font=f_l, fill=(200, 170, 120), anchor="mm")
        y += 58
    if small:
        d.text((W // 2, H - 220), small.upper(), font=f_s, fill=(150, 145, 135), anchor="mm")
    img.save(path)
    return path


def caption_png(path, text, y_frac=0.74, size=78, lower=False):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if lower:       # small, spaced, bottom-left lower third with a thin rule
        f = _font(46, text)
        d.line([(70, int(H * 0.86) - 40), (190, int(H * 0.86) - 40)], fill=(200, 170, 120, 255), width=3)
        d.text((70, int(H * 0.86)), spaced(text), font=f, fill=(245, 240, 230, 255), anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0, 160))
        img.save(path)
        return path
    f = _font(size, text)
    lines = _wrap(d, text, f, W - 140)
    y = int(H * y_frac)
    for ln in lines:
        d.text((W // 2 + 3, y + 3), ln, font=f, fill=(0, 0, 0, 200), anchor="mm")
        d.text((W // 2, y), ln, font=f, fill=(255, 255, 255, 255), anchor="mm")
        y += int(size * 1.18)
    img.save(path)
    return path


def video_info(path, ffprobe="ffprobe"):
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    data = json.loads(r.stdout or "{}")
    st = (data.get("streams") or [{}])[0]
    return float(data.get("format", {}).get("duration") or 0), int(st.get("width") or 0), int(st.get("height") or 0)


def has_audio(path, ffprobe="ffprobe"):
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k"]


def render_card(ffmpeg, png, out, seconds=CARD_SECONDS):
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-t", f"{seconds}", "-i", png, "-f", "lavfi", "-t", f"{seconds}",
           "-i", "anullsrc=r=44100:cl=stereo", "-vf", "fade=t=in:st=0:d=0.3,fade=t=out:st=%.2f:d=0.3" % (seconds - 0.3), *ENC, "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Could not make a title card: " + (r.stderr or "")[-300:])


def render_clip(ffmpeg, src, start, seconds, out, caption_file=None, layout="auto", size=None, audio=True, cap_from=0.3, cap_gap=0.3, grade="", fade_s=0.2, layers=None):
    w, h = size or (0, 0)
    portrait = h > w > 0
    if layout == "crop" or (layout == "auto" and portrait == (H > W)):
        base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    else:
        base = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    fade = (f",{grade}" if grade else "") + f",fade=t=in:st=0:d={fade_s}:color=black,fade=t=out:st={seconds - fade_s:.2f}:d={fade_s}:color=black"
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{seconds:.2f}", "-i", src]
    if layers:
        n = len(layers)
        for png, _ts in layers:
            cmd += ["-loop", "1", "-t", f"{seconds:.2f}", "-i", png]
        chain, cur = [f"[0:v]{base}[v0]"], "v0"
        for i, (_png, ts) in enumerate(layers, 1):
            chain.append(f"[{i}:v]format=rgba,fade=t=in:st={ts:.2f}:d=0.7:alpha=1,fade=t=out:st={max(ts + 0.8, seconds - 0.6):.2f}:d=0.4:alpha=1[l{i}]")
            chain.append(f"[{cur}][l{i}]overlay=0:0[v{i}]")
            cur = f"v{i}"
        vf = ";".join(chain) + f";[{cur}]null{fade}[vout]"
    elif caption_file:
        n = 1
        cmd += ["-loop", "1", "-t", f"{seconds:.2f}", "-i", caption_file]
        vf = f"[0:v]{base}[v0];[v0][1:v]overlay=0:0:enable='between(t,{cap_from:.2f},{max(cap_from + 0.1, seconds - cap_gap):.2f})'{fade}[vout]"
    else:
        n = 0
        vf = f"[0:v]{base}{fade}[vout]"
    cmd += ["-filter_complex", vf, "-map", "[vout]"]
    if audio:
        cmd += ["-map", "0:a:0", "-af", f"afade=t=in:st=0:d={fade_s},afade=t=out:st={seconds - fade_s:.2f}:d={fade_s},aresample=44100"]
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.2f}", "-i", "anullsrc=r=44100:cl=stereo", "-map", f"{n + 1}:a"]
    cmd += [*ENC, "-t", f"{seconds:.2f}", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("Could not cut a clip: " + (r.stderr or "")[-400:])


def concat(ffmpeg, parts, out, session_dir, music=None, music_gain=0.25):
    lst = os.path.join(session_dir, "recap_parts.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '" + os.path.abspath(p).replace("\\", "/").replace("'", "'\\''") + "'\n")
    joined = out if not music else os.path.join(session_dir, "recap_nomusic.mp4")
    r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Could not join the recap: " + (r.stderr or "")[-300:])
    if music:
        r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-i", music,
                            "-filter_complex", f"[1:a]volume={music_gain}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("Could not add the music: " + (r.stderr or "")[-300:])


def scenic_score(jpeg):
    """How striking a frame is: colourful and with real contrast scores high, grey/dark/flat frames low. 0..1."""
    import io
    from PIL import Image, ImageStat
    try:
        img = Image.open(io.BytesIO(jpeg)).convert("RGB").resize((64, 64))
    except Exception:
        return 0.0
    hsv = img.convert("HSV")
    sat = ImageStat.Stat(hsv).mean[1] / 255.0
    lum = img.convert("L")
    st = ImageStat.Stat(lum)
    contrast = min(1.0, st.stddev[0] / 70.0)
    bright = st.mean[0] / 255.0
    exposure = 1.0 - min(1.0, abs(bright - 0.5) * 2.0)           # very dark or blown-out frames are not scenic
    return round(0.5 * sat + 0.3 * contrast + 0.2 * exposure, 4)


def pick_glimpses(days, k, length, grab=None, score=scenic_score, per_candidates=6, rate=None, shortlist=24):
    """The k most scenic windows over the whole trip: [{file, start, end, size, day}], in trip order.

    Every video is sampled at `per_candidates` evenly spread windows; one frame of each is scored. No day contributes more than
    ceil(k / days) + 1 glimpses, so the opening shows the whole trip and not only its prettiest day."""
    if grab is None:
        from engine.visual_context import grab_frames
        grab = lambda f, s, e: grab_frames(f, s, e, n=1)  # noqa: E731
    cands = []
    for di, d in enumerate(days):
        for f, dur, w, h in d["infos"]:
            for s, e in pick_windows(dur, per_candidates, length):
                frames = grab(f, s, e)
                if frames:
                    cands.append({"file": f, "start": s, "end": e, "size": (w, h), "day": di, "score": score(frames[0]), "_frame": frames[0]})
    if rate and cands:
        # the colour score is only a first filter; the vision model judges the shortlist (lakes, canyons, mountains; no text overlays)
        top = sorted(cands, key=lambda c: c["score"], reverse=True)[:shortlist]
        rated = rate([c["_frame"] for c in top])
        if rated and len(rated) == len(top):
            cands = []
            for c, r in zip(top, rated):
                if r.get("overlay"):
                    continue
                c["score"] = float(r.get("score", 0)) + 0.5 * c["score"]          # the colour score breaks ties
                cands.append(c)
    for c in cands:
        c.pop("_frame", None)
    cap = int(-(-k // max(1, len(days)))) + 1
    chosen, used = [], {}
    ranked = sorted(cands, key=lambda c: c["score"], reverse=True)
    firsts = []                                                  # the best shot of every day goes in first: the opening shows the whole trip
    for c in ranked:
        if c["day"] not in {x["day"] for x in firsts}:
            firsts.append(c)
    for c in firsts[:k] + [c for c in ranked if c not in firsts]:
        if len(chosen) >= k:
            break
        if used.get(c["day"], 0) >= cap or any(c["file"] == x["file"] and abs(c["start"] - x["start"]) < length * 2 for x in chosen):
            continue
        chosen.append(c)
        used[c["day"]] = used.get(c["day"], 0) + 1
    return sorted(chosen, key=lambda c: (c["day"], c["file"], c["start"]))


def decide_look(paths, probe=None, sample=12):
    """Picks the style and frame shape from the footage itself: mostly widescreen footage (cameras, drones) -> the cinematic travel film in
    2.35:1; mostly vertical phone clips -> the fast 9:16 hype recap. Returns (style, aspect, reason)."""
    probe = probe or video_info
    files = [v[0] if isinstance(v, tuple) else v for v in collect_videos(list(paths))]
    step = max(1, len(files) // sample)
    wide = tall = 0
    for f in files[::step][:sample]:
        try:
            _d, w, h = probe(f)
        except Exception:
            continue
        if w > h > 0:
            wide += 1
        elif h > w > 0:
            tall += 1
    if wide > tall:
        return "cinematic", "2.35:1", f"{wide} of {wide + tall} sampled videos are widescreen"
    return "hype", "9:16", f"{tall} of {wide + tall} sampled videos are vertical" if tall else "no readable footage to judge from"


def make_recap(paths, session_dir, trip_name="", note="", total_seconds=60, music=None, visual=False, layout="auto",
               ask=None, describe=None, ffmpeg=None, hook="", style="hype", grab=None, stops=None, aspect=None):
    """Build the recap. Returns {"video", "itinerary_md", "itinerary_json", "days"}. Raises ValueError for no videos.
    aspect: "9:16" (default), "16:9" or "2.35:1"; the cinematic style defaults to 2.35:1."""
    global W, H
    if style == "auto":
        style, auto_aspect, why = decide_look(paths)
        aspect = aspect or auto_aspect
        print(f"[Log] Auto look: {style} {aspect} ({why}).")
    old = (W, H)
    key = aspect or ("2.35:1" if style == "cinematic" else "9:16")
    if key not in ASPECTS:
        raise ValueError(f"Unknown aspect {key!r}. Choose one of: {', '.join(ASPECTS)}")
    W, H = ASPECTS[key]
    try:
        return _make_recap(paths, session_dir, trip_name, note, total_seconds, music, visual, layout, ask, describe, ffmpeg, hook, style, grab, stops)
    finally:
        W, H = old


def _make_recap(paths, session_dir, trip_name, note, total_seconds, music, visual, layout, ask, describe, ffmpeg, hook, style, grab, stops):
    videos = collect_videos(list(paths))
    days_paths = group_days(videos)
    if not days_paths:
        raise ValueError("No videos found. Give video files, or folders with one folder per day.")
    stops = parse_stops(stops)
    if stops:
        days_paths = split_into(days_paths, len(stops))
        stops = stops[:len(days_paths)]
        print(f"[Log] {len(stops)} stop(s): {', '.join(stops)}.")
    unit = "Stop" if stops else "Day"
    os.makedirs(session_dir, exist_ok=True)
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cine = style == "cinematic"
    hype = style != "plain"
    grade, fade_s = (CINEMATIC_GRADE, 0.5) if cine else ("", 0.2)
    opening = (GLIMPSES * GLIMPSE_SECONDS + CARD_SECONDS) if hype else 0.0      # glimpses + the trip title card
    all_infos = []
    for files in days_paths:
        infos = []
        for f in files:
            dur, w, h = video_info(f)
            if dur > 1:
                infos.append((f, dur, w, h))
        if infos:
            all_infos.append(infos)
    if not all_infos:
        raise ValueError("None of the videos could be read.")
    if cine:
        grade = pick_grade(ffmpeg, [i[0] for infos in all_infos for i in infos])
        print(f"[Log] Colour grade: {'warm' if grade == CINEMATIC_GRADE else 'cool'} (from the footage).")
    counts, clip_len = plan_days([len(i) for i in all_infos], max(float(total_seconds) - opening, len(all_infos) * 6.0))
    if cine and music:
        snapped = beat_length(music, clip_len)
        if snapped != clip_len:
            print(f"[Log] Cuts follow the music: moments {clip_len:.2f}s -> {snapped:.2f}s (whole beats).")
            clip_len = snapped
    print(f"[Log] Trip recap: {len(all_infos)} day(s), {sum(len(i) for i in all_infos)} video(s); moments per day: {counts} of {clip_len:g}s.")

    days = []
    for di, infos in enumerate(all_infos, 1):
        n_clips = counts[di - 1]
        total_dur = sum(i[1] for i in infos)
        moments = []
        for f, dur, w, h in infos:
            share = max(1, int(round(n_clips * dur / total_dur))) if len(infos) > 1 else n_clips
            levels = loudness_per_second(f, ffmpeg=ffmpeg)
            for s, e in pick_windows(dur, share, clip_len, levels):
                moments.append({"file": f, "start": s, "end": e, "size": (w, h)})
        # keep the day's moments in filming order and trim to the plan
        moments.sort(key=lambda m: (infos_order(infos, m["file"]), m["start"]))
        while len(moments) > n_clips:
            moments.pop(len(moments) // 2)
        print(f"[Log] Day {di}: {len(moments)} moment(s) from {len(infos)} video(s).")
        days.append({"files": [i[0] for i in infos], "moments": moments, "infos": infos})
    if not days:
        raise ValueError("None of the videos could be read.")

    if visual:
        from engine.visual_context import describe_candidates
        for d in days:
            for m in d["moments"]:
                one = describe_candidates(m["file"], [{"start": m["start"], "end": m["end"]}], about=f"{trip_name} {note}".strip(),
                                          cache_path=os.path.join(session_dir, "visual_context.json"),
                                          ask=describe)
                if one and one[0].get("visual"):
                    m["visual"] = one[0]["visual"]

    it = write_itinerary(trip_name, note, days, ask=ask, stops=stops)
    parts = []
    parts_dir = os.path.join(session_dir, "recap_parts")
    os.makedirs(parts_dir, exist_ok=True)
    it["hook"] = (hook or it.get("hook") or "").strip() or (f"{trip_name}: you have to see this" if trip_name else "You have to see this place")
    if hype:
        rate = None
        if visual:
            from engine.visual_context import rate_scenery
            rate = rate_scenery
        glimpses = pick_glimpses(days, GLIMPSES, GLIMPSE_SECONDS, grab=grab, rate=rate)
        if glimpses:
            hook_png = caption_png(os.path.join(parts_dir, "hook.png"), it["hook"], y_frac=0.3, size=96, lower=cine)
            for gi, g in enumerate(glimpses, 1):
                out = os.path.join(parts_dir, f"glimpse_{gi}.mp4")
                render_clip(ffmpeg, g["file"], g["start"], GLIMPSE_SECONDS, out, hook_png, layout, g["size"], audio=has_audio(g["file"]),
                            cap_from=0.0, cap_gap=0.0, grade=grade, fade_s=fade_s)
                parts.append(out)
            print(f"[Log] Opening: hook \"{it['hook']}\" over {len(glimpses)} glimpse(s).")
        if cine:
            m0 = days[0]["moments"][0]
            out = os.path.join(parts_dir, "trip_title.mp4")
            lay = cinematic_layers(os.path.join(parts_dir, "trip_title"), it["title"], " · ".join(stops) if stops else "A travel film", "",
                                   look=frame_look(ffmpeg, m0["file"], m0["start"] + 1.0), index=0)
            render_clip(ffmpeg, m0["file"], m0["start"], 3.4, out, None, layout, m0["size"], audio=has_audio(m0["file"]), grade=grade, fade_s=fade_s, layers=lay)
            parts.append(out)
        else:
            title = title_card_png(os.path.join(parts_dir, "trip_title.png"), it["title"], " · ".join(stops) if stops else "Day by day", "")
            card = os.path.join(parts_dir, "trip_title.mp4")
            render_card(ffmpeg, title, card)
            parts.append(card)
    for di, (d, row) in enumerate(zip(days, it["days"]), 1):
        if cine:
            card_png = None      # the title appears over the day's first shot instead of a card
        elif stops:
            card_png = title_card_png(os.path.join(parts_dir, f"card_{di}.png"), row["title"], f"Stop {di} of {len(days)}", row["summary"])
        else:
            card_png = title_card_png(os.path.join(parts_dir, f"card_{di}.png"), f"Day {di}", row["title"], row["summary"])
        if card_png:
            card = os.path.join(parts_dir, f"card_{di}.mp4")
            render_card(ffmpeg, card_png, card)
            parts.append(card)
        for mi, (m, cap) in enumerate(zip(d["moments"], row["captions"]), 1):
            cap_png = caption_png(os.path.join(parts_dir, f"cap_{di}_{mi}.png"), cap, lower=cine) if cap and not (cine and mi == 1) else None
            out = os.path.join(parts_dir, f"clip_{di}_{mi}.mp4")
            lay, secs = None, m["end"] - m["start"]
            if cine and mi == 1:
                lay = cinematic_layers(os.path.join(parts_dir, f"title_{di}"), row["title"], f"{unit} {di}" if len(days) > 1 else "",
                                       look=frame_look(ffmpeg, m["file"], m["start"] + 1.0), index=di)
                secs = max(secs, 3.2)
            render_clip(ffmpeg, m["file"], m["start"], secs, out, cap_png, layout, m["size"], audio=has_audio(m["file"]), grade=grade, fade_s=fade_s, layers=lay)
            parts.append(out)
        print(f"[Log] Day {di} rendered.")
    video = os.path.join(session_dir, "recap.mp4")
    concat(ffmpeg, parts, video, session_dir, music=music)
    md_path, js_path = os.path.join(session_dir, "itinerary.md"), os.path.join(session_dir, "itinerary.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(itinerary_markdown(it, days, unit))
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump({"itinerary": it, "days": [{"files": d["files"], "moments": [{k: v for k, v in m.items() if k != "size"} for m in d["moments"]]}
                                             for d in days]}, f, indent=1, ensure_ascii=False)
    print(f"[Success] Trip recap ready at: {video}")
    print(f"[Log] Itinerary: {md_path}")
    return {"video": video, "itinerary_md": md_path, "itinerary_json": js_path, "days": len(days)}


def infos_order(infos, f):
    return next((i for i, x in enumerate(infos) if x[0] == f), 0)


def run(args, target_bitrate=None, target_preset=None):
    paths = getattr(args, "trip_videos", None) or ([args.source_video] if getattr(args, "source_video", None) else [])
    session_dir = args.session_dir if args.session_dir else f"sessions/trip_{int(time.time())}"
    album = getattr(args, "trip_album", None)
    if album:
        from engine.gphotos_album import AlbumError, download_album
        day = (getattr(args, "trip_day", "") or "").strip()
        try:
            got = download_album(album, os.path.join(session_dir, "videos"), only_days=[day] if day else None)
        except (AlbumError, OSError) as e:
            print(f"[Error] Could not read the Google Photos album: {e} Download the videos yourself and use --trip_videos.")
            sys.exit(1)
        if not got["folders"]:
            print("[Error] The album has no videos" + (f" for '{day}'" if day else "") + " (shorter than 5 minutes).")
            sys.exit(1)
        if got["failed"]:
            print(f"[Warning] {got['failed']} video(s) could not be downloaded and are left out.")
        paths = list(paths) + got["folders"]
        if not getattr(args, "trip_name", ""):
            args.trip_name = got["title"]
    if not paths:
        print("[Error] TRIP mode needs --trip_videos (video files, or folders with one folder per day) or --trip_album (a shared "
              "Google Photos link), e.g. --mode TRIP --trip_videos day1 day2 --trip_name Almaty")
        sys.exit(2)
    layout = getattr(args, "layout", "auto")
    try:
        make_recap(paths, session_dir, trip_name=getattr(args, "trip_name", "") or "", note=getattr(args, "user_context", "") or "",
                   total_seconds=getattr(args, "recap_length", 60) or 60, music=getattr(args, "music", None),
                   visual=bool(getattr(args, "visual_context", False)), hook=getattr(args, "recap_hook", "") or "",
                   style=getattr(args, "recap_style", "auto") or "auto", stops=getattr(args, "trip_stops", None), aspect=getattr(args, "recap_aspect", None), layout="fit" if layout == "fit" else ("crop" if layout == "crop" else "auto"))
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        sys.exit(1)
    sys.exit(0)

