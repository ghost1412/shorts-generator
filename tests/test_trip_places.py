"""Trip recap: GPS places, look-alike shots, sideways videos (all offline, no network)."""
import json
import os
import subprocess

import pytest

from engine import geo, trip_recap as tr


def test_parse_iso6709():
    assert geo.parse_iso6709("+43.2466+078.8971/") == (43.2466, 78.8971)
    assert geo.parse_iso6709("+43.0557+76.9807/") == (43.0557, 76.9807)
    assert geo.parse_iso6709("+43.2-076.9+100.5/") == (43.2, -76.9)       # altitude after the position is ignored
    assert geo.parse_iso6709("") is None and geo.parse_iso6709("junk") is None
    assert geo.parse_iso6709("+00.0000+000.0000/") is None                  # (0, 0) is "no fix"


def test_video_location_reads_the_tag():
    class R:
        stdout = json.dumps({"format": {"tags": {"location": "+42.9922+078.4640/"}}})
    assert geo.video_location("x.mp4", run=lambda *a, **k: R()) == (42.9922, 78.4640)

    class N:
        stdout = json.dumps({"format": {"tags": {}}})
    assert geo.video_location("x.mp4", run=lambda *a, **k: N()) is None


def test_group_places_splits_on_distance_and_keeps_unlocated_videos_with_the_previous_place():
    files = ["a", "b", "c", "d", "e"]
    locs = [(43.25, 78.90), (43.251, 78.901), None, (42.99, 78.46), (42.99, 78.461)]
    places = geo.group_places(files, locs)
    assert [p["files"] for p in places] == [["a", "b", "c"], ["d", "e"]]


def test_name_from_reply_prefers_a_named_feature_and_ignores_benches_and_road_codes():
    lake = {"name": "Kolsay Lakes Town", "category": "leisure", "address": {"county": "Kegen District", "state": "Almaty Region"}, "display_name": "Kolsay Lakes Town, P-16"}
    assert geo.name_from_reply(lake)["name"] == "Kolsay Lakes Town"
    bench = {"name": "", "category": "amenity", "address": {"county": "Kegen District", "state": "Almaty Region"}, "display_name": "Kegen District"}
    got = geo.name_from_reply(bench)
    assert got["name"] == "" and got["area"] == "Kegen District"
    road = {"name": "KZ05-08", "category": "highway", "address": {"county": "Kegen District"}}
    assert geo.name_from_reply(road)["name"] == ""
    assert geo.name_from_reply({"error": "Unable to geocode"}) is None


def test_place_name_caches_and_can_be_switched_off(tmp_path, monkeypatch):
    calls = []

    def fetch(lat, lon):
        calls.append((lat, lon))
        return {"name": "Kaindy", "category": "natural", "address": {"state": "Almaty Region"}, "display_name": "Kaindy"}
    cache = str(tmp_path / "places.json")
    monkeypatch.delenv("SHORTSFLOW_GEOCODE", raising=False)
    assert geo.place_name((42.9922, 78.4640), cache, fetch=fetch)["name"] == "Kaindy"
    assert geo.place_name((42.9923, 78.4641), cache, fetch=fetch)["name"] == "Kaindy"      # same 3-decimal cell: from the cache
    assert len(calls) == 1
    monkeypatch.setenv("SHORTSFLOW_GEOCODE", "off")
    assert geo.place_name((10.0, 10.0), None, fetch=fetch) is None and len(calls) == 1


def m(file, start, loc=None):
    return {"file": file, "start": start, "end": start + 4, "loc": loc}


def test_same_scene_by_spot_and_time():
    here = (43.0557, 76.9807)
    a = m("/v/101000_aa.mp4", 2, here)
    b = m("/v/101130_bb.mp4", 1, (43.0558, 76.9806))        # 90 s later, a few metres away: the same scene
    far = m("/v/101130_cc.mp4", 1, (43.30, 77.5))
    late = m("/v/120000_dd.mp4", 1, here)                   # two hours later at the same spot: a new shot
    assert tr.same_scene(a, b)
    assert not tr.same_scene(a, far) and not tr.same_scene(a, late)
    assert not tr.same_scene(m("/v/x.mp4", 1, here), m("/v/y.mp4", 1, here))      # no times in the names: cannot tell, keep both


def test_spread_moments_drops_the_same_scene_and_fills_up_from_spares():
    here = (43.0, 77.0)
    cands = [m("/v/100000_a.mp4", 0, here), m("/v/100100_b.mp4", 0, here), m("/v/100200_c.mp4", 0, here), m("/v/130000_d.mp4", 0, (43.2, 77.3))]
    chosen, spares = tr.spread_moments(cands, 2)
    assert [c["file"][-8:] for c in chosen] == ["00_a.mp4", "00_d.mp4"]
    assert len(spares) == 2
    chosen, spares = tr.spread_moments(cands, 4)          # only two real scenes, but four asked: repeats beat missing shots
    assert len(chosen) == 4 and not spares and chosen == cands


def test_same_description_and_drop_repeats_swaps_in_a_different_spare():
    assert tr.same_description("Couple posing in a snowy mountain landscape", "A couple posing in snowy mountains landscape")
    assert not tr.same_description("Couple posing in a snowy mountain landscape", "River flowing through autumn forest")
    one, two = m("/v/100000_a.mp4", 0), m("/v/100500_b.mp4", 0)
    one["visual"], two["visual"] = "Couple posing in a snowy mountain landscape", "Couple posing in a snowy mountain landscape"
    spare = m("/v/110000_c.mp4", 0)
    texts = {id(spare): "Autumn river valley with yellow trees"}

    def describe_one(x):
        x["visual"] = texts[id(x)]
    out = tr.drop_repeats([one, two], [spare], describe_one)
    assert out == [one, spare]
    out = tr.drop_repeats([one, dict(two)], [], describe_one)       # nothing to swap in: the repeat stays
    assert len(out) == 2


def test_name_places_uses_the_map_first_and_the_llm_only_to_improve_it(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_GEOCODE", raising=False)
    monkeypatch.setattr(geo, "place_name", lambda loc, cache_path=None, **k: {"name": "", "area": "Kegen District", "region": "Almaty Region", "hint": "Kegen District"})
    monkeypatch.setattr(geo, "nearby_attractions", lambda loc, cache_path=None, **k: ["Каинды", "Viewpoint shelter"])
    places = [{"center": (42.99, 78.46), "files": ["a"], "visuals": ["Turquoise lake among spruce trees"]}, {"center": None, "files": ["b"], "visuals": []}]
    seen = []

    def ask(prompt):
        seen.append(prompt)
        return '[{"id": 1, "name": "Kaindy Lake"}]'
    tr.name_places(places, "Almaty", "", ask=ask)
    assert places[0]["name"] == "Kaindy Lake" and places[1]["name"] == ""
    assert "42.9900, 78.4600" in seen[0] and "Turquoise lake" in seen[0] and "do not guess" in seen[0]
    assert "Каинды" in seen[0] and "NEVER answer with a district" in seen[0]          # map attractions are offered, districts are ruled out
    tr.name_places(places, "Almaty", "", ask=lambda p: "not json")        # a bad answer keeps the map's name
    assert places[0]["name"] == "Kegen District"


def test_rotate_filter_values():
    assert tr.rotate_filter(0) == "" and tr.rotate_filter(90) == "transpose=1" and tr.rotate_filter(270) == "transpose=2"
    assert tr.rotate_filter(180).count("transpose=1") == 2


def test_fix_rotation_judges_every_moment_on_its_own_and_needs_both_frames_to_agree():
    # a phone turned sideways in the middle of ONE video: only the later moment is wrong
    items = [{"file": "a", "start": 2.0, "end": 6.0, "size": (1080, 1920)}, {"file": "a", "start": 30.0, "end": 34.0, "size": (1080, 1920)},
             {"file": "b", "start": 5.0, "end": 9.0, "size": (1080, 1920)}, {"file": "c", "start": 5.0, "end": 9.0, "size": (1080, 1920)}]
    answers = {("a", 2): [0, 0], ("a", 30): [270, 270], ("b", 5): [90, 0], ("c", 5): [0, 0]}      # b: the two frames disagree

    def grab(f, lo, hi):
        return [f"{f}|{round(lo)}".encode()]

    asked = []

    def check(frames):
        asked.append(len(frames))
        out = []
        for fr in frames:
            name, lo = fr.decode().split("|")
            key = (name, (2 if float(lo) < 20 else 30) if name == "a" else 5)
            out.append(answers[key].pop(0))
        return out
    known = {}
    n = tr.fix_rotation(items, check=check, grab=grab, known=known)
    assert n == 1 and asked == [8]                                   # two frames for each of the four moments, in one request
    assert [i.get("rotate", 0) for i in items] == [0, 270, 0, 0]
    assert items[1]["size"] == (1920, 1080) and items[0]["size"] == (1080, 1920)
    tr.fix_rotation([{"file": "a", "start": 30.0, "end": 34.0, "size": (1080, 1920)}], check=check, grab=grab, known=known)
    assert asked == [8]                                              # remembered: nothing is asked again for that moment


def test_when_gemini_cannot_answer_the_local_sky_check_decides():
    items = [{"file": "a", "start": 0.0, "end": 4.0, "size": (1080, 1920)}]
    tr.fix_rotation(items, check=lambda frames: None, grab=lambda f, lo, hi: [b"x"], local=lambda frames: [270] * len(frames))
    assert items[0]["rotate"] == 270
    quiet = [{"file": "b", "start": 0.0, "end": 4.0, "size": (1080, 1920)}]
    tr.fix_rotation(quiet, check=lambda frames: None, grab=lambda f, lo, hi: [b"x"], local=lambda frames: [90, 0])        # frames disagree
    assert "rotate" not in quiet[0]


def test_check_rotation_maps_where_the_top_is_to_a_clockwise_turn(monkeypatch):
    from engine import visual_context as vc
    import io
    reply = {"candidates": [{"content": {"parts": [{"text": '[{"id": 1, "up": "top"}, {"id": 2, "up": "right"}, {"id": 3, "up": "left"}, {"id": 4, "up": "bottom"}]'}]}}]}
    monkeypatch.setattr(vc.urllib.request, "urlopen", lambda req, timeout=0: io.BytesIO(json.dumps(reply).encode()))
    assert vc.check_rotation([b"1", b"2", b"3", b"4"], key="k") == [0, 270, 90, 180]


def test_check_rotation_without_a_key_does_nothing(monkeypatch):
    from engine import visual_context as vc
    monkeypatch.setattr(vc, "gemini_key", lambda: None)
    assert vc.check_rotation([b"x"]) is None


def test_landmarks_come_before_districts_in_the_title_line():
    assert tr.landmarks_first(["Almaly District", "Kaindy Lake", "Almaty Region", "Charyn Canyon"]) == ["Kaindy Lake", "Charyn Canyon", "Almaly District", "Almaty Region"]


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="needs ffmpeg")
def test_render_clip_turns_a_sideways_video_upright(tmp_path):
    ff = __import__("shutil").which("ffmpeg")
    src = str(tmp_path / "wide.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=2:r=10", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "2", "-pix_fmt", "yuv420p", src], check=True)
    old = (tr.W, tr.H)
    tr.W, tr.H = 180, 320
    try:
        out = str(tmp_path / "turned.mp4")
        tr.render_clip(ff, src, 0, 1.0, out, None, "crop", (320, 180), audio=False, rotate=90)
        assert os.path.isfile(out) and tr.video_info(out)[1:] == (180, 320)
    finally:
        tr.W, tr.H = old


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="needs ffmpeg")
def test_trip_title_shot_is_not_repeated_as_the_first_shot_of_day_one(tmp_path):
    ff = __import__("shutil").which("ffmpeg")
    (tmp_path / "day1").mkdir()
    for n, tone in (("a.mp4", 300), ("b.mp4", 500)):
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=15:duration=30", "-f", "lavfi", "-i", f"sine=f={tone}:d=30",
                        "-shortest", "-pix_fmt", "yuv420p", str(tmp_path / "day1" / n)], check=True)
    shots, real = [], tr.render_clip

    def spy(ffmpeg, src, start, seconds, out, *a, **k):
        shots.append((os.path.basename(out), os.path.basename(src), round(start, 1)))
        return real(ffmpeg, src, start, seconds, out, *a, **k)
    tr.render_clip = spy
    try:
        tr.make_recap([str(tmp_path / "day1")], str(tmp_path / "out"), trip_name="T", total_seconds=40, style="cinematic", aspect="16:9",
                      ask=lambda p: "{}", geocode=False)
    finally:
        tr.render_clip = real
    title = [s for s in shots if s[0] == "trip_title.mp4"]
    day = [s for s in shots if s[0].startswith("clip_1_")]
    assert title and day and all(t[1:] != d[1:] for t in title for d in day)


def test_nearby_attractions_collects_named_places_and_caches_them(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_GEOCODE", raising=False)
    rows = {"viewpoint": [{"name": "Black Charyn Canyon"}, {"name": ""}], "waterfall": [{"name": "Maiden tears"}], "lake": [],
            "attraction": [{"name": "Black Charyn Canyon"}], "park": [{"name": "KZ05-11"}]}
    calls = []

    def fetch(q, lat, lon, span):
        calls.append(q)
        return rows[q]
    cache = str(tmp_path / "places.json")
    assert geo.nearby_attractions((43.35, 79.05), cache, fetch=fetch) == ["Black Charyn Canyon", "Maiden tears"]
    assert geo.nearby_attractions((43.3504, 79.0504), cache, fetch=fetch) == ["Black Charyn Canyon", "Maiden tears"]      # same cell: cached
    assert len(calls) == len(geo.ATTRACTION_QUERIES)
    monkeypatch.setenv("SHORTSFLOW_GEOCODE", "off")
    assert geo.nearby_attractions((10.0, 10.0), None, fetch=fetch) == []


def test_nearby_attractions_offline_is_not_cached_as_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_GEOCODE", raising=False)

    def down(q, lat, lon, span):
        raise OSError("offline")
    cache = str(tmp_path / "places.json")
    assert geo.nearby_attractions((43.0, 77.0), cache, fetch=down) == []
    assert not os.path.exists(cache)                                    # a failed lookup must not be remembered as "nothing there"


def test_manual_rotation_parses_and_forces_the_turn_and_size():
    assert tr.parse_rotations("183047=270, 101930_CLN=90;bad;x=45") == [("183047", 270), ("101930_CLN", 90)]
    assert tr.parse_rotations("") == [] and tr.parse_rotations("a=-90") == [("a", 270)]
    items = [{"file": "/v/183047_ufRMEJTR.mp4", "size": (1080, 1920), "start": 0, "end": 4},
             {"file": "/v/183047_ufRMEJTR.mp4", "size": (1920, 1080), "rotate": 90, "start": 9, "end": 13},      # had an automatic 90 turn
             {"file": "/v/other.mp4", "size": (1920, 1080), "start": 0, "end": 4}]
    assert tr.apply_rotations(items, [("183047", 270)]) == 2
    assert items[0]["rotate"] == 270 and items[0]["size"] == (1920, 1080)
    assert items[1]["rotate"] == 270 and items[1]["size"] == (1920, 1080)          # swapped back to the file as shown, then for the new turn
    assert "rotate" not in items[2] and items[2]["size"] == (1920, 1080)
    cancel = {"file": "/v/183047_x.mp4", "size": (1080, 1920), "rotate": 90}
    tr.apply_rotations([cancel], [("183047", 0)])
    assert cancel["rotate"] == 0 and cancel["size"] == (1920, 1080)


def test_boring_shots_are_swapped_for_a_spare():
    assert tr.looks_boring("A still shot of an empty wooden bench on a paved area") and tr.looks_boring("Blurry footage of a pocket")
    assert not tr.looks_boring("A woman in a dark jacket stands at a turquoise lake")
    a, b = m("/v/100000_a.mp4", 0), m("/v/110000_b.mp4", 0)
    a["visual"], b["visual"] = "An empty bench in a park", "A woman hikes along a river"
    spare = m("/v/105000_c.mp4", 0)

    def describe_one(x):
        x["visual"] = "A waterfall drops into a pool"
    out = tr.drop_repeats([a, b], [spare], describe_one)
    assert out[0] is spare and out[1] is b                                            # the empty bench made room for a better shot
    assert tr.drop_repeats([a], [], describe_one) == [a]                              # nothing better: it stays


def test_the_cinematic_plan_does_not_reserve_time_for_title_cards():
    with_cards, _ = tr.plan_days([5, 5, 5, 5, 5], 80)
    without, _ = tr.plan_days([5, 5, 5, 5, 5], 80, card=0.0)
    assert sum(without) > sum(with_cards)


def _no_network(monkeypatch, near=()):
    monkeypatch.delenv("SHORTSFLOW_GEOCODE", raising=False)
    monkeypatch.setattr(geo, "place_name", lambda loc, cache_path=None, **k: {"name": "", "area": "Kegen District", "region": "Almaty Region", "hint": "Kegen District"})
    monkeypatch.setattr(geo, "nearby_attractions", lambda loc, cache_path=None, **k: list(near))


def test_place_overrides_parse_and_win_over_the_ai(monkeypatch):
    assert tr.parse_place_overrides("42.985,78.465=Kaindy Lake; 42.991, 78.326 = Kolsay Lakes;bad;1,2=") == [(42.985, 78.465, "Kaindy Lake"), (42.991, 78.326, "Kolsay Lakes")]
    _no_network(monkeypatch)
    places = [{"center": (42.9851, 78.4652), "files": ["a"], "visuals": []}, {"center": (43.35, 79.05), "files": ["b"], "visuals": []}]
    asked = []
    tr.name_places(places, ask=lambda p: asked.append(p) or '[{"id": 1, "name": "Wrong"}, {"id": 2, "name": "Charyn Canyon"}]', overrides=tr.parse_place_overrides("42.985,78.465=Kaindy Lake"))
    assert [p["name"] for p in places] == ["Kaindy Lake", "Charyn Canyon"]                  # typed name kept, the other asked
    assert len(asked) == 1 and "[1]" not in asked[0] and "[2]" in asked[0]               # the typed place was not even put to the AI


def test_shots_from_a_plane_are_named_in_flight_without_asking():
    places = [{"center": (43.29, 75.6), "files": ["a"], "visuals": ["Aerial view from airplane window over clouds"]}]
    import engine.geo as g
    orig_p, orig_n = g.place_name, g.nearby_attractions
    g.place_name, g.nearby_attractions = (lambda *a, **k: None), (lambda *a, **k: [])
    try:
        tr.name_places(places, ask=lambda p: (_ for _ in ()).throw(AssertionError("must not ask")))
    finally:
        g.place_name, g.nearby_attractions = orig_p, orig_n
    assert places[0]["name"] == "In flight"


def test_the_same_name_on_two_far_places_is_corrected_or_dropped(monkeypatch):
    _no_network(monkeypatch)
    places = [{"center": (42.985, 78.465), "files": ["a"], "visuals": []}, {"center": (42.991, 78.326), "files": ["b"], "visuals": []}]
    answers = iter(['[{"id": 1, "name": "Kolsay Lakes"}, {"id": 2, "name": "Kolsay Lakes"}]', '[{"id": 1, "name": "Kaindy Lake"}, {"id": 2, "name": "Kolsay Lakes"}]'])
    prompts = []
    tr.name_places(places, ask=lambda p: prompts.append(p) or next(answers))
    assert [p["name"] for p in places] == ["Kaindy Lake", "Kolsay Lakes"] and "SAME name" in prompts[1]
    # still the same name after the corrective request: only the first keeps it
    places2 = [{"center": (42.985, 78.465), "files": ["a"], "visuals": []}, {"center": (42.991, 78.326), "files": ["b"], "visuals": []}]
    both = '[{"id": 1, "name": "Kolsay Lakes"}, {"id": 2, "name": "Kolsay Lakes"}]'
    tr.name_places(places2, ask=lambda p: both)
    assert places2[0]["name"] == "Kolsay Lakes" and tr.is_plain_area(places2[1]["name"])      # the loser falls back to the map's area name, which is never shown
    assert tr.name_conflicts([{"center": (1.0, 1.0), "name": "A Lake"}, {"center": (1.001, 1.001), "name": "A Lake"}]) == []      # same lake, 150 m


def test_an_unsure_ai_answers_blank_and_the_map_fallback_stays(monkeypatch):
    _no_network(monkeypatch)
    places = [{"center": (43.0, 77.0), "files": ["a"], "visuals": []}]
    tr.name_places(places, ask=lambda p: '[{"id": 1, "name": ""}]')
    assert places[0]["name"] == "Kegen District" and tr.is_plain_area(places[0]["name"])          # kept for the itinerary, never shown on screen


def test_old_cached_names_are_not_trusted_and_new_ones_are_remembered(tmp_path, monkeypatch):
    _no_network(monkeypatch)
    cache = tmp_path / "places.json"
    (tmp_path / "place_names.json").write_text('{"v2:43.000,77.000": "Wrong Old Name"}', encoding="utf-8")
    places = [{"center": (43.0, 77.0), "files": ["a"], "visuals": []}]
    tr.name_places(places, ask=lambda p: '[{"id": 1, "name": "Big Almaty Lake"}]', cache_path=str(cache))
    assert places[0]["name"] == "Big Almaty Lake"
    saved = json.loads((tmp_path / "place_names.json").read_text(encoding="utf-8"))
    assert saved["v3:43.000,77.000"] == "Big Almaty Lake"
    again = [{"center": (43.0, 77.0), "files": ["a"], "visuals": []}]
    tr.name_places(again, ask=lambda p: (_ for _ in ()).throw(AssertionError("cached: no request")), cache_path=str(cache))
    assert again[0]["name"] == "Big Almaty Lake"


def test_on_screen_labels_are_place_names_only_and_only_when_the_place_changes_in_the_cinematic_look():
    days = [{"moments": [{"place": "Kaindy Lake"}, {"place": "Kaindy Lake"}, {"place": "Kegen District"}, {"place": "Kolsay Lakes"}]},
            {"moments": [{"place": "Kolsay Lakes"}, {}]}]
    assert tr.moment_labels(days, cine=True) == [["Kaindy Lake", "", "", "Kolsay Lakes"], ["", ""]]
    assert tr.moment_labels(days, cine=False) == [["Kaindy Lake", "Kaindy Lake", "", "Kolsay Lakes"], ["Kolsay Lakes", ""]]


def test_places_review_lists_names_coordinates_and_map_links(tmp_path):
    places = [{"center": (42.985, 78.465), "name": "Kaindy Lake", "files": ["a", "b"], "visuals": ["A turquoise lake"]},
              {"center": (43.0, 77.0), "name": "Kegen District", "files": ["c"], "visuals": []}, {"center": None, "name": "", "files": []}]
    path = tr.write_places_review(str(tmp_path / "places_review.md"), places, "Almaty")
    text = open(path, encoding="utf-8").read()
    assert "google.com/maps?q=42.9850,78.4650" in text and "**Kaindy Lake**" in text and "2 video(s)" in text
    assert "not shown on screen" in text and "--place_names" in text


def test_avoid_reads_earlier_recaps_and_skips_moments_that_overlap_them(tmp_path):
    for sub in ("", "portrait", "landscape"):
        d = tmp_path / "recap" / sub
        d.mkdir(parents=True, exist_ok=True)
    (tmp_path / "recap" / "portrait" / "itinerary.json").write_text(json.dumps({"days": [{"moments": [{"file": "C:" + chr(92) + "v" + chr(92) + "104340_a.mp4", "start": 4.0, "end": 8.8}]}]}), encoding="utf-8")
    (tmp_path / "recap" / "landscape" / "itinerary.json").write_text(json.dumps({"days": [{"moments": [{"file": "/v/day3/090000_b.mp4", "start": 0.0, "end": 4.8}]}, {"moments": []}]}), encoding="utf-8")
    avoid = tr.load_avoid(f"{tmp_path / 'recap'}, {tmp_path / 'missing'}")
    assert avoid == {("104340_a.mp4", 4.0, 8.8), ("090000_b.mp4", 0.0, 4.8)}
    assert tr.was_used("/other/folder/104340_a.mp4", 4.5, 9.3, avoid)           # mostly the same stretch
    assert not tr.was_used("/x/104340_a.mp4", 9.0, 13.8, avoid)                 # a different stretch of the same video
    assert not tr.was_used("/x/other.mp4", 4.0, 8.8, avoid) and tr.load_avoid("") == set()
    direct = tr.load_avoid(str(tmp_path / "recap" / "portrait" / "itinerary.json"))
    assert direct == {("104340_a.mp4", 4.0, 8.8)}                                # a single itinerary.json works too


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="needs ffmpeg")
def test_a_second_recap_with_avoid_uses_different_stretches_of_the_footage(tmp_path):
    ff = __import__("shutil").which("ffmpeg")
    (tmp_path / "day1").mkdir()
    for n, tone in (("a.mp4", 300), ("b.mp4", 500), ("c.mp4", 700)):
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10:duration=40", "-f", "lavfi", "-i", f"sine=f={tone}:d=40",
                        "-shortest", "-pix_fmt", "yuv420p", str(tmp_path / "day1" / n)], check=True)
    first = tr.make_recap([str(tmp_path / "day1")], str(tmp_path / "one"), total_seconds=30, style="plain", aspect="16:9", ask=lambda p: "{}", geocode=False)
    second = tr.make_recap([str(tmp_path / "day1")], str(tmp_path / "two"), total_seconds=30, style="plain", aspect="16:9", ask=lambda p: "{}", geocode=False,
                           avoid=str(tmp_path / "one"))
    used = lambda r: {(os.path.basename(m["file"]), round(m["start"])) for d in json.load(open(r["itinerary_json"], encoding="utf-8"))["days"] for m in d["moments"]}   # noqa: E731
    assert used(first) and used(second) and not (used(first) & used(second))


def _jpeg_with_bands(top=None, bottom=None, left=None, right=None, size=96):
    import io
    from PIL import Image
    img = Image.new("RGB", (size, size), (70, 60, 40))                       # brown ground everywhere
    px = img.load()
    band = 14
    for x in range(size):
        for y in range(size):
            for side, cond in (("top", y < band), ("bottom", y >= size - band), ("left", x < band), ("right", x >= size - band)):
                if cond and {"top": top, "bottom": bottom, "left": left, "right": right}[side]:
                    px[x, y] = (150, 190, 245)                                # bright smooth blue sky
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def test_sky_side_finds_a_clear_sky_edge_and_is_silent_otherwise():
    from engine import visual_context as vc
    assert vc.sky_side(_jpeg_with_bands(top=True)) == "top"
    assert vc.sky_side(_jpeg_with_bands(right=True)) == "right" and vc.sky_side(_jpeg_with_bands(left=True)) == "left"
    assert vc.sky_side(_jpeg_with_bands(bottom=True)) == "bottom"
    assert vc.sky_side(_jpeg_with_bands()) is None                            # no sky anywhere
    assert vc.sky_side(_jpeg_with_bands(top=True, right=True)) is None        # two equal candidates: not sure
    assert vc.sky_side(b"not an image") is None
    assert vc.local_rotation([_jpeg_with_bands(right=True), _jpeg_with_bands(top=True), _jpeg_with_bands()]) == [270, 0, 0]


def test_the_same_spot_on_different_days_is_named_once_and_shares_the_name(monkeypatch):
    _no_network(monkeypatch)
    places = [{"center": (43.2575, 76.9414), "files": ["d1"], "visuals": ["Night park path with fallen leaves"]},
              {"center": (43.2576, 76.9415), "files": ["d4"], "visuals": ["A woman hiking near a small waterfall"]},
              {"center": (42.99, 78.33), "files": ["d2"], "visuals": []}]
    prompts = []
    answers = iter(['[{"id": 1, "name": "Republic Square"}, {"id": 3, "name": "Kolsay Lakes"}]'])
    tr.name_places(places, ask=lambda p: prompts.append(p) or next(answers))
    assert places[0]["name"] == places[1]["name"] == "Republic Square" and places[2]["name"] == "Kolsay Lakes"
    assert len(prompts) == 1 and "[2]" not in prompts[0] and "waterfall" in prompts[0]      # one question for the spot, with both days' pictures


def test_a_place_the_ai_is_unsure_about_keeps_the_maps_own_name():
    import engine.geo as g
    orig = g.place_name, g.nearby_attractions
    g.place_name, g.nearby_attractions = (lambda *a, **k: {"name": "Kolsay Lakes Town", "area": "Kegen District", "hint": "x"}), (lambda *a, **k: [])
    try:
        places = [{"center": (42.9913, 78.3261), "files": ["a"], "visuals": []}]
        tr.name_places(places, ask=lambda p: '[{"id": 1, "name": ""}]')
    finally:
        g.place_name, g.nearby_attractions = orig
    assert places[0]["name"] == "Kolsay Lakes Town"                        # a named map feature beats leaving the stop unnamed


def test_the_second_version_reuses_the_first_versions_place_names(tmp_path):
    a, b = tmp_path / "portrait", tmp_path / "landscape"
    a.mkdir()
    b.mkdir()
    (a / "place_names.json").write_text(json.dumps({"v3:42.985,78.465": "Kaindy Lake", "v3:43.354,79.058": "Charyn Canyon"}), encoding="utf-8")
    (b / "place_names.json").write_text(json.dumps({"v3:42.985,78.465": "Something Else", "v3:43.111,77.111": "Shymbulak"}), encoding="utf-8")
    assert tr.share_place_names(str(a), str(b)) == 2
    merged = json.loads((b / "place_names.json").read_text(encoding="utf-8"))
    assert merged == {"v3:42.985,78.465": "Kaindy Lake", "v3:43.354,79.058": "Charyn Canyon", "v3:43.111,77.111": "Shymbulak"}   # the first version's names win
    assert tr.share_place_names(str(tmp_path / "none"), str(b)) == 0
