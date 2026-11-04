"""`shortsflow clip` for several videos: a folder, a list of files and links, or `--watch FOLDER`.

Each video is one run of the normal pipeline in its own session folder (a child process, so one bad file cannot
stop the others); a summary table is printed at the end. The runner, the clock and the folder listing are injectable
so the logic is tested without rendering anything.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".wmv", ".mpg", ".mpeg", ".ts")


def is_url(text):
    return str(text).lower().startswith(("http://", "https://"))


def is_video_file(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def list_folder(folder):
    """Video files directly inside `folder` (not sub-folders), sorted by name; hidden files are skipped."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    return [os.path.join(folder, n) for n in names
            if not n.startswith(".") and is_video_file(n) and os.path.isfile(os.path.join(folder, n))]


def collect_videos(inputs):
    """(sources, problems): links and files kept as given, folders expanded to their video files, duplicates dropped.
    `problems` is a list of plain-language messages for inputs that do not exist or hold no video."""
    sources, problems, seen = [], [], set()

    def add(item):
        key = os.path.normcase(os.path.abspath(item)) if not is_url(item) else item
        if key not in seen:
            seen.add(key)
            sources.append(item)

    for item in inputs:
        if is_url(item):
            add(item)
        elif os.path.isdir(item):
            found = list_folder(item)
            if not found:
                problems.append(f"No video files in the folder '{item}'.")
            for f in found:
                add(f)
        elif os.path.isfile(item):
            add(item)
        else:
            problems.append(f"'{item}' was not found.")
    return sources, problems


def safe_stem(source, limit=40):
    """Short folder-friendly name for a source: the file name without extension, or the tail of a link."""
    base = source.rstrip("/").split("/")[-1] if is_url(source) else os.path.splitext(os.path.basename(source))[0]
    keep = "".join(c if c.isalnum() or c in "-_" else "_" for c in base).strip("_")
    return (keep or "video")[:limit]


def session_for(source, index, stamp=None):
    """Unique session folder for one batch item (the browser app's 'Open an earlier run' lists these too)."""
    stamp = stamp or time.strftime("%Y%m%d_%H%M%S")
    return os.path.join("sessions", f"batch_{stamp}_{index:02d}_{safe_stem(source)}")


def item_flags(base_flags, source, session):
    """Pipeline flags for one video: the common flags, its own source, session folder and results file."""
    flags = ["--source_video", source, "--session_dir", session, "--output_json", os.path.join(session, "results.json")]
    flags += list(base_flags)
    if "--clip_report" not in flags:
        flags += ["--clip_report", "md"]
    return flags


def default_runner(flags):
    """Run one pipeline in a child process and return its exit code. `python -m shortsflow` works from a checkout
    (workspace) and from a pip install alike."""
    return subprocess.call([sys.executable, "-m", "shortsflow", *flags])


def read_clip_count(session):
    try:
        with open(os.path.join(session, "results.json"), encoding="utf-8") as f:
            return len(json.load(f).get("clips") or [])
    except (OSError, ValueError):
        return 0


def run_one(source, index, base_flags, runner=default_runner, stamp=None, out=print):
    """One video -> {source, session, status ('ok'/'failed'/'no clips'), clips, code, seconds}. Never raises."""
    session = session_for(source, index, stamp)
    out(f"\n[shortsflow] ({index}) {source}")
    t0 = time.time()
    try:
        code = runner(item_flags(base_flags, source, session))
    except Exception as e:  # a child that cannot even start must not end the batch
        out(f"[shortsflow] Could not start: {e}")
        code = 1
    clips = read_clip_count(session)
    status = "failed" if code else ("ok" if clips else "no clips")
    return {"source": source, "session": session, "status": status, "clips": clips, "code": code,
            "seconds": round(time.time() - t0)}


def run_batch(sources, base_flags, runner=default_runner, out=print):
    """Process every source in turn and keep going after failures. Returns the list of per-video result dicts."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    results = []
    for i, source in enumerate(sources, start=1):
        results.append(run_one(source, i, base_flags, runner, stamp, out))
    return results


def summary_table(results):
    """Plain-text table of a batch (one row per video) plus a totals line."""
    if not results:
        return "Nothing to process."
    rows = [("#", "Video", "Result", "Shorts", "Folder")]
    for i, r in enumerate(results, start=1):
        name = r["source"] if is_url(r["source"]) else os.path.basename(r["source"])
        rows.append((str(i), name if len(name) <= 42 else name[:39] + "...", r["status"], str(r["clips"]),
                     r["session"].replace("\\", "/")))
    widths = [max(len(row[c]) for row in rows) for c in range(5)]
    lines = ["  ".join(cell.ljust(widths[c]) for c, cell in enumerate(row)).rstrip() for row in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    failed = sum(r["status"] == "failed" for r in results)
    total = sum(r["clips"] for r in results)
    lines.append(f"\n{len(results)} video(s), {total} short(s), {failed} failed.")
    return "\n".join(lines)


# ---------- watch mode ----------

def state_path(folder):
    """Where the 'already done' list lives: in the workspace's sessions folder, not in the watched folder."""
    tag = hashlib.sha1(os.path.normcase(os.path.abspath(folder)).encode("utf-8")).hexdigest()[:10]
    return os.path.join("sessions", f".watch_{tag}.json")


def load_done(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_done(path, done):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(done, f, indent=2)


def _fingerprint(path):
    st = os.stat(path)
    return f"{st.st_size}:{int(st.st_mtime)}"


def watch_once(folder, base_flags, state_file, pending, runner=default_runner, out=print, lister=list_folder):
    """One poll. A file is processed only once its size has stopped changing between two polls (so a file that is
    still being copied is not clipped half-way) and only if it is not in the done list. `pending` is the
    {path: fingerprint} seen on the previous poll and is updated in place. Returns the results of this poll."""
    done = load_done(state_file)
    results, seen_now = [], {}
    for path in lister(folder):
        try:
            fp = _fingerprint(path)
        except OSError:
            continue
        key = os.path.abspath(path)
        if done.get(key, {}).get("fingerprint") == fp:
            continue
        seen_now[path] = fp
        if pending.get(path) != fp:
            continue  # first sighting or still growing: wait for the next poll
        result = run_one(path, len(done) + 1, base_flags, runner, out=out)
        results.append(result)
        done[key] = {"fingerprint": fp, "status": result["status"], "session": result["session"],
                     "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        save_done(state_file, done)
        seen_now.pop(path, None)
    pending.clear()
    pending.update(seen_now)
    return results


def watch(folder, base_flags, interval=30, runner=default_runner, out=print, sleep=time.sleep, max_polls=None):
    """Poll `folder` every `interval` seconds until Ctrl+C (or `max_polls`, for tests). Returns all results."""
    state_file = state_path(folder)
    pending, everything, polls = {}, [], 0
    out(f"[shortsflow] Watching '{folder}' every {interval} s. New videos are clipped once; press Ctrl+C to stop.")
    try:
        while max_polls is None or polls < max_polls:
            polls += 1
            for r in watch_once(folder, base_flags, state_file, pending, runner, out):
                everything.append(r)
                out(summary_table([r]))
            if max_polls is None or polls < max_polls:
                sleep(interval)
    except KeyboardInterrupt:
        out("\n[shortsflow] Stopped watching.")
    return everything
