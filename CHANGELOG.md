# Changelog

Release notes for the `shortsflow` package and the Windows installer. Newest first.

## Unreleased

### New
- **Click-to-cut words**: under "Edit this short" in the browser app, every word of the short is a tick box. Tick the words you do not want ("um", a false start), press "Cut the ticked words" and the short is re-rendered without them (picture and captions); untick to bring them back, "Undo last change" restores the earlier version. Also `python -m engine.rerender SESSION INDEX --cuts 7.0:8.0`.
- **Captions in another language**: `--caption_lang es` (or the "Languages" box in the browser app) translates the captions with your AI provider and keeps them timed to the speech. Spanish, French, German, Portuguese, Italian, Dutch, Polish, Turkish, Indonesian, Vietnamese, Hindi and Marathi (the bundled caption fonts cannot draw Japanese, Chinese, Korean, Arabic or Russian yet). Translation quality depends on the model; small local models are weaker in Hindi.
- **Highlights video** option in the browser app (one landscape video made of the best moments, any length).
- **"Pick the moments"** in the browser app: make shorts only about a topic you describe, and cut chosen words or phrases out.
- The browser app has a **spoken-language** box (default: detect it automatically).
- **`--layout auto`**: per clip, a two-person shot gets the cut-to-whoever-is-talking layout, anything else the tracked single crop. Used by default on the browser app's Start here tab.

- **Captions in Russian, Ukrainian, Bulgarian and Greek** (bundled Noto Sans, Cyrillic/Greek subset); verified in a real Remotion render. The highlights video uses the same font.
- The **number of shorts has no limit** any more (browser app, REST API, MCP); the highlights video length has no limit either (a number box).

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
