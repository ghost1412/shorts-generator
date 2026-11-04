import json
import random

from engine import filler, video_gen


def test_graph_stacks_clip_over_filler():
    g = filler.build_filler_split_graph("null", 1080, 1920)
    assert g.startswith("[0:v]null,scale=1080:960")
    assert "[1:v]scale=1080:960" in g
    assert "vstack=inputs=2" in g and g.endswith("[v]")


def test_find_local_filler_filters_videos(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    assert filler.find_local_filler(str(tmp_path), random.Random(1)).endswith("a.mp4")
    assert filler.find_local_filler(str(tmp_path / "missing")) is None


def test_resolve_order(tmp_path, monkeypatch):
    explicit = tmp_path / "mine.mp4"
    explicit.write_bytes(b"x")
    assert filler.resolve_filler_video(str(explicit), str(tmp_path)) == str(explicit)

    monkeypatch.setattr(filler, "find_local_filler", lambda *a, **k: "local.mp4")
    assert filler.resolve_filler_video(str(tmp_path / "gone.mp4"), str(tmp_path)) == "local.mp4"

    monkeypatch.setattr(filler, "find_local_filler", lambda *a, **k: None)
    monkeypatch.setattr(filler, "download_stock_filler", lambda out: "stock.mp4")
    assert filler.resolve_filler_video(None, str(tmp_path)) == "stock.mp4"

    monkeypatch.setattr(filler, "download_stock_filler", lambda out: None)
    assert filler.resolve_filler_video(None, str(tmp_path)) is None


def test_stock_needs_key(monkeypatch, tmp_path):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert filler.download_stock_filler(str(tmp_path / "f.mp4")) is None


def _run_extract(monkeypatch, tmp_path, layout, filler_path):
    cmds = []

    class FakeProc:
        def __init__(self, cmd, **kw):
            cmds.append(cmd)

        def wait(self):
            return 0

    monkeypatch.setattr(video_gen.subprocess, "Popen", FakeProc)
    monkeypatch.setattr(video_gen, "_check_nvenc", lambda: False)
    monkeypatch.setattr(video_gen, "generate_thumbnail", lambda *a, **k: None, raising=False)
    tr = tmp_path / "t.json"
    tr.write_text(json.dumps({}))
    out = tmp_path / "out"
    out.mkdir()
    try:
        video_gen.extract_segments("src.mp4", [{"start": 0, "end": 5}], str(tr), str(out),
                                   layout=layout, filler_video=filler_path)
    except Exception:
        pass  # post-processing (thumbnails) is irrelevant to the command under test
    return cmds


def test_extract_uses_second_input_for_split_filler(monkeypatch, tmp_path):
    f = tmp_path / "f.mp4"
    f.write_bytes(b"x")
    cmd = _run_extract(monkeypatch, tmp_path, "split_filler", str(f))[0]
    assert cmd.count("-i") == 2 and "-stream_loop" in cmd and "-filter_complex" in cmd
    assert "-vf" not in cmd and "[v]" in cmd


def test_extract_without_filler_falls_back_to_single(monkeypatch, tmp_path):
    monkeypatch.setattr(filler, "find_local_filler", lambda *a, **k: None)
    monkeypatch.setattr(filler, "download_stock_filler", lambda out: None)
    cmd = _run_extract(monkeypatch, tmp_path, "split_filler", None)[0]
    assert "-vf" in cmd and "-filter_complex" not in cmd
