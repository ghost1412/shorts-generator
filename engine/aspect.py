"""Output frame shapes for clips: 9:16 (default), 1:1, 4:5 and 16:9.

The clip pipeline was written for 9:16. Its layouts already take a width and a height; this module gives them the size for the chosen
shape, the crop window of that shape, and moves the caption heights (written for a 1920 px tall frame) to the same place in the new frame.
"""
from math import gcd

SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}
NAMES = tuple(SIZES)
BASE_HEIGHT = 1920          # the frame height the caption heights and offsets in the pipeline are written for


def valid(ratio):
    return ratio in SIZES


def size(ratio):
    """(width, height) of the output frame; unknown shapes mean 9:16."""
    return SIZES.get(ratio or "9:16", SIZES["9:16"])


def fraction(w, h):
    """'9/16' for 1080x1920, '1/1' for 1080x1080, '4/5', '16/9': the crop shape as FFmpeg writes it."""
    g = gcd(int(w), int(h)) or 1
    return f"{int(w) // g}/{int(h) // g}"


def crop_exprs(w=1080, h=1920):
    """(crop width, crop height) FFmpeg expressions for the largest window of this shape inside the source frame."""
    f = fraction(w, h)
    num, den = f.split("/")
    return f"min(iw,ih*{num}/{den})", f"min(ih,iw*{den}/{num})"


def center_crop(w=1080, h=1920):
    """A centred crop of this shape (for 9:16 this is exactly the old CENTER_CROP_9X16)."""
    cw, ch = crop_exprs(w, h)
    return f"crop='{cw}':'{ch}':(iw-ow)/2:(ih-oh)/2"


def scale_y(y, ratio_or_height):
    """A vertical position written for a 1920 px tall frame, moved to the same relative place in the frame of this shape (or height)."""
    height = ratio_or_height if isinstance(ratio_or_height, (int, float)) else size(ratio_or_height)[1]
    if height == BASE_HEIGHT:
        return y
    return int(round(y * height / BASE_HEIGHT))
