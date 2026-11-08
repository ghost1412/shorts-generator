import random

from engine import puzzle_variety as pv


def test_fresh_avoids_recent_picks_and_remembers(tmp_path):
    path = str(tmp_path / "h.json")
    rng = random.Random(1)
    opts = ["a", "b", "c", "d", "e", "f"]
    picks = [pv.fresh(opts, "k", rng=rng, path=path) for _ in range(3)]
    assert len(set(picks)) == 3                      # the last half of the list is skipped, so no repeat within 3 picks
    assert pv.fresh(opts, "other", rng=rng, path=path) in opts


def test_fresh_works_with_one_option_and_a_broken_history_file(tmp_path):
    path = tmp_path / "h.json"
    path.write_text("not json")
    assert pv.fresh(["only"], "k", path=str(path)) == "only"
    assert pv.fresh(["only"], "k", path=str(path)) == "only"


def test_real_emojis_and_fit_check():
    from engine import script_gen as g
    assert len(g._real_emojis("🦁 👑 🌅")) == 3 and g._real_emojis("|, abc 12") == []
    assert g.emojis_fit_answer("🦁 👑", "The Lion King", "Disney movie", ask=lambda q: '{"kind_ok": true, "emojis_fit": true}') is True
    assert g.emojis_fit_answer("🌟 💎", "Alamogordo", "Movie", ask=lambda q: '{"kind_ok": false, "emojis_fit": false}') is False

    def broken(q):
        raise RuntimeError("rate limited")
    assert g.emojis_fit_answer("🦁 👑", "The Lion King", "Disney movie", ask=broken) is True      # a failed check never blocks a run


def test_recent_and_record(tmp_path):
    path = str(tmp_path / "h.json")
    pv.record("x", "Titanic", path=path)
    pv.record("x", "Frozen", path=path)
    assert pv.recent("x", path=path) == ["Titanic", "Frozen"] and pv.recent("y", path=path) == []


def test_odd_variants_are_clearly_different_and_keep_size_and_transparency():
    from PIL import Image, ImageChops
    from engine import video_gen as vg
    base = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    for x in range(20, 100):
        for y in range(30, 90):
            base.putpixel((x, y), (200, 60, 40, 255) if x < 60 else (40, 90, 200, 255))
    for effect in vg.ODD_EFFECTS:
        odd = vg.make_odd_variant(base, effect)
        assert odd.size == base.size and odd.mode == "RGBA"
        diff = ImageChops.difference(odd.convert("RGB"), base.convert("RGB")).convert("L")
        assert sum(diff.getdata()) > 120 * 120 * 3, effect                 # not a near-invisible change
        assert odd.getpixel((2, 2))[3] == 0 or effect == "tilt"             # transparent corners stay transparent


def test_odd_levels_get_harder_and_pick_is_valid():
    import random
    from PIL import Image, ImageChops
    from engine import video_gen as vg
    base = Image.new("RGBA", (150, 150), (0, 0, 0, 255))
    for x in range(150):
        for y in range(150):
            base.putpixel((x, y), (x * 255 // 150, 90, y * 255 // 150, 255) if (x // 5 + y // 5) % 2 else (200, 40, 60, 255))     # a checker has edges, so blur shows

    def change(effect, level):
        diff = ImageChops.difference(vg.make_odd_variant(base, effect, level).convert("RGB"), base.convert("RGB")).convert("L")
        return sum(diff.getdata())

    for effect in ("tilt", "hue", "dark", "blur"):
        assert change(effect, "easy") > change(effect, "medium") > change(effect, "hard") > 0, effect
    assert {vg.pick_odd_level(random.Random(i)) for i in range(200)} == {"easy", "medium", "hard"}
