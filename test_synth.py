import numpy as np
from moviepy.audio.AudioClip import AudioClip
import os

def test_synth():
    print("Synthesizing whoosh...")
    os.makedirs("assets", exist_ok=True)
    
    def make_whoosh(t):
        t = np.atleast_1d(t)
        # White noise with a sharp central peak
        noise = np.random.normal(0, 0.5, len(t))
        envelope = np.exp(-((t - 0.5) ** 2) / 0.02)
        frame = noise * envelope
        return np.vstack([frame, frame]).T
        
    whoosh = AudioClip(make_whoosh, duration=1.0)
    whoosh.write_audiofile("assets/synth_whoosh.mp3", fps=44100, bitrate="192k")
    print("Done! File size:", os.path.getsize("assets/synth_whoosh.mp3"))

if __name__ == "__main__":
    test_synth()
