"""Where the action is in a screen recording or slide deck, so the "fit" layout can zoom in on it.

`active_region(video, start, end)` compares frames inside [start, end] and finds the box where pixels change (the page or slide
area; static browser chrome, sidebars and empty margins stay out). It returns a zoom window with the SAME aspect as the frame
(so the fitted picture keeps its size and the captions below it stay clear): (scale, cx, cy) as shares of the frame, or None
when zooming would not help or cannot be trusted. The zoom is capped (at most 1/MIN_SCALE, about 1.7x) and a window that would
still cover most of the frame is not used. Nothing here calls an LLM or the network.
"""

MIN_SCALE = 0.6        # the window is never smaller than this share of the frame (a lone moving cursor must not zoom in to it)
MAX_SCALE = 0.88       # a window larger than this share is not worth a re-crop
PAD = 1.12             # a little margin around the changing box
DIFF = 24              # gray-level change that counts as "this pixel changed"
MIN_COLUMN_SHARE = 0.004   # a row/column counts when this share of its pixels changed (ignores specks and a thin cursor trail)


def zoom_window(box, scale_pad=PAD):
    """(scale, cx, cy) for a changed-pixel box (x0, y0, x1, y1 as 0..1 shares), or None when the zoom would not pay off."""
    x0, y0, x1, y1 = box
    scale = max(x1 - x0, y1 - y0) * scale_pad
    scale = max(MIN_SCALE, scale)
    if scale > MAX_SCALE:
        return None
    cx = min(max((x0 + x1) / 2, scale / 2), 1 - scale / 2)
    cy = min(max((y0 + y1) / 2, scale / 2), 1 - scale / 2)
    return round(scale, 3), round(cx, 3), round(cy, 3)


def changed_box(masks_sum):
    """Box (x0, y0, x1, y1 as shares) of the rows/columns where enough pixels changed, from a 2-D count array; None when nothing did."""
    import numpy as np
    h, w = masks_sum.shape
    cols = np.where(masks_sum.sum(axis=0) > MIN_COLUMN_SHARE * h * max(1, masks_sum.max()))[0]
    rows = np.where(masks_sum.sum(axis=1) > MIN_COLUMN_SHARE * w * max(1, masks_sum.max()))[0]
    if len(cols) == 0 or len(rows) == 0:
        return None
    return cols[0] / w, rows[0] / h, (cols[-1] + 1) / w, (rows[-1] + 1) / h


def active_region(video, start, end, samples=10, gap=0.6):
    """(scale, cx, cy) zoom window for the changing part of the picture in [start, end] of `video`, or None (no clear region,
    too little change, or the frames cannot be read)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    cap = cv2.VideoCapture(video)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if fps <= 0 or end - start < 2 * gap:
            return None
        acc, pairs = None, 0
        for i in range(samples):
            t = start + (i + 0.5) * (end - start - gap) / samples
            frames = []
            for dt in (0.0, gap):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int((t + dt) * fps))
                ok, frame = cap.read()
                if not ok:
                    break
                small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90))
                frames.append(small)
            if len(frames) < 2:
                continue
            mask = (cv2.absdiff(frames[0], frames[1]) > DIFF).astype(np.uint8)
            acc = mask if acc is None else acc + mask
            pairs += 1
        if acc is None or pairs < samples - 2 or acc.max() == 0:
            return None
        box = changed_box(acc)
        return zoom_window(box) if box else None
    except Exception:
        return None
    finally:
        cap.release()


def crop_filter(window):
    """FFmpeg crop expression for a zoom window (scale, cx, cy): even sizes, same aspect as the input (crop keeps x/y inside the frame)."""
    scale, cx, cy = window
    return f"crop=2*round(iw*{scale}/2):2*round(ih*{scale}/2):iw*{cx}-ow/2:ih*{cy}-oh/2"
