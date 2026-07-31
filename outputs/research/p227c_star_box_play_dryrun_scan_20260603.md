# P227C — 3_STAR / 4_STAR Box-Play Dry-Run Scan with Power Gate

**Date:** 2026-06-03
**Task:** `P227C_STAR_BOX_PLAY_DRYRUN_SCAN_COMPLETE`
**Status:** COMPLETE / READ-ONLY DRY-RUN
**Final Classification:** `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL`
**Authorized by:** User explicit task prompt 2026-06-03

This report covers the P227C read-only dry-run scan. No DB writes, no replay rows created, no registry changes, no production changes.

---

## Phase 0 Verification

| Check | Expected | Actual | Result |
|---|---|---|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | confirmed | PASS |
| branch | `main` → `p227c-star-box-play-dryrun-scan` | confirmed | PASS |
| HEAD == origin/main | match | `b47a806` == `b47a806` | PASS |
| staged files | 0 | 0 | PASS |
| total replay rows | 94,924 | 94,924 | PASS |
| BIG_LOTTO rows | 24,140 | 24,140 | PASS |
| DAILY_539 rows | 34,680 | 34,680 | PASS |
| POWER_LOTTO rows | 36,104 | 36,104 | PASS |
| 3_STAR draw rows | 4,179 | 4,179 | PASS |
| 4_STAR draw rows | 2,922 | 2,922 | PASS |
| 3_STAR/4_STAR replay rows | 0 | 0 | PASS |
| bet_index nulls | 0 | 0 | PASS |
| duplicate replay keys | 0 | 0 | PASS |
| PRAGMA integrity_check | `ok` | `ok` | PASS |
| drift guard | PASS | PASS | PASS |
| P227B files tracked | 2 | 2 | PASS |

---

## Pre-Registration Record

| Item | Value |
|---|---|
| Lotteries | 3_STAR, 4_STAR |
| Mode | box-play exact match only |
| Straight-play | BLOCKED (sorted DB storage, positional order lost) |
| Windows short | 100, 125, 150 |
| Windows mid | 500, 750, 1000 |
| All-history | reference only |
| Feature families | F1 hot, F2 cold, F3 midfreq short/mid, F4 midfreq mid/all, F5 overdue, F6 sum band, F7 high/low, F8 odd/even, F9 span, F10 consensus |
| Total hypotheses | 2 × 10 × 6 = **120** |
| Bonferroni threshold | 0.05 / 120 = **0.000417** |
| Significance level | α = 0.05 (pre-registered) |
| OOS split | 50% warm-up / 50% walk-forward evaluation |
| Power gate threshold | 3_STAR ≥ 10,000 OOS draws; 4_STAR ≥ 17,000 OOS draws |
| NULL accepted | Yes |
| Metric | `star_box_exact_match` via P227B `star_calculate_box_score` |

---

## Statistical Power Warning

Both lotteries are **UNDERPOWERED** for this scan. Current draw counts fall far short of the minimum needed to reliably detect a 20% relative lift:

| Lottery | Available draws | OOS draws (~50%) | Exact hits expected (baseline) | Draws needed (80% power, 20% lift, α=0.05) |
|---|---|---|---|---|
| 3_STAR | 4,179 | ~2,090 | ~17 | **~10,000** |
| 4_STAR | 2,922 | ~1,461 | ~7 | **~17,000** |

Any positive signal detected in this scan is classified as `WEAK_OBSERVATION_UNDERPOWERED` or `UNDERPOWERED_NO_SIGNAL` — never as deployable.

---

## Scan Results

### 3_STAR

| Metric | Value |
|---|---|
| n_draws | 4,179 |
| baseline (no-repeat C(10,3)) | 1/120 ≈ **0.00833** |
| n_hypotheses_tested | 60 |
| n_positive_lift | 29 / 60 |
| **Bonferroni passes** | **0** |
| **BH-FDR passes** | **1** |
| Best feature/window | `F7_high_low / w750` |
| Best lift | **+0.00650** (hit rate 0.01483 vs baseline 0.00833) |
| Best p-value | **0.0008** |
| Best power status | **UNDERPOWERED** (n_oos=2,090 < 10,000) |
| **Overall classification** | `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL` |

**Top 5 features by lift:**

| Feature | Window | Lift | p-value | Bonf | BH-FDR | Classification |
|---|---|---|---|---|---|---|
| F7_high_low | w750 | +0.00650 | 0.0008 | ❌ | ✅ | WEAK_OBSERVATION_UNDERPOWERED |
| F9_span | w750 | +0.00411 | 0.0259 | ❌ | ❌ | WEAK_OBSERVATION_UNDERPOWERED |
| F1_hot | w750 | +0.00363 | 0.0442 | ❌ | ❌ | WEAK_OBSERVATION_UNDERPOWERED |
| F8_odd_even | w750 | +0.00315 | 0.0716 | ❌ | ❌ | UNDERPOWERED_NO_SIGNAL |
| F5_overdue | w100 | +0.00171 | 0.2291 | ❌ | ❌ | UNDERPOWERED_NO_SIGNAL |

**3_STAR conclusion:** `F7_high_low/w750` passes BH-FDR but NOT Bonferroni. OOS sample size (n_oos=2,090) is far below the 10,000-draw power threshold. This result is classified as `WEAK_OBSERVATION_UNDERPOWERED` — **not a deployable signal**. The apparent positive lift may be noise.

### 4_STAR

| Metric | Value |
|---|---|
| n_draws | 2,922 |
| baseline (no-repeat C(10,4)) | 1/210 ≈ **0.00476** |
| n_hypotheses_tested | 60 |
| n_positive_lift | 25 / 60 |
| **Bonferroni passes** | **0** |
| **BH-FDR passes** | **0** |
| Best feature/window | `F7_high_low / w100` |
| Best lift | **+0.00345** |
| Best p-value | **0.0421** |
| Best power status | **UNDERPOWERED** |
| **Overall classification** | `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL` |

**4_STAR conclusion:** No feature passes BH-FDR or Bonferroni. Consistent with `UNDERPOWERED_NO_SIGNAL`.

---

## Overall Conclusions

### Final Classification: `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL`

1. **Both lotteries: Bonferroni = 0.** No feature/window combination passes the pre-registered Bonferroni threshold of 0.000417.
2. **3_STAR: BH-FDR = 1 (F7_high_low/w750, p=0.0008).** This single BH-FDR pass is in the UNDERPOWERED regime (n_oos=2,090 << 10,000). The effect size (lift=+0.65 × baseline) is plausible but not confirmed.
3. **4_STAR: BH-FDR = 0.** No signal.
4. **Honest prior: NULL/lean-null.** These results are consistent with the expectation from P226/P227A that both lotteries are statistically underpowered.
5. **F7_high_low (high/low composition) is the only feature with a trend.** This should be noted as a candidate for future re-evaluation **if and only if** additional draw data becomes available (target: ≥10,000 draws for 3_STAR).

### What This Scan Does NOT Mean

- ❌ No strategy is deployable.
- ❌ No hit-rate improvement is confirmed.
- ❌ No registry write, production write, or recommendation-logic change is authorized.
- ❌ The BH-FDR pass for F7_high_low does not constitute a validated edge.

### What This Scan DOES Mean

- ✅ Box-play semantics (P227B module) work correctly on real DB data.
- ✅ The P221F anti-overfit gate was applied: pre-registered features, windows, baselines, Bonferroni/BH-FDR, power analysis, walk-forward OOS.
- ✅ NULL / UNDERPOWERED is a valid, successful outcome.
- ✅ F7_high_low/w750 is a weak candidate for future monitoring if data grows.
- ✅ DB unchanged: 94,924 replay rows, 0 star replay rows.

---

## Straight-Play: Still Blocked

Straight-play requires per-digit positional order. Current DB stores draws as sorted arrays. Re-ingestion from a raw positional source remains a separate, unauthorized task.

---

## Test Results

**69/69 PASS** — P227B + P227C targeted tests combined.

| Test file | Tests | Result |
|---|---|---|
| `test_p227b_star_box_play_semantics.py` | 42 | PASS |
| `test_p227c_star_box_play_dryrun_scan.py` | 27 | PASS |
| **Total** | **69** | **ALL PASS** |

---

## DB Unchanged (Post-Scan)

| Check | Before | After | Status |
|---|---|---|---|
| Total replay rows | 94,924 | 94,924 | UNCHANGED |
| 3_STAR replay rows | 0 | 0 | UNCHANGED |
| 4_STAR replay rows | 0 | 0 | UNCHANGED |
| PRAGMA integrity_check | `ok` | `ok` | PASS |
| Drift guard | PASS | PASS | PASS |

---

## Required Completion Check

1. **是否真的完成:** YES — scan complete, 120 hypotheses tested, power gate applied, artifacts written.
2. **測試結果:** **69/69 PASS** (P227B 42 + P227C 27). Drift guard PASS. Full pytest suite NOT RUN.
3. **仍卡住的唯一問題:** Both lotteries UNDERPOWERED; 3_STAR needs ~10,000 draws (has 4,179), 4_STAR needs ~17,000 (has 2,922). Straight-play still blocked.
4. **修改檔案清單:**
   - `scripts/p227c_star_box_play_dryrun_scan.py` (new)
   - `tests/test_p227c_star_box_play_dryrun_scan.py` (new)
   - `outputs/research/p227c_star_box_play_dryrun_scan_20260603.json` (new)
   - `outputs/research/p227c_star_box_play_dryrun_scan_20260603.md` (new)
5. **staged / commit / push:** awaiting staging.
6. **是否允許進入下一輪:** YES — future work (if authorized) would require ~5× more 3_STAR draws or re-ingestion with positional order.
7. **Final Classification:** `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL`
