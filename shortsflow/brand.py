"""The user's saved brand kit (logo, @handle, end card, colour), stored in the workspace and handed to the pipeline as `--brand`.

Files: <workspace>/brand/brand.json and <workspace>/brand/logo.png. The pipeline (engine/branding.py) reads that JSON.
"""
import json
import os
import re

POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
DEFAULT_COLOR = "#FFEA00"
MAX_LOGO_SIDE = 1024


def _dir(home):
    return os.path.join(home, "brand")


def _json_path(home):
    return os.path.join(_dir(home), "brand.json")


def load(home):
    """Saved brand as a dict (handle, end_card, color, logo_position, logo = absolute path or None); {} when none is saved."""
    try:
        with open(_json_path(home), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    logo = data.get("logo")
    logo = os.path.join(_dir(home), logo) if logo and os.path.exists(os.path.join(_dir(home), logo)) else None
    return {"handle": data.get("handle") or "", "end_card": data.get("end_card") or "", "color": data.get("color") or DEFAULT_COLOR,
            "logo_position": data.get("logo_position") or "top-right", "logo": logo}


def clean_handle(text):
    """'@name' from user input, or '' when empty. Raises ValueError for characters a handle cannot have."""
    text = (text or "").strip().lstrip("@").strip()
    if not text:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", text):
        raise ValueError("A handle can only use letters, numbers, dots and underscores (up to 30 characters).")
    return "@" + text


def save(home, logo_path=None, handle="", end_card="", color=DEFAULT_COLOR, position="top-right"):
    """Validate and store the brand. Returns a message for the user; raises ValueError with a plain-language reason."""
    handle = clean_handle(handle)
    end_card = (end_card or "").strip()
    if len(end_card) > 60:
        raise ValueError("The end card text is too long (60 characters at most).")
    color = (color or DEFAULT_COLOR).strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        raise ValueError("The colour must look like #FFEA00.")
    if position not in POSITIONS:
        raise ValueError("Pick a logo position from the list.")
    os.makedirs(_dir(home), exist_ok=True)

    logo_name = None
    if logo_path:
        try:
            from PIL import Image
            with Image.open(logo_path) as im:
                im.load()
                im = im.convert("RGBA")
                im.thumbnail((MAX_LOGO_SIDE, MAX_LOGO_SIDE))
                im.save(os.path.join(_dir(home), "logo.png"), format="PNG")
            logo_name = "logo.png"
        except Exception:
            raise ValueError("That file could not be read as an image. Use a PNG or JPG logo.")
    elif os.path.exists(os.path.join(_dir(home), "logo.png")):
        logo_name = "logo.png"      # keep the logo saved earlier

    if not (logo_name or handle or end_card):
        raise ValueError("Add at least a logo, a handle or end-card text.")
    data = {"logo": logo_name, "logo_position": position, "handle": handle or None, "end_card": end_card or None, "color": color}
    with open(_json_path(home), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    parts = [p for p, on in (("logo", logo_name), ("handle " + handle, handle), ("end card", end_card)) if on]
    return "Saved your brand (" + ", ".join(parts) + "). It is added to every short you make while the box is ticked."


def clear(home):
    """Delete the saved brand."""
    for name in ("brand.json", "logo.png"):
        path = os.path.join(_dir(home), name)
        if os.path.exists(path):
            os.remove(path)


def cli_args(home):
    """Pipeline arguments that apply the saved brand ([] when none is saved)."""
    return ["--brand", _json_path(home)] if load(home) else []
