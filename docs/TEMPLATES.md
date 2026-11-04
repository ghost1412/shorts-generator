# Templates and looks

Ready-made ways to shape a video. Each is a choice, not a fixed layout: where it says "from the footage", the tool decides by looking at your videos.

## Trip recap looks (`--mode TRIP --recap_style ...`)

| Style | What you get | Best for |
| :-- | :-- | :-- |
| `auto` (default) | Looks at your videos: mostly widescreen goes cinematic (2.35:1), mostly vertical phone clips go hype (9:16). Prints the reason. | Anything |
| `cinematic` | Travel-film look: 2.35:1 frame, grade from the footage (warm for sand/rock/sunset, cool for water/ice/forest), 0.5 s fades, titles laid over the footage and revealed in stages, small spaced place labels, no black cards. | Camera/drone footage |
| `hype` | A hook line over fast glimpses of the most beautiful shots, then the trip title card and a card per day or stop. | Phone clips, shorts |
| `plain` | Day 1 first, no opening. | Plain diary |

`--recap_aspect 9:16|16:9|2.35:1` overrides the frame shape. `--music file` makes cinematic cuts land on whole beats. `--recap_hook "Woke up at 4 AM just for this view"` sets the opening line. `--trip_stops "A, B, C"` names the stops of a one-day tour.

How a cinematic title is decided: the tool reads a frame of the shot under it, puts the text in the calmest area (centre, left, lower or upper), uses light or dark text by brightness there, takes the accent colour from the shot, and rotates the layout (centred, left-aligned, stacked words) so the titles are not all alike.

## Auto-edit presets (`--auto_edit`, `--edit_strength subtle|medium|hyped`)

`podcast` (clean, pauses and ums cut, subtitle bar, gentle zooms), `hype` (karaoke captions with emoji, frequent zooms, cutaways, teaser, vibrant colour), `educational` (subtitle bar, cutaways, number pop-ups, no teaser), `vlog` (glow captions, warm grade, teaser). Your own flags always win. A summary of what was done is written to `edit_plan.json`.

## Photo reel types (`--mode PHOTO_REEL --reel_type ...`)

`memories`, `travel`, `product`, `then_now`, `countdown`, `tribute`: each sets order, timing, captions, title and look. Blurry and duplicate photos are skipped.

## Explainer beats (`python -m engine.explainer_template beats.json out_dir`)

Each beat has a sentence and one ready-made Manim visual: `title`, `counter`, `sigma`, `scale`, `bullets`. The narration is voiced first and each visual lasts as long as its sentence.

## Caption styles (`--caption_style`)

`HORMOZI`, `GLOW_BOX`, `BOUNCE`, `MINIMAL`, `KARAOKE`, `BAR` (Remotion, see `remotion-video/src/`).
