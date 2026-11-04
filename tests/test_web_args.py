import os

import pytest

from shortsflow import onboarding, web_args


def test_extras_args_only_adds_what_is_ticked():
    assert web_args.extras_args() == []
    assert web_args.extras_args(clean_audio=True) == ["--clean_audio"]
    assert web_args.extras_args(True, True, True) == ["--clean_audio", "--hook_overlay", "--caption_emoji"]


def test_hook_and_emoji_are_dropped_without_animated_captions():
    assert web_args.extras_args(True, True, True, use_remotion=False) == ["--clean_audio"]


def test_filler_only_goes_with_the_split_filler_layout():
    assert web_args.filler_args("split_filler", "/x/gameplay.mp4") == ["--filler_video", "/x/gameplay.mp4"]
    assert web_args.filler_args("single", "/x/gameplay.mp4") == []
    assert web_args.filler_args("split_filler", None) == []
    assert web_args.filler_args("split_filler", "  ") == []


def test_dub_args_minimal_and_full():
    assert web_args.dub_args("a.mp4", "es") == ["--mode", "DUB", "--source_video", "a.mp4", "--target_lang", "es", "--language", "auto"]
    full = web_args.dub_args("a.mp4", "hi", "en", True, "sessions/dub_1")
    assert "--dub_captions" in full and full[-2:] == ["--session_dir", "sessions/dub_1"]
    assert full[full.index("--language") + 1] == "en"


def test_dub_languages_match_the_engine():
    from engine.dubbing import supported_languages
    codes = [c for _, c in web_args.dub_languages()]
    assert sorted(codes) == sorted(supported_languages())
    assert ("Spanish", "es") in web_args.dub_languages()


def test_find_dub_outputs(tmp_path):
    assert web_args.find_dub_outputs(str(tmp_path)) == (None, None)
    (tmp_path / "talk_dub_es.mp4").write_bytes(b"x")
    (tmp_path / "talk_es.srt").write_text("1")
    video, srt = web_args.find_dub_outputs(str(tmp_path))
    assert os.path.basename(video) == "talk_dub_es.mp4" and os.path.basename(srt) == "talk_es.srt"


def test_dub_progress_moves_forward_only():
    p = onboarding.Progress(steps=onboarding.DUB_STEPS)
    assert "Getting your video" in p.message
    assert "Listening" in p.feed("[Log] Transcribing audio with Whisper...")
    assert "Translating" in p.feed("[Log] Dubbing 12 spoken segment(s) into Spanish...")
    assert "Translating" in p.feed("[Log] Transcribing again")   # never goes back
    assert "Done" in p.feed("[Success] Dubbed video ready at: x.mp4")


def test_default_progress_is_unchanged():
    p = onboarding.Progress()
    assert "Listening" in p.feed("Transcribing")
    assert "Translating" not in p.feed("Dubbing 3 spoken segment(s) into Spanish...")


# --- webui wiring (needs gradio; run with py -3.12) -------------------------------------------------

@pytest.fixture
def webui(monkeypatch, tmp_path):
    pytest.importorskip("gradio")
    import webui as w
    monkeypatch.setattr(w, "ROOT", str(tmp_path))
    monkeypatch.setattr(w, "_pipeline_cmd", lambda: ["py", "main.py"])
    seen = {}

    def fake_run(cmd):
        seen["cmd"] = cmd
        yield "", []
    monkeypatch.setattr(w, "_run", fake_run)
    w.seen = seen
    return w


def _drain(gen):
    return list(gen)


def test_quick_clip_passes_the_extras(webui):
    _drain(webui.quick_clip("http://x/y", None, 2, True, "HORMOZI", False, clean_audio=True, hook_overlay=True,
                            caption_emoji=True, filler=True, filler_video="/g.mp4"))
    cmd = webui.seen["cmd"]
    assert cmd[cmd.index("--layout") + 1] == "split_filler"
    assert cmd[cmd.index("--filler_video") + 1] == "/g.mp4"
    for flag in ("--clean_audio", "--hook_overlay", "--caption_emoji", "--use_remotion"):
        assert flag in cmd


def test_quick_clip_default_command_has_no_extras(webui):
    _drain(webui.quick_clip("http://x/y", None, 2, True, "HORMOZI", False))
    cmd = webui.seen["cmd"]
    assert cmd[cmd.index("--layout") + 1] == "auto"
    for flag in ("--clean_audio", "--hook_overlay", "--caption_emoji", "--filler_video"):
        assert flag not in cmd


def test_quick_clip_without_captions_skips_remotion_only_extras(webui):
    _drain(webui.quick_clip("http://x/y", None, 2, False, "HORMOZI", False, clean_audio=True, hook_overlay=True, caption_emoji=True))
    cmd = webui.seen["cmd"]
    assert "--clean_audio" in cmd and "--hook_overlay" not in cmd and "--caption_emoji" not in cmd


def test_clip_video_passes_the_extras(webui):
    _drain(webui.clip_video("http://x/y", None, 2, 30, "split_filler", True, True, False, False,
                            "HORMOZI", "9:16", True, "auto", "auto", True, True, False, "/g.mp4"))
    cmd = webui.seen["cmd"]
    assert "--clean_audio" in cmd and "--hook_overlay" in cmd and "--caption_emoji" not in cmd
    assert cmd[cmd.index("--filler_video") + 1] == "/g.mp4"


def test_dub_requires_a_video_and_a_language(webui):
    import gradio as gr
    with pytest.raises(gr.Error):
        _drain(webui.dub_video(None, "", "es"))
    with pytest.raises(gr.Error):
        _drain(webui.dub_video(None, "http://x/y", ""))


def test_dub_builds_the_command_and_reports_the_result(webui, tmp_path):
    def fake_run(cmd):
        webui.seen["cmd"] = cmd
        session = cmd[cmd.index("--session_dir") + 1]
        with open(os.path.join(session, "talk_dub_es.mp4"), "wb") as f:
            f.write(b"x")
        with open(os.path.join(session, "talk_es.srt"), "w") as f:
            f.write("1")
        yield "[Log] Dubbing 3 spoken segment(s) into Spanish...\n[Success] Dubbed video ready at: x\n", []
    webui._run = fake_run
    out = _drain(webui.dub_video(None, "http://x/y", "es", "en", True, "edgetts"))
    cmd = webui.seen["cmd"]
    assert cmd[:3] == ["py", "main.py", "--mode"] and cmd[3] == "DUB"
    assert "--dub_captions" in cmd and cmd[cmd.index("--tts_provider") + 1] == "edgetts"
    status, _log, video, srt = out[-1]
    assert status.startswith("✅") and "Spanish" in status
    assert video.endswith("talk_dub_es.mp4") and srt.endswith("talk_es.srt")


def test_dub_voice_and_engine_choices_become_flags(webui):
    base = web_args.dub_args("a.mp4", "es")
    assert "--dub_voice" not in base and "--tts_provider" not in base
    assert web_args.dub_args("a.mp4", "es", voice="male")[-2:] == ["--dub_voice", "male"]
    both = web_args.dub_args("a.mp4", "en", tts_provider="kokoro", voice="female")
    assert both[both.index("--dub_voice") + 1] == "female" and both[both.index("--tts_provider") + 1] == "kokoro"
    assert [v for _, v in web_args.DUB_VOICE_CHOICES] == ["auto", "female", "male"]
    assert [v for _, v in web_args.DUB_PROVIDER_CHOICES] == ["auto", "edgetts", "kokoro"]

    def fake_run(cmd):
        webui.seen["cmd"] = cmd
        yield "[Error] stop\n", []
    webui._run = fake_run
    _drain(webui.dub_video(None, "http://x/y", "es", "en", False, "kokoro", "male"))
    cmd = webui.seen["cmd"]
    assert cmd[cmd.index("--dub_voice") + 1] == "male" and cmd[cmd.index("--tts_provider") + 1] == "kokoro"


def test_dub_failure_shows_the_engine_error(webui):
    def fake_run(cmd):
        yield "[Error] The video is already in 'es'; choose another --target_lang.\n", []
    webui._run = fake_run
    status = _drain(webui.dub_video(None, "http://x/y", "es"))[-1][0]
    assert status.startswith("❌") and "already in 'es'" in status


def test_the_ui_has_the_dub_tab_and_extras():
    pytest.importorskip("gradio")
    import webui as w
    demo = w.build_ui()
    labels = {getattr(b, "label", None) for b in demo.blocks.values()}
    assert "Dub into" in labels and "Clean up the sound" in labels and "Clean audio" in labels


def test_cold_open_flag_in_extras():
    from shortsflow import web_args
    assert "--cold_open" in web_args.extras_args(cold_open=True)
    assert "--cold_open" not in web_args.extras_args()


def test_shared_or_network_webui_always_gets_a_login():
    from shortsflow import web_args
    import pytest
    assert web_args.resolve_auth(None, False, "127.0.0.1") is None                      # local only: no login needed
    user, pw = web_args.resolve_auth(None, True, "127.0.0.1")                          # --share: generated
    assert user == "shortsflow" and len(pw) >= 8
    assert web_args.resolve_auth(None, False, "0.0.0.0")[0] == "shortsflow"             # listening on the network: generated
    assert web_args.resolve_auth("me:secret", True) == ("me", "secret")
    with pytest.raises(SystemExit):
        web_args.resolve_auth("nopassword", True)


def test_photo_reel_command_and_staging(tmp_path):
    from PIL import Image
    from shortsflow import web_args
    a, b = tmp_path / "b.jpg", tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(a)
    Image.new("RGB", (8, 8)).save(b)
    (tmp_path / "notes.txt").write_text("x")
    folder = web_args.stage_photos([str(a), str(b), str(tmp_path / "notes.txt")], str(tmp_path / "stage"))
    assert sorted(os.listdir(folder)) == ["001_b.jpg", "002_a.png"]                      # order kept, non-images ignored
    cmd = web_args.photo_reel_args(folder, "countdown", " Top places ", "best | good", "song.mp3", 30, "sessions/x")
    assert cmd[:4] == ["--mode", "PHOTO_REEL", "--photos_dir", folder] and "--skip_upload" in cmd
    assert cmd[cmd.index("--reel_type") + 1] == "countdown" and cmd[cmd.index("--prompt") + 1] == "Top places"
    assert [cmd[i + 1] for i, c in enumerate(cmd) if c == "--reel_text"] == ["best", "good"]
    assert cmd[cmd.index("--music") + 1] == "song.mp3" and cmd[cmd.index("--target_duration") + 1] == "30"
    plain = web_args.photo_reel_args(folder, "memories")
    assert "--prompt" not in plain and "--music" not in plain and "--reel_text" not in plain


def test_edit_args():
    from shortsflow import web_args
    assert web_args.edit_args("none") == [] and web_args.edit_args("") == []
    assert web_args.edit_args("hype", "hyped") == ["--auto_edit", "hype", "--edit_strength", "hyped"]
    assert web_args.edit_args("vlog", "loud") == ["--auto_edit", "vlog", "--edit_strength", "medium"]


def test_stat_pops_flag_in_extras():
    from shortsflow import web_args
    assert "--stat_pops" in web_args.extras_args(stat_pops=True) and "--stat_pops" not in web_args.extras_args()
    assert "--stat_pops" not in web_args.extras_args(use_remotion=False, stat_pops=True)    # drawn by Remotion only


def test_trip_args():
    a = web_args.trip_args(["a.mp4", "b.mp4"], "sess", name=" Almaty ", stops="Kolsai, Kaindy", note="", hook="Woke up", length=5, style="plain")
    assert a[:4] == ["--mode", "TRIP", "--trip_videos", "a.mp4"]
    assert "--trip_name" in a and a[a.index("--trip_name") + 1] == "Almaty"
    assert "--user_context" not in a and a[a.index("--recap_length") + 1] == "20"      # empty note left out, length clamped
    assert "--recap_style" in a and web_args.trip_args(["a.mp4"], "s").count("--recap_style") == 0
