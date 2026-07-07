---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-memory/MEMORY_SYSTEM.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: 1a27051a040f902050d6ffc7c65fcc11019ee02fe6f26bdff799f2a10084aa60
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# MEMORY_SYSTEM

Project: LotteryNew
Initialized: 2026-04-27
Mode: safe overlay

Purpose:
- Track stable architecture facts learned during AI-assisted work.
- Record reusable navigation hints for future tasks.
- Keep overlay knowledge separate from the source repository.

Current baseline:
- Frontend is a vanilla JS SPA rooted at `index.html` and `src/main.js`.
- Backend is a FastAPI service started from `lottery_api/app.py` on port 8002.
- Local startup is orchestrated by `start_all.sh`.
- Research and operational scripts are concentrated under `tools/`.
- Orchestrator policy and status are part of the runtime surface.

Update rules:
- Add confirmed architecture facts only.
- Prefer short entries over narrative.
- Record source evidence when possible.
- Do not log speculative conclusions from incomplete scans.