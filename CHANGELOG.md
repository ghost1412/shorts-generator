# Changelog

Release notes for the `shortsflow` package and the Windows installer. Newest first.

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
