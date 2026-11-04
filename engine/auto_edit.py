"""Auto-edit director: one choice ("podcast", "hype", ...) that edits a short the way an editor would.

ShortsFlow already has the pieces of an edit: pause and filler cuts, punch-in zooms, B-roll cutaways, animated captions, a hook
title, a cold open, colour grades, audio clean-up. The director decides which of them to use and how strongly, from a *preset*
(what kind of video this is) and a *strength* (subtle / medium / hyped), applies them through the normal pipeline, adds the one thing
that was missing, sound effects under the edits, and writes down what it did (`edit_plan.json`, plus a one-line summary on each
review card) so nothing is a black box.

`apply_preset` only turns things ON or picks a style; it never overrides what the user asked for explicitly on the command line.
"""
import json
import os

PRESETS = {
    "podcast": {
        "label": "Podcast / interview", "about": "Clean and calm: pauses and ums cut, clear subtitle bar, a teaser opening, gentle zooms.",
        "tighten": True, "remove_fillers": True, "clean_audio": True, "caption_style": "BAR", "caption_emoji": False,
        "hook_overlay": True, "cold_open": True, "auto_zoom": True, "broll": False, "video_filter": None,
        "sfx": {"zoom": None, "broll": "whoosh", "cut": "whoosh"},
    },
    "hype": {
        "label": "Hype / gaming / reaction", "about": "Fast and loud: karaoke captions with emoji, frequent zooms, cutaways, a teaser, punchy colour.",
        "tighten": True, "remove_fillers": True, "clean_audio": True, "caption_style": "KARAOKE", "caption_emoji": True,
        "hook_overlay": True, "cold_open": True, "auto_zoom": True, "broll": True, "video_filter": "vibrant_action",
        "sfx": {"zoom": "pop", "broll": "whoosh", "cut": "hit"},
    },
    "educational": {
        "label": "Educational / explainer", "about": "Clear and focused: subtitle bar, stock cutaways for the things named, zooms on numbers, no teaser.",
        "tighten": True, "remove_fillers": True, "clean_audio": True, "caption_style": "BAR", "caption_emoji": False,
        "hook_overlay": True, "cold_open": False, "auto_zoom": True, "broll": True, "video_filter": None,
        "sfx": {"zoom": "pop", "broll": "whoosh", "cut": None},
    },
    "vlog": {
        "label": "Vlog / lifestyle", "about": "Warm and personal: glow captions with emoji, a warm colour grade, a teaser, light cutaways.",
        "tighten": True, "remove_fillers": False, "clean_audio": True, "caption_style": "GLOW_BOX", "caption_emoji": True,
        "hook_overlay": True, "cold_open": True, "auto_zoom": True, "broll": True, "video_filter": "cinematic_warm",
        "sfx": {"zoom": None, "broll": "whoosh", "cut": "whoosh"},
    },
}

# strength: how much of the edit shows. zoom_* feed engine/auto_zoom, sfx_db is the volume of the sound effects.
STRENGTHS = {
    "subtle": {"zoom_intensity": 0.6, "zoom_spacing": 5.0, "sfx_db": -22.0, "cold_open": False, "broll": False, "emoji": False},
    "medium": {"zoom_intensity": 1.0, "zoom_spacing": 3.5, "sfx_db": -17.0, "cold_open": True, "broll": True, "emoji": True},
    "hyped": {"zoom_intensity": 1.4, "zoom_spacing": 2.5, "sfx_db": -13.0, "cold_open": True, "broll": True, "emoji": True},
}
MAX_STATIC = 6.0        # seconds without a visible change before the rhythm report flags a stretch


def preset_names():
    return list(PRESETS)


def preset_choices():
    """[(label, key)] for a dropdown."""
    return [(p["label"], k) for k, p in PRESETS.items()]


def _given(argv, flag):
    return any(a == flag or a.startswith(flag + "=") for a in (argv or []))


def apply_preset(args, preset, strength="medium", argv=None):
    """Set the pipeline options on `args` for this preset and strength; returns {"preset","strength","flags","notes"}.

    Booleans are only switched ON (a flag the user passed is never switched off); the caption style and colour grade are only chosen when
    the user did not pass --caption_style / --video_filter. Also exports the zoom strength to the renderer through the environment."""
    if preset not in PRESETS:
        raise ValueError(f"Unknown auto-edit style {preset!r}. Choose one of: {', '.join(PRESETS)}")
    if strength not in STRENGTHS:
        raise ValueError(f"Unknown edit strength {strength!r}. Choose one of: {', '.join(STRENGTHS)}")
    p, s = PRESETS[preset], STRENGTHS[strength]
    flags, notes = {}, []

    def turn_on(name, wanted):
        if wanted and not getattr(args, name, False):
            setattr(args, name, True)
        if wanted:
            flags[name] = True

    turn_on("tighten", p["tighten"])
    turn_on("remove_fillers", p["remove_fillers"])
    turn_on("clean_audio", p["clean_audio"])
    turn_on("hook_overlay", p["hook_overlay"])
    turn_on("auto_zoom", p["auto_zoom"])
    turn_on("cold_open", p["cold_open"] and s["cold_open"])
    turn_on("broll", p["broll"] and s["broll"])
    turn_on("caption_emoji", p["caption_emoji"] and s["emoji"])
    if strength == "hyped":                                      # hyped always shows the full toolbox
        turn_on("cold_open", True)
        turn_on("caption_emoji", True)
    if not getattr(args, "use_remotion", False):
        args.use_remotion = True
        notes.append("animated captions turned on (the edit needs them)")
    flags["use_remotion"] = True
    if getattr(args, "tighten_mode", "cut") != "cut":
        args.tighten_mode = "cut"
        notes.append("pauses are cut, not sped up (needed with animated captions)")
    if not _given(argv, "--caption_style"):
        args.caption_style = p["caption_style"]
    flags["caption_style"] = args.caption_style
    if p["video_filter"] and not _given(argv, "--video_filter") and getattr(args, "video_filter", "none") in (None, "none"):
        args.video_filter = p["video_filter"]
    if getattr(args, "video_filter", None) not in (None, "none", "auto"):
        flags["video_filter"] = args.video_filter
    os.environ["SHORTSFLOW_ZOOM_INTENSITY"] = str(s["zoom_intensity"])
    os.environ["SHORTSFLOW_ZOOM_SPACING"] = str(s["zoom_spacing"])
    os.environ["SHORTSFLOW_ZOOM_FILL"] = "1"
    args.auto_edit_cfg = {"preset": preset, "strength": strength, "sfx": dict(p["sfx"]), "sfx_db": s["sfx_db"],
                          "zoom_intensity": s["zoom_intensity"], "zoom_spacing": s["zoom_spacing"]}
    return {"preset": preset, "strength": strength, "label": p["label"], "flags": flags, "notes": notes}


def cfg_from_settings(settings):
    """The director config saved in a run's settings (re-render uses it), or None."""
    preset, strength = settings.get("auto_edit"), settings.get("edit_strength") or "medium"
    if preset not in PRESETS or strength not in STRENGTHS:
        return None
    s = STRENGTHS[strength]
    return {"preset": preset, "strength": strength, "sfx": dict(PRESETS[preset]["sfx"]), "sfx_db": s["sfx_db"],
            "zoom_intensity": s["zoom_intensity"], "zoom_spacing": s["zoom_spacing"]}


def read_zoom_moments(clip_file):
    """Zoom moments the renderer chose for this clip ([] when there are none)."""
    try:
        with open(f"{clip_file}.zoom.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def build_sfx_events(cfg, zoom_moments=None, broll_events=None, cold_info=None):
    """Sound-effect events {t, kind, why} on the FINISHED clip's timeline.

    A cold open moves the main clip later by the teaser length, so zooms and cutaways are shifted by it and the cut from teaser
    to clip gets its own sound. (Events inside the teaser copy are left out: the teaser is short and already has its cut sound.)"""
    if not cfg:
        return []
    sfx = cfg.get("sfx", {})
    shift = float(cold_info["duration"]) if cold_info else 0.0
    events = []
    if cold_info and sfx.get("cut"):
        events.append({"t": shift, "kind": sfx["cut"], "why": "cut from the teaser to the clip"})
    if sfx.get("zoom"):
        for m in zoom_moments or []:
            if float(m["end"]) - float(m["start"]) <= 1.3:                  # quick punch-ins get a sound; slow pushes stay silent
                events.append({"t": float(m["start"]) + shift, "kind": sfx["zoom"], "why": "zoom"})
    if sfx.get("broll"):
        for b in broll_events or []:
            events.append({"t": float(b["t"]) + shift, "kind": sfx["broll"], "why": f"cutaway: {b.get('keyword', '')}".strip()})
    return sorted(events, key=lambda e: e["t"])


def rhythm(zoom_moments, broll_events, cold_info, duration, max_static=MAX_STATIC):
    """{"longest_static", "static_stretches"}: stretches longer than `max_static` s with no zoom, cutaway or cut (what makes an
    edit feel flat). Times are on the finished clip's timeline."""
    shift = float(cold_info["duration"]) if cold_info else 0.0
    marks = [0.0] + ([shift] if cold_info else []) + [float(m["start"]) + shift for m in zoom_moments or []] \
        + [float(b["t"]) + shift for b in broll_events or []] + [float(duration)]
    marks = sorted(set(round(m, 2) for m in marks))
    gaps = [(a, b) for a, b in zip(marks, marks[1:])]
    longest = max((b - a for a, b in gaps), default=0.0)
    return {"longest_static": round(longest, 1),
            "static_stretches": [[round(a, 1), round(b, 1)] for a, b in gaps if b - a > max_static]}


def summarize(edit):
    """One plain-language line for a review card from a clip's edit log."""
    parts = []
    if edit.get("tightened"):
        parts.append("pauses and ums cut")
    if edit.get("zooms"):
        parts.append(f"{edit['zooms']} zoom{'s' if edit['zooms'] != 1 else ''}")
    if edit.get("broll"):
        parts.append(f"{edit['broll']} cutaway{'s' if edit['broll'] != 1 else ''}")
    if edit.get("cold_open"):
        parts.append(f"{edit['cold_open']:.1f} s teaser first")
    if edit.get("sfx"):
        parts.append(f"{edit['sfx']} sound effect{'s' if edit['sfx'] != 1 else ''}")
    if edit.get("grade"):
        parts.append(f"{str(edit['grade']).replace('_', ' ')} colour")
    if edit.get("captions"):
        parts.append(f"{edit['captions'].lower()} captions")
    line = " · ".join(parts)
    r = edit.get("rhythm") or {}
    if r.get("static_stretches"):
        a, b = r["static_stretches"][0]
        line += f" (calm stretch {a:.0f}-{b:.0f} s)"
    return line


def write_plan(session_dir, plan, clip_logs):
    """edit_plan.json: what the director chose and what each clip actually got."""
    path = os.path.join(session_dir, "edit_plan.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**plan, "clips": clip_logs}, f, indent=2)
    except OSError:
        return None
    return path
