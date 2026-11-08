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


def test_emoji_script_and_overused_answers(monkeypatch, tmp_path):
    from engine import puzzle_variety as pv2, script_gen as g
    monkeypatch.setattr(pv2, "_path", lambda: str(tmp_path / "h.json"))
    monkeypatch.setattr(g, "get_sub_topic", lambda c: c)
    replies = iter(['{"emojis": "🦁 👑 🌅", "answer": "The Lion King", "hint": "Disney movie", "script": "x"}',
                    '{"emojis": "🧊 🚢 💔", "answer": "Moonlight Harbor", "hint": "Romance movie", "script": "x"}'])
    monkeypatch.setattr(g, "get_llm_response", lambda *a, **k: next(replies) if "Emoji puzzle" not in a[0] else '{"kind_ok": true, "emojis_fit": true}')
    out = g.generate_emoji_guess("movies")
    assert out["answer"] == "Moonlight Harbor"                       # the overused answer was rejected and asked again
    assert "3 seconds" not in out["script"] and "7 seconds" not in out["script"]       # the on-screen countdown is 5 s


def test_chat_story_validator_rejects_copied_example_and_short_chats():
    from engine.script_gen import validate_chat_story
    def chat(texts):
        return {"messages": [{"sender": "A" if i % 2 else "B", "text": t, "is_me": bool(i % 2)} for i, t in enumerate(texts)]}
    good = chat([f"line {i}" for i in range(8)])
    assert validate_chat_story(good)
    assert not validate_chat_story(chat([f"line {i}" for i in range(4)]))
    copied = chat(["hi"] * 7 + ["I'm standing by the blue car."])
    assert not validate_chat_story(copied)


def test_horror_cleaning_and_validation():
    from engine.script_gen import clean_spoken, validate_horror
    assert clean_spoken("It came. <Dramatic pause> Closer. [pause] Now.") == "It came. Closer. Now."
    body = " ".join(["word"] * 60)
    assert validate_horror({"narrator_script": body})
    assert not validate_horror({"narrator_script": "too short"})
    assert not validate_horror({"narrator_script": "In the dead of night " + body})


def test_reddit_validator_rejects_raw_json_fallback_and_parser_reads_single_quotes():
    from engine.script_gen import robust_json_parse, validate_reddit
    body = " ".join(["word"] * 45) + " AITA?"
    assert validate_reddit({"title": "AITA for x", "story": body})
    assert not validate_reddit({"title": "Viral Update", "story": body})
    assert not validate_reddit({"title": "AITA", "story": '{ "title": "x" ' + body})
    assert not validate_reddit({"title": "AITA", "story": "short story? yes"})
    assert not validate_reddit({"title": "AITA", "story": " ".join(["word"] * 60)})  # never asks for judgment
    bs = chr(92)  # a backslash-escaped apostrophe inside a single-quoted string
    got = robust_json_parse("{ 'title': 'AITA for this', 'story': 'It" + bs + "'s a story. Am I wrong?' }")
    assert got["title"] == "AITA for this" and got["story"].endswith("Am I wrong?")


def test_quote_validator_rejects_cliches_and_openers():
    from engine.script_gen import validate_quote
    assert validate_quote({"quote": "Time is a racehorse, and you are holding the reins loosely today."})
    assert not validate_quote({"quote": "In stillness lies the strength of the soul and the calm."})
    assert not validate_quote({"quote": "In every step of darkness there is a glimmer of light."})
    assert not validate_quote({"quote": "Weather every storm with a steady mind and open hands."})
    assert not validate_quote({"quote": "Too short."})


def test_manim_answer_takes_code_from_a_fenced_block():
    from engine.script_gen import parse_manim_answer
    reply = '''{"title": "Why the sky is blue", "voiceover_text": "Sunlight scatters."}

```python
from manim import *

class ExplainerScene(Scene):
    def construct(self):
        self.add(Text("Hi"))
```
'''
    got = parse_manim_answer(reply)
    assert got["title"] == "Why the sky is blue" and got["voiceover_text"] == "Sunlight scatters."
    assert got["code"].startswith("from manim import *") and "class ExplainerScene" in got["code"]
    old = parse_manim_answer('{"title": "T", "code": "from manim import *", "voiceover_text": "v"}')
    assert old["title"] == "T" and old["code"].startswith("from manim")
