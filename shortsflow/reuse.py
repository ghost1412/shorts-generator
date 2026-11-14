"""Reuse the slow work of an earlier run in a new one, from the browser app.

A new run starts in a fresh folder (so every setting you change, captions, brand, length, extras, is applied) but is seeded with the
earlier run's expensive results: the transcript (Whisper), the picture descriptions and place names (Gemini / the map), and, if you
ask for it, the chosen moments, the crop/silence analysis and the pieces already cut. The finished clips are not reused, so a changed
caption style, brand or extra is always applied.
"""
import glob
import json
import os
import re
import shutil

CLIP_FILES = ("transcript.json", "visual_context.json")
MOMENT_FILES = ("highlights.json", "interest_points.json", "silence_intervals.json")
TRIP_FILES = ("visual_context.json", "places.json", "place_names.json")


def _flag_values(cmd, flag):
    """The arguments after `flag` up to the next option, [] when the flag is missing."""
    if flag not in cmd:
        return []
    out = []
    for item in cmd[cmd.index(flag) + 1:]:
        if str(item).startswith("--"):
            break
        out.append(item)
    return out


def saved_command(command_json):
    """The saved command list of a run, [] when it cannot be read."""
    try:
        with open(command_json, "r", encoding="utf-8") as f:
            return [str(x) for x in json.load(f)["cmd"]]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def earlier_runs(root, kind="clip", limit=15):
    """[(label, command.json path)] of earlier runs of this kind ('clip' = Start here, 'trip' = Trip recap), newest first, finished or not."""
    prefix = "trip_" if kind == "trip" else "web_"
    out = []
    for d in sorted(glob.glob(os.path.join(root, "sessions", prefix + "*")), reverse=True):
        cmd_file = os.path.join(d, "command.json")
        cmd = saved_command(cmd_file) if os.path.isfile(cmd_file) else []
        if not cmd:
            continue
        if kind == "trip":
            name = _flag_values(cmd, "--trip_name")
            first = _flag_values(cmd, "--trip_videos")[:1]
            what = name[0] if name else (os.path.basename(str(first[0]).rstrip("/\\")) if first else "recap")
        else:
            vals = _flag_values(cmd, "--source_video")
            what = os.path.basename(str(vals[0]).rstrip("/")) if vals else "video"
        m = re.match(r"\w+?_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})", os.path.basename(d))
        when = f"{m.group(3)}.{m.group(2)}.{m.group(1)} {m.group(4)}:{m.group(5)}" if m else os.path.basename(d)
        done = os.path.isfile(os.path.join(d, "results.json")) or os.path.isfile(os.path.join(d, "recap.mp4"))
        out.append((f"{when} - {str(what)[:50]}{'' if done else ' (unfinished)'}", cmd_file))
    return out[:limit]


def source_of(command_json):
    """The source video (path or link) the earlier clip run used, '' when unknown."""
    vals = _flag_values(saved_command(command_json), "--source_video")
    return str(vals[0]) if vals else ""


def trip_videos_of(command_json):
    """The video files the earlier recap used."""
    return [str(v) for v in _flag_values(saved_command(command_json), "--trip_videos")]


def _link_or_copy(src, dest, link=False):
    """Copy a file; with `link` try a hard link first (no extra disk space). Only for big files that are never rewritten in place:
    a rewritten linked file would change the earlier run's copy too."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if link:
        try:
            os.link(src, dest)
            return
        except OSError:
            pass
    shutil.copyfile(src, dest)


def seed_session(old_dir, new_dir, keep_moments=True, kind="clip"):
    """Copy the earlier run's slow results into the new session folder. Returns the relative names copied.

    clip: transcript + picture descriptions always; with keep_moments also the chosen moments, the crop/silence analysis and the cut
    pieces (temp_segments/seg_*.mp4), so the run can be started with --use_cache and only renders again. trip: descriptions + places."""
    names = list(TRIP_FILES if kind == "trip" else CLIP_FILES + (MOMENT_FILES if keep_moments else ()))
    copied = []
    for dirpath, dirs, files in os.walk(old_dir):
        rel_dir = os.path.relpath(dirpath, old_dir)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        in_segments = parts[:1] == ["temp_segments"]
        if in_segments and not (kind == "clip" and keep_moments):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in ("recap_parts", "photos", "videos") and len(parts) < 1]       # root and one level
        for name in files:
            if name in names or (in_segments and re.fullmatch(r"seg_\d+\.mp4(\.key)?", name)):
                rel = os.path.relpath(os.path.join(dirpath, name), old_dir)
                _link_or_copy(os.path.join(dirpath, name), os.path.join(new_dir, rel), link=in_segments)
                copied.append(rel)
    return copied
