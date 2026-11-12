import shutil
import subprocess

import pytest

from engine.screen_region import MAX_SCALE, MIN_SCALE, active_region, crop_filter, zoom_window


def test_zoom_window_is_capped_centred_and_skipped_when_it_would_not_help():
    assert zoom_window((0.0, 0.0, 1.0, 1.0)) is None                       # everything changes: no zoom
    assert zoom_window((0.1, 0.1, 0.95, 0.95)) is None                     # 85% * 1.12 > MAX_SCALE: not worth a re-crop
    assert zoom_window((0.2, 0.2, 0.9, 0.9))[0] == 0.784                   # 70% * 1.12: a mild zoom
    scale, cx, cy = zoom_window((0.45, 0.45, 0.55, 0.55))                  # a lone cursor: never tighter than MIN_SCALE
    assert scale == MIN_SCALE and abs(cx - 0.5) < 0.01 and abs(cy - 0.5) < 0.01
    scale, cx, cy = zoom_window((0.0, 0.0, 0.5, 0.5))                      # a corner: the window stays inside the frame
    assert cx - scale / 2 >= 0 and cy - scale / 2 >= 0 and scale <= MAX_SCALE


def _write_video(path, moving_region, active_until=None, fps=10, seconds=40):
    """Grey frames; the given region keeps changing brightness (a page that keeps changing).
    `active_until` (seconds) stops the changes after that time."""
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), fps, (320, 180))
    x0, y0, x1, y1 = moving_region
    for n in range(fps * seconds):
        frame = np.full((180, 320, 3), 90, dtype=np.uint8)
        live = active_until is None or n / fps < active_until
        frame[y0:y1, x0:x1] = 20 + (n % 40) * 5 if live else 20      # a ramp: frames 6 apart always differ by 30 levels
        out.write(frame)
    out.release()


def test_active_region_finds_the_changing_part_of_a_video(tmp_path):
    path = str(tmp_path / "screen.avi")
    _write_video(path, (80, 40, 240, 140))            # the middle half of the frame changes
    window = active_region(path, 1.0, 38.0)
    assert window is not None
    scale, cx, cy = window
    assert 0.6 <= scale <= MAX_SCALE and abs(cx - 0.5) < 0.1 and abs(cy - 0.5) < 0.1


def test_a_small_changing_area_never_steers_a_zoom(tmp_path):
    path = str(tmp_path / "cursor.avi")
    _write_video(path, (10, 10, 40, 40))              # a cursor / webcam inset / sidebar-sized change
    assert active_region(path, 1.0, 38.0) is None
    path = str(tmp_path / "sidebar.avi")
    _write_video(path, (0, 0, 70, 180))               # a narrow sidebar, under a quarter of the frame
    assert active_region(path, 1.0, 38.0) is None


def test_a_picture_that_changes_in_only_a_few_places_in_time_is_not_zoomed(tmp_path):
    path = str(tmp_path / "brief.avi")
    _write_video(path, (80, 40, 240, 140), active_until=6.0)      # changes only during the first seconds of the span
    assert active_region(path, 1.0, 38.0) is None


def test_active_region_is_none_when_the_whole_frame_changes_or_nothing_does(tmp_path):
    path = str(tmp_path / "full.avi")
    _write_video(path, (0, 0, 320, 180))
    assert active_region(path, 1.0, 38.0) is None
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    still = str(tmp_path / "still.avi")
    out = cv2.VideoWriter(still, cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 180))
    for _ in range(400):
        out.write(np.full((180, 320, 3), 90, dtype=np.uint8))
    out.release()
    assert active_region(still, 1.0, 38.0) is None
    assert active_region(str(tmp_path / "missing.avi"), 1.0, 38.0) is None


def test_crop_filter_runs_in_ffmpeg_and_keeps_the_aspect(tmp_path):
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("no ffmpeg")
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    path = str(tmp_path / "in.avi")
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 180))
    for _ in range(10):
        out.write(np.full((180, 320, 3), 90, dtype=np.uint8))
    out.release()
    from engine.video_gen import generate_ffmpeg_fit_filter
    vf = generate_ffmpeg_fit_filter(360, 640, crop_filter((0.7, 0.8, 0.3)))
    res = subprocess.run([exe, "-y", "-loglevel", "error", "-i", path, "-filter_complex", vf, "-frames:v", "1", str(tmp_path / "o.png")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    cropped = subprocess.run([exe, "-y", "-loglevel", "error", "-i", path, "-vf", crop_filter((0.7, 0.8, 0.3)), "-frames:v", "1", str(tmp_path / "c.png")],
                             capture_output=True, text=True)
    assert cropped.returncode == 0, cropped.stderr
    img = cv2.imread(str(tmp_path / "c.png"))
    assert img.shape[1] == 224 and img.shape[0] == 126           # 0.7 of 320x180, even sizes, same 16:9 aspect
