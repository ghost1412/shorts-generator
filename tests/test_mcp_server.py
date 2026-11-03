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
