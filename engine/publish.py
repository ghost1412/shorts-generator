"""Publish rendered clips to TikTok, Instagram Reels and YouTube Shorts, now or on a schedule.

Uses the Upload-Post service (https://upload-post.com), which holds the platform OAuth tokens so
ShortsFlow does not need an app review for each network. Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER.

    python -m engine.publish sessions/extraction_123/metadata.json --platforms tiktok,instagram,youtube
    python -m engine.publish metadata.json --platforms tiktok --start 2026-11-02T10:00 --every 180 --timezone Europe/Madrid

`metadata.json` is the file clip extraction writes next to the clips ([{file, title, description, tags}]).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import requests

API_URL = "https://api.upload-post.com/api/upload"
PLATFORMS = ("tiktok", "instagram", "youtube", "facebook", "linkedin", "x", "threads", "pinterest")
TIMEOUT = 120


def hashtags(tags, limit=5):
    """['AI tools', 'shorts'] -> '#aitools #shorts' (hashtags can't contain spaces)."""
    out = []
    for t in tags or []:
        tag = "#" + "".join(ch for ch in str(t) if ch.isalnum())
        if len(tag) > 1 and tag.lower() not in (o.lower() for o in out):
            out.append(tag)
        if len(out) >= limit:
            break
    return " ".join(out)


def build_fields(item, platforms, user, scheduled_at=None, timezone=None):
    """Form fields for one clip. TikTok/Instagram get a caption with hashtags, YouTube a clean title."""
    title = (item.get("title") or "New short").strip()
    tags = hashtags(item.get("tags"))
    caption = f"{title} {tags}".strip()
    fields = [("user", user), ("title", title), ("description", item.get("description") or title),
              ("tiktok_title", caption[:2200]), ("instagram_title", caption[:2200]),
              ("youtube_title", title[:100]), ("async_upload", "true")]
    fields += [("platform[]", p) for p in platforms]
    if scheduled_at:
        fields.append(("scheduled_date", scheduled_at.strftime("%Y-%m-%dT%H:%M:%S")))
        fields.append(("timezone", timezone or "UTC"))
    return fields


def schedule_slots(count, start=None, every_minutes=180):
    """`count` datetimes spaced `every_minutes` apart from `start`, or [None]*count to post immediately."""
    if start is None:
        return [None] * count
    return [start + timedelta(minutes=every_minutes * i) for i in range(count)]


def publish_clip(video_path, fields, api_key, post=requests.post):
    with open(video_path, "rb") as f:
        resp = post(API_URL, headers={"Authorization": f"Apikey {api_key}"}, data=fields,
                    files={"video": (os.path.basename(video_path), f, "video/mp4")}, timeout=TIMEOUT)
    try:
        body = resp.json()
    except ValueError:
        body = {"error": resp.text[:300]}
    return resp.status_code, body


def publish_all(metadata_path, platforms, start=None, every_minutes=180, timezone=None,
                api_key=None, user=None, dry_run=False, post=requests.post):
    api_key = api_key or os.getenv("UPLOAD_POST_API_KEY")
    user = user or os.getenv("UPLOAD_POST_USER")
    if not dry_run and not (api_key and user):
        raise SystemExit("Set UPLOAD_POST_API_KEY and UPLOAD_POST_USER (create both at upload-post.com).")
    bad = [p for p in platforms if p not in PLATFORMS]
    if bad:
        raise SystemExit(f"Unknown platform(s): {', '.join(bad)}. Choose from: {', '.join(PLATFORMS)}")

    base = os.path.dirname(os.path.abspath(metadata_path))
    with open(metadata_path, encoding="utf-8") as f:
        items = json.load(f)
    slots = schedule_slots(len(items), start, every_minutes)
    results = []
    for item, slot in zip(items, slots):
        video = os.path.join(base, item.get("file", ""))
        when = slot.isoformat() if slot else "now"
        if not os.path.isfile(video):
            results.append({"file": item.get("file"), "ok": False, "error": "video file not found"})
            continue
        fields = build_fields(item, platforms, user or "DRY_RUN", slot, timezone)
        if dry_run:
            print(f"[dry-run] {item['file']} -> {','.join(platforms)} at {when}: {item.get('title')}")
            results.append({"file": item["file"], "ok": True, "dry_run": True})
            continue
        status, body = publish_clip(video, fields, api_key, post)
        ok = status in (200, 202) and body.get("success", True) is not False
        print(f"[{'ok' if ok else 'FAILED'}] {item['file']} -> {','.join(platforms)} at {when} ({status})"
              + ("" if ok else f": {body.get('error') or body}"))
        results.append({"file": item["file"], "ok": ok, "status": status, "response": body})
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish clips to TikTok / Instagram / YouTube via Upload-Post")
    ap.add_argument("metadata", help="metadata.json written by clip extraction")
    ap.add_argument("--platforms", default="tiktok,instagram,youtube", help="comma-separated: " + ", ".join(PLATFORMS))
    ap.add_argument("--start", help="first slot, local time in --timezone, e.g. 2026-11-02T10:00. Omit to post now.")
    ap.add_argument("--every", type=int, default=180, help="minutes between scheduled clips (default 180)")
    ap.add_argument("--timezone", default="UTC", help="IANA timezone for --start, e.g. Europe/Madrid")
    ap.add_argument("--dry-run", action="store_true", help="print what would be posted, send nothing")
    a = ap.parse_args(argv)
    start = datetime.fromisoformat(a.start) if a.start else None
    results = publish_all(a.metadata, [p.strip().lower() for p in a.platforms.split(",") if p.strip()],
                          start, a.every, a.timezone, dry_run=a.dry_run)
    sys.exit(0 if results and all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
