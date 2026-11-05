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
    assert "42.9900, 78.4600" in seen[0] and "Turquoise lake" in seen[0] and "Never invent" in seen[0]
    assert "Каинды" in seen[0] and "NEVER answer with a district" in seen[0]          # map attractions are offered, districts are ruled out
    tr.name_places(places, "Almaty", "", ask=lambda p: "not json")        # a bad answer keeps the map's name
    assert places[0]["name"] == "Kegen District"


def test_rotate_filter_values():
    assert tr.rotate_filter(0) == "" and tr.rotate_filter(90) == "transpose=1" and tr.rotate_filter(270) == "transpose=2"
    assert tr.rotate_filter(180).count("transpose=1") == 2


def test_fix_rotation_needs_both_frames_to_agree_and_asks_once_per_video():
    items = [{"file": "a", "start": 5, "end": 9, "size": (1920, 1080)}, {"file": "a", "start": 9, "end": 13, "size": (1920, 1080)},
             {"file": "b", "start": 5, "end": 9, "size": (1080, 1920)}, {"file": "c", "start": 5, "end": 9, "size": (1080, 1920)}]
    asked = []
    answers = {"a": [90, 90], "b": [90, 0], "c": [0, 0]}          # b: the frames disagree (a camera pointing up): leave it alone

    def check(frames):
        asked.append(len(frames))
        out = []
        for f in frames:
            out.append(answers[f.decode()].pop(0))
        return out
    known = {}
    n = tr.fix_rotation(items, check=check, grab=lambda f, s, e: [f.encode()], known=known)
    assert n == 1 and asked == [6]                                    # two frames for each of the three videos, in one request
    assert [i.get("rotate", 0) for i in items] == [90, 90, 0, 0]
    assert items[0]["size"] == (1080, 1920) and items[2]["size"] == (1080, 1920)
    tr.fix_rotation([{"file": "a", "start": 30, "end": 34, "size": (1920, 1080)}], check=check, grab=lambda f, s, e: [f.encode()], known=known)
    assert asked == [6]                                               # the answers are remembered: nothing is asked again


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
