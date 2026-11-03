"""The folder ShortsFlow works in once installed with pip.

A git checkout is its own workspace. A pip install keeps its code in site-packages, but the pipeline expects
assets/, music/, remotion-video/ and a .env next to where it runs, so `shortsflow` creates a workspace
(default ~/shortsflow, or SHORTSFLOW_HOME) and copies those in from the wheel the first time.
"""
import os
import re
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


_PLACEHOLDER = re.compile(r"^(\s*)([A-Z][A-Z0-9_]*)\s*=\s*(your_\S*|\S*_here)\b(.*)$")


def comment_out_placeholders(env_path):
    """Turn `GEMINI_API_KEY=your_gemini_api_key_here` into a comment. A placeholder is not a key: loaded as one, every AI step
    retried it for minutes ("400 Bad Request") before falling back. Returns how many lines were changed. Safe to repeat."""
    if not os.path.exists(env_path):
        return 0
    with open(env_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    changed = 0
    for i, line in enumerate(lines):
        m = _PLACEHOLDER.match(line)
        if m:
            lines[i] = f"{m.group(1)}# {m.group(2)}={m.group(3)}{m.group(4)}"
            changed += 1
    if changed:
        with open(env_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    return changed


def bootstrap(home=None):
    """Create/refresh the workspace and return its path. Safe to call on every run."""
    home = home or resolve_home()
    os.makedirs(home, exist_ok=True)
    if not is_checkout():
        _copy_missing(BUNDLE, home)
        env, example = os.path.join(home, ".env"), os.path.join(home, "env.example")
        if not os.path.exists(env) and os.path.exists(example):
            shutil.copy2(example, env)
        comment_out_placeholders(env)   # new and existing workspaces: placeholder values must not count as keys
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
        ("FFmpeg", bool(shutil.which("ffmpeg")), "install FFmpeg (winget install Gyan.FFmpeg) or reinstall with the ShortsFlow installer"),
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
    checks.append(("An LLM key (Gemini/Groq/OpenAI/HF) or local Ollama", have_llm,
                   f"optional - clipping works without one; titles and idea-to-video modes need it. Easiest free option: get a key at console.groq.com and add GROQ_API_KEY=... to {os.path.join(home, '.env')}, "
                   "or install Ollama from ollama.com"))
    checks.append(("PEXELS_API_KEY (stock footage)", real(os.getenv("PEXELS_API_KEY")) or bool(keys.get("PEXELS_API_KEY")),
                   f"only for idea-to-video modes: free key at pexels.com/api, add PEXELS_API_KEY to {os.path.join(home, '.env')}"))
    return checks
