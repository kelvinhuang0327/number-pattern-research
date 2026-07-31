# P219 — Ten-Method External Diagnostic Sweep (PRE-REGISTRATION)

**Task ID:** P219
**Date:** 2026-06-05 Asia/Taipei
**Type:** Read-only, pre-registered diagnostic sweep. No DB/registry/production write, no strategy promotion, no betting advice, no predictability claim.
**Authorization:** User directed (2026-06-05) "import external methods, cost-no-object, try hard to raise prediction success rate," and selected running **all 10 method families** (the P219 menu) *after* being shown on record that (a) external scouting is already complete (P236A), (b) the one net-new external tool — NIST randomness audit — was already built and ran `YELLOW = no actionable bias` (P238B), and (c) no external method can raise P(win) on a fair-random draw (internal L91/L82/P178A + external NIST/academic literature).
**Pre-registration integrity (P221F):** every hypothesis, statistic, null model, window, and the multiple-testing family below is fixed in this file **before** any OOS statistic is computed. Results go in a separate report (`p219_external_method_diagnostic_sweep_20260605.{md,json}`).
**Honest expected outcome:** NULL across the board. The valuable deliverable is the **feature-bottleneck report** (Method 10) that explains *why* no family beats the random baseline. NULL is a complete, valid result.

---

## 0. Toolchain & reproducibility

- Pure Python **stdlib only** (`sqlite3`, `json`, `math`, `random`, `zlib`, `statistics`, `collections`). `numpy`/`scipy` are not installed; no dependency is added (minimal-impact).
- **All p-values are Monte-Carlo / permutation empirical p-values:** `p = (1 + #{stat_b ≥ stat_obs}) / (B + 1)` — consistent with L96 (Binomial-MC null) and L47 (shuffle p-floor). No analytic CDF is used.
- Fixed seed `SEED = 20260605`. B (replicates) declared per method below.
- DB opened **read-only**: `sqlite3.connect("file:<db>?mode=ro", uri=True)`. Zero writes.

## 1. Data universe (statistical unit = distinct REAL draws)

Verified read-only this session. **BIG_LOTTO excludes 19,100 simulation artifacts** (composite IDs `NNNNNNNNN-NN`, e.g. `103000009-01..-100`); only hyphen-free serial draws count.

| Game | Filter | Distinct draws | Structure | Random baseline (SSOT) |
|---|---|---|---|---|
| DAILY_539 | `lottery_type='DAILY_539'` | 5,879 | 5-of-39 | per-number 5/39=0.1282; M3+ hit rate per-bet |
| BIG_LOTTO | `='BIG_LOTTO' AND draw NOT LIKE '%-%'` | 3,138 | 6-of-49 | per-number 6/49=0.1224 |
| POWER_LOTTO | `='POWER_LOTTO'` | 1,916 | 6-of-38 (+1-of-8 special) | first-zone 6/38=0.1579; second-zone 1/8=0.125 |
| 3_STAR | `='3_STAR'` | 5,850 | 3 digits 0–9 (positional) | per-position-digit 1/10=0.10 |
| 4_STAR | `='4_STAR'` | 5,850 | 4 digits 0–9 (positional) | per-position-digit 1/10=0.10 |

Numbers parsed from `numbers` (sorted) and, for star games, `numbers_positional` (draw order) via `json.loads`. Draw ordering: `CAST(draw AS INTEGER)` ascending (DB rule; TEXT column). For BIG_LOTTO mixed-length serials this orders chronologically within the hyphen-free set.

## 2. The 10 method families (fixed statistics & nulls)

For each: **H0 = fair random draws** (game-appropriate). A family "fires" only if it passes the §3 gate. Prior project results noted to avoid mis-reading a re-tread as discovery.

| # | Family | Statistic (pre-declared) | Null model | Games | B | Prior result |
|---|---|---|---|---|---|---|
| M1 | **Markov / consecutive dependency** | number games: mean \|D_t ∩ D_{t+1}\| over consecutive pairs; digit games: per-position digit-match rate t→t+1 | permute draw order | all | 1000 | L80 假性自相關, L103 Lag-1±1 FAST_REJECT |
| M2 | **Gap / waiting-time** | pooled gap-distribution dispersion index (var/mean) vs random | simulate uniform draws | 539/BIG/POWER | 1000 | SGP V3–V11 absorbed by freq window |
| M3 | **Rolling-window drift** | max over rolling W-windows of L1(window-freq, global-freq) | permute draw order | all | 500 | RSM DriftDetector / PSI; overfit-prone |
| M4 | **Change-point** | max CUSUM of draw-level scalar (normalized draw sum / digit mean) | permute draw order | all | 1000 | P238B NIST audit = YELLOW (no actionable bias) |
| M5 | **Bayesian smoothing (predictive)** | walk-forward OOS hit-rate of top-k Dirichlet-posterior numbers vs baseline | Binomial(baseline) MC | 539/BIG/POWER | 1000 | P236A S5 GRAYLIST benchmark-only |
| M6 | **Entropy / compression** | Shannon entropy of freq dist + zlib compression ratio of draw stream | simulate uniform draws | all | 1000 | L91 Shannon+PE PASS random |
| M7 | **Spectral / periodogram** | max Schuster-periodogram power of draw-level scalar over periods 2..min(60,T/4) | permute draw order | all | 1000 | Fourier heavily tested; 539 REJECT, BIG +0.414% noise |
| M8 | **Permutation model score** | frequency-generator OOS hit-rate vs Binomial(baseline) MC null (L96 fix) | Binomial(baseline) MC | 539/BIG/POWER | 1000 | standard gate |
| M9 | **Conformal calibration** | split-conformal coverage error + set-size vs trivial for a freq-score predictor | MC coverage band | 539/BIG/POWER | 500 | net-new framing |
| M10 | **Feature-bottleneck report** | per-feature MI (recent-freq/gap/parity → next-hit) + min-detectable-edge power calc | (synthesis; analytic + the above) | all | — | L91 signal-strength estimation, generalized |

Walk-forward (M5/M8/M9): expanding train window, OOS tail; OOS unit = distinct draws; require usable OOS length (≥500 where N permits, else documented). No training on future draws (data-leakage-prevention).

## 3. Mandatory validation gate (a family may claim a real signal ONLY if all hold)

Adopted from P236A §6 / CLAUDE.md / lessons:

1. **Pre-registration (P221F):** statistic & null fixed in this file before OOS. ✓ (this doc)
2. **Baseline SSOT:** the §1 per-game random baseline is the reference; stated explicitly.
3. **Multiple-testing correction:** the family = every (method × game) test below + walk-forward sub-tests. Apply **Bonferroni** (α=0.05/m) **and BH-FDR** across the full family. m is fixed by §2 (≈ 10 methods × applicable games). A finding must survive **both** to be "corrected-significant."
4. **Permutation/MC p < 0.05 corrected.** Uncorrected p<0.05 alone = `EXPLORATORY_WEAK_UNCONFIRMED`, never promoted (cf. P214C).
5. **Direction/consistency:** for predictive families (M5/M8), three-window spirit (short/mid/long OOS) must be consistent; a single-window blip does not qualify.
6. **Coverage-normalized** at fixed bet count; no geometric-benefit trap (L37).
7. **Honest economics:** even a surviving signal is reported with the standing fact that all games remain −EV, ruin_prob=1.000 (L99). No betting advice.
8. **NULL = success.** In-sample structure is never claimed generalizable.

## 4. Boundaries (STOP if violated)

- Read-only. Writes limited to: this plan, the report `.md`/`.json`, the engine `analysis/p219_*.py`, the test `tests/test_p219_*.py`. **No DB / registry / production / runtime write.** No strategy promotion. No monitoring job. No betting advice. No P211 restart.
- Branch is a dev worktree branch (NOT main; repo hook blocks main writes).
- Statistical unit = distinct real draws (BIG_LOTTO hyphen-free). Never replay rows.
- Multiplicity correction is mandatory — 10 methods × 5 games will manufacture ~2–3 uncorrected p<0.05 by chance alone; only corrected survivors count.

## 5. Deliverables

1. `analysis/p219_external_method_diagnostic_sweep.py` — read-only engine.
2. `outputs/research/p219_external_method_diagnostic_sweep_20260605.{md,json}` — results + Bonferroni/BH table + **feature-bottleneck report**.
3. `tests/test_p219_external_method_diagnostic_sweep.py` — false-positive control (random input → high p), power check (injected-bias input → low p), correction monotonicity, seed reproducibility, simulated-row exclusion.

**Final classification (to be set by report):** `P219_TEN_METHOD_DIAGNOSTIC_SWEEP_<RESULT>` where RESULT ∈ {COMPLETE_NULL, COMPLETE_WITH_EXPLORATORY_WEAK, COMPLETE_WITH_CORRECTED_SIGNAL}.
