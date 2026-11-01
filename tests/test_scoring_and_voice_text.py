from engine.analysis import score_segment
from engine.voice_gen import add_dramatic_pauses, clean_for_tts, group_subtitles, split_hook


# --- clip scoring ----------------------------------------------------------------------------
def test_shorts_score_rewards_hooks_and_intensity():
    boring = score_segment("The meeting is at three o'clock tomorrow in the office", "shorts", 0, 20, 30)
    hooky = score_segment("Wait, what? That is INSANE, no way!", "shorts", 0, 20, 30)
    assert hooky > boring
    assert score_segment("Why does this happen to everyone?", "shorts", 0, 20) > score_segment("It happens to everyone.", "shorts", 0, 20)


def test_shorts_score_penalises_clips_past_the_shorts_limit():
    text = "Wait what happened"
    assert score_segment(text, "shorts", 0, 20, 30) > score_segment(text, "shorts", 0, 75, 30)


def test_shorts_score_prefers_the_requested_duration():
    text = "Here is a normal sentence of some length"
    near = score_segment(text, "shorts", 0, 31, 30)
    far = score_segment(text, "shorts", 0, 12, 30)
    assert near > far


def test_long_mode_rewards_story_beats():
    flat = score_segment("We talked about lunch", "long", 0, 30)
    story = score_segment("But then he finally discovered the problem, and in the end it turns out he was wrong.", "long", 0, 30)
    assert story > flat


def test_score_never_crashes_without_times():
    assert isinstance(score_segment("hello", "shorts"), int)
    assert isinstance(score_segment("hello", "long"), int)


# --- text prepared for TTS -------------------------------------------------------------------
def test_clean_for_tts_strips_urls_emoji_and_domains():
    out = clean_for_tts("Check https://example.com/x out 😱 or visit shop.com now v1.0 100% real $5")
    assert "http" not in out and "😱" not in out and ".com" not in out and "v1.0" not in out
    assert "100%" in out and "$5" in out


def test_clean_for_tts_coerces_non_strings():
    assert clean_for_tts(1234) == "1234"


def test_split_hook_prefers_ellipsis_then_first_sentence():
    assert split_hook("Big hook ... the rest here") == ("Big hook", "the rest here")
    assert split_hook("First sentence. Second one.") == ("First sentence", "Second one.")
    assert split_hook("no punctuation") == ("no punctuation", "")


def test_dramatic_pauses_after_numbers_and_reveal():
    # Characterisation of what the live channel feeds edge-tts today (the stacked dots are existing behaviour)
    out = add_dramatic_pauses("1. Cats purr. The real answer is cats, really.")
    assert out.startswith("1...") and out.split("The real answer")[0].rstrip().endswith("...")
    assert "The real answer is cats" in out and "really" in out


def test_group_subtitles_breaks_on_punctuation_and_length():
    words = [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25, "duration": 0.25}
             for i, w in enumerate(["So", "this", "is", "it.", "Next", "one", "is", "longer", "than", "four", "words"])]
    grouped = group_subtitles(words)
    assert grouped[0]["word"].endswith("it.")
    assert group_subtitles([]) == []
