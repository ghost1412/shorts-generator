"""'Satisfying footage' split layout: the clip on top, looping gameplay/filler footage underneath (9:16).

Resolution order for the filler video (AGENTS.md fallback rules):
1. ``--filler_video PATH`` when it exists,
2. a random video from ``assets/backgrounds/local/`` (the user's own library),
3. a stock clip from Pexels (needs PEXELS_API_KEY),
4. nothing found -> the caller falls back to the normal single crop.
"""
import glob
import os
import random

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".m4v")
LOCAL_DIR = os.path.join("assets", "backgrounds", "local")
STOCK_QUERY = "oddly satisfying"


def find_local_filler(local_dir=LOCAL_DIR, rng=random):
    """A random video from the local background library, or None."""
    files = [p for p in glob.glob(os.path.join(local_dir, "*")) if p.lower().endswith(VIDEO_EXTS)]
    return rng.choice(files) if files else None


def download_stock_filler(output_path):
    """One Pexels 'satisfying' clip saved to output_path, or None when offline / no key / nothing found."""
    if not os.getenv("PEXELS_API_KEY"):
        return None
    try:
        from engine import media_gen
        media_gen.PEXELS_API_KEY = media_gen.PEXELS_API_KEY or os.getenv("PEXELS_API_KEY")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        got = media_gen.download_background_video("", fallback_query=STOCK_QUERY, output_path=output_path,
                                                  orientation="portrait", force_literal=True)
    except Exception as e:  # network errors, recursion on empty search results, ...
        print(f"[Warning] Could not download stock filler footage: {e}")
        return None
    return got if got and os.path.exists(got) and os.path.getsize(got) > 1000 else None


def resolve_filler_video(path=None, session_dir="sessions"):
    """Pick the filler footage per the order above; None when nothing is available."""
    if path:
        if os.path.isfile(path):
            return path
        print(f"[Warning] --filler_video '{path}' not found; trying the local library / stock footage.")
    local = find_local_filler()
    if local:
        print(f"[Log] Filler footage: {local}")
        return local
    stock = download_stock_filler(os.path.join(session_dir, "filler_stock.mp4"))
    if stock:
        print("[Log] Filler footage: Pexels stock clip")
    return stock


def build_filler_split_graph(top_chain, w=1080, h=1920, scaling_alg="lanczos"):
    """filter_complex for two inputs: [0:v] the clip, [1:v] the filler. Output label [v].

    ``top_chain`` is an optional comma-separated filter chain applied to the clip first (letterbox crop,
    colour grade, ...). Both halves are cover-cropped to w x h/2 and stacked.
    """
    half = h // 2
    pre = f"{top_chain}," if top_chain else ""
    return (
        f"[0:v]{pre}scale={w}:{half}:force_original_aspect_ratio=increase:flags={scaling_alg},"
        f"crop={w}:{half},setsar=1[top];"
        f"[1:v]scale={w}:{half}:force_original_aspect_ratio=increase:flags={scaling_alg},"
        f"crop={w}:{half},setsar=1,fps=30[bot];"
        f"[top][bot]vstack=inputs=2,format=yuv420p[v]"
    )
