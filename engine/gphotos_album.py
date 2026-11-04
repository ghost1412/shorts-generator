"""Videos from a Google Photos *shared album* link (https://photos.app.goo.gl/...), for the trip recap.

Google closed its Library API to apps in 2025 (an app can only see what it uploaded itself), so there is no official way to read a
user's photos. A shared album, however, is a public web page (anyone with the link). This module reads that page the way a browser
does and downloads the album's videos. It is unofficial: Google can change the page format, and then this stops working (the error
says so); the fallback is to download the videos from the album yourself.

Only albums you share by link, and only your own use of them: nothing is uploaded and no login is needed.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0"
VIDEO_KEY = "76647426"          # present on video items of the page data
MAX_VIDEO_SECONDS = 300         # longer videos are skipped (a 20-minute recording is not a recap clip)


class AlbumError(RuntimeError):
    pass


def _get(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data, {"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


def is_album_link(text):
    return bool(re.match(r"https?://(photos\.app\.goo\.gl|photos\.google\.com/share|photos\.google\.com/u/\d+/share)/", str(text or "").strip()))


def parse_page(html):
    """(album_id, title, first_items, continuation_token) from the shared-album page, AlbumError when the format is unknown."""
    i = html.find("AF_initDataCallback({key: 'ds:1'")
    if i < 0:
        raise AlbumError("This does not look like a shared Google Photos album page (the link may be private, or Google changed the page).")
    j = html.index("data:", i) + 5
    try:
        data, _ = json.JSONDecoder().raw_decode(html[j:])
        items, token, meta = data[1], data[2], data[3]
        return meta[0], str(meta[1]), list(items), (token if isinstance(token, str) else None)
    except (ValueError, IndexError, TypeError, KeyError) as e:
        raise AlbumError(f"Could not read the album page: Google may have changed its format ({e}).")


def next_page(album_id, token, key):
    """(items, next_token) from the album's continuation request."""
    inner = json.dumps([album_id, token, None, key])
    body = urllib.parse.urlencode({"f.req": json.dumps([[["snAcKc", inner, None, "generic"]]])}).encode()
    raw, _ = _get(f"https://photos.google.com/_/PhotosUi/data/batchexecute?rpcids=snAcKc&source-path=%2Fshare%2F{album_id}&rt=c", body,
                  {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    line = next((ln for ln in raw.decode("utf-8", "ignore").splitlines() if ln.startswith('[["wrb.fr"')), None)
    if not line:
        raise AlbumError("Google did not return the next page of the album.")
    payload = json.loads(json.loads(line)[0][2])
    got = payload[1] if len(payload) > 1 and isinstance(payload[1], list) else []
    token = payload[2] if len(payload) > 2 and isinstance(payload[2], str) else None
    return got, token


def to_rows(items):
    """[{id, url, w, h, ts (ms), video, seconds}] from the raw page items; unreadable items are skipped."""
    rows = []
    for it in items:
        try:
            iid, (url, w, h, *_), ts = it[0], it[1], it[2]
            meta = it[-1] if isinstance(it[-1], dict) else {}
            vid = meta.get(VIDEO_KEY)
            rows.append({"id": iid, "url": url, "w": int(w), "h": int(h), "ts": int(ts), "video": bool(vid),
                         "seconds": (vid[0] / 1000.0 if vid else 0.0)})
        except (ValueError, IndexError, TypeError, KeyError):
            continue
    return rows


def list_album(link, fetch=_get, pages_max=60):
    """(title, rows) for the whole shared album, following its continuation pages."""
    html, final = fetch(link)
    album_id, title, items, token = parse_page(html.decode("utf-8", "ignore"))
    key = (re.search(r"[?&]key=([\w-]+)", final) or re.search(r"[?&]key=([\w-]+)", link) or [None, ""])[1]
    n = 0
    while token and n < pages_max:
        more, token = next_page(album_id, token, key)
        items += more
        n += 1
    return title, to_rows(items)


def pick_videos(rows, max_seconds=MAX_VIDEO_SECONDS):
    """(kept, skipped) videos in time order; videos longer than `max_seconds` are skipped."""
    vids = sorted((r for r in rows if r["video"]), key=lambda r: r["ts"])
    return [r for r in vids if r["seconds"] <= max_seconds], [r for r in vids if r["seconds"] > max_seconds]


def local_time(ts_ms, utc_offset_hours):
    return time.gmtime(ts_ms / 1000.0 + utc_offset_hours * 3600)


def plan_files(videos, dest, utc_offset_hours=5.0):
    """[(row, path)] with one folder per calendar day, 'day1_2026-10-15' ..., and names that sort in filming order."""
    days = sorted({time.strftime("%Y-%m-%d", local_time(v["ts"], utc_offset_hours)) for v in videos})
    out = []
    for v in videos:
        t = local_time(v["ts"], utc_offset_hours)
        day = time.strftime("%Y-%m-%d", t)
        folder = os.path.join(dest, f"day{days.index(day) + 1}_{day}")
        out.append((v, os.path.join(folder, f"{time.strftime('%H%M%S', t)}_{re.sub(r'[^A-Za-z0-9]', '', v['id'])[-8:]}.mp4")))
    return out


def download(row, path, fetch=_get, retries=3):
    """Download one video to `path` (skipped when it is already there). Returns True on success."""
    if os.path.isfile(path) and os.path.getsize(path) > 10000:
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(retries):
        try:
            data, _ = fetch(row["url"] + "=dv", timeout=600)
            if len(data) < 10000:
                raise AlbumError("empty video")
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return True
        except Exception:
            time.sleep(2 * (attempt + 1))
    return False


def download_album(link, dest, max_seconds=MAX_VIDEO_SECONDS, utc_offset_hours=5.0, workers=4, only_days=None, log=print):
    """Download the album's videos into `dest/dayN_YYYY-MM-DD/`. Returns {"title", "folders", "downloaded", "failed", "skipped"}."""
    title, rows = list_album(link)
    kept, skipped = pick_videos(rows, max_seconds)
    log(f"[Log] Album '{title}': {len(rows)} items, {len(kept) + len(skipped)} videos; skipping {len(skipped)} longer than {max_seconds // 60} min.")
    plan = plan_files(kept, dest, utc_offset_hours)
    if only_days:
        plan = [(v, p) for v, p in plan if any(d in os.path.basename(os.path.dirname(p)) for d in only_days)]
    done = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, ok in enumerate(ex.map(lambda vp: download(*vp), plan), 1):
            done += bool(ok)
            failed += not ok
            if i % 10 == 0 or i == len(plan):
                log(f"[Log] Downloaded {i}/{len(plan)} video(s).")
    folders = sorted({os.path.dirname(p) for _, p in plan})
    return {"title": title, "folders": folders, "downloaded": done, "failed": failed, "skipped": len(skipped)}
