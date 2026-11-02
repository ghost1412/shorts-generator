from engine.pipeline import batch_item_command


def test_user_flags_carry_over_and_per_item_ones_are_replaced():
    argv = ["--batch_file", "urls.txt", "--use_remotion", "--layout", "active", "--find", "pricing",
            "--output_json=out.json", "--session_dir", "s", "--tighten"]
    cmd = batch_item_command(argv, "http://x/1", 2, python="py")
    assert cmd[:3] == ["py", "-m", "shortsflow"]
    for flag in ("--use_remotion", "--layout", "active", "--find", "pricing", "--tighten"):
        assert flag in cmd
    assert "urls.txt" not in cmd and "--batch_file" not in cmd and "s" not in cmd
    assert cmd[-4:] == ["--source_video", "http://x/1", "--output_json", "batch_out_2.json"]


def test_no_output_json_when_not_requested():
    cmd = batch_item_command(["--batch_file", "u.txt", "--cut", "you know"], "a.mp4", 1)
    assert "--output_json" not in cmd and cmd[-2:] == ["--source_video", "a.mp4"]
