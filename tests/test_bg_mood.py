import random

from engine import bg_mood


def test_mood_follows_the_story_words():
    assert bg_mood.mood_of("My boss fired me at the office") == "work"
    assert bg_mood.mood_of("AITA for skipping my sister's wedding?") == "family"
    assert bg_mood.mood_of("My ex was cheating on me") == "love"


def test_no_clear_mood_returns_none():
    assert bg_mood.mood_of("A quick story about a purple elephant") is None
    assert bg_mood.pick("") is None
    assert bg_mood.pick(None) is None


def test_pick_returns_a_query_of_that_mood():
    q = bg_mood.pick("The teacher gave the whole classroom an exam", rng=random.Random(1))
    assert q in dict((n, qs) for n, _k, qs in bg_mood.MOODS)["school"]


def test_every_mood_has_queries_and_keywords():
    for name, keys, queries in bg_mood.MOODS:
        assert keys and queries, name
