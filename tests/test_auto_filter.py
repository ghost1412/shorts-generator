from engine import script_gen


def test_keywords_match_whole_words_only(monkeypatch):
    monkeypatch.setattr(script_gen, "get_llm_response", lambda *a, **k: "")
    assert script_gen.auto_detect_video_filter(user_context="a samurai duel at dawn") == "kurosawa"
    assert script_gen.auto_detect_video_filter(user_context="a chase with a crash") == "vibrant_action"
    assert script_gen.auto_detect_video_filter(user_context="my reaction to the temple attempt") == "none"   # 'action', 'emp' inside other words


def test_no_context_gives_no_filter_and_does_not_ask_the_ai(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not ask")
    monkeypatch.setattr(script_gen, "get_llm_response", boom)
    assert script_gen.auto_detect_video_filter() == "none" and script_gen.auto_detect_video_filter(user_context="  ") == "none"


def test_the_ai_answer_is_used_when_no_keyword_matches(monkeypatch):
    monkeypatch.setattr(script_gen, "get_llm_response", lambda *a, **k: '{"filter": "moody_dark"}')
    assert script_gen.auto_detect_video_filter(user_context="walking through an old library") == "moody_dark"
    monkeypatch.setattr(script_gen, "get_llm_response", lambda *a, **k: "I would pick cyberpunk.")
    assert script_gen.auto_detect_video_filter(user_context="walking through an old library") == "cyberpunk"
    monkeypatch.setattr(script_gen, "get_llm_response", lambda *a, **k: '{"filter": "rainbow"}')
    assert script_gen.auto_detect_video_filter(user_context="walking through an old library") == "none"
    monkeypatch.setattr(script_gen, "get_llm_response", lambda *a, **k: None)
    assert script_gen.auto_detect_video_filter(user_context="walking through an old library") == "none"
