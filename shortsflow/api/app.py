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
import ipaddress
import os
import socket
from urllib.parse import urlparse
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from shortsflow.api.jobs import JobManager, public_view

app = FastAPI(title="ShortsFlow API", version="1.0.0",
              description="Self-hosted Opus Clip alternative. Submit a job, poll it or receive a webhook.")
manager = JobManager(max_concurrent=int(os.getenv("SHORTSFLOW_MAX_CONCURRENT", "1")),
                     webhook_secret=os.getenv("SHORTSFLOW_WEBHOOK_SECRET"))

CaptionStyle = Literal["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR", "AUTO", "RANDOM"]


def require_key(authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    expected = os.getenv("SHORTSFLOW_API_KEY")
    if not expected:
        return
    supplied = x_api_key or (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(401, "Invalid or missing API key")


def _no_flag(v):
    """A user string starting with '-' could be read as a CLI flag by main.py."""
    if isinstance(v, str) and v.lstrip().startswith("-"):
        raise ValueError("must not start with '-'")
    return v


def _check_webhook(url):
    if url is None:
        return url
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("webhook_url must be an http(s) URL")
    if os.getenv("SHORTSFLOW_ALLOW_PRIVATE_WEBHOOKS") == "1":
        return url
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("webhook_url host does not resolve")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_unspecified or ip.is_multicast:
            raise ValueError("webhook_url must not point to a private address (set SHORTSFLOW_ALLOW_PRIVATE_WEBHOOKS=1 to allow)")
    return url


class Common(BaseModel):
    caption_style: CaptionStyle = "HORMOZI"
    aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"
    use_remotion: bool = True
    llm_provider: str = "auto"
    webhook_url: Optional[str] = Field(None, description="POSTed once when the job finishes")
    tts_provider: Literal["auto", "elevenlabs", "voicestudio", "edgetts", "local", "kokoro"] = "auto"

    @field_validator("webhook_url")
    @classmethod
    def _webhook_ok(cls, v):
        return _check_webhook(v)

    @field_validator("llm_provider")
    @classmethod
    def _provider_ok(cls, v):
        return _no_flag(v)


class ShortRequest(Common):
    mode: str = "FACTS"
    category: Optional[str] = None
    prompt: Optional[str] = None
    script: Optional[str] = None
    vibe: Literal["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"] = "suspense"

    @field_validator("mode", "category", "prompt", "script")
    @classmethod
    def _no_flag_ok(cls, v):
        return _no_flag(v)


class ClipRequest(Common):
    source_video: str = Field(..., description="YouTube URL or a path on the server")
    clip_count: int = Field(3, ge=1)
    target_duration: int = Field(45, ge=10, le=180)
    layout: Literal["single", "split", "active", "auto", "split_filler"] = "single"
    smart_crop: bool = True
    tighten: bool = False
    logo: Optional[str] = Field(None, description="Logo PNG path on the server")
    handle: Optional[str] = Field(None, description="@handle shown with the logo and on the end card")
    end_card: Optional[str] = Field(None, description="Closing end card text")
    find: Optional[str] = Field(None, description='Only clip moments matching this request, e.g. "where they discuss pricing"')

    @field_validator("source_video", "logo", "handle", "end_card", "find")
    @classmethod
    def _no_flag_ok(cls, v):
        return _no_flag(v)


def _common_args(r: Common):
    args = ["--caption_style", r.caption_style, "--aspect_ratio", r.aspect_ratio, "--llm_provider", r.llm_provider,
            "--tts_provider", r.tts_provider]
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
    for flag, value in (("--logo", r.logo), ("--handle", r.handle), ("--end_card", r.end_card)):
        if value:
            args += [flag, value]
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
