# P43 — Operator Demo Readiness Update

**Date:** 2026-05-13
**Agent:** P43 Backend Startup Repair & Live Operator Demo Unblock Agent
**Reports To:** CTO
**Supersedes:** P42 operator demo status (`LIVE_BROWSER_DEMO_BLOCKED`)

---

## 1. Demo Unblock Status

| Flag | P42 Status | P43 Status |
|---|---|---|
| `LIVE_BROWSER_DEMO_BLOCKED` | ✅ YES | ❌ NO — **UNBLOCKED** |
| `PRE_EXISTING_BACKEND_STARTUP_BLOCKER` | ✅ YES | ❌ NO — **RESOLVED** |
| `MOCKED_EVIDENCE_BASELINE_AVAILABLE` | ✅ YES | ✅ YES — still valid |
| `BACKEND_LIVE_STARTUP_PASS` | ❌ — | ✅ YES |
| `REPLAY_API_LIVE` | ❌ — | ✅ YES |

---

## 2. Live Operator Demo — Now Unblocked

### 2.1 What changed

**No source code was modified.** The fix is a startup environment variable:

```
PYTHONPATH=/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api
```

This resolves the `ModuleNotFoundError: No module named 'routes'` by adding the `lottery_api/` directory to Python's search path, while keeping the workspace root on path so `lottery_api.models.*` absolute imports also resolve.

### 2.2 Why this works

The backend's import convention is mixed:
- `app.py` and most routes use **bare imports** (`from routes import ...`, `from utils.scheduler import ...`) — designed for CWD = `lottery_api/`
- `routes/replay.py` uses **absolute imports** (`from lottery_api.models.replay_strategy_registry import ...`) — designed for CWD = workspace root

Setting `PYTHONPATH=lottery_api/` satisfies both simultaneously:
- Workspace root in sys.path → resolves `lottery_api.*`
- `lottery_api/` in PYTHONPATH → resolves `routes`, `utils`, `models`, `schemas`, `database`

---

## 3. P35 Mocked Baseline — Still Valid

| Item | Status |
|---|---|
| P35 screenshots (7 PNGs on main) | ✅ Still valid |
| `capture_summary.json` on main | ✅ Still valid |
| P35 report on main | ✅ Still valid |
| `rpCatalogLifecycleBadge` in `index.html:3031` | ✅ Still valid |
| `rpRenderCatalogDisplayMode` in `index.html:3044` | ✅ Still valid |

The P35 mocked baseline remains available as a secondary evidence source. The live backend demo now supplements (not replaces) it.

---

## 4. P25 Display-Only Catalog — Still Verified

| Lifecycle | JS behavior | Regression test |
|---|---|---|
| ONLINE | Production replay rows | `test_p25_display_only_catalog.py` PASS |
| REJECTED | Display-only + "無歷史回放資料" | PASS |
| RETIRED | Display-only + "無歷史回放資料" | PASS |
| OBSERVATION | Display-only + "無歷史回放資料" | PASS |
| OFFLINE | "目前無已登錄項目（coming soon）" | PASS |

All 35 display-only catalog tests pass. No regression from P43.

---

## 5. Backend + Frontend Simultaneous Operation — Confirmed

Both services run on separate ports without conflict:

| Service | Port | URL | Status |
|---|---|---|---|
| Backend API | 8889 | `http://127.0.0.1:8889` | HTTP 200 ✅ |
| Backend docs | 8889 | `http://127.0.0.1:8889/docs` | HTTP 200 ✅ |
| Backend health | 8889 | `http://127.0.0.1:8889/health` | HTTP 200 ✅ |
| Frontend | 8081 | `http://127.0.0.1:8081` | HTTP 200 ✅ |

Replay API endpoints (all HTTP 200): `/api/replay/strategies`, `/api/replay/strategy-lifecycle`, `/api/replay/history`, `/api/replay/summary`, `/api/replay/runs`, `/api/replay/freshness`

Live strategy-lifecycle response:
```json
{"total":16,"lifecycle_counts":{"ONLINE":6,"REJECTED":4,"OBSERVATION":1,"RETIRED":5}}
```

---

## 6. Exact Operator Demo Startup Commands

### Start backend:
```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean

PYTHONPATH=/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api \
  nohup /usr/bin/python3 -m uvicorn lottery_api.app:app \
  --host 127.0.0.1 --port 8889 > /tmp/lottery_backend.log 2>&1 &

sleep 3 && curl http://127.0.0.1:8889/health
```

### Start frontend:
```bash
nohup /usr/bin/python3 -m http.server 8081 > /tmp/lottery_frontend.log 2>&1 &
```

### Access:
- Frontend: http://127.0.0.1:8081
- Backend API docs: http://127.0.0.1:8889/docs
- Replay lifecycle: http://127.0.0.1:8889/api/replay/strategy-lifecycle

### Stop:
```bash
lsof -ti:8889 | xargs kill 2>/dev/null
lsof -ti:8081 | xargs kill 2>/dev/null
```

---

## 7. Operator Demo Scenarios (from P34 SOP)

All 7 P35 scenarios are now executable via live backend:

| # | Scenario | Lifecycle | Expected Result |
|---|---|---|---|
| 1 | ONLINE production replay | ONLINE | Rows shown: `biglotto_triple_strike` etc. |
| 2 | REJECTED display-only | REJECTED | Catalog + "無歷史回放資料" banner |
| 3 | RETIRED display-only | RETIRED | Catalog + "無歷史回放資料" banner |
| 4 | OBSERVATION display-only | OBSERVATION | Catalog + "無歷史回放資料" banner |
| 5 | OFFLINE coming soon | OFFLINE | "目前無已登錄項目（coming soon）" |
| 6 | Fixture mode ON | any | Yellow fixture banner in UI |
| 7 | Fixture mode OFF | any | Clean production view |

---

## 8. Explicit PR / Merge Status

**PR #74** — docs(replay/p41): display-only catalog readiness and roadmap decision
- State: OPEN / MERGEABLE / CLEAN
- **NOT merged — awaiting `YES merge PR #74.`**

**PR #75** — docs(replay/p42): operator demo readiness and next decision
- State: OPEN / MERGEABLE / CLEAN
- **NOT merged — awaiting `YES merge PR #75.`**

**PR #76** (P43 repair) — fix(relay/p43): repair backend startup import for operator demo
- State: OPEN (to be created in Task 10)
- **NOT merged — awaiting `YES merge PR #76.`**

---

## 9. What This Does NOT Change

- No product behavior changes
- No production DB writes
- No strategy mining or edge discovery
- No winning claim, edge claim, or betting recommendation
- No lifecycle taxonomy changes
- No branch protection changes
- No force merges

---

## 10. Next Decision Gates

| Gate | Required Command |
|---|---|
| Official operator demo acceptance | `YES start operator demo.` |
| Merge PR #74 | `YES merge PR #74.` |
| Merge PR #75 | `YES merge PR #75.` |
| Merge PR #76 (P43) | `YES merge PR #76.` |
| No-write backfill dry-run | `YES start no-write backfill dry-run.` |

---

*Readiness update generated by P43 Backend Startup Repair & Live Operator Demo Unblock Agent*
*main SHA: 4590786 | Date: 2026-05-13*
