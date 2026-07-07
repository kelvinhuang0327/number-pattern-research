---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/flows/prediction-request.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: 9a15fc944006372f660d80b511dc09bfb94b7ade9b5bcf7782e8d4af85696664
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Prediction Request

Intent: surface prediction or research output from backend and tooling to the UI or CLI.

Flow:
1. User opens the frontend on port 8081 or runs a CLI prediction command.
2. Frontend code in `src/` requests data from the backend on port 8002.
3. Backend routes delegate to service and engine layers in `lottery_api/`.
4. Backend reads local data assets, strategy outputs, and monitoring state.
5. Backend returns JSON responses for UI rendering, or CLI tools emit terminal/report output.

Primary actors:
- Browser UI
- `src/main.js` frontend app
- FastAPI routes and services
- Prediction / monitoring engine modules

Observed entry points:
- Browser entry: `index.html`
- Frontend code entry: `src/main.js`
- CLI entry: `python3 tools/quick_predict.py all`

Notes:
- This is a synthesized high-level flow from README architecture statements and directory layout.