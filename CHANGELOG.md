# Changelog

Release notes for the `shortsflow` package and the Windows installer. Newest first.

## Unreleased

### New
- **Use the browser app from a phone on another network**: `shortsflow webui --share` creates a temporary public link (Gradio tunnel). Shared links and apps listening on the network now always ask for a login: a password is generated and printed at start, or choose your own with `--auth user:password`.
- **Cold open (`--cold_open`)**: each short can start with its strongest later sentence as a 1.5-6 s teaser, then play from the beginning. It is built from the finished clip, so the captions, B-roll and audio clean-up come along, and the .srt is shifted to match (teaser cue first). It skips clips under 14 s, clips that would pass a minute with the teaser, and `--tighten_mode speed`. Works with re-render and `--use_cache` (no double teaser); a checkbox in the browser app's Extras. Off by default.
- **Two more scoring signals**: speech-rate change (people speed up when excited, slow down before a reveal; from the transcript alone) and laughter / applause (loud, noise-like, ha-ha-paced sound; only with `--use_audio_detect`). Together they carry about 10% of the clip score. The laughter detector is a heuristic: loud explosions or gunfire in game footage can also trigger it. `--no_signals` turns both off.
- **Smarter clip choice with one LLM request**: the first pass now offers up to twice as many candidates, then a second pass rates ALL of them in a single request, with a short overview of the video and the sentence before and after each clip. It can add a sentence at the end so the payoff is included, or drop a throat-clearing first sentence, and the best clips win. One request replaces the old one-call-per-clip scoring, and if no LLM answers (or the reply is unusable) the older scoring runs as before. `--no_rerank` turns it off.
- **More varied shorts**: when picking clips, a moment that repeats the wording of one already chosen is skipped, and a clip on a new topic is preferred over a slightly better repeat from the same topic (topics are found from how the vocabulary of neighbouring sentences changes; no model needed). `--no_diversity` turns it off.
- **Cleaner clip boundaries**: short clips (and `--find` results) now start at the beginning of a sentence, skip a leading "So, um, okay.", finish the sentence they stop in and keep a 0.4 s tail, instead of starting or ending mid-sentence. `--no_snap` turns it off. An offline benchmark (`python scripts/benchmark_highlights.py`) measures it on seeded synthetic transcripts: starts on a sentence 10% -> 100%, ends 27% -> 100%, payoff included 40% -> 82%. Numbers come from synthetic picks, so they measure the boundary handling, not a model's taste.

## 0.4.0 (2026-11-04)

### New
- **Auto B-roll (`--broll`, rebuilt)**: when a concrete thing is said (money, car, ocean, coffee ...), a short stock clip (about 2 s) is laid over the upper part of the picture while the original audio keeps playing; captions stay visible and the bottom half of `split_filler` is never covered. At most one cutaway per 8 s, none in the first 2 s (3 s with `--hook_overlay`), each keyword once per clip. Footage comes from a download cache (`assets/broll`), then Pexels (needs `PEXELS_API_KEY`), then clips in `assets/backgrounds/local`; with none of those the clip is left as it was. Done as one FFmpeg overlay pass on the finished short (audio copied), so it works with every render path, re-renders keep it, and a "Stock cutaways" checkbox is in the browser app's Extras. Word choice uses a built-in noun list (English); `pick_cutaways(..., ask=...)` can take an LLM for extra words. The old MoviePy cutaway code (it only ran in `--tighten_mode speed`, on the wrong intervals, with a MoviePy 1 API) and the unused `download_broll_clips` library are removed. Not applied to the highlights video.
- **Three new caption styles** (`--caption_style KARAOKE|NEON|BAR`, also in the browser app's style picker with previews): KARAOKE sweeps the highlight colour across each word as it is spoken, NEON glows the active word, BAR puts the line in a clean subtitle bar. They show a short line (3-6 words) that stays put while the highlight moves, and work with Latin, Cyrillic, Arabic (right-to-left, sweep runs right to left), Chinese/Japanese/Korean (no letter-spacing) and `--caption_emoji`. AUTO and RANDOM still pick only from the original four styles.
- **`--caption_color '#FF3366'`**: accent colour of the active caption word for every style (HORMOZI, GLOW_BOX, BOUNCE, MINIMAL and the new ones); a re-render keeps it.
- **Clip many videos at once**: `shortsflow clip A.mp4 B.mp4`, `shortsflow clip FOLDER` (every video directly inside it) or a mix of files and links. Each video is its own run in its own `sessions/batch_*` folder (the browser app lists them under "Open an earlier run"), a failed video does not stop the others, and a summary table (result, shorts, folder) is printed at the end.
- **`shortsflow clip --watch FOLDER [--interval N]`**: keeps checking the folder and clips each new video once, after its size has stopped changing (so a file still being copied is not clipped half-way). The done list lives in `sessions/.watch_*.json`; Ctrl+C stops it.
- **`--zh_script simplified|traditional|auto`**: Chinese captions (and the AI-written titles) in the script you want; `auto` keeps what Whisper wrote (it often writes Traditional for Simplified speech). Needs `pip install "shortsflow[zh]"` (OpenCC); without it the run goes on and says so. Timing is untouched because words are converted one by one.
- **`--clip_report [md|csv|both]`**: writes `clip_report.md` and/or `clip_report.csv` into the session folder with each clip's title, time range, score label, file and thumbnail. Batch runs write the Markdown report by default.
- **YouTube chapters for the highlights video**: the description (and `metadata.json`, `--output_json` under `chapters`, and a `chapters.txt` in the session folder) now carries a `0:00 Title` list that YouTube turns into chapters: at least three chapters, each at least 10 seconds, timestamps placed on the real reel timeline (crossfades and the file's measured length included). Titles are written from what is said in each chapter; a title with a number or name the chapter never says is replaced by a keyword title, and keywords are used when no AI answers.
- **Alternative titles per clip** (`title_variants`): three ideas in different styles (curiosity, number, question) next to the main title, in the review screen under "Other title ideas", in the download zip's text file and in `--output_json`. Ideas with a number or capitalised name that the clip never says are dropped, so a local model cannot invent details. Existing fields are unchanged; older results files without variants still open.
- **Platform limits** (`engine/platform_limits.py`): TikTok / Instagram / YouTube Shorts caption, title, hashtag and tag-list limits in one place, with a helper that fits a clip's metadata to each platform. Text is cut at a word and hashtags are dropped whole, never cut in half. `engine.publish` now uses it instead of a blind character cut.
- **Browser app controls for the 0.3.0 options**: an "Extras" section on the Start here tab (clean up the sound, big title at the start, emoji next to key words, satisfying video underneath with an optional footage file) and the same options under Clip (advanced). The title and emoji are only passed when animated captions are on, since Remotion draws them.
- **`--auto_zoom` (punch-in zoom)**: a subtle zoom on the picture at numbers, strong words and loud moments (quick punch, about 8%) and a slow push across sentences that start after a pause (about 5%). Animated captions, the hook title and the brand never move, because only the picture layer zooms. Needs `--use_remotion`; skipped with `--layout split_filler` (clip and filler are one picture there, so zooming would move the seam). A checkbox in both Extras sections of the browser app; kept when you re-render a short. Moments come from `engine/auto_zoom.py`.
- **"Dub a video" tab**: pick a video or link, the language to dub into and the language spoken, optionally burn the translated subtitles in; shows plain-language progress and gives you the dubbed video and the translated `.srt`.

- **Dub tab: voice and voice engine**: choose female or male (`--dub_voice`) and the engine (automatic, Edge online, or Kokoro on this PC for English).
- **Click-to-cut words: type a phrase to tick it** (any script, no spaces needed for Chinese or Japanese), and the word list now scrolls inside a fixed-height box instead of making a very long panel.

### Improved
- The "UI screenshots" workflow now also shows the Extras sections, the Dub tab and the word tick boxes (with a typed phrase ticked), from a small generated transcript.
- Checked MINIMAL and BOUNCE captions with Arabic plus Chinese / Japanese in real renders: joined Arabic letters, CJK from the per-render subset font. The pinned Korean font hash was confirmed against a real download.

### Fixed
- **`--srt` wrote nothing** (it imported a function from the wrong module and the error was hidden); SRT segments are also cut per clip with the right offsets.
- **`--add_commentary` and `--show_banner` never applied** (a misplaced `import subprocess`).
- **`--mode STORY` crashed on every run**: `--setting` was read but never defined. Added.
- **`--batch_file` now carries all your options** (the old loop that dropped them and shadowed the tested one is gone); topic lines still work with a `--mode`.
- **A failed clip no longer shifts the others**: titles, thumbnails, SRTs and `results.json` stay with their own clip.
- **Tall and portrait sources work**: any shape is cropped to 9:16 (a 1080x2400 phone video used to fail with "No videos were generated", 4:5 video was stretched).
- **Smart crop follows a moving subject in seconds** instead of about ten (smoothing was applied twice).
- **Sound effects played at the wrong speed** (synthesized whoosh/rain were twice as long and an octave low).
- **`--quality` and `--bitrate` now reach the animated-caption (Remotion) output** (medium is still CRF 16).
- **`--caption_lang` no longer switches off `--remove_fillers`**; chapters are found for URL sources; brand-kit errors show up before the render, and `--use_cache` no longer stamps the logo or normalises the audio twice.
- **Re-render keeps** caption emoji, the colour grade, filler removal and ad-hoc `--logo/--handle/--end_card`.
- **Number handling in narration**: `3.14`, `3,000` and `10:30` are no longer split by the dramatic pauses.
- **Custom image backgrounds** become real videos; the emoji-guess loop and ambient audio no longer use MoviePy 1 calls that failed silently.
- **Photo reel without `--music`** no longer stops with "Voice audio path not found" (bundled track or silence).
- **Factual script modes (true crime, Bible, article, Top 5, ...) no longer publish a canned script** when no LLM answers: the run fails so a scheduled run is flagged. In AUTO, article/product/Bible/true-crime picks fall back to FACTS when there is no topic.
- **Desktop GUI** only sends values the command line accepts (vibes, extraction formats), sends the chosen LLM provider, and no longer offers the non-existent Rank-It mode.
- **MCP**: `extract_clips` without a source gives a clear error, errors always get a reply, and finished clips are reported with their real paths.
- **`--cookies_from_browser` no longer force-closes Edge/Chrome** unless `SHORTSFLOW_CLOSE_BROWSER=1`.
- `--enhance_audio` is now `--clean_audio` and `--enable_zoom` is `--auto_zoom`; `--llm_model` works; `--auto_ducking`, `--sfx_preset` and `--aspect_ratio` say they are not implemented instead of silently doing nothing; help texts for `--min_duration`, `--edit_transcript`, `--subtitle_y_pos` corrected.
- The caption-language hint in the browser app no longer says Japanese, Chinese, Korean and Arabic are unsupported.
- `--layout split_filler` with animated (Remotion) captions: the captions sat on the filler half (default position 1150). They now sit just above the seam in the lower part of the clip half. An explicit `--subtitle_y_pos` is kept as you set it.
- Re-rendering a short (change style, trim, or cut words) dropped `--hook_overlay` and `--clean_audio`: the hook title disappeared and the loudness fell back from about -14 LUFS to about -20 LUFS. Both settings are now saved with the run and applied again.
- `python -m engine.rerender` reported a failed re-render when its output was piped on Windows (the progress lines contain emoji and the console encoding was cp1252). It now writes UTF-8.
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
