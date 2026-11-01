"""The folder ShortsFlow works in once installed with pip.

A git checkout is its own workspace. A pip install keeps its code in site-packages, but the pipeline expects
assets/, music/, remotion-video/ and a .env next to where it runs, so `shortsflow` creates a workspace
(default ~/shortsflow, or SHORTSFLOW_HOME) and copies those in from the wheel the first time.
"""
import os
import shutil
import subprocess

BUNDLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bundle")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_checkout():
    """True when running from a git checkout (no bundled data; the repo itself is the workspace)."""
    return not os.path.isdir(BUNDLE)


def resolve_home():
    if os.environ.get("SHORTSFLOW_HOME"):
        return os.path.abspath(os.path.expanduser(os.environ["SHORTSFLOW_HOME"]))
    if is_checkout():
        return REPO_ROOT
    return os.path.join(os.path.expanduser("~"), "shortsflow")


def _copy_missing(src, dst):
    """Copy files from src into dst without overwriting anything the user already has there."""
    for folder, _, files in os.walk(src):
        target = os.path.join(dst, os.path.relpath(folder, src))
        os.makedirs(target, exist_ok=True)
        for name in files:
            out = os.path.join(target, name)
            if not os.path.exists(out):
                shutil.copy2(os.path.join(folder, name), out)


def bootstrap(home=None):
    """Create/refresh the workspace and return its path. Safe to call on every run."""
    home = home or resolve_home()
    os.makedirs(home, exist_ok=True)
    if not is_checkout():
        _copy_missing(BUNDLE, home)
        env, example = os.path.join(home, ".env"), os.path.join(home, "env.example")
        if not os.path.exists(env) and os.path.exists(example):
            shutil.copy2(example, env)
    os.environ["SHORTSFLOW_HOME"] = home
    return home


def install_remotion(home):
    """npm install for the Remotion renderer. Returns True on success."""
    remotion = os.path.join(home, "remotion-video")
    if os.path.isdir(os.path.join(remotion, "node_modules")):
        return True
    npm = shutil.which("npm")
    if not npm or not os.path.isdir(remotion):
        return False
    print("[shortsflow] Installing Remotion (npm install, one-time, ~1-2 min)...")
    cmd = [npm, "ci" if os.path.exists(os.path.join(remotion, "package-lock.json")) else "install"]
    return subprocess.run(cmd, cwd=remotion).returncode == 0


def doctor(home):
    """[(label, ok, hint)] for everything the pipeline needs."""
    import importlib.util

    def has(mod):
        return importlib.util.find_spec(mod) is not None

    checks = [
        ("FFmpeg", bool(shutil.which("ffmpeg")) or has("imageio_ffmpeg"), "install FFmpeg or `pip install imageio-ffmpeg`"),
        ("Node.js (Remotion captions)", bool(shutil.which("node")), "install Node 18+ from nodejs.org"),
        ("Remotion installed", os.path.isdir(os.path.join(home, "remotion-video", "node_modules")), "run `shortsflow init`"),
        ("Clipping extras (Whisper, OpenCV)", has("stable_whisper") and has("cv2"), "pip install 'shortsflow[clip]'"),
        ("Local voice (Kokoro)", has("kokoro_onnx"), "pip install 'shortsflow[local-voice]' (optional)"),
    ]
    from dotenv import dotenv_values

    def real(value):  # env.example ships placeholders like your_gemini_key_here
        return bool(value) and "your_" not in value and not value.endswith("_here")

    keys = {k: v for k, v in dotenv_values(os.path.join(home, ".env")).items() if real(v)}
    have_llm = any(real(os.getenv(k)) or keys.get(k) for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "HF_API_KEY"))
    checks.append(("An LLM key (Gemini/Groq/OpenAI/HF) or local Ollama", have_llm, f"add GEMINI_API_KEY to {os.path.join(home, '.env')}"))
    checks.append(("PEXELS_API_KEY (stock footage)", real(os.getenv("PEXELS_API_KEY")) or bool(keys.get("PEXELS_API_KEY")),
                   f"add PEXELS_API_KEY to {os.path.join(home, '.env')} (free)"))
    return checks
