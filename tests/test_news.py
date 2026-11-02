import json
import random
from datetime import datetime, timedelta, timezone

from engine import news_feed as nf

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
CUTOFF = NOW - timedelta(hours=48)

RSS = """<rss><channel>
<item><title>Cat elected mayor of small town in Alaska</title><link>http://a/1</link><source>AP</source>
 <pubDate>Mon, 02 Nov 2026 09:00:00 GMT</pubDate><description>&lt;p&gt;The cat won 3 of 5 votes.&lt;/p&gt;</description></item>
<item><title>Old story about a cat mayor</title><link>http://a/2</link><source>AP</source>
 <pubDate>Mon, 26 Oct 2026 09:00:00 GMT</pubDate></item>
<item><title>Undated oddity</title><link>http://a/3</link></item>
</channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Alaska town elects cat as mayor</title><link href="http://r/1"/><updated>2026-11-02T10:00:00+00:00</updated>
 <summary>cat mayor</summary></entry>
<entry><title>Fatal crash kills three</title><link href="http://r/2"/><updated>2026-11-02T10:30:00Z</updated></entry>
</feed>"""


def test_parse_rss_drops_stale_keeps_undated_and_cleans_html():
    items = nf.parse_feed(RSS, "rss", CUTOFF)
    assert [i["headline"] for i in items] == ["Cat elected mayor of small town in Alaska", "Undated oddity"]
    assert items[0]["description"] == "The cat won 3 of 5 votes."
    assert items[0]["outlet"] == "AP" and items[1]["published"] is None


def test_parse_atom():
    items = nf.parse_feed(ATOM, "atom", CUTOFF)
    assert len(items) == 2 and items[0]["source"] == "http://r/1"


def test_sensitive_detection():
    assert nf.is_sensitive("Fatal crash kills three")
    assert nf.is_sensitive("Man sentenced after trial")
    assert not nf.is_sensitive("Cat elected mayor of small town")
    assert not nf.is_sensitive("Warship museum opens")  # 'war' must match whole words only


def test_same_story_and_cluster_coverage():
    items = nf.parse_feed(RSS, "rss", CUTOFF) + nf.parse_feed(ATOM, "atom", CUTOFF)
    groups = nf.cluster(items)
    cat = [g for g in groups if "cat" in g["best"]["headline"].lower()][0]
    assert cat["coverage"] == 2 and len(cat["items"]) == 2
    assert cat["best"]["description"] == "The cat won 3 of 5 votes."  # richest description wins


def test_pick_prefers_coverage_skips_sensitive_and_history():
    items = nf.parse_feed(RSS, "rss", CUTOFF) + nf.parse_feed(ATOM, "atom", CUTOFF)
    assert "cat" in nf.pick(items, rng=random.Random(1))["headline"].lower()  # most covered
    only_bad = [i for i in items if "crash" in i["headline"].lower()]
    assert nf.pick(only_bad, avoid_sensitive=True) is None
    assert nf.pick(only_bad, avoid_sensitive=False)["headline"].startswith("Fatal")
    posted = [{"headline": "Alaska town elects a cat as mayor"}]
    left = nf.pick(items, history=posted, avoid_sensitive=True, rng=random.Random(1))
    assert left is None or "cat" not in left["headline"].lower()


def test_history_roundtrip_and_expiry(tmp_path):
    p = str(tmp_path / "h.json")
    nf.remember("Old news", path=p, now=NOW - timedelta(days=30))
    nf.remember("Fresh news", path=p, now=NOW)
    assert [h["headline"] for h in nf.load_history(p, now=NOW)] == ["Fresh news"]
    assert nf.load_history(str(tmp_path / "missing.json")) == []


def test_ungrounded_numbers():
    src = "The cat won 3 of 5 votes in 2026."
    assert nf.ungrounded_numbers("The cat won 3 votes.", src) == []
    assert nf.ungrounded_numbers("The cat won 300 votes, 12 percent more.", src) == ["300", "12"]


def test_generate_funny_news_end_to_end_offline(monkeypatch, tmp_path):
    import engine.script_gen as sg

    class Resp:
        status_code = 200
        text = RSS.replace("Mon, 02 Nov 2026", datetime.now(timezone.utc).strftime("%a, %d %b %Y")).replace("Mon, 26 Oct 2026", "Mon, 01 Jan 2024")

    monkeypatch.setattr(sg.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(nf, "history_path", lambda: str(tmp_path / "hist.json"))
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])  # tie between equally covered stories -> first one
    answers = iter([
        json.dumps({"title": "x", "hook": "h", "story": "The cat won 300 votes in a landslide that stunned the whole town today.", "search_term": "cat"}),
        json.dumps({"title": "x", "hook": "h", "story": "The cat won 3 of 5 votes in a landslide that stunned the whole town today.", "search_term": "cat"}),
    ])
    prompts = []
    monkeypatch.setattr(sg, "get_llm_response", lambda prompt, **k: (prompts.append(prompt), next(answers))[1])
    out = sg.generate_funny_news("world", tone="serious")
    assert "3 of 5" in out["story"] and out["original_headline"].startswith("Cat elected")
    assert len(prompts) == 2 and "SOURCE SUMMARY" in prompts[0] and "3 of 5 votes" in prompts[0]
    assert nf.load_history(str(tmp_path / "hist.json"))[0]["headline"].startswith("Cat elected")
