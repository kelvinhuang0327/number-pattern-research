# P1 Strategy Universe Inventory Report

**Document type**: Read-Only Inventory Report  
**Date**: 2026-05-15  
**Branch**: `docs/p1-strategy-universe-inventory-20260515`  
**Base commit**: `b98a1feb8465ae82a520a2a7c6c5e07325f2ca4c` (PR #100 merge)  
**Script**: `scripts/p1_strategy_universe_inventory_readonly.py`  

---

## 1. 本輪目標

建立「策略全集 strategy universe」完整分母，用於衡量 Replay 頁面真實覆蓋率。

**本輪執行規則：**
- ✅ Read-only 掃描
- ❌ 未寫 DB
- ❌ 未跑 backtest
- ❌ 未新增 replay row
- ❌ 未修改策略邏輯
- ❌ 未修改 API / UI / backend behavior
- ❌ 未修改 registry semantics

---

## 2. 掃描來源

| 來源 | 路徑 | 找到策略 |
|------|------|---------|
| 官方 Registry | `lottery_api/models/replay_strategy_registry.py` | 16 canonical |
| V3 Tombstone Guard | `scripts/replay_lifecycle_drift_guard.py` | 6 CODE_MISSING IDs |
| DB read-only | `lottery_api/data/lottery_v2.db` → `strategy_prediction_replays` | 10 distinct |
| Artifact JSON/JSONL | `outputs/replay/*.json`, `*.jsonl` | 93 unique IDs (含 noise) |
| Prev inventory | `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` | 91 candidates |
| Code search | `lottery_api/`, `scripts/`, `tests/`, `tools/` | 16 (registry-only) |

---

## 3. 統計摘要

| 指標 | 數量 |
|------|------|
| **Total unique strategy candidates** | **89** |
| Canonical registry strategies | 16 |
| DB distinct strategies | 10 |
| Artifact-only strategies (not in registry/DB) | 73 |
| Code-only strategies | 0 |
| Unknown lifecycle | 2 |
| Replay COVERED (DB rows + ONLINE) | **6** |
| Replay PARTIAL (DB rows + REJECTED/OBSERVATION) | 4 |
| Coverage gaps | 73 |

**Replay coverage rate = 6 / 89 = 6.7%** (ONLINE strategies fully covered)  
**Including PARTIAL = 10 / 89 = 11.2%** (all strategies with any DB rows)

> Note: 4 noise IDs removed from universe (`strategy`, `big_lotto`, `daily_539`, `power_lotto`)

---

## 4. Canonical 16 vs Strategy Universe 差異

**Canonical 16 (registry):**

| Strategy ID | Lifecycle | DB Rows | Truth | Coverage |
|-------------|-----------|---------|-------|----------|
| power_precision_3bet | ONLINE | 120 | REGENERATED_RETROSPECTIVE | COVERED |
| power_orthogonal_5bet | ONLINE | 120 | REGENERATED_RETROSPECTIVE | COVERED |
| biglotto_triple_strike | ONLINE | 120 | REGENERATED_RETROSPECTIVE | COVERED |
| biglotto_deviation_2bet | ONLINE | 120 | REGENERATED_RETROSPECTIVE | COVERED |
| daily539_f4cold | ONLINE | 140 | REGENERATED_RETROSPECTIVE | COVERED |
| daily539_markov_cold | ONLINE | 140 | REGENERATED_RETROSPECTIVE | COVERED |
| biglotto_ts3_acb_4bet | REJECTED | 50 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | PARTIAL |
| biglotto_ts3_markov_freq_5bet | REJECTED | 50 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | PARTIAL |
| power_shlc_midfreq | REJECTED | 50 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | PARTIAL |
| p1_deviation_2bet_539 | REJECTED | 50 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | PARTIAL |
| acb_1bet | RETIRED | **0** | CODE_MISSING | NOT_COVERED |
| acb_markov_midfreq | RETIRED | **0** | CODE_MISSING | NOT_COVERED |
| acb_markov_midfreq_3bet | RETIRED | **0** | CODE_MISSING | NOT_COVERED |
| midfreq_acb_2bet | RETIRED | **0** | CODE_MISSING | NOT_COVERED |
| midfreq_fourier_2bet | RETIRED | **0** | CODE_MISSING | NOT_COVERED |
| h6_gate_mk20_ew85 | OBSERVATION | **0** | CODE_MISSING | NOT_COVERED |

**Non-canonical strategies (73 artifact-only):**

These 73 strategies appeared in historical backtest/research artifacts but are NOT in the canonical registry and have NO DB replay rows. They represent the "extended universe" found in research outputs.

> Full list in `outputs/replay/p1_strategy_universe_inventory_20260515.csv`

---

## 5. DB-only Strategies

**Zero strategies** in DB without a registry entry.  
All 10 DB strategies are accounted for in the canonical registry:  
→ No orphaned DB rows detected.

---

## 6. Artifact-only Strategies (73)

These strategies appeared only in historical JSON/JSONL artifact files (outputs/replay/*.json, outputs/replay/*.jsonl). They are **not** in the canonical registry and have **zero DB rows**.

**Lifecycle breakdown of artifact-only:**
- REJECTED: 71 (from previous inventory classification)
- UNKNOWN: 2 (`fourier_rhythm_3bet`, `ts3_regime_3bet`)

**Notable subgroups:**

| Subgroup | Count | Examples |
|----------|-------|---------|
| H-series research tools | 8 | `H001` through `H008` |
| ACB variants | ~10 | `acb_extremecol_2bet_539`, `acb_hot_fourier_3bet_biglotto`, etc. |
| Biglotto research | ~15 | `biglotto_6bet_zone_residual`, `ts3_acb_4bet_biglotto`, etc. |
| Power lotto research | ~10 | `fourier_w100_pp3_power`, `sgp_power_017_research`, etc. |
| Daily 539 research | ~15 | `bandit_ucb1_2bet_539`, `cold_burst_3bet_539`, etc. |
| Phase-named variants | ~8 | `p0_neighbor_injection`, `p0b_539_3bet_f_cold_fmid`, etc. |
| Zone/gap/cold variants | ~7 | `zone_cascade_guard_biglotto`, `zone_gap_3bet_539`, etc. |

---

## 7. Code-only Strategies

**Zero code-only strategies** detected.  
All registry strategies have corresponding registry entries.  
Non-registry strategy code files (`backtest_monte_carlo_strategy.py`, etc.) are backtest/evaluation tools, not deployable strategies.

---

## 8. Registry-without-row Strategies

6 registry strategies have zero DB rows — all are V3 CODE_MISSING tombstones:

| Strategy ID | Lifecycle | Reason |
|-------------|-----------|--------|
| acb_1bet | RETIRED | V3 CODE_MISSING; code unavailable for re-run |
| acb_markov_midfreq | RETIRED | V3 CODE_MISSING; code unavailable for re-run |
| acb_markov_midfreq_3bet | RETIRED | V3 CODE_MISSING; code unavailable for re-run |
| midfreq_acb_2bet | RETIRED | V3 CODE_MISSING; code unavailable for re-run |
| midfreq_fourier_2bet | RETIRED | V3 CODE_MISSING; code unavailable for re-run |
| h6_gate_mk20_ew85 | OBSERVATION | V3 CODE_MISSING; code unavailable for re-run |

Zero rows is **by design and enforced** by the drift guard (PR #100).  
Display: tombstone card with `NO_DATA` label per PR #102 spec §F.

---

## 9. UNKNOWN Lifecycle Strategies

2 strategies with UNKNOWN lifecycle — both artifact-only, not in registry:

| Strategy ID | Sources | Gap Type | Recommended Action |
|-------------|---------|----------|--------------------|
| `fourier_rhythm_3bet` | artifact only | unknown_lifecycle | Operator classify: likely REJECTED research prototype |
| `ts3_regime_3bet` | artifact only | unknown_lifecycle | Operator classify: likely REJECTED (appeared in ts3 backtest batch) |

---

## 10. Replay Coverage Gaps Summary

| Gap Type | Count | Description |
|----------|-------|-------------|
| `artifact_only` | 71 | In historical artifacts only; no registry, no DB rows |
| `unknown_lifecycle` | 2 | Lifecycle unknown; need operator classification |
| `registry_without_rows` | 6 | V3 tombstones in registry with 0 DB rows (by design) |
| **Total gaps** | **73** (+ 6 by-design) | |

---

## 11. 不應進 Registry 的研究工具 / Superseded Artifact 候選

The following categories are candidates for "research archive" classification  
(should NOT enter the canonical registry without new governance approval):

1. **H-series IDs** (`H001`–`H008`): Appear to be hypothesis testing labels, no identifying names, UNKNOWN lottery type. Recommend: classify as `research_archive`, exclude from replay denominator.

2. **Phase-prototype variants** (`p0_neighbor_injection`, `p0b_*`, `p0c_*`, `p2_mab_fusion`, `p3_state_aware`): Intermediate pipeline prototypes. Recommend: `research_archive`.

3. **Biglotto ts3 variants** (`ts3_acb_4bet_biglotto`, `ts3_markov_freq_5bet_biglotto`, `ts3_regime_3bet`): Similar to canonical REJECTED biglotto_ts3_* but with different naming. Possible duplicates of registry entries. Recommend: cross-reference with registry canonical REJECTED entries.

4. **SGP research** (`sgp_power_017_research`, `sgp_v9_apex_powerlotto`): Research variants. Not in registry. Recommend: `research_archive`.

5. **Generic single-bet prototypes** (`markov_1bet_539`, `extremecol_1bet_539`, `acb_single_539`, etc.): Early-stage single-number prototypes. Recommend: `research_archive`.

---

## 12. 建議下一步

### Option A — P1.1: Operator Acceptance / Classification Cleanup
- Operator reviews the 73 artifact-only strategies
- For each: classify as `RETIRED` / `REJECTED` / `research_archive` / `duplicate`
- Clean up noise IDs (`fourier_rhythm_3bet`, `ts3_regime_3bet`, H-series)
- Determines the **authoritative denominator** for replay coverage rate
- **Estimated universe after cleanup**: ~20–25 legitimate non-canonical strategies (vs 73 raw)

### Option B — P2: Operator Acceptance UI
- Build the replay display UI based on PR #102 display semantics spec
- Use canonical 16 as the initial denominator
- P1.1 cleanup runs in parallel without blocking UI

### Recommendation: **P1.1 first** — the denominator must be agreed before reporting coverage %.  
If we ship UI with denominator = 89, coverage rate looks artificially low (6.7%).  
After P1.1 cleanup, likely denominator = 20–25, coverage rate improves to ~40–50%.

---

## 13. 本輪 Non-goals 確認

| Non-goal | Confirmed |
|----------|-----------|
| 未新增策略 | ✅ |
| 未補 replay row | ✅ |
| 未寫 DB | ✅ |
| 未修改 API / UI / backend | ✅ |
| 未跑 backtest | ✅ |
| 未把 retrospective row 說成 live prediction | ✅ |
| 未修改 registry | ✅ |
| 未 merge PR | ✅ |

---

## Appendix: Artifact Files Scanned

```
outputs/replay/*.json   (20 files)
outputs/replay/*.jsonl  (3 files)
```

Key files contributing strategy IDs:
- `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` — 91 candidates
- `outputs/replay/p56_all_lifecycle_replay_coverage_manifest_20260512.json`
- `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json`
- `outputs/replay/non_online_replay_fixture_20260511.json`
- `outputs/replay/p1_executable_inventory_20260513.json`
