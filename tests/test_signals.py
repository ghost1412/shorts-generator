import numpy as np

from engine.signals import extra_signal, laughter_signal, speech_rate_signal

SR = 16000


def _audio(kinds, n=5, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n * SR) / SR
    makers = {
        "speech": lambda: 0.10 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t)),
        "laugh": lambda: 0.35 * rng.normal(0, 1, len(t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 5 * t)) ** 2,
        "applause": lambda: 0.35 * rng.normal(0, 1, len(t)),
        "loudtone": lambda: 0.35 * np.sin(2 * np.pi * 440 * t),
    }
    audio = np.concatenate([makers[k]() for k in kinds]).astype(np.float32)
    return audio, [{"start": i * n, "end": i * n + n} for i in range(len(kinds))]


def test_laughter_like_sound_scores_high_and_quiet_speech_or_a_loud_tone_does_not():
    kinds = ["speech"] * 4 + ["laugh", "applause", "loudtone", "speech"]
    audio, segs = _audio(kinds)
    s = dict(zip(range(len(kinds)), laughter_signal(audio, SR, segs)))
    assert s[4] > 0.7 and 0.3 < s[5] <= s[4]          # rhythmic laughter > steady applause-like noise
    assert s[0] == s[1] == s[2] == s[3] == 0.0 and s[6] == 0.0 and s[7] == 0.0


def test_no_audio_means_zeros():
    assert laughter_signal(None, SR, [{"start": 0, "end": 5}]) == [0.0]
    assert laughter_signal(np.zeros(10, dtype=np.float32), SR, []) == []


def test_speech_rate_flags_the_burst_and_its_neighbours():
    txt = [{"start": i * 5, "end": i * 5 + 5, "text": " ".join(["w"] * n)} for i, n in enumerate([12, 12, 12, 40, 12, 12])]
    r = speech_rate_signal(txt)
    assert r[3] == 1.0 and r[2] > 0 and r[4] > 0 and r[0] == r[1] == r[5] == 0.0
    assert speech_rate_signal([]) == []


def test_extra_signal_uses_laughter_only_when_there_is_audio():
    audio, segs = _audio(["speech", "laugh"])
    for s in segs:
        s["text"] = "same number of words in each segment here"
    with_audio, _, laugh = extra_signal(segs, audio, SR)
    without, _, zeros = extra_signal(segs, None, SR)
    assert with_audio[1] > 0.5 and laugh[1] > 0.7
    assert without == [0.0, 0.0] and zeros == [0.0, 0.0]
