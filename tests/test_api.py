import time

import pytest
from fastapi.testclient import TestClient

from api import app as api_app
from api import jobs as api_jobs


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


def test_webhook_signature():
    body = b'{"id":"a"}'
    sig = api_jobs.sign("k", body)
    assert sig.startswith("sha256=") and len(sig) == 71
    assert sig == api_jobs.sign("k", body) != api_jobs.sign("other", body)
