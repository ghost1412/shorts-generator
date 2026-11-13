import os
import shutil
import subprocess
import sys

import pytest

from engine import video_gen


def test_cpu_retry_swaps_the_gpu_encoder_only():
    gpu = ["ffmpeg", "-y", "-ss", "5", "-i", "in.mp4", "-t", "30", "-vf", "scale=1080:1920", "-r", "30", "-c:v", "h264_nvenc", "-preset", "p6",
           "-rc", "vbr", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "out.part.mp4"]
    cpu = video_gen.cpu_retry_command(gpu)
    assert cpu[cpu.index("-c:v") + 1] == "libx264" and cpu[cpu.index("-preset") + 1] == "veryfast"
    assert "-rc" not in cpu and "-cq" not in cpu and "-b:v" not in cpu and cpu[cpu.index("-crf") + 1] == "18"
    assert cpu[-1] == "out.part.mp4" and cpu[cpu.index("-vf") + 1] == "scale=1080:1920"          # everything else is unchanged
    assert cpu.index("-crf") == cpu.index("libx264") + 1
    assert video_gen.cpu_retry_command(["ffmpeg", "-c:v", "libx264", "-crf", "18", "o.mp4"]) is None         # already the CPU: nothing to retry
    assert video_gen.cpu_retry_command(["ffmpeg", "-i", "x"]) is None


class FailedProc:
    returncode = 1

    def wait(self):
        return 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_a_failed_gpu_cut_is_retried_on_the_cpu_and_reported(tmp_path, capsys):
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=3:r=30", "-pix_fmt", "yuv420p", src], check=True)
    part, final = str(tmp_path / "seg_0.part.mp4"), str(tmp_path / "seg_0.mp4")
    cmd = ["ffmpeg", "-y", "-i", src, "-t", "2", "-c:v", "h264_nvenc", "-preset", "p6", "-rc", "vbr", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p", part]
    video_gen.finish_segment_processes([(FailedProc(), part, final, cmd)])
    out = capsys.readouterr().out
    assert os.path.exists(final) and os.path.getsize(final) > 1000 and "trying again on the CPU" in out
    assert not os.path.exists(part)


def test_a_failure_with_no_retry_is_reported_not_silent(tmp_path, capsys):
    final = str(tmp_path / "seg_1.mp4")
    video_gen.finish_segment_processes([(FailedProc(), str(tmp_path / "seg_1.part.mp4"), final)])
    assert "[Error] Segment seg_1.mp4" in capsys.readouterr().out and not os.path.exists(final)
