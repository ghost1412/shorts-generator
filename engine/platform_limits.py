"""Caption / title / hashtag limits per platform, and a helper that fits a clip's metadata into them.

The numbers are the limits the platforms document today (they change; keep them in one place so they are easy to update):
- TikTok: caption up to 2200 characters, hashtags count towards it.
- Instagram Reels: caption up to 2200 characters, at most 30 hashtags.
- YouTube Shorts: title up to 100 characters, description up to 5000, the tag list up to 500 characters in total.

Nothing is ever cut in the middle of a word or a hashtag: text is shortened at a word boundary and hashtags are dropped whole.
"""
import re

LIMITS = {
    "tiktok": {"title": 150, "caption": 2200, "hashtags": 5},
    "instagram": {"title": 125, "caption": 2200, "hashtags": 30},
    "youtube": {"title": 100, "description": 5000, "tag_chars": 500, "hashtags": 15},
}
ELLIPSIS = "…"


def truncate_words(text, limit, ellipsis=ELLIPSIS):
    """Shorten `text` to at most `limit` characters (ellipsis included), cutting at a word boundary."""
    text = (text or "").strip()
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    room = limit - len(ellipsis)
    if room <= 0:
        return text[:limit]
    cut = text[:room + 1]
    if not cut[-1].isspace() and " " in cut:       # we are inside a word: back up to the previous space
        cut = cut[:cut.rfind(" ")]
    cut = cut[:room].rstrip(" ,;:-–—.!?")
    return (cut or text[:room]) + ellipsis


def clean_hashtags(tags, limit=None):
    """['AI tools', 'ai tools', '#shorts', '!!'] -> ['#AItools', '#shorts'] (no spaces or symbols, no duplicates)."""
    out = []
    for t in tags or []:
        tag = "#" + "".join(ch for ch in str(t) if ch.isalnum() or ch == "_")
        if len(tag) > 1 and tag.lower() not in (o.lower() for o in out):
            out.append(tag)
        if limit and len(out) >= limit:
            break
    return out


def join_caption(title, tag_line, limit):
    """'title #a #b' within `limit` characters: the title gives way (cut at a word), the hashtags stay whole."""
    title, tag_line = (title or "").strip(), (tag_line or "").strip()
    full = f"{title} {tag_line}".strip()
    if len(full) <= limit:
        return full
    if len(tag_line) + 2 >= limit:       # hashtags alone do not fit: keep the title only
        return truncate_words(title, limit)
    return f"{truncate_words(title, limit - len(tag_line) - 1)} {tag_line}".strip()


def _strip_hashtags(text):
    return re.sub(r"(?:^|\s)#\w+", "", text or "").strip()


def fit_tag_list(tags, max_chars):
    """Keep tags, in order, while their comma-joined length stays within `max_chars` (YouTube counts the whole list)."""
    kept, used = [], 0
    for t in tags or []:
        t = str(t).strip().lstrip("#")
        if not t:
            continue
        extra = len(t) + (1 if kept else 0) + (2 if " " in t else 0)    # YouTube quotes multi-word tags
        if used + extra > max_chars:
            break
        kept.append(t)
        used += extra
    return kept


def fit_for_platform(platform, title, description="", tags=None):
    """Metadata ready to paste for one platform: {"platform", "title", "text", "hashtags", "tags"}.

    `text` is the caption (TikTok / Instagram) or the description (YouTube). Hashtags the description already carries are
    kept as the hashtags; hashtags are placed at the end and are never cut in half.
    """
    platform = (platform or "").lower()
    if platform in ("shorts", "youtube_shorts", "yt"):
        platform = "youtube"
    if platform not in LIMITS:
        raise ValueError(f"Unknown platform '{platform}'. Choose from: {', '.join(LIMITS)}")
    lim = LIMITS[platform]
    own_tags = re.findall(r"#\w+", description or "")
    hashtags = clean_hashtags(list(own_tags) + list(tags or []), limit=lim["hashtags"])
    body = _strip_hashtags(description)
    title = truncate_words(title or "", lim["title"])

    if platform == "youtube":
        tag_line = " ".join(hashtags)
        budget = lim["description"] - (len(tag_line) + 2 if tag_line else 0)
        text = truncate_words(body, budget)
        text = f"{text}\n\n{tag_line}".strip() if tag_line else text
        return {"platform": platform, "title": title, "text": text, "hashtags": hashtags,
                "tags": fit_tag_list(tags, lim["tag_chars"])}

    # TikTok / Instagram: one caption = title, body and hashtags; hashtags count towards the limit, so drop them whole first
    cap = lim["caption"]
    while hashtags and len(" ".join(hashtags)) + len(title) + 2 > cap:
        hashtags.pop()
    tag_line = " ".join(hashtags)
    head = title
    room = cap - len(head) - (len(tag_line) + 2 if tag_line else 0) - (2 if body else 0)
    parts = [head]
    if body and room > 20:
        parts.append(truncate_words(body, room))
    if tag_line:
        parts.append(tag_line)
    return {"platform": platform, "title": title, "text": "\n\n".join(p for p in parts if p),
            "hashtags": hashtags, "tags": []}
