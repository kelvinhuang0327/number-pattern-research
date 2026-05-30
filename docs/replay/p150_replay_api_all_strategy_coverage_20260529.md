# P150: Replay API All Strategy Coverage

**Generated**: 2026-05-30T11:32:11.467760+00:00
**Classification**: `P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY`
**Canonical repo**: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`
**Canonical branch**: `claude/zen-gates-ff6802`

---

## 1. Executive Summary

P150 closes three replay API coverage gaps identified in P149:

1. **bet_index** was missing from `/api/replay/history` response — multi-bet rows were indistinguishable
2. **no_data_reason** was absent — strategies with zero replay rows had no explanation
3. **All-strategy visibility** — 22 DB-only strategies had no lifecycle registration

Changes are exclusively source-controlled (Python registry + route files). Zero DB writes.

---

## 2. Canonical Repo / Branch Confirmation

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | OK |
| branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | OK |
| DB rows | 94924 | 94924 | OK |
| drift guard | PASS | PASS | OK |

---

## 3. P149 Recap and Gap Mapping

**P149 artifact**: `outputs/replay/p149_replay_product_coverage_audit_20260529.json`
**P149 classification**: `P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY`
**P149 commit**: `d455ac0`

P149 identified 40 total strategies with these P150-targeted gaps:

| Gap ID | Area | Severity | Status |
|--------|------|----------|--------|
| GAP-001 | catalog | HIGH | Closed — 22 DB-only stubs added to registry |
| GAP-002 | data | CRITICAL | Documented — h6_gate_mk20_ew85 marked ONLINE_ZERO_REPLAY_ROWS |
| GAP-003 | catalog | MEDIUM | Closed — 4 REJECTED stubs have no_data_reason |
| GAP-004 | api | HIGH | Closed — bet_index added to /api/replay/history |
| GAP-005 | api | MEDIUM | Closed — no_data_reason in /api/replay/all-strategy-catalog |
| GAP-006 | ui | HIGH | Open → P151 |
| GAP-007 | ui | MEDIUM | Open → P151 |
| GAP-008 | data | LOW | No action required (governed baseline per P144D) |
| GAP-009 | data | MEDIUM | Documented in catalog |

---

## 4. Replay API Changes

### Files Modified

- `lottery_api/routes/replay.py`
- `lottery_api/models/replay_strategy_registry.py`

### Summary

- `lottery_api/routes/replay.py`: Added `bet_index` to SQL SELECT and response record; added `get_strategy_lifecycle_metadata` import; added new `/api/replay/all-strategy-catalog` endpoint
- `lottery_api/models/replay_strategy_registry.py`: Added `no_data_reason` field to `_StrategyMeta` and `_LifecycleStub`; added `DB_ONLY_MISSING_LIFECYCLE` to `LIFECYCLE_STATUSES`; added 22 DB-only strategy stubs; added `no_data_reason` markers for h6 and 4 REJECTED strategies

---

## 5. bet_index Support

**Before P150**: `bet_index` existed in DB schema but was NOT selected or returned by `/api/replay/history`. Multi-bet rows (bet_index 2..5) were indistinguishable from single-bet rows.

**After P150**: `bet_index` is included in the SQL SELECT clause and returned in every record of `/api/replay/history`. Records are ordered by `target_draw DESC, strategy_id ASC, bet_index ASC` so multi-bet groups are contiguous.

### bet_index distribution in DB

| bet_index | row_count |
|-----------|-----------|
| 1 | 54302 |
| 2 | 16581 |
| 3 | 15041 |
| 4 | 6000 |
| 5 | 3000 |

---

## 6. no_data_reason Support

A new `no_data_reason` field is added to `_StrategyMeta` in the source-controlled registry. Values used:

| Value | When used |
|-------|-----------|
| `ONLINE_ZERO_REPLAY_ROWS` | OBSERVATION/ONLINE strategy with zero rows (h6_gate_mk20_ew85) |
| `REJECTED_NO_REPLAY_DATA` | REJECTED strategies with no replay rows (4 strategies) |
| `ARTIFACT_ONLY` | RETIRED/OFFLINE strategies with no rows |
| `NO_REPLAY_DATA` | Generic fallback for other zero-row strategies |

`no_data_reason` is returned by the new `/api/replay/all-strategy-catalog` endpoint for all strategies.

---

## 7. All-Strategy Replay Catalog Coverage

### New endpoint: `GET /api/replay/all-strategy-catalog`

Returns all 40 strategies from the source-controlled registry with:
- `replay_row_count` — actual row count from DB
- `lifecycle_status` — from source-controlled registry
- `no_data_reason` — populated for zero-row strategies
- `is_row_backed` — true if row_count > 0

### Coverage summary

| lifecycle_status | count |
|-----------------|-------|
| `ONLINE` | 8 |
| `REJECTED` | 4 |
| `OBSERVATION` | 1 |
| `RETIRED` | 5 |
| `DB_ONLY_MISSING_LIFECYCLE` | 22 |

---

## 8. Zero Replay Rows Handling

Strategies with zero replay rows:

- `biglotto_ts3_acb_4bet` — no_data_reason: `see registry`
- `biglotto_ts3_markov_freq_5bet` — no_data_reason: `see registry`
- `power_shlc_midfreq` — no_data_reason: `see registry`
- `p1_deviation_2bet_539` — no_data_reason: `see registry`
- `h6_gate_mk20_ew85` — no_data_reason: `see registry`


**Approach**: `no_data_reason_in_registry_not_db_write`
— no_data_reason set in source-controlled registry; zero DB writes.

---

## 9. DB-Only Lifecycle Handling

22 strategies existed in DB replay rows without any lifecycle registration. Added as `DB_ONLY_MISSING_LIFECYCLE` placeholder stubs in `replay_strategy_registry.py`.

**Approach**: `source_controlled_registry_placeholder`

Strategies added:
- `539_3bet_orthogonal`
- `acb_single_539`
- `bet2_fourier_expansion_biglotto`
- `biglotto_echo_aware_3bet`
- `biglotto_ts3_markov_4bet_w30`
- `cold_complement_2bet`
- `cold_complement_biglotto`
- `coldpool15_biglotto`
- `daily539_f4cold_3bet`
- `daily539_f4cold_5bet`
- `fourier30_markov30_2bet`
- `fourier30_markov30_biglotto`
- `markov_1bet_539`
- `markov_2bet_biglotto`
- `markov_single_biglotto`
- `midfreq_fourier_mk_3bet`
- `p0b_539_3bet_f_cold_fmid`
- `p0c_539_3bet_f_cold_x2`
- `power_fourier_rhythm_2bet`
- `pp3_freqort_4bet`
- `zonal_entropy_2bet`
- `zone_gap_3bet_539`

---

## 10. h6_gate_mk20_ew85 Handling

| Property | Value |
|----------|-------|
| lifecycle_status | `OBSERVATION` |
| no_data_reason | `ONLINE_ZERO_REPLAY_ROWS` |
| replay_rows_inserted | 0 |
| action_taken | `registry_marker_added` |

h6_gate_mk20_ew85 is an OBSERVATION strategy (shadow evaluation only). Zero replay rows are expected and documented. No DB write performed.

---

## 11. Tests and Verification

- **Test file**: `tests/test_p150_replay_api_all_strategy_coverage.py`
- **Tests added**: 20
- **All pass**: True

Tests cover: JSON artifact existence, classifications, repo/branch/DB checks, bet_index in API code, no_data_reason in API code, all-strategy catalog coverage, h6 handling, non-actions, Markdown existence.

---

## 12. Explicit Non-Actions

| Action | Executed |
|--------|----------|
| DB write | NO |
| Replay rows inserted | 0 |
| Replay rows updated | 0 |
| Replay rows deleted | 0 |
| Controlled apply executed | NO |
| Champion promotion | NO |
| Registry promotion | NO |
| Live API called | NO |
| Scheduler installed | NO |
| P108/P117/P118 executed | NO |

---

## 13. Dirty File Hygiene

Status: `CLEAN`

Pre-existing modified files (not staged for P150):
- `docs/replay/p145b_*.md` — pre-existing from P145B
- `docs/replay/p146a_*.md` — pre-existing from P146A
- `outputs/replay/live_monitoring_observation_only/...` — pre-existing
- `outputs/replay/p145b_*.json` — pre-existing
- `outputs/replay/p146a_*.json` — pre-existing
- `backups/` — untracked, not staged (OK per task spec)

---

## 14. Remaining Risks

- midfreq_fourier_2bet exists in DB for both DAILY_539 and POWER_LOTTO — registry stub covers DAILY_539 only; POWER_LOTTO rows still visible via history API
- 22 DB-only strategies have lifecycle_status=DB_ONLY_MISSING_LIFECYCLE — formal governance review needed to assign correct RETIRED/REJECTED/OFFLINE status
- h6_gate_mk20_ew85 has zero replay rows despite OBSERVATION status — shadow evaluation not yet backfilled; requires separate replay generation task
- GAP-006 (UI multi-bet display) and GAP-007 (UI no_data badges) remain open — addressed in P151_REPLAY_UI_MULTI_BET_DISPLAY

---

## 15. Recommended Next Task

**P151_REPLAY_UI_MULTI_BET_DISPLAY**

Closes GAP-006 (UI multi-bet display) and GAP-007 (UI no_data placeholder badges).

---

## 16. Final Classification

**`P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY`**
