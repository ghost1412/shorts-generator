import os

from engine import video_gen as vg


def _piece(tmp_path, name="seg_0.mp4", size=2000):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return str(path)


def test_key_changes_with_moment_source_and_settings(tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(b"abc")
    hi = {"start": 10.0, "end": 40.0}
    base = vg.segment_key(str(src), hi, layout="single", aspect="9:16")
    assert base == vg.segment_key(str(src), dict(hi), layout="single", aspect="9:16")
    assert base != vg.segment_key(str(src), {"start": 11.0, "end": 40.0}, layout="single", aspect="9:16")
    assert base != vg.segment_key(str(src), hi, layout="fit", aspect="9:16")
    assert base != vg.segment_key(str(src), hi, layout="single", aspect="1:1")
    src.write_bytes(b"abcd")                                    # the source file changed
    assert base != vg.segment_key(str(src), hi, layout="single", aspect="9:16")


def test_a_piece_is_only_trusted_with_a_matching_key(tmp_path):
    piece = _piece(tmp_path)
    assert not vg.segment_is_cached(piece, "k1")                # no key file (older version, or copied from another run)
    vg.write_segment_key(piece, "k1")
    assert vg.segment_is_cached(piece, "k1")
    assert not vg.segment_is_cached(piece, "k2")                # other moments or settings
    assert not vg.segment_is_cached(str(tmp_path / "missing.mp4"), "k1")


def test_a_tiny_or_broken_piece_is_never_trusted(tmp_path):
    piece = _piece(tmp_path, size=10)
    vg.write_segment_key(piece, "k1")
    assert not vg.segment_is_cached(piece, "k1")


def test_seeding_a_new_run_carries_the_key_files(tmp_path):
    from shortsflow import reuse
    old = tmp_path / "old" / "temp_segments"
    old.mkdir(parents=True)
    (tmp_path / "old" / "transcript.json").write_text("{}", encoding="utf-8")
    (old / "seg_0.mp4").write_bytes(b"x" * 2000)
    (old / "seg_0.mp4.key").write_text("k1", encoding="utf-8")
    new = tmp_path / "new"
    new.mkdir()
    reuse.seed_session(str(tmp_path / "old"), str(new), keep_moments=True)
    assert (new / "temp_segments" / "seg_0.mp4.key").read_text() == "k1"
