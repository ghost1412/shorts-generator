from engine.video_gen import apply_influencer_subtitles


def test_influencer_subtitles_returns_word_overlays():
    transcript = {"segments": [
        {"start": 10.0, "end": 12.0, "text": "hello there world",
         "words": [{"word": " hello", "start": 10.0, "end": 10.5},
                   {"word": " there", "start": 10.6, "end": 11.0},
                   {"word": " world", "start": 11.1, "end": 11.8}]},
        {"start": 30.0, "end": 31.0, "text": "outside the clip"},
    ]}
    clips = apply_influencer_subtitles(None, transcript, 10.0, 20.0, size=(270, 480), y_pos=240)
    assert isinstance(clips, list) and len(clips) == 3
    assert [round(c.start, 2) for c in clips] == [0.0, 0.6, 1.1]


def test_falls_back_to_even_split_without_word_timestamps():
    transcript = {"segments": [{"start": 0.0, "end": 2.0, "text": "one two"}]}
    clips = apply_influencer_subtitles(None, transcript, 0.0, 5.0, size=(270, 480), y_pos=240)
    assert [round(c.start, 2) for c in clips] == [0.0, 1.0]
