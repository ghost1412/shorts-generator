"""Audio clean-up for finished clips (`--clean_audio`).

Chain: high-pass (rumble) -> noise reduction (arnndn model if given, else afftdn) -> gentle compressor ->
loudness normalisation to about -14 LUFS (EBU R128 loudnorm, two-pass when the measurement works).
The video stream is copied untouched; only the audio is re-encoded. Every step degrades gracefully: a filter
this FFmpeg build lacks is dropped, and on any failure the original file is left as it was.
"""
import json
import os
import re
import shutil
import subprocess

TARGET_LUFS = -14.0
TARGET_TP = -1.5
TARGET_LRA = 11.0

_filter_cache = {}


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def available_filters(ffmpeg=None):
    """Names of the audio filters this FFmpeg build has (cached per binary)."""
    ffmpeg = ffmpeg or _ffmpeg()
    if ffmpeg in _filter_cache:
        return _filter_cache[ffmpeg]
    names = set()
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            parts = line.split()
            # flag column is 2-3 chars of T/S/C/. depending on the FFmpeg version, then the name and an "A->A"-style IO column
            if len(parts) >= 3 and re.fullmatch(r"[TSC.]{2,3}", parts[0]) and "->" in parts[2]:
                names.add(parts[1])
    except Exception:
        pass
    _filter_cache[ffmpeg] = names
    return names


def build_filter_chain(filters, noise=True, compress=True, highpass=True, rnn_model=None, loudnorm=None):
    """Return the `-af` string. `filters` = set of available filter names; `loudnorm` = extra loudnorm options
    (e.g. measured values for the second pass) or None for single-pass defaults; "" skips loudnorm."""
    chain = []
    if highpass and "highpass" in filters:
        chain.append("highpass=f=80")
    if noise:
        if rnn_model and os.path.exists(rnn_model) and "arnndn" in filters:
            chain.append("arnndn=m=" + rnn_model.replace("\\", "/").replace(":", "\\:"))
        elif "afftdn" in filters:
            chain.append("afftdn=nr=12:nf=-30")
    if compress and "acompressor" in filters:
        chain.append("acompressor=threshold=-21dB:ratio=3:attack=20:release=250:makeup=2")
    if loudnorm != "" and "loudnorm" in filters:
        base = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}"
        chain.append(base + (":" + loudnorm if loudnorm else ""))
    return ",".join(chain)


def parse_loudnorm_json(stderr):
    """Pull the measurement block printed by `loudnorm=print_format=json` out of FFmpeg's stderr."""
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return {k: float(d[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except Exception:
        return None


def measure_loudness(path, ffmpeg=None):
    """Integrated loudness (LUFS) of a file's audio, or None."""
    ffmpeg = ffmpeg or _ffmpeg()
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
                            "loudnorm=print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=300)
        d = parse_loudnorm_json(r.stderr)
        return d["input_i"] if d else None
    except Exception:
        return None


def _two_pass_option(m):
    return (f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def clean_audio(path, noise=True, compress=True, highpass=True, rnn_model=None, ffmpeg=None):
    """Clean the audio of `path` in place (video stream copied). Returns True when the file was replaced."""
    ffmpeg = ffmpeg or _ffmpeg()
    if not os.path.exists(path):
        return False
    try:
        filters = available_filters(ffmpeg)
        pre = build_filter_chain(filters, noise, compress, highpass, rnn_model, loudnorm="")
        loud = None
        if "loudnorm" in filters:
            # pass 1: measure the audio AFTER the pre-filters so the normalisation is exact
            af1 = (pre + "," if pre else "") + "loudnorm=print_format=json"
            r = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", path, "-vn", "-af", af1, "-f", "null", "-"],
                               capture_output=True, text=True, timeout=600)
            m = parse_loudnorm_json(r.stderr)
            if m and m["input_i"] > -70:  # -inf / silence cannot be normalised
                loud = _two_pass_option(m)
        chain = build_filter_chain(filters, noise, compress, highpass, rnn_model, loudnorm=loud)
        if not chain:
            print("[Warning] --clean_audio: this FFmpeg has none of the needed audio filters; skipped.")
            return False
        tmp = path + ".clean.mp4"
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", path, "-map", "0:v?", "-map", "0:a:0",
               "-c:v", "copy", "-af", chain, "-ar", "44100", "-c:a", "aac", "-b:a", "192k", tmp]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1024:
            print(f"[Warning] --clean_audio failed for {os.path.basename(path)}: {(r.stderr or '')[-200:]}")
            if os.path.exists(tmp):
                os.remove(tmp)
            return False
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"[Warning] --clean_audio failed for {os.path.basename(path)}: {e}")
        return False


def clean_clips(paths, **kw):
    """Run clean_audio over several clips; returns how many were cleaned."""
    done = 0
    for p in paths:
        if clean_audio(p, **kw):
            done += 1
    return done
