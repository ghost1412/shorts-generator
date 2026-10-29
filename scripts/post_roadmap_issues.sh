#!/usr/bin/env bash
# Posts open ROADMAP.md tasks as GitHub issues plus a reply on #27.
# Requires the GitHub CLI: winget install GitHub.cli && gh auth login
# Run once: bash scripts/post_roadmap_issues.sh
set -e
R=ghost1412/shorts-generator

gh issue comment 27 -R $R --body "Shipped in fa2ff35 (shot-length fix in d34dc39) as \`--layout active\` (also in the WebUI and the MCP \`extract_clips\` tool), following the approach above - thanks again @dillonstreator:

- Mouth-motion energy per speaker, weighted by the audio loudness envelope and normalised per speaker
- Shots hold at least 2.5 s, and a new speaker must persist 0.6 s before a cut
- Low confidence falls back to a stacked split, zoomed onto both faces
- A static crop per shot, so there is no camera shake

Faces come from OpenCV frontal + profile detection, because guests usually face each other. A MediaPipe Face Mesh lip-landmark variant is tracked as a follow-up."

new() { gh issue create -R $R --title "$1" --label "$2" --body "$3"; }

new "feat(api): REST API with OpenAPI docs, job status and completion webhooks" "feature" \
"Replace the minimal Flask \`server.py\` with a FastAPI service:
- \`POST /v1/shorts\`, \`POST /v1/clips\`, \`GET /v1/jobs/{id}\`, \`GET /v1/jobs/{id}/files\`
- Completion webhooks with optional HMAC signature, API-key auth, concurrency-limited job queue
- Interactive docs at \`/docs\`; exposed from the Docker image
See ROADMAP.md workstream B."

new "docs(n8n): Example n8n workflow for automated Shorts generation" "documentation" \
"Add \`examples/n8n/\` with an importable workflow (schedule -> generate short via API -> upload) and a README section. Depends on the REST API issue."

new "feat(webui): Show virality score and hook title for each extracted clip" "enhancement" \
"Clip scores already exist in the clipping pipeline (\`--output_json\`). Surface them in \`webui.py\` next to each rendered clip, sorted by score, with the reason/hook text."

new "feat(cv): MediaPipe Face Mesh lip landmarks for active-speaker detection" "enhancement" \
"Follow-up to #27. \`engine/speaker_focus.py\` uses Haar frontal/profile faces + mouth-region frame difference. Lip landmarks (MediaPipe Face Mesh) should be more accurate and robust to head motion. Keep the Haar path as a fallback (MediaPipe wheels lag new Python versions)."

new "feat(facts): Topic memory to avoid repeating facts and hooks" "enhancement" \
"Keep a history of recent FACTS hooks/facts (e.g. \`data/facts_history.json\`, persisted by the scheduled workflow) and pass the last ~50 into the prompt so the channel never repeats itself. Reduces YouTube reused-content risk."

new "feat(facts): Second-pass verification of the two true facts" "AI/LLM" \
"After generating a spot-the-lie set, ask a second LLM call to verify that both \`truth: true\` facts are accurate and well documented; regenerate if either fails. Credibility matters for a facts channel."

new "feat(publishing): Pin the answer as the first comment after upload" "feature" \
"FACTS uploads put the answer in the description. Post it as a pinned comment instead/as well via the YouTube Data API \`commentThreads.insert\` - drives comment engagement."

new "feat(deploy): Hugging Face Space demo of the WebUI" "feature" \
"Publish \`webui.py\` as a Hugging Face Space (CPU) for idea-to-video modes so people can try ShortsFlow without installing anything."

new "feat(packaging): pip install shortsflow" "feature" \
"Move \`main.py\` + \`engine/\` into an installable package that resolves assets and \`remotion-video/\` relative to the package, with a \`shortsflow\` console script. Large refactor - coordinate via ROADMAP.md."

new "feat(tts): Kokoro local TTS provider with word timestamps" "enhancement" \
"Add Kokoro as a free, local, high-quality voice provider in \`engine/voice_gen.py\`, producing word-level timestamps for Remotion captions."

new "chore: Merge .env.example and env.example into one template" "good first issue" \
"Only \`env.example\` is tracked; README, AGENTS.md, setup scripts and Docker docs should all point at one template. Merge any keys missing from \`env.example\`, delete the other name everywhere, and check \`setup.sh\`/\`setup.bat\` still create \`.env\`."
