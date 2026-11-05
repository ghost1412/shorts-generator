"""Remotion worker count: sensible defaults, an override that cannot inject anything odd."""
from engine.remotion_renderer import auto_workers, concurrency_flag


def test_gpu_pc_default_scales_with_cpu_threads_and_ram():
    assert auto_workers(cpu_threads=16, ram_gb=32) == 8          # half the threads, capped at 8
    assert auto_workers(cpu_threads=32, ram_gb=64) == 8          # more cores do not help beyond that
    assert auto_workers(cpu_threads=8, ram_gb=32) == 4
    assert auto_workers(cpu_threads=4, ram_gb=16) == 2           # never fewer than 2
    assert auto_workers(cpu_threads=16, ram_gb=8) == 4           # RAM limit: one worker per 2 GB
    assert auto_workers(cpu_threads=16, ram_gb=2) == 2
    assert auto_workers(cpu_threads=16, ram_gb=None) == 8        # unknown RAM: only the CPU rule


def test_defaults_per_machine_kind():
    assert concurrency_flag(use_nvenc=True, is_ci=False, env={}, cpu_threads=16, ram_gb=32) == "--concurrency=8"
    assert concurrency_flag(use_nvenc=True, is_ci=False, env={}, cpu_threads=4, ram_gb=8) == "--concurrency=2"
    assert concurrency_flag(use_nvenc=False, is_ci=True, env={}) == "--concurrency=1"
    assert concurrency_flag(use_nvenc=False, is_ci=False, env={}) == "--concurrency=50%"


def test_the_environment_override_accepts_a_count_or_a_percentage():
    assert concurrency_flag(True, False, {"SHORTSFLOW_REMOTION_CONCURRENCY": "6"}) == "--concurrency=6"
    assert concurrency_flag(False, True, {"SHORTSFLOW_REMOTION_CONCURRENCY": " 75% "}) == "--concurrency=75%"


def test_a_bad_override_is_ignored_and_the_default_is_used():
    for bad in ("0", "0%", "abc", "4; rm -rf /", "-1", "1000", "", "4 5"):
        assert concurrency_flag(True, False, {"SHORTSFLOW_REMOTION_CONCURRENCY": bad}, cpu_threads=4, ram_gb=8) == "--concurrency=2", bad
