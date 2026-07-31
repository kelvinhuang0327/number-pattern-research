# P246K — Canonical BIG_LOTTO NIST/Randomness Re-audit

**Task ID:** P246K · **Date:** 2026-06-06 · **Type:** Read-only canonical randomness re-audit.
**Input population:** CANONICAL_MAIN_DRAW only (2,113 rows, via `get_canonical_draws("BIG_LOTTO")`)
**No DB write. No prediction claim. No strategy promotion.**
**Final Classification:** `P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE`

> **Key result: 5/5 randomness tests GREEN on canonical population. P238B YELLOW was contamination-driven.** The canonical 6/49 BIG_LOTTO main draws are consistent with a fair random process. This does NOT unlock predictive research — randomness ≠ exploitable signal.

---

## 1. Why This Canonical Re-audit Was Needed

P238B ran on all 22,238 raw BIG_LOTTO rows (mixed population) and produced `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`. P246B-J established that 19,100 of those rows were ADD_ON_PRIZE_EXCLUDED (add-on/special prize records) and ~1,025 were DATE_FORMAT_ALIEN + SMALL_POOL_ALIEN (rows with numbers inconsistent with 6/49 pool).

**Question:** Does the YELLOW observation persist when we audit the canonical 6/49 main-draw population only?

**Answer: No. All tests are GREEN on the canonical 2,113-row population.** The YELLOW was driven by the mixed-population contamination.

---

## 2. Population Definition and Counts

| Population | Count | Source |
|---|---|---|
| Raw total | 22,238 | `get_all_draws('BIG_LOTTO')` — includes all families |
| ADD_ON_PRIZE_EXCLUDED | 19,100 | Add-on/special prize records (valid, preserved) |
| DATE_FORMAT_ALIEN | 375 | Non-canonical format |
| SMALL_POOL_ALIEN | ~650 | Likely mislabeled game |
| **CANONICAL_MAIN_DRAW** | **2,113** | `get_canonical_draws('BIG_LOTTO')` — this audit's input |

**Exclusion verification:**
- Hyphenated IDs in canonical: **0** ✅
- Date-format alien IDs in canonical: **0** ✅
- max(numbers) ≤ 25 in canonical: **0** ✅ (all max numbers in range 26–49)

---

## 3. Comparison to P238B

| Aspect | P238B (raw) | P246K (canonical) |
|---|---|---|
| Sample size | 22,238 | 2,113 |
| Population | Mixed (all families) | CANONICAL_MAIN_DRAW only |
| Classification | YELLOW OBSERVATION_ONLY | **GREEN RANDOM_COMPATIBLE** |
| Corrected-significant | False | N/A — all GREEN |
| Date | 2026-06-04 | 2026-06-06 |

**P238B YELLOW is NOT confirmed on the canonical population.** It was a mixed-population artifact.

---

## 4. Audit Results

| Test | Statistic | p-value | Status |
|---|---|---|---|
| Draw-sum KS (vs normal) | KS=0.0222 | p=0.2458 | ✅ GREEN |
| Number frequency chi-square (49 balls) | χ²=40.46, df=48 | p=0.7720 | ✅ GREEN |
| Runs test (sum above/below mean) | z=-0.054 | p=0.9569 | ✅ GREEN |
| Ljung-Box autocorrelation (lag 10) | stat=10.32 | p=0.4129 | ✅ GREEN |
| Shannon entropy (normalized) | 0.999584 | — | ✅ GREEN |

**Overall: 5/5 GREEN — canonical BIG_LOTTO draws are consistent with a fair random 6/49 process.**

### Key statistics
- Draw sum: mean=151.03, sd=32.19 (theoretical mean=150.0 for uniform 6/49)
- Number frequency: max=284, min=243, expected=258.7 — well within uniform range
- Shannon entropy: 5.6124 / max 5.6147 = 99.96% of maximum possible entropy

### Era stability (last 6 years)
| Year | N | Mean sum |
|---|---|---|
| 2021 | ~114 | ~150 |
| 2022 | 111 | 153.6 |
| 2023 | 114 | 151.0 |
| 2024 | 118 | 154.6 |
| 2025 | 114 | 149.3 |
| 2026 | 57 | 152.1 |

Stable sum distribution across years — no regime breaks on canonical data.

---

## 5. Gate Implication

**For randomness gating:**

✅ P238B YELLOW is superseded for canonical research gating. The canonical BIG_LOTTO population passes all randomness checks. It is consistent with a fair random 6/49 lottery.

**For predictive/bias research gate:**

❌ GREEN randomness ≠ exploitable signal. BIG_LOTTO predictive research remains blocked per:
- L91: 6 randomness tests all pass; MI=0.006 bits; all observed signals within noise (99th pct MC baseline)
- L90: BIG_LOTTO signal space exhausted — 7 signal families, zero pass p<0.05 on canonical data

**GATE_RED for predictive research remains in effect.** GREEN randomness is the expected baseline for a fair lottery — it confirms there is nothing exploitable, not that a signal was found.

**DB-level canonical separation (P247 Type D)** is still recommended to complete the architecture.

---

## 6. Limitations

- N=2,113 canonical draws. Power is sufficient for frequency tests but some serial-correlation tests have limited power at this N.
- SMALL_POOL_ALIEN were excluded by Python max(numbers)>25 filter — a small number of borderline rows may vary slightly by definition.
- No block-frequency or longest-run-of-ones NIST test was run (would require bit-stream encoding); Ljung-Box serves as a proxy for serial independence.

---

## 7. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No row deletion | ✅ confirmed |
| Add-on rows preserved | ✅ get_all_draws() still returns 22,238 |
| No prediction claim | ✅ GREEN randomness ≠ exploitable signal |
| No betting advice | ✅ confirmed |
| No strategy promotion | ✅ confirmed |
| No GATE_OPEN for predictive research | ✅ gate remains blocked per L91/L90 |
| DB-level separation (P247 Type D) | ✅ still recommended |

**ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are valid lottery-related records. They remain preserved and raw-accessible. They are excluded from canonical research due to population mismatch.**

**Final Classification:** `P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE`
