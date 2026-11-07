import shutil
import subprocess

import numpy as np
import pytest

from engine import subject_cut as sc
from engine import transitions as tx
from engine import trip_recap as tr

FF = shutil.which("ffmpeg")
SIZE = (320, 180)
ENC = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-ar", "44100", "-ac", "2"]


def _box_mask(frames):
    out = []
    for f in frames:
        m = np.zeros(f.shape[:2], np.float32)
        m[40:150, 110:210] = 1.0                 # a person-sized block in the middle
        out.append(m)
    return out


def _clip(path, seconds, color, freq=400):
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:size=320x180:rate=30:duration={seconds}", "-f", "lavfi",
                    "-i", f"sine=frequency={freq}:duration={seconds}", *ENC, "-shortest", str(path)], check=True)


def test_subject_is_a_transition_with_a_normal_fallback():
    assert tx.validate("subject") == "subject" and ("Subject cut-out (the person stays, the background changes)", "subject") in tx.LABELS
    assert tx.cut_types("subject", 3) == ["subject"] * 3
    assert tx.fallback_type(0) in ("punch", "whip", "glitch", "flash") and tx.fallback_type(6) == tx.fallback_type(0)
    assert tx.clip_effect("subject", "subject", 4.0, 0.2, 320, 180) == ("", "", "")       # the bridge makes the effect, not the shot
    assert "fade" not in tx.xfade_names("subject", 6)


def test_clear_subject_needs_a_person_of_sensible_size():
    big, small, none = np.ones((10, 10), np.float32), np.zeros((100, 100), np.float32), np.zeros((10, 10), np.float32)
    small[30:70, 30:70] = 1.0
    assert sc.clear_subject([small, small]) and not sc.clear_subject([none]) and not sc.clear_subject([big]) and not sc.clear_subject([])
    assert not sc.clear_subject([small, none, none])                     # the person walks out of the frame: no cut-out
    assert sc.clear_subject([small] * 9 + [none]) and not sc.clear_subject([small] * 3 + [none] * 2)       # one missed frame in ten is fine


def test_compose_keeps_the_person_and_reveals_the_next_shot():
    a = [np.full((90, 160, 3), 200, np.uint8)] * 10
    b = [np.full((90, 160, 3), 20, np.uint8)] * 10
    for f in a:
        f[:, 70:90] = (255, 0, 0)
    masks = []
    for _ in a:
        m = np.zeros((90, 160), np.float32)
        m[:, 70:90] = 1.0
        masks.append(m)
    out = sc.compose(a, b, masks)
    assert len(out) == 10 and out[0].shape == (90, 160, 3)
    assert out[0][45, 5, 0] > 150 and out[9][45, 5, 0] < 80                # background: A first, B at the end
    assert out[1][45, 80, 0] > 200 and out[1][45, 80, 1] < 60               # the person is still red and in front early on


@pytest.mark.skipif(not FF, reason="needs ffmpeg")
def test_apply_adds_a_bridge_that_overlaps_both_shots(tmp_path):
    a, b, c = tmp_path / "clip_1.mp4", tmp_path / "clip_2.mp4", tmp_path / "card_1.mp4"
    _clip(a, 3, "red"), _clip(b, 3, "blue", 600), _clip(c, 2, "green", 800)
    parts = [str(a), str(b), str(c)]
    before = sum(sc._duration(FF, p) for p in parts)
    new, made = sc.apply(FF, parts, {(str(a), str(b))}, SIZE, ENC, str(tmp_path / "w"), masks_fn=_box_mask)
    assert made == 1 and len(new) == 4 and new[1].endswith("bridge_0.mp4") and new[2].endswith("trim_1_clip_2.mp4") and new[3] == str(c)
    assert abs(sum(sc._duration(FF, p) for p in new) - (before - sc.BRIDGE_S)) < 0.25      # like a crossfade: the bridge covers the end of A and the start of B
    same, none_made = sc.apply(FF, parts, {(str(a), str(b))}, SIZE, ENC, str(tmp_path / "w2"), masks_fn=lambda fr: [np.zeros(f.shape[:2], np.float32) for f in fr])
    assert none_made == 0 and same == parts                                # no person: untouched plain cut


@pytest.mark.skipif(not FF, reason="needs ffmpeg")
def test_apply_skips_shots_that_are_too_short(tmp_path):
    a, b = tmp_path / "clip_1.mp4", tmp_path / "clip_2.mp4"
    _clip(a, 1, "red"), _clip(b, 3, "blue")
    new, made = sc.apply(FF, [str(a), str(b)], {(str(a), str(b))}, SIZE, ENC, str(tmp_path / "w"), masks_fn=_box_mask)
    assert made == 0 and new == [str(a), str(b)]


def test_cut_sounds_follow_the_bridge_not_the_trimmed_shots():
    parts = [("p/clip_1.mp4", 3.5), ("p/bridge_0.mp4", 0.5), ("w/trim_2_clip_2.mp4", 3.5), ("p/clip_3.mp4", 4.0), ("p/end.mp4", 3.0)]
    events = tr.cut_sound_events(parts, "whoosh")
    assert [e["t"] for e in events] == [3.5, 7.5]          # the bridge start and the plain cut before clip_3; none after the bridge


def test_frames_are_laid_out_like_the_render():
    wide = np.full((90, 160, 3), 200, np.uint8)
    fit = sc.frame_like_render(wide, (90, 160), crop=False)             # 16:9 source into a 9:16 recap: letterboxed, black bars above and below
    assert fit.shape == (160, 90, 3) and fit[0, 0].sum() == 0 and fit[80, 45, 0] == 200
    crop = sc.frame_like_render(wide, (90, 160), crop=True)             # centre crop: no bars
    assert crop.shape == (160, 90, 3) and crop.min() == 200


def test_has_person_jpegs_is_false_without_frames_or_on_bad_data():
    assert not sc.has_person_jpegs([]) and not sc.has_person_jpegs([b"not a jpeg"])


def test_letterbox_box_is_the_sharp_picture_inside_the_bars():
    assert sc.letterbox_box((1920, 1080), (1080, 1920)) == (656, 1264, 0, 1080)        # landscape shot in a portrait frame: bars above and below
    assert sc.letterbox_box((1080, 1920), (1080, 1920)) == (0, 1920, 0, 1080)
    assert sc.letterbox_box((0, 0), (1080, 1920)) == (0, 1920, 0, 1080)


def test_text_is_taken_out_of_the_person_layer(tmp_path):
    cv2 = pytest.importorskip("cv2")
    png = np.zeros((90, 160, 4), np.uint8)
    png[40:50, 20:140] = (255, 255, 255, 255)                                            # a title line
    path = str(tmp_path / "t.png")
    cv2.imwrite(path, png)
    tm = sc.text_mask([path, str(tmp_path / "missing.png")], (160, 90))
    assert tm is not None and tm[45, 80] == 255 and tm[5, 5] == 0 and sc.text_mask([], (160, 90)) is None
    frame = np.full((90, 160, 3), 60, np.uint8)
    frame[40:50, 20:140] = 255
    clean = sc.without_text(frame, tm)
    assert clean[45, 80].max() < 120 and clean[5, 5].tolist() == [60, 60, 60]


def test_person_is_only_looked_for_inside_the_box(monkeypatch):
    monkeypatch.setattr(sc, "person_mask", lambda rgb, long_side=480: np.ones(rgb.shape[:2], np.float32))
    frames = [np.zeros((100, 60, 3), np.uint8)] * 2
    m = sc.masks_for(frames, (30, 70, 0, 60))[0]
    assert m[50, 30] == 1.0 and m[10, 30] == 0.0 and m[90, 30] == 0.0
