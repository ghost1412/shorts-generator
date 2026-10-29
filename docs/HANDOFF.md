# Session Hand-off - 2026-10-30

Where things stand after the 2026-10-29/30 working session, what the owner still has to do by hand,
and how the next person (human or agent) picks up. For the full task board see [ROADMAP.md](../ROADMAP.md);
for architecture and commands see [AGENTS.md](../AGENTS.md).

---

## 1. Owner to-do (needs GitHub login / local tools - not doable by an agent)

Do these **in order** before any launch post goes out.

| # | Task | How |
|---|---|---|
| 1 | Remove the `ai-video-generator-crack` repo topic (looks like malware bait) | Repo page → ⚙️ next to **About** → remove topic |
| 2 | Make the Docker image public | GitHub profile → **Packages** → `shorts-generator` → **Package settings** → **Change visibility** → Public |
| 3 | Smoke-test what new visitors try first | `docker run -p 7860:7860 -e GEMINI_API_KEY=... ghcr.io/ghost1412/shorts-generator` → open http://localhost:7860; click the README Colab badge and run all 3 cells |
| 4 | Post open ROADMAP tasks as issues + reply on #27 | `winget install GitHub.cli` → `gh auth login` → `bash scripts/post_roadmap_issues.sh` (11 issues; run once) |
| 5 | Add `GEMINI_API_KEY` as a repo secret if it isn't one | Settings → Secrets → Actions. Without it the channel's facts come from Llama-3.1-8B via Hugging Face |
| 6 | Upgrade local edge-tts | `pip install -U edge-tts` - 7.2.7 now gets HTTP 403 from Microsoft; CI already installs the latest |
| 7 | Launch | Drafts in [docs/LAUNCH.md](LAUNCH.md): Show HN, r/selfhosted, r/LocalLLaMA, awesome-mcp-servers / Smithery / Glama |

Optional: set repo variable `SCHEDULED_MODE` if the channel should ever post something other than `FACTS`.

---

## 2. What changed this session (all on `main`)

| Commit | Change |
|---|---|
| af2988e | Browser WebUI (`webui.py`), Colab notebook, Dockerfile + `.dockerignore`, `requirements-full.txt`, `SKILL.md`, README quick-start |
| 603442d | `docker-publish.yml` → `ghcr.io/ghost1412/shorts-generator` |
| 375f0de | FACTS quality: strict 1-lie validator, shuffled lie, fresh hooks, per-fact footage queries, background cuts on "Number N", `FACT N / 3` badge, answer in description; ElevenLabs never-returned crash; Pexels resolution; clip looping; caption outline |
| c4f5e51 | Schedule defaults to FACTS; CI passes all LLM keys; failures exit 1; safe FACTS categories; `ROADMAP.md`; `scripts/offline_facts_render.py` |
| fa2ff35 | `--layout single/split/active` - active-speaker switching (closes #27), `engine/speaker_focus.py` |
| d34dc39 | Bounded dependency versions, 29 pytest tests, `tests.yml`, pre-flight in the daily workflow, 0 `tsc` errors |
| 2e8b8bc / 5ece252 | README demo GIF + production channel link; removed never-passing `ci.yml` |
| 816bbf6 | Standalone pipelines → `engine/modes/`, helpers → `engine/pipeline.py`; non-Remotion clip crash fixed; edge-tts ≥7.3.1 |
| 11616f3 | Idea-to-video path → `engine/modes/generate.py` (`main.py` 2.4k → 270 lines); `e2e.yml` real render in CI |

CI status at hand-off: **Tests ✅, E2E Render ✅, Publish Docker Image ✅** on 11616f3.

---

## 3. Code map after the refactor

```
main.py                     args, quality presets, dispatch (270 lines)
engine/modes/generate.py    idea-to-video path the channel runs (FACTS and 30+ modes)
engine/modes/clip_extract   long video / YouTube -> clips (--layout single|split|active)
engine/modes/{music,explainer,photo_reel,video_filter}.py
engine/pipeline.py          report_status, export_srt, voice maps, POOL_SIZE
engine/speaker_focus.py     active-speaker shot planning + ffmpeg filter
engine/script_gen.py        all LLM prompts + provider fallback chain
engine/utils.py             find_fact_start_times, decrypt_secret
remotion-video/src/ShortFlow.tsx   every Remotion layout (1.6k lines)
webui.py / mcp_server.py / server.py   front doors
tests/                      31 offline tests;  scripts/offline_facts_render.py = no-LLM render
```

---

## 4. Next up (ranked)

1. **REST API + webhooks + n8n example** (ROADMAP B) - biggest pull for automation users.
2. **Virality score + hook in the WebUI** (C1) - scores already exist via `--output_json`.
3. **Validate `--layout active` on a real podcast with speech.** It was only tested on silent Pexels footage plus a synthetic voice; the shot planning is right, but whether it picks the true speaker is unverified.
4. **FACTS topic memory + second-pass fact check** (A1, A2) - the channel's credibility.
5. **Break `engine/modes/generate.py` up per mode** - still has per-mode `if/elif` chains and `'x' in locals()` checks.

---

## 5. Gotchas learned the hard way

- **No LLM on the dev machine**: `.env` has no `GEMINI_API_KEY`, Hugging Face returns 402, Ollama isn't running. Use `python scripts/offline_facts_render.py` to test rendering, or add a key.
- **Moving module-level code into a function**: an `import x` inside any branch makes `x` local to the whole function → `UnboundLocalError` on other branches. Scan for shadowed names before moving code (see commit 11616f3 message).
- **`OffthreadVideo` ignores `loop`** - use `<Loop>` with a known clip duration or `Html5Video` with `loop`.
- **edge-tts and yt-dlp must stay current** - Microsoft/YouTube break old releases; both are uncapped in `requirements.txt`.
- **Pexels clips usually have no audio track** - Whisper fails on them; mux a voice track for clipping tests.
- `main.py` and the pipelines exit **non-zero** when no video is produced, so a red scheduled run = nothing posted.
- Output files land in the project root (`interactive_short_*.mp4`) unless `--session_dir` is given; they're gitignored but pile up (~860 MB at last count) - safe to delete.
