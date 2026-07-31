# P24: Full Strategy Universe Inventory
**Date:** 2026-05-21  
**Branch:** `p24-full-strategy-universe-inventory`  
**Phase:** P24  
**Status:** READY_FOR_MERGE

---

## Objective

Build a comprehensive, read-only inventory of **all strategies** in the replay system, classified by their `replay_visibility_state`. Sources include the authoritative registry, the production DB, rejected governance artifacts, and the P0 universe reference.

---

## Production State at Time of Inventory

| Metric | Value |
|---|---|
| Total production rows | **12460** |
| Row-backed strategies | **8** |
| Registry entries | **18** |
| Rejected artifacts | **42** JSON files |
| Total strategies inventoried | **59** |
| P0 universe reference | 512 strategies |

---

## Replay Visibility State Taxonomy

| State | Count | Meaning |
|---|---|---|
| `ONLINE_ROW_BACKED` | 8 | ONLINE in registry AND has rows in production DB |
| `OBSERVATION` | 1 | Shadow eval mode, under observation, no rows yet |
| `RETIRED` | 5 | Preserved in registry, superseded, no active rows |
| `REJECTED_REGISTERED` | 4 | Failed governance gates, adapter stub preserved in registry |
| `ARTIFACT_ONLY` | 41 | Only a rejected/ JSON artifact exists, no registry entry |

### ONLINE_ROW_BACKED strategies

| Strategy ID | Lottery Type | Row Count | Verified Rows |
|---|---|---|---|
| `power_precision_3bet` | POWER_LOTTO | 1570 | 1500 |
| `power_orthogonal_5bet` | POWER_LOTTO | 1570 | 1500 |
| `fourier_rhythm_3bet` | POWER_LOTTO | 1500 | 1500 |
| `biglotto_triple_strike` | BIG_LOTTO | 1570 | 1500 |
| `biglotto_deviation_2bet` | BIG_LOTTO | 1570 | 1500 |
| `ts3_regime_3bet` | BIG_LOTTO | 1500 | 1500 |
| `daily539_f4cold` | DAILY_539 | 1590 | 1500 |
| `daily539_markov_cold` | DAILY_539 | 1590 | 1500 |

### OBSERVATION

| Strategy ID | Lottery Type |
|---|---|
| `h6_gate_mk20_ew85` | BIG_LOTTO |

### RETIRED (adapter preserved, reconstructible)

| Strategy ID |
|---|
| `acb_1bet` |
| `acb_markov_midfreq` |
| `acb_markov_midfreq_3bet` |
| `midfreq_acb_2bet` |
| `midfreq_fourier_2bet` |

### REJECTED_REGISTERED (adapter stub, reconstructible)

| Strategy ID |
|---|
| `biglotto_ts3_acb_4bet` |
| `biglotto_ts3_markov_freq_5bet` |
| `power_shlc_midfreq` |
| `p1_deviation_2bet_539` |

### ARTIFACT_ONLY (rejected/ JSON only, 41 entries)

Not listed individually here. Refer to `outputs/replay/p24_full_strategy_universe_inventory_20260521.json` for the full list.

---

## By Lottery Type

| Lottery Type | Count |
|---|---|
| BIG_LOTTO | 23 |
| DAILY_539 | 18 |
| POWER_LOTTO | 12 |
| UNSPECIFIED | 6 |

---

## Output Artifact

```
outputs/replay/p24_full_strategy_universe_inventory_20260521.json
```

Fields per strategy entry:

| Field | Description |
|---|---|
| `strategy_id` | Unique strategy identifier |
| `display_name` | Human-readable name |
| `strategy_version` | Semver |
| `lottery_type` | DAILY_539 / BIG_LOTTO / POWER_LOTTO / UNSPECIFIED |
| `lifecycle_state` | ONLINE / REJECTED / RETIRED / OBSERVATION / OFFLINE |
| `replay_visibility_state` | P24 classification (see taxonomy above) |
| `row_count` | Total rows in production DB for this strategy |
| `verified_row_count` | Rows with a non-null truth_level |
| `truth_level_summary` | Truth levels seen in DB |
| `source_path` | Registry file path (null for ARTIFACT_ONLY) |
| `source_artifact` | Artifact file path (null for registry entries) |
| `reconstructible_candidate` | True if adapter exists and could be reactivated |
| `needs_manual_review` | True if classification requires human review |

---

## Test Coverage

File: `tests/test_p24_full_strategy_universe_inventory.py`

| Test Class | Tests | Description |
|---|---|---|
| `TestInventoryFileStructure` | 7 | File existence, JSON validity, top-level keys |
| `TestRequiredFields` | 8 | All entries have required fields, types valid |
| `TestOnlineRowBacked` | 8 | row_count > 0, exact strategy IDs, verified ≥ 1500 |
| `TestArtifactOnly` | 6 | source_artifact set, row_count=0, files exist on disk |
| `TestRegisteredNonOnline` | 8 | RETIRED x5, REJECTED_REGISTERED x4, reconstructible |
| `TestObservation` | 4 | h6_gate_mk20_ew85, reconstructible, row_count=0 |
| `TestProductionDBIntegrity` | 4 | rows=12460 in JSON and via live DB |
| `TestSummaryCounts` | 7 | totals, P0 reference count, vis counts sum |
| `TestCategorySeparation` | 5 | No duplicates, source_path/artifact rules |
| `TestP22Regression` | 3 | DAILY_539 predicted_special=NULL |
| `TestP23Regression` | 3 | Registry has 8 ONLINE, preset buttons in HTML |
| `TestDriftGuardCrossCheck` | 2 | rows=12460, strategy IDs stable |

**Total: 65 tests, 65 PASS**

Canonical regression: **186/186 PASS** (P21b + P22 + P23 suites unchanged).

---

## Guards

| Guard | Result |
|---|---|
| `replay_lifecycle_drift_guard.py --strict` | **PASS** |
| `replay_branch_governance_guard.py --expected-branch p24-full-strategy-universe-inventory --expected-rows 12460` | **PASS** |

---

## Governance

- **No DB writes** — `dry_run_only=True`
- **No strategy execution** — read-only inventory only
- **No external API calls**
- Committed files: generator script, output JSON, test file, this doc
- DB not staged
