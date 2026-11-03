import shutil
import subprocess

import pytest

from engine.reel_captions import ass_document, burn_captions, reel_words

TRANSCRIPT = {"segments": [{"words": [
    {"word": " hello", "start": 10.0, "end": 10.4},
    {"word": " there", "start": 10.5, "end": 11.0},
    {"word": " later", "start": 50.0, "end": 50.5},
    {"word": " words", "start": 51.0, "end": 51.4},
]}]}


def test_words_are_placed_on_the_reel_timeline_with_crossfade_overlap():
    # segment A = source 10-12 (2 s), segment B = source 50-52 (2 s), 0.25 s crossfade
    words = reel_words([(10.0, 12.0, 2.0), (50.0, 52.0, 2.0)], TRANSCRIPT, xf=0.25)
    assert [w[2] for w in words] == ["hello", "there", "later", "words"]
    assert words[0][0] == 0.0 and abs(words[1][0] - 0.5) < 1e-9
    assert abs(words[2][0] - (2.0 - 0.25)) < 1e-9          # B starts at 1.75 on the reel
    assert abs(words[3][0] - (1.75 + 1.0)) < 1e-9


def test_words_outside_a_segment_are_dropped_and_never_overlap():
    words = reel_words([(10.0, 10.8, 0.8)], TRANSCRIPT)
    assert [w[2] for w in words] == ["hello", "there"]
    for (s1, e1, _), (s2, e2, _) in zip(words, words[1:]):
        assert e1 <= s2 + 1e-9


def test_ass_document_has_one_dialogue_line_per_word_and_escapes_override_braces():
    doc = ass_document([(0.0, 0.5, "hi"), (0.5, 1.25, "{x}")], size=(1920, 1080))
    assert doc.count("Dialogue:") == 2 and "PlayResX: 1920" in doc
    assert "Dialogue: 0,0:00:00.00,0:00:00.50,Default,,0,0,0,,HI" in doc
    assert "{x}" not in doc and ",X\n" in doc


def test_burn_captions_produces_a_playable_video(tmp_path):
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg not installed")
    src = tmp_path / "in.mp4"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "color=c=gray:size=640x360:rate=25:duration=3", "-f", "lavfi",
                    "-i", "sine=frequency=300:duration=3", "-shortest", str(src)], check=True, capture_output=True)
    ass = tmp_path / "c.ass"
    ass.write_text(ass_document([(0.2, 1.5, "hello"), (1.5, 2.8, "world")], size=(640, 360)), encoding="utf-8")
    out = tmp_path / "out.mp4"
    assert burn_captions(str(src), str(ass), str(out), codec="libx264")
    # the caption must really be on the picture: frame at 1 s differs from the plain frame
    def frame(path):
        return subprocess.run([ff, "-ss", "1", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                              capture_output=True).stdout
    assert frame(src) != frame(out)


def _clip(ff, path, seconds, freq, color):
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", f"color=c={color}:size=320x180:rate=30:duration={seconds}", "-f", "lavfi",
                    "-i", f"sine=frequency={freq}:duration={seconds}", "-shortest", str(path)], check=True, capture_output=True)


def _duration(ff, path, stream):
    import re
    err = subprocess.run([ff, "-i", str(path), "-map", f"0:{stream}", "-f", "null", "-"], capture_output=True, text=True).stderr
    h, m, s = re.findall(r"time=(\d+):(\d+):([\d.]+)", err)[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def test_render_reel_crossfades_segments_and_keeps_audio(tmp_path):
    from engine.reel_captions import render_reel
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg not installed")
    paths = []
    for i, (freq, color) in enumerate([(300, "red"), (500, "green"), (700, "blue")]):
        p = tmp_path / f"s{i}.mp4"
        _clip(ff, p, 3, freq, color)
        paths.append(p)
    out = tmp_path / "reel.mp4"
    assert render_reel([str(p) for p in paths], [3.0, 3.0, 3.0], str(out), xf=0.25, codec="libx264")
    assert abs(_duration(ff, out, "v:0") - (9 - 2 * 0.25)) < 0.2     # overlaps removed
    assert abs(_duration(ff, out, "a:0") - (9 - 2 * 0.25)) < 0.3


def test_render_reel_single_segment_and_captions_in_the_same_pass(tmp_path):
    from engine.reel_captions import render_reel
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg not installed")
    p = tmp_path / "only.mp4"
    _clip(ff, p, 3, 400, "gray")
    ass = tmp_path / "c.ass"
    ass.write_text(ass_document([(0.2, 2.8, "hello")], size=(320, 180)), encoding="utf-8")
    out = tmp_path / "reel.mp4"
    assert render_reel([str(p)], [3.0], str(out), ass_path=str(ass), codec="libx264")
    def frame(path):
        return subprocess.run([ff, "-ss", "1", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                              capture_output=True).stdout
    assert frame(p) != frame(out)


def test_render_reel_rejects_mismatched_inputs(tmp_path):
    from engine.reel_captions import render_reel
    assert render_reel([], [], str(tmp_path / "x.mp4")) is False
    assert render_reel(["a.mp4"], [1.0, 2.0], str(tmp_path / "x.mp4")) is False


def test_devanagari_words_name_the_bundled_font():
    doc = ass_document([(0.0, 0.5, "hello"), (0.5, 1.0, "नमस्ते")], size=(1920, 1080))
    assert ",,HELLO\n" in doc
    assert ",,{\\fnNoto Sans Devanagari}नमस्ते\n" in doc
