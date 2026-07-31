---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/modules/frontend-spa.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: 450617375dc9a09c867e7db5c19e1a1335d1c55f6cab10d28e8a94ee10eb0e35
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Frontend SPA

Scope: browser UI served as a vanilla JavaScript single-page app.

Primary paths:
- `index.html`
- `src/main.js`
- `src/core/`
- `src/ui/`
- `src/services/`
- `src/data/`
- `src/utils/`

Responsibilities:
- Render the research UI on port 8081.
- Organize section-based navigation through internal app/UI manager logic.
- Fetch backend data and prediction outputs from the FastAPI service.
- Display charts and operational dashboards.

Observed entry points:
- `index.html` is the browser entry.
- `src/main.js` is the frontend code entry.

Key integrations:
- FastAPI backend on `http://localhost:8002`
- Chart.js
- Lucide Icons

Notes:
- RE-ANALYSIS 2026-07-07: root `package.json` and `vite.config.*` were not found in the bootstrap worktree. Treat the frontend as `index.html` + `src/main.js` served by the static server unless a later task verifies otherwise.
- README contains older framework wording; use PROJECT_CONTEXT / RUNBOOK for current bootstrap facts.
- SYSTEM_MAP.md indicates section-based routing and internal state management.
