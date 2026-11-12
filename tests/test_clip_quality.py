"""Label-free clip quality report (offline, synthetic transcripts)."""
import json
import os

from engine import clip_quality as q

SEGS = [
    {"start": 0.0, "end": 4.0, "text": " We tested the battery for three days.", "words": [{"word": " We", "start": 0.1}, {"word": " tested", "start": 0.5}]},
    {"start": 4.0, "end": 9.0, "text": " It lost only twelve percent and", "words": []},
    {"start": 9.0, "end": 14.0, "text": " the charging surprised me.", "words": []},
    {"start": 14.0, "end": 20.0, "text": " Then we tried the camera.", "words": []},
    {"start": 60.0, "end": 66.0, "text": " Next topic entirely.", "words": []},
]


def test_sentence_edges_follow_punctuation():
    starts, ends = q.sentence_edges(SEGS)
    assert starts == [0.0, 4.0, 14.0, 60.0] and 9.0 not in starts                    # 9.0 continues "...percent and"
    assert ends == [4.0, 14.0, 20.0, 66.0] and 9.0 not in ends


def test_overlap_spread_and_text_helpers():
    clips = [{"start": 0, "end": 10}, {"start": 8, "end": 14}, {"start": 60, "end": 66}]
    assert q.overlap_seconds(clips) == 2.0
    assert q.spread_share(clips, 100.0) == 0.67                  # two of the three clips share a tenth of the video
    assert q.spread_share([], 100.0) is None
    assert "battery" in q.clip_text(SEGS, 0, 5) and "camera" not in q.clip_text(SEGS, 0, 5)


def test_measure_reports_boundaries_length_and_grounding():
    results = {"clips": [
        {"start": 0.0, "end": 20.0, "title": "Battery lost twelve percent", "description": "Real test. #battery", "hook": "twelve percent"},
        {"start": 4.1, "end": 14.0, "title": "Phone lost 90 percent", "description": "x"},                  # starts where a sentence starts (4.0), invents "90"
    ]}
    m = q.measure(SEGS, results, min_len=15, max_len=75)
    assert m["clips"] == 2 and m["median_length_s"] in (14.9, 15.0)
    assert m["length_in_range"] == 0.5                                                                       # 20 s is in range, 9.9 s is not
    assert m["ends_at_sentence"] == 1.0                                                                     # 20.0 and 14.0 are sentence ends
    assert m["overlap_s"] == 9.9
    assert m["titles_grounded"] == 0.5                                                                      # "90" is never said


def test_gold_scores_recall_and_precision():
    clips = [{"start": 0, "end": 20}, {"start": 100, "end": 120}]
    gold = [[2, 18], [200, 220]]
    s = q.gold_scores(clips, gold)
    assert s == {"recall": 0.5, "precision": 0.5}
    assert q.gold_scores([], gold) == {"recall": None, "precision": None}


def test_report_reads_a_session_folder_and_uses_the_gold_file_by_video_name(tmp_path):
    (tmp_path / "transcript.json").write_text(json.dumps({"segments": SEGS}), encoding="utf-8")
    (tmp_path / "results.json").write_text(json.dumps({"source_video": "C:/v/talk.mp4", "settings": {"user_context": ""},
                                                       "clips": [{"start": 0.0, "end": 20.0, "title": "Battery test", "description": "", "hook": "x"}]}), encoding="utf-8")
    r = q.report(str(tmp_path), gold={"talk.mp4": [[1, 19]]})
    assert r["video"] == "talk.mp4" and r["clips"] == 1 and r["recall"] == 1.0 and r["precision"] == 1.0
    assert q.report(str(tmp_path / "missing")) is None


def test_the_benchmark_script_prints_a_table_and_skips_unreadable_folders(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("clip_benchmark", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "clip_benchmark.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    run = tmp_path / "run_a"
    run.mkdir()
    (run / "transcript.json").write_text(json.dumps({"segments": SEGS}), encoding="utf-8")
    (run / "results.json").write_text(json.dumps({"clips": [{"start": 0.0, "end": 20.0, "title": "Battery test", "description": ""}]}), encoding="utf-8")
    out = tmp_path / "out.json"
    assert mod.main([str(run), str(tmp_path / "nope"), "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "run_a" in printed and "skipped" in printed and json.loads(out.read_text(encoding="utf-8"))[0]["clips"] == 1
    assert mod.main([str(tmp_path / "nope")]) == 1


def test_a_long_pause_counts_as_a_sentence_edge_like_in_the_snapper():
    words = [{"word": " so", "start": 0.0, "end": 0.3}, {"word": " we", "start": 0.4, "end": 0.6}, {"word": " tried", "start": 0.7, "end": 1.1},
             {"word": " it", "start": 1.2, "end": 1.5},                                  # no punctuation, then a 1.5 s pause
             {"word": " it", "start": 3.0, "end": 3.2}, {"word": " worked.", "start": 3.3, "end": 3.9}]
    starts, ends = q.sentence_edges([{"start": 0.0, "end": 3.9, "text": " so we tried it it worked.", "words": words}])
    assert starts == [0.0, 3.0] and ends == [1.5, 3.9]


def test_clip_videos_prefers_the_session_folder_over_the_current_folder(tmp_path, monkeypatch):
    run_a, run_b = tmp_path / "run_a", tmp_path / "run_b"
    for d in (run_a, run_b):
        d.mkdir()
        (d / "video_clip_1.mp4").write_bytes(b"x")
    monkeypatch.chdir(run_a)
    res = {"clips": [{"video_path": "video_clip_1.mp4"}, {"video_path": "sub\\video_clip_1.mp4"}]}
    found = q.clip_videos(res, str(run_b))
    assert [os.path.normcase(os.path.abspath(f)) for f in found] == [os.path.normcase(str(run_b / "video_clip_1.mp4"))] * 2
    # An absolute path is used as given; a missing session file falls back to the bare relative path.
    assert q.clip_videos({"clips": [{"video_path": str(run_a / "video_clip_1.mp4")}]}, str(run_b)) == [str(run_a / "video_clip_1.mp4")]
    assert q.clip_videos({"clips": [{"video_path": "video_clip_1.mp4"}]}, str(tmp_path / "missing")) == ["video_clip_1.mp4"]


def test_speech_gaps_count_pauses_lead_in_and_tail():
    from engine.clip_quality import speech_gaps
    segs = [{"start": 0, "end": 10, "words": [{"word": "a", "start": 1.0, "end": 1.5}, {"word": "b", "start": 1.6, "end": 2.0},
                                                {"word": "c", "start": 4.0, "end": 4.5}]}]
    # lead-in 0-1 (1.0), gap 2.0-4.0 (2.0), tail 4.5-6 (1.5); the 0.1 s gap between a and b is speech
    assert speech_gaps(segs, 0, 6) == 4.5
    assert speech_gaps(segs, 7, 9) == 2.0                 # no words at all: the whole span


def test_highlights_run_reports_reel_length_and_target(tmp_path):
    import json
    from engine.clip_quality import report
    words = [{"word": f"w{i}.", "start": i * 1.0, "end": i * 1.0 + 0.5} for i in range(200)]
    (tmp_path / "transcript.json").write_text(json.dumps({"segments": [{"start": 0, "end": 200, "text": "x", "words": words}]}))
    (tmp_path / "results.json").write_text(json.dumps({"settings": {"extract_mode": "long", "target_duration": 120},
                                                       "clips": [{"start": 10, "end": 70}, {"start": 100, "end": 160}]}))
    r = report(str(tmp_path))
    assert r["reel_s"] == 120.0 and r["target_s"] == 120.0
    assert r["length_in_range"] == 1.0                    # 60 s moments are fine in a highlights video
    assert "cut_s" not in r


def _words(items):
    return [{"start": 0, "end": items[-1][0] + 1, "text": " ".join(w for _, w in items),
             "words": [{"start": t, "end": t + 0.4, "word": w} for t, w in items]}]


def test_hook_ok_needs_a_standalone_opening():
    from engine.clip_quality import hook_ok
    good = _words([(10.0, "Nobody"), (10.4, "expected"), (10.8, "this"), (11.2, "result.")])
    assert hook_ok(good, 10.0, 20.0)
    assert not hook_ok(_words([(10.0, "And"), (10.4, "then"), (10.8, "we"), (11.2, "left.")]), 10.0, 20.0)   # connective first
    assert not hook_ok(_words([(10.0, "Uh,"), (10.4, "yes"), (10.8, "it"), (11.2, "works.")]), 10.0, 20.0)    # filler first
    assert not hook_ok(_words([(10.0, "Why."), (10.4, "Because"), (10.8, "so"), (11.2, "it.")]), 10.0, 20.0)   # first sentence too short
    assert hook_ok(_words([(10.0, "Why"), (10.4, "does"), (10.8, "it"), (11.2, "float?")]), 10.0, 20.0)
    assert hook_ok(_words([(10.0, "Why"), (10.4, "me?"), (10.8, "Because"), (11.2, "so.")]), 10.0, 20.0)      # a short question is a hook
    assert not hook_ok(_words([(13.0, "Nobody"), (13.4, "expected"), (13.8, "this"), (14.2, "result.")]), 10.0, 20.0)  # silent lead-in
    assert not hook_ok([], 10.0, 20.0)


def test_hook_ok_without_word_times_uses_the_text():
    from engine.clip_quality import hook_ok
    assert hook_ok([{"start": 0, "end": 5, "text": "This is a plain opening line"}], 0, 5)
    assert not hook_ok([{"start": 0, "end": 5, "text": "And this is not a hook"}], 0, 5)


def test_placeholder_clip_titles_are_not_counted_as_ungrounded():
    from engine.clip_quality import grounded_share
    segs = [{"start": 0, "end": 10, "text": "We keep the water in a closed loop."}]
    assert grounded_share([{"start": 0, "end": 10, "title": "Clip #2", "description": ""}], segs) == 1.0
    assert grounded_share([{"start": 0, "end": 10, "title": "Water 99 times", "description": ""}], segs) == 0.0


def test_no_face_clip_needs_every_sampled_frame_empty(monkeypatch):
    from engine import clip_picture, video_gen
    calls = {}

    def fake(track):
        def f(video, samples=12, start=None, end=None, min_face_div=12):
            calls["span"] = (start, end)
            return track
        return f

    monkeypatch.setattr(clip_picture, "face_track", fake([None] * 8))
    assert video_gen.no_face_clip("src.mp4", 10.0, 40.0) is True
    assert calls["span"] == (10.0, 40.0)                                  # only the clip's own part of the source is sampled
    monkeypatch.setattr(clip_picture, "face_track", fake([None] * 7 + [(0.5, 0.4, 0.2)]))
    assert video_gen.no_face_clip("src.mp4", 10.0, 40.0) is False         # one face anywhere: keep the crop
    monkeypatch.setattr(clip_picture, "face_track", fake([None] * 3))
    assert video_gen.no_face_clip("src.mp4", 10.0, 40.0) is False         # too few frames read: no decision
    monkeypatch.setattr(clip_picture, "face_track", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no cv2")))
    assert video_gen.no_face_clip("src.mp4", 10.0, 40.0) is False


def test_face_track_samples_only_the_asked_span(tmp_path):
    cv2 = __import__("pytest").importorskip("cv2")
    import numpy as np
    from engine.clip_picture import face_track
    path = str(tmp_path / "blank.avi")
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    for _ in range(100):
        out.write(np.zeros((120, 160, 3), dtype=np.uint8))
    out.release()
    assert len(face_track(path, samples=4, start=2.0, end=6.0)) == 4
    assert not any(face_track(path, samples=4))


def test_length_vs_target_counts_clips_within_a_quarter_of_the_asked_length():
    from engine.clip_quality import length_vs_target
    assert length_vs_target([30, 33, 22, 45], 30) == 0.5            # 30 and 33 fit (22.5..37.5), 22 and 45 do not
    assert length_vs_target([30], None) is None and length_vs_target([], 30) is None and length_vs_target([30], "x") is None
