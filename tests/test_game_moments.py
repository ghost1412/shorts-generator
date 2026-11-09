from engine import game_moments as gm


def win(start, speech=0.0, motion=0.0, peak=0.0, dyn=0.0, text=0.0, words="", length=30.0):
    """motion, peak, dyn and text are given as 0..1 shares of the real scale seen on game footage (see gm.FLOORS)."""
    return {"start": float(start), "end": float(start) + length, "speech": speech, "motion": motion * 19.0,
            "peak": peak * 8.0, "dyn": dyn * 2.0, "text": text * 79.0, "words": words}


def labelled(windows):
    gm.normalise(windows)
    return [gm.label(w) for w in windows]


def test_dialogue_fight_and_menu_are_labelled_apart():
    dialogue = win(0, speech=1.8, motion=0.3, peak=0.5, dyn=0.5, text=0.9)
    fight = win(30, speech=0.0, motion=1.0, peak=1.0, dyn=0.3)
    noisy_fight = win(60, speech=1.0, motion=0.95, peak=0.95, dyn=0.3, text=0.2)   # Whisper hears words in fight noise
    menu = win(90, speech=0.0, motion=0.05, peak=0.05, dyn=0.05)
    assert labelled([dialogue, fight, noisy_fight, menu]) == ["story", "action", "action", "quiet"]


def test_silent_action_can_be_chosen_which_the_speech_based_picker_never_sees():
    wins = [win(0, motion=0.05), win(30, motion=1.0, peak=1.0, dyn=0.4), win(60, motion=0.9, peak=0.9, dyn=0.4)]
    got = gm.choose(wins, 1, story_share=0.0)
    assert [w["start"] for w in got] == [30.0] and got[0]["kind"] == "action"


def test_mix_follows_story_share_and_gaps_are_filled_by_the_other_kind():
    story = [win(i * 40, speech=1.5, motion=0.3, peak=0.5, dyn=0.5, text=0.5 + i / 20) for i in range(4)]
    action = [win(400 + i * 40, motion=1.0, peak=1.0, dyn=0.3) for i in range(4)]
    got = gm.choose(story + action, 4, story_share=0.5, min_gap=0)
    assert sorted(w["kind"] for w in got) == ["action", "action", "story", "story"]
    only_story = gm.choose([dict(w) for w in story], 3, story_share=0.0, min_gap=0)   # no action exists: story fills in
    assert len(only_story) == 3 and all(w["kind"] == "story" for w in only_story)


def test_picks_never_overlap_and_respect_the_gap_and_the_intro_skip():
    wins = [win(t, motion=1.0, peak=1.0, dyn=0.3) for t in (0, 15, 30, 45, 60, 75)]
    got = gm.choose(wins, 6, story_share=0.0, min_gap=30, skip_before=10)
    starts = [w["start"] for w in got]
    assert 0.0 not in starts
    assert all(b - a >= 60 for a, b in zip(starts, starts[1:]))   # 30 s clips and a 30 s gap


def test_words_per_second_windows_and_highlight_shape():
    segs = [{"start": 0, "end": 10, "text": "one two three four five"}]
    assert gm.words_per_second(segs, 0, 10) == 0.5
    assert gm.words_per_second(segs, 5, 15) == 0.25      # only half of the segment falls in the window
    assert gm.windows_for(100, 30) == [(0.0, 30.0), (15.0, 45.0), (30.0, 60.0), (45.0, 75.0), (60.0, 90.0)]
    s = win(10, speech=1.5, words="You know who I am? Back before winter set in again")
    s.update(kind="story", story_score=0.8, action_score=0.4)
    h = gm.to_highlight(s)
    assert h["kind"] == "story" and h["hook_text"].startswith("You know who I am") and 40 <= h["viral_score"] <= 95
    a = win(50, motion=1.0, peak=1.0)
    a.update(kind="action", story_score=0.2, action_score=0.9)
    h = gm.to_highlight(a)
    assert h["tone"] == "action_peak" and h["hook_text"] == "Action moment"


def test_a_video_with_only_dialogue_is_not_scaled_up_into_action():
    talk = [win(i * 30, speech=1.5, motion=0.5, peak=0.8, dyn=0.8, text=0.6 + i / 40) for i in range(5)]
    assert set(labelled(talk)) == {"story"}


def test_cli_has_content_and_game_mix_options():
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "shortsflow", "_main.py"), encoding="utf-8").read()
    assert '"--content"' in src and '"--game_mix"' in src
