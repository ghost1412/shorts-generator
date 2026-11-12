<!-- DRAFT of a short README (about 120 lines). Not live: the current README.md stays until the owner approves the swap.
     Plan: move today's README.md to docs/FEATURES.md unchanged (nothing is lost), then use this file as README.md.
     Fill the DEMO VIDEO placeholder below with the 60-90 s video (podcast in -> captioned clips out, with sound). -->

# ⚡ ShortsFlow

> **Drop in a podcast or interview, get captioned vertical clips. No account, no API key, no upload.**
> Free and open source (MIT): no watermark, no credits, no subscription. Runs on your own PC.

<p align="center">
  <!-- DEMO VIDEO: replace with the YouTube link / thumbnail, e.g. [![Watch the 90 s demo](docs/demo_thumb.png)](https://youtu.be/XXXX) -->
  <img src="demos/demo_podcast_cuts.gif" width="260" alt="A podcast clip: the crop cuts to whoever is speaking, with word-by-word captions" />
  <br/><sub>A real run: the 9:16 crop cuts to whoever is talking, with word-timed captions.</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/shortsflow/"><img src="https://img.shields.io/pypi/v/shortsflow?style=flat&logo=pypi&logoColor=white&color=3775A9" alt="PyPI version" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="MIT License" /></a>
  <a href="https://github.com/ghost1412/shorts-generator/actions/workflows/tests.yml"><img src="https://github.com/ghost1412/shorts-generator/actions/workflows/tests.yml/badge.svg" alt="Tests" /></a>
</p>

## Try it in two minutes

| | |
|---|---|
| 🪟 **Windows, no setup** | [⬇ ShortsFlow-Setup.exe](https://github.com/ghost1412/shorts-generator/releases/latest/download/ShortsFlow-Setup.exe), open **ShortsFlow**, press **Try a 2-minute sample**, then **Start**. |
| 🍎🐧 **Mac or Linux** | `curl -fsSL https://raw.githubusercontent.com/ghost1412/shorts-generator/main/install.sh \| sh` (needs Python 3.10+ and FFmpeg; installs into `~/.shortsflow`). |
| 💻 **Any OS** | `pip install "shortsflow[clip]"`, then `shortsflow doctor`, then `shortsflow clip my_video.mp4` |
| ☁️ **Nothing to install** | [Open in Colab](https://colab.research.google.com/github/ghost1412/shorts-generator/blob/main/ShortsFlow_Colab.ipynb) (free GPU) |

No account or API key is needed to clip a video. A key (or a free local Ollama) only adds AI titles and descriptions.

## What you get from one long video

- **The moments.** Local Whisper reads the speech; clips start and end on sentences, skip a mic check or a mumbled opening, and never overlap. Every clip says why it was picked.
- **The framing.** Face-tracked 9:16 crops, a cut to whoever is speaking in a two-person talk, and the whole picture over a blurred copy for slides and screen recordings.
- **The captions.** Animated word-by-word captions (Hormozi, glow box, bounce), your logo and handle, and an editor to re-cut or restyle any clip.
- **Tighter pacing.** `--tighten` removes silences and pauses between words, never a spoken word, and keeps laughter and applause.

```bash
# the one command most people need
shortsflow clip interview.mp4 --captions

# a podcast: cut to whoever is talking, remove silences, animated captions
python main.py --source_video "https://www.youtube.com/watch?v=VIDEO_ID" --extract_mode shorts \
  --clip_count 3 --layout auto --smart_crop --tighten --use_remotion --caption_style HORMOZI
```

## How good is it? We measure it

Clip quality is checked on public-domain and Creative Commons videos with no AI key at all, with a benchmark that runs on GitHub's runners
(`python scripts/clip_benchmark.py <session> --picture`): clips that start and end on a sentence, no overlap, length near the asked one,
a standalone opening line, titles that say only what the clip says, a face found and centred. The workflow is `.github/workflows/clip_benchmark.yml`; a results table per release is planned (TODO before this goes live: publish the first one). We do not claim to beat Opus Clip on every video; a side-by-side on public footage is the next thing to publish.

## ShortsFlow vs Opus Clip, Klap and Vizard

| | ShortsFlow | Opus Clip, Klap, Vizard |
|---|---|---|
| Price | Free, MIT | Subscription or credits |
| Watermark | None | On the free tier |
| Where your video goes | Stays on your machine; Whisper runs locally (text goes to an AI provider only if you add a key) | Uploaded to their cloud |
| Account | Not needed | Required |
| Best at | Podcasts and interviews, privacy, full control | Polish, hosted convenience |

## Privacy: what leaves your PC

Everything runs locally by default. Only these leave it, and each is optional: AI text providers (Gemini, Groq, Hugging Face, Ollama is local) receive the
transcript text when you set a key; Gemini receives small frames for `--visual_context` when a key is set; OpenStreetMap place names for trip recaps
(`--recap_no_geocode` turns it off); Microsoft's Edge voice service or ElevenLabs receive the text to speak in the dub and idea-to-video modes;
Google Drive upload only when you ask. A pasted YouTube link is downloaded to your PC; use your own files where the video's terms require it.

## More than clips

Browser app, desktop studio, CLI, Docker, REST API, an MCP server for AI agents, dubbing, trip and event recaps, photo reels, step-by-step videos,
game moments, and 30+ idea-to-video formats. They are documented in **[docs/FEATURES.md](docs/FEATURES.md)** (the full feature reference).

## Help and contributing

- Something wrong? [Open an issue](https://github.com/ghost1412/shorts-generator/issues) with `shortsflow doctor` output.
- Roadmap and open tasks: [ROADMAP.md](ROADMAP.md). Tests: `python -m pytest` (offline).
- Sample footage in the demos is public domain or Creative Commons and credited where used.

## License

MIT. Remotion (animated captions) has its own licence for companies above its size threshold; see [remotion.dev/license](https://remotion.dev/license).
