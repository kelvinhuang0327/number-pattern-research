---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/flows/startup-and-health.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: e374b5aa235f2de046a0c8aa6e68c327b59ba19081b4ca922efc3cb18733b6ab
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Startup And Health

Intent: bring up frontend, backend, and orchestrator services for local operation.

Flow:
1. Run `./start_all.sh`.
2. Script checks whether backend is already bound to port 8002.
3. If not running, it changes into `lottery_api/`, installs `requirements.txt` if present, and starts Uvicorn with `app:app`.
4. Script starts a static frontend server on port 8081 from repo root.
5. Script reloads orchestrator launchd jobs from `runtime/agent_orchestrator/launchd`.
6. Script probes backend `/health` and frontend root URL.
7. Script runs `python3 tools/verify_prediction_api.py` unless `--skip-verify` is passed.

Primary actors:
- Operator
- Frontend server
- FastAPI backend
- Orchestrator launchd jobs

Observed outputs:
- `backend.log`
- `frontend.log`
- `backend.pid`
- `frontend.pid`

Notes:
- This is the clearest runtime entry flow captured in the lightweight scan.