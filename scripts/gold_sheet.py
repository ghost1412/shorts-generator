"""Helpers to label "best moments" by hand and turn them into the gold file the clip benchmark reads (--gold).

  python scripts/gold_sheet.py sheet <session_folder> [--out sheet.md] [--block 60]
      Writes a readable sheet of the transcript (a time stamp in front of every line, a heading every --block seconds).
      Read it, and write down the moments a viewer would want as a short clip.

  python scripts/gold_sheet.py build moments.txt --video video.webm [--out gold.json]
      Turns your moments into {"<video file name>": [[start, end], ...]} (seconds). One moment per line:
          12:30-13:05
          1:02:10-1:02:50   # optional note after a hash
      Times are m:ss, h:mm:ss or plain seconds. Blank lines and lines starting with # are ignored.

Then:  python scripts/clip_benchmark.py <session_folder> --gold gold.json   (adds recall and precision to the report)
Nothing here calls an LLM or the network.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_time(text):
    """Seconds from '90', '1:30' or '1:02:10' (a fraction is allowed in the last part)."""
    parts = str(text).strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"not a time: {text!r}")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def stamp(seconds):
    seconds = int(max(0, seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_moments(text):
    """[[start, end], ...] from the lines of a moments file; raises ValueError (with the line number) on a bad line."""
    moments = []
    for number, raw in enumerate(str(text).splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"([\d:.]+)\s*(?:-|to|–)\s*([\d:.]+)", line)
        if not m:
            raise ValueError(f"line {number}: expected 'start-end' like 12:30-13:05, got {raw.strip()!r}")
        start, end = parse_time(m.group(1)), parse_time(m.group(2))
        if end <= start:
            raise ValueError(f"line {number}: the end must be after the start ({raw.strip()!r})")
        moments.append([round(start, 2), round(end, 2)])
    return moments


def build_sheet(segments, title="Transcript", block=60.0):
    """Markdown text: the transcript with a time stamp on every line and a heading every `block` seconds."""
    lines = [f"# {title}", "",
             "Read this and write down the moments a viewer would want as a short clip (15-60 s each), one per line as `start-end`, e.g. `12:30-13:05`.",
             "Pick about 10. Choose moments that stand alone: they make sense without the rest, start on a line that grabs, and end on a complete thought.",
             ""]
    next_heading = 0.0
    for seg in sorted(segments, key=lambda s: float(s.get("start", 0))):
        start = float(seg.get("start", 0))
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        if start >= next_heading:
            lines += ["", f"## {stamp(start)}", ""]
            next_heading = (int(start // block) + 1) * block
        lines.append(f"[{stamp(start)}] {text}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("sheet", help="write a labelling sheet from a session's transcript.json")
    sh.add_argument("session")
    sh.add_argument("--out", default=None)
    sh.add_argument("--block", type=float, default=60.0)
    bd = sub.add_parser("build", help="turn a moments text file into a gold json")
    bd.add_argument("moments")
    bd.add_argument("--video", required=True, help="the file name the run used (e.g. video.webm)")
    bd.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "sheet":
        path = os.path.join(a.session, "transcript.json")
        with open(path, "r", encoding="utf-8") as f:
            segments = json.load(f).get("segments", [])
        text = build_sheet(segments, title=f"Transcript of {os.path.basename(os.path.normpath(a.session))}", block=a.block)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Wrote {a.out} ({len(segments)} lines)")
        else:
            print(text)
        return 0

    with open(a.moments, "r", encoding="utf-8") as f:
        moments = parse_moments(f.read())
    gold = {a.video: moments}
    text = json.dumps(gold, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Wrote {a.out}: {len(moments)} moment(s) for {a.video}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
