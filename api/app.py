"""ShortsFlow REST API.

  POST /v1/shorts        generate a short from an idea (FACTS, EXPLAINER, WYR, ...)
  POST /v1/clips         clip a long video / YouTube link into shorts
  GET  /v1/jobs/{id}     status and result (add ?log=true for the log tail)
  GET  /v1/jobs/{id}/files/{name}   download a rendered video

Auth: set SHORTSFLOW_API_KEY and send `Authorization: Bearer <key>` (or `X-API-Key`).
Webhooks: pass `webhook_url` in a request; set SHORTSFLOW_WEBHOOK_SECRET to get an
`X-ShortsFlow-Signature: sha256=<hmac of body>` header.
"""
import hmac
import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.jobs import JobManager, public_view

app = FastAPI(title="ShortsFlow API", version="1.0.0",
              description="Self-hosted Opus Clip alternative. Submit a job, poll it or receive a webhook.")
manager = JobManager(max_concurrent=int(os.getenv("SHORTSFLOW_MAX_CONCURRENT", "1")),
                     webhook_secret=os.getenv("SHORTSFLOW_WEBHOOK_SECRET"))

CaptionStyle = Literal["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "AUTO", "RANDOM"]


def require_key(authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    expected = os.getenv("SHORTSFLOW_API_KEY")
    if not expected:
        return
    supplied = x_api_key or (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Invalid or missing API key")


class Common(BaseModel):
    caption_style: CaptionStyle = "HORMOZI"
    aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"
    use_remotion: bool = True
    llm_provider: str = "auto"
    webhook_url: Optional[str] = Field(None, description="POSTed once when the job finishes")


class ShortRequest(Common):
    mode: str = "FACTS"
    category: Optional[str] = None
    prompt: Optional[str] = None
    script: Optional[str] = None
    vibe: Literal["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"] = "suspense"


class ClipRequest(Common):
    source_video: str = Field(..., description="YouTube URL or a path on the server")
    clip_count: int = Field(3, ge=1, le=15)
    target_duration: int = Field(45, ge=10, le=180)
    layout: Literal["single", "split", "active"] = "single"
    smart_crop: bool = True
    tighten: bool = False
    find: Optional[str] = Field(None, description='Only clip moments matching this request, e.g. "where they discuss pricing"')


def _common_args(r: Common):
    args = ["--caption_style", r.caption_style, "--aspect_ratio", r.aspect_ratio, "--llm_provider", r.llm_provider]
    return args + (["--use_remotion"] if r.use_remotion else [])


def _accepted(job):
    return {"id": job["id"], "status": job["status"], "url": f"/v1/jobs/{job['id']}"}


@app.post("/v1/shorts", status_code=202, dependencies=[Depends(require_key)])
def create_short(r: ShortRequest):
    args = ["--mode", r.mode.upper(), "--vibe", r.vibe]
    for flag, value in (("--category", r.category), ("--prompt", r.prompt), ("--script", r.script)):
        if value:
            args += [flag, value]
    return _accepted(manager.submit(args + _common_args(r), r.webhook_url))


@app.post("/v1/clips", status_code=202, dependencies=[Depends(require_key)])
def create_clips(r: ClipRequest):
    args = ["--source_video", r.source_video, "--extract_mode", "shorts", "--clip_count", str(r.clip_count),
            "--target_duration", str(r.target_duration), "--layout", r.layout]
    args += [f for f, on in (("--smart_crop", r.smart_crop), ("--tighten", r.tighten)) if on]
    if r.find:
        args += ["--find", r.find]
    return _accepted(manager.submit(args + _common_args(r), r.webhook_url))


def _job_or_404(job_id):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return job


@app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_key)])
def get_job(job_id: str, log: bool = False):
    job = _job_or_404(job_id)
    view = public_view(job)
    if log:
        view["log"] = job["log"]
    return view


@app.get("/v1/jobs/{job_id}/files/{name}", dependencies=[Depends(require_key)])
def get_file(job_id: str, name: str):
    job = _job_or_404(job_id)
    for path in job["files"]:
        if os.path.basename(path) == name:
            return FileResponse(path, media_type="video/mp4", filename=name)
    raise HTTPException(404, "No such file for this job")


@app.get("/health")
def health():
    return {"ok": True}
