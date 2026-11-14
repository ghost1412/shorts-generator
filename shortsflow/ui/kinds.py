"""What kind of video is it? One choice that fills in several settings together (no gradio here, so it is easy to test).

Each kind sets: how the moments are picked (`game` = story and action moments for game footage, otherwise from the speech), the
auto-edit style, the picture framing, a visual template and the caption style. The browser app shows the resulting line
(`describe`) so nothing is silent, and every field can be changed afterwards.
"""

KINDS = {
    "podcast": {"label": "Podcast or interview", "game": False, "edit": "podcast", "framing": "auto", "template": "podcast-card", "captions": "BAR"},
    "gaming": {"label": "Gaming", "game": True, "edit": "hype", "framing": "crop", "template": "neon-frame", "captions": "KARAOKE"},
    "vlog": {"label": "Vlog or lifestyle", "game": False, "edit": "vlog", "framing": "auto", "template": "story-progress", "captions": "GLOW_BOX"},
    "teach": {"label": "Teaching or explainer", "game": False, "edit": "educational", "framing": "auto", "template": "title-bars", "captions": "BAR"},
    "news": {"label": "News or commentary", "game": False, "edit": "news", "framing": "auto", "template": "news-banner", "captions": "BAR"},
    "story": {"label": "Storytime", "game": False, "edit": "storytime", "framing": "auto", "template": "minimal-line", "captions": "GLOW_BOX"},
    "other": {"label": "Something else", "game": False, "edit": "minimal", "framing": "auto", "template": "none", "captions": "MINIMAL"},
}
DEFAULT_KIND = "other"


def kind_choices():
    """[(label, key)] for a picker."""
    return [(k["label"], key) for key, k in KINDS.items()]


def settings_for(kind):
    """The settings of a kind (a copy); an unknown or empty kind gives the neutral one."""
    return dict(KINDS.get(kind) or KINDS[DEFAULT_KIND])


def describe(kind):
    """One plain line telling what choosing this kind switches on."""
    s = settings_for(kind)
    picking = "game mode on (story and action moments)" if s["game"] else "moments picked from what is said"
    framing = {"crop": "full-screen crop", "fit": "whole picture over blurred bars"}.get(s["framing"], "automatic framing")
    template = "no template" if s["template"] == "none" else f"{s['template']} template"
    return f"{s['label']}: {picking}, {s['edit']} edit style, {framing}, {template}, {s['captions'].lower()} captions."
