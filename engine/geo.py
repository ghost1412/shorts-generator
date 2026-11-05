"""Where a video was filmed: GPS from the file's own metadata, grouped into places, named by reverse geocoding.

Phones write the position into the video (an ISO 6709 `location` tag such as `+43.2466+078.8971/`). The trip recap uses it to tell
the places of a day apart and to name them. Naming sends the rounded coordinates (about 100 m) to the free OpenStreetMap Nominatim
service; set SHORTSFLOW_GEOCODE=off (or pass geocode=False) to keep everything on the PC. Every step fails safe: no tag, no
network, an unknown place -> the recap simply has no place name.
"""
import json
import math
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "ShortsFlow-TripRecap/1.0 (open-source video tool)"
_ISO = re.compile(r"^\s*([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def parse_iso6709(text):
    """(lat, lon) from '+43.2466+078.8971/' (an altitude after them is ignored), None when it is not a position."""
    m = _ISO.match(str(text or ""))
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    return lat, lon


def video_location(path, ffprobe="ffprobe", run=subprocess.run):
    """(lat, lon) stored in the video file, None when it has none."""
    try:
        r = run([ffprobe, "-v", "error", "-show_entries", "format_tags=location,location-eng", "-of", "json", path],
                capture_output=True, text=True, timeout=30)
        tags = (json.loads(r.stdout or "{}").get("format") or {}).get("tags") or {}
    except Exception:
        return None
    for k in ("location", "location-eng"):
        if tags.get(k):
            return parse_iso6709(tags[k])
    return None


def distance_km(a, b):
    """Great-circle distance between two (lat, lon) points."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def group_places(files, locations, radius_km=3.0):
    """Places visited in order: [{"files": [...], "center": (lat, lon) or None}].

    `files` are in filming order, `locations` the (lat, lon) of each (None when unknown). A new place starts when a video is more than
    `radius_km` from the place's first video; a video without GPS stays with the place before it."""
    places = []
    for f, loc in zip(files, locations):
        cur = places[-1] if places else None
        if cur is None or (loc is not None and cur["center"] is not None and distance_km(cur["center"], loc) > radius_km):
            places.append({"files": [f], "center": loc})
        else:
            cur["files"].append(f)
            if cur["center"] is None:
                cur["center"] = loc
    return places


def _short(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


GOOD_CATEGORIES = ("tourism", "natural", "leisure", "historic", "waterway", "place", "boundary")


def name_from_reply(data):
    """{"name", "area", "hint"} from a Nominatim reverse reply. `name` is a named feature (a lake, a viewpoint, a resort) and is empty
    when the spot is only a bench, a road or a cafe; `area` is the nearest settlement or district; `hint` is the full address line."""
    if not isinstance(data, dict) or "error" in data:
        return None
    addr = data.get("address") or {}
    feature = _short(data.get("name")) if data.get("category") in GOOD_CATEGORIES else ""
    if re.fullmatch(r"[A-Z]{1,3}[\d\-]+", feature or ""):
        feature = ""                                  # a road code such as KZ05-08
    area = ""
    for k in ("suburb", "neighbourhood", "quarter", "village", "hamlet", "town", "city", "municipality", "county", "state_district"):
        if addr.get(k):
            area = _short(addr[k])
            break
    region = _short(addr.get("state") or addr.get("region") or addr.get("country"))
    if not (feature or area or region):
        return None
    return {"name": feature[:60], "area": area[:60], "region": region[:60], "hint": _short(data.get("display_name"))[:160]}


def place_name(loc, cache_path=None, fetch=None, language="en", pause=1.1):
    """{"name", "area", "region", "hint"} for a (lat, lon), None when it cannot be had. Cached in `cache_path` (json) by 3-decimal coordinates."""
    if loc is None or (os.getenv("SHORTSFLOW_GEOCODE") or "").strip().lower() in ("off", "0", "no", "false"):
        return None
    key = f"{loc[0]:.3f},{loc[1]:.3f}"
    cache = {}
    if cache_path and os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}
    if key in cache:
        return cache[key] or None
    if fetch is None:
        def fetch(lat, lon):
            q = urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat:.3f}", "lon": f"{lon:.3f}", "zoom": 18, "accept-language": language})
            req = urllib.request.Request(f"{NOMINATIM}?{q}", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                time.sleep(pause)               # the service allows one request per second
                return json.load(r)
    try:
        found = name_from_reply(fetch(loc[0], loc[1]))
    except Exception as e:
        print(f"[Warning] Could not look up the place name ({str(e)[:80]}).")
        return None
    cache[key] = found or {}
    if cache_path:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=1, ensure_ascii=False)
        except OSError:
            pass
    return found


ATTRACTION_QUERIES = ("viewpoint", "waterfall", "lake", "attraction", "park")


def _cached(cache_path, key, make):
    """cache[key] from the json file, else make() stored there. A failed make() (None) is not stored."""
    cache = {}
    if cache_path and os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}
    if key in cache:
        return cache[key]
    value = make()
    if value is not None and cache_path:
        cache[key] = value
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=1, ensure_ascii=False)
        except OSError:
            pass
    return value


def nearby_attractions(loc, cache_path=None, fetch=None, span=0.03, language="en", pause=1.1, limit=8):
    """Named tourist places (viewpoints, waterfalls, lakes, attractions, parks) within about 3 km of (lat, lon), from OpenStreetMap
    search; [] when none, offline, or SHORTSFLOW_GEOCODE=off. Names can be in the local language (the caller translates)."""
    if loc is None or (os.getenv("SHORTSFLOW_GEOCODE") or "").strip().lower() in ("off", "0", "no", "false"):
        return []
    lat, lon = loc

    def make():
        names, failed = [], 0
        for q in ATTRACTION_QUERIES:
            try:
                if fetch is not None:
                    rows = fetch(q, lat, lon, span)
                else:
                    params = urllib.parse.urlencode({"q": q, "format": "jsonv2", "bounded": 1, "limit": 5, "accept-language": language,
                                                     "viewbox": f"{lon - span},{lat + span},{lon + span},{lat - span}"})
                    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{params}", headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        rows = json.load(r)
                    time.sleep(pause)
            except Exception:
                failed += 1
                continue
            for row in rows or []:
                name = _short(row.get("name"))
                if name and not re.fullmatch(r"[A-Z]{1,3}[\d\-]+", name) and name not in names:
                    names.append(name)
        return None if failed == len(ATTRACTION_QUERIES) else names[:limit]
    return _cached(cache_path, f"near:{lat:.3f},{lon:.3f}", make) or []
