import os

import numpy as np
import pytest
from PIL import Image, ImageFilter

from engine import photo_reel_types as prt


def _photo(path, seed, blur=0, date=None, size=(160, 120)):
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (size[1] // 8, size[0] // 8, 3), dtype=np.uint8)
    im = Image.fromarray(base).resize(size, Image.NEAREST)
    im = Image.fromarray((np.asarray(im, dtype=np.int16) + rng.integers(-40, 40, (size[1], size[0], 3))).clip(0, 255).astype("uint8"))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    exif = Image.Exif()
    if date:
        exif[306] = date
    im.save(path, exif=exif)
    return str(path)


def _set(tmp_path, specs):
    return [_photo(tmp_path / f"p{i}.jpg", **kw) for i, kw in enumerate(specs)]


def test_sharpness_ranks_a_blurred_copy_lower():
    rng = np.random.default_rng(3)
    img = rng.integers(0, 255, (120, 160)).astype(np.float32)
    blurred = np.asarray(Image.fromarray(img.astype("uint8")).filter(ImageFilter.GaussianBlur(4)), dtype=np.float32)
    assert prt.sharpness(img) > prt.sharpness(blurred) * 5


def test_near_duplicates_keep_the_sharper_and_blurry_ones_go(tmp_path):
    files = _set(tmp_path, [dict(seed=1), dict(seed=1, blur=1.2), dict(seed=2), dict(seed=3), dict(seed=4, blur=6), dict(seed=5)])
    infos = [prt.analyse(f) for f in files]
    kept = [os.path.basename(i["path"]) for i in prt.select_photos(infos, max_n=10)]
    assert "p0.jpg" in kept and "p1.jpg" not in kept          # the sharp original of the duplicate pair stays
    assert "p4.jpg" not in kept                               # heavily blurred: dropped
    assert kept == sorted(kept)                               # input order preserved


def test_selection_never_drops_below_the_minimum(tmp_path):
    files = _set(tmp_path, [dict(seed=1), dict(seed=1), dict(seed=1)])           # three copies of one shot
    infos = [prt.analyse(f) for f in files]
    assert len(prt.select_photos(infos, max_n=10, min_keep=3)) == 3


def test_too_many_photos_keeps_the_sharpest(tmp_path):
    files = _set(tmp_path, [dict(seed=i, blur=(0 if i % 2 else 2.0)) for i in range(10, 20)])
    infos = [prt.analyse(f) for f in files]
    picked = prt.select_photos(infos, max_n=5, min_keep=3)
    assert len(picked) == 5 and all(prt.analyse(i["path"])["sharp"] >= min(x["sharp"] for x in infos) for i in picked)


def test_chronological_order_uses_exif_dates(tmp_path):
    files = _set(tmp_path, [dict(seed=1, date="2024:08:02 10:00:00"), dict(seed=2, date="2023:01:05 09:00:00"),
                            dict(seed=3, date="2024:08:01 18:30:00")])
    infos = prt.order_photos([prt.analyse(f) for f in files], "chronological")
    assert [os.path.basename(i["path"]) for i in infos] == ["p1.jpg", "p2.jpg", "p0.jpg"]
    assert [os.path.basename(i["path"]) for i in prt.order_photos([prt.analyse(f) for f in files], "given")] == ["p0.jpg", "p1.jpg", "p2.jpg"]


def test_times_cover_the_target_and_hold_first_and_last_longer():
    starts = prt.plan_times(6, 30.0)
    assert starts[0] == 0.0 and starts == sorted(starts) and starts[-1] < 30.0
    gaps = [b - a for a, b in zip(starts, starts[1:])] + [30.0 - starts[-1]]
    assert abs(sum(gaps) - 30.0) < 0.1 and gaps[0] > gaps[2] and gaps[-1] > gaps[2]
    assert prt.plan_times(3, 9.0) == [0.0, 3.0, 6.0]                      # too few for a hero hold: even


def test_captions_per_type():
    infos = [{"date": None}, {"date": None}, {"date": None}, {"date": None}]
    assert prt.make_captions("countdown", infos) == ["#4", "#3", "#2", "#1"]
    assert prt.make_captions("then_now", infos) == ["THEN", "THEN", "NOW", "NOW"]
    assert prt.make_captions("days", infos) == ["Stop 1", "Stop 2", "Stop 3", "Stop 4"]       # no dates: stops
    from datetime import datetime
    dated = [{"date": datetime(2024, 8, 1)}, {"date": datetime(2024, 8, 1)}, {"date": datetime(2024, 8, 3)}]
    assert prt.make_captions("days", dated) == ["Day 1", "Day 1", "Day 2"]
    assert prt.make_captions("dates", dated)[0] == "August 2024"
    assert prt.make_captions("countdown", infos, ["best", "good"])[:2] == ["#4 best", "#3 good"]   # own lines join the numbers
    assert prt.make_captions("features", infos, ["Waterproof"])[0] == "Waterproof"
    assert prt.make_captions("then_now", infos, ["with mum"])[0] == "THEN · with mum"      # the THEN / NOW label stays


def test_plan_reel_for_every_type(tmp_path):
    files = _set(tmp_path, [dict(seed=20 + i, date=f"2024:0{1 + i % 9}:1{i % 9} 10:00:00") for i in range(7)])
    for t in prt.type_names():
        plan = prt.plan_reel(files, t, target_duration=24.0, name="Mia", texts=["one", "two"])
        assert plan["type"] == t and len(plan["photos"]) == len(plan["captions"]) == len(plan["starts"]) >= 3
        assert plan["captions"][-1] and plan["title"] and plan["style"]["accent"].startswith("#")
        assert plan["starts"][-1] < plan["duration"]
    assert "Mia" in prt.plan_reel(files, "tribute", name="Mia")["title"]
    assert prt.plan_reel(files, "countdown")["title"].startswith("Top ")


def test_plan_errors_are_plain(tmp_path):
    files = _set(tmp_path, [dict(seed=1), dict(seed=2)])
    with pytest.raises(ValueError, match="at least 3"):
        prt.plan_reel(files, "memories")
    with pytest.raises(ValueError, match="Unknown reel type"):
        prt.plan_reel(files, "nope")


def test_parse_texts():
    assert prt.parse_texts("a | b\nc") == ["a", "b", "c"] and prt.parse_texts(["x", " "]) == ["x"] and prt.parse_texts(None) == []


def test_smooth_gradients_are_not_mistaken_for_duplicates(tmp_path):
    # unrelated pictures dominated by the same gradient share an average hash; the gradient hash tells them apart
    paths = []
    for k in range(4):
        rng = np.random.default_rng(100 + k)
        arr = np.tile(np.linspace(230, 20, 120)[:, None, None], (1, 160, 3)).astype(np.float32)
        for _ in range(12):
            x, y = rng.integers(0, 140), rng.integers(0, 100)
            arr[y:y + 20, x:x + 20] = rng.integers(0, 255, 3)
        p = tmp_path / f"g{k}.jpg"
        Image.fromarray(arr.clip(0, 255).astype("uint8")).save(p)
        paths.append(str(p))
    infos = [prt.analyse(p) for p in paths]
    assert len(prt.select_photos(infos, max_n=10, min_keep=3)) == 4
