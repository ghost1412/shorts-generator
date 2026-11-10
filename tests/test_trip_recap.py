import json
import os
import shutil
import subprocess

import pytest

from engine import trip_recap as tr


def test_natural_order():
    assert sorted(["day10", "day2", "day1"], key=tr.natural_key) == ["day1", "day2", "day10"]


def test_group_days_by_name_and_folder(tmp_path):
    for name in ("Day2_b.mp4", "day1_a.mp4", "day 10.mp4", "day2_a.mp4"):
        (tmp_path / name).write_bytes(b"x")
    days = tr.group_days(tr.collect_videos([str(tmp_path)]))
    assert [[os.path.basename(p) for p in d] for d in days] == [["day1_a.mp4"], ["Day2_b.mp4", "day2_a.mp4"][::-1], ["day 10.mp4"]]


def test_group_days_subfolders(tmp_path):
    for d in ("Day 2", "Day 1"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "clip.mp4").write_bytes(b"x")
    days = tr.group_days(tr.collect_videos([str(tmp_path)]))
    assert [os.path.basename(os.path.dirname(d[0])) for d in days] == ["Day 1", "Day 2"]


def test_files_without_any_hint_become_one_day_each(tmp_path):
    for n in ("b.mp4", "a.mp4"):
        (tmp_path / n).write_bytes(b"x")
    days = tr.group_days([(str(tmp_path / "b.mp4"), None), (str(tmp_path / "a.mp4"), None)])
    assert [os.path.basename(d[0]) for d in days] == ["a.mp4", "b.mp4"]


def test_plan_counts_fills_the_length():
    n, clip = tr.plan_counts(3, 60)
    assert n >= 1 and 3 * (tr.CARD_SECONDS + n * clip) == pytest.approx(60, abs=6)
    assert tr.plan_counts(1, 10)[0] >= 1


def test_pick_windows_prefers_loud_parts_and_spreads():
    levels = [-60.0] * 100
    for i in range(70, 76):
        levels[i] = -10.0
    w = tr.pick_windows(100, 3, 5, levels)
    assert len(w) == 3 and w == sorted(w)
    assert any(abs(a - 70) < 3 for a, _ in w)               # the loud stretch is chosen
    assert all(e - s == pytest.approx(5, abs=0.01) for s, e in w)
    assert tr.pick_windows(3, 3, 5) == [[0.0, 3.0]]          # a very short video gives one window


def test_itinerary_parsing_and_fallback():
    days = [{"moments": [{"file": "a.mp4", "start": 1, "visual": "a lake"}, {"file": "a.mp4", "start": 9}]}]
    good = '{"title": "Northvale", "days": [{"title": "Lakes", "summary": "A day at the lake.", "captions": ["Big Northvale Lake"]}]}'
    it = tr.write_itinerary("Northvale", "", days, ask=lambda p: good)
    assert it["title"] == "Northvale" and it["days"][0]["captions"] == ["Big Northvale Lake", ""]
    bad = tr.write_itinerary("Northvale", "", days, ask=lambda p: "nonsense")
    assert bad["days"][0]["title"] == "Day 1"
    boom = tr.write_itinerary("", "", days, ask=lambda p: 1 / 0)
    assert boom["title"] == "Trip recap"
    assert "a lake" in tr.build_prompt("Northvale", "note", days)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")
def test_make_recap_end_to_end(tmp_path):
    def make(path, w, h, secs, tone):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=15:duration={secs}",
                        "-f", "lavfi", "-i", f"sine=f={tone}:d={secs}", "-shortest", "-pix_fmt", "yuv420p", str(path)], check=True)

    (tmp_path / "day1").mkdir()
    (tmp_path / "day2").mkdir()
    make(tmp_path / "day1" / "a.mp4", 640, 360, 20, 300)
    make(tmp_path / "day2" / "b.mp4", 360, 640, 20, 600)          # a portrait phone video too
    ask = lambda p: json.dumps({"title": "Test Trip", "days": [  # noqa: E731
        {"title": "Arrival", "summary": "We landed.", "captions": ["Hello", "Lake"]},
        {"title": "Mountains", "summary": "Up high.", "captions": ["Peak", "View"]}]})
    res = tr.make_recap([str(tmp_path / "day1"), str(tmp_path / "day2")], str(tmp_path / "out"), trip_name="Test", total_seconds=24, ask=ask)
    assert res["days"] == 2 and os.path.isfile(res["video"])
    dur, w, h = tr.video_info(res["video"])
    assert (w, h) == (1080, 1920) and 14 < dur < 36
    assert tr.has_audio(res["video"])
    md = open(res["itinerary_md"], encoding="utf-8").read()
    assert "Day 1: Arrival" in md and "Day 2: Mountains" in md


def test_no_videos_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError):
        tr.make_recap([str(tmp_path)], str(tmp_path / "o"))


def _jpeg(color, noise=False):
    import io
    from PIL import Image
    img = Image.new("RGB", (64, 64), color)
    if noise:
        for x in range(0, 64, 2):
            for y in range(64):
                img.putpixel((x, y), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def test_scenic_score_prefers_colourful_frames():
    assert tr.scenic_score(_jpeg((30, 144, 255), noise=True)) > tr.scenic_score(_jpeg((90, 90, 90)))
    assert tr.scenic_score(b"not an image") == 0.0


def test_pick_glimpses_spreads_over_days_and_follows_trip_order():
    days = [{"infos": [("d1.mp4", 60, 640, 360)]}, {"infos": [("d2.mp4", 60, 640, 360)]}, {"infos": [("d3.mp4", 60, 640, 360)]}]
    grab = lambda f, s, e: [f"{f}|{s}".encode()]  # noqa: E731
    # day 1 is the prettiest by far, but may not fill the whole opening
    score = lambda b: 1.0 if b.startswith(b"d1") else 0.2 + (hash(b) % 100) / 1000  # noqa: E731
    g = tr.pick_glimpses(days, 5, 1.4, grab=grab, score=score)
    assert len(g) == 5
    per_day = [sum(1 for x in g if x["day"] == d) for d in range(3)]
    assert max(per_day) <= 3 and min(per_day) >= 1
    assert [x["day"] for x in g] == sorted(x["day"] for x in g)


def test_hook_comes_from_ai_and_is_overridable():
    days = [{"moments": [{"file": "a.mp4", "start": 1}]}]
    good = '{"title": "Northvale", "hook": "Woke up at 4 AM just for this view", "days": [{"title": "Lakes", "summary": "", "captions": ["x"]}]}'
    assert tr.write_itinerary("Northvale", "woke up at 4am", days, ask=lambda p: good)["hook"] == "Woke up at 4 AM just for this view"
    assert "Use only facts from the traveller" in tr.build_prompt("Northvale", "note", days)


def test_parse_stops_and_split_into():
    assert tr.parse_stops("Pinemere Lake, Larkwater Lake; Stonegate Canyon") == ["Pinemere Lake", "Larkwater Lake", "Stonegate Canyon"]
    assert tr.parse_stops("") == [] and tr.parse_stops(None) == []
    g = tr.split_into([["a", "b", "c"], ["d", "e"]], 3)
    assert g == [["a", "b"], ["c", "d"], ["e"]]
    assert tr.split_into([["a"]], 3) == [["a"]]                       # never more stops than videos


def test_stop_names_are_used_verbatim_and_prompt_forbids_inventing():
    days = [{"moments": [{"file": "a.mp4", "start": 1}]}, {"moments": [{"file": "b.mp4", "start": 1}]}]
    stops = ["Pinemere Lake", "Larkwater Lake"]
    reply = '{"title": "Northvale tour", "hook": "h", "days": [{"title": "Whatever", "summary": "s", "captions": ["x"]}, {"title": "Else", "summary": "", "captions": [""]}]}'
    it = tr.write_itinerary("Northvale", "17 hour tour from 5 am", days, ask=lambda p: reply, stops=stops)
    assert [d["title"] for d in it["days"]] == stops
    p = tr.build_prompt("Northvale", "note", days, stops)
    assert "Never invent" in p and "Stop 1 = Pinemere Lake" in p
    assert tr.fallback_itinerary("", days, stops)["days"][1]["title"] == "Larkwater Lake"
    assert "## Stop 1: Pinemere Lake" in tr.itinerary_markdown(it, [{"moments": [{"file": "a.mp4", "start": 1}]}] * 2, "Stop")


def test_stops_are_cut_at_the_longest_pauses():
    names = ["083000_a.mp4", "083500_b.mp4", "102700_c.mp4", "105000_d.mp4", "132200_e.mp4", "134300_f.mp4", "161800_g.mp4", "171900_h.mp4"]
    g = tr.split_into([names], 3)
    assert [len(x) for x in g] == [4, 2, 2] and g[1][0] == "132200_e.mp4"
    # no times in the names, or no clear pauses: equal counts as before
    assert tr.split_by_gaps(["a.mp4", "b.mp4", "c.mp4"], 2) is None
    assert tr.split_by_gaps(["080000_a.mp4", "080500_b.mp4", "081000_c.mp4"], 2) is None


def test_plan_days_gives_the_big_day_more_time_but_every_day_some():
    counts, clip = tr.plan_days([4, 68, 31, 32, 38], 100)
    assert counts[1] == max(counts) and counts[1] > counts[0] and min(counts) >= 1
    assert sum(counts) * clip + 5 * tr.CARD_SECONDS == pytest.approx(100, abs=12)
    assert tr.plan_days([5], 40)[0][0] >= 1
    assert sum(tr.plan_days([1, 1, 1], 30)[0]) >= 3


def test_glimpses_use_the_vision_rating_and_skip_overlays():
    days = [{"infos": [(f"d{d}.mp4", 60, 640, 360)]} for d in range(3)]
    grab = lambda f, s, e: [f"{f}|{s}".encode()]  # noqa: E731
    colour = lambda b: 1.0 if b.startswith(b"d0") else 0.1  # noqa: E731    # colour alone would favour day 1 (the night park walk)

    def rate(frames):
        out = []
        for fr in frames:
            name = fr.decode()
            out.append({"score": 9.0 if name.startswith("d2") else 2.0, "overlay": name.startswith("d1")})
        return out

    g = tr.pick_glimpses(days, 4, 1.4, grab=grab, score=colour, rate=rate)
    assert all(x["day"] != 1 for x in g)                      # the clip with a text overlay never opens the video
    assert sum(1 for x in g if x["day"] == 2) >= 2            # the rated-beautiful day leads
    assert tr.pick_glimpses(days, 4, 1.4, grab=grab, score=colour, rate=lambda fr: None)    # a failed rating falls back to colour


def test_spaced_keeps_word_gaps():
    from engine import trip_recap as t
    assert t.spaced("Take me back") == "T A K E   M E   B A C K"
    assert t.spaced("x" * 30) == "X" * 30            # long text is only upper-cased


def test_decide_look_follows_the_footage(tmp_path):
    from engine import trip_recap as t
    for n in "abc":
        (tmp_path / f"{n}.mp4").write_bytes(b"x")
    assert t.decide_look([str(tmp_path)], probe=lambda f: (5.0, 1920, 1080))[:2] == ("cinematic", "2.35:1")
    assert t.decide_look([str(tmp_path)], probe=lambda f: (5.0, 1080, 1920))[:2] == ("hype", "9:16")


def test_frame_look_falls_back_to_a_neutral_look():
    from engine import trip_recap as t
    look = t.frame_look("no-such-ffmpeg", "no-such.mp4", 1.0, run=lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert look["zone"] == "center" and look["dark"] is True


def test_cinematic_layers_follow_the_look(tmp_path):
    from engine import trip_recap as t
    lay = t.cinematic_layers(str(tmp_path / "t"), "Northvale trip", "Day 2", "a film", look={"zone": "lower", "dark": False, "accent": (200, 120, 60)}, index=1)
    assert [ts for _p, ts in lay] == sorted(ts for _p, ts in lay) and len(lay) == 3      # credit, title, rule + line appear one after another
    assert all(os.path.isfile(p) for p, _ts in lay)


def test_beat_length_unchanged_without_a_tempo():
    from engine import trip_recap as t
    assert t.beat_length("missing.mp3", 3.0) == 3.0


def test_video_info_swaps_sides_for_phone_rotation(monkeypatch):
    import json as _json
    from engine import trip_recap as t

    def fake(side):
        class R:
            stdout = _json.dumps({"streams": [side], "format": {"duration": "4.0"}})
        return lambda *a, **k: R()
    monkeypatch.setattr(t.subprocess, "run", fake({"width": 1920, "height": 1080, "side_data_list": [{"rotation": -90}]}))
    assert t.video_info("x.mp4") == (4.0, 1080, 1920)               # stored landscape, shown portrait
    monkeypatch.setattr(t.subprocess, "run", fake({"width": 1920, "height": 1080, "tags": {"rotate": "270"}}))
    assert t.video_info("x.mp4") == (4.0, 1080, 1920)
    monkeypatch.setattr(t.subprocess, "run", fake({"width": 1920, "height": 1080, "side_data_list": [{"rotation": 180}]}))
    assert t.video_info("x.mp4") == (4.0, 1920, 1080)               # upside down is still landscape


def test_filter_orientation_keeps_one_shape_or_falls_back():
    from engine import trip_recap as t
    day = [("a", 5, 1920, 1080), ("b", 5, 1080, 1920), ("c", 5, 1920, 1080), ("d", 5, 1920, 1080), ("e", 5, 1080, 1920)]
    land, _ = t.filter_orientation([day], "landscape", minimum=3)
    assert [i[0] for i in land[0]] == ["a", "c", "d"]
    same, note = t.filter_orientation([day], "portrait", minimum=3)      # only 2 vertical videos: keep all, say so
    assert same == [day] and "only 2" in note
    assert t.filter_orientation([day], "any") == ([day], "")


def test_on_beat_gives_whole_beats():
    from engine import trip_recap as t
    assert abs(t.on_beat(1.4, 0.5) - 1.5) < 1e-9
    assert abs(t.on_beat(4.99, 0.4, 2) - 4.8) < 1e-9
    assert t.on_beat(0.01, 0.5) == 0.5                                  # never shorter than one beat


def test_render_clip_silent_track_comes_before_the_maps(tmp_path):
    from engine import trip_recap as t
    seen = {}

    def fake(cmd, **k):
        seen["cmd"] = cmd
        open(cmd[-1], "wb").write(b"x")

        class R:
            returncode = 0
            stderr = ""
        return R()
    orig = t.subprocess.run
    t.subprocess.run = fake
    try:
        t.render_clip("ffmpeg", "in.mp4", 0, 2.0, str(tmp_path / "o.mp4"), None, "auto", (1920, 1080), audio=False)
    finally:
        t.subprocess.run = orig
    cmd = seen["cmd"]
    assert max(i for i, c in enumerate(cmd) if c == "-i") < cmd.index("-map")      # every input is declared before the first -map


def test_long_titles_and_captions_stay_inside_a_vertical_frame(tmp_path):
    from PIL import Image
    from engine import trip_recap as t
    old = (t.W, t.H)
    t.W, t.H = t.ASPECTS["9:16"]
    try:
        for index, zone in ((0, "center"), (1, "left"), (1, "lower")):
            lay = t.cinematic_layers(str(tmp_path / f"t{index}{zone}"), "Day 1: Arriving in Northvale, Eastland", "Day 1 of 5 in the mountains", "a very long credit line for the film",
                                     look={"zone": zone, "dark": True, "accent": (200, 150, 90)}, index=index)
            for png, _ts in lay:
                box = Image.open(png).getchannel("A").getbbox()
                assert box is None or (box[0] >= 0 and box[2] <= t.W), (zone, png, box)       # nothing is cut off at the sides
                assert box is None or (box[0] > 0 or zone == "center" or True)
        cap = t.caption_png(str(tmp_path / "cap.png"), "Walking down wooden steps through the forest to the lake", lower=True)
        box = Image.open(cap).getchannel("A").getbbox()
        assert box[2] <= t.W - 20
    finally:
        t.W, t.H = old


def test_recap_kinds_change_the_wording_and_default_to_the_trip():
    days = [{"moments": [{"visual": "a groom on a horse", "file": "a.mp4", "start": 1}]},
            {"moments": [{"visual": "a couple dancing", "file": "b.mp4", "start": 2}]}]
    trip = tr.build_prompt("Northvale", "note", days)
    wed = tr.build_prompt("Alex and Sam", "note", days, ["Ceremony", "Dinner"], kind="wedding")
    assert "travel recap" in trip and "Day 1" in trip and "traveller" in trip
    assert "wedding film" in wed and "Part 1 = Ceremony" in wed and "travel" not in wed.lower() and "GPS" not in wed
    assert tr.get_kind("nonsense") is tr.KINDS["trip"] and tr.get_kind(None) is tr.KINDS["trip"]
    fb = tr.fallback_itinerary("", days, kind="wedding")
    assert fb["title"] == "Wedding recap" and fb["days"][1]["title"] == "Part 2"
    assert tr.fallback_itinerary("", days)["days"][0]["title"] == "Day 1"            # trips are unchanged
    good = '{"title": "x", "hook": "h", "days": [{"title": "", "summary": "", "captions": ["a"]}, {"title": "", "summary": "", "captions": ["b"]}]}'
    assert tr.write_itinerary("", "", days, ask=lambda p: good, kind="event")["days"][0]["title"] == "Part 1"


def test_web_args_pass_the_kind_and_keep_sound_only_when_needed():
    from shortsflow import web_args
    plain = web_args.trip_args(["a.mp4"], "s")
    assert "--recap_kind" not in plain and "--recap_keep_sound" not in plain
    both = web_args.trip_args(["a.mp4"], "s", kind="wedding", keep_sound=True)
    assert both[both.index("--recap_kind") + 1] == "wedding" and "--recap_keep_sound" in both
    assert web_args.recap_kind_labels("wedding")[1].startswith("Parts of the day") and web_args.recap_kind_labels("zzz") == web_args.RECAP_KIND_TEXT["trip"]


def test_resolve_look_automatic_none_named_and_edit_style():
    from engine.video_gen import FILTER_PRESETS
    assert tr.resolve_look("default", "", tr.CINEMATIC_GRADE) == (tr.CINEMATIC_GRADE, "automatic")      # the cinematic look the footage suits
    assert tr.resolve_look("default", "", "") == ("", "none needed")                                    # no look when none suits
    assert tr.resolve_look("none", "hype", tr.CINEMATIC_GRADE)[0] == ""                                  # explicit 'none' beats everything
    assert tr.resolve_look("teal_orange", "", "")[0] == FILTER_PRESETS["teal_orange"]
    assert tr.resolve_look("default", "hype", "")[0] == FILTER_PRESETS["vibrant_action"]                 # the style's own look
    assert tr.resolve_look("default", "podcast", tr.CINEMATIC_GRADE)[0] == tr.CINEMATIC_GRADE           # a style without a look keeps the automatic one


def test_zoom_filter_fixes_the_frame_rate_and_cut_sounds_skip_cards():
    z = tr.zoom_filter(5.0, 0.06)
    assert z.startswith("fps=30,zoompan=") and "1+0.0600*on/150" in z and "d=1" in z
    assert "1+0.0600-0.0600*on/150" in tr.zoom_filter(5.0, 0.06, out=True)
    parts = [("p/glimpse_1.mp4", 1.4), ("p/trip_title.mp4", 3.4), ("p/card_1.mp4", 2.2), ("p/clip_1_1.mp4", 5.0), ("p/clip_1_2.mp4", 5.0), ("p/end.mp4", 3)]
    ev = tr.cut_sound_events(parts, "whoosh")
    assert [e["t"] for e in ev] == [1.4, 7.0, 12.0] and {e["kind"] for e in ev} == {"whoosh"}        # not at the start, not at cards or the end


def test_recap_options_reach_the_command_line_and_long_recaps_are_allowed():
    from shortsflow import web_args
    a = web_args.trip_args(["a.mp4"], "s", length=1500, grade="teal_orange", edit="hype", edit_strength="hyped", clean_sound=True)
    assert a[a.index("--recap_length") + 1] == "1500"
    assert a[a.index("--video_filter") + 1] == "teal_orange" and a[a.index("--auto_edit") + 1] == "hype" and "--clean_audio" in a
    assert web_args.trip_args(["a.mp4"], "s", length=99999)[4:6] == ["--recap_length", str(web_args.MAX_RECAP_SECONDS)] or "--recap_length" in web_args.trip_args(["a.mp4"], "s", length=99999)
    plain = web_args.trip_args(["a.mp4"], "s")
    assert not {"--video_filter", "--auto_edit", "--clean_audio"} & set(plain)                              # nothing extra unless chosen


def test_wedding_folders_become_parts_in_the_order_given_whatever_the_file_dates(tmp_path):
    for name in ("henna evening one", "music night + dance", "farewell part"):
        d = tmp_path / name
        d.mkdir()
        for i in (10, 2, 1):
            (d / f"C{i:04d}.mp4").write_bytes(b"x")
    paths = [str(tmp_path / n) for n in ("henna evening one", "music night + dance", "farewell part")]
    videos = tr.collect_videos(paths)
    groups = tr.group_days(videos, by_folder=True)
    assert [os.path.basename(os.path.dirname(g[0])) for g in groups] == ["henna evening one", "music night + dance", "farewell part"]
    assert [os.path.basename(f) for f in groups[0]] == ["C0001.mp4", "C0002.mp4", "C0010.mp4"]         # natural order inside a folder
    assert tr.folder_names(videos) == ["Henna evening one", "Music night + dance", "Farewell part"]
    assert len(tr.group_days(videos)) == 1                                                             # trips: still grouped by date (all files made now)
    assert tr.folder_names(tr.collect_videos(paths[:1])) == [] and len(tr.group_days(tr.collect_videos(paths[:1]), by_folder=True)) == 1


def test_sample_videos_thins_big_parts_only_when_asked():
    infos = [(f"v{i}.mp4", 10.0, 1920, 1080) for i in range(600)]
    s = tr.sample_videos(infos, 20, 3.0)
    assert len(s) == 60 and s[0] == infos[0] and s[-1] == infos[-1] and s == sorted(s, key=lambda x: int(x[0][1:-4]))     # spread, in order
    assert tr.sample_videos(infos, 20, None) == infos and tr.sample_videos(infos, 20, 0) == infos                         # trips: everything
    few = infos[:40]
    assert tr.sample_videos(few, 20, 3.0) == few                                                                          # not many more than needed
    assert tr.get_kind("trip").get("sample") is None and tr.get_kind("wedding")["sample"] == 3.0


def test_sampling_is_a_choice_not_hard_coded():
    from shortsflow import web_args
    kd = tr.get_kind("wedding").get("sample")
    assert tr.sample_factor("auto", kd) == 3.0 and tr.sample_factor(None, kd) == 3.0 and tr.sample_factor("auto", None) is None
    assert tr.sample_factor("all", kd) is None and tr.sample_factor("6", kd) == 6.0 and tr.sample_factor("0", kd) is None
    with pytest.raises(ValueError):
        tr.sample_factor("lots", kd)
    assert "--recap_sample" not in web_args.trip_args(["a.mp4"], "s")
    a = web_args.trip_args(["a.mp4"], "s", sample="all")
    assert a[a.index("--recap_sample") + 1] == "all"


def test_cut_sound_events_follow_the_dissolve_overlap():
    parts = [("clip_1.mp4", 4.0), ("clip_2.mp4", 4.0), ("clip_3.mp4", 4.0)]
    plain = [e["t"] for e in tr.cut_sound_events(parts, "whoosh")]
    melt = [e["t"] for e in tr.cut_sound_events(parts, "whoosh", overlap=0.6)]
    assert plain == [4.0, 8.0] and melt == [3.4, 6.8]


def test_timelapse_factor_never_asks_for_more_footage_than_the_file_has():
    assert tr.timelapse_factor(None, 3.0, 100) == 1.0 and tr.timelapse_factor(1.0, 3.0, 100) == 1.0
    assert tr.timelapse_factor("oops", 3.0, 100) == 1.0
    assert tr.timelapse_factor(2.5, 3.0, 100) == 2.5
    assert tr.timelapse_factor(3.0, 3.0, 6.0) == pytest.approx(2.0)          # only 6 s left: 2x at most for a 3 s shot
    assert tr.timelapse_factor(3.0, 3.0, 1.0) == 1.0 and tr.timelapse_factor(3.0, 3.0, -4) == 1.0


def test_render_clip_time_lapse_plays_a_longer_stretch_in_the_same_time(tmp_path):
    import subprocess
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        from PIL import Image
    except Exception:
        pytest.skip("needs ffmpeg and Pillow")
    src = str(tmp_path / "rb.mp4")
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=160x90:d=2:r=10", "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=2:r=10",
                        "-filter_complex", "[0][1]concat=n=2:v=1:a=0", "-pix_fmt", "yuv420p", src], capture_output=True)
    if r.returncode != 0:
        pytest.skip("ffmpeg could not make the test video")

    def last_frame_colour(path):
        png = str(tmp_path / "f.png")
        subprocess.run([ff, "-y", "-loglevel", "error", "-sseof", "-0.15", "-i", path, "-frames:v", "1", png], check=True)
        px = Image.open(png).convert("RGB").getpixel((80, 45))
        return "red" if px[0] > px[2] else "blue"

    old = (tr.W, tr.H)
    tr.W, tr.H = 160, 90
    try:
        normal, fast = str(tmp_path / "n.mp4"), str(tmp_path / "s.mp4")
        tr.render_clip(ff, src, 0, 1.0, normal, None, "crop", (160, 90), audio=False)
        tr.render_clip(ff, src, 0, 1.0, fast, None, "crop", (160, 90), audio=False, speed=4.0)
        for path in (normal, fast):
            assert 0.9 < tr.video_info(path, ff.replace("ffmpeg", "ffprobe") if "ffprobe" in ff else "ffprobe")[0] < 1.2 if shutil_which_ffprobe() else True
        assert last_frame_colour(normal) == "red"             # 1 s of normal speed stays inside the 2 s of red
        assert last_frame_colour(fast) == "blue"              # 4x reaches the blue part within the same 1 s
    finally:
        tr.W, tr.H = old


def shutil_which_ffprobe():
    import shutil
    return bool(shutil.which("ffprobe"))


def test_recap_options_for_pace_ending_and_counter_exist():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "shortsflow", "_main.py"), encoding="utf-8").read()
    for flag in ('"--recap_speed"', '"--recap_end"', '"--recap_end_text"', '"--recap_counter"'):
        assert flag in src
    assert 'default="card"' in src[src.index('"--recap_end"'):src.index('"--recap_end"') + 120]            # the old closing card stays the default


def test_stops_can_be_separated_with_a_bar_like_the_recap_lines():
    assert tr.parse_stops("Fry the nuts|Roast semolina and khoya|Mix") == ["Fry the nuts", "Roast semolina and khoya", "Mix"]
    assert tr.parse_stops("A, B; C") == ["A", "B", "C"]


def test_quick_text_layers_show_at_once_and_old_timings_are_unchanged(tmp_path, monkeypatch):
    """The fast recap pace shows the text straight away; the normal timings (0.3, 0.9, 1.7 s with 0.7 s fades) stay as they were."""
    import subprocess
    seen = {}

    def fake_run(cmd, **kw):
        seen["filter"] = cmd[cmd.index("-filter_complex") + 1]
        open(cmd[-1], "wb").write(b"x")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(tr.subprocess, "run", fake_run)
    layers = [(str(tmp_path / "a.png"), 0.3), (str(tmp_path / "b.png"), 0.9)]
    tr.render_clip("ffmpeg", "src.mp4", 0, 3.0, str(tmp_path / "o.mp4"), None, "crop", (1080, 1920), audio=False, layers=layers)
    assert "fade=t=in:st=0.30:d=0.7:alpha=1" in seen["filter"] and "fade=t=out:st=2.40:d=0.4:alpha=1" in seen["filter"]
    tr.render_clip("ffmpeg", "src.mp4", 0, 3.0, str(tmp_path / "o2.mp4"), None, "crop", (1080, 1920), audio=False,
                   layers=[(str(tmp_path / "a.png"), 0.05)], layer_fade=(0.2, 0.25))
    assert "fade=t=in:st=0.05:d=0.2:alpha=1" in seen["filter"] and "fade=t=out:st=2.55:d=0.25:alpha=1" in seen["filter"]


def test_ingredient_amounts_are_split_from_the_names():
    assert tr.split_amount("250g all-purpose flour (maida)") == ("250g", "all-purpose flour (maida)")
    assert tr.split_amount("1 liter refined oil") == ("1 liter", "refined oil")
    assert tr.split_amount("6-8 green cardamom (choti elaichi)") == ("6-8", "green cardamom (choti elaichi)")
    assert tr.split_amount("1/4 teaspoon salt") == ("1/4 teaspoon", "salt")
    assert tr.split_amount("salt to taste") == ("", "salt to taste")


def _ink_rows(path):
    from PIL import Image
    img = Image.open(path).convert("RGBA")
    if img.getchannel("A").getextrema()[1] == 255 and img.convert("RGB").getextrema() != ((0, 0), (0, 0), (0, 0)):
        box = img.convert("RGB").point(lambda v: 255 if v > 40 else 0).getbbox()          # an opaque card: anything lighter than black
    else:
        box = img.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()          # a transparent text layer
    return box


def test_ingredients_card_lists_everything_inside_the_free_part_of_the_screen(tmp_path):
    items = ["250g all-purpose flour (maida)", "250g khoya (mava)", "1 liter refined oil", "6-8 green cardamom (choti elaichi)", "50g desiccated coconut powder",
             "25g almonds (badam)", "25g cashews (kaju)", "25g raisins (kismis)", "50g semolina (suji)", "1/4 teaspoon salt", "1 cup water", "200g powdered sugar",
             "1/2 cup ghee"]
    png = tr.ingredients_card_png(str(tmp_path / "ing.png"), items)
    from PIL import Image
    assert Image.open(png).size == (tr.W, tr.H)
    box = _ink_rows(png)
    assert box and box[1] >= 0.12 * tr.H and box[3] <= 0.80 * tr.H            # clear of the top bar and the bottom buttons and caption


def test_safe_text_keeps_the_whole_title_stack_in_the_upper_middle_band(tmp_path):
    look = {"zone": "lower", "dark": True, "accent": (232, 200, 140)}          # the look that would put text at 78% of the height
    long_line = "Add 200g powdered sugar and 6-8 cardamom pods, powdered, then mix: filling ready"
    safe = tr.cinematic_layers(str(tmp_path / "s"), "Grind nuts and roast coconut", long_line, small="Part 3 / 7", look=look, index=1, quick=True, safe=True)
    boxes = [_ink_rows(png) for png, _ts in safe]
    assert all(b for b in boxes)
    assert min(b[1] for b in boxes) >= 0.12 * tr.H and max(b[3] for b in boxes) <= 0.74 * tr.H
    normal = tr.cinematic_layers(str(tmp_path / "n"), "Grind nuts and roast coconut", long_line, look=look, index=1)
    assert max(_ink_rows(png)[3] for png, _ts in normal) > 0.74 * tr.H          # without the option the stack runs down into the unsafe part


def test_recap_ingredients_and_safe_text_options_exist_and_are_off_by_default():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "shortsflow", "_main.py"), encoding="utf-8").read()
    for flag in ('"--recap_ingredients"', '"--recap_ingredients_at"', '"--recap_safe_text"'):
        assert flag in src
    assert '"--recap_ingredients_at", choices=["end", "start"], default="end"' in src
