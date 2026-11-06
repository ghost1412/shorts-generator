"""Cut transitions for edits made of several shots (the recap; clips cut into pieces).

A cut between shot A and shot B is built from the TAIL of A and the HEAD of B, so every shot is rendered on its own and the pieces are still
joined without re-encoding. `clip_effect()` returns the FFmpeg filter text for one shot's head and tail. Everything runs on this PC.

Types: punch (a fast push-in with a short blur, the next shot settles out of it), whip (the picture slides away with horizontal motion
blur and the next one slides in), flash (a white flash), glitch (RGB split and noise), mix (these, one after the other).
"""

NAMES = ("none", "punch", "whip", "flash", "glitch", "mix")
LABELS = [("None (plain cuts)", "none"), ("Mix (a different one on every cut)", "mix"), ("Zoom punch", "punch"), ("Whip pan", "whip"),
          ("White flash", "flash"), ("Glitch", "glitch")]
MIX_ORDER = ("punch", "whip", "glitch", "punch", "flash", "whip")
SECONDS = {"subtle": 0.14, "medium": 0.2, "hyped": 0.26}       # length of the head and of the tail
PUNCH_AMOUNT = 0.30                                            # how much bigger the picture gets at the cut


def validate(name):
    name = (name or "none").strip().lower()
    if name not in NAMES:
        raise ValueError(f"Unknown transition {name!r}. Choose one of: {', '.join(NAMES)}")
    return name


def seconds_for(strength):
    return SECONDS.get(strength or "medium", SECONDS["medium"])


def cut_types(name, count):
    """The transition of each of `count` cuts, in order: the one chosen, or the mix cycling."""
    name = validate(name)
    if name == "none":
        return [None] * count
    if name == "mix":
        return [MIX_ORDER[i % len(MIX_ORDER)] for i in range(count)]
    return [name] * count


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
