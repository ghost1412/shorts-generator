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
            ask = lambda p: get_llm_response(p, "You write short, honest travel captions. Reply with raw JSON only.", max_tokens=1200)  # noqa: E731
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


def caption_png(path, text, y_frac=0.74, size=78):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
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


def render_clip(ffmpeg, src, start, seconds, out, caption_file=None, layout="auto", size=None, audio=True, cap_from=0.3, cap_gap=0.3):
    w, h = size or (0, 0)
    portrait = h > w > 0
    if layout == "crop" or (layout == "auto" and portrait):
        base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    else:
        base = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    fade = f",fade=t=in:st=0:d=0.2,fade=t=out:st={seconds - 0.2:.2f}:d=0.2"
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{seconds:.2f}", "-i", src]
    if caption_file:
        cmd += ["-loop", "1", "-t", f"{seconds:.2f}", "-i", caption_file]
        vf = f"[0:v]{base}[v0];[v0][1:v]overlay=0:0:enable='between(t,{cap_from:.2f},{max(cap_from + 0.1, seconds - cap_gap):.2f})'{fade}[vout]"
    else:
        vf = f"[0:v]{base}{fade}[vout]"
    cmd += ["-filter_complex", vf, "-map", "[vout]"]
    if audio:
        cmd += ["-map", "0:a:0", "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={seconds - 0.2:.2f}:d=0.2,aresample=44100"]
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.2f}", "-i", "anullsrc=r=44100:cl=stereo", "-map", "2:a" if caption_file else "1:a"]
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


def pick_glimpses(days, k, length, grab=None, score=scenic_score, per_candidates=6):
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
                    cands.append({"file": f, "start": s, "end": e, "size": (w, h), "day": di, "score": score(frames[0])})
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


def make_recap(paths, session_dir, trip_name="", note="", total_seconds=60, music=None, visual=False, layout="auto",
               ask=None, describe=None, ffmpeg=None, hook="", style="hype", grab=None, stops=None):
    """Build the recap. Returns {"video", "itinerary_md", "itinerary_json", "days"}. Raises ValueError for no videos."""
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
    hype = style != "plain"
    opening = (GLIMPSES * GLIMPSE_SECONDS + CARD_SECONDS) if hype else 0.0      # glimpses + the trip title card
    n_clips, clip_len = plan_counts(len(days_paths), max(float(total_seconds) - opening, len(days_paths) * 6.0))
    print(f"[Log] Trip recap: {len(days_paths)} day(s), {sum(len(d) for d in days_paths)} video(s); {n_clips} moment(s) of {clip_len:g}s per day.")

    days = []
    for di, files in enumerate(days_paths, 1):
        infos = []
        for f in files:
            dur, w, h = video_info(f)
            if dur > 1:
                infos.append((f, dur, w, h))
        if not infos:
            continue
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
        from engine import visual_context
        for d in days:
            for m in d["moments"]:
                one = describe_candidates(m["file"], [{"start": m["start"], "end": m["end"]}], about=f"{trip_name} {note}".strip(),
                                          cache_path=os.path.join(session_dir, "visual_context.json"),
                                          ask=describe or visual_context.describe)
                if one and one[0].get("visual"):
                    m["visual"] = one[0]["visual"]

    it = write_itinerary(trip_name, note, days, ask=ask, stops=stops)
    parts = []
    parts_dir = os.path.join(session_dir, "recap_parts")
    os.makedirs(parts_dir, exist_ok=True)
    it["hook"] = (hook or it.get("hook") or "").strip() or (f"{trip_name}: you have to see this" if trip_name else "You have to see this place")
    if hype:
        glimpses = pick_glimpses(days, GLIMPSES, GLIMPSE_SECONDS, grab=grab)
        if glimpses:
            hook_png = caption_png(os.path.join(parts_dir, "hook.png"), it["hook"], y_frac=0.3, size=96)
            for gi, g in enumerate(glimpses, 1):
                out = os.path.join(parts_dir, f"glimpse_{gi}.mp4")
                render_clip(ffmpeg, g["file"], g["start"], GLIMPSE_SECONDS, out, hook_png, layout, g["size"], audio=has_audio(g["file"]),
                            cap_from=0.0, cap_gap=0.0)
                parts.append(out)
            print(f"[Log] Opening: hook \"{it['hook']}\" over {len(glimpses)} glimpse(s).")
        title = title_card_png(os.path.join(parts_dir, "trip_title.png"), it["title"], " · ".join(stops) if stops else "Day by day", "")
        card = os.path.join(parts_dir, "trip_title.mp4")
        render_card(ffmpeg, title, card)
        parts.append(card)
    for di, (d, row) in enumerate(zip(days, it["days"]), 1):
        if stops:
            card_png = title_card_png(os.path.join(parts_dir, f"card_{di}.png"), row["title"], f"Stop {di} of {len(days)}", row["summary"])
        else:
            card_png = title_card_png(os.path.join(parts_dir, f"card_{di}.png"), f"Day {di}", row["title"], row["summary"])
        card = os.path.join(parts_dir, f"card_{di}.mp4")
        render_card(ffmpeg, card_png, card)
        parts.append(card)
        for mi, (m, cap) in enumerate(zip(d["moments"], row["captions"]), 1):
            cap_png = caption_png(os.path.join(parts_dir, f"cap_{di}_{mi}.png"), cap) if cap else None
            out = os.path.join(parts_dir, f"clip_{di}_{mi}.mp4")
            render_clip(ffmpeg, m["file"], m["start"], m["end"] - m["start"], out, cap_png, layout, m["size"], audio=has_audio(m["file"]))
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
                   style=getattr(args, "recap_style", "hype") or "hype", stops=getattr(args, "trip_stops", None), layout="fit" if layout == "fit" else ("crop" if layout == "crop" else "auto"))
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        sys.exit(1)
    sys.exit(0)

