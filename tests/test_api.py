import time

import pytest
from fastapi.testclient import TestClient

from shortsflow.api import app as api_app
from shortsflow.api import jobs as api_jobs


@pytest.fixture
def client(monkeypatch, tmp_path):
    video = tmp_path / "out.mp4"
    video.write_bytes(b"fake-mp4")
    calls = []

    def fake_run(self, job):
        calls.append(job["args"])
        job.update(status="succeeded", files=[str(video)], finished_at=time.time())

    monkeypatch.setattr(api_jobs.JobManager, "_run", fake_run)
    monkeypatch.delenv("SHORTSFLOW_API_KEY", raising=False)
    c = TestClient(api_app.app)
    c.calls = calls
    return c


def _wait(client, job_id):
    for _ in range(50):
        body = client.get(f"/v1/jobs/{job_id}").json()
        if body["status"] in ("succeeded", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError("job never finished")


def test_create_short_builds_cli_args(client):
    r = client.post("/v1/shorts", json={"mode": "facts", "category": "space", "caption_style": "BOUNCE"})
    assert r.status_code == 202
    body = _wait(client, r.json()["id"])
    assert body["status"] == "succeeded"
    args = client.calls[0]
    assert args[:2] == ["--mode", "FACTS"]
    assert "--category" in args and "space" in args
    assert "BOUNCE" in args and "--use_remotion" in args


def test_create_clips_and_download(client):
    r = client.post("/v1/clips", json={"source_video": "https://youtu.be/x", "layout": "active", "clip_count": 2})
    job = _wait(client, r.json()["id"])
    assert "--layout" in client.calls[0] and "active" in client.calls[0]
    f = job["files"][0]
    assert client.get(f["url"]).content == b"fake-mp4"


def test_validation_rejects_bad_layout(client):
    r = client.post("/v1/clips", json={"source_video": "x", "layout": "nope"})
    assert r.status_code == 422


def test_unknown_job_and_file(client):
    assert client.get("/v1/jobs/missing").status_code == 404
    job_id = client.post("/v1/shorts", json={}).json()["id"]
    _wait(client, job_id)
    assert client.get(f"/v1/jobs/{job_id}/files/..%2Fsecret.mp4").status_code == 404


def test_api_key_enforced(client, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_API_KEY", "s3cret")
    assert client.post("/v1/shorts", json={}).status_code == 401
    ok = client.post("/v1/shorts", json={}, headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 202


def test_api_key_with_non_ascii_header_is_401_not_500(client, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_API_KEY", "s3cret")
    r = client.post("/v1/shorts", json={}, headers={"X-API-Key": "sécret".encode("latin-1")})
    assert r.status_code == 401


def test_webhook_signature():
    body = b'{"id":"a"}'
    sig = api_jobs.sign("k", body)
    assert sig.startswith("sha256=") and len(sig) == 71
    assert sig == api_jobs.sign("k", body) != api_jobs.sign("other", body)


def test_brand_find_and_tts_fields_reach_the_cli(client):
    r = client.post("/v1/clips", json={"source_video": "x", "find": "pricing", "logo": "l.png",
                                       "handle": "@me", "end_card": "Follow", "tts_provider": "kokoro"})
    _wait(client, r.json()["id"])
    args = client.calls[-1]
    for pair in (("--find", "pricing"), ("--logo", "l.png"), ("--handle", "@me"),
                 ("--end_card", "Follow"), ("--tts_provider", "kokoro")):
        assert args[args.index(pair[0]) + 1] == pair[1]


def test_webhook_url_validation(client, monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_ALLOW_PRIVATE_WEBHOOKS", raising=False)
    for bad in ("ftp://example.com/x", "file:///etc/passwd", "http://127.0.0.1:9/x", "http://localhost/x",
                "http://169.254.169.254/latest", "http://10.0.0.5/x"):
        r = client.post("/v1/shorts", json={"webhook_url": bad})
        assert r.status_code == 422, bad
    monkeypatch.setenv("SHORTSFLOW_ALLOW_PRIVATE_WEBHOOKS", "1")
    assert client.post("/v1/shorts", json={"webhook_url": "http://127.0.0.1:9/x"}).status_code == 202


def test_flag_like_strings_rejected(client):
    for field in ("category", "prompt", "script", "mode"):
        assert client.post("/v1/shorts", json={field: "--use_audio_detect"}).status_code == 422, field
    for field in ("source_video", "find", "handle", "end_card", "logo"):
        body = {"source_video": "x", field: "-rf"}
        assert client.post("/v1/clips", json=body).status_code == 422, field


def test_clip_count_is_not_capped(client):
    r = client.post("/v1/clips", json={"source_video": "https://youtu.be/x", "clip_count": 60})
    assert r.status_code == 202 and "60" in client.calls[-1]
    assert client.post("/v1/clips", json={"source_video": "x", "clip_count": 0}).status_code == 422
