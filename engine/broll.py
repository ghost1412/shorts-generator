"""Auto B-roll cutaways (`--broll`).

On the finished clip, a short stock clip is laid over the picture for ~2 s whenever a concrete noun is spoken
("money", "car", "ocean" ...). The original audio keeps playing and captions stay visible: the cutaway covers only the
upper part of the frame (above the caption line, and never the bottom half of a split_filler layout).

Pieces, all offline-testable except the download:
  * `pick_cutaways`      words -> [{start, end, keyword, query}] (keyword lexicon; an LLM `ask` can add queries)
  * `cutaway_region`     the pixel box the cutaway may cover for a given layout
  * `fetch_footage`      cache -> Pexels (needs PEXELS_API_KEY) -> local library -> None
  * `render_cutaways`    one FFmpeg overlay pass (video re-encoded, audio copied)
  * `apply_to_clip`      the whole thing for one finished clip; never raises, the clip is left alone on failure
Without PEXELS_API_KEY and without a local library no cutaway is made and the clip is untouched.
"""
import glob
import os
import random
import re
import shutil
import subprocess

CACHE_DIR = os.path.join("assets", "broll")
LOCAL_DIR = os.path.join("assets", "backgrounds", "local")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv")

MIN_START = 2.0        # never in the first seconds (the hook lives there)
HOOK_MIN_START = 3.0   # --hook_overlay shows its title for ~2.8 s
MIN_SPACING = 8.0      # at most one cutaway per this many seconds (start to start)
MIN_LEN, DEFAULT_LEN, MAX_LEN = 1.5, 2.2, 3.0
LEAD = 0.15            # the picture changes just before the word is said
TAIL_GUARD = 0.5       # leave the last half second on the speaker
CAPTION_MARGIN = 170   # px (of 1920) kept free above the caption line
DEFAULT_CAPTION_Y = 1150

# word -> stock search query ("" = the word itself). Concrete, filmable things only; abstract words give bad footage.
_QUERY = {}
for _w in """money cash dollar coin gold diamond jewelry wallet bank bitcoin crypto stock market economy
car truck bus train plane airplane airport flight ship boat bike motorcycle road highway traffic rocket satellite
house home apartment kitchen bedroom office building skyscraper city street village farm factory warehouse
phone smartphone laptop computer keyboard screen robot camera drone server data code chip battery
food pizza burger coffee tea pasta salad bread cake fruit vegetable meat steak sushi chocolate restaurant
dog cat horse bird fish shark whale lion tiger elephant monkey snake spider bee butterfly wolf bear
ocean sea beach wave river lake mountain forest jungle desert island waterfall rain snow storm fire volcano
sun moon star planet galaxy space earth cloud sky sunset sunrise lightning rainbow
tree flower garden grass leaf
doctor hospital medicine surgery gym workout running football soccer basketball tennis golf swimming boxing yoga
school classroom student book library exam teacher university
baby child kids family wedding party dance concert guitar piano music microphone
gun sword knife explosion tank soldier army police
clock watch calendar key door window bridge tower castle temple church statue museum
shoes shirt dress suit hat glasses
""".split():
    _QUERY[_w] = _w
_QUERY.update({"dollars": "money", "bucks": "money", "cash": "money cash", "millions": "money", "billion": "money",
               "investing": "stock market", "invest": "stock market", "shares": "stock market", "bitcoin": "bitcoin",
               "cars": "car", "vehicle": "car", "plane": "airplane", "planes": "airplane", "flights": "airplane flight",
               "workout": "gym workout", "exercise": "gym workout", "football": "football", "iphone": "smartphone",
               "android": "smartphone", "app": "smartphone", "internet": "computer", "website": "computer",
               "hacker": "hacker computer", "ai": "robot", "robots": "robot", "dinosaur": "dinosaur", "oceans": "ocean",
               "seas": "sea", "mountains": "mountain", "forests": "forest", "cities": "city", "streets": "street",
               "kids": "children playing", "children": "children playing", "kitchen": "kitchen cooking", "cooking": "cooking",
               "restaurant": "restaurant", "coffee": "coffee", "house": "house", "houses": "house", "homes": "house"})


def normalize_word(word):
    """Lower-case, strip punctuation and a plural 's' (`cars` -> `car`) when the singular is in the lexicon."""
    w = re.sub(r"[^a-z0-9']", "", (word or "").lower()).replace("'s", "")
    for suffix in ("es", "s"):
        if w.endswith(suffix) and w[: -len(suffix)] in _QUERY:
            return w[: -len(suffix)]
    return w


def llm_queries(words, ask, limit=8):
    """Optional: ask an LLM which spoken words deserve footage. `ask(prompt) -> parsed JSON`.
    Returns {normalized word: stock search query}. Any failure gives {} so the keyword lexicon still works."""
    text = " ".join(w.get("word", "") for w in words)[:3000]
    prompt = (
        "Pick up to %d words from this transcript that name something concrete and filmable "
        "(an object, place, animal, activity). For each give a 2-3 word stock-footage search query.\n"
        "Transcript: %s\nReturn ONLY JSON: [{\"word\": \"<word as spoken>\", \"query\": \"<search>\"}]" % (limit, text))
    try:
        data = ask(prompt)
        return {normalize_word(i["word"]): str(i["query"]).strip() for i in data
                if isinstance(i, dict) and i.get("word") and i.get("query")}
    except Exception:
        return {}


def pick_cutaways(words, duration, min_start=MIN_START, spacing=MIN_SPACING, length=DEFAULT_LEN, ask=None):
    """Choose the moments. `words`: [{'word','start','end'}] on the finished clip's timeline (seconds).

    Rules: nothing before `min_start`, at least `spacing` seconds between cutaway starts, each cutaway
    MIN_LEN..MAX_LEN long and never into the last TAIL_GUARD seconds, each keyword used once per clip.
    Returns [{'start','end','keyword','query'}] in time order.
    """
    extra = llm_queries(words, ask) if ask else {}
    length = min(MAX_LEN, max(MIN_LEN, length))
    seen, candidates = set(), []
    for w in words:
        key = normalize_word(w.get("word"))
        query = extra.get(key) or _QUERY.get(key)
        if not query:
            continue
        if key in seen or float(w["start"]) < min_start:   # said during the hook: no cutaway for it
            continue
        start = max(min_start, float(w["start"]) - LEAD)
        end = min(start + length, duration - TAIL_GUARD)
        if end - start < MIN_LEN:
            continue
        seen.add(key)
        candidates.append({"start": round(start, 2), "end": round(end, 2), "keyword": key, "query": query,
                           "score": 2 if key in extra else 1})
    candidates.sort(key=lambda c: (-c["score"], c["start"]))
    chosen = []
    for c in candidates:
        if all(abs(c["start"] - o["start"]) >= spacing for o in chosen):
            chosen.append(c)
    chosen.sort(key=lambda c: c["start"])
    return [{k: c[k] for k in ("start", "end", "keyword", "query")} for c in chosen]


def cutaway_region(width, height, layout="single", caption_y=DEFAULT_CAPTION_Y):
    """(x, y, w, h) in pixels the cutaway may cover; None when the output is not vertical.

    Single layout: from the top down to a margin above the caption line (so animated captions stay readable).
    Split layout: only inside the clip half, above the captions that sit just over the seam.
    """
    if width <= 0 or height <= width:
        return None
    scale = height / 1920.0
    cap = caption_y if caption_y else DEFAULT_CAPTION_Y
    if layout == "split_filler":
        from engine.filler import split_caption_y
        cap = min(split_caption_y(caption_y), 960)
    h = int((cap - CAPTION_MARGIN) * scale)
    if layout == "split_filler":
        h = min(h, height // 2)
    h -= h % 2
    return (0, 0, width - width % 2, h) if h >= 200 else None


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "clip"


def _find_local(rng=random):
    files = [p for p in glob.glob(os.path.join(LOCAL_DIR, "*")) if p.lower().endswith(VIDEO_EXTS)]
    return rng.choice(files) if files else None


def _download_pexels(query, out_path):
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None
    try:
        import requests
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                         params={"query": query, "per_page": 5, "orientation": "portrait"}, timeout=15)
        r.raise_for_status()
        for video in r.json().get("videos", []):
            files = sorted((f for f in video.get("video_files", []) if f.get("link")),
                           key=lambda f: abs((f.get("height") or 0) - 1280))
            if files:
                content = requests.get(files[0]["link"], timeout=45).content
                if len(content) > 1000:
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                    with open(out_path, "wb") as fh:
                        fh.write(content)
                    return out_path
    except Exception as e:
        print(f"[Warning] B-roll download failed for '{query}': {e}")
    return None


def fetch_footage(query, cache_dir=CACHE_DIR, download=_download_pexels, local_pick=_find_local):
    """Footage for `query`: cached download -> Pexels -> a random local clip -> None (the cutaway is skipped)."""
    path = os.path.join(cache_dir, f"broll_{_slug(query)}.mp4")
    if os.path.isfile(path) and os.path.getsize(path) > 1000:
        return path
    got = download(query, path)
    if got and os.path.isfile(got):
        return got
    return local_pick()


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _probe(path, ffmpeg):
    """(width, height, duration) from ffmpeg's banner (no ffprobe needed)."""
    err = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True).stderr
    size = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", err)
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
    if not size or not dur:
        raise RuntimeError(f"Could not read video info for {path}")
    return int(size.group(1)), int(size.group(2)), int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))


def build_overlay_command(ffmpeg, video, items, region, output, fps=30):
    """FFmpeg command laying each item's footage over `region` during its window. items: [{'start','end','footage'}]."""
    x, y, w, h = region
    cmd = [ffmpeg, "-y", "-i", video]
    chain, last = [], "0:v"
    for n, it in enumerate(items, start=1):
        length = it["end"] - it["start"]
        cmd += ["-stream_loop", "-1", "-i", it["footage"]]
        fade = min(0.15, length / 4)
        chain.append(
            f"[{n}:v]trim=duration={length:.3f},setpts=PTS-STARTPTS,fps={fps},"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuva420p,"
            f"fade=t=in:st=0:d={fade:.2f}:alpha=1,fade=t=out:st={length - fade:.3f}:d={fade:.2f}:alpha=1,"
            f"setpts=PTS+{it['start']:.3f}/TB[b{n}]")
        chain.append(f"[{last}][b{n}]overlay={x}:{y}:eof_action=pass:format=auto[v{n}]")
        last = f"v{n}"
    cmd += ["-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", output]
    return cmd


def render_cutaways(video, items, region, ffmpeg=None):
    """Overlay `items` on `video` in place. True when the file was replaced; on any failure it is left as it was."""
    ffmpeg = ffmpeg or _ffmpeg()
    tmp = os.path.join(os.path.dirname(os.path.abspath(video)), f".broll_{os.getpid()}_{os.path.basename(video)}")
    try:
        res = subprocess.run(build_overlay_command(ffmpeg, video, items, region, tmp), capture_output=True, text=True)
        if res.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) < 1000:
            print(f"[Warning] B-roll overlay failed: {res.stderr[-300:].strip()}")
            return False
        os.replace(tmp, video)
        return True
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def clip_words(transcript_data, start, end, keep_intervals=None, tighten_mode="cut", remove_fillers=False):
    """Words of source range [start, end] on the finished clip's timeline: the same retiming the captions use.
    keep_intervals: the run's keep intervals in source seconds (None when --tighten is off).
    Returns None when the timeline cannot be reconstructed (tighten_mode other than 'cut')."""
    from engine.transcript_edit import clip_transcript, plan_keeps
    duration = end - start
    keeps = [(0.0, duration)]
    if keep_intervals:
        if tighten_mode != "cut":
            return None
        local = [(max(s, start) - start, min(e, end) - start) for s, e in keep_intervals if min(e, end) > max(s, start)]
        fine = {"padding": 0.02, "min_gap": 0.06} if remove_fillers else {}
        keeps = plan_keeps(local, duration, **fine) or keeps
    words = []
    for seg in clip_transcript(transcript_data, start, end, keeps).get("segments", []):
        words.extend(seg.get("words") or [])
    return words


def apply_to_clip(video, words, layout="single", caption_y=DEFAULT_CAPTION_Y, hook_overlay=False, ask=None,
                  fetch=fetch_footage):
    """B-roll for one finished clip. Returns the number of cutaways placed (0 = clip untouched). Never raises."""
    try:
        ffmpeg = _ffmpeg()
        width, height, duration = _probe(video, ffmpeg)
        region = cutaway_region(width, height, layout, caption_y)
        if region is None:
            print("[Log] B-roll: only vertical clips get cutaways; skipped.")
            return 0
        picks = pick_cutaways(words, duration, min_start=HOOK_MIN_START if hook_overlay else MIN_START, ask=ask)
        items = []
        for p in picks:
            footage = fetch(p["query"])
            if footage:
                items.append(dict(p, footage=footage))
        if not items:
            print("[Log] B-roll: no matching moments or no footage available (set PEXELS_API_KEY or add clips to "
                  f"{LOCAL_DIR}); clip left as it was.")
            return 0
        if render_cutaways(video, items, region, ffmpeg):
            print(f"[Log] B-roll: {len(items)} cutaway(s) in {os.path.basename(video)} ({', '.join(i['keyword'] for i in items)})")
            return len(items)
    except Exception as e:
        print(f"[Warning] B-roll skipped for {os.path.basename(str(video))}: {e}")
    return 0
