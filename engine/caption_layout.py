"""Where the animated captions sit and how big they are (`--caption_position`, `--caption_size`)."""

DEFAULT_Y = 1150
# Top edge of the caption block in a 1080x1920 short. "default" keeps the normal height (and the layouts' own choice:
# the fit layout moves it below the picture, a split-filler layout off the filler half).
POSITIONS = {"top": 350, "middle": 860, "bottom": 1480}
SIZES = {"small": 0.8, "default": 1.0, "large": 1.3, "xlarge": 1.6}


def y_for(position, current=DEFAULT_Y):
    """Caption top edge for a named position; 'default' (or nothing) keeps `current`. An explicit --subtitle_y_pos that is
    not the default always wins over a named position."""
    if current not in (None, DEFAULT_Y):
        return current
    return POSITIONS.get(position or "default", current if current is not None else DEFAULT_Y)


def size_for(size):
    """Scale factor for a named size (a number is accepted too, kept between 0.6 and 1.8)."""
    if isinstance(size, (int, float)):
        return max(0.6, min(1.8, float(size)))
    return SIZES.get(size or "default", 1.0)
