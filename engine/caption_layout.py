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


FACE_SAFE_Y = 1400          # lower third, the same height the plain captions use (engine.video_gen.PLAIN_CAPTION_Y)
FACE_MIN_SIZE = 0.15        # face height as a share of the frame: smaller faces are a normal framing, not a close-up
FACE_MIN_FOUND = 0.5        # a face in at least half the sampled frames
FACE_MARGIN = 50            # move when the face's chin comes within this many pixels of the default caption top


def face_safe_y(current_y, track, frame_h=1920):
    """Caption top edge that keeps animated captions off a close-up speaker's mouth.

    `track` is engine.clip_picture.face_track output for the finished 9:16 clip: [(cx, cy, size) or None], shares of the frame.
    Only the default height moves (to FACE_SAFE_Y), and only when a large face is found in most samples and the median chin
    reaches the caption area. Anything else, including an explicit height or no faces, returns `current_y` unchanged."""
    if current_y != DEFAULT_Y or not track:
        return current_y
    faces = [f for f in track if f]
    if len(faces) < FACE_MIN_FOUND * len(track):
        return current_y
    faces = [f for f in faces if f[2] >= FACE_MIN_SIZE]
    if len(faces) < FACE_MIN_FOUND * len(track):          # mostly large faces, not one close frame among wide ones
        return current_y
    bottoms = sorted((cy + size / 2) * frame_h for _cx, cy, size in faces)
    chin = bottoms[len(bottoms) // 2]
    return FACE_SAFE_Y if chin > DEFAULT_Y - FACE_MARGIN else current_y
