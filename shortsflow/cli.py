"""`shortsflow` command.

    shortsflow init                     create the workspace, install Remotion
    shortsflow doctor                   check FFmpeg / Node / API keys
    shortsflow clip VIDEO_OR_URL        cut a long video into vertical shorts (no API key needed; --count N, --captions)
    shortsflow clip A.mp4 B.mp4 | FOLDER   several videos in turn, with a summary table; --watch FOLDER clips new files as they appear
    shortsflow webui [--open]           browser app: paste a link or upload a video, press one button (needs `pip install "shortsflow[webui]"`)
    shortsflow api                      REST API on :8080 (SHORTSFLOW_API_KEY recommended)
    shortsflow --source_video URL ...   anything else goes to the pipeline (same flags as `python main.py`)
"""
import os
import runpy
import sys

from shortsflow import __version__, workspace

USAGE = __doc__


def _init(home):
    print(f"[shortsflow] Workspace: {home}")
    ok = workspace.install_remotion(home)
    print("[shortsflow] Remotion ready." if ok else
          "[shortsflow] Remotion not installed (needs Node 18+ and npm). Captions need it; plain clips do not.")
    print(f"[shortsflow] Put your keys in {os.path.join(home, '.env')}, then run `shortsflow doctor`.")


def _doctor(home):
    bad = 0
    for label, ok, hint in workspace.doctor(home):
        print(f"  {'OK ' if ok else 'FIX'}  {label}" + ("" if ok else f"  ->  {hint}"))
        bad += not ok
    print("\nAll good." if not bad else f"\n{bad} item(s) to fix.")
    return 1 if bad else 0


def _clip_parser():
    import argparse
    p = argparse.ArgumentParser(prog="shortsflow clip", description="Cut long videos (files, a folder or links) into vertical shorts.")
    p.add_argument("video", nargs="*", help="video file(s), a folder of videos, or YouTube/other link(s)")
    p.add_argument("--count", type=int, default=3, help="how many shorts per video (default 3)")
    p.add_argument("--captions", action="store_true", help="burn in animated captions (needs Node.js; run `shortsflow init` once)")
    p.add_argument("--watch", metavar="FOLDER", help="keep watching this folder and clip every new video once (Ctrl+C to stop)")
    p.add_argument("--interval", type=int, default=30, help="seconds between checks with --watch (default 30)")
    return p


def _clip_common(ns, extra):
    flags = ["--extract_mode", "shorts", "--clip_count", str(ns.count), "--smart_crop", "--tighten", "--skip-upload"]
    if ns.captions:
        flags += ["--use_remotion", "--caption_style", "HORMOZI"]
    return flags + extra


def clip_args(rest):
    """`shortsflow clip VIDEO [--count N] [--captions]` -> the full pipeline flags. Plain clipping needs no API key."""
    p = _clip_parser()
    ns, extra = p.parse_known_args(rest)
    if len(ns.video) != 1:
        p.error("give one video here (use `shortsflow clip A.mp4 B.mp4`, a folder, or --watch FOLDER for several)")
    return ["--source_video", ns.video[0], *_clip_common(ns, extra)]


def clip_plan(rest, base_dir=None):
    """Work out what `shortsflow clip ...` should do. Returns
    {'kind': 'single'|'batch'|'watch', 'flags': pipeline flags (single) or common flags (batch/watch),
     'sources': [...], 'problems': [...], 'folder': str|None, 'interval': int}.
    Paths are resolved against `base_dir` (where the user ran the command; the pipeline itself runs in the workspace)."""
    p = _clip_parser()
    ns, extra = p.parse_known_args(rest)

    def resolve(item):
        from shortsflow.batch import is_url
        if is_url(item) or os.path.isabs(item) or not base_dir:
            return item
        return os.path.abspath(os.path.join(base_dir, item))

    inputs = [resolve(v) for v in ns.video]
    common = _clip_common(ns, extra)
    if ns.watch:
        folder = resolve(ns.watch)
        return {"kind": "watch", "flags": common, "sources": [], "problems": [] if os.path.isdir(folder)
                else [f"The folder '{ns.watch}' was not found."], "folder": folder, "interval": max(5, ns.interval)}
    if not inputs:
        p.error("give a video file, a folder, a link, or --watch FOLDER")
    if len(inputs) == 1 and not os.path.isdir(inputs[0]):
        return {"kind": "single", "flags": ["--source_video", inputs[0], *common], "sources": inputs, "problems": [],
                "folder": None, "interval": 0}
    from shortsflow.batch import collect_videos
    sources, problems = collect_videos(inputs)
    return {"kind": "batch", "flags": common, "sources": sources, "problems": problems, "folder": None, "interval": 0}


def _clip_many(plan):
    """Batch / watch: each video is its own pipeline run; ends with a summary table. Returns the exit code."""
    from shortsflow import batch
    for msg in plan["problems"]:
        print(f"[shortsflow] {msg}")
    if plan["kind"] == "watch":
        if plan["problems"]:
            return 2
        batch.watch(plan["folder"], plan["flags"], plan["interval"])
        return 0
    if not plan["sources"]:
        print("[shortsflow] Nothing to clip.")
        return 2
    print(f"[shortsflow] {len(plan['sources'])} video(s) to clip, one after the other. Clipping needs no API key.")
    results = batch.run_batch(plan["sources"], plan["flags"])
    print("\n" + batch.summary_table(results))
    return 1 if any(r["status"] == "failed" for r in results) else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-V", "--version", "version"):
        print(f"shortsflow {__version__}")
        return
    if not argv or argv[0] in ("-h", "--help") and len(argv) == 1:
        print(USAGE)
        print("Pipeline flags: `shortsflow run --help`")
        return

    start_dir = os.getcwd()  # the pipeline runs in the workspace; `clip` paths are relative to here
    home = workspace.bootstrap()
    from shortsflow.ffmpeg_path import ensure_ffmpeg_on_path
    ensure_ffmpeg_on_path(home)   # Whisper & co. start `ffmpeg` by name; a clean PC has none on its PATH
    os.chdir(home)  # the pipeline reads/writes assets/, sessions/ and renders relative to here
    if home not in sys.path:
        sys.path.insert(0, home)
    cmd = argv[0]
    if cmd == "init":
        return _init(home)
    if cmd == "doctor":
        sys.exit(_doctor(home))
    if cmd == "webui":
        try:
            import gradio  # noqa: F401
        except ImportError:
            print('[shortsflow] The browser app needs one more package. Run:  pip install "shortsflow[webui]"')
            sys.exit(1)
        try:
            import webui  # a git checkout keeps it next to main.py
        except ImportError:
            from shortsflow import webui
        return webui.main(argv[1:])
    if cmd == "api":
        import uvicorn
        uvicorn.run("shortsflow.api.app:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8080")))
        return
    if cmd == "clip":
        if len(argv) < 2 or argv[1] in ("-h", "--help"):
            clip_args(["-h"])
        plan = clip_plan(argv[1:], base_dir=start_dir)
        if plan["kind"] != "single":
            sys.exit(_clip_many(plan))
        argv = plan["flags"]
        print("[shortsflow] Clipping needs no API key. Titles/descriptions are written when an AI key or Ollama is set up "
              "(`shortsflow doctor` shows what you have).")
    elif cmd == "run":
        argv = argv[1:]
    if not workspace.is_checkout() and "remotion-video" and not os.path.isdir(os.path.join(home, "remotion-video", "node_modules")) \
            and "--use_remotion" in argv:
        workspace.install_remotion(home)
    sys.argv = ["shortsflow", *argv]
    print(f"[shortsflow] Workspace: {home}  (renders land in {home} and {os.path.join(home, 'sessions')})")
    runpy.run_module("shortsflow._main", run_name="__main__")


if __name__ == "__main__":
    main()
