"""Extra signals for highlight scoring: speech-rate change and laughter / applause.

Both are cheap, need no model, and return one number in 0..1 per transcript segment so they can be folded into the existing
signal mix (engine/analysis.py gives them about 10% of the weight):

* `speech_rate_signal`: people speed up when they are excited and slow down (or pause) before a reveal. A segment scores
  high when its words-per-second differs a lot from its neighbours or is well above the video's typical pace.
  Works from the transcript alone.
* `laughter_signal`: laughter and applause are LOUD, noise-like, and (laughter) rhythmic at roughly 3-8 beats per second.
  It measures how much of the loudness envelope's variation sits in that band, how noise-like the spectrum is, and gates on
  loudness. It is a heuristic, not a classifier: explosions and gunfire in game footage can also trigger it, which is why it
  only runs with --use_audio_detect and carries a small weight.
"""
import numpy as np


def speech_rate_signal(segments):
    """[0..1] per segment from words per second (segments need start, end, text)."""
    if not segments:
        return []
    rates = []
    for s in segments:
        dur = max(0.5, float(s["end"]) - float(s["start"]))
        rates.append(len(str(s.get("text", "")).split()) / dur)
    typical = float(np.median([r for r in rates if r > 0] or [1.0])) or 1.0
    out = []
    for i, r in enumerate(rates):
        neighbours = [rates[j] for j in (i - 1, i + 1) if 0 <= j < len(rates)]
        change = abs(r - float(np.mean(neighbours))) / typical if neighbours else 0.0     # speeding up / slowing down
        fast = max(0.0, r / typical - 1.0)                                                # clearly faster than usual
        out.append(round(float(min(1.0, 0.5 * min(1.0, change) + 0.5 * min(1.0, fast))), 3))
    return out


def _window_score(chunk, sr, loud_ref):
    if len(chunk) < sr // 2:
        return 0.0
    hop = max(1, int(sr * 0.01))                                   # 10 ms frames
    n = len(chunk) // hop
    env = np.sqrt(np.mean(chunk[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    loud = float(np.mean(env))
    gate = min(1.0, max(0.0, (loud / loud_ref - 0.8) / 1.2)) if loud_ref > 0 else 0.0     # quiet = not laughter / applause
    if gate <= 0.0:
        return 0.0
    e = env - env.mean()
    spec = np.abs(np.fft.rfft(e)) ** 2
    freqs = np.fft.rfftfreq(len(e), d=0.01)
    band = spec[(freqs >= 3.0) & (freqs <= 8.0)].sum()
    total = spec[(freqs >= 0.5) & (freqs <= 20.0)].sum() + 1e-12
    rhythm = float(min(1.0, (band / total) * 2.5))                 # share of the loudness variation that is "ha-ha-ha" paced
    # noise-likeness: spectral flatness of the 300-4000 Hz region (tones ~0, noise ~1)
    sp = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
    f = np.fft.rfftfreq(len(chunk), d=1.0 / sr)
    region = sp[(f >= 300) & (f <= 4000)] + 1e-9
    flat = float(np.exp(np.mean(np.log(region))) / np.mean(region)) if len(region) else 0.0
    flat = min(1.0, flat * 1.6)
    return float(gate * (0.6 * rhythm + 0.4 * flat))


def laughter_signal(audio, sr, segments):
    """[0..1] per segment: how laughter / applause-like the sound inside the segment is (0 when there is no audio)."""
    if audio is None or not len(audio) or not segments:
        return [0.0] * len(segments or [])
    audio = np.asarray(audio, dtype=np.float32)
    hop = max(1, int(sr * 0.01))
    n = len(audio) // hop
    frames = np.sqrt(np.mean(audio[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12) if n else np.array([0.0])
    loud_ref = float(np.median(frames[frames > np.percentile(frames, 20)])) if len(frames) else 0.0   # typical speech loudness
    out = []
    for s in segments:
        a, b = int(float(s["start"]) * sr), int(float(s["end"]) * sr)
        out.append(round(_window_score(audio[a:b], sr, loud_ref), 3))
    return out


def extra_signal(segments, audio=None, sr=16000):
    """Combined 0..1 per segment (+ the two parts); laughter counts more than pace when audio is available."""
    rate = speech_rate_signal(segments)
    laugh = laughter_signal(audio, sr, segments) if audio is not None else [0.0] * len(rate)
    has_audio = audio is not None
    extra = [round(min(1.0, (0.35 * r + 0.65 * l) if has_audio else r), 3) for r, l in zip(rate, laugh)]
    return extra, rate, laugh
