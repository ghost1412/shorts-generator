import pytest

flask = pytest.importorskip("flask")

import server  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    started = []
    monkeypatch.setattr(server.threading, "Thread", lambda target, args: type("T", (), {"start": lambda self: started.append(args)})())
    monkeypatch.delenv("SHORTSFLOW_API_KEY", raising=False)
    c = server.app.test_client()
    c.started = started
    return c


def test_open_when_no_key_and_health_always_open(client, monkeypatch):
    assert client.post("/render", json={"mode": "FACTS"}).status_code == 202
    monkeypatch.setenv("SHORTSFLOW_API_KEY", "k")
    assert client.get("/health").status_code == 200


def test_key_required_for_render_and_kids_image(client, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_API_KEY", "secret")
    assert client.post("/render", json={}).status_code == 401
    assert client.post("/kids-image", json={"prompt": "x"}).status_code == 401
    assert client.post("/render", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/render", json={}, headers={"Authorization": "Bearer secret"}).status_code == 202
    assert client.post("/render", json={}, headers={"X-API-Key": "secret"}).status_code == 202


def test_flag_like_values_rejected(client):
    r = client.post("/render", json={"sourceVideoUrl": "--help"})
    assert r.status_code == 400
    assert not client.started
