import json
import os

import pytest

from engine import dubbing


def test_normalize_and_voice():
    assert dubbing.normalize_lang("pt_BR") == "pt"
    assert dubbing.voice_for("ES").startswith("es-")
    assert dubbing.voice_for("xx") is None


def test_srt_format():
    srt = dubbing.build_srt([{"start": 0.5, "end": 3725.25, "text": " hola "}])
    assert srt == "1\n00:00:00,500 --> 01:02:05,250\nhola\n"


def test_segments_drop_empty_and_tiny():
    data = {"segments": [{"start": 0, "end": 2, "text": " hi "}, {"start": 2, "end": 2.1, "text": "x"},
                         {"start": 3, "end": 5, "text": "  "}]}
    assert dubbing.segments_from_transcript(data) == [{"start": 0.0, "end": 2.0, "text": "hi"}]


def test_plan_fit_short_audio_untouched():
    assert dubbing.plan_fit(1.5, 2.0, 3.0) == {"tempo": 1.0, "duration": 1.5, "trim": None}


def test_plan_fit_speeds_up_within_limits():
    soft = dubbing.plan_fit(2.4, 2.0, 5.0)
    assert soft["tempo"] == pytest.approx(1.2) and soft["trim"] is None
    borrowed = dubbing.plan_fit(4.0, 2.0, 2.5)  # own slot would need 2x; borrows the gap at <= 1.6x
    assert borrowed["tempo"] == pytest.approx(1.6) and borrowed["trim"] is None


def test_plan_fit_trims_when_still_too_long():
    fit = dubbing.plan_fit(6.0, 2.0, 2.5)
    assert fit["tempo"] == dubbing.HARD_SPEEDUP and fit["trim"] == 2.5


def test_translate_segments_keeps_order_and_counts_missing():
    segs = [{"start": 0, "end": 2, "text": "one"}, {"start": 2, "end": 4, "text": "two"}]
    llm = lambda prompt: '{"translations": [{"id": 1, "text": "dos"}]}'  # noqa: E731 - id 0 missing
    texts, failed = dubbing.translate_segments(segs, "es", llm=llm, parse=json.loads)
    assert texts == ["one", "dos"] and failed == 1


def test_translate_segments_survives_llm_error():
    def boom(prompt):
        raise RuntimeError("no llm")
    texts, failed = dubbing.translate_segments([{"start": 0, "end": 2, "text": "one"}], "es", llm=boom, parse=json.loads)
    assert texts == ["one"] and failed == 1


def test_build_filter_delays_and_ducks():
    flt = dubbing.build_filter([{"index": 1, "start": 1.5, "tempo": 1.2, "trim": None},
                                {"index": 2, "start": 4.0, "tempo": 1.0, "trim": 2.0}], 10.0)
    assert "atempo=1.200,adelay=1500|1500[d1]" in flt
    assert "atrim=0:2.000" in flt and "adelay=4000|4000[d2]" in flt
    assert "sidechaincompress" in flt and "[aout]" in flt
    silent = dubbing.build_filter([{"index": 1, "start": 0, "tempo": 1.0, "trim": None}], 5.0, source_has_audio=False)
    assert "sidechaincompress" not in silent and silent.endswith("[aout]")


@pytest.fixture
def transcript(tmp_path):
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps({"language": "en", "segments": [
        {"start": 0.0, "end": 2.0, "text": "Hello there"}, {"start": 3.0, "end": 5.0, "text": "Welcome back"}]}))
    return str(path)


def _fake_media(monkeypatch):
    monkeypatch.setattr(dubbing, "media_duration", lambda p: 1.0)


def test_dub_video_pipeline_with_fakes(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    llm = lambda prompt: json.dumps({"translations": [{"id": 0, "text": "Hola"}, {"id": 1, "text": "Bienvenido"}]})  # noqa: E731
    monkeypatch.setattr(dubbing, "_parse", json.loads)

    def synth(text, out):
        open(out, "wb").write(b"x" * 500)

    seen = {}

    def mixer(src, clips, out, session_dir, burn_srt=None):
        seen.update(clips=clips, burn=burn_srt)
        open(out, "wb").write(b"video")

    res = dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=synth,
                            mixer=mixer, captions=True)
    assert res["segments"] == 2 and res["failed_translations"] == 0 and res["failed_voices"] == 0
    assert [c["start"] for c in seen["clips"]] == [0.0, 3.0] and seen["burn"] == res["srt"]
    assert "Bienvenido" in open(res["srt"], encoding="utf-8").read()
    assert json.load(open(res["json"], encoding="utf-8"))["segments"][0]["text"] == "Hola"
    assert res["video"].endswith("clip_dub_es.mp4")


def test_dub_video_rejects_same_language_and_unknown_language(tmp_path, transcript):
    with pytest.raises(ValueError):
        dubbing.dub_video("clip.mp4", "en", str(tmp_path), transcribe=lambda: transcript)
    with pytest.raises(ValueError):
        dubbing.dub_video("clip.mp4", "xx", str(tmp_path), transcribe=lambda: transcript)


def test_dub_video_fails_loudly_without_llm(tmp_path, transcript):
    def boom(prompt):
        raise RuntimeError("down")
    with pytest.raises(RuntimeError, match="Translation failed"):
        dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=boom)


def test_dub_video_fails_when_no_voice(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    monkeypatch.setattr(dubbing, "_parse", json.loads)
    llm = lambda prompt: json.dumps({"translations": [{"id": 0, "text": "a"}, {"id": 1, "text": "b"}]})  # noqa: E731

    def synth(text, out):
        raise RuntimeError("offline")
    with pytest.raises(RuntimeError, match="No voice"):
        dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=synth)


def test_failed_voices_are_not_kept_as_empty_files_and_the_403_cause_is_named(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    llm = lambda prompt: json.dumps({"translations": [{"id": 0, "text": "Hola"}, {"id": 1, "text": "Bienvenido"}]})  # noqa: E731
    monkeypatch.setattr(dubbing, "_parse", json.loads)

    def broken(text, out):
        open(out, "wb").close()                                   # what a rejected request leaves behind: an empty file
        raise RuntimeError("403, message='Invalid response status'")

    with pytest.raises(RuntimeError, match="pip install -U edge-tts"):
        dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=broken)
    assert os.listdir(tmp_path / "dub_clips") == []                                   # no empty files left behind

    def empty(text, out):
        open(out, "wb").close()                                   # "succeeds" but writes nothing
    with pytest.raises(RuntimeError, match="No voice|rejected"):
        dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=empty)


def test_voice_failure_message_generic_and_specific():
    from engine.dubbing import voice_failure_message
    assert "pip install -U edge-tts" in voice_failure_message(["WSServerHandshakeError 403"])
    assert "needs internet" in voice_failure_message(["timeout"]) and "needs internet" in voice_failure_message([])


def _placements():
    return [{"index": 1, "start": 1.0, "tempo": 1.0}, {"index": 2, "start": 5.0, "tempo": 1.2}]


def test_original_sound_options_in_the_filter():
    quiet = dubbing.build_filter(_placements(), 20.0, True, "quiet")
    duck = dubbing.build_filter(_placements(), 20.0, True, "duck")
    mute = dubbing.build_filter(_placements(), 20.0, True, "mute")
    assert "volume=0.12[orig]" in quiet and "sidechaincompress" in quiet and "[0:a]" in quiet      # faint bed + lowered under the voice
    assert "volume=" not in duck.split("[orig]")[0].split("[0:a]")[-1] and "sidechaincompress" in duck
    assert "[0:a]" not in mute and "sidechaincompress" not in mute and "[aout]" in mute              # original removed entirely
    assert dubbing.build_filter(_placements(), 20.0, True) == quiet                                  # quiet is the default
    assert "[0:a]" not in dubbing.build_filter(_placements(), 20.0, False)                           # no source audio: nothing to mix


def test_coverage_warning_when_little_speech_was_recognised():
    segs = [{"start": 1.7, "end": 3.0}, {"start": 31.0, "end": 32.0}]
    msg = dubbing.coverage_warning(segs, 45.0)
    assert "only 2 s of the 45 s" in msg and "SHORTSFLOW_WHISPER_MODEL=large-v3" in msg
    assert dubbing.coverage_warning([{"start": 0, "end": 30}], 45.0) is None                         # most of the video is speech
    assert dubbing.coverage_warning(segs, 3.0) is None and dubbing.coverage_warning([], 45.0) is None


def test_dub_args_original_option():
    from shortsflow import web_args
    assert "--dub_original" not in web_args.dub_args("a.mp4", "en")                                  # the default needs no flag
    assert web_args.dub_args("a.mp4", "en", original="mute")[-2:] == ["--dub_original", "mute"]
    assert web_args.dub_args("a.mp4", "en", original="duck", session_dir="s")[-4:-2] == ["--dub_original", "duck"]


def test_a_second_run_reuses_the_saved_translation_and_finished_voices(tmp_path, monkeypatch, transcript):
    """A dub that crashed in the final mix is run again in the same folder: no AI text call, no voice call."""
    _fake_media(monkeypatch)
    monkeypatch.setattr(dubbing, "_parse", json.loads)
    llm = lambda prompt: json.dumps({"translations": [{"id": 0, "text": "Hola"}, {"id": 1, "text": "Bienvenido"}]})  # noqa: E731
    voiced = []

    def synth(text, out):
        voiced.append(text)
        open(out, "wb").write(b"x" * 500)

    def crashing_mixer(src, clips, out, session_dir, burn_srt=None):
        raise OSError("[WinError 206] The filename or extension is too long")

    with pytest.raises(OSError):
        dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=synth, mixer=crashing_mixer)
    assert len(voiced) == 2

    def no_llm(prompt):
        raise AssertionError("the AI text service must not be called again")

    def no_voice(text, out):
        raise AssertionError("a finished voice clip must not be made again")

    def mixer(src, clips, out, session_dir, burn_srt=None):
        open(out, "wb").write(b"video")

    res = dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=no_llm, synth=no_voice, mixer=mixer)
    assert res["failed_translations"] == 0 and res["failed_voices"] == 0
    assert "Bienvenido" in open(res["srt"], encoding="utf-8").read()


def test_saved_translation_is_ignored_when_it_does_not_match(tmp_path):
    path = tmp_path / "x_es.json"
    segs = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 3.0, "end": 5.0, "text": "b"}]
    path.write_text(json.dumps({"target_lang": "es", "segments": [dict(s, text="t") for s in segs]}), encoding="utf-8")
    assert dubbing.saved_translation(str(path), "es", segs) == ["t", "t"]
    assert dubbing.saved_translation(str(path), "fr", segs) is None                       # another language
    assert dubbing.saved_translation(str(path), "es", segs[:1]) is None                   # another number of lines
    assert dubbing.saved_translation(str(path), "es", [dict(segs[0], start=9.0), segs[1]]) is None   # different timing
    assert dubbing.saved_translation(str(tmp_path / "missing.json"), "es", segs) is None


def _prompt_for(tone, segments=None):
    seen = []
    segs = segments or [{"start": 0.0, "end": 2.0, "text": "Hello there"}]

    def llm(prompt):
        seen.append(prompt)
        return json.dumps({"translations": [{"id": 0, "text": "Hola"}]})

    import json as _j
    old = dubbing._parse
    dubbing._parse = _j.loads
    try:
        dubbing.translate_segments(segs, "es", llm=llm, tone=tone) if tone is not None else dubbing.translate_segments(segs, "es", llm=llm)
    finally:
        dubbing._parse = old
    return seen[0]


def test_default_tone_leaves_the_translation_prompt_exactly_as_it_was():
    plain = _prompt_for(None)
    assert _prompt_for("faithful") == plain and _prompt_for("nonsense") == plain
    assert "Rewrite each line" not in plain
    assert "Keep the meaning and tone." in plain


def test_a_chosen_tone_adds_one_instruction():
    for tone in ("funny", "sarcastic", "dramatic", "formal", "casual"):
        prompt = _prompt_for(tone)
        assert dubbing.TONES[tone] in prompt and "keep the meaning and every fact" in prompt


def test_neutral_delivery_calls_the_voice_exactly_as_before_and_others_set_speed_and_pitch(tmp_path, monkeypatch):
    import sys
    import types
    calls = []

    class Fake:
        def __init__(self, *a, **k):
            calls.append((a, k))

        async def save(self, out):
            open(out, "wb").write(b"x" * 300)

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Fake))
    dubbing.synthesize("hola", "es", str(tmp_path / "a.mp3"))
    dubbing.synthesize("hola", "es", str(tmp_path / "b.mp3"), delivery="neutral")
    dubbing.synthesize("hola", "es", str(tmp_path / "c.mp3"), delivery="excited")
    assert calls[0] == calls[1] and calls[0][1] == {}                 # no rate or pitch: the old call
    assert calls[2][1] == {"rate": "+12%", "pitch": "+3Hz"}


def test_web_and_cli_flags_appear_only_for_a_chosen_tone_or_delivery():
    from shortsflow import web_args
    base = web_args.dub_args("v.mp4", "es")
    assert "--dub_tone" not in base and "--dub_delivery" not in base
    assert web_args.dub_args("v.mp4", "es", tone="faithful", delivery="neutral") == base
    more = web_args.dub_args("v.mp4", "es", tone="sarcastic", delivery="calm")
    assert more[more.index("--dub_tone") + 1] == "sarcastic" and more[more.index("--dub_delivery") + 1] == "calm"
    assert [v for _, v in web_args.DUB_TONE_CHOICES] == list(dubbing.TONES)
    assert [v for _, v in web_args.DUB_DELIVERY_CHOICES] == list(dubbing.DELIVERIES)


def _dub(tmp_path, transcript, llm, synth, **kw):
    def mixer(src, clips, out, session_dir, burn_srt=None):
        open(out, "wb").write(b"video")
    return dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=synth, mixer=mixer, **kw)


def test_resume_is_safe_with_tones_deliveries_and_old_sessions(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    monkeypatch.setattr(dubbing, "_parse", json.loads)
    asked, voiced = [], []

    def llm(prompt):
        asked.append(prompt)
        return json.dumps({"translations": [{"id": 0, "text": "Hola"}, {"id": 1, "text": "Bienvenido"}]})

    def synth(text, out):
        voiced.append(text)
        open(out, "wb").write(b"x" * 500)

    _dub(tmp_path, transcript, llm, synth)                                   # first run: 1 translation call, 2 voices
    assert len(asked) == 1 and len(voiced) == 2
    _dub(tmp_path, transcript, llm, synth)                                   # same settings: everything reused
    assert len(asked) == 1 and len(voiced) == 2
    _dub(tmp_path, transcript, llm, synth, delivery="calm")                  # same translation, new delivery: voices again, no translation
    assert len(asked) == 1 and len(voiced) == 4
    _dub(tmp_path, transcript, llm, synth, delivery="calm")                  # and that is reused in turn
    assert len(voiced) == 4
    _dub(tmp_path, transcript, llm, synth, tone="sarcastic", delivery="calm")   # another tone: translated and voiced again
    assert len(asked) == 2 and len(voiced) == 6


def test_a_session_saved_before_tones_existed_still_resumes(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    monkeypatch.setattr(dubbing, "_parse", json.loads)
    segs = dubbing.segments_from_transcript(json.load(open(transcript, encoding="utf-8")))
    old = {"target_lang": "es", "source_lang": "en", "segments": [dict(s, text="viejo") for s in segs]}   # no tone, no delivery keys
    (tmp_path / "clip_es.json").write_text(json.dumps(old), encoding="utf-8")
    (tmp_path / "dub_clips").mkdir()
    for i in range(len(segs)):
        (tmp_path / "dub_clips" / f"seg_{i:04d}.mp3").write_bytes(b"x" * 500)                  # clips without a .voice note

    def no_llm(prompt):
        raise AssertionError("must not translate again")

    def no_voice(text, out):
        raise AssertionError("must not voice again")

    res = _dub(tmp_path, transcript, no_llm, no_voice)
    assert res["failed_translations"] == 0 and res["failed_voices"] == 0
