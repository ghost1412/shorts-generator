# ShortsFlow Roadmap & Agent Hand-off

Living task board for Claude Code, Cursor, Copilot and other agents (and humans) working on this repo,
alone or in parallel. Read [AGENTS.md](AGENTS.md) first for architecture and commands.

**Goals**
1. Grow GitHub stars: make the project easy to try and clearly better than paid clippers.
2. Keep the production channel ([@spottheliee](https://www.youtube.com/@spottheliee)) healthy. It is
   fed by `.github/workflows/daily_generate.yml` every 4 hours (6 videos/day) in `FACTS` ("spot the lie") mode.

_Last updated: 2026-10-29_

---

## How to work on this board

- **Claim a task** by putting your agent/branch name in its `Owner` cell in the same commit as your first change.
  Skip tasks that are already claimed.
- **One workstream = one branch** (`ws/<letter>-<slug>`, e.g. `ws/b-rest-api`). Keep to the files listed for your
  workstream; if you must touch a shared file (see below), keep the change small and mention it in the PR.
- **When done**: tick the box, add a one-line note with the commit/PR, and move anything you discovered into
  *Known issues* or a new task.
- **Never** push generated media, `.env`, `token*.json` or `client_secrets*.json`. `main` feeds a live channel:
  anything that changes the scheduled FACTS output must be render-checked first (see *Verifying changes*).

### Shared hot-spot files (coordinate before big edits)
| File | Why it's risky |
|---|---|
| `main.py` (~1.6k lines, module-level script) | Generate-path dispatch, background selection and the Remotion call live here; standalone pipelines are in `engine/modes/` |
| `engine/script_gen.py` | All LLM prompts and the provider fallback chain (Gemini → Ollama → HuggingFace) |
| `remotion-video/src/ShortFlow.tsx` | Single 1.6k-line composition used by every Remotion mode |
| `.github/workflows/daily_generate.yml` | Runs the live channel |

---

## Verifying changes

| What | Command |
|---|---|
| Tests | `python -m pytest` (offline, ~1 s) |
| Python syntax | `python -m py_compile main.py engine/*.py engine/modes/*.py webui.py mcp_server.py` |
| Remotion types | `cd remotion-video && npx tsc --noEmit -p .` (must be 0 errors - CI enforces it) |
| Full FACTS render **without an LLM key** | `python scripts/offline_facts_render.py` → `sessions/offline_test/*.mp4` (needs `PEXELS_API_KEY`, Node, FFmpeg) |
| Real FACTS render | `python main.py --mode FACTS --use_remotion --skip-upload` (needs an LLM key) |
| Inspect frames | `ffmpeg -ss 9 -i <video>.mp4 -frames:v 1 frame.jpg` |
| WebUI | `python webui.py` → http://localhost:7860 |

`main.py` exits **non-zero** when nothing is rendered, so a red Actions run means no video was posted.

---

## Recently done

- [x] Browser WebUI (`webui.py`), Colab notebook, Dockerfile + `.dockerignore`, `requirements-full.txt`, `SKILL.md` (af2988e)
- [x] GHCR image publishing workflow `docker-publish.yml` (603442d)
- [x] FACTS quality: strict 1-lie validator, shuffled lie position, fresh hooks, per-fact stock-footage queries,
      background cuts synced to "Number N", `FACT N / 3` badge, spoiler in description, ElevenLabs return bug,
      Pexels resolution pick, clip looping, caption outline (375f0de)
- [x] Scheduled runs default to `FACTS` (repo variable `SCHEDULED_MODE` overrides); CI passes Gemini/Groq/OpenAI/
      DeepSeek/Anthropic/OpenRouter keys; failed generations exit 1; FACTS limited to safe categories;
      unknown categories no longer map to random kids/intimacy sub-topics

---

## Parallel workstreams

Workstreams A–F touch mostly separate files and can run at the same time.

### A. Channel reliability & quality (owner of `daily_generate.yml`, FACTS path in `script_gen.py`)
| | Task | Owner | Notes |
|---|---|---|---|
| [ ] | A1. Topic memory: keep `data/facts_history.json` (committed by the workflow or cached) and pass the last ~50 hooks/facts into the FACTS prompt to avoid repeats | | Reused-content risk on YouTube |
| [ ] | A2. Second-pass fact check: ask a second model call to verify both `truth: true` facts; regenerate if either fails | | Credibility of a facts channel |
| [ ] | A3. Pin the answer as the first comment after upload (YouTube `commentThreads.insert`) instead of only in the description | | `engine/social_gen.py` uploader |
| [ ] | A4. Analytics loop: pull views/retention per video weekly, weight categories/hook styles that perform | | `youtube_analytics.json` is stale (March) |
| [ ] | A5. Use the thumbnail badge generator for FACTS uploads | | |
| [ ] | A6. Badge timing: show `FACT 1 / 3` only from the first "Number 1", not during the hook | | `ShortFlow.tsx` `BackgroundSegment` + `main.py` `find_fact_start_times` |

### B. Automation API (new files: `api/` or `server.py` rewrite)
| | Task | Owner | Notes |
|---|---|---|---|
| [ ] | B1. FastAPI server with OpenAPI docs: `POST /v1/shorts`, `POST /v1/clips`, `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/files` | | Reuse the subprocess pattern from `webui.py` |
| [ ] | B2. Completion webhooks with optional HMAC signature | | |
| [ ] | B3. API keys via env, job queue with concurrency limit | | |
| [ ] | B4. `examples/n8n/` workflow JSON + README section | | Big star driver for openshorts / short-video-maker |
| [ ] | B5. Expose the API from the Docker image (second port) | | Touches `Dockerfile`, `docker-compose.yml` |

### C. Clipping UX (`webui.py`, `engine/analysis.py`)
| | Task | Owner | Notes |
|---|---|---|---|
| [ ] | C1. Show virality score + hook title per clip in the WebUI (scores already exist; use `--output_json`) | | Opus Clip's headline feature |
| [x] | C2. `--layout single/split/active`; active = speaker switching (issue #27) in `engine/speaker_focus.py` | Claude | Haar frontal+profile faces, mouth motion x audio envelope, 2.5 s dwell, stacked fallback. Tested on silent stock footage only - needs a check on a real podcast with speech |
| [ ] | C4. Active speaker: try MediaPipe Face Mesh lip landmarks instead of Haar + frame difference (more accurate, needs Python <= 3.12) | | Analysis takes ~0.8x clip length at 1280 px |
| [ ] | C3. In-browser preview + re-render a single clip with a different caption style | | |

### D. Distribution (`README.md`, new `spaces/`, packaging)
| | Task | Owner | Notes |
|---|---|---|---|
| [ ] | D1. Hugging Face Space running `webui.py` (CPU, idea-to-video modes) | | |
| [ ] | D2. WebUI demo GIF at the top of the README | | |
| [ ] | D3. `pip install shortsflow`: move `main.py` + `engine/` into a package, resolve asset paths from the package, console script `shortsflow` | | Large; conflicts with anything touching `main.py` - schedule alone |
| [ ] | D4. Submit MCP server to awesome-mcp-servers / Smithery / Glama | | Human task |

### E. Voices & visuals (`engine/voice_gen.py`, `ShortFlow.tsx`)
| | Task | Owner | Notes |
|---|---|---|---|
| [ ] | E1. Kokoro (local, free) TTS provider with word timestamps | | |
| [ ] | E2. Fish Audio TTS provider | | |
| [x] | E3. 0 tsc errors: `Html5Video` with `loop` for split/avatar clips | Claude | |
| [ ] | E4. Bundle an OFL caption font (e.g. Anton) via `staticFile` so captions don't depend on system Impact | | |

### F. Code health (any)
| | Task | Owner | Notes |
|---|---|---|---|
| [x] | F1. Bounded dependency versions in `requirements*.txt` | Claude | Lower bound = known-good, cap below next major; yt-dlp uncapped |
| [x] | F2. Pre-flight in `daily_generate.yml`: engine imports + pytest | Claude | No test render yet (needs Remotion + Pexels in CI) |
| [~] | F3. `tests/` pytest suite (31 tests) + `tests.yml` on 3.11/3.12 + Remotion tsc | Claude | Next: tests for social_gen metadata, remotion_renderer props, clip scoring |
| [~] | F4. Split `main.py`: standalone pipelines moved to `engine/modes/`, shared helpers to `engine/pipeline.py` (2.4k -> 1.6k lines) | Claude | Remaining: the generate path (script -> voice -> backgrounds -> render -> metadata -> upload) is still one module-level script with per-mode if/elif chains |
| [ ] | F5. Merge `.env.example` / `env.example` (only `env.example` is tracked) | | |

---

## Known issues

- Remotion props are not schema-validated at render time; `null` is passed for optional fields and works today.
- `get_video_duration` in `main.py` returns 10.0 on ffprobe failure, which can mis-size backgrounds silently.

## Open decisions (ask the repo owner)

- Should scheduled runs ever use modes other than FACTS? (Set repo variable `SCHEDULED_MODE`.)
- Is the hosted SaaS in `web/` (Stripe, Supabase) still maintained, or should docs focus on self-hosting?
