# P2 Catalog Apply — CTO Readiness Report
**Date:** 2026-05-19  
**Author:** CTO Agent (Replay Track)  
**Branch:** `feat/p0-single-repo-stabilization-p1-catalog-plan-20260519`

---

## 1. P0/P1 Re-verification (2026-05-19)

| Check | Status |
|-------|--------|
| `pytest tests/test_replay_api_contract.py` | **44/44 PASS** ✅ |
| `pytest tests/test_p0_schema_migration.py` | **6/6 PASS** ✅ |
| `pytest tests/test_p1_catalog_visibility_contract.py` | **14/14 PASS** ✅ |
| `pytest tests/test_p1_catalog_visibility_plan.py` | **15/15 PASS** ✅ |
| `scripts/replay_lifecycle_drift_guard.py --strict` | **PASS** ✅ |
| DB replay rows | **460 legacy rows, unchanged** ✅ |
| Registry count | **18 strategies** (reconciled; CEO brief said 16) ✅ |

P1 planner re-run output consistent with prior run:
- `runtime_canonical_before.total` = 18
- `REGISTERED_WITH_REPLAY_ROWS` = 6
- `RECONSTRUCTIBLE` = 12
- `ARTIFACT_CANDIDATE` = 41
- `REGISTERED_NO_DATA` = 0
- `UNSUPPORTED` = 0

---

## 2. P2 Apply Scope

P2 creates one new table (`strategy_catalog`) and writes catalog entries from the P1 plan.

**What P2 does:**
- Creates `strategy_catalog` table via `0002_p2_catalog_table.sql`
- Upserts 59 catalog entries (18 registered + 41 artifact candidates)
- Every entry has `dry_run_only=1` (informational catalog only)

**What P2 explicitly does NOT do:**
- Does NOT generate replay rows
- Does NOT generate prediction rows
- Does NOT execute strategy logic
- Does NOT import draw data
- Does NOT modify `strategy_prediction_replays` (protected)
- Does NOT modify `prediction_items` / `prediction_runs` (protected)
- Does NOT change `lifecycle_state` to ONLINE for any entry
- Does NOT mark ARTIFACT_CANDIDATE as runtime-online

---

## 3. Planned Catalog Row Counts

| Category | Count |
|----------|-------|
| Registered strategies | 18 |
| Artifact candidates (rejected/) | 41 |
| **Total** | **59** |

Expected `strategy_catalog` rows after apply: **59**

---

## 4. Registered vs Artifact Candidate Distribution

### Registered (18)
| Lifecycle | Count | Strategy IDs |
|-----------|-------|--------------|
| ONLINE | 8 | power_precision_3bet, power_orthogonal_5bet, fourier_rhythm_3bet, biglotto_triple_strike, biglotto_deviation_2bet, ts3_regime_3bet, daily539_f4cold, daily539_markov_cold |
| REJECTED | 4 | biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539 |
| RETIRED | 5 | acb_1bet, acb_markov_midfreq, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet |
| OBSERVATION | 1 | h6_gate_mk20_ew85 |

### Visibility States (registered)
| State | Count |
|-------|-------|
| REGISTERED_WITH_REPLAY_ROWS | 6 |
| RECONSTRUCTIBLE | 12 |
| REGISTERED_NO_DATA | 0 |

### Artifact Candidates (41)
- Source: `rejected/` JSON files
- All have `lifecycle_state = NOT_REGISTERED`
- All have `catalog_visibility_state = ARTIFACT_CANDIDATE`
- All have `dry_run_only = 1`
- None can be marked ONLINE (enforced in code + tests)

---

## 5. RECONSTRUCTIBLE Queue Summary (P5 Input)

12 strategies are classified RECONSTRUCTIBLE — they exist in the runtime registry but have 0 replay rows, and their code artifact was found via Python source scan.

| Strategy ID | Lifecycle | Artifact Source |
|-------------|-----------|-----------------|
| fourier_rhythm_3bet | ONLINE | CODE_SCAN |
| ts3_regime_3bet | ONLINE | CODE_SCAN |
| biglotto_ts3_acb_4bet | REJECTED | CODE_SCAN |
| biglotto_ts3_markov_freq_5bet | REJECTED | CODE_SCAN |
| power_shlc_midfreq | REJECTED | CODE_SCAN |
| p1_deviation_2bet_539 | REJECTED | CODE_SCAN |
| acb_1bet | RETIRED | CODE_SCAN |
| acb_markov_midfreq | RETIRED | CODE_SCAN |
| acb_markov_midfreq_3bet | RETIRED | CODE_SCAN |
| midfreq_acb_2bet | RETIRED | CODE_SCAN |
| midfreq_fourier_2bet | RETIRED | CODE_SCAN |
| h6_gate_mk20_ew85 | OBSERVATION | CODE_SCAN |

These are inputs for P5-P7 historical reconstruction. P2 catalog apply marks them RECONSTRUCTIBLE in the catalog — no rows are generated.

---

## 6. Rollback Plan

**Rollback command (instant, no data loss):**
```bash
python3 scripts/p2_catalog_apply.py --rollback --apply
```

This executes `DROP TABLE IF EXISTS strategy_catalog`. Since `strategy_catalog` is a new table that never existed before P2, rollback restores the DB to its pre-P2 state with zero risk.

**Rollback timing:** Can be executed at any time after apply. Strategy prediction replays (460 rows) are entirely unaffected.

**Backup created automatically:** `backups/lottery_v2_pre_p2_catalog_apply_YYYYMMDD_HHMMSS.db`

---

## 7. Safety Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| No replay rows modified | `_PROTECTED_TABLES` set + pre/post count assertion |
| No prediction rows modified | Same protected table check |
| ARTIFACT_CANDIDATE never ONLINE | Code-level assertion + test coverage |
| Backup before write | `_backup_db()` called in `run_apply()` before first DB write |
| Idempotent | `INSERT OR REPLACE ON CONFLICT(strategy_id, lottery_type)` |
| Rollback available | `DROP TABLE IF EXISTS strategy_catalog` |
| Dry-run by default | `--apply` flag required; tests verify dry-run writes nothing |
| Migration IF NOT EXISTS | Re-run safe |

---

## 8. Explicit Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `strategy_catalog` table is NEW — no existing rows to protect | LOW | Rollback trivial: DROP TABLE |
| 41 artifact candidates in catalog may confuse UI if displayed without filter | MEDIUM | `dry_run_only=1` flag; UI must filter or label accordingly |
| RECONSTRUCTIBLE strategies appear in catalog before rows exist | LOW | `has_replay_rows=0` and `reconstructible_reason` field communicate this |
| CEO brief's "16 strategies" vs actual 18 may cause confusion | LOW | Reconciliation doc committed at `docs/replay/p0_registry_reconciliation_20260519.md` |
| Planner performs Python source scan — could be slow on large repos | LOW | 59 entries processed in <2s in tests |

---

## 9. CEO Authorization Question

P2 catalog apply is non-destructive: it adds one new table, does not touch any existing rows, and is fully rollback-able in one command.

**To authorize P2 controlled catalog apply, please reply:**

> **YES apply P2 catalog**

---

## 10. Exact Apply Command (Do NOT execute without CEO authorization)

```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
python3 scripts/p2_catalog_apply.py --apply
```

Expected output:
- Backup created: `backups/lottery_v2_pre_p2_catalog_apply_YYYYMMDD_HHMMSS.db`
- `strategy_catalog` table created
- 59 rows INSERTed
- 0 violations
- `strategy_prediction_replays` row count = 460 (unchanged)

Post-apply verification:
```bash
python3 scripts/replay_lifecycle_drift_guard.py --strict
python3 -m pytest -q tests/
```
