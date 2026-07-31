---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/modules/backend-api.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: f8fa4e996429aac06298802aeb74dc23e67d8afb40b996a25ea1627799a4884c
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Backend API

Scope: Python FastAPI application serving API, prediction, and monitoring endpoints.

Primary paths:
- `lottery_api/app.py`
- `lottery_api/routes/`
- `lottery_api/services/`
- `lottery_api/engine/`
- `lottery_api/models/`
- `lottery_api/fetcher/`

Responsibilities:
- Serve REST API endpoints on port 8002.
- Expose health checks and prediction-related endpoints.
- Host monitoring and strategy evaluation logic.
- Coordinate data access and backend service operations.

Observed entry points:
- `lottery_api/app.py` via `python3 -m uvicorn app:app --host 127.0.0.1 --port 8002`
- `GET /health`
- `GET/POST /api/orchestrator/llm-control`

Key integrations:
- Uvicorn
- SQLite databases
- Pandas / NumPy
- Scikit-learn / XGBoost
- APScheduler or internal polling

Notes:
- Startup behavior confirmed from `start_all.sh`.
- RE-ANALYSIS 2026-07-07: `lottery_api/app.py` runs FastAPI via uvicorn on port 8002, and `start_all.sh` uses that path. `lottery_api/README.md` still mentions port 5000 and root README contains older Flask wording; treat those as production-doc mismatches until separately fixed.
- Startup loads scheduler data in `app.py`, so service start remains outside Bootstrap/Re-Analysis.
