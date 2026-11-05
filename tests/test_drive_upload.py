"""Google Drive upload helper (offline: a fake Drive service, no sign-in, no network)."""
from engine import drive_upload as du


def test_folder_id_from_links_and_ids():
    assert du.folder_id("https://drive.google.com/drive/folders/ABCdef123456_-xyz?usp=sharing") == "ABCdef123456_-xyz"
    assert du.folder_id("https://drive.google.com/drive/u/0/folders/ABCdef123456") == "ABCdef123456"
    assert du.folder_id("https://drive.google.com/open?id=ABCdef123456") == "ABCdef123456"
    assert du.folder_id("ABCdef123456") == "ABCdef123456"
    assert du.folder_id("") == "" and du.folder_id("https://example.com/") == "" and du.folder_id("short") == ""


def test_files_to_send_skips_missing_folders_and_repeats(tmp_path):
    a = tmp_path / "a.mp4"
    a.write_bytes(b"x")
    assert du.files_to_send([str(a), str(a), str(tmp_path), str(tmp_path / "nope.mp4")]) == [str(a)]


class FakeRequest:
    def __init__(self, name):
        self.name, self.calls = name, 0

    def next_chunk(self):
        self.calls += 1
        return (None, {"id": f"id-{self.name}", "webViewLink": f"https://drive/{self.name}"})


class FakeFiles:
    def __init__(self):
        self.created = []

    def create(self, body, media_body, fields, supportsAllDrives):
        self.created.append(body)
        return FakeRequest(body["name"])


class FakeService:
    def __init__(self):
        self.f = FakeFiles()

    def files(self):
        return self.f


def test_upload_puts_each_file_in_the_folder_and_reports_links(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_bytes(b"x" * 10)
    b.write_bytes(b"y" * 10)
    svc = FakeService()
    got = du.upload([str(a), str(b)], "https://drive.google.com/drive/folders/ABCdef123456", service=svc)
    assert [g["name"] for g in got] == ["a.mp4", "b.mp4"] and got[0]["link"] == "https://drive/a.mp4"
    assert svc.f.created == [{"name": "a.mp4", "parents": ["ABCdef123456"]}, {"name": "b.mp4", "parents": ["ABCdef123456"]}]


def test_upload_refuses_a_bad_folder_and_missing_files(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    assert du.upload([str(f)], "not a folder", service=FakeService()) == []
    assert du.upload([str(tmp_path / "none.mp4")], "ABCdef123456", service=FakeService()) == []


def test_credentials_without_a_client_file_says_what_to_do(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert du.credentials(str(tmp_path / "none.json"), str(tmp_path / "token.json")) is None
    assert "OAuth client file" in capsys.readouterr().out
