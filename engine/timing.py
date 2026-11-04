"""Where did the time go? `mark("name")` prints the time since the previous mark and the total, e.g.

    [Time] outline + audio load: +41.2s (total 63.0s)

Cheap and always on (one print per pipeline phase), so a slow run can be diagnosed from its log alone."""
import time

_T0 = None
_LAST = None


def reset():
    global _T0, _LAST
    _T0 = _LAST = time.perf_counter()


def mark(name):
    global _T0, _LAST
    now = time.perf_counter()
    if _T0 is None:
        _T0 = _LAST = now
    print(f"[Time] {name}: +{now - _LAST:.1f}s (total {now - _T0:.1f}s)", flush=True)
    _LAST = now
