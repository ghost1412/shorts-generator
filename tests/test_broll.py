from engine import broll
from shortsflow import web_args


def W(word, start, end=None):
    return {"word": word, "start": start, "end": end if end is not None else start + 0.3}


TRANSCRIPT_WORDS = [
    W("Money", 0.5), W("is", 0.9), W("the", 1.0), W("root", 1.2),                # first 2 s: never
    W("Cars", 3.0), W("and", 3.4), W("houses", 3.6),                              # car at 3.0, house 0.6 s later: too close
    W("ocean", 5.0), W("freedom", 5.6),
    W("coffee", 12.0), W("money", 12.5), W("again", 13.0),                         # money already? first money was in 0.5 (skipped, not "seen")
    W("tiger", 19.0),
]


def test_normalize_word_handles_case_punctuation_and_plurals():
    assert broll.normalize_word("Cars,") == "car"
    assert broll.normalize_word("Houses!") == "house"
    assert broll.normalize_word("Money's") == "money"
    assert broll.normalize_word("Freedom") == "freedom"


def test_pick_cutaways_respects_start_spacing_length_and_end_guard():
    picks = broll.pick_cutaways(TRANSCRIPT_WORDS, duration=20.0)
    starts = [p["start"] for p in picks]
    assert starts == sorted(starts)
    assert all(s >= broll.MIN_START for s in starts)                       # nothing in the first 2 s
    assert all(b - a >= broll.MIN_SPACING for a, b in zip(starts, starts[1:]))
    for p in picks:
        assert broll.MIN_LEN <= p["end"] - p["start"] <= broll.MAX_LEN
        assert p["end"] <= 20.0 - broll.TAIL_GUARD
    assert [p["keyword"] for p in picks] == ["car", "coffee"]   # money said in the first 2 s, ocean too close to car, tiger too close to the end
    assert "freedom" not in {p["keyword"] for p in picks}                  # abstract words get no footage


def test_pick_cutaways_one_per_keyword_and_none_for_abstract_text():
    words = [W("car", 3.0), W("car", 14.0), W("car", 25.0)]
    assert len(broll.pick_cutaways(words, duration=40.0)) == 1
    assert broll.pick_cutaways([W("really", 3.0), W("important", 4.0), W("thing", 5.0)], duration=30.0) == []


def test_pick_cutaways_drops_a_keyword_too_close_to_the_end():
    assert broll.pick_cutaways([W("ocean", 9.4)], duration=10.0) == []


def test_pick_cutaways_hook_overlay_start_floor():
    floor = broll.HOOK_MIN_START
    assert broll.pick_cutaways([W("car", 2.2)], duration=20.0, min_start=floor) == []          # said while the title shows
    picks = broll.pick_cutaways([W("car", 3.05)], duration=20.0, min_start=floor)
    assert picks and picks[0]["start"] >= floor


def test_llm_queries_add_words_and_failures_fall_back_to_the_lexicon():
    words = [W("the", 3.0), W("blockchain", 3.5), W("car", 14.0)]
    ask = lambda prompt: [{"word": "blockchain", "query": "digital network"}]
    picks = broll.pick_cutaways(words, duration=30.0, ask=ask)
    assert {p["keyword"]: p["query"] for p in picks} == {"blockchain": "digital network", "car": "car"}

    def broken(_prompt):
        raise RuntimeError("no llm")
    assert [p["keyword"] for p in broll.pick_cutaways(words, duration=30.0, ask=broken)] == ["car"]


def test_cutaway_region_single_split_and_landscape():
    assert broll.cutaway_region(1080, 1920, "single", 1150) == (0, 0, 1080, 980)      # above the captions
    x, y, w, h = broll.cutaway_region(1080, 1920, "split_filler", 1150)
    assert h <= 960 and h <= 740 - broll.CAPTION_MARGIN                                  # inside the clip half, above the captions
    assert broll.cutaway_region(1920, 1080, "single", 1150) is None                       # landscape: skipped
    assert broll.cutaway_region(540, 960, "single", 1150)[3] == 490                       # scales with the height


def test_fetch_footage_order_cache_then_download_then_local_then_none(tmp_path):
    calls = []

    def download(query, path):
        calls.append(("dl", query))
        with open(path, "wb") as f:
            f.write(b"x" * 2000)
        return path

    first = broll.fetch_footage("ocean waves", cache_dir=str(tmp_path), download=download, local_pick=lambda: "LOCAL")
    again = broll.fetch_footage("ocean waves", cache_dir=str(tmp_path), download=download, local_pick=lambda: "LOCAL")
    assert first == again and calls == [("dl", "ocean waves")]                            # second call hits the cache
    assert broll.fetch_footage("tiger", cache_dir=str(tmp_path), download=lambda q, p: None, local_pick=lambda: "LOCAL") == "LOCAL"
    assert broll.fetch_footage("tiger", cache_dir=str(tmp_path), download=lambda q, p: None, local_pick=lambda: None) is None


def test_download_pexels_needs_a_key(monkeypatch, tmp_path):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert broll._download_pexels("car", str(tmp_path / "x.mp4")) is None


def test_overlay_command_loops_footage_fades_and_copies_audio():
    items = [{"start": 3.0, "end": 5.2, "footage": "a.mp4"}, {"start": 12.0, "end": 14.0, "footage": "b.mp4"}]
    cmd = broll.build_overlay_command("ffmpeg", "clip.mp4", items, (0, 0, 1080, 980), "out.mp4")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert cmd.count("-stream_loop") == 2 and cmd[cmd.index("-c:a") + 1] == "copy"
    assert "scale=1080:980" in graph and "crop=1080:980" in graph and "alpha=1" in graph
    assert "setpts=PTS+3.000/TB" in graph and "setpts=PTS+12.000/TB" in graph
    assert "overlay=0:0" in graph and cmd[cmd.index("-map") + 1] == "[v2]" and cmd[-1] == "out.mp4"


def test_clip_words_follow_the_tightened_timeline():
    data = {"segments": [{"start": 10, "end": 20, "words": [W("hello", 10.0), W("car", 18.0, 18.4)]}]}
    assert [w["word"] for w in broll.clip_words(data, 10, 20)] == ["hello", "car"]            # no tighten: shifted by the start
    assert broll.clip_words(data, 10, 20)[1]["start"] == 8.0
    cut = broll.clip_words(data, 10, 20, keep_intervals=[(10.0, 12.0), (16.0, 20.0)])           # 4 s of silence removed
    car = next(w for w in cut if w["word"] == "car")
    assert 3.5 < car["start"] < 4.5                                                           # 8 s -> about 4 s
    assert broll.clip_words(data, 10, 20, keep_intervals=[(10.0, 20.0)], tighten_mode="speed") is None


def test_apply_to_clip_skips_cleanly(monkeypatch, tmp_path):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"0" * 100)
    monkeypatch.setattr(broll, "_probe", lambda p, f: (1080, 1920, 20.0))
    monkeypatch.setattr(broll, "render_cutaways", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no render expected")))
    assert broll.apply_to_clip(str(clip), [W("car", 3.0)], fetch=lambda q: None) == 0             # no footage anywhere
    assert broll.apply_to_clip(str(clip), [W("really", 3.0)], fetch=lambda q: "x.mp4") == 0       # nothing concrete said
    monkeypatch.setattr(broll, "_probe", lambda p, f: (1920, 1080, 20.0))
    assert broll.apply_to_clip(str(clip), [W("car", 3.0)], fetch=lambda q: "x.mp4") == 0          # landscape


def test_apply_to_clip_renders_the_picks(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(broll, "_probe", lambda p, f: (1080, 1920, 20.0))
    monkeypatch.setattr(broll, "render_cutaways", lambda video, items, region, ffmpeg=None: seen.update(items=items, region=region) or True)
    n = broll.apply_to_clip("c.mp4", [W("car", 3.0), W("ocean", 14.0)], fetch=lambda q: f"{q}.mp4", hook_overlay=True)
    assert n == 2 and [i["footage"] for i in seen["items"]] == ["car.mp4", "ocean.mp4"]
    assert seen["region"] == (0, 0, 1080, 980)


def test_apply_to_clip_never_raises(monkeypatch):
    monkeypatch.setattr(broll, "_probe", lambda p, f: (_ for _ in ()).throw(RuntimeError("bad file")))
    assert broll.apply_to_clip("missing.mp4", [W("car", 3.0)]) == 0


def test_old_moviepy_cutaway_function_is_gone():
    import engine.video_gen as vg
    assert not hasattr(vg, "insert_broll_cutaways")


def test_web_args_broll_flag():
    assert web_args.extras_args(broll=True) == ["--broll"]
    assert "--broll" in web_args.extras_args(clean_audio=True, broll=True, use_remotion=False)
    assert "--broll" not in web_args.extras_args(clean_audio=True)
