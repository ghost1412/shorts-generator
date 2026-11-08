"""Trip recap: several videos (day 1, day 2, ...) -> one vertical recap with a title card per day and a written itinerary.

    python main.py --mode TRIP --trip_videos day1/ day2/ --trip_name "Northvale" --recap_length 60

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


def folder_names(videos):
    """Readable section names from the folders the videos came from, in the order the folders were given: 'henna evening one' ->
    'Henna evening one'. [] unless the videos come from at least two folders."""
    seen = list(dict.fromkeys(h for _p, h in videos if h))
    if len(seen) < 2:
        return []
    return [re.sub(r"\s+", " ", re.sub(r"[_]+", " ", h)).strip().capitalize() for h in seen]


def group_days(videos, by_folder=False):
    """[[path, ...], ...] one list per day, in day order.

    A day number in the folder or file name ("day2", "Day 02") wins; else the date the file was modified; videos that share neither
    form one day each in name order.
    by_folder (weddings, parties: one folder per part): one group per folder, in the order the folders were given, whatever the
    file dates are. Falls back to the normal grouping when the videos come from fewer than two folders."""
    if by_folder and len(folder_names(videos)) >= 2:
        groups = {}
        for path, hint in videos:
            groups.setdefault(hint or "", []).append(path)
        return [sorted(files, key=natural_key) for files in groups.values()]
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
    """['Pinemere Lake', 'Larkwater Lake', ...] from 'Pinemere Lake, Larkwater Lake; Stonegate Canyon' (or a list)."""
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


SAME_SPOT_KM = 0.15          # two shots filmed this close ...
SAME_SPOT_SECONDS = 240      # ... and this soon after each other are the same scene (a pose from three angles, one stretch of path)
_STOP_WORDS = set("a an the of in on at to and with is are was by for from into over near toward towards their his her two three".split())


def moment_time(m):
    """Seconds since midnight when the moment was filmed (from the file name HHMMSS_..., plus the offset in the video), None if unknown."""
    base = file_seconds(m["file"])
    return None if base is None else base + float(m["start"])


def same_scene(a, b):
    """True when two moments are almost certainly the same scene: the same video close together, or the same spot (GPS) filmed minutes apart."""
    if a["file"] == b["file"]:
        return abs(a["start"] - b["start"]) < 20
    ta, tb, la, lb = moment_time(a), moment_time(b), a.get("loc"), b.get("loc")
    if None in (ta, tb) or la is None or lb is None:
        return False
    from engine.geo import distance_km
    return abs(ta - tb) < SAME_SPOT_SECONDS and distance_km(la, lb) < SAME_SPOT_KM


def spread_moments(cands, n):
    """(chosen, spares): up to n moments in filming order with no two from the same scene; the rest are spares, nearest-first usable.

    `cands` are in filming order. When the scenes are fewer than n the spares fill the gap (a repeat beats a missing shot)."""
    chosen, spares = [], []
    for c in cands:
        (spares if any(same_scene(c, k) for k in chosen) else chosen).append(c)
    if len(chosen) > n:
        keep = sorted({round(i * (len(chosen) - 1) / max(1, n - 1)) for i in range(n)}) if n > 1 else [len(chosen) // 2]
        spares += [c for i, c in enumerate(chosen) if i not in keep]
        chosen = [chosen[i] for i in keep]
    elif len(chosen) < n:
        for c in list(spares):
            if len(chosen) >= n:
                break
            chosen.append(c)
            spares.remove(c)
    order = {id(c): i for i, c in enumerate(cands)}
    chosen.sort(key=lambda c: order[id(c)])
    return chosen, spares


def description_words(text):
    return {w for w in re.findall(r"[a-z]+", str(text or "").lower()) if w not in _STOP_WORDS and len(w) > 2}


def same_description(a, b, threshold=0.4):
    """True when two picture descriptions say nearly the same (word overlap)."""
    wa, wb = description_words(a), description_words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= threshold


_BORING = re.compile(r"\b(empty (?:\w+ ){0,2}(?:bench|room|street|path|chair|table|hallway|park)|blurry|out of focus|black screen|completely dark|lens (cap|is covered)|"
                     r"inside (a|the|his|her) pocket|nothing (is )?(visible|happening)|unclear|obscured|accidental|mating|pigeons?|buffet|dining (?:establishment|room|hall)|"
                     r"(?:very|too|mostly|extremely|pitch|almost) dark|pitch[- ]black|dimly lit|barely visible|"
                     r"(?:close-up|view|shot) of (?:the |a )?(?:ground|floor|pavement|sidewalk|dirt|asphalt|feet))\b", re.I)


def looks_boring(text):
    """True when a picture description says the shot is empty, blurry, black or accidental (not worth a place in the recap)."""
    return bool(_BORING.search(str(text or "")))


LOOK_ALIKE = 26.0             # thumbnails closer than this look like the same shot (real look-alikes: 7-22, different shots: 30 and up)


def thumb_distance(a, b):
    """How different two JPEG frames look: mean difference of 12x12 thumbnails with the brightness removed. Same view ~ 0-22, others 30+.
    1000.0 when a frame cannot be read (never 'alike')."""
    import io
    try:
        import numpy as np
        from PIL import Image

        def thumb(j):
            t = np.asarray(Image.open(io.BytesIO(j)).convert("RGB").resize((12, 12)), dtype=float)
            return t - t.mean()
        return float(np.abs(thumb(a) - thumb(b)).mean())
    except Exception:
        return 1000.0


def drop_repeats(moments, spares, describe_one, before=(), window=2, alike=None):
    """Moments of one day where none looks like one of the `window` shots before it (by description, by `alike(a, b)` on the pictures,
    also across days through `before`, the moments of the day before) and none is an empty, blurry, dark or accidental shot. Such a
    moment is swapped for the nearest spare that is neither (described on the spot by describe_one(moment)). A repeat with no spare
    stays; an empty or accidental shot with no spare is dropped when the day has other moments."""
    out, spares = [], list(spares)
    earlier = list(before)
    alike = alike or (lambda a, b: False)

    def boring(c):
        return looks_boring(c.get("visual"))

    def bad(c):
        v = c.get("visual")
        recent = (earlier + out)[-window:]
        return boring(c) or any(alike(c, r) or (bool(v) and same_description(v, r.get("visual"))) for r in recent)
    for m in moments:
        cur = m
        while bad(cur):
            pool = [s for s in spares if not any(same_scene(s, k) for k in out)]
            if not pool:
                break
            nxt = min(pool, key=lambda s: abs((moment_time(s) or 0) - (moment_time(cur) or 0)))
            spares.remove(nxt)
            describe_one(nxt)
            if not bad(nxt):
                cur = nxt
        if boring(cur) and len(moments) > 1:
            continue
        out.append(cur)
    return out


def best_closing(moments, grab=None, score=None):
    """`moments` with the most striking of them last, so the recap ends on a strong shot (a wide view, not a wing tip or a dark street).
    Fewer than 3 moments, or when no frame can be read: unchanged. Only that one shot moves; the rest keep their filming order."""
    if len(moments) < 3:
        return list(moments)
    if grab is None:
        from engine.visual_context import grab_frames
        grab = lambda f, s, e: grab_frames(f, s, e, n=1)  # noqa: E731
    score = score or scenic_score
    scores = []
    for m in moments:
        try:
            frames = grab(m["file"], m["start"], m["end"])
        except Exception:
            frames = None
        scores.append(score(frames[0]) if frames else None)
    if None in scores:
        return list(moments)
    best = max(range(len(moments)), key=lambda i: scores[i])
    return [m for i, m in enumerate(moments) if i != best] + [moments[best]]


PLAIN_AREA = ("district", "region", "oblast", "province", "county")
CACHE_PREFIX = "v3:"          # v3: names from the no-guessing prompt with the conflict check (older prefixes held wrong names)
CONFLICT_KM = 2.5             # one name on two places this far apart is a mistake (two different lakes cannot both be "Pinemere Lakes")


def latin_or_empty(name):
    """The name when it is written in Latin letters, else '' (a map name in Kazakh/Cyrillic/other script is not shown on screen)."""
    name = str(name or "").strip()
    return "" if any(c.isalpha() and ord(c) > 0x24F for c in name) else name


def is_plain_area(name):
    """True for no name or an administrative area ("Westford District"): fine for the itinerary, never shown on screen."""
    return not str(name or "").strip() or str(name).strip().lower().endswith(PLAIN_AREA)


def parse_place_overrides(text):
    """[(lat, lon, name)] from '42.985,78.465=Larkwater Lake; 42.991,78.326=Pinemere Lakes' (names you know to be right)."""
    out = []
    for item in re.split(r"[;\n]+", str(text or "")):
        m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*=\s*(.+?)\s*", item)
        if m and m.group(3):
            out.append((float(m.group(1)), float(m.group(2)), m.group(3)[:60]))
    return out


def apply_place_overrides(places, overrides, radius_km=1.5):
    """Give each place the name you typed for the nearest override within radius_km. Returns the indices that were set."""
    from engine.geo import distance_km
    done = []
    for i, p in enumerate(places):
        if not p.get("center"):
            continue
        best = min(((distance_km(p["center"], (la, lo)), n) for la, lo, n in overrides), default=None)
        if best and best[0] <= radius_km:
            p["name"], p["_done"], p["manual"] = best[1], True, True
            done.append(i)
    return done


_FLIGHT = re.compile(r"\b(airplane|aeroplane|plane window|from a plane|aerial view from|above the clouds|wing of)\b", re.I)


def name_conflicts(places, min_km=CONFLICT_KM):
    """[[indices]] of places that got the same name although they are more than min_km apart (a naming mistake)."""
    from engine.geo import distance_km
    groups = {}
    for i, p in enumerate(places):
        if p.get("center") and p.get("name") and not is_plain_area(p["name"]):
            groups.setdefault(p["name"].strip().lower(), []).append(i)
    out = []
    for idx in groups.values():
        if len(idx) > 1 and any(distance_km(places[a]["center"], places[b]["center"]) > min_km for a in idx for b in idx if a < b):
            out.append(idx)
    return out


def _place_line(i, p, f):
    seen = "; ".join(v for v in p.get("visuals", [])[:3] if v) or "no description"
    near = "; ".join(f.get("near") or []) or "none found"
    return (f"[{i}] GPS {p['center'][0]:.4f}, {p['center'][1]:.4f}; address: {f.get('hint') or 'nothing useful'}; "
            f"named places on the map within ~3 km (may be in the local language): {near}; pictures show: {seen}")


def _apply_rows(rows, places, saved, key_of, only=None):
    if isinstance(rows, dict):
        rows = rows.get("places") or []
    for r in rows if isinstance(rows, list) else []:
        try:
            i = int(r.get("id", 0)) - 1
        except (TypeError, ValueError):
            continue
        name = re.sub(r"\s+", " ", str(r.get("name") or "")).strip()
        if 0 <= i < len(places) and (only is None or i in only) and not places[i].get("manual") and name and len(name) <= 60:
            places[i]["name"] = name                      # a blank answer means "not sure": the map's own name stays
            if places[i].get("center"):
                saved[key_of(places[i])] = name


def name_places(places, trip_name="", note="", ask=None, geocode=True, cache_path=None, overrides=()):
    """Give every place of `places` ({"center", "files", "visuals"}) a "name" a tourist would use. Order of trust:
    names you typed (`overrides`) > "in flight" for shots from a plane > the AI choosing from the map's named places or a famous
    attraction it is sure of > the map's own feature or area. The AI is told to answer '' when unsure; one name on two places more than
    2.5 km apart is a mistake and gets one corrective request, then only the first keeps the name. Missing names stay ''."""
    from engine.geo import nearby_attractions, place_name
    facts = []
    for p in places:
        f = place_name(p["center"], cache_path=cache_path) if (geocode and p.get("center")) else None
        f = dict(f or {})
        f["near"] = nearby_attractions(p["center"], cache_path=cache_path) if (geocode and p.get("center")) else []
        facts.append(f)
        p["name"] = latin_or_empty(f.get("name")) or latin_or_empty(f.get("area"))
    if not any(p.get("center") for p in places):
        return places
    names_path = os.path.join(os.path.dirname(cache_path), "place_names.json") if cache_path else None
    saved = {}
    if names_path and os.path.isfile(names_path):
        try:
            with open(names_path, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
        except (OSError, ValueError):
            saved = {}
    key_of = lambda p: f"{CACHE_PREFIX}{p['center'][0]:.3f},{p['center'][1]:.3f}" if p.get("center") else ""  # noqa: E731
    for p in places:
        if p.get("center") and key_of(p) in saved:
            p["name"], p["_done"] = saved[key_of(p)], True              # the same answer as the last run
    # the same spot filmed on different days is ONE place: it is named once (from all its pictures) and every entry gets that name
    from engine.geo import distance_km
    group_of = list(range(len(places)))
    for i, p in enumerate(places):
        for j in range(i):
            if p.get("center") and places[j].get("center") and group_of[j] == j and distance_km(p["center"], places[j]["center"]) < 1.0:
                group_of[i] = j
                places[j]["visuals"] = list(places[j].get("visuals", [])) + [v for v in p.get("visuals", []) if v]
                break
    for i in apply_place_overrides(places, list(overrides or [])):
        saved[key_of(places[i])] = places[i]["name"]                   # what you typed is remembered too
    for p in places:
        if not p.get("_done") and any(_FLIGHT.search(v or "") for v in p.get("visuals", [])):
            p["name"], p["_done"] = "In flight", True
    pending = [i for i, p in enumerate(places) if p.get("center") and not p.get("_done") and group_of[i] == i]
    if pending:
        if ask is None:
            try:
                from engine.script_gen import get_llm_response
                ask = lambda q: get_llm_response(q, "You name places for a travel video. Reply with raw JSON only.", max_tokens=4000)  # noqa: E731
            except Exception:
                ask = None
        if ask is not None:
            lines = [_place_line(i + 1, places[i], facts[i]) for i in pending]
            prompt = (f"Trip: {trip_name or 'a trip'}. Traveller's note: {note or '(none)'}\n"
                      "Name each place where videos were filmed, as a TOURIST would call it: the attraction (lake, canyon, waterfall, viewpoint, "
                      "mountain, trail, park, famous square or landmark), not an administrative area. Choose from the named places on the map, or "
                      "a well-known attraction you are SURE is within about 2 km of that GPS position and matches the pictures; translate local "
                      "names to English. NEVER answer with a district, region or province name. Two places that are more than 2 km apart cannot "
                      "have the same name. If you are not sure, answer an empty string \"\": do not guess a famous name. At most 4 words, in English.\n"
                      + "\n".join(lines) + '\nReply with JSON only: [{"id": 1, "name": "Larkwater Lake"}, {"id": 2, "name": ""}, ...]')
            try:
                from engine.script_gen import robust_json_parse
                _apply_rows(robust_json_parse(ask(prompt)), places, saved, key_of, only=set(pending))
                clash = name_conflicts(places)
                if clash:
                    ids = sorted({i for grp in clash for i in grp})
                    print(f"[Log] Place names: the same name was given to places far apart ({len(ids)} places); asking again.")
                    prompt2 = ("These places were given the SAME name although they are different places (several km apart). Give each its own "
                               "correct name from the map's named places or a famous attraction you are sure of, or an empty string if you are not sure.\n"
                               + "\n".join(_place_line(i + 1, places[i], facts[i]) + f"; wrongly named: {places[i]['name']}" for i in ids)
                               + '\nReply with JSON only: [{"id": 1, "name": "..."}, ...]')
                    for i in ids:
                        places[i]["name"] = ""
                    _apply_rows(robust_json_parse(ask(prompt2)), places, saved, key_of, only=set(ids))
                    for grp in name_conflicts(places):                      # still the same name: only the first keeps it
                        for i in grp[1:]:
                            places[i]["name"] = ""
                            saved.pop(key_of(places[i]), None)
            except Exception as e:
                print(f"[Warning] Could not ask the AI for place names ({str(e)[:80]}); using the map's names.")
    for i, p in enumerate(places):
        rep = places[group_of[i]]
        if group_of[i] != i:
            p["name"] = rep.get("name", "")                           # the same spot on another day: the same name
        if not p.get("name") and p.get("center"):
            p["name"] = latin_or_empty(facts[i].get("name")) or latin_or_empty(facts[i].get("area"))      # the AI was unsure or lost a conflict: the map's own name
        if p.get("center") and p.get("name") and not is_plain_area(p["name"]):
            saved[key_of(p)] = p["name"]
    if names_path and saved:
        try:
            with open(names_path, "w", encoding="utf-8") as fh:
                json.dump(saved, fh, indent=1, ensure_ascii=False)
        except OSError:
            pass
    for p in places:
        p.pop("_done", None)
    return places


def write_places_review(path, places, trip_name=""):
    """places_review.md: every place with its GPS, a map link and the name used, so wrong names can be corrected with --place_names."""
    lines = [f"# Places{(' of ' + trip_name) if trip_name else ''}", "",
             "Check the names. To correct one, run again with `--place_names \"LAT,LON=Right name; LAT,LON=Another\"` (or edit place_names.json).", ""]
    for i, p in enumerate(places, 1):
        if not p.get("center"):
            continue
        la, lo = p["center"]
        shown = p.get("name") or "(no name)"
        flag = "" if not is_plain_area(p.get("name")) else "  <- not shown on screen"
        seen = next((v for v in p.get("visuals", []) if v), "")
        lines.append(f"{i}. **{shown}**{flag}  \n   {la:.4f},{lo:.4f}  [map](https://www.google.com/maps?q={la:.4f},{lo:.4f})  ·  {len(p.get('files', []))} video(s)"
                     + (f"  ·  e.g. {seen[:90]}" if seen else ""))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def moment_labels(days, cine):
    """Per day, per moment: the text to show on the shot. Cinematic: the place name, only when the place changes (clean, like a travel
    film). Other looks: the place name on every shot that has one. Administrative areas are never shown."""
    out, prev = [], None
    for d in days:
        row = []
        for m in d["moments"]:
            place = m.get("place") if not is_plain_area(m.get("place")) else ""
            row.append((place if (place and (not cine or place != prev)) else ""))
            if place:
                prev = place
        out.append(row)
    return out


def landmarks_first(names):
    """Place names with real landmarks (lakes, canyons, parks) before plain districts and regions, for the title line and the closing card."""
    plain = ("district", "region", "oblast", "province", "county")
    return sorted(names, key=lambda n: str(n).lower().endswith(plain))


def parse_rotations(text):
    """[(file-name part, degrees)] from '183047=270, 101930_CLN=90' (degrees clockwise: 0, 90, 180 or 270; 0 cancels a wrong automatic turn)."""
    out = []
    for item in re.split(r"[,;\n]+", str(text or "")):
        m = re.fullmatch(r"\s*(.+?)\s*=\s*(-?\d+)\s*", item)
        if m and int(m.group(2)) % 90 == 0:
            out.append((m.group(1), int(m.group(2)) % 360))
    return out


def apply_rotations(items, rotations):
    """Force the turn of every moment/glimpse whose file name contains a given part (the owner knows which clip is sideways); the size
    is swapped as needed. Returns how many items were changed."""
    changed = 0
    for it in items:
        name = os.path.basename(it["file"])
        for part, deg in rotations:
            if part in name:
                size = it.get("size")
                if size and (it.get("rotate", 0) % 180 == 90):
                    size = (size[1], size[0])                         # back to the picture as the file shows it
                if size and deg % 180 == 90:
                    size = (size[1], size[0])
                it["size"] = size
                it["rotate"] = deg
                changed += 1
    return changed


def rotate_filter(deg):
    """ffmpeg filter that turns the (already flag-corrected) picture `deg` degrees clockwise, '' for 0."""
    return {90: "transpose=1", 270: "transpose=2", 180: "transpose=1,transpose=1"}.get(int(deg or 0) % 360, "")


def fix_rotation(items, ffmpeg=None, check=None, grab=None, known=None, local=None):
    """Sets item["rotate"] (clockwise degrees) on moments/glimpses whose picture is sideways although the file says otherwise, and swaps
    their size for 90/270. Every MOMENT is judged on its own (a phone turned sideways in the middle of a video is only wrong for the later
    stretch): two frames inside the moment are looked at by Gemini, or by the local sky check when Gemini cannot answer, and the moment
    is only turned when both frames say the same. `known` {(file, second): degrees} remembers answers across calls. Returns how many
    moments are turned."""
    known = {} if known is None else known
    if check is None:
        from engine.visual_context import check_rotation as check
    if local is None:
        from engine.visual_context import local_rotation as local
    if grab is None:
        from engine.visual_context import grab_frames
        grab = lambda f, s, e: grab_frames(f, s, e, n=1, ffmpeg=ffmpeg)  # noqa: E731

    def key_of(it):
        return (it["file"], int(round(float(it["start"]))))
    first = {}
    for it in items:
        if key_of(it) not in known:
            first.setdefault(key_of(it), it)
    frames, owners = [], []
    for k, it in first.items():
        s0, e0 = float(it["start"]), float(it["end"])
        mid = (s0 + e0) / 2.0
        for lo, hi in ((s0, mid), (mid, e0)):                          # the middles of the two halves: 25% and 75% of the moment
            got = grab(it["file"], lo, hi)
            if got:
                frames.append(got[0])
                owners.append(k)
    if frames:
        turns = check(frames)
        if turns is None or len(turns) != len(owners):                  # Gemini is not available (no key, busy): the local sky check
            turns = local(frames)
        votes = {}
        for k, d in zip(owners, turns):
            votes.setdefault(k, []).append(d)
        for k, v in votes.items():
            known[k] = v[0] if len(v) >= 2 and len(set(v)) == 1 else 0       # two frames, and both must agree
    for it in items:
        d = known.get(key_of(it), 0)
        if d and not it.get("rotate"):
            it["rotate"] = d
            if d % 180 == 90 and it.get("size"):
                it["size"] = (it["size"][1], it["size"][0])
    return len({k for k, d in known.items() if d})


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


def _file_name(path):
    """File name of a path written on any OS (an itinerary made on Windows can be read elsewhere)."""
    return re.split(r"[\\/]", str(path))[-1]


def load_avoid(spec):
    """{(file name, start, end)} of the moments that earlier recaps used, from `spec`: itinerary.json files or recap folders (the folder
    itself and its portrait/ and landscape/ sub-folders), separated by commas. Missing or unreadable ones are skipped."""
    found = set()
    for part in re.split(r"[,;]+", str(spec or "")):
        part = part.strip().strip('"')
        if not part:
            continue
        paths = [part] if os.path.isfile(part) else [os.path.join(part, n) for n in ("itinerary.json", os.path.join("portrait", "itinerary.json"),
                                                                                       os.path.join("landscape", "itinerary.json"))]
        for pth in paths:
            try:
                with open(pth, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            for day in data.get("days", []) if isinstance(data, dict) else []:
                for m in day.get("moments", []):
                    try:
                        found.add((_file_name(m["file"]), float(m["start"]), float(m["end"])))
                    except (KeyError, TypeError, ValueError):
                        continue
    return found


def was_used(path, start, end, avoid, min_overlap=0.4):
    """True when [start, end] of this video overlaps a moment from `avoid` by at least min_overlap of its length."""
    name, length = _file_name(path), max(0.1, float(end) - float(start))
    return any(n == name and max(0.0, min(end, b) - max(start, a)) / length >= min_overlap for n, a, b in avoid)


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


_NOT_GEO = {"geo": False, "sample": 3.0, "unit": "Part", "stop_unit": "Part", "by": "Part by part", "note": "Note from the person who filmed",
            "invent": "Never invent names, relationships, places, times, speeches or feelings.", "writer": "warm"}
KINDS = {
    "trip": {"label": "Trip", "recap": "travel recap", "writer": "travel", "note": "Traveller's note", "geo": True, "unit": "Day", "stop_unit": "Stop",
             "by": "Day by day", "tagline": "A travel film", "hook": "Woke up at 4 AM just for this view", "hook_none": "You have to see this place",
             "facts": "the traveller's note, the stop names, the place names (read from the videos' GPS, reliable) or the descriptions",
             "invent": "Never invent places, times, weather, food or feelings."},
    "wedding": {**_NOT_GEO, "label": "Wedding", "recap": "wedding film", "tagline": "A wedding film", "hook": "The day we had been waiting for",
                "hook_none": "The day we had been waiting for", "facts": "the note, the names of the parts (the events of the day) or the descriptions"},
    "event": {**_NOT_GEO, "label": "Event", "recap": "event recap", "tagline": "An event recap", "hook": "You had to be there",
              "hook_none": "You had to be there", "facts": "the note, the names of the parts or the descriptions"},
    "family": {**_NOT_GEO, "label": "Memories", "recap": "family memories film", "tagline": "Our memories", "hook": "These are the moments we keep",
               "hook_none": "These are the moments we keep", "facts": "the note, the names of the parts or the descriptions"},
}


def sample_factor(sample, kind_default):
    """Videos to look at per shot: `sample` is "auto" (the recap kind's own default: weddings and events sample, trips look at everything),
    "all" (every video), or a number such as 3 (about 3 videos per shot). Returns None for everything."""
    s = str(sample if sample is not None else "auto").strip().lower()
    if s in ("", "auto"):
        return kind_default
    if s in ("all", "none", "0", "off"):
        return None
    try:
        return max(1.0, float(s))
    except ValueError:
        raise ValueError(f"--recap_sample must be auto, all or a number (videos per shot), not {sample!r}.")


def sample_videos(infos, n_clips, factor, extra=6):
    """`infos` (in filming order) thinned to videos spread evenly over the whole list when there are far more videos than shots to pick
    (about `factor` videos per shot), so a part made of 600 videos is not scanned end to end. Everything is kept when `factor` is falsy,
    when there are not many more videos than needed, or when n_clips is unknown."""
    keep = int(factor * max(1, n_clips)) if factor else 0
    if not keep or len(infos) <= keep + extra:
        return list(infos)
    keep = max(2, keep)
    picks = sorted({round(i * (len(infos) - 1) / (keep - 1)) for i in range(keep)})
    return [infos[i] for i in picks]


def get_kind(kind):
    """The settings for a recap kind (trip, wedding, event, family); an unknown or empty name means a trip."""
    return KINDS.get(str(kind or "trip").strip().lower(), KINDS["trip"])


def build_prompt(trip_name, note, days, stops=None, kind="trip"):
    K = get_kind(kind)
    unit = K["stop_unit"] if stops else K["unit"]
    lines = []
    for i, d in enumerate(days, 1):
        moms = "; ".join(f"[{j}] {('(at ' + m['place'] + ') ') if m.get('place') else ''}{m.get('visual') or 'no description'}"
                         for j, m in enumerate(d["moments"], 1))
        name = f" = {stops[i - 1]}" if stops and i <= len(stops) else ""
        seen = list(dict.fromkeys(m["place"] for m in d["moments"] if m.get("place")))
        where = f" (places visited, from GPS: {', '.join(seen)})" if seen else ""
        lines.append(f"{unit} {i}{name}{where}: {moms}")
    trip = K is KINDS["trip"]
    return (f"Write a {K['recap']} itinerary for a short video.\n{K['label']}: {trip_name or ('my trip' if trip else 'our ' + K['label'].lower())}\n"
            f"STRICT: use only facts that are in {K['facts']}. {K['invent']} "
            "When a moment has no description, leave its caption empty (\"\").\n"
            f"{K['note']}: {note or '(none)'}\n\nWhat each {'day' if trip else 'part'}'s moments show (the pictures were described automatically, "
            f"some descriptions may be missing or wrong; never invent {'places' if trip else 'names or people'} the descriptions or note do not support):\n"
            + "\n".join(lines) + "\n\n"
            'Reply with JSON only: {"title": "<recap title, max 5 words>", "hook": "<one excited first-person line of at most 9 words '
            f'that opens the video, e.g. {K["hook"]}. Use only facts from the {"traveller" if trip else "person who filmed"}\'s note; with no usable note '
            f'write a neutral line like {K["hook_none"]}>", "days": [{{"title": "<{"day" if trip else "part"} title, max 5 words>", '
            '"summary": "<one sentence>", "captions": ["<caption for moment 1, max 6 words>", ...]}]}. '
            f"Exactly {len(days)} {unit.lower()}s, and for each {unit.lower()} one caption per moment."
            + (" The stop names are given: use each one exactly as its title." if stops else ""))


def fallback_itinerary(trip_name, days, stops=None, kind="trip"):
    K = get_kind(kind)
    return {"title": trip_name or f"{K['label']} recap", "hook": "",
            "days": [{"title": stops[i - 1] if stops and i <= len(stops) else f"{K['unit']} {i}", "summary": "",
                      "captions": ["" for _ in d["moments"]]} for i, d in enumerate(days, 1)]}


def write_itinerary(trip_name, note, days, ask=None, stops=None, kind="trip"):
    """The itinerary dict {title, days:[{title, summary, captions}]}; never fails (falls back to plain 'Day N' / 'Part N')."""
    K = get_kind(kind)
    fb = fallback_itinerary(trip_name, days, stops, kind)
    if ask is None:
        try:
            from engine.script_gen import get_llm_response
            ask = lambda p: get_llm_response(p, f"You write short, honest, {K['writer']} captions. Reply with raw JSON only.", max_tokens=4000)  # noqa: E731
        except Exception:
            return fb
    try:
        from engine.script_gen import robust_json_parse
        data = robust_json_parse(ask(build_prompt(trip_name, note, days, stops, kind)))
        rows = data.get("days") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            return fb
        out = {"title": (trip_name or str(data.get("title") or fb["title"]))[:60], "hook": str(data.get("hook") or "").strip()[:70], "days": []}
        for i, d in enumerate(days):
            row = rows[i] if i < len(rows) and isinstance(rows[i], dict) else {}
            caps = [str(c)[:60] for c in (row.get("captions") or []) if isinstance(c, (str, int, float))]
            caps += [""] * (len(d["moments"]) - len(caps))
            title = stops[i] if stops and i < len(stops) else str(row.get("title") or f"{K['unit']} {i + 1}")
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
        seen = list(dict.fromkeys(m["place"] for m in d["moments"] if m.get("place")))
        if seen:
            lines.append("Places: " + ", ".join(seen))
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


def resolve_look(grade_name, edit, auto_grade, text=""):
    """(FFmpeg colour chain, what it is) for the recap.

    grade_name: "default" / "auto" (a look only if one suits: the Auto-edit style's own look, else `auto_grade`, which is the footage-based
    cinematic grade or '' for the other styles), "none" (no colour look at all), "ai" (the AI chooses from `text`), or the name of one of the
    named looks in engine.video_gen.FILTER_PRESETS."""
    from engine.video_gen import FILTER_PRESETS
    name = str(grade_name or "default").strip().lower()
    if name == "none":
        return "", "none"
    if name in FILTER_PRESETS:
        return FILTER_PRESETS[name], name
    if name == "ai":
        try:
            from engine.script_gen import auto_detect_video_filter
            picked = auto_detect_video_filter(user_context=text)
            if picked in FILTER_PRESETS:
                return FILTER_PRESETS[picked], f"{picked} (AI)"
        except Exception as e:
            print(f"[Warning] The AI colour choice failed ({str(e)[:60]}); using the automatic look.")
    if edit:
        from engine.auto_edit import PRESETS
        wanted = (PRESETS.get(edit) or {}).get("video_filter")
        if wanted in FILTER_PRESETS:
            return FILTER_PRESETS[wanted], f"{wanted} (from the {edit} edit style)"
    return auto_grade or "", "automatic" if auto_grade else "none needed"


def cut_sound_events(parts, kind):
    """Sound-effect events {t, kind, why} at the start of every shot except the first: [(path, seconds)] of the recap's parts, in order."""
    events, t, prev = [], 0.0, ""
    for path, seconds in parts:
        name = re.sub(r"^trim_\d+_", "", os.path.basename(path))             # a shot trimmed for a subject cut-out is still a shot
        after_bridge = prev.startswith("bridge_")                              # the bridge already carries the cut: no second sound after it
        if t > 0 and not after_bridge and name.startswith(("clip_", "glimpse_", "trip_title", "bridge_")):
            events.append({"t": round(t, 3), "kind": kind, "why": "cut"})
        t += float(seconds)
        prev = name
    return events


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

    max_w = (W - cx - int(W * 0.06)) if left else int(W * 0.86)         # text never leaves the frame
    meter = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    def fit(text, size, min_size, max_lines=1):
        """(lines, font, line height): wide-spaced on one line if it fits, else plain capitals wrapped and shrunk until every line fits."""
        for sz in range(size, min_size - 1, -4):
            f = font(sz)
            if meter.textlength(spaced(text), font=f) <= max_w:
                return [spaced(text)], f, int(sz * 1.15 * u)
        plain = str(text).upper()
        for sz in range(size, 23, -4):
            f = font(sz)
            lines = _wrap(meter, plain, f, max_w)
            if len(lines) <= max(max_lines, 2) and all(meter.textlength(ln, font=f) <= max_w for ln in lines):
                return lines, f, int(sz * 1.15 * u)
        f = font(24)
        return _wrap(meter, plain, f, max_w), f, int(28 * u)

    if stacked:
        size = 120
        while size > 48 and max(meter.textlength(w.upper(), font=font(size)) for w in words) > max_w:
            size -= 6
        t_lines, t_font, t_lh = [w.upper() for w in words], font(size), int(size * 1.05 * u)
    else:
        t_lines, t_font, t_lh = fit(title, 86, 52, max_lines=3)
    block = t_lh * len(t_lines)

    def title_fn(d):
        y = cy - block // 2 + t_lh // 2
        for ln in t_lines:
            d.text((cx, y), ln, font=t_font, fill=ink, anchor=anchor, stroke_width=2, stroke_fill=shadow)
            y += t_lh

    below = cy + block // 2 + int(30 * u)
    layers = []
    if small:
        s_lines, s_font, s_lh = fit(small, 34, 24)

        def credit(d):
            y = cy - block // 2 - int(40 * u) - s_lh * (len(s_lines) - 1)
            for ln in s_lines:
                d.text((cx, y), ln, font=s_font, fill=ink, anchor=anchor)
                y += s_lh
        layers.append((layer(credit, "a"), 0.3))
    layers.append((layer(title_fn, "b"), 0.9))
    if line:
        l_lines, l_font, l_lh = fit(line, 40, 28)

        def sub(d):
            x0, x1 = (cx, cx + int(120 * u)) if left else (cx - int(60 * u), cx + int(60 * u))
            d.line([(x0, below), (x1, below)], fill=accent, width=max(2, int(3 * u)))
            y = below + int(50 * u)
            for ln in l_lines:
                d.text((cx, y), ln, font=l_font, fill=accent, anchor=anchor)
                y += l_lh
        layers.append((layer(sub, "c"), 1.7))
    return layers


def beat_grid(music):
    """(beat seconds, time of the first beat) of the music, or None when no steady tempo is found."""
    try:
        from engine.beat_sync import detect_beats
        beats = detect_beats(music, max_duration=90, min_interval=0.3, max_interval=1.5)
        gaps = sorted(b - a for a, b in zip(beats, beats[1:]) if 0.25 < b - a < 1.6)
        if len(gaps) < 6:
            return None
        return gaps[len(gaps) // 2], float(beats[0])
    except Exception:
        return None


def on_beat(seconds, beat, bars=1):
    """`seconds` rounded to a whole number of `bars` beats (at least one)."""
    unit = beat * bars
    return max(1, round(seconds / unit)) * unit


def filter_orientation(all_infos, mode, minimum=3):
    """Keeps only landscape or only portrait videos (as shown, rotation included). Returns (infos, note); with fewer than `minimum`
    left it keeps everything (they are then shown blurred-fit) and says so."""
    if mode not in ("landscape", "portrait"):
        return all_infos, ""
    keep = (lambda w, h: w >= h) if mode == "landscape" else (lambda w, h: h > w)
    kept = [[i for i in infos if keep(i[2], i[3])] for infos in all_infos]
    kept = [k for k in kept if k]
    n = sum(len(k) for k in kept)
    if n < minimum:
        return all_infos, f"only {n} {mode} video(s), so all videos are used"
    return kept, f"{n} {mode} of {sum(len(i) for i in all_infos)} videos"


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
    if lower:       # small, spaced, bottom-left lower third with a thin rule; wraps and shrinks to stay inside the frame
        u = min(W, H) / 1080.0
        left_x, max_w = int(70 * u), W - int(70 * u) - int(W * 0.06)
        label, f = spaced(text), None
        for sz in (46, 42, 38, 34):
            f = _font(int(sz * u), text)
            if d.textlength(label, font=f) <= max_w:
                lines = [label]
                break
        else:
            label = str(text).upper()
            f = _font(int(40 * u), text)
            lines = _wrap(d, label, f, max_w)[:3]
        lh = int(54 * u)
        y0 = int(H * 0.86) - lh * (len(lines) - 1)
        d.line([(left_x, y0 - int(40 * u)), (left_x + int(120 * u), y0 - int(40 * u))], fill=(200, 170, 120, 255), width=max(2, int(3 * u)))
        for i, ln in enumerate(lines):
            d.text((left_x, y0 + i * lh), ln, font=f, fill=(245, 240, 230, 255), anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0, 160))
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
    """(seconds, width, height) as the video is SHOWN: phones store a vertical clip as 1920x1080 with a 90/270 degree rotation flag."""
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_tags=rotate:stream_side_data=rotation:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    data = json.loads(r.stdout or "{}")
    st = (data.get("streams") or [{}])[0]
    w, h = int(st.get("width") or 0), int(st.get("height") or 0)
    rot = 0
    try:
        for sd in st.get("side_data_list") or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        if not rot:
            rot = int(float((st.get("tags") or {}).get("rotate") or 0))
    except (TypeError, ValueError):
        rot = 0
    if abs(rot) % 180 == 90:
        w, h = h, w
    return float(data.get("format", {}).get("duration") or 0), w, h


def has_audio(path, ffprobe="ffprobe"):
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


QUALITY = {"crf": "21", "preset": "veryfast"}      # the cinematic style renders at crf 17 / preset fast


def _enc():
    return ["-c:v", "libx264", "-preset", QUALITY["preset"], "-crf", QUALITY["crf"], "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k"]


def render_card(ffmpeg, png, out, seconds=CARD_SECONDS):
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-t", f"{seconds}", "-i", png, "-f", "lavfi", "-t", f"{seconds}",
           "-i", "anullsrc=r=44100:cl=stereo", "-vf", "fade=t=in:st=0:d=0.3,fade=t=out:st=%.2f:d=0.3" % (seconds - 0.3), *_enc(), "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Could not make a title card: " + (r.stderr or "")[-300:])


def zoom_filter(seconds, amount, out=False, fps=30):
    """A slow push-in (or push-out) over the whole shot: `amount` = how much bigger the picture gets by the end (0.06 = 6 %).
    The frame rate is fixed first so a 60 fps source does not make the shot twice as long."""
    frames = max(2, int(round(seconds * fps)))
    z = f"1+{amount:.4f}-{amount:.4f}*on/{frames}" if out else f"1+{amount:.4f}*on/{frames}"
    return f"fps={fps},zoompan=z='{z}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}"


def render_clip(ffmpeg, src, start, seconds, out, caption_file=None, layout="auto", size=None, audio=True, cap_from=0.3, cap_gap=0.3, grade="", fade_s=0.2, layers=None, rotate=0, fix="", zoom=0.0, zoom_out=False, head=None, tail=None, trans_s=0.2):
    w, h = size or (0, 0)
    portrait = h > w > 0
    if layout == "crop" or (layout == "auto" and portrait == (H > W)):
        base = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1"
    else:
        base = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    turn = rotate_filter(rotate)
    if turn:
        base = f"{turn},{base}"
    if zoom and zoom > 0:
        base = f"{base},{zoom_filter(seconds, zoom, zoom_out)}"
    grade = ",".join(x for x in (fix, grade) if x)           # first the correction (exposure, cast ...), then the look
    if head or tail:        # a cut transition: its effect replaces the black dip on the sides that have one
        from engine.transitions import clip_effect
        fx, f_in, f_out = clip_effect(head, tail, seconds, trans_s, W, H)
        if fx:
            base = f"{base},{fx}"
        f_in = f_in or ("" if head else f"fade=t=in:st=0:d={fade_s}:color=black")
        f_out = f_out or ("" if tail else f"fade=t=out:st={seconds - fade_s:.2f}:d={fade_s}:color=black")
        fade = (f",{grade}" if grade else "") + "".join(f",{x}" for x in (f_in, f_out) if x)
    else:
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
    if not audio:       # the silent track is an INPUT: it has to come before any output option such as -map
        cmd += ["-f", "lavfi", "-t", f"{seconds:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-filter_complex", vf, "-map", "[vout]"]
    if audio:
        cmd += ["-map", "0:a:0", "-af", f"afade=t=in:st=0:d={fade_s},afade=t=out:st={seconds - fade_s:.2f}:d={fade_s},aresample=44100"]
    else:
        cmd += ["-map", f"{n + 1}:a"]
    cmd += [*_enc(), "-t", f"{seconds:.2f}", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("Could not cut a clip: " + (r.stderr or "")[-400:])


def concat(ffmpeg, parts, out, session_dir, music=None, music_gain=0.25, music_start=0.0, music_only=False):
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
        total = video_info(joined)[0] or 0.0
        fades = f"afade=t=in:st=0:d=0.6,afade=t=out:st={max(0.0, total - 2.5):.2f}:d=2.5"
        if music_only:      # the clips' own sound is dropped: one unbroken song, faded in and out
            graph = f"[1:a]volume={music_gain},{fades}[a]"
        else:
            graph = f"[1:a]volume={music_gain},{fades}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]"
        r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-ss", f"{max(0.0, music_start):.3f}", "-i", music,
                            "-filter_complex", graph,
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
               ask=None, describe=None, ffmpeg=None, hook="", style="hype", grab=None, stops=None, aspect=None, orientation="any", geocode=True, enhance="off", enhance_strength="medium", manual_rotate="", place_names="", avoid="", kind="trip", keep_sound=False, grade_name="default", edit="", edit_strength="medium", clean_sound=False, sample="auto", transitions="auto", subject_look="auto", subject_color="auto", subject_max=2):
    """Build the recap. Returns {"video", "itinerary_md", "itinerary_json", "days"}. Raises ValueError for no videos.
    aspect: "9:16" (default), "16:9" or "2.35:1"; the cinematic style defaults to 2.35:1.
    kind: "trip" (default), "wedding", "event" or "family" - the wording, the section names and whether places are looked up from GPS.
    keep_sound: keep the clips' own sound under the music (vows, speeches, laughter) instead of a music-only soundtrack.
    grade_name: colour look ("default" = automatic, "none", "ai" or a named look); edit / edit_strength: the Auto-edit director style
    (podcast, hype, educational, vlog; subtle, medium, hyped) - its look, a slow zoom on every shot and sound effects at the cuts;
    clean_sound: remove noise from the clips' own sound (only matters with keep_sound or without music).
    sample: how many videos to look at when a part has far more videos than shots: "auto" (weddings/events sample about 3 videos per shot,
    trips look at everything), "all", or a number of videos per shot."""
    global W, H
    if not get_kind(kind)["geo"]:
        geocode = False                       # no map lookups for a wedding or a party (the GPS never leaves the PC)
    if style == "auto":
        style, auto_aspect, why = decide_look(paths)
        aspect = aspect or auto_aspect
        print(f"[Log] Auto look: {style} {aspect} ({why}).")
    old = (W, H)
    key = aspect or ("2.35:1" if style == "cinematic" else "9:16")
    if key not in ASPECTS:
        raise ValueError(f"Unknown aspect {key!r}. Choose one of: {', '.join(ASPECTS)}")
    W, H = ASPECTS[key]
    old_quality = dict(QUALITY)
    if style == "cinematic":
        QUALITY.update(crf="17", preset="fast")
    try:
        return _make_recap(paths, session_dir, trip_name, note, total_seconds, music, visual, layout, ask, describe, ffmpeg, hook, style, grab, stops, orientation, geocode, enhance, enhance_strength, manual_rotate, place_names, avoid, kind=kind, keep_sound=keep_sound,
                           grade_name=grade_name, edit=edit, edit_strength=edit_strength, clean_sound=clean_sound, sample=sample, transitions=transitions, subject_look=subject_look, subject_color=subject_color, subject_max=subject_max)
    finally:
        W, H = old
        QUALITY.update(old_quality)


def _make_recap(paths, session_dir, trip_name, note, total_seconds, music, visual, layout, ask, describe, ffmpeg, hook, style, grab, stops, orientation="any", geocode=True, enhance="off", enhance_strength="medium", manual_rotate="", place_names="", avoid="", kind="trip", keep_sound=False, grade_name="default", edit="", edit_strength="medium", clean_sound=False, sample="auto", transitions="auto", subject_look="auto", subject_color="auto", subject_max=2):
    K = get_kind(kind)
    factor = sample_factor(sample, K.get("sample"))
    from engine import auto_edit
    if edit and edit not in auto_edit.PRESETS:
        raise ValueError(f"Unknown auto-edit style {edit!r}. Choose one of: {', '.join(auto_edit.PRESETS)}")
    director = auto_edit.PRESETS.get(edit) if edit else None
    strength = auto_edit.STRENGTHS.get(edit_strength) or auto_edit.STRENGTHS["medium"]
    videos = collect_videos(list(paths))
    by_folder = not K["geo"]                              # a wedding or party: one folder per part
    days_paths = group_days(videos, by_folder=by_folder)
    if not days_paths:
        raise ValueError("No videos found. Give video files, or folders with one folder per day.")
    stops = parse_stops(stops)
    folder_parts = by_folder and len(folder_names(videos)) >= 2
    if folder_parts and not stops:
        stops = folder_names(videos)                      # the folder names are the part names
    if stops and folder_parts and len(stops) == len(days_paths):
        print(f"[Log] {len(stops)} part(s), one per folder: {', '.join(stops)}.")      # names given for the folders: keep the folders as they are
    elif stops:
        days_paths = split_into(days_paths, len(stops))
        stops = stops[:len(days_paths)]
        print(f"[Log] {len(stops)} stop(s): {', '.join(stops)}.")
    unit = K["stop_unit"] if stops else K["unit"]
    os.makedirs(session_dir, exist_ok=True)
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cine = style == "cinematic"
    hype = style != "plain"
    grade, fade_s = (CINEMATIC_GRADE, 0.5) if cine else ("", 0.2)
    closing_s = 3.2
    opening = ((GLIMPSES * GLIMPSE_SECONDS + CARD_SECONDS) if hype else 0.0) + closing_s      # glimpses + the trip title card + the closing card
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
    all_infos, note_o = filter_orientation(all_infos, orientation)
    if note_o:
        print(f"[Log] {orientation.capitalize()} version: {note_o}.")
    if cine and str(grade_name or "default").lower() in ("default", "auto", "ai"):
        grade = pick_grade(ffmpeg, [i[0] for infos in all_infos for i in infos])
        print(f"[Log] Colour grade: {'warm' if grade == CINEMATIC_GRADE else 'cool'} (from the footage).")
    elif cine:
        grade = ""                      # an explicit choice replaces the automatic cinematic look
    grade, look_name = resolve_look(grade_name, edit, grade, f"{trip_name} {note}")
    print(f"[Log] Colour look: {look_name}.")
    zoom_amount = 0.06 * strength["zoom_intensity"] if director else 0.0
    shot_no = [0]

    def zoom_kw():
        """The slow push-in for the next shot (in, out, in...), or nothing when no edit style is chosen."""
        shot_no[0] += 1
        return {"zoom": zoom_amount, "zoom_out": shot_no[0] % 2 == 0} if zoom_amount else {}
    from engine import transitions as _tr
    trans_name = _tr.resolve(transitions, edit)
    if trans_name != "none":
        print(f"[Log] Transitions between shots: {trans_name}.")
    from engine import subject_cut as _subject
    subject_style = _subject.resolve_style(subject_look, subject_color, edit) if trans_name == "subject" else None
    if subject_style:
        print(f"[Log] Subject cut-out look: {subject_style['look']}.")
    trans_s = _tr.seconds_for(edit_strength)
    trans_types = _tr.cut_types(trans_name, 400)
    clip_no, tail_seq, overlays, boxes, subject_cuts = [0], [], {}, {}, []      # overlays: shot -> the title/caption PNGs burned into it (taken out of the subject cut-out)

    def _person_near_end(file, start, secs, size=None):
        """A clear person in four frames over the shot's last second (the bridge, with its build-up, covers up to 0.8 s), laid out the way the shot is rendered (crop or letterbox)."""
        if not _subject.available():
            return False
        grabber = grab
        if grabber is None:
            from engine.visual_context import grab_frames
            grabber = lambda f, s, e: grab_frames(f, s, e, n=1, ffmpeg=ffmpeg)  # noqa: E731
        end = start + secs
        frames = []
        for back in (1.00, 0.70, 0.50, 0.30):                    # each call returns the frame 0.25 s after its start (the window is at least 0.5 s)
            got = grabber(file, end - back, end - back + 0.5) or []
            if not got:
                return False
            frames.append(got[0])
        w, h = size or (0, 0)
        crop = not w or layout == "crop" or (layout == "auto" and (h > w) == (H > W))
        return _subject.has_person_jpegs(frames, (W, H), crop)

    def note_shot(out, size, pngs):
        """What the subject cut-out needs to know about a rendered shot: its title/caption PNGs and, when letterboxed, where the sharp picture is."""
        overlays[out] = [p for p in pngs if p]
        w, h = size or (0, 0)
        if w and layout != "crop" and not (layout == "auto" and (h > w) == (H > W)):
            boxes[out] = _subject.letterbox_box((w, h), (W, H))

    def trans_kw(file=None, start=0.0, secs=0.0, size=None):
        """Head and tail transition of the next shot: the cut before it and the cut after it share one type. Nothing when none is chosen.
        For the subject cut-out the tail is "subject" only when a clear person is in the shot's last moments; otherwise a normal type."""
        i = clip_no[0]
        clip_no[0] += 1
        if trans_name == "none":
            return {}
        tail = trans_types[i]
        if tail == "subject":
            spaced = not subject_cuts or i - subject_cuts[-1] >= _subject.MIN_GAP
            if file and subject_max > 0 and len(subject_cuts) < subject_max + 1 and spaced and _person_near_end(file, start, secs, size):      # one person; one spare candidate in case a bridge fails (apply() keeps at most subject_max)
                subject_cuts.append(i)
            else:
                tail = _tr.fallback_type(i)
        tail_seq.append(tail)
        return {"head": tail_seq[i - 1] if i else None, "tail": tail, "trans_s": trans_s}
    fixes, fix_stats, ref_box = {}, {}, []

    def stats_for(path):
        if path not in fix_stats:
            from engine.enhance import measure, sample_frames
            fix_stats[path] = measure(sample_frames(path, ffmpeg=ffmpeg))
        return fix_stats[path]

    def brightness_reference():
        """The typical median brightness over the videos the recap uses, so the shots are corrected towards each other (None: too few)."""
        if not ref_box:
            import statistics
            meds = []
            for d in days:
                for f in dict.fromkeys(m["file"] for m in d["moments"]):
                    st = stats_for(f)
                    if st:
                        meds.append(st["p50"])
            ref_box.append(statistics.median(meds) if len(meds) >= 3 else None)
        return ref_box[0]

    def fix_for(path):
        """Correction chain for one source video (measured once), '' when enhance is off or the clip needs nothing."""
        if enhance in (None, "", "off"):
            return ""
        if path not in fixes:
            try:
                from engine.enhance import build_filter, plan
                fixes[path] = build_filter(plan(stats_for(path), enhance_strength, brightness_reference()))
            except Exception as e:
                print(f"[Warning] Could not measure {os.path.basename(path)} for enhancing ({str(e)[:60]}); left as it is.")
                fixes[path] = ""
        return fixes[path]
    if enhance not in (None, "", "off"):
        print(f"[Log] Auto enhance ({enhance_strength}): each video is measured and corrected where needed (exposure, colour cast, dullness, sharpness).")
    avoid = load_avoid(avoid) if isinstance(avoid, str) else set(avoid or ())
    if avoid:
        print(f"[Log] Picking new moments: {len(avoid)} moment(s) from earlier recaps are avoided.")
    counts, clip_len = plan_days([len(i) for i in all_infos], max(float(total_seconds) - opening, len(all_infos) * 6.0),
                                 card=0.0 if cine else CARD_SECONDS)          # the cinematic look puts the titles over the footage: no card time to reserve
    glimpse_s, title_s, first_min, music_start = GLIMPSE_SECONDS, 3.4, 3.2, 0.0
    mute_orig = bool(cine and music and not keep_sound)      # the song carries the edit: the clips' own sound would break it at every cut
    if cine and music:
        grid = beat_grid(music)
        if grid:
            beat, music_start = grid
            snapped = on_beat(clip_len, beat, 2)
            if 0.6 * clip_len <= snapped <= 1.5 * clip_len:
                clip_len = snapped
            glimpse_s, title_s, first_min = on_beat(GLIMPSE_SECONDS, beat), on_beat(3.4, beat), on_beat(3.2, beat)
            closing_s = on_beat(closing_s, beat)
            print(f"[Log] Cuts follow the music: beat {beat:.3f}s, every shot is a whole number of beats; the song starts on its first beat.")
    print(f"[Log] Trip recap: {len(all_infos)} day(s), {sum(len(i) for i in all_infos)} video(s); moments per day: {counts} of {clip_len:g}s.")

    from engine.geo import group_places, video_location
    locs = {}
    for infos in all_infos:
        for f, *_rest in infos:
            locs[f] = video_location(f)
    print(f"[Log] GPS found in {sum(1 for v in locs.values() if v)} of {len(locs)} video(s).")
    cache = {}
    days = []
    for di, infos in enumerate(all_infos, 1):
        n_clips = counts[di - 1]
        sampled = sample_videos(infos, n_clips, factor)
        if len(sampled) < len(infos):
            print(f"[Log] {K['unit']} {di}: {len(infos)} videos for {n_clips} shot(s): looking at {len(sampled)} of them, spread over the whole part.")
            infos = sampled
        total_dur = sum(i[1] for i in infos)
        cands, reused = [], []
        for f, dur, w, h in infos:
            share = max(1, int(round(n_clips * dur / total_dur))) if len(infos) > 1 else n_clips
            levels = loudness_per_second(f, ffmpeg=ffmpeg)
            for s_, e_ in pick_windows(dur, (share + (share + 1) // 2) * (2 if avoid else 1), clip_len, levels):      # a few spares for the repeat check
                m_ = {"file": f, "start": s_, "end": e_, "size": (w, h), "loc": locs.get(f)}
                (reused if avoid and was_used(f, s_, e_, avoid) else cands).append(m_)
        if avoid and len(cands) < n_clips + 2:
            cands += reused[:n_clips + 2 - len(cands)]                       # not enough new moments: a repeat beats a missing shot
        cands.sort(key=lambda m: (infos_order(infos, m["file"]), m["start"]))
        moments, spares = spread_moments(cands, n_clips)
        print(f"[Log] Day {di}: {len(moments)} moment(s) from {len(infos)} video(s).")
        days.append({"files": [i[0] for i in infos], "moments": moments, "spares": spares, "infos": infos})
    if not days:
        raise ValueError("None of the videos could be read.")

    from engine.visual_context import grab_frames as _grab_frames
    grab_one = grab or (lambda f, s_, e_: _grab_frames(f, s_, e_, n=1, ffmpeg=ffmpeg))
    frame_cache = {}

    def frame_of(m):
        k = (m["file"], round(m["start"], 1))
        if k not in frame_cache:
            try:
                got = grab_one(m["file"], m["start"], m["end"])
            except Exception:
                got = None
            frame_cache[k] = got[0] if got else None
        return frame_cache[k]

    def alike(a, b):
        fa, fb = frame_of(a), frame_of(b)
        return fa is not None and fb is not None and thumb_distance(fa, fb) < LOOK_ALIKE

    def describe_one(m):
        if not visual:
            return
        from engine.visual_context import describe_candidates
        one = describe_candidates(m["file"], [{"start": m["start"], "end": m["end"]}], about=f"{trip_name} {note}".strip(),
                                  cache_path=os.path.join(session_dir, "visual_context.json"), ask=describe)
        if one and one[0].get("visual"):
            m["visual"] = one[0]["visual"]
    previous = []
    for d in days:
        for m in d["moments"]:
            describe_one(m)
        before = list(d["moments"])
        d["moments"] = drop_repeats(d["moments"], d["spares"], describe_one, before=previous, alike=alike)
        previous = d["moments"][-2:]
        swapped = sum(1 for a, b in zip(before, d["moments"]) if a is not b)
        if swapped or len(d["moments"]) < len(before):
            print(f"[Log] Replaced or dropped {swapped + len(before) - len(d['moments'])} shot(s) that looked like a shot just before them or were dark or empty.")
    for d in days:
        d.pop("spares", None)

    # where each day went: places from the videos' GPS, named from the map and the pictures
    all_places = []
    for d in days:
        d["places"] = group_places(d["files"], [locs.get(f) for f in d["files"]])
        for p in d["places"]:
            p["visuals"] = [m.get("visual", "") for m in d["moments"] if m["file"] in p["files"]]
            all_places.append(p)
    typed = parse_place_overrides(place_names)
    if (geocode or typed) and any(p.get("center") for p in all_places):
        name_places(all_places, trip_name=trip_name, note=note, ask=ask if geocode else (lambda q: "[]"), geocode=geocode,
                    cache_path=os.path.join(session_dir, "places.json"), overrides=typed)
        names = [p["name"] for p in all_places if p.get("name") and not is_plain_area(p["name"])]
        print(f"[Log] Places from GPS: {', '.join(dict.fromkeys(names)) or 'none named'}.")
        write_places_review(os.path.join(session_dir, "places_review.md"), all_places, trip_name)
    for d in days:
        for m in d["moments"]:
            for p in d["places"]:
                if m["file"] in p["files"] and p.get("name"):
                    m["place"] = p["name"]
    trip_places = landmarks_first(dict.fromkeys(p["name"] for p in all_places if p.get("name") and not is_plain_area(p["name"]) and p["name"] != "In flight"))

    rot_known = {}
    turned = fix_rotation([m for d in days for m in d["moments"]], ffmpeg=ffmpeg, known=rot_known) if visual else 0      # sends frames to Gemini: only with --visual_context
    if turned:
        print(f"[Log] {turned} sideways video(s) turned upright.")
    rotations = parse_rotations(manual_rotate)
    if rotations and apply_rotations([m for d in days for m in d["moments"]], rotations):       # (the title shot is taken from these afterwards)
        print(f"[Log] Manual rotation applied: {manual_rotate}.")

    # the trip title is shown over a shot of its own: the same shot must not open Day 1 again right after it
    title_m = days[0]["moments"].pop(0) if cine and len(days[0]["moments"]) > 1 else None
    if len(days[-1]["moments"]) >= 3:
        last_before = list(days[-1]["moments"])
        days[-1]["moments"] = best_closing(last_before, grab=grab)
        if days[-1]["moments"] != last_before:
            print("[Log] The recap ends on the most striking shot of the last day.")
    it = write_itinerary(trip_name, note, days, ask=ask, stops=stops, kind=kind)
    parts = []
    parts_dir = os.path.join(session_dir, "recap_parts")
    os.makedirs(parts_dir, exist_ok=True)
    it["hook"] = (hook or it.get("hook") or "").strip() or ((f"{trip_name}: you have to see this" if K is KINDS["trip"] else trip_name) if trip_name else K["hook_none"])
    if hype:
        rate = None
        if visual:
            from engine.visual_context import rate_scenery
            rate = rate_scenery
        glimpses = pick_glimpses(days, GLIMPSES, glimpse_s, grab=grab, rate=rate)
        if visual:
            fix_rotation(glimpses, ffmpeg=ffmpeg, known=rot_known)
        if rotations:
            apply_rotations(glimpses, rotations)
        if glimpses:
            hook_png = caption_png(os.path.join(parts_dir, "hook.png"), it["hook"], y_frac=0.3, size=96, lower=cine)
            for gi, g in enumerate(glimpses, 1):
                out = os.path.join(parts_dir, f"glimpse_{gi}.mp4")
                render_clip(ffmpeg, g["file"], g["start"], glimpse_s, out, hook_png, layout, g["size"], audio=has_audio(g["file"]) and not mute_orig,
                            cap_from=0.0, cap_gap=0.0, grade=grade, fade_s=fade_s, rotate=g.get("rotate", 0), fix=fix_for(g["file"]), **zoom_kw(), **trans_kw(g["file"], g["start"], glimpse_s, g["size"]))
                note_shot(out, g["size"], [hook_png])
                parts.append(out)
            print(f"[Log] Opening: hook \"{it['hook']}\" over {len(glimpses)} glimpse(s).")
        if cine:
            m0 = title_m or days[0]["moments"][0]
            out = os.path.join(parts_dir, "trip_title.mp4")
            lay = cinematic_layers(os.path.join(parts_dir, "trip_title"), it["title"], " · ".join(stops) if stops else (" · ".join(trip_places[:4]) or K["tagline"]), "",
                                   look=frame_look(ffmpeg, m0["file"], m0["start"] + 1.0), index=0)
            render_clip(ffmpeg, m0["file"], m0["start"], title_s, out, None, layout, m0["size"], audio=has_audio(m0["file"]) and not mute_orig, grade=grade, fade_s=fade_s, layers=lay, rotate=m0.get("rotate", 0), fix=fix_for(m0["file"]), **zoom_kw(), **trans_kw(m0["file"], m0["start"], title_s, m0["size"]))
            note_shot(out, m0["size"], [png for png, _ts in lay or []])
            parts.append(out)
        else:
            title = title_card_png(os.path.join(parts_dir, "trip_title.png"), it["title"], " · ".join(stops) if stops else K["by"], "")
            card = os.path.join(parts_dir, "trip_title.mp4")
            render_card(ffmpeg, title, card)
            parts.append(card)
    labels = moment_labels(days, cine)
    for d, row in zip(days, it["days"]):
        day_places = list(dict.fromkeys(m["place"] for m in d["moments"] if m.get("place") and not is_plain_area(m["place"]) and m["place"] != "In flight"))
        if day_places:
            three = " · ".join(day_places[:3])
            row["title"] = (three if len(three) <= 40 else " · ".join(day_places[:2]))[:50]           # the real places, not a vague "Day 3 Northvale"
    for di, (d, row) in enumerate(zip(days, it["days"]), 1):
        if cine:
            card_png = None      # the title appears over the day's first shot instead of a card
        elif stops:
            card_png = title_card_png(os.path.join(parts_dir, f"card_{di}.png"), row["title"], f"{K['stop_unit']} {di} of {len(days)}", row["summary"])
        else:
            card_png = title_card_png(os.path.join(parts_dir, f"card_{di}.png"), f"{K['unit']} {di}", row["title"], row["summary"])
        if card_png:
            card = os.path.join(parts_dir, f"card_{di}.mp4")
            render_card(ffmpeg, card_png, card)
            parts.append(card)
        for mi, (m, cap) in enumerate(zip(d["moments"], row["captions"]), 1):
            label = labels[di - 1][mi - 1] or ("" if cine else cap)             # cinematic: the place name only; no vague picture captions
            cap_png = caption_png(os.path.join(parts_dir, f"cap_{di}_{mi}.png"), label, lower=cine) if label and not (cine and mi == 1) else None
            out = os.path.join(parts_dir, f"clip_{di}_{mi}.mp4")
            lay, secs = None, m["end"] - m["start"]
            if cine and mi == 1:
                lay = cinematic_layers(os.path.join(parts_dir, f"title_{di}"), row["title"], f"{unit} {di}" if len(days) > 1 else "",
                                       look=frame_look(ffmpeg, m["file"], m["start"] + 1.0), index=di)
                secs = max(secs, first_min)
            render_clip(ffmpeg, m["file"], m["start"], secs, out, cap_png, layout, m["size"], audio=has_audio(m["file"]) and not mute_orig, grade=grade, fade_s=fade_s, layers=lay, rotate=m.get("rotate", 0), fix=fix_for(m["file"]), **zoom_kw(), **trans_kw(m["file"], m["start"], secs, m["size"]))
            note_shot(out, m["size"], [cap_png] + [png for png, _ts in lay or []])
            parts.append(out)
        print(f"[Log] {K['unit']} {di} rendered.")
    # a closing card, so the recap does not just fade out on the last shot
    end_line = " · ".join(trip_places[:4]) if trip_places else (" · ".join(stops) if stops else "")
    end_png = os.path.join(parts_dir, "end.png")
    if cine:
        cinematic_card_png(end_png, it["title"], end_line, f"{len(days)} {unit.lower()}s" if len(days) > 1 else "")
    else:
        title_card_png(end_png, it["title"], end_line or "Thanks for watching", f"{len(days)} {unit.lower()}s" if len(days) > 1 else "")
    end_card = os.path.join(parts_dir, "end.mp4")
    render_card(ffmpeg, end_png, end_card, seconds=closing_s)
    parts.append(end_card)
    if clean_sound and not mute_orig:                 # the clips' own sound is in the recap: take the noise out of every shot first
        from engine.audio_clean import clean_audio
        cleaned = sum(1 for p in parts if os.path.basename(p).startswith(("clip_", "glimpse_", "trip_title")) and has_audio(p) and clean_audio(p))
        print(f"[Log] Cleaned the sound of {cleaned} shot(s).")
    if trans_name == "subject":
        shots = [p for p in parts if os.path.basename(p).startswith(("clip_", "glimpse_", "trip_title"))]
        pairs = {(a, b) for k, (a, b) in enumerate(zip(shots, shots[1:])) if k < len(tail_seq) and tail_seq[k] == "subject" and parts.index(b) == parts.index(a) + 1}
        if pairs:
            try:
                parts, made = _subject.apply(ffmpeg, parts, pairs, (W, H), _enc(), os.path.join(parts_dir, "subject"), overlays=overlays, boxes=boxes, style=subject_style, max_bridges=subject_max)
                print(f"[Log] Subject cut-out: {made} of {len(pairs)} planned cut(s) have the person staying in front; the rest are plain cuts.")
            except Exception as e:
                print(f"[Warning] Subject cut-out skipped ({e}); plain cuts are used.")
    video = os.path.join(session_dir, "recap.mp4")
    concat(ffmpeg, parts, video, session_dir, music=music, music_gain=0.9 if mute_orig else 0.25, music_start=music_start, music_only=mute_orig)
    edit_log = {}
    cut_kind = ((director or {}).get("sfx") or {}).get("cut") or ((director or {}).get("sfx") or {}).get("broll")
    if director and cut_kind:                          # the director's cut sound under every shot change
        from engine import sfx_mix
        events = cut_sound_events([(p, video_info(p)[0] or 0.0) for p in parts], cut_kind)
        edit_log["sfx"] = len(sfx_mix.mix_events(video, events, volume_db=strength["sfx_db"]))
    if director:
        edit_log.update({"style": edit, "strength": edit_strength, "zoom": round(zoom_amount, 3), "look": look_name})
        print(f"[Log] Edit style {edit} ({edit_strength}): slow zoom {zoom_amount * 100:.1f} %, {edit_log.get('sfx', 0)} cut sound(s), look {look_name}.")
    md_path, js_path = os.path.join(session_dir, "itinerary.md"), os.path.join(session_dir, "itinerary.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(itinerary_markdown(it, days, unit))
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump({"itinerary": it, "edit": edit_log, "days": [{"files": d["files"], "moments": [{k: v for k, v in m.items() if k != "size"} for m in d["moments"]]}
                                             for d in days]}, f, indent=1, ensure_ascii=False)
    print(f"[Success] Trip recap ready at: {video}")
    print(f"[Log] Itinerary: {md_path}")
    return {"video": video, "itinerary_md": md_path, "itinerary_json": js_path, "days": len(days)}


def share_place_names(src_dir, dst_dir):
    """Copy the place names decided for one version into the other's folder (the first version's names win), so the same spot has the same
    name in the portrait and the landscape recap. Returns how many names were carried over."""
    def load(d):
        try:
            with open(os.path.join(d, "place_names.json"), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
    names = load(src_dir)
    if not names:
        return 0
    merged = {**load(dst_dir), **names}
    os.makedirs(dst_dir, exist_ok=True)
    with open(os.path.join(dst_dir, "place_names.json"), "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=1, ensure_ascii=False)
    return len(names)


def make_recap_versions(paths, session_dir, aspect=None, style="auto", **kw):
    """One recap for portrait devices (9:16, only the vertical videos) and one for landscape (16:9 unless `aspect` is given, only the
    landscape videos). Returns {"portrait": result, "landscape": result}; the videos are session_dir/recap_portrait.mp4 and recap_landscape.mp4."""
    import shutil
    style = "cinematic" if style == "auto" else style
    out = {}
    for name, asp, ori in (("portrait", "9:16", "portrait"), ("landscape", aspect or "16:9", "landscape")):
        sub = os.path.join(session_dir, name)
        print(f"[Log] === {name.capitalize()} version ({asp}) ===")
        if out:                                                    # the second version reuses the first one's place names
            carried = share_place_names(os.path.join(session_dir, next(iter(out))), sub)
            if carried:
                print(f"[Log] {carried} place name(s) carried over from the {next(iter(out))} version.")
        res = make_recap(paths, sub, aspect=asp, style=style, orientation=ori, **kw)
        final = os.path.join(session_dir, f"recap_{name}.mp4")
        shutil.copyfile(res["video"], final)
        res["video"] = final
        out[name] = res
        print(f"[Success] {name.capitalize()} recap: {final}")
    return out


def infos_order(infos, f):
    return next((i for i, x in enumerate(infos) if x[0] == f), 0)


def _explicit_filter(args):
    """The colour filter only when it was typed on the command line (--video_filter has a default of 'none' that must not switch off the
    automatic look); an Auto-edit style may have filled it in, and that look is applied by the style itself."""
    given = any(a == "--video_filter" or a.startswith("--video_filter=") for a in sys.argv[1:])
    return (getattr(args, "video_filter", "default") or "default") if given else "default"


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
              "Google Photos link), e.g. --mode TRIP --trip_videos day1 day2 --trip_name Northvale")
        sys.exit(2)
    layout = getattr(args, "layout", "auto")
    try:
        common = dict(trip_name=getattr(args, "trip_name", "") or "", note=getattr(args, "user_context", "") or "",
                      total_seconds=getattr(args, "recap_length", 60) or 60, music=getattr(args, "music", None),
                      visual=bool(getattr(args, "visual_context", False)), hook=getattr(args, "recap_hook", "") or "",
                      stops=getattr(args, "trip_stops", None), geocode=not getattr(args, "recap_no_geocode", False), enhance=getattr(args, "enhance", "off") or "off",
                      enhance_strength=getattr(args, "enhance_strength", "medium") or "medium",
                      manual_rotate=getattr(args, "recap_rotate", "") or "", place_names=getattr(args, "place_names", "") or "", avoid=getattr(args, "recap_avoid", "") or "", kind=getattr(args, "recap_kind", "trip") or "trip", keep_sound=bool(getattr(args, "recap_keep_sound", False)),
                      grade_name=_explicit_filter(args), edit=getattr(args, "auto_edit", "") if getattr(args, "auto_edit", "none") != "none" else "",
                      edit_strength=getattr(args, "edit_strength", "medium") or "medium", clean_sound=bool(getattr(args, "clean_audio", False)), sample=getattr(args, "recap_sample", "auto") or "auto", transitions=getattr(args, "transitions", "auto") or "auto", subject_look=getattr(args, "subject_look", "auto") or "auto", subject_color=getattr(args, "subject_color", "auto") or "auto", subject_max=getattr(args, "subject_max", 2), layout="fit" if layout == "fit" else ("crop" if layout == "crop" else "auto"))
        style = getattr(args, "recap_style", "auto") or "auto"
        if getattr(args, "recap_versions", "one") == "both":
            made = make_recap_versions(paths, session_dir, aspect=getattr(args, "recap_aspect", None), style=style, **common)
            videos = [r["video"] for r in made.values()]
        else:
            videos = [make_recap(paths, session_dir, style=style, aspect=getattr(args, "recap_aspect", None),
                                 orientation=getattr(args, "recap_orientation", "any") or "any", **common)["video"]]
        drive = getattr(args, "upload_drive", None)
        if drive:
            from engine.drive_upload import upload
            if len(upload(videos, drive)) < len(videos):
                sys.exit(1)
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        sys.exit(1)
    sys.exit(0)

