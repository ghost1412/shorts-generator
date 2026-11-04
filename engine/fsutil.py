"""Small file helpers."""
import os
import time


def replace_file(src, dst, tries=10, delay=0.5):
    """os.replace that waits out a momentary lock. On Windows, antivirus or the process that just wrote a video can hold the
    file for a second or two, and os.replace then fails with "[WinError 5] Access is denied". Retrying makes post-processing
    (audio clean-up, sound effects, cold open, B-roll, brand) reliable instead of skipping a clip at random.
    Raises the last error when the file stays locked."""
    for attempt in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(delay)
