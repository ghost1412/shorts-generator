from engine import audio_clean as ac

ALL = {"highpass", "afftdn", "arnndn", "acompressor", "loudnorm"}


def test_chain_order_full():
    chain = ac.build_filter_chain(ALL)
    names = [f.split("=")[0] for f in chain.split(",")]
    assert names == ["highpass", "afftdn", "acompressor", "loudnorm"]
    assert "I=-14.0" in chain


def test_missing_filters_are_dropped():
    assert ac.build_filter_chain({"loudnorm"}).startswith("loudnorm=")
    assert ac.build_filter_chain(set()) == ""


def test_loudnorm_skipped_with_empty_string_and_options_appended():
    assert "loudnorm" not in ac.build_filter_chain(ALL, loudnorm="")
    assert ac.build_filter_chain(ALL, loudnorm="measured_I=-30").endswith("measured_I=-30")


def test_arnndn_used_only_with_existing_model(tmp_path):
    model = tmp_path / "m.rnnn"
    model.write_text("x")
    assert "arnndn" in ac.build_filter_chain(ALL, rnn_model=str(model))
    assert "arnndn" not in ac.build_filter_chain(ALL, rnn_model=str(tmp_path / "none.rnnn"))


def test_parse_loudnorm_json():
    err = 'junk\n{\n "input_i" : "-30.5",\n "input_tp" : "-8.0",\n "input_lra" : "3.0",\n "input_thresh" : "-41.0",\n "target_offset" : "0.5"\n}\n'
    m = ac.parse_loudnorm_json(err)
    assert m["input_i"] == -30.5 and m["target_offset"] == 0.5
    assert ac.parse_loudnorm_json("no json") is None


def test_clean_audio_missing_file_is_noop(tmp_path):
    assert ac.clean_audio(str(tmp_path / "nope.mp4")) is False


def test_clean_audio_failure_keeps_original(tmp_path):
    f = tmp_path / "c.mp4"
    f.write_bytes(b"not a video" * 200)
    before = f.read_bytes()
    assert ac.clean_audio(str(f)) is False
    assert f.read_bytes() == before
