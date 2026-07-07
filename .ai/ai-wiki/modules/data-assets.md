---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/modules/data-assets.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: ff4e0dbbe518afecc93b13948fdc9fbd2ad64e786f376399c4a5f3d288c2889a
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Data Assets

Scope: persisted research data, databases, caches, and model outputs.

Primary paths:
- `data/`
- `lottery_api/data/`
- `strategies/`
- `predictions/`
- `outputs/`
- `rejected/`

Responsibilities:
- Store historical draw data and local persistence.
- Hold strategy monitoring cache and generated outputs.
- Preserve accepted and rejected research artifacts.

Observed storage and formats:
- SQLite databases
- JSON files
- Logs and report artifacts

Key integrations:
- Backend API data access
- Research tooling write paths
- Frontend read/display via backend endpoints

Notes:
- README calls out `data/` as strategy monitoring cache and historical data storage.
- SYSTEM_MAP.md describes local JSON persistence with SQLite.