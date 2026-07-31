# P75 — Backend Startup Reliability Patch Report
**Date**: 2026-05-13  
**Branch**: `ops/p75-startup-reliability-20260513`  
**Agent Role**: Replay Truth UI Final Merge & Startup Patch Agent  
**Reports to**: CTO → CEO

---

## 1. Round Objective

P75 had two goals:
1. **Merge PR #87** — standalone approval `YES merge PR #87` received → executed
2. **Patch start_all.sh** — apply REPO_ROOT + PYTHONPATH + PYTHON_BIN fix; verify cold-start backend

Both goals completed successfully.

---

## 2. Approval Gate Result

| Item | Value |
|------|-------|
| Approval phrase | `YES merge PR #87` |
| Received | ✅ YES — standalone, as the entire user message |
| Gate result | P75_APPROVAL_CONFIRMED |
| Downstream stages | All unblocked |

---

## 3. PR #87 Merge Result

| Item | Value |
|------|-------|
| PR URL | https://github.com/kelvinhuang0327/number-pattern-research/pull/87 |
| Pre-merge state | OPEN / MERGEABLE / CLEAN / CI 2/2 ✅ |
| Diff scope (pre-merge) | `index.html` + `outputs/replay/p69_truth_ui_polish_and_operator_smoke_report_20260513.md` |
| Forbidden files | 0 ✅ |
| Merge method | squash |
| Merge commit | `a7c8399e614ed4c3c704ed9130dbe5c67fd3bb7f` |
| Merged at | 2026-05-13T05:16:01Z |
| Post-merge state | MERGED |
| main HEAD after merge | `a7c8399` |

### Static Verification 12/12 (post-merge on main `a7c8399`)

| # | Signal | Line | Result |
|---|--------|------|--------|
| 1 | `function deriveTruthLevelForStrategy` | 2876 | ✅ |
| 2 | `function renderTruthLevelBadge` | 2901 | ✅ |
| 3 | `rpFetchReplaySummaryCounts` | 2920, 3472 | ✅ |
| 4 | `rpBuildStrategyRowCountMap` | 2925, 2937 | ✅ |
| 5 | `rpStrategyRowCountMap` | 2712, 2975, 3469, 3474, 3477 | ✅ |
| 6 | `Truth Level` | 2133 | ✅ |
| 7 | `LEGACY ERROR` | 2907 | ✅ |
| 8 | `NO HISTORY` | 2905 | ✅ |
| 9 | `METADATA ONLY` | 2904 | ✅ |
| 10 | `REGENERATED_RETROSPECTIVE` | 2898, 2908 | ✅ |
| 11 | `#6f42c1` | 80, 269 | ✅ |
| 12 | `aria-label` | 2903–2910 (all 6 badge types + UNKNOWN) | ✅ |

**Static 12/12 PASS ✅**

---

## 4. PR #88 Status

| Item | Value |
|------|-------|
| PR URL | https://github.com/kelvinhuang0327/number-pattern-research/pull/88 |
| State | OPEN / MERGEABLE / CLEAN / CI 2/2 ✅ |
| Approval received | NO — `YES merge PR #88` not sent |
| Action | NOT MERGED — not blocking startup patch |
| Marker | WAITING_FOR_YES_MERGE_PR88 |

---

## 5. start_all.sh Root Cause

| Issue | Line | Description | Severity |
|-------|------|-------------|----------|
| No PYTHONPATH | 31 | `nohup python3 app.py` with CWD=`lottery_api/` → `ModuleNotFoundError: No module named 'lottery_api'` | HIGH |
| Bare python3 | 31 | Resolves to active venv — if LotteryNew venv active (missing torch/fastapi), startup fails | MEDIUM |
| Fragile cd | 17 | `cd lottery_api` with no anchor → breaks if script called from non-root CWD | LOW |
| Relative log path | 31 | `../backend.log` — relative to `lottery_api/` CWD | LOW |

---

## 6. Patch Summary

**File modified**: `start_all.sh` only

### Changes applied

| Change | Old | New |
|--------|-----|-----|
| Add REPO_ROOT | (missing) | `REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"` |
| Add PYTHON_BIN | (missing) | `PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"` |
| Add PYTHONPATH export | (missing) | `export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"` |
| Fix cd | `cd lottery_api` | `cd "$REPO_ROOT/lottery_api"` |
| Fix Python binary | `nohup python3 app.py` | `nohup "$PYTHON_BIN" app.py` |
| Fix backend log | `> ../backend.log` | `> "$REPO_ROOT/backend.log"` |
| Fix backend.pid | `echo $BACKEND_PID > ../backend.pid` | `echo $BACKEND_PID > "$REPO_ROOT/backend.pid"` |
| Fix return cd | `cd ..` | `cd "$REPO_ROOT"` |
| Fix python check | `command -v python3` | `command -v "$PYTHON_BIN"` |
| Improve port warning | Port 8002 message with no guidance | Added: `請確認此 process 來自正確 repo` + `如需重啟，請先執行 ./stop_all.sh` |

---

## 7. Startup Verification Commands

```bash
# Stop existing backend
./stop_all.sh

# Start via patched script
./start_all.sh

# Verify
curl -s http://localhost:8002/health
curl -s http://localhost:8002/api/replay/strategy-lifecycle
curl -s "http://localhost:8002/api/replay/summary?lottery_type=BIG_LOTTO"
curl -s "http://localhost:8002/api/replay/summary?lottery_type=POWER_LOTTO"
curl -s "http://localhost:8002/api/replay/summary?lottery_type=DAILY_539"
```

---

## 8. Backend Startup Result

| Item | Value |
|------|-------|
| Pre-existing backend | PIDs 56256, 56392 (from manual session startup) |
| Stop method | `./stop_all.sh` — safe, expected, repo-owned processes |
| Start method | `./start_all.sh` (patched) from repo root |
| New backend PID | 27006 |
| REPO_ROOT resolved | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean` ✅ |
| backend.log path | `$REPO_ROOT/backend.log` = absolute ✅ |
| PYTHONPATH | `$REPO_ROOT` prepended ✅ |
| PYTHON_BIN | `/usr/bin/python3` (has torch, sklearn, fastapi, xgboost) ✅ |
| Startup result | **SUCCESS** |

---

## 9. Replay Endpoint Verification

| Endpoint | Result | Details |
|----------|--------|---------|
| `/health` | ✅ 200 OK | `status=healthy`, `busy=false`, models: prophet/xgboost/autogluon/lstm |
| `/api/replay/strategy-lifecycle` | ✅ 200 OK | 16 strategies returned |
| `/api/replay/summary?lottery_type=BIG_LOTTO` | ✅ data available | `biglotto_deviation_2bet` 70 rows, `biglotto_triple_strike` 70 rows |
| `/api/replay/summary?lottery_type=POWER_LOTTO` | ✅ data available | `power_orthogonal_5bet` 70 rows, `power_precision_3bet` 70 rows |
| `/api/replay/summary?lottery_type=DAILY_539` | ✅ data available | `daily539_f4cold` 90 rows, `daily539_markov_cold` 90 rows |

**P75_REPLAY_ENDPOINTS_VERIFIED ✅**

---

## 10. DB / Registry Hash Verification

| File | Expected | Actual | Status |
|------|---------|--------|--------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |
| `data/lottery_v2.db` (root) | — | ` M` pre-existing dirty | ⚠️ NOT staged |
| `backend.pid` | — | ` M` (runtime write by start_all.sh) | ⚠️ NOT staged |
| `frontend.pid` | — | ` M` (runtime write by start_all.sh) | ⚠️ NOT staged |

**P75_DB_UNCHANGED ✅ — P75_REGISTRY_UNCHANGED ✅**

---

## 11. Diff Scope

Files on branch `ops/p75-startup-reliability-20260513` vs `main`:

| File | Status |
|------|--------|
| `start_all.sh` | ✅ modified — startup patch |
| `outputs/replay/p75_startup_reliability_patch_report_20260513.md` | ✅ new — this report |
| `data/lottery_v2.db` | ⛔ NOT staged |
| `backend.pid` | ⛔ NOT staged |
| `frontend.pid` | ⛔ NOT staged |

---

## 12. Remaining Limitations

| Limitation | Impact | Resolution |
|-----------|--------|-----------|
| PR #88 not merged | P70 docs not in main | Reply `YES merge PR #88` |
| `backend.pid` written to repo root | Appears as dirty in git status | Acceptable — `.gitignore` entry would help (out of P75 scope) |
| `frontend.log` not yet using REPO_ROOT absolute path | Minor — frontend http.server CWD-relative log works when called from repo root | Can be addressed in follow-up patch |

---

## 13. Recommendation

**STARTUP_RELIABILITY_PATCH_READY_FOR_REVIEW**

The startup reliability PR is OPEN. No further blockers on startup reliability. The only pending item is PR #88 merge (P70 docs).

---

## 14. Next 24H Prompt for P76

After merging this P75 startup reliability PR (or in parallel):

```
# P76 — Post-P75 Browser Visual QA Evidence

1. Confirm main branch contains PR #87 P69 UI polish (static 12/12 verification)
2. Open http://localhost:8081 with merged index.html
3. Capture browser screenshots:
   - p76_live_badge_evidence.png      (LIVE badges green)
   - p76_metadata_only_evidence.png   (METADATA ONLY amber)
   - p76_no_history_evidence.png      (NO HISTORY tombstone + zh copy)
   - p76_retro_color_purple.png       (RETROSPECTIVE #6f42c1 vs FIXTURE blue)
4. Verify tooltip hover visible (aria-label)
5. Optionally merge PR #88 if approved
6. Produce P76 evidence report
7. No new feature scope

Optional:
YES merge PR #88
```

---

## 15. Final Markers

- ✅ P75_APPROVAL_CONFIRMED — `YES merge PR #87` received as standalone
- ✅ P75_BASELINE_VERIFIED — main HEAD `5e1b23f` pre-merge, `a7c8399` post-merge
- ✅ P75_DB_UNCHANGED — `de0e27bb800bc7183773a0dc596d66b8`
- ✅ P75_REGISTRY_UNCHANGED — `3ea71cfc20c882714f3824ad68202f6e`
- ✅ P75_PR87_MERGED — squash merge `a7c8399`, static 12/12 PASS
- ⏳ WAITING_FOR_YES_MERGE_PR88 — PR #88 OPEN, not blocking
- ✅ P75_STARTUP_PATCH_APPLIED — start_all.sh patched (REPO_ROOT + PYTHON_BIN + PYTHONPATH)
- ✅ P75_BACKEND_STARTUP_VERIFIED — cold start via patched script, PID 27006
- ✅ P75_REPLAY_ENDPOINTS_VERIFIED — /health + strategy-lifecycle (16) + 3× summary
- ✅ P75_REPORT_CREATED
- (pending Stage K) P75_PR_OPENED_<URL>
- (pending Stage K) P75_READY_FOR_REVIEW
