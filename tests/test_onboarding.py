from shortsflow import onboarding as ob


def test_friendly_step_maps_pipeline_lines():
    assert "Listening" in ob.friendly_step("Transcribe:  42%|####")[1]
    assert "best moments" in ob.friendly_step("[Log] LLM Virality Scoring: rating top 2 candidate clips...")[1]
    assert "Cutting" in ob.friendly_step("[Log] Extracting 2 segments in parallel via FFmpeg...")[1]
    assert "Done" in ob.friendly_step("[Log] SUCCESS! Extracted videos to sessions/x")[1]
    assert ob.friendly_step("[Log] Local LLM (qwen2.5:7b) success!") is None   # not the end of the run
    assert ob.friendly_step("[Log] Saved interest points to cache") is None
    assert ob.friendly_step("") is None


def test_friendly_step_surfaces_key_problems():
    rank, msg = ob.friendly_step("[Warning] Groq says this account has no credits left. Add credits there")
    assert rank == -1 and msg.startswith("⚠") and "no credits" in msg


def test_progress_only_moves_forward_and_shows_warnings():
    p = ob.Progress()
    assert "Getting" in p.message
    assert "Listening" in p.feed("Transcribe:   0%")
    assert "best moments" in p.feed("[Log] Merging adjacent highlights")
    assert "best moments" in p.feed("Transcribe: 100%")           # never goes back
    assert "best moments" in p.feed("[Log] Attempting local LLM at http://localhost:11434")
    assert "Cutting" in p.feed("[Log] Extracting 2 segments in parallel")
    assert p.feed("[Warning] Groq rate limiting you").startswith("⚠")
    assert "Done" in p.feed("[Log] SUCCESS! Extracted videos to x")


def test_save_env_key_adds_replaces_and_validates(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("PEXELS_API_KEY=abc\nGROQ_API_KEY=old\n")
    assert ob.save_env_key(str(env), "GROQ_API_KEY", ' "gsk_new" ') is True
    text = env.read_text()
    assert "GROQ_API_KEY=gsk_new" in text and "old" not in text and "PEXELS_API_KEY=abc" in text
    assert text.count("GROQ_API_KEY") == 1
    assert ob.save_env_key(str(tmp_path / "new.env"), "GEMINI_API_KEY", "k") is True
    assert ob.save_env_key(str(env), "bad name", "x") is False
    assert ob.save_env_key(str(env), "GROQ_API_KEY", "has space") is False
    assert ob.save_env_key(str(env), "GROQ_API_KEY", "") is False


def test_checklist_text_for_desktop_dialogs():
    txt = ob.checklist_text([("FFmpeg", True, ""), ("Node.js", False, "install Node 18+")])
    assert "FFmpeg" in txt and "Node.js" in txt and "install Node 18+" in txt and "&nbsp;" not in txt


def test_checklist_markdown_shows_ticks_and_fixes():
    md = ob.checklist_markdown([("FFmpeg", True, ""), ("Node.js", False, "install Node 18+")])
    assert "✅ FFmpeg" in md and "⚠️ Node.js" in md and "install Node 18+" in md
