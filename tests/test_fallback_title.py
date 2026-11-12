from engine.social_gen import _fallback_clip_metadata, clean_spoken, fallback_title


def test_fillers_and_stutters_are_removed():
    assert clean_spoken("so um I, I think that, that is uh right.") == "so I think that is right."
    assert "Umbrella" in clean_spoken("Umbrella, uh, works.")          # a word that starts like a filler stays


def test_title_is_a_clean_whole_sentence_without_a_leading_and():
    t = fallback_title(None, "And if you slosh it too hard, it, it all comes out and makes a mess. Then we clean it.")
    assert t == "If you slosh it too hard, it all comes out and makes a mess."


def test_long_title_is_cut_at_a_word():
    t = fallback_title(None, "This is a standard motif from what happens when humans live in space for months on end and nobody notices.")
    assert len(t) <= 73 and t.endswith("...") and " " in t and not t[:-3].endswith(" ")


def test_hook_is_preferred_and_empty_input_has_a_default():
    assert fallback_title("Water from pee, explained by an astronaut.", "something else entirely here.") .startswith("Water from pee")
    assert fallback_title(None, "") == "Must-watch moment"


def test_fallback_description_is_clean_and_cut_at_a_word():
    meta = _fallback_clip_metadata("Well, uh, " + " ".join(f"word{i}" for i in range(80)), None)
    first = meta["description"].split("\n")[0]
    assert "uh" not in first.split() and len(first) <= 203 and first.endswith("...")


def test_title_skips_sentences_that_trail_off():
    t = fallback_title(None, "You can have maps and places that... In those songs from the 70-90s you can see the whole story unfold.")
    assert t.startswith("In those songs")
    assert fallback_title(None, "How much detailed data about... Ten public events happened online last year.").startswith("Ten public events")
    # when every sentence trails off the first one is still used (a title is always returned)
    assert fallback_title(None, "We looked at the results of the.") == "We looked at the results of the."
