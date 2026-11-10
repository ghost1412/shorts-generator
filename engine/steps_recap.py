"""A step-by-step video (a recipe, a DIY job, a workout, a tutorial): `--mode TRIP --steps_file steps.txt`.

You write the steps in a plain text file, put your clips in step order (one folder per step, or one folder of clips in filming order),
and ShortsFlow builds a recap that opens on the finished result, goes straight into the steps with a title and a caption for each, and
can end on a "what you need" card. Nothing here is specific to cooking: the words come from your file.

    Title: Build a bird house
    Hook: Done in one afternoon
    Needs: 4 pine boards | 30 screws | wood glue | a drill
    End: Ready to hang!

    1. Cut the boards | Cut four 20 cm sides and two 15 cm roof pieces
    2. Drill the hole | 3 cm hole, 12 cm above the floor
    3. Assemble | Glue, then 6 screws per side

Lines starting with # are notes. A step without "|" uses its whole text as the caption. The needs list can also be bullet lines under
"Needs:" (or "Ingredients:", "Materials:", "Tools:", "Supplies:", "Equipment:", which also name the card).
"""
import os
import re

KEYS = {"title": "title", "name": "title", "hook": "hook", "intro": "hook", "end": "end", "outro": "end", "closing": "end"}
NEEDS = {"needs": "What you need", "you need": "What you need", "ingredients": "Ingredients", "materials": "Materials", "tools": "Tools",
         "supplies": "Supplies", "equipment": "Equipment"}
_KEY_LINE = re.compile(r"^([A-Za-z][A-Za-z ]{1,18}):\s*(.*)$")
_STEP_LINE = re.compile(r"^(?:step\s*)?\d+\s*[.):\-]\s*(.*)$", re.I)
_BULLET = re.compile(r"^[-*•]\s+(.*)$")


def parse_steps(text):
    """{"title", "hook", "end", "needs_title", "needs": [...], "steps": [(title, caption), ...]} from the text of a steps file."""
    plan = {"title": "", "hook": "", "end": "", "needs_title": "What you need", "needs": [], "steps": []}
    collecting = False                                           # bullet lines under "Needs:" belong to the needs list
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _KEY_LINE.match(line)
        key = m.group(1).strip().lower() if m else ""
        if m and key in KEYS:
            plan[KEYS[key]] = m.group(2).strip()
            collecting = False
            continue
        if m and key in NEEDS:
            plan["needs_title"] = NEEDS[key]
            plan["needs"] += [i.strip() for i in re.split(r"[|;]", m.group(2)) if i.strip()]
            collecting = True
            continue
        bullet = _BULLET.match(line)
        if bullet and collecting:
            plan["needs"].append(bullet.group(1).strip())
            continue
        step = _STEP_LINE.match(line)
        body = step.group(1) if step else (bullet.group(1) if bullet else "")
        if not body.strip():
            continue
        collecting = False
        title, bar, caption = body.partition("|")
        title, caption = title.strip(), caption.strip()
        if not bar:                                              # no "|": the whole text is the caption, the title falls back to "Step N"
            title, caption = "", title
        plan["steps"].append((title or f"Step {len(plan['steps']) + 1}", caption or title))
    return plan


def apply_steps(args):
    """Fill the recap options from `args.steps_file` (explicit command-line options always win) and switch on the defaults that suit a
    step-by-step video: cinematic look, vertical frame, the result first, a fast pace, text clear of the phone app's bars.
    Returns the parsed plan, or None when there is no steps file. Raises ValueError for a file with no steps."""
    path = getattr(args, "steps_file", None)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            plan = parse_steps(f.read())
    except OSError as e:
        raise ValueError(f"Cannot read the steps file {path!r}: {e}")
    if not plan["steps"]:
        raise ValueError(f"No steps found in {path!r}. Write one per line, like: 1. Cut the boards | Cut four 20 cm sides")

    def unset(name):
        return getattr(args, name, None) in (None, "")

    args.recap_kind = "steps"
    if unset("trip_name"):
        args.trip_name = plan["title"]
    if unset("trip_stops"):
        args.trip_stops = "|".join(t for t, _c in plan["steps"])
    if unset("recap_lines"):
        args.recap_lines = "|".join(c for _t, c in plan["steps"])
    if unset("recap_hook"):
        args.recap_hook = plan["hook"]
    if plan["needs"] and unset("recap_ingredients"):
        args.recap_ingredients = "|".join(plan["needs"])
        if unset("recap_ingredients_title"):
            args.recap_ingredients_title = plan["needs_title"]
    if plan["end"] and unset("recap_end_text"):
        args.recap_end_text = plan["end"]
    if unset("recap_pace"):
        args.recap_pace = "fast"
    if unset("recap_opening"):
        args.recap_opening = "result"
    if unset("recap_end"):
        args.recap_end = "result" if plan["end"] else "none"
    if getattr(args, "recap_style", "auto") in (None, "", "auto"):
        args.recap_style = "cinematic"
    if unset("recap_aspect"):
        args.recap_aspect = "9:16"
    args.recap_safe_text = True
    if getattr(args, "recap_length", 60) in (None, 60):          # the default length: about five seconds a step plus the opening
        args.recap_length = max(40, int(round(5.2 * len(plan["steps"]) + 6)))
    folders = [p for p in (getattr(args, "trip_videos", None) or []) if os.path.isdir(p)]
    if len(folders) > 1 and len(folders) != len(plan["steps"]):
        print(f"[Warning] {len(plan['steps'])} steps in the steps file but {len(folders)} folders of clips: the clips are split into "
              f"the steps in filming order, which may not match what each step shows. One folder per step is the safe way.")
    print(f"[Log] Steps file: {len(plan['steps'])} step(s)" + (f", a '{plan['needs_title']}' card with {len(plan['needs'])} item(s)" if plan["needs"] else "") + ".")
    return plan
