"""Take the voice out of a video's sound and keep everything else (music, game audio, effects).

Used by dubbing so the original language is not heard under the new voice while the music stays. It needs the optional `demucs`
package (`pip install demucs`); the first run downloads a small model. Without it the callers fall back to a faint original.
"""
import os
import subprocess
import sys


def available():
    try:
        import importlib.util
        return importlib.util.find_spec("demucs") is not None
    except Exception:
        return False


def split_vocals(video, session_dir, ffmpeg=None, run=subprocess.run):
    """Path to a stereo WAV of the video's sound WITHOUT the voice, or None when it cannot be made (demucs missing, a failure).

    The result is cached in `<session_dir>/stems` and reused."""
    stems = os.path.join(session_dir, "stems")
    result = os.path.join(stems, "htdemucs", "voice_src", "no_vocals.wav")
    if os.path.isfile(result) and os.path.getsize(result) > 1000:
        return result
    if not available():
        print("[Warning] Keeping the music but removing the original voice needs the 'demucs' package: pip install demucs. "
              "Falling back to a faint original sound.")
        return None
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(stems, exist_ok=True)
    src = os.path.join(stems, "voice_src.wav")
    r = run([ffmpeg, "-y", "-loglevel", "error", "-i", os.path.abspath(video), "-vn", "-ac", "2", "-ar", "44100", src],
            capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(src):
        print("[Warning] Could not read the video's sound for voice removal; falling back to a faint original.")
        return None
    print("[Log] Separating the original voice from the music (a minute or two on the CPU)...")
    r = run([sys.executable, "-m", "demucs.separate", "--two-stems=vocals", "-n", "htdemucs", "-o", stems, src],
            capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(result):
        print("[Warning] Voice removal failed (" + ((r.stderr or "")[-200:].strip().replace("\n", " ") or "no details") +
              "); falling back to a faint original.")
        return None
    return result
