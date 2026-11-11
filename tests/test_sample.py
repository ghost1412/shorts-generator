from shortsflow import sample


def test_sample_fills_the_link_and_clears_the_upload():
    url, upload, note = sample.use_sample()
    assert url == sample.SAMPLE_URL and upload is None
    assert url.startswith("https://github.com/ghost1412/shorts-generator/releases/download/samples-v1/")
    assert "public domain" in note and "NASA" in note
