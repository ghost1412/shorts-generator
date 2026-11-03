"""Remove the solid green screen from still avatar images (assets/avatars/*.png are generated on a green backdrop).

Non-destructive: the original art is left alone, a keyed copy is written for the render. Only green regions that connect to
the image border are removed, so green details on the character itself survive.
"""
import cv2
import numpy as np


def _green_mask(rgb):
    """Pixels whose hue is green / lime and which are saturated and bright enough to be a backdrop (OpenCV hue 0-179)."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (h >= 28) & (h <= 85) & (s >= 110) & (v >= 90)


def key_green_screen(src, dst, feather=1.2):
    """Write `src` with its green backdrop made transparent to `dst` (PNG). Returns True when a green screen was found and
    keyed, False (and writes nothing) when the corners are not green, so photos and transparent art are never touched."""
    from PIL import Image
    with Image.open(src) as im:
        im.load()
        rgb = np.asarray(im.convert("RGB"))
    h, w = rgb.shape[:2]
    mask = _green_mask(rgb)
    k = max(3, min(h, w) // 100)
    # the backdrop is above the desk/floor, so judge it by the top corners and the upper left/right edges
    probes = [mask[:k, :k], mask[:k, -k:], mask[h // 8:h // 3, :k], mask[h // 8:h // 3, -k:]]
    if sum(c.mean() > 0.9 for c in probes) < 4:
        return False
    # keep only the green that is connected to the border
    count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=4)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    bg = np.isin(labels, [b for b in border if b != 0])
    # backdrop seen through glass or between ears/headset is enclosed, not connected to the border: drop pockets that are
    # large enough to be backdrop (small green details such as indicator LEDs stay)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    ref_h, ref_s = np.median(hsv[bg][:, 0]), np.median(hsv[bg][:, 1])
    areas = np.bincount(labels.ravel(), minlength=count)
    big = []
    for i in range(1, count):
        if areas[i] < max(250, h * w // 1500) or bg[labels == i].any():
            continue
        m = labels == i
        if abs(np.median(hsv[m][:, 0]) - ref_h) <= 4 and abs(np.median(hsv[m][:, 1]) - ref_s) <= 45:
            big.append(i)   # the same colour as the backdrop, so it is the backdrop (a lime smile is yellower: it stays)
    bg |= np.isin(labels, big)
    alpha = np.where(bg, 0.0, 1.0).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
    # despill: on the semi-transparent edge, clamp green to the larger of red/blue so no lime halo remains
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    edge = (alpha > 0.02) & (alpha < 0.98)
    # also clean a thin band of fully opaque pixels next to the backdrop
    near = cv2.dilate(bg.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~bg
    fix = edge | near
    g = np.where(fix, np.minimum(g, np.maximum(r, b) + 8), g)
    out = np.dstack([r, g, b, (alpha * 255).round()]).clip(0, 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(dst, format="PNG")
    return True
