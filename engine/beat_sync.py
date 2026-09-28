import os
import subprocess
import numpy as np

def detect_beats(audio_path, target_count=None, max_duration=None, min_interval=0.35, max_interval=2.0):
    """
    Detects beat/transient timestamps (in seconds) in an audio file.
    Uses numpy energy-peak analysis on PCM audio extracted via FFmpeg.
    If target_count is specified, returns beat timestamps suitable for dividing into photo cuts.
    """
    if not audio_path or not os.path.exists(audio_path):
        return []

    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    beats = []
    try:
        # Extract 16kHz mono raw PCM audio s16le using FFmpeg
        cmd = [
            ffmpeg_exe, "-y", "-i", audio_path,
            "-ac", "1", "-ar", "16000", "-f", "s16le", "-"
        ]
        proc = subprocess.run(cmd, capture_output=True, check=True)
        raw_audio = proc.stdout
        
        # Convert bytes to numpy array
        audio_data = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
        sr = 16000
        total_duration = len(audio_data) / sr

        if total_duration <= 0:
            return []

        if max_duration and max_duration > 0 and total_duration > max_duration:
            total_duration = max_duration
            audio_data = audio_data[:int(sr * max_duration)]

        # Calculate short-time energy over 50ms windows (800 samples)
        window_size = int(sr * 0.05)  # 50ms
        hop_size = int(sr * 0.02)     # 20ms step
        
        num_frames = (len(audio_data) - window_size) // hop_size
        if num_frames <= 0:
            return [0.0]

        energies = np.zeros(num_frames)
        for i in range(num_frames):
            start = i * hop_size
            frame = audio_data[start:start + window_size]
            energies[i] = np.mean(frame ** 2)

        # Smooth energy curve
        kernel_size = 5
        energies_smooth = np.convolve(energies, np.ones(kernel_size)/kernel_size, mode='same')

        # Detect energy spikes (onset detection)
        # Compute first-order difference (novelty curve)
        diff = np.diff(energies_smooth)
        diff = np.maximum(0, diff) # half-wave rectification

        # Dynamic threshold based on mean + std
        threshold = np.mean(diff) + 0.5 * np.std(diff)
        
        peak_indices = []
        min_hop_samples = int(min_interval / 0.02)
        
        last_peak = -min_hop_samples
        for idx, val in enumerate(diff):
            if val > threshold and (idx - last_peak) >= min_hop_samples:
                peak_indices.append(idx)
                last_peak = idx

        raw_beats = [round(idx * 0.02, 3) for idx in peak_indices]

        # Always start at 0.0
        if not raw_beats or raw_beats[0] > 0.1:
            raw_beats.insert(0, 0.0)

        # If target photo count is provided, fit beats to evenly spread across photo count
        if target_count and target_count > 1:
            if len(raw_beats) >= target_count:
                # Downsample beats to target count
                indices = np.linspace(0, len(raw_beats) - 1, target_count, dtype=int)
                beats = [raw_beats[i] for i in indices]
            else:
                # Interpolate additional intervals to reach target photo count
                beats = list(np.linspace(0.0, total_duration, target_count + 1)[:-1])
                beats = [round(float(b), 3) for b in beats]
        else:
            beats = raw_beats

    except Exception as e:
        print(f"[Warning] Beat detection failed: {e}. Falling back to even intervals.")
        beats = []

    return beats
