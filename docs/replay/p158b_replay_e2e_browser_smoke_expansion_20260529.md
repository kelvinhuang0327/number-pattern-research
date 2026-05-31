# P158B: Replay E2E Browser Smoke Expansion

**Classification**: `P158B_REPLAY_STATIC_UI_SMOKE_READY`
**Task ID**: P158B
**Generated**: 2026-05-30

---

## 1. Executive Summary

P158B extends the existing replay browser smoke tests (`test_replay_browser_smoke.py`) with static HTML/JS inspection coverage for P151-P157 features. No Playwright, no live API, no external browser process.

All 7 smoke dimensions confirmed present in `index.html`:
1. ✅ Replay entrypoint
2. ✅ All-strategy catalog (P151)
3. ✅ Lifecycle visibility invariant (P157)
4. ✅ NO_DATA reason badges (P151)
5. ✅ Multi-bet / bet_index display (P151)
6. ✅ Provenance metadata (P152)
7. ✅ Champion boundary confirmed

**77 P158B tests pass. DB = 94924 unchanged. No DB writes.**

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `.../zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | PASS | ✅ PASS |

---

## 3. P158 Governance Chain Closure Recap

P158 (`1f20c88`) formally closed the replay product governance chain with 0 blocking gaps, 40/40 strategies, 94924 rows, DB_ONLY=0, visibility invariant confirmed.

P158B provides browser smoke evidence for the P151-P157 feature set.

---

## 4. Browser/Static Smoke Strategy

| Item | Value |
|------|-------|
| Smoke mode | `static_html_inspection` |
| Existing browser framework | ✅ Yes (`test_replay_browser_smoke.py`) |
| No new large dependency | ✅ True |
| Method | Static HTML/JS string inspection (extends existing pattern) |

---

## 5. Replay Entrypoint Smoke

| Check | Status |
|-------|--------|
| `<section id="replay-section">` exists | ✅ |
| `/api/replay` base configured | ✅ |
| History endpoint (`${BASE}/history`) | ✅ |
| Strategy endpoint present | ✅ |

---

## 6. All-Strategy Catalog Smoke

| Check | Status |
|-------|--------|
| `rp-all-catalog-card` present | ✅ |
| `rp-all-catalog-tbody` present | ✅ |
| `all-strategy-catalog` endpoint called | ✅ |
| `rpLoadAllStrategyCatalog` function defined | ✅ |
| Expected total = 40 | ✅ |
| RETIRED visible | ✅ |
| REJECTED visible | ✅ |
| OBSERVATION visible | ✅ |

---

## 7. Lifecycle Visibility Smoke

| Check | Status |
|-------|--------|
| lifecycle is label not gate | ✅ |
| RETIRED visible | ✅ (17 strategies, all with rows) |
| REJECTED visible | ✅ (4 strategies) |
| OBSERVATION visible | ✅ (h6_gate) |
| DB_ONLY_MISSING_LIFECYCLE remaining | 0 ✅ |
| Visibility invariant confirmed (P157) | ✅ |

---

## 8. NO_DATA Smoke

| Check | Status |
|-------|--------|
| `rpNoDataReasonBadge` function | ✅ |
| `ONLINE_ZERO_REPLAY_ROWS` label | ✅ |
| `REJECTED_NO_REPLAY_DATA` label | ✅ |
| `DB_ONLY_MISSING_LIFECYCLE` label | ✅ |
| `.rp-ndr-zero-online` CSS | ✅ |
| `.rp-ndr-rejected` CSS | ✅ |
| h6_gate visible zero rows | ✅ |

---

## 9. Multi-Bet Smoke

| Check | Status |
|-------|--------|
| `rp-bet-index-badge` present | ✅ |
| `.rp-bet-index-badge` CSS | ✅ |
| `rp-detail-bet-index` testid | ✅ |
| `注次（bet_index）` label | ✅ |
| `multi-bet` label | ✅ |
| Max bet_index expected | 5 |
| Multi-bet rows in DB | 40622 |

---

## 10. Provenance Metadata Smoke

| Check | Status |
|-------|--------|
| `rp-detail-truth-level` | ✅ |
| `rp-detail-source` | ✅ |
| `rp-detail-controlled-apply-id` | ✅ |
| `rp-detail-provenance-hash` | ✅ |
| `rp-row-source` (history row) | ✅ |
| `rp-truth-legacy-unverified` badge | ✅ |
| `rp-truth-tierb` badge | ✅ |

---

## 11. Champion Boundary Smoke

| Check | Status |
|-------|--------|
| Champion evaluation blocked | ✅ True |
| Replay UI blocked by champion | ❌ False |
| Historical `actual_numbers` used | ✅ |
| LIVE_MONITORING_VERIFIED for champion only | ✅ |

---

## 12. Tests and Verification

| Suite | Result |
|-------|--------|
| `tests/test_p158b_replay_e2e_browser_smoke_expansion.py` | **77 passed** |
| Regression (P149–P158) | **497 passed** |
| Total | **574 passed** |
| Drift guard | PASS |
| DB rows | 94924 (unchanged) |

---

## 13. Explicit Non-Actions

DB write ❌ / lifecycle update ❌ / replay rows 0/0/0 / controlled_apply ❌ / champion ❌ / live API ❌ / scheduler ❌.

---

## 14. Dirty File Hygiene Note

- `backups/` untracked — not staged
- `replay_strategy_registry.py` NOT staged
- Only P158B whitelist files staged

---

## 15. Remaining Risks

1. No live browser integration testing (static smoke only)
2. h6_gate_mk20_ew85 still 0 rows — non-blocking, visible
3. P108/P117/P118/4★ BLOCKED — separate chain

---

## 16. Recommended Next Task

`P159_PROVENANCE_SOURCE_UI_POLISH` (optional) or **governance chain fully complete**.

---

## 17. Final Classification

```
P158B_REPLAY_STATIC_UI_SMOKE_READY
```
