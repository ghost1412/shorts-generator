"""A short sample video for people who want to try ShortsFlow before finding a video of their own.

The file is a two-minute excerpt of a public-domain NASA video (an astronaut on the space station talking with a
podcast host), stored as an asset of the `samples-v1` GitHub release so it is downloaded only when someone asks for it.
"""

SAMPLE_URL = "https://github.com/ghost1412/shortsflow/releases/download/samples-v1/shortsflow_sample_nasa.mp4"

SAMPLE_CREDIT = ("Sample: a 2-minute excerpt of *NASA Astronaut Don Pettit Talks with Neil deGrasse Tyson's \"Star Talk\"* "
                 "(April 3, 2025), NASA Johnson Space Center, public domain "
                 "([source](https://commons.wikimedia.org/wiki/File:NASA_Astronaut_Don_Pettit_Talks_with_Neil_deGrasse_Tyson%E2%80%99s_"
                 "%E2%80%9CStar_Talk%E2%80%9D_%E2%80%93_April_3,_2025_(iss072m260931539).webm)). "
                 "It downloads from GitHub (about 10 MB) when you press **Make my shorts**.")


def use_sample():
    """Values for the Start here form: (video link, upload, note shown under the button)."""
    return SAMPLE_URL, None, SAMPLE_CREDIT
