"""Cut transitions for edits made of several shots (the recap; clips cut into pieces).

A cut between shot A and shot B is built from the TAIL of A and the HEAD of B, so every shot is rendered on its own and the pieces are still
joined without re-encoding. `clip_effect()` returns the FFmpeg filter text for one shot's head and tail. Everything runs on this PC.

Types: punch (a fast push-in with a short blur, the next shot settles out of it), whip (the picture slides away with horizontal motion
blur and the next one slides in), flash (a white flash), glitch (RGB split and noise), mix (these, one after the other), subject (the person cut
out of the shot stays in front while the background wipes to the next shot; engine/subject_cut.py; a cut without a clear person gets one of the
other types instead).
"""

NAMES = ("none", "punch", "whip", "flash", "glitch", "mix", "subject", "dissolve")      # NAMES[1:5] (punch..glitch) is used by position below
AUTO = "auto"       # follows the Auto-edit style (STYLE_DEFAULTS); an explicit choice, including "none", always wins
STYLE_DEFAULTS = {"hype": "mix", "vlog": "punch"}              # podcast, educational and no style: plain cuts
LABELS = [("Auto (follows the edit style)", "auto"), ("None (plain cuts)", "none"), ("Dissolve (smooth crossfade, no zoom)", "dissolve"), ("Mix (a different one on every cut)", "mix"), ("Zoom punch", "punch"), ("Whip pan", "whip"),
          ("White flash", "flash"), ("Glitch", "glitch"),
          ("Subject cut-out (the person stays, the background changes)", "subject")]
MIX_ORDER = ("punch", "whip", "glitch", "punch", "flash", "whip")
SECONDS = {"subtle": 0.14, "medium": 0.2, "hyped": 0.26}       # length of the head and of the tail
PUNCH_AMOUNT = 0.30                                            # how much bigger the picture gets at the cut


def validate(name):
    name = (name or AUTO).strip().lower()
    if name != AUTO and name not in NAMES:
        raise ValueError(f"Unknown transition {name!r}. Choose one of: {AUTO}, {', '.join(NAMES)}")
    return name


def resolve(name, style=None):
    """The transition to use: `name` itself, or for "auto" the default of the Auto-edit `style` (none for styles without one)."""
    name = validate(name)
    if name == AUTO:
        return STYLE_DEFAULTS.get((style or "").strip().lower(), "none")
    return name


def seconds_for(strength):
    return SECONDS.get(strength or "medium", SECONDS["medium"])


def cut_types(name, count):
    """The transition of each of `count` cuts, in order: the one chosen, or the mix cycling."""
    name = validate(name)
    if name in ("none", AUTO, "dissolve"):       # dissolve is a crossfade made when the shots are joined, not an effect on each shot
        return [None] * count
    if name == "subject":
        return ["subject"] * count
    if name == "mix":
        return [MIX_ORDER[i % len(MIX_ORDER)] for i in range(count)]
    return [name] * count


XFADE = {"punch": "zoomin", "whip": "slideleft", "flash": "fadewhite", "glitch": "pixelize"}     # FFmpeg xfade look-alikes for the reel join


def fallback_type(index):
    """The normal transition for cut number `index` when the subject cut-out cannot be used there (no clear person)."""
    return MIX_ORDER[index % len(MIX_ORDER)]


def xfade_names(name, count):
    """FFmpeg xfade transition names for `count` joins in a compiled reel (several moments of one video); plain 'fade' when no type is set."""
    return [XFADE.get(fallback_type(i) if k == "subject" else k, "fade") for i, k in enumerate(cut_types(name, count))]


def _windows(kinds, seconds, d, head, tail):
    """ffmpeg `enable` expression: true in the head and/or tail window when that side's type is in `kinds`."""
    terms = []
    if head in kinds:
        terms.append(f"lt(t,{d:.3f})")
    if tail in kinds:
        terms.append(f"gt(t,{max(d, seconds - d):.3f})")
    return "+".join(terms)


def clip_effect(head, tail, seconds, d, w, h, fps=30):
    """(filters, fade_in, fade_out) for one shot: `head` and `tail` are transition types or None. `filters` goes after the picture is
    scaled to w x h; fade_in / fade_out are the fade filters ('' for none). A side without a type keeps a short black fade only when both
    are None (the caller handles that case)."""
    head, tail = (head if head in NAMES[1:5] else None), (tail if tail in NAMES[1:5] else None)
    d = max(0.05, min(float(d), seconds / 3.0))
    parts = []
    frames, d_frames = max(2, int(round(seconds * fps))), max(1, int(round(d * fps)))
    if "punch" in (head, tail):
        terms = []
        if head == "punch":
            terms.append(f"max(0,1-on/{d_frames})")
        if tail == "punch":
            terms.append(f"max(0,(on-({frames}-{d_frames}))/{d_frames})")
        parts.append(f"fps={fps},zoompan=z='1+{PUNCH_AMOUNT}*({'+'.join(terms)})':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}")
        win = _windows(("punch",), seconds, d, head, tail)
        parts.append(f"gblur=sigma=7:steps=2:enable='{win}'")
    if "whip" in (head, tail):
        bw, bh = int(w * 1.2) // 2 * 2, int(h * 1.2) // 2 * 2
        hs = f"max(0,1-t/{d:.3f})" if head == "whip" else "0"
        ts = f"max(0,(t-({seconds:.3f}-{d:.3f}))/{d:.3f})" if tail == "whip" else "0"
        parts.append(f"scale={bw}:{bh},crop={w}:{h}:x='(iw-ow)/2*(1+{ts}-{hs})':y='(ih-oh)/2'")
        parts.append(f"avgblur=sizeX=45:sizeY=1:enable='{_windows(('whip',), seconds, d, head, tail)}'")
    if "glitch" in (head, tail):
        win = _windows(("glitch",), seconds, d, head, tail)
        parts.append(f"rgbashift=rh=-16:bh=16:gv=6:enable='{win}'")
        parts.append(f"noise=alls=35:allf=t:enable='{win}'")
    fade_in = f"fade=t=in:st=0:d={d:.3f}:color=white" if head == "flash" else ""
    fade_out = f"fade=t=out:st={seconds - d:.3f}:d={d:.3f}:color=white" if tail == "flash" else ""
    return ",".join(parts), fade_in, fade_out
