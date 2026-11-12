# Gold sets (best moments)

Moments per public test video, used by `python scripts/clip_benchmark.py <session> --gold docs/gold/<video>.json`
(or the `gold` input of the Clip Benchmark workflow) to add **recall** (share of these moments the picker also found)
and **precision** (share of the picked clips that match one).

**These are model-labelled:** Claude read each transcript (2026-11-12) and picked 7 to 11 standalone moments of 15 to 60 s. They are
not a person's picks, so they say whether ShortsFlow picks what a language model would pick, not what viewers prefer. Replace or extend
them with human picks (`scripts/gold_sheet.py sheet` writes a labelling sheet, `build` turns the moments into json).

Each json is keyed `video.webm`, the file name the workflow downloads, so one file scores one video per run. The `moments_*.txt` files
are the readable source (`m:ss-m:ss`, notes after `#`). Videos: space podcast, NASA interview, keynote, slides talk (see docs/BENCHMARKS.md).
