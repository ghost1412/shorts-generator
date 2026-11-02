"""News sourcing for the NEWS / NEWS_SERIOUS modes: parse feeds, drop sensitive stories, rank by coverage, avoid repeats.

Pure functions (no network) so they can be tested with saved feed XML.
"""
import email.utils
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

ATOM = {"atom": "http://www.w3.org/2005/Atom"}
STOP = frozenset("a an the of to in on for and or at by with from as is are was were be been it its this that after over "
                 "into new says say said us".split())

# Stories a joke persona must not touch (deaths, violence, disasters, abuse, court cases, medical crises).
SENSITIVE = re.compile(
    r"\b(dead|dies|died|death|deaths|killed|killing|kills|murder\w*|shoot\w*|shot|stabb\w*|massacre|terror\w*|"
    r"attack\w*|bomb\w*|war|invasion|hostage\w*|rape\w*|assault\w*|abuse\w*|suicide|overdose|fatal\w*|crash\w*|"
    r"earthquake|tsunami|hurricane|wildfire|flood\w*|disaster|victims?|funeral|tragedy|tragic|mourn\w*|cancer|"
    r"pandemic|outbreak|missing|kidnap\w*|trial|sentenced|convicted|lawsuit)\b", re.I)


def is_sensitive(text):
    return bool(SENSITIVE.search(text or ""))


def clean(text):
    """Strip tags/entities and collapse whitespace (feed descriptions are often HTML)."""
    text = html.unescape(text or "")  # feeds ship descriptions HTML-escaped, so unescape before stripping tags
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _is_fresh(dt, cutoff):
    return dt is None or dt >= cutoff


def parse_feed(xml_text, feed_url, cutoff):
    """[{headline, source, feed, description, published}] from an RSS 2.0 or Atom document.
    Items whose date cannot be read are kept (and counted as undated) instead of silently treated as fresh."""
    root = ET.fromstring(xml_text)
    out = []
    for entry in root.findall("atom:entry", ATOM):
        title = entry.find("atom:title", ATOM)
        if title is None or not (title.text or "").strip():
            continue
        link = entry.find("atom:link", ATOM)
        updated = entry.find("atom:updated", ATOM)
        dt = None
        if updated is not None and updated.text:
            try:
                dt = datetime.fromisoformat(updated.text.strip().replace("Z", "+00:00"))
            except ValueError:
                dt = None
        if _is_fresh(dt, cutoff):
            summary = entry.find("atom:summary", ATOM)
            if summary is None:
                summary = entry.find("atom:content", ATOM)
            out.append({"headline": clean(title.text), "source": link.get("href", feed_url) if link is not None else feed_url,
                        "feed": feed_url, "description": clean(summary.text) if summary is not None else "",
                        "published": dt.isoformat() if dt else None})
    for item in root.findall(".//item"):
        title = item.find("title")
        if title is None or not (title.text or "").strip():
            continue
        pub = item.find("pubDate")
        dt = None
        if pub is not None and pub.text:
            try:
                dt = email.utils.parsedate_to_datetime(pub.text.strip())
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                dt = None
        if _is_fresh(dt, cutoff):
            src, link = item.find("source"), item.find("link")
            name = src.text if src is not None and src.text else "News"
            desc = item.find("description")
            out.append({"headline": clean(title.text), "source": f"{name} ({link.text if link is not None else feed_url})",
                        "feed": feed_url, "description": clean(desc.text) if desc is not None else "",
                        "published": dt.isoformat() if dt else None, "outlet": name})
    return out


def tokens(headline):
    return {w for w in re.findall(r"[a-z0-9]+", headline.lower()) if w not in STOP and len(w) > 2}


def same_story(a, b, threshold=0.5):
    ta, tb = tokens(a), tokens(b)
    return bool(ta and tb) and len(ta & tb) / min(len(ta), len(tb)) >= threshold


def cluster(headlines):
    """Group items about the same story. Each cluster: the first item plus `coverage` = number of distinct feeds/outlets."""
    groups = []
    for h in headlines:
        for g in groups:
            if same_story(h["headline"], g["items"][0]["headline"]):
                g["items"].append(h)
                break
        else:
            groups.append({"items": [h]})
    for g in groups:
        g["coverage"] = len({i.get("outlet") or i["feed"] for i in g["items"]})
        best = max(g["items"], key=lambda i: len(i.get("description") or ""))
        g["best"] = dict(g["items"][0], description=best.get("description", ""))
    return groups


def history_path():
    return os.path.join(os.path.expanduser("~"), ".cache", "shortsflow", "news_history.json")


def load_history(path=None, keep_days=14, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        with open(path or history_path(), "r", encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError):
        return []
    cutoff = (now - timedelta(days=keep_days)).isoformat()
    return [i for i in items if isinstance(i, dict) and i.get("at", "") >= cutoff]


def remember(headline, path=None, now=None):
    now = now or datetime.now(timezone.utc)
    p = path or history_path()
    items = load_history(p, now=now) + [{"headline": headline, "at": now.isoformat()}]
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(items[-200:], f)
    except OSError:
        pass


def pick(headlines, history=None, avoid_sensitive=True, rng=None):
    """Best cluster: not posted recently, not sensitive (when asked), widest coverage, then newest. Returns the item
    (with its best description) or None."""
    import random
    rng = rng or random
    seen = [h["headline"] for h in history or []]
    groups = cluster(headlines)
    ok = [g for g in groups
          if not any(same_story(g["best"]["headline"], s) for s in seen)
          and not (avoid_sensitive and is_sensitive(g["best"]["headline"] + " " + g["best"].get("description", "")))]
    if not ok:
        return None
    top = max(g["coverage"] for g in ok)
    best = [g for g in ok if g["coverage"] == top]
    return rng.choice(best)["best"]


def ungrounded_numbers(story, source_text):
    """Numbers in the retelling that appear nowhere in the headline/description it was written from."""
    have = set(re.findall(r"\d[\d,.]*", source_text or ""))
    have = {n.strip(",.") for n in have}
    return [n for n in (x.strip(",.") for x in re.findall(r"\d[\d,.]*", story or "")) if n and n not in have]
