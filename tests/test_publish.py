import json
from datetime import datetime

import pytest

from engine import publish


def test_hashtags_strip_spaces_dedupe_and_limit():
    assert publish.hashtags(["AI tools", "ai tools", "#shorts", "!!"], limit=5) == "#AItools #shorts"
    assert len(publish.hashtags([f"t{i}" for i in range(20)]).split()) == 5


def test_schedule_slots():
    assert publish.schedule_slots(2) == [None, None]
    a, b, c = publish.schedule_slots(3, datetime(2026, 11, 2, 10, 0), 90)
    assert (b - a).total_seconds() == 5400 and c.hour == 13


def test_build_fields_platform_specific_captions():
    item = {"title": "Why prices doubled", "description": "d", "tags": ["economy", "prices"]}
    fields = dict(publish.build_fields(item, ["tiktok", "youtube"], "me", datetime(2026, 11, 2, 10), "Europe/Madrid"))
    assert fields["tiktok_title"] == "Why prices doubled #economy #prices"
    assert fields["youtube_title"] == "Why prices doubled"
    assert fields["scheduled_date"] == "2026-11-02T10:00:00" and fields["timezone"] == "Europe/Madrid"
    plats = [v for k, v in publish.build_fields(item, ["tiktok", "youtube"], "me") if k == "platform[]"]
    assert plats == ["tiktok", "youtube"]


class FakeResp:
    def __init__(self, status=202, body=None):
        self.status_code, self._body, self.text = status, body or {"success": True}, ""

    def json(self):
        return self._body


@pytest.fixture
def meta(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps([{"file": "a.mp4", "title": "A", "tags": []}, {"file": "missing.mp4", "title": "B"}]))
    return str(path)


def test_publish_all_posts_and_reports_missing_files(meta):
    sent = []

    def post(url, headers, data, files, timeout):
        sent.append((url, headers, dict(data)))
        return FakeResp()

    res = publish.publish_all(meta, ["tiktok"], datetime(2026, 11, 2, 10), 60, "UTC",
                              api_key="k", user="u", post=post)
    assert [r["ok"] for r in res] == [True, False]
    url, headers, data = sent[0]
    assert url == publish.API_URL and headers["Authorization"] == "Apikey k" and data["user"] == "u"


def test_publish_failure_is_reported(meta):
    res = publish.publish_all(meta, ["tiktok"], api_key="k", user="u",
                              post=lambda *a, **k: FakeResp(403, {"success": False, "error": "free plan"}))
    assert res[0]["ok"] is False


def test_requires_credentials_and_valid_platform(meta, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        publish.publish_all(meta, ["tiktok"])
    with pytest.raises(SystemExit):
        publish.publish_all(meta, ["myspace"], dry_run=True)


def test_dry_run_sends_nothing(meta):
    def post(*a, **k):
        raise AssertionError("must not post")

    res = publish.publish_all(meta, ["tiktok"], dry_run=True, post=post)
    assert res[0]["dry_run"] is True
