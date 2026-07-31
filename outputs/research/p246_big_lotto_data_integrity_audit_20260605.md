# P246 — BIG_LOTTO Data-Integrity Audit

**Task ID:** P246 · **Date:** 2026-06-05 · **Type:** Read-only data-integrity audit.
**DB:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db` (SQLite mode=ro, read-only confirmed)
**Final Classification:** `P246_BIG_LOTTO_DATA_INTEGRITY_AUDIT_COMPLETE_GATE_RED_CONFIRMED`

---

## 1. Executive Summary

[Confirmed] BIG_LOTTO `draws` table: **22,238 total rows**, only **2,113 plausible real 6/49** (governance expectation ≈2,118; delta -5).
**20,125 rows (90.5%) are contaminated** across three identified families.

[Confirmed] All corrected-significant P219 BIG_LOTTO signals (M1/M2/M3/M4/M6) are fully explained by these contamination families. **Anomaly is NOT predictor.**

[Confirmed] No DB write was performed. `GATE_RED_DATA_CONTAMINATION` remains in effect. BIG_LOTTO bias research blocked until Type D quarantine is authorized and a clean re-audit passes.

---

## 2. Prior Evidence Verified

| Artifact | Classification | Finding Used |
|---|---|---|
| **P219** | `PREDICTIVE_NULL + BIG_LOTTO_CONTAMINATION` | Bonferroni/BH signals = contamination artifacts |
| **P245B** | `CORRECTED_BIAS_GATE_LAYER_DESIGN_COMPLETE` | BIG_LOTTO = GATE_RED_DATA_CONTAMINATION |
| **P238B** | `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY` | No actionable bias on clean games |

---

## 3. Row-Family Classification

| Family | Count | % | draw_id example | sum_mean | max_mean | max range | Year span |
|---|---|---|---|---|---|---|---|
| `SIM_HYPHEN` | 19,100 | 85.89% | `100000009-01` | 149.2 | 43.0 | 11–49 | 2011–2023 |
| `DATE_FORMAT_ALIEN` | 375 | 1.69% | `20090727` | 74.7 | 22.5 | 21–24 | 2009–2010 |
| `SMALL_POOL_ALIEN` | 650 | 2.92% | `96000058` | 75.0 | 22.5 | 17–25 | 2007–2026 |
| `CANONICAL_PLAUSIBLE` | 2,113 | 9.5% | `96000001` | 151.0 | 43.0 | 26–49 | 2007–2026 |

---

## 4. Contamination Evidence

### 4.1 SIM_HYPHEN — Simulation Artifacts
- **Count:** 19,100
- **Pattern:** composite IDs like `103000009-01`…`103000009-100` — 100 synthetic variants per real draw date.
- **Numbers:** plausible 6/49 ranges (real draws' numbers reused), but IDs are non-canonical.
- **P219 link:** Excluded at load time by `draw NOT LIKE '%-%'`; did not drive structural-break signals.

### 4.2 DATE_FORMAT_ALIEN — Date-Literal IDs
- **Count:** 375
- **Pattern:** 8-digit `YYYYMMDD` IDs starting `20` (e.g. `20090727`).
- **Numbers:** sum_mean ≈ 74.7, max ≤ 24 — NOT 6/49 pool.
- **P219 link:** Excluded in P219 secondary filter; residual contributed to CUSUM/drift signals.

### 4.3 SMALL_POOL_ALIEN — Mislabeled Small-Pool Game
- **Count:** 650 (23.5% of serial rows)
- **Pattern:** Normal serial IDs (e.g. `100000003`) but `max(numbers) ≤ 25`. Concentrated 2011–2014 era.
- **Likely cause:** Different game (possibly 6/38 or earlier 6/42 format) mislabeled as `BIG_LOTTO`.
- **P219 link:** **Primary driver** of all P219 BIG_LOTTO corrected signals. During their chronological block, numbers 26–49 are absent → CUSUM 11× null, M3 drift 4×, M2 gap 4×.

---

## 5. Why This Is Contamination, Not Prediction

- Structural-break detectors (M4 CUSUM, M3 drift) align precisely with ingestion boundaries between alien sub-series — not with any change in the lottery draw mechanism.
- Forward-predictive methods (M5/M8/M9) return NULL on BIG_LOTTO even on the contaminated series (+0.49pp p=0.226 — not significant).
- **Anomaly is NOT predictor.** Per P245B §3.3 (BOCD layer): detected structural break → data-integrity audit first; only after contamination excluded can break be considered a bias candidate.
- BIG_LOTTO currently fails the data-integrity quarantine check; it cannot be used in any bias research until GATE_RED is resolved.

---

## 6. Risk Impact on BIG_LOTTO Analysis

| Analysis type | Risk from contamination |
|---|---|
| Frequency / hot-cold analysis | Inflated/deflated frequency for numbers 26–49 during alien eras |
| Temporal / rolling-window | Regime shifts are ingestion artifacts, not mechanism changes |
| Baseline computation | Random baseline over mixed-pool rows is biased |
| Randomness audit (NIST) | Structured non-randomness detected = contamination, not real bias |
| Walk-forward OOS | Crossing alien-era boundary leaks structural differences |

---

## 7. Recommended Type D Quarantine Plan

> **Planning only. No DB modification performed. Type D explicit human gate required for all phases.**

**Phase 1 — Backup**
```bash
cp lottery_api/data/lottery_v2.db backups/p246_big_lotto_quarantine_backup_$(date +%Y%m%d_%H%M%S).db
sha256sum backups/p246_big_lotto_quarantine_backup_*.db
```

**Phase 2 — Quarantine Move**
```sql
-- Requires Python-driven script for SMALL_POOL_ALIEN (number-content inspection)
-- SIM_HYPHEN:      draw LIKE '%-%'
-- DATE_FORMAT:     LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%'
-- SMALL_POOL:      max(json_each.value) <= 25  (per-row inspection, Python-driven)
```

**Phase 3 — Verify**
```sql
SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO';  -- expect ~2118
```
- Drift guard: replay rows must remain 94,924
- `PRAGMA integrity_check` → `ok`

**Phase 4 — Re-Audit**
- Re-run `python3 analysis/p246_big_lotto_data_integrity_audit.py`
- Expected: CANONICAL_PLAUSIBLE ≈2118, contamination families empty
- Gate reassignment: GATE_RED → GATE_CLOSED_RANDOM_COMPATIBLE (pending clean NIST-style re-audit)

---

## 8. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ respected — read-only mode=ro |
| No migration applied | ✅ plan only |
| No strategy promotion | ✅ respected |
| No betting advice | ✅ respected |
| No P(win) claim | ✅ contamination is not an edge |
| BIG_LOTTO GATE_RED | ✅ unchanged — remains in effect |
| Type D gate for quarantine | ✅ required — not authorized here |

**Final Classification:** `P246_BIG_LOTTO_DATA_INTEGRITY_AUDIT_COMPLETE_GATE_RED_CONFIRMED`
