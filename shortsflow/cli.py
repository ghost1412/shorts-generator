"""`shortsflow` command.

    shortsflow init                     create the workspace, install Remotion
    shortsflow doctor                   check FFmpeg / Node / API keys
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-V", "--version", "version"):
        print(f"shortsflow {__version__}")
        return
    if not argv or argv[0] in ("-h", "--help") and len(argv) == 1:
        print(USAGE)
        print("Pipeline flags: `shortsflow run --help`")
        return

    home = workspace.bootstrap()
    os.chdir(home)  # the pipeline reads/writes assets/, sessions/ and renders relative to here
    if home not in sys.path:
        sys.path.insert(0, home)
    cmd = argv[0]
    if cmd == "init":
        return _init(home)
    if cmd == "doctor":
        sys.exit(_doctor(home))
    if cmd == "api":
        import uvicorn
        uvicorn.run("shortsflow.api.app:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8080")))
        return
    if cmd == "run":
        argv = argv[1:]
    if not workspace.is_checkout() and "remotion-video" and not os.path.isdir(os.path.join(home, "remotion-video", "node_modules")) \
            and "--use_remotion" in argv:
        workspace.install_remotion(home)
    sys.argv = ["shortsflow", *argv]
    print(f"[shortsflow] Workspace: {home}  (renders land in {home} and {os.path.join(home, 'sessions')})")
    runpy.run_module("shortsflow._main", run_name="__main__")


if __name__ == "__main__":
    main()
