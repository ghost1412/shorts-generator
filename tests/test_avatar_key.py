import numpy as np
from PIL import Image

from engine.avatar_key import key_green_screen


def _art(path, size=200):
    arr = np.zeros((size, size, 3), np.uint8)
    arr[:] = (70, 200, 20)                       # green screen
    arr[60:140, 60:140] = (200, 60, 40)          # the character
    arr[90:94, 95:99] = (70, 200, 20)            # a tiny green detail enclosed in the character (an LED)
    Image.fromarray(arr).save(path)


def test_green_backdrop_becomes_transparent_and_character_survives(tmp_path):
    src, dst = tmp_path / "a.png", tmp_path / "k.png"
    _art(src)
    assert key_green_screen(str(src), str(dst)) is True
    out = np.asarray(Image.open(dst))
    assert out[5, 5, 3] == 0 and out[195, 195, 3] == 0      # backdrop gone
    assert out[100, 70, 3] == 255 and tuple(out[100, 70, :3]) == (200, 60, 40)   # character untouched
    assert out[91, 96, 3] == 255                              # small enclosed green detail stays


def test_non_green_image_is_left_alone(tmp_path):
    src, dst = tmp_path / "p.png", tmp_path / "k.png"
    Image.fromarray(np.full((120, 120, 3), (90, 90, 160), np.uint8)).save(src)
    assert key_green_screen(str(src), str(dst)) is False
    assert not dst.exists()
