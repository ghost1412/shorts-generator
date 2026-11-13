"""Visual templates (--visual_template): a designed skin drawn over the picture by the animated renderer (remotion-video/src/visualTemplates.tsx).

The command line (or a re-render) sets three environment variables; the renderer turns them into props. Text slots are optional and only what
the user typed is ever drawn: nothing is made up.
"""
import json
import os
import re

from engine.auto_edit import ANIMATIONS, ANIMATION_NAMES, VISUAL_TEMPLATE_NAMES, VISUAL_TEMPLATES

TEXT_KEYS = ("show", "speaker", "role", "handle", "headline", "label", "cta")
MAX_TEXT = 80
ENV_NAME, ENV_TEXT, ENV_ACCENT = "SHORTSFLOW_VISUAL_TEMPLATE", "SHORTSFLOW_TEMPLATE_TEXT", "SHORTSFLOW_TEMPLATE_ACCENT"
ENV_INTRO, ENV_OUTRO, ENV_ANIM_COLOR = "SHORTSFLOW_INTRO_ANIM", "SHORTSFLOW_OUTRO_ANIM", "SHORTSFLOW_ANIM_COLOR"
ALL_ENV = (ENV_NAME, ENV_TEXT, ENV_ACCENT, ENV_INTRO, ENV_OUTRO, ENV_ANIM_COLOR)


def parse_text(items):
    """["speaker=Alex Morgan", "role=Host"] -> {"speaker": "Alex Morgan", "role": "Host"}. Raises ValueError on a bad item or an unknown slot."""
    out = {}
    for item in items or []:
        key, sep, value = str(item).partition("=")
        key, value = key.strip().lower(), " ".join(value.split())
        if not sep or key not in TEXT_KEYS:
            raise ValueError(f"--template_text needs KEY=VALUE with KEY one of: {', '.join(TEXT_KEYS)} (got {item!r})")
        if value:
            out[key] = value[:MAX_TEXT]
    return out


def normalize_accent(value):
    v = str(value or "").strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return "#" + v.upper() if re.fullmatch(r"[0-9a-fA-F]{6}", v) else None


def set_env(name, text=None, accent=None, environ=None):
    """Export the choice for the renderer (and for a re-render). An empty name clears all three."""
    environ = os.environ if environ is None else environ
    if not name:
        for k in (ENV_NAME, ENV_TEXT, ENV_ACCENT):
            environ.pop(k, None)
        return
    if name not in VISUAL_TEMPLATES:
        raise ValueError(f"Unknown visual template {name!r}. Choose one of: {', '.join(VISUAL_TEMPLATE_NAMES)}")
    environ[ENV_NAME] = name
    environ[ENV_TEXT] = json.dumps(text or {}, ensure_ascii=False)
    colour = normalize_accent(accent)
    if colour:
        environ[ENV_ACCENT] = colour
    else:
        environ.pop(ENV_ACCENT, None)


def set_animation_env(intro=None, outro=None, color=None, environ=None):
    """Export the intro / outro transitions (independent of the visual template). Empty values clear them."""
    environ = os.environ if environ is None else environ
    for key, value in ((ENV_INTRO, intro), (ENV_OUTRO, outro)):
        if value and value not in ANIMATIONS:
            raise ValueError(f"Unknown transition {value!r}. Choose one of: {', '.join(ANIMATION_NAMES)}")
        if value:
            environ[key] = value
        else:
            environ.pop(key, None)
    colour = normalize_accent(color)
    if colour and (intro or outro):
        environ[ENV_ANIM_COLOR] = colour
    else:
        environ.pop(ENV_ANIM_COLOR, None)


def props_from_env(environ=None):
    """The Remotion props for the chosen template and transitions ({} when none is chosen)."""
    environ = os.environ if environ is None else environ
    props = {}
    for env_key, prop in ((ENV_INTRO, "introAnimation"), (ENV_OUTRO, "outroAnimation")):
        if environ.get(env_key) in ANIMATIONS:
            props[prop] = environ[env_key]
    if props and normalize_accent(environ.get(ENV_ANIM_COLOR)):
        props["animationColor"] = normalize_accent(environ.get(ENV_ANIM_COLOR))
    name = environ.get(ENV_NAME, "")
    if name not in VISUAL_TEMPLATES:
        return props
    props["visualTemplate"] = name
    try:
        text = json.loads(environ.get(ENV_TEXT) or "{}")
    except ValueError:
        text = {}
    text = {k: str(v)[:MAX_TEXT] for k, v in (text if isinstance(text, dict) else {}).items() if k in TEXT_KEYS and str(v).strip()}
    if text:
        props["templateText"] = text
    colour = normalize_accent(environ.get(ENV_ACCENT))
    if colour:
        props["templateAccent"] = colour
    return props
