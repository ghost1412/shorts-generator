"""In-process job queue: runs the shortsflow pipeline as a subprocess, one job per render, bounded concurrency."""
import glob
import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

from engine.paths import project_root

LOG_TAIL = 20000


def _snapshot_videos():
    """Rendered .mp4 files main.py may write (workspace root and sessions/)."""
    files = {}
    for pattern in (os.path.join(project_root(), "*.mp4"), os.path.join(project_root(), "sessions*", "**", "*.mp4")):
        for path in glob.glob(pattern, recursive=True):
            if "TEMP_MPY" in path or os.path.basename(path).startswith(("preview_", "scene_clip_", "temp_")):
                continue
            files[path] = os.path.getmtime(path)
    return files


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class JobManager:
    """Output files are found by diffing the file system, so keep max_concurrent=1 unless jobs
    never overlap in time; with higher values a job may report another job's video."""

    def __init__(self, max_concurrent=1, webhook_secret=None):
        self.jobs = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=max_concurrent)
        self.webhook_secret = webhook_secret

    def submit(self, args, webhook_url=None):
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "status": "queued", "created_at": time.time(), "args": args,
               "files": [], "log": "", "returncode": None, "webhook_url": webhook_url}
        with self.lock:
            self.jobs[job_id] = job
        self.pool.submit(self._run, job)
        return job

    def get(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def _run(self, job):
        job["status"] = "running"
        before = _snapshot_videos()
        out_json = os.path.join(project_root(), f"api_job_{job['id']}.json")
        cmd = [sys.executable, "-m", "shortsflow", *job["args"], "--skip-upload", "--output_json", out_json]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        try:
            proc = subprocess.Popen(cmd, cwd=project_root(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", env=env)
            for line in proc.stdout:
                job["log"] = (job["log"] + line)[-LOG_TAIL:]
            proc.wait()
            job["returncode"] = proc.returncode
            after = _snapshot_videos()
            job["files"] = sorted(p for p, m in after.items() if p not in before or m > before[p])
            if os.path.exists(out_json):
                try:
                    with open(out_json, encoding="utf-8") as f:
                        job["result"] = json.load(f)
                except (OSError, ValueError):
                    pass
                os.remove(out_json)
            ok = proc.returncode == 0 and job["files"]
            job["status"] = "succeeded" if ok else "failed"
        except Exception as e:  # surface any launch error on the job
            job["status"] = "failed"
            job["log"] += f"\n{e}"
        job["finished_at"] = time.time()
        self._notify(job)

    def _notify(self, job):
        if not job.get("webhook_url"):
            return
        body = json.dumps(public_view(job)).encode()
        headers = {"Content-Type": "application/json"}
        if self.webhook_secret:
            headers["X-ShortsFlow-Signature"] = sign(self.webhook_secret, body)
        for attempt in range(3):
            try:
                requests.post(job["webhook_url"], data=body, headers=headers, timeout=10).raise_for_status()
                return
            except requests.RequestException:
                time.sleep(2 ** attempt)


def public_view(job):
    names = [os.path.basename(p) for p in job["files"]]
    view = {k: job.get(k) for k in ("id", "status", "created_at", "finished_at", "returncode", "result")}
    view["files"] = [{"name": n, "url": f"/v1/jobs/{job['id']}/files/{n}"} for n in names]
    return view
