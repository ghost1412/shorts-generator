"""Where ShortsFlow keeps its working files.

From a git checkout this is the repo root. After `pip install shortsflow` it is the workspace folder
(SHORTSFLOW_HOME, set by the `shortsflow` command), which holds assets/, music/, remotion-video/ and .env.
"""
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_root():
    return os.environ.get("SHORTSFLOW_HOME") or _REPO_ROOT
