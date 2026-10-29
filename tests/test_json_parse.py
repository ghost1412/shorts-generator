from engine.script_gen import robust_json_parse


def test_plain_json():
    assert robust_json_parse('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json():
    assert robust_json_parse('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_json_with_surrounding_chatter():
    assert robust_json_parse('Sure! Here it is:\n{"title": "x"}\nHope that helps.')["title"] == "x"
