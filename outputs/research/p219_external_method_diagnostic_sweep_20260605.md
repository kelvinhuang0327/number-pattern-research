# P219 — Ten-Method External Diagnostic Sweep (RESULTS + ADJUDICATION)

**Task ID:** P219 · **Date:** 2026-06-05 Asia/Taipei · **Type:** Read-only pre-registered diagnostic sweep.
**Pre-registration:** `p219_external_method_diagnostic_sweep_plan_20260605.md` (statistics/nulls/family fixed before OOS).
**Engine:** `analysis/p219_external_method_diagnostic_sweep.py` (pure stdlib; seed 20260605; read-only DB).
**Raw output:** `p219_external_method_diagnostic_sweep_20260605.json` (reproducible).

**Adjudicated final classification:** `P219_TEN_METHOD_SWEEP_PREDICTIVE_NULL_PLUS_BIG_LOTTO_DATA_CONTAMINATION_ARTIFACT`
> The raw engine label is `COMPLETE_WITH_CORRECTED_SIGNAL` (it mechanically reports that some tests survived Bonferroni/BH). **Adjudication: every surviving test is a non-predictive structural-break detector firing on a contaminated BIG_LOTTO series. Zero forward-predictive methods beat baseline on any game. For the user's goal — raise P(win) — the result is NULL.**

---

## 1. Executive summary

[Confirmed] Ran all **10 pre-registered method families × 5 games = 44 multiplicity-corrected tests**, statistical unit = distinct real draws, all p-values Monte-Carlo/permutation empirical.

[Confirmed] **The three forward-predictive families are NULL on every game:**

| Family | DAILY_539 | BIG_LOTTO | POWER_LOTTO | 3_STAR | 4_STAR |
|---|---|---|---|---|---|
| M5 Dirichlet top-k OOS edge | −1.70pp (p=0.998) | +0.49pp (p=0.226) | −0.06pp (p=0.538) | — | — |
| M8 frequency-generator OOS edge | −1.70pp (p=0.995) | +0.49pp (p=0.207) | −0.06pp (p=0.534) | +0.0pp (p=0.491) | −0.30pp (p=0.681) |
| M9 conformal set-size reduction | −0.026 (p=0.998) | −0.020 (p=0.983) | −0.020 (p=0.965) | — | — |

No predictive method beat its random baseline; conformal sets were **larger** than the trivial set (negative "reduction"). This reproduces L82/L91/P178A and P236A.

[Confirmed] **The only Bonferroni/BH survivors are all on BIG_LOTTO** (M1 markov, M4 changepoint — Bonferroni; M2 gap, M3 drift, M6 entropy+compression — BH), plus one weak `DAILY_539:M3_drift` (BH-only, Bonferroni-FAIL). **All are non-predictive structural-break / heterogeneity detectors, pre-registered as "anomaly ≠ predictor."**

[Confirmed] **Root cause = data contamination, not a lottery bias.** The BIG_LOTTO `draws` table aggregates **≥3 distinct sources** under one label (§4). The structural-break detectors correctly fired on a discontinuous *data record*; they say nothing about the next draw's numbers.

[Confirmed] **Bonus finding (high value):** BIG_LOTTO stored data is ~90% non-canonical (§4) — a real **data-integrity issue** worth fixing independently of prediction.

**Bottom line: no external method raises P(win). The sweep is predictive-NULL. The "signal" is a data bug, which P219 caught.**

---

## 2. What ran (pre-registered family)

10 families (M1 Markov/consecutive-dependency, M2 gap/waiting-time, M3 rolling-drift, M4 change-point/CUSUM, M5 Bayesian-Dirichlet predictive, M6 entropy+compression, M7 spectral/periodogram, M8 permutation-model-score, M9 conformal calibration, M10 feature-bottleneck). Family size **m=44**; **Bonferroni α=0.05/44=0.00114**; BH-FDR at α=0.05. Cheap O(N) methods at B=2000 (Bonferroni-capable: p-floor 1/2001<α); M3/M7/M2/M6/M9 at B=400–800 (B-capped — flagged; none of the *predictive* ones approached significance so capping is immaterial).

## 3. Forward-predictive verdict (the user's actual goal)

[Confirmed] On **clean, stationary games** (DAILY_539, POWER_LOTTO, 3_STAR, 4_STAR) and even on contaminated BIG_LOTTO, walk-forward OOS (≥500 draws, expanding window, no future leakage) shows **no family beats baseline**:
- Best observed predictive edge anywhere: BIG_LOTTO +0.49pp (p=0.226) — and that is *on contaminated data*; not significant, not corrected, not exploitable.
- DAILY_539/POWER predictive edges are **negative** (selective/top-k frequency loses to flat baseline — consistent with L101 unconditional-dilution).
- Conformal (M9): the calibrated prediction set is **larger** than the trivial set at 80% coverage on every game → there is no score that shrinks the candidate set while preserving coverage → no exploitable structure.

## 4. Adjudication of the BIG_LOTTO "corrected signals" — proven data contamination

BIG_LOTTO `draws` = **22,238 rows** but only **~2,113 are plausible real 6/49** (matches the canonical "≈2,118 draws" on record). The rest:

| Sub-series | Rows | Signature | Identifiable by |
|---|---|---|---|
| Simulation artifacts | **19,100** | composite IDs `103000009-01 … -100` (100 variants/draw) | hyphen in `draw` (excluded at load) |
| Date-format alien game | **375** | IDs `20090727…20101231`; sum **74.7 ± 2.4**, max-number **≤24** | 8-digit ID starting `20` |
| Small-pool alien block | **~650** | 2011–2014; max-number **≤25**, mean draw-sum dips to ~100 (vs ~148 real) | max(numbers)≤25 (heuristic; 23.5% of "clean serial" vs 1.3% chance) |

**Mechanism** (each flagged statistic explained, none predictive):
- **M4 CUSUM = 761 (11× null):** draw-sum jumps between ~75/~100 (alien) and ~148 (real) → giant level shifts. Removing the 375 date rows leaves CUSUM=760 (the 650-row 2011–2014 block remains) — confirming a *second* contaminating source.
- **M3 drift 4× / M2 gap 4× / M6 low-entropy & high-compressibility:** during alien blocks numbers 25–49 are absent → window frequencies, gaps, and entropy all break.
- **M1 overlap 0.99 vs 0.81:** chronologically-contiguous alien blocks share their restricted number set; order-shuffle mixes eras → lower overlap.

**Control — DAILY_539 is clean and stationary:** flat draw-sum (~100) and max-number (~33) across all 10 chronological blocks (2007–2026); 2.6% of draws have max≤20, matching the 5/39 chance rate (2.7%). Its lone `M3_drift` flag is 1.2× null, **fails Bonferroni**, and is uncorroborated (M1 p=0.62, M4 p=0.30) → borderline BH false positive, not structure. This proves the methods do **not** manufacture signals on clean data — they fired on BIG_LOTTO specifically because BIG_LOTTO is contaminated.

## 5. Feature-bottleneck report (M10 — why no edge exists)

[Confirmed] Mutual information between the strongest candidate feature (trailing-50-draw number frequency) and the next-draw hit outcome:

| Game | MI (bits) | % of per-number outcome entropy | Min detectable edge @N (power 0.8) |
|---|---|---|---|
| DAILY_539 | 8.8e-06 | 0.0016% | 1.87pp |
| BIG_LOTTO (contaminated) | 9.6e-03 | 1.79% | 1.68pp |
| POWER_LOTTO | 1.6e-05 | 0.0026% | 1.86pp |
| 3_STAR / 4_STAR | ~0 | ~0 | 2.17 / 1.88pp |

The feature→outcome channel carries **essentially zero bits** on clean games. BIG_LOTTO's 1.79% is an inflated artifact of the same contamination (the model "learns" the alien-block frequency regime). Even that is below the min-detectable-edge floor. **There is no information bottleneck to widen — the channel is empty.** This generalizes L91's signal-strength estimate to all five games and all ten method families.

## 6. Honest economics & governance

- [Confirmed] All games remain deeply −EV; ruin_prob = 1.000 (L99). Nothing here is betting advice or a strategy.
- [Confirmed] Read-only: wrote only this report, the plan, the engine, and the test. **No DB / registry / production / runtime write. No strategy promotion. No P211 restart.** Branch is a dev worktree (not main).
- [Confirmed] Statistical unit = distinct real draws; BIG_LOTTO simulation rows excluded at load.
- [Confirmed] Multiplicity corrected (Bonferroni + BH over m=44). Pre-registration honored (P221F).

## 7. Verification

| Check | Value |
|---|---|
| Engine run | exit 0; JSON written; seed 20260605 |
| Test suite | `tests/test_p219_external_method_diagnostic_sweep.py` — **10/10 PASS** (false-positive control, injected-bias power, Bonferroni⊆BH, reproducibility, sim-row exclusion) |
| Contamination proof | reproduced read-only (clean-set re-run + block trajectory + 539 control) |
| DB writes | 0 (read-only `mode=ro`) |
| Predictive families | NULL on all 5 games |

## 8. Recommendation

| Question | Answer |
|---|---|
| Did any external method raise P(win)? | **NO** — predictive-NULL on all games (reproduces L82/L91/P178A/P236A) |
| Are the BIG_LOTTO "signals" real/exploitable? | **NO** — data-contamination artifacts (≥3 mixed sources), non-predictive break detectors |
| Net-new actionable finding? | **YES (data-integrity, not prediction):** BIG_LOTTO `draws` is ~90% non-canonical; a read-only audit + quarantine plan is warranted (separate Type B/D task; this task does not modify the DB) |
| Reopen prediction research? | **NO** — gated on the NIST tripwire (P238B = YELLOW, observation-only) + ≥300 new clean draws (P224B), not on this sweep |

**Adjudicated final classification:** `P219_TEN_METHOD_SWEEP_PREDICTIVE_NULL_PLUS_BIG_LOTTO_DATA_CONTAMINATION_ARTIFACT`
