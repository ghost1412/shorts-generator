# Changelog

Release notes for the `shortsflow` package and the Windows installer. Newest first.

## Unreleased

### New
- **Browser app controls for the 0.3.0 options**: an "Extras" section on the Start here tab (clean up the sound, big title at the start, emoji next to key words, satisfying video underneath with an optional footage file) and the same options under Clip (advanced). The title and emoji are only passed when animated captions are on, since Remotion draws them.
- **"Dub a video" tab**: pick a video or link, the language to dub into and the language spoken, optionally burn the translated subtitles in; shows plain-language progress and gives you the dubbed video and the translated `.srt`.

### Fixed
- The caption-language hint in the browser app no longer says Japanese, Chinese, Korean and Arabic are unsupported.
- `--layout split_filler` with animated (Remotion) captions: the captions sat on the filler half (default position 1150). They now sit just above the seam in the lower part of the clip half. An explicit `--subtitle_y_pos` is kept as you set it.
- Re-rendering a short (change style, trim, or cut words) dropped `--hook_overlay` and `--clean_audio`: the hook title disappeared and the loudness fell back from about -14 LUFS to about -20 LUFS. Both settings are now saved with the run and applied again.
- `python -m engine.rerender` reported a failed re-render when its output was piped on Windows (the progress lines contain emoji and the console encoding was cp1252). It now writes UTF-8.
### Improved
- **Dubbing captions in every script**: `--dub_captions` now burns an ASS file instead of a plain SRT, naming a font with the glyphs for each word, so Hindi, Arabic (joined and right-to-left), Cyrillic, Greek, Chinese, Japanese and Korean no longer show empty boxes (the SRT is still written). Long Chinese/Japanese lines are cut to fit the frame; the Hindi and Arabic fonts are scaled up a little because they look small next to Latin.
- **Dubbing voices**: `--dub_voice female|male|<edge-tts name>` (for example `es-ES-AlvaroNeural`) picks the voice for the target language; every supported language has a female (default) and a male choice. A misspelt voice fails before any work is done.
- **CJK caption font download is pinned**: the Noto Sans SC/JP/KR files come from one fixed google/fonts commit and are checked against a SHA256; a file that does not match (or a stale cached copy) is discarded and the captions fall back to the old behaviour with a warning, instead of using whatever the `main` branch held.

## 0.3.0 (2026-11-04)

### New
- **"Satisfying footage" layout**: `--layout split_filler` puts the clip on the top half and looping gameplay or satisfying footage underneath (also in the browser app's Framing choice and the REST API). `--filler_video FILE` picks the footage; otherwise a video from `assets/backgrounds/local/` is used, else a Pexels stock clip (needs `PEXELS_API_KEY`), else the normal crop.
- **Audio clean-up**: `--clean_audio` removes rumble and background noise, evens out the volume and normalises loudness to about -14 LUFS on every finished clip (video is not re-encoded). Filters this FFmpeg lacks are skipped; on any failure the clip is left untouched.
- **Click-to-cut words**: under "Edit this short" in the browser app, every word of the short is a tick box. Tick the words you do not want ("um", a false start), press "Cut the ticked words" and the short is re-rendered without them (picture and captions); untick to bring them back, "Undo last change" restores the earlier version. Also `python -m engine.rerender SESSION INDEX --cuts 7.0:8.0`.
- **Basic AI dubbing**: `--mode DUB --source_video talk.mp4 --target_lang es` transcribes the video, translates it sentence by sentence with your AI provider, speaks it with edge-tts (internet needed; Kokoro for English), fits each line to its time slot, lowers the original audio under the new voice and writes a translated `.srt` (`--dub_captions` burns it in). One voice for every speaker, no voice cloning or lip-sync; translation and voice quality depend on the model and voice.
- **Captions in another language**: `--caption_lang es` (or the "Languages" box in the browser app) translates the captions with your AI provider and keeps them timed to the speech. Spanish, French, German, Portuguese, Italian, Dutch, Polish, Turkish, Indonesian, Vietnamese, Hindi and Marathi (the bundled caption fonts cannot draw Japanese, Chinese, Korean, Arabic or Russian yet). Translation quality depends on the model; small local models are weaker in Hindi.
- **Captions in another language**: `--caption_lang es` (or the "Languages" box in the browser app) translates the captions with your AI provider and keeps them timed to the speech. Spanish, French, German, Portuguese, Italian, Dutch, Polish, Turkish, Indonesian, Vietnamese, Hindi and Marathi (see below for Russian, Greek, Arabic, Chinese, Japanese and Korean). Translation quality depends on the model; small local models are weaker in Hindi.
- **Highlights video** option in the browser app (one landscape video made of the best moments, any length).
- **"Pick the moments"** in the browser app: make shorts only about a topic you describe, and cut chosen words or phrases out.
- The browser app has a **spoken-language** box (default: detect it automatically).
- **`--layout auto`**: per clip, a two-person shot gets the cut-to-whoever-is-talking layout, anything else the tracked single crop. Used by default on the browser app's Start here tab.

- **Captions in Russian, Ukrainian, Bulgarian and Greek** (bundled Noto Sans, Cyrillic/Greek subset); verified in a real Remotion render. The highlights video uses the same font.
- **Captions in Chinese, Japanese, Korean and Arabic** (`--caption_lang zh|ja|ko|ar`, and for sources already spoken in them). Arabic uses a small bundled Noto Sans Arabic and is laid out right to left with joined letters. Chinese/Japanese/Korean fonts are 10-18 MB each, so they are downloaded once (`~/.cache/shortsflow/fonts`) and cut down per video to a ~100 KB font with just the characters used; offline they still show empty boxes. Both the animated (Remotion) captions and the highlights-video captions use them. Han-only text is treated as Chinese.
- The **number of shorts has no limit** any more (browser app, REST API, MCP); the highlights video length has no limit either (a number box).

- **Hook overlay**: `--hook_overlay` shows each clip's hook as a big title for the first ~3 seconds (pops in, fades out). Works with `--use_remotion` clipping.
- **Caption emoji work everywhere**: `--caption_emoji` now draws bundled Twemoji images (CC-BY 4.0) instead of relying on a system emoji font, so it also works on a clean Windows PC, in Docker and on CI.

### Fixed
- Highlights-video prompt now includes the segment-length rules; an API key with non-ASCII characters returns 401 instead of 500; network calls to social/ComfyUI services have timeouts.
- Security hardening: the legacy `server.py` worker supports `SHORTSFLOW_API_KEY` and listens on localhost by default; API webhook URLs must be http(s) and cannot point at private addresses (override: `SHORTSFLOW_ALLOW_PRIVATE_WEBHOOKS=1`); text values starting with `-` are rejected.
- Clipping no longer needs `supabase` to be importable; the dead Aspect ratio choice was removed from the Clip (advanced) tab (clips are always 9:16).
- Cropping on footage without faces (gameplay, scenery): the crop stays centred instead of being pulled to the edge by false face detections.
- The brand typed in the browser app is now applied even if "Save my brand" was not pressed.
- The local AI default is `qwen2.5:7b` (about 13x faster than the previous `qwen3:8b` for clip scoring).

## 0.2.0 (2026-11-03)

### New
- **Review screen** in the browser app: every short as a card with a preview player, a strong / good / okay / weak label with the reason, and a copy-ready title, description and hashtags. Remove shorts, download all as a `.zip`, reopen earlier runs.
- **Edit one short**: choose another caption style or change its start and end; only that short is re-rendered from the run's saved analysis (about a minute), and **Undo** restores the previous version.
- **Caption style picker** with a preview image for each style (Bold yellow, Pink glow box, Bouncy gold, Clean dark boxes). The chosen style is now actually used (it was always the first one).
- **Brand kit** panel: logo, @handle, end-card text, accent colour and logo position, saved in your workspace and added to every short while ticked.

### Fixed
- The review page no longer crashes when `ffmpeg` is available but `ffprobe` is not.
- Results written by the command line with relative paths can be opened in the app.

## 0.1.5 (2026-11-03)
- **NVIDIA GPUs:** the Windows installer now installs a GPU build of PyTorch that matches the driver (CUDA 13.0 / 12.6 / 12.4) and checks that CUDA works. Before, it announced the GPU build but ended with a CPU-only one. An older CPU-only install is repaired when you run the installer again.
- New workspaces no longer start with placeholder API keys (`your_..._here`) that were treated as real keys and made every AI step retry for minutes.
- A silent install (`/VERYSILENT`) no longer hangs waiting for a click when something fails.
- The installer script no longer depends on PowerShell's `Get-FileHash`.

## 0.1.4 (2026-11-03)
- The Windows installer downloads FFmpeg (with `ffprobe`, checksum-verified) so a clean PC works; pip installs expose their bundled `ffmpeg` by name when none is on the PATH.

## 0.1.3 (2026-11-03)
- Fixed "No videos were generated" on PCs without an NVIDIA graphics card: hardware encoding is now only used when a real test encode works.
- PCs without a GPU use the smaller `small` speech model by default; a "downloading the speech model" message appears on first use.
- Groq: a retired model no longer breaks the AI fallback. A working model is chosen automatically (this also fixed the daily channel).

## 0.1.2 (2026-11-03)
- **Windows one-click installer** (no admin rights, no Python or Node needed first) and `shortsflow webui`, the browser app, now included in the package.

## 0.1.1 (2026-11-03)
- `shortsflow clip VIDEO_OR_LINK`: one command, no API key needed.
- Plain-language messages for bad keys, no credits, rate limits and being offline; friendlier `shortsflow doctor`.

## 0.1.0 (2026-11-01)
- First release on PyPI: `pip install shortsflow`.
