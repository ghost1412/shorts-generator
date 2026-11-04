"""Sound effects on edits: a soft whoosh or pop where the picture changes.

Editors put a quiet sound under every zoom, cutaway and teaser cut; it is a big part of why an edit feels "produced". The sounds are
synthesised here (numpy, no downloads, no licences) and mixed under the finished clip with FFmpeg: the picture is copied untouched,
only the audio is re-encoded. Everything fails safe: when anything goes wrong the clip is left exactly as it was.

    events = [{"t": 3.2, "kind": "whoosh"}, {"t": 7.5, "kind": "pop"}]       # seconds on the clip's timeline
    mix_events(video, events, volume_db=-16)
"""
import os
import subprocess
import wave

import numpy as np

SR = 44100
KINDS = ("whoosh", "pop", "hit")


def synth(kind):
    """Mono float32 samples of one effect (peak ~0.9)."""
    rng = np.random.default_rng(7)
    if kind == "pop":                                   # a short bright blip with a fast decay
        t = np.arange(int(SR * 0.14)) / SR
        sig = np.sin(2 * np.pi * (900 - 1800 * t) * t) * np.exp(-t * 32)
    elif kind == "hit":                                 # a low thud
        t = np.arange(int(SR * 0.35)) / SR
        sig = np.sin(2 * np.pi * (95 - 120 * t) * t) * np.exp(-t * 9) + 0.15 * rng.normal(0, 1, len(t)) * np.exp(-t * 30)
    else:                                               # whoosh: noise whose brightness sweeps up then away, with a soft envelope
        n = int(SR * 0.5)
        t = np.arange(n) / SR
        noise = rng.normal(0, 1, n)
        k = (np.sin(np.pi * t / 0.5) ** 2)              # 0 -> 1 -> 0
        smooth = np.convolve(noise, np.ones(60) / 60, mode="same")       # low-passed copy
        sig = (smooth * (1 - k) + (noise - smooth) * k) * k
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * 0.9
    fade = min(len(sig) // 8, int(SR * 0.02))
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    return sig.astype(np.float32)


def write_wav(path, samples):
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def sfx_files(folder):
    """{kind: wav path}, written on first use."""
    os.makedirs(folder, exist_ok=True)
    out = {}
    for kind in KINDS:
        p = os.path.join(folder, f"sfx_{kind}.wav")
        if not os.path.isfile(p):
            write_wav(p, synth(kind))
        out[kind] = p
    return out


def clean_events(events, duration, min_gap=0.6, edge=0.25):
    """Sorted events inside the clip, at least `min_gap` apart (the first of two close ones stays)."""
    out = []
    for e in sorted(events or [], key=lambda e: float(e["t"])):
        t = float(e["t"])
        if t < edge or t > duration - 0.3 or e.get("kind") not in KINDS:
            continue
        if out and t - out[-1]["t"] < min_gap:
            continue
        out.append({"t": round(t, 3), "kind": e["kind"]})
    return out


def build_command(ffmpeg, video, events, files, volume_db, output, has_audio=True):
    """FFmpeg command mixing every event's sound under the clip's own audio (video stream copied)."""
    gain = 10 ** (volume_db / 20.0)
    cmd = [ffmpeg, "-y", "-i", video]
    chain, labels = [], []
    for n, e in enumerate(events, start=1):
        cmd += ["-i", files[e["kind"]]]
        ms = int(round(e["t"] * 1000))
        chain.append(f"[{n}:a]aresample=48000,volume={gain:.4f},adelay={ms}|{ms}[s{n}]")
        labels.append(f"[s{n}]")
    base = "[0:a]aresample=48000[a0];" if has_audio else ""
    if has_audio:
        mix = f"[a0]{''.join(labels)}amix=inputs={len(events) + 1}:duration=first:dropout_transition=0:normalize=0[aout]"
    else:
        mix = f"{''.join(labels)}amix=inputs={len(events)}:duration=longest:dropout_transition=0:normalize=0[aout]"
    cmd += ["-filter_complex", base + ";".join(chain) + ";" + mix, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output]
    return cmd


def mix_events(video, events, volume_db=-16.0, folder=None):
    """Mix `events` under `video` in place. Returns the events actually mixed ([] = untouched). Never raises."""
    try:
        from engine.broll import _ffmpeg, _probe
        ffmpeg = _ffmpeg()
        _, _, duration = _probe(video, ffmpeg)
        events = clean_events(events, duration)
        if not events:
            return []
        files = sfx_files(folder or os.path.join(os.path.dirname(os.path.abspath(video)), ".sfx"))
        banner = subprocess.run([ffmpeg, "-i", video], capture_output=True, text=True).stderr
        tmp = os.path.join(os.path.dirname(os.path.abspath(video)), f".sfx_{os.getpid()}_{os.path.basename(video)}")
        try:
            res = subprocess.run(build_command(ffmpeg, video, events, files, volume_db, tmp, has_audio="Audio:" in banner),
                                 capture_output=True, text=True)
            if res.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) < 1000:
                print(f"[Warning] Sound effects failed: {res.stderr[-300:].strip()}")
                return []
            from engine.fsutil import replace_file
            replace_file(tmp, video)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        print(f"[Log] Sound effects: {len(events)} under {os.path.basename(video)} ({', '.join(sorted({e['kind'] for e in events}))})")
        return events
    except Exception as e:
        print(f"[Warning] Sound effects skipped for {os.path.basename(str(video))}: {e}")
        return []
