import json
import os
import subprocess
import sys

import mcp_server
from shortsflow import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _talk(messages, cwd):
    """Send JSON-RPC lines to a fresh `python mcp_server.py` started from `cwd` and return the parsed replies."""
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    out = subprocess.run([sys.executable, os.path.join(ROOT, "mcp_server.py")], input=payload, capture_output=True, text=True,
                         encoding="utf-8", cwd=cwd, timeout=60).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip().startswith("{")]


def test_handshake_and_tool_list_work_from_any_working_directory(tmp_path):
    replies = _talk([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ], cwd=str(tmp_path))
    by_id = {r["id"]: r for r in replies if "id" in r}
    info = by_id[1]["result"]["serverInfo"]
    assert info["version"] == __version__                     # not a stale hard-coded number
    tools = {t["name"] for t in by_id[2]["result"]["tools"]}
    assert tools == {"generate_short", "extract_clips", "generate_social_package", "get_render_status", "list_supported_modes"}
    assert all(t["inputSchema"]["type"] == "object" for t in by_id[2]["result"]["tools"])


def test_render_jobs_run_main_py_by_absolute_path_in_the_repo(monkeypatch, tmp_path):
    """AI tools start the server from arbitrary folders; `python main.py` must not depend on the caller's cwd."""
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"], seen["cwd"] = cmd, kwargs.get("cwd")
        raise RuntimeError("stop here")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mcp_server.subprocess, "Popen", fake_popen)
    mcp_server.run_main_command("job-test", ["--mode", "FACTS"])
    assert os.path.isabs(seen["cmd"][1]) and seen["cmd"][1].endswith("main.py") and os.path.exists(seen["cmd"][1])
    assert os.path.abspath(seen["cwd"]) == ROOT
    assert "--mode" in seen["cmd"] and "--skip_upload" in seen["cmd"]


def test_a_minimal_container_still_answers_introspection_and_explains_rendering(tmp_path):
    """Dockerfile.mcp only copies mcp_server.py and shortsflow/__init__.py: it must start, list the tools, and fail a render politely."""
    import shutil
    import time
    (tmp_path / "shortsflow").mkdir()
    shutil.copy(os.path.join(ROOT, "mcp_server.py"), tmp_path / "mcp_server.py")
    shutil.copy(os.path.join(ROOT, "shortsflow", "__init__.py"), tmp_path / "shortsflow" / "__init__.py")
    NL = chr(10)
    p = subprocess.Popen([sys.executable, "-I", "mcp_server.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", cwd=str(tmp_path))

    def send(obj):
        p.stdin.write(json.dumps(obj) + NL)
        p.stdin.flush()

    def recv():
        end = time.time() + 30
        while time.time() < end:
            line = p.stdout.readline()
            if line.strip():
                return json.loads(line)
        raise AssertionError("no reply from the MCP server")

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                                                              "clientInfo": {"name": "t", "version": "1"}}})
        assert recv()["result"]["serverInfo"]["version"] == __version__
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert len(recv()["result"]["tools"]) == 5
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "generate_short", "arguments": {"mode": "FACTS"}}})
        job_id = json.loads(recv()["result"]["content"][0]["text"])["job_id"]
        time.sleep(1.5)
        send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_render_status", "arguments": {"job_id": job_id}}})
        status = json.loads(recv()["result"]["content"][0]["text"])
        assert status["status"] == "failed" and "full ShortsFlow checkout" in status["error"]
    finally:
        p.terminate()
