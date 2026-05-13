# P70 — PR #87 Merge Gate & Operator Evidence Report
**Date**: 2026-05-13  
**Branch**: `docs/p70-pr87-operator-evidence-20260513` (docs PR)  
**Agent Role**: Replay Truth UI Merge & Evidence Agent  
**Reports to**: CTO → CEO  

---

## 1. Round Objective

P70 executes the merge gate for PR #87 (P69 truth-level UI polish), runs post-merge verification, confirms main-branch backend reliability, and captures live operator evidence via API cross-validation.

**Merge Decision**: Awaiting explicit `YES merge PR #87` approval. No merge executed this round.

---

## 2. PR #87 State (Stage A)

| Item | Value |
|------|-------|
| PR URL | https://github.com/kelvinhuang0327/number-pattern-research/pull/87 |
| Title | `frontend(replay/p69): polish truth-level UI badges` |
| State | OPEN |
| Base → Head | `main` ← `frontend/p69-replay-truth-ui-polish-20260513` |
| mergeable | MERGEABLE |
| mergeStateStatus | CLEAN |
| reviewDecision | (none required — branch protection passes) |
| isDraft | false |
| CI Checks | 2/2 ✅ green, 1 skipped |
| Blocking? | No |

---

## 3. Approval Gate Result (Stage D)

**Required exact phrase**: `YES merge PR #87`  
**Status**: NOT received in this session.

**→ WAITING_FOR_YES_MERGE_PR87**  
No merge executed. All remaining stages run without merge.

---

## 4. Merge Result

**NOT MERGED** — pending explicit YES approval.

---

## 5. Main HEAD & Baseline (Stage A)

| Item | Value |
|------|-------|
| main HEAD | `5e1b23f` |
| Commit message | `docs(replay/p67): verify PR84 post-merge truth-level UI (#85)` |
| PR #84 (truth badges) | `0316a57` — merged ✅ |
| PR #85 (P67 report) | `5e1b23f` — merged ✅ |
| PR #86 (P68 docs) | OPEN (independent, CI green) |
| PR #87 (P69 polish) | OPEN, MERGEABLE, CI 2/2 ✅ |

---

## 6. Diff Scope Verification — PR #87 (Stage B)

Files in PR #87 diff:
| File | Allowed? |
|------|---------|
| `index.html` | ✅ YES |
| `outputs/replay/p69_truth_ui_polish_and_operator_smoke_report_20260513.md` | ✅ YES |

No forbidden files detected:
- No `.db`, `.sqlite`, `.db-wal`, `.db-shm` ✅
- No `lottery_api/models/replay_strategy_registry.py` ✅
- No adapters, fixture artifacts, branch protection config ✅

**P70_DIFF_SCOPE_VERIFIED ✅**

---

## 7. DB / Registry Hash Verification (Stage C)

| File | Expected | Actual | Status |
|------|---------|--------|--------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |
| `data/lottery_v2.db` (root-level) | — | ` M` (dirty) | ⚠️ pre-existing local dirty — NOT committed in any P6x round |

**P70_DB_UNCHANGED ✅ — P70_REGISTRY_UNCHANGED ✅**

---

## 8. Backend Startup Reliability (Stage F)

### Current State
| Item | Value |
|------|-------|
| PIDs on :8002 | 56256, 56392 |
| Runtime | `/usr/bin/python3` |
| PYTHONPATH | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean` |
| Source | main-branch `LotteryNew-clean/lottery_api/` (903-line `replay.py`) |
| Health | `status=healthy busy=False models=[prophet,xgboost,autogluon,lstm]` |
| /api/replay/strategy-lifecycle | HTTP 200, 16 strategies ✅ |
| /api/replay/summary BIG_LOTTO | biglotto_deviation_2bet: 70 rows, biglotto_triple_strike: 70 rows ✅ |
| /api/replay/summary POWER_LOTTO | power_orthogonal_5bet: 70 rows, power_precision_3bet: 70 rows ✅ |
| /api/replay/summary DAILY_539 | daily539_f4cold: 90 rows (errors=20), daily539_markov_cold: 90 rows (errors=20) ✅ |

### start_all.sh Audit Findings (Stage F — audit only)

| # | Issue | Severity | Fix Required |
|---|-------|----------|-------------|
| 1 | `nohup python3 app.py` — no `PYTHONPATH` set | HIGH | Will fail: `ModuleNotFoundError: No module named 'lottery_api'` |
| 2 | Uses bare `python3` (not `/usr/bin/python3`) | MEDIUM | Resolved by PATH or venv — but fragile |
| 3 | `pip3 install -r requirements.txt` may hit wrong venv | LOW | Depends on active venv at call time |

**Recommendation**: P71 startup reliability patch to `start_all.sh`:  
```bash
# Proposed P71 patch (NOT applied in P70):
cd lottery_api
PYTHONPATH=/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean \
  nohup /usr/bin/python3 app.py > ../backend.log 2>&1 &
```

**P70_BACKEND_SMOKE_PASS ✅** (manual startup verified; start_all.sh issue documented for P71)

---

## 9. Operator Evidence (Stage G)

### Browser Screenshot
**Browser Screenshot = NOT RUN** (no browser session active in this round)  
No screenshots generated. Evidence captured via API cross-validation + static code analysis.

### Truth Level Matrix — Live API Cross-Validation

All truth levels derived using `deriveTruthLevelForStrategy()` logic (line 2876) against live `/api/replay/strategy-lifecycle` + `/api/replay/summary`:

#### ONLINE → PRODUCTION_REPLAY → LIVE badge (green)

| Strategy | rows | Truth Level | Badge | Verified |
|---------|------|-------------|-------|---------|
| power_precision_3bet | 70 | PRODUCTION_REPLAY | **LIVE** | ✅ API |
| power_orthogonal_5bet | 70 | PRODUCTION_REPLAY | **LIVE** | ✅ API |
| biglotto_triple_strike | 70 | PRODUCTION_REPLAY | **LIVE** | ✅ API |
| biglotto_deviation_2bet | 70 | PRODUCTION_REPLAY | **LIVE** | ✅ API |
| daily539_f4cold | 90 | PRODUCTION_REPLAY | **LIVE** | ✅ API |
| daily539_markov_cold | 90 | PRODUCTION_REPLAY | **LIVE** | ✅ API |

#### REJECTED / OBSERVATION → DISPLAY_ONLY → METADATA ONLY badge (amber)

| Strategy | lifecycle_status | Truth Level | Badge | Verified |
|---------|-----------------|-------------|-------|---------|
| biglotto_ts3_acb_4bet | REJECTED | DISPLAY_ONLY | **METADATA ONLY** | ✅ API |
| biglotto_ts3_markov_freq_5bet | REJECTED | DISPLAY_ONLY | **METADATA ONLY** | ✅ API |
| power_shlc_midfreq | REJECTED | DISPLAY_ONLY | **METADATA ONLY** | ✅ API |
| p1_deviation_2bet_539 | REJECTED | DISPLAY_ONLY | **METADATA ONLY** | ✅ API |
| h6_gate_mk20_ew85 | OBSERVATION | DISPLAY_ONLY | **METADATA ONLY** | ✅ API |

#### RETIRED (rows=0) → MISSING_HISTORY → NO HISTORY badge + tombstone (dark gray)

| Strategy | lifecycle_status | rows | Truth Level | Badge | Verified |
|---------|-----------------|------|-------------|-------|---------|
| acb_1bet | RETIRED | 0 | MISSING_HISTORY | **NO HISTORY** | ✅ API |
| acb_markov_midfreq | RETIRED | 0 | MISSING_HISTORY | **NO HISTORY** | ✅ API |
| acb_markov_midfreq_3bet | RETIRED | 0 | MISSING_HISTORY | **NO HISTORY** | ✅ API |
| midfreq_acb_2bet | RETIRED | 0 | MISSING_HISTORY | **NO HISTORY** | ✅ API |
| midfreq_fourier_2bet | RETIRED | 0 | MISSING_HISTORY | **NO HISTORY** | ✅ API |

#### REPLAY_ERROR Visibility
- `daily539_f4cold` error_count=20 → filter `REPLAY_ERROR` surfaceable ✅
- `daily539_markov_cold` error_count=20 → filter `REPLAY_ERROR` surfaceable ✅
- Total REPLAY_ERROR rows in DAILY_539: 40

#### Color Distinction
- FIXTURE: `.rp-truth-fixture { background:#1f6feb }` — blue (line 268) ✅
- RETROSPECTIVE: `.rp-truth-retro { background:#6f42c1 }` — purple (line 269) ✅
- No collision ✅

**P70_OPERATOR_EVIDENCE_PARTIAL ✅** (API cross-validation complete; browser DOM screenshots not captured)

---

## 10. Static Verification (Stage H)

Verified against P69 branch `index.html` (commit `49c3f7a`):

| # | Check | Line | Result |
|---|-------|------|--------|
| 1 | `function deriveTruthLevelForStrategy` | 2876 | ✅ |
| 2 | `function renderTruthLevelBadge` | 2901 | ✅ |
| 3 | `rpFetchReplaySummaryCounts` present (×2) | 2920, 3472 | ✅ |
| 4 | `rpBuildStrategyRowCountMap` present (×2) | 2925, 2937 | ✅ |
| 5 | `Truth Level` column header | 2133 | ✅ |
| 6 | `LEGACY ERROR` badge + zh tooltip | 2907 | ✅ |
| 7 | `NO HISTORY` badge + zh tooltip | 2905 | ✅ |
| 8 | `METADATA ONLY` badge + zh tooltip | 2904 | ✅ |
| 9 | `REGENERATED_RETROSPECTIVE` placeholder | 2908 | ✅ |
| 10 | `.rp-truth-retro { background:#6f42c1 }` | 269 | ✅ |
| 11 | `aria-label` badge count ≥ 6 | — | 8 found ✅ |
| 12 | `rp-truth-fixture` color distinct from retro | 268 vs 269 | ✅ |

**Static Verification: 12/12 PASS — P70_STATIC_VERIFICATION_PASS ✅**

---

## 11. start_all.sh Audit Result

**Current state**: Broken for main-branch backend.  
`start_all.sh` will produce `ModuleNotFoundError: No module named 'lottery_api'` because `PYTHONPATH` is not set and `lottery_api/` is the CWD.

**Action**: Do NOT modify in P70. List as **P71 startup reliability patch** scope.

**Mitigation now**: Backend running manually (PID 56256) with correct env. Operators must use manual startup command until P71.

**Manual startup command (working)**:
```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api
PYTHONPATH=/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean \
  nohup /usr/bin/python3 app.py > ../backend.log 2>&1 &
```

---

## 12. Remaining Limitations

| Limitation | Impact | Resolution |
|-----------|--------|-----------|
| PR #87 not merged — awaiting `YES merge PR #87` | P69 polish not in main yet | Reply with exact phrase to proceed |
| PR #86 (P68 docs) still open | Independent — CI green | Merge at operator discretion |
| Browser DOM screenshots not captured | No visual PNG evidence | Run with browser session in P71 QA round |
| `start_all.sh` missing PYTHONPATH | Backend fails on cold start | P71 startup reliability patch |
| Backend running via manual startup (not launchd) | Backend lost on machine restart | P71: add to start_all.sh or launchd plist |

---

## 13. Recommendation

**READY_FOR_P71_STARTUP_RELIABILITY** (after PR #87 merges)

Rationale:
- PR #87: OPEN, MERGEABLE, CLEAN, CI 2/2 ✅ — ready to merge
- All safety gates passed: diff scope, DB hash, registry hash
- Main-branch backend fully operational: health ✅, strategy-lifecycle ✅, 3×summary ✅
- Truth-level matrix: all 16 strategies correct via API cross-validation
- Static verification: 12/12 PASS
- Only gap: browser visual evidence (P71 scope) + start_all.sh fix (P71 scope)

---

## 14. Next 24H Prompt for P71

```
# P71 Trigger
After "YES merge PR #87" is given and P70 docs PR merges:

P71: Startup Reliability Patch + Browser Visual Evidence

1. MERGE PR #87 (if not already done via P70)
2. PATCH start_all.sh in LotteryNew-clean:
   - Add PYTHONPATH=/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean
   - Use /usr/bin/python3 explicitly in backend startup
   - Test: ./stop_all.sh && ./start_all.sh → verify health OK
3. Browser QA session:
   - Open http://localhost:8081 (with P69 index.html)
   - Verify LIVE badge renders green with hover tooltip
   - Verify METADATA ONLY badge renders amber
   - Verify NO HISTORY tombstone renders with 🪦 Chinese text
   - Capture screenshots:
     outputs/replay/p71_live_badge_evidence_20260513.png
     outputs/replay/p71_metadata_only_evidence_20260513.png
     outputs/replay/p71_no_history_evidence_20260513.png
4. Produce P71 evidence report
5. Open docs PR for P71

No new feature scope. P71 = start_all.sh fix + browser visual QA.
```

---

## 15. Final Markers

- ✅ P70_BASELINE_VERIFIED — main HEAD `5e1b23f`, PR #84/#85 merged
- ✅ P70_PR87_STATE_VERIFIED — OPEN, MERGEABLE, CLEAN, CI 2/2
- ✅ P70_DIFF_SCOPE_VERIFIED — index.html + P69 report only, no forbidden files
- ✅ P70_DB_UNCHANGED — `de0e27bb800bc7183773a0dc596d66b8`
- ✅ P70_REGISTRY_UNCHANGED — `3ea71cfc20c882714f3824ad68202f6e`
- ⏳ WAITING_FOR_YES_MERGE_PR87 — exact approval not received
- (skipped) P70_MAIN_SYNCED — not applicable until merge
- ✅ P70_BACKEND_SMOKE_PASS — `/health`, `/strategy-lifecycle`, 3× `/summary` all OK
- ✅ P70_OPERATOR_EVIDENCE_PARTIAL — API cross-validation complete; screenshots NOT RUN
- ✅ P70_STATIC_VERIFICATION_PASS — 12/12
- ✅ P70_REPORT_CREATED
- ⏳ P70_DOCS_PR_OPENED_<URL> — pending Stage J
- ✅ P70_READY_FOR_P71_STARTUP_RELIABILITY
