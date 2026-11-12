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
MIN_CHANGED_PIXELS = 30    # fewer changed pixels (of 160x90) than this in a frame pair is not a change
MIN_ACTIVE_PAIRS = 3       # the picture must change in at least this many of the sampled pairs
MIN_AREA = 0.25            # the changing box must cover this share of the frame (a cursor, sidebar or webcam inset must not steer a zoom)


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


def changed_box(mask):
    """Box (x0, y0, x1, y1 as 0..1 shares) holding the middle 94% of the changed pixels of a 0/1 mask (the 3rd to 97th percentile of
    their columns and rows, so a few stray pixels at the edge do not stretch it); None when almost nothing changed."""
    import numpy as np
    h, w = mask.shape
    if mask.sum() < MIN_CHANGED_PIXELS:
        return None
    cols, rows = mask.sum(axis=0).cumsum(), mask.sum(axis=1).cumsum()
    x0, x1 = np.searchsorted(cols, 0.03 * cols[-1]), np.searchsorted(cols, 0.97 * cols[-1]) + 1
    y0, y1 = np.searchsorted(rows, 0.03 * rows[-1]), np.searchsorted(rows, 0.97 * rows[-1]) + 1
    return x0 / w, y0 / h, min(1.0, x1 / w), min(1.0, y1 / h)


def active_region(video, start, end, samples=10, gap=0.6):
    """(scale, cx, cy) zoom window for the changing part of the picture in [start, end] of `video`, or None: too little change (fewer
    than MIN_ACTIVE_PAIRS of the frame pairs changed), a changing area under MIN_AREA of the frame (a cursor, a sidebar, a webcam
    inset), a box that covers most of the frame anyway, or frames that cannot be read."""
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
        acc, pairs, active = None, 0, 0
        for i in range(samples):
            t = start + (i + 0.5) * (end - start - gap) / samples
            frames = []
            for dt in (0.0, gap):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int((t + dt) * fps))
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90)))
            if len(frames) < 2:
                continue
            mask = (cv2.absdiff(frames[0], frames[1]) > DIFF).astype(np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))      # specks and compression noise are not content
            pairs += 1
            if mask.sum() >= MIN_CHANGED_PIXELS:
                active += 1
            acc = mask.astype(np.int32) if acc is None else acc + mask
        if acc is None or pairs < samples - 2 or active < MIN_ACTIVE_PAIRS:
            return None
        box = changed_box((acc > 0).astype(np.uint8))
        if box is None or (box[2] - box[0]) * (box[3] - box[1]) < MIN_AREA:
            return None
        return zoom_window(box)
    except Exception:
        return None
    finally:
        cap.release()


def crop_filter(window):
    """FFmpeg crop expression for a zoom window (scale, cx, cy): even sizes, same aspect as the input (crop keeps x/y inside the frame)."""
    scale, cx, cy = window
    return f"crop=2*round(iw*{scale}/2):2*round(ih*{scale}/2):iw*{cx}-ow/2:ih*{cy}-oh/2"
