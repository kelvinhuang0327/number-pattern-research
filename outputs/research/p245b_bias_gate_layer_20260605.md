# P245B — Corrected Bias Gate Layer

**Task ID:** P245B · **Date:** 2026-06-05 Asia/Taipei · **Type:** Read-only design artifact. No build, no code execution, no DB write, no registry mutation, no production change, no strategy promotion, no betting advice.
**Final Classification:** `P245B_CORRECTED_BIAS_GATE_LAYER_DESIGN_COMPLETE`

---

## 0. Correction Notice

[Confirmed] **P245A does not exist.** The prior handoff that referenced `p245a_external_predictive_method_scouting_20260605.*` was stale/mislabeled. P245B is built directly on verified, committed prior evidence: **P236A + P237C + P238B + P219**. No P245A dependency exists.

---

## 1. Executive Summary

[Confirmed] **Fair-random lotteries have no validated external method that raises P(win).** This is established by: L82 (DAILY_539 signal space exhausted), L91 (BIG_LOTTO indistinguishable from random, 6 tests), P178A (POWER_LOTTO 17 candidates NULL), P236A (external-method scouting: 7/8 methods already owned, 1 net-new — the randomness audit — is a tripwire, not a predictor), and P219 (10-method sweep: forward-predictive families NULL on all 5 games, MI ≈ 0 bits).

[Confirmed] **Anomaly detection is not prediction.** The NIST-style randomness audit (P237C design → P238B artifact, YELLOW = no actionable bias) and the P219 contamination-detector results confirm that structural breaks and frequency anomalies in the draw record reflect *data-pipeline events* (machine changes, contamination) rather than predictable patterns. Detecting an anomaly does not make the next draw foreseeable.

This document defines a **bias gate** that governs the only legitimate pathway from anomaly observation to (carefully gated) bias research — while maintaining a hard firewall against prediction claims, betting advice, strategy promotion, or production changes.

---

## 2. Dependency Evidence (verified from actual files)

| Artifact | File | Classification | Key Finding |
|---|---|---|---|
| **P236A** | `p236a_…_20260604.md` | `FALSIFICATION_AND_DIAGNOSTICS_ONLY` | No external method raises P(win); NIST-audit is sole net-new diagnostic |
| **P237C** | `p237c_…_20260604.md` | `NIST_RANDOMNESS_AUDIT_TRIPWIRE_DESIGN_READY` | Drew architecture for draw-level randomness audit; defines GREEN/YELLOW/ORANGE/RED taxonomy |
| **P238B** | `p238b_…_20260604.{md,json}` | `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY` | NIST battery ran; YELLOW = faint observation, no actionable bias, no gate breach |
| **P219** | `p219_…_20260605.{md,json}` | `PREDICTIVE_NULL_PLUS_BIG_LOTTO_DATA_CONTAMINATION_ARTIFACT` | 10-method NULL; BIG_LOTTO fires only on contamination (simulation + alien rows), not real bias |

**P245A: ABSENT** — not a dependency; not required; not assumed.

---

## 3. Gate Architecture

### 3.1 Five Gate States

```
GATE_CLOSED_RANDOM_COMPATIBLE    — expected steady state; no anomaly; no action
GATE_YELLOW_OBSERVATION_ONLY     — weak anomaly, below threshold; log only (current state per P238B)
GATE_RED_DATA_CONTAMINATION      — anomaly attributable to data issue; block research; quarantine first
GATE_OPEN_BIAS_RESEARCH_ALLOWED  — all evidence thresholds met; authorize read-only research only
GATE_INVALID_INSUFFICIENT_DATA   — data not ready; pre-registration not done; no gate assignable
```

**Current state (2026-06-05):**
- DAILY_539 / POWER_LOTTO / 3_STAR / 4_STAR → `GATE_YELLOW_OBSERVATION_ONLY` (P238B)
- BIG_LOTTO → `GATE_RED_DATA_CONTAMINATION` (P219: ~90% non-canonical rows)

### 3.2 Sequential E-Value Layer (always-valid monitoring)

An **e-value** is a likelihood ratio (or a composite thereof) that can be evaluated at any stopping time without inflating the false-positive rate. Unlike p-values, e-values are valid under optional stopping — the core benefit for persistent lottery monitoring.

**Pre-registration requirements (must be filed before monitoring begins):**
1. Feature — exactly what is monitored (e.g. "DAILY_539 number frequency in zone Z1, rolling W=200 draws")
2. Window — rolling vs expanding; start draw T₀
3. Null — explicit distribution (e.g. Binomial(5/39) per number per draw)
4. Alternative — direction and hypothesized magnitude
5. Stopping rule — threshold K (default **K=100** for confirmatory evidence; K=20 for replication)
6. Family — all (game × feature × window) combinations to be monitored simultaneously
7. Reset conditions — contamination detected, draw-format schema change, operator confirms mechanism change

**Threshold rationale:** K=100 ≈ p<0.01 under a well-specified point alternative. Conservative given the project's history of NULLs (L82/L91/P178A/P219) and the prior confirmed YELLOW not breaching any threshold.

**Cooldown after contamination:** When `GATE_RED_DATA_CONTAMINATION` is set for a game, reset that game's e-value accumulator. Resume only after a clean data-integrity audit. Contamination can artificially accumulate e-value (P219 BIG_LOTTO: contaminated series manufactured all corrected-significant signals).

### 3.3 Bayesian Online Changepoint Detection (BOCD) Layer

**Purpose:** Detect regime shifts in draw-level summary statistics. A detected changepoint means *inspect the data pipeline at that timestamp*, not *predict the next draw*.

**Monitored scalars (pre-declared):**
- Draw sum (mean and rolling variance per W-draw window)
- Zone/frequency L1 distance from baseline (rolling)
- Per-position digit frequency entropy (3_STAR / 4_STAR)

**Hazard function:** Pre-declared geometric hazard with rate parameter λ (baseline: λ=1/T_total as flat prior; must be stated in pre-registration).

**First action on changepoint suspicion: data-integrity audit.** The P219 BIG_LOTTO example is the template: the CUSUM changepoint fired at exactly the boundary between alien sub-series (sum ~75 → ~148). This was data contamination, not a real bias. *Every* BOCD alarm must be answered first with a contamination check. Only if contamination is excluded does the changepoint become a bias candidate.

**Anomaly is NOT prediction.** A confirmed structural break in the draw record justifies investigation of data provenance, not deployment of a strategy.

**Minimum sample:** ≥500 draws per game after the detected break point to run walk-forward verification; ≥1500 preferred (three-window standard).

### 3.4 Multiple-Testing Correction

[Confirmed] Mandatory. Applies across: **games × features × windows × methods × repeated looks**.

| Correction | Use |
|---|---|
| **Bonferroni (α/m)** | Confirmatory gate decisions — a finding must survive Bonferroni to advance the gate state |
| **BH-FDR (α, sorted)** | Exploratory context reporting only — BH-only findings are `EXPLORATORY_WEAK_UNCONFIRMED` and must not be promoted |
| **E-value family** | Pre-registered family corrects for simultaneous monitoring via product e-value or Bonferroni across family |

Precedents: P214C (0/7 Bonferroni-significant; uncorrected-weak p≈0.025 not promoted). P219 (44 tests; BIG_LOTTO BH-survivors = contamination artifact). No uncorrected finding may ever advance a gate state.

Minimum B for Monte-Carlo nulls: **B=2000** (Bonferroni-capable p-floor 1/2001 < α=0.05/44). L96 fix: use Binomial(baseline) MC null — label-shuffle preserves mean and gives p=1.0 (broken test).

### 3.5 Data-Integrity Quarantine

[Confirmed] Required before any signal review. Checklist (must all PASS before a game's e-value or BOCD results are considered):

| Check | Method | BIG_LOTTO P219 Status |
|---|---|---|
| Mixed lottery_type | Confirm `lottery_type` column matches declared game | RED (alien rows mislabeled) |
| Simulated rows | Exclude `draw LIKE '%-%'` composite IDs | RED (19,100 sim rows) |
| Date-style vs serial IDs | 8-digit IDs starting `20` ≠ serial draw IDs | RED (375 rows, sum~75, max≤24) |
| Impossible number ranges | For 6/49: >2% of draws with max(numbers)≤25 is anomalous (expected ~1.3%) | RED (23.5% of "clean" serial) |
| Small-pool sub-series | Chronological block mean draw-sum must be stable | RED (dip to ~100 in 2011–2014 block) |
| Duplicate draw IDs | COUNT(*) == COUNT(DISTINCT draw) | OK |
| Lifecycle leakage | Statistical unit = distinct draws, not replay rows | Must check per-game |
| Positional schema mismatch | 3_STAR/4_STAR: numbers_positional must be non-null for positional analysis | Must check |
| Canonical count match | Loaded N ≈ governance-recorded draw count | RED (3,138 vs canonical ≈2,118; extra = contamination) |

A game in `GATE_RED_DATA_CONTAMINATION` must not be included in any bias research until a Type-D-authorized DB cleanup produces a clean re-audit pass.

---

## 4. Future Research Unlock Conditions (GATE_OPEN)

**ALL** of the following must be simultaneously met. Partial compliance is insufficient.

1. **E-value K ≥ 100** on a pre-registered (game, feature, window) triple
2. **BOCD changepoint posterior** confirms a break at the same temporal location as the e-value rise
3. **Data-integrity audit returns clean** for the affected game — no contamination, schema mismatch, or alien subseries
4. **≥500 clean OOS draws** after the detected changepoint (walk-forward verification possible)
5. **Independent replication**: anomaly confirmed in a second non-overlapping draw window
6. **Bonferroni correction** across the pre-registered family — finding survives at α/m
7. **Explicit human authorization** for a follow-on read-only research task
8. **Pre-registration of follow-on task** filed before any OOS data is touched

**Current status:** No condition is met for any game. P238B = YELLOW (below K threshold). P219 = predictive NULL + BIG_LOTTO GATE_RED. All games: ruin_prob = 1.000, all EV negative.

---

## 5. Promotion Boundary (hard firewall)

Even `GATE_OPEN_BIAS_RESEARCH_ALLOWED` does **NOT** authorize:
- Production recommendation changes
- Betting advice of any kind
- Registry promotion or mutation
- DB writes (outside an explicitly authorized Type D cleanup)
- Candidate ranking changes
- Controlled apply / deployment
- Any claim that P(win) can be improved

`GATE_OPEN` authorizes **only**: a future separately authorized read-only research task, which must itself pass the full §6 validation rubric (P221F pre-registration, three-window, permutation, McNemar, walk-forward OOS ≥500 draws, multiple-testing corrected).

---

## 6. Validation Rubric for Any Future Research Triggered by Gate Open

(Inherited from P236A §6 / CLAUDE.md / project lessons)

1. Pre-registration (P221F): hypothesis, windows, statistic fixed before OOS
2. Baseline SSOT: game-appropriate random baseline stated explicitly
3. Three-window validation (150/500/1500): all ROI > baseline
4. Permutation test p < 0.05 using Binomial(baseline) MC null (L96 fix)
5. Walk-forward OOS (≥500 draws; no training on future data)
6. Multiple-testing correction (Bonferroni + BH) across candidates × windows × thresholds
7. McNemar vs incumbent (replacement requires p < 0.05; L48/L61)
8. Coverage-normalized comparison at fixed bet count (no geometric-benefit trap; L37)
9. Sharpe > 0 AND honest economic note (all games −EV; ruin_prob=1.000; L99)
10. Reproducibility: fixed seed, data snapshot, version tag

NULL = success. In-sample improvement may never be claimed as generalizable.

---

## 7. Governance

| Rule | Status |
|---|---|
| No prediction claim | respected — anomaly detection is not prediction |
| No betting advice | respected |
| No P(win) improvement claim | respected — fair-random; L82/L91/P178A/P219 confirmed |
| No strategy promotion | respected |
| No DB write | respected — read-only design artifact only |
| No registry mutation | respected |
| No production recommendation change | respected |
| P211 hold | unchanged — P211R = HISTORICAL_ARTIFACT; P245B does not restart it |
| P238B YELLOW | unchanged — observation-only; this gate formalizes its taxonomy |
| BIG_LOTTO | GATE_RED_DATA_CONTAMINATION — quarantine required before research |
| P245A | absent; not a dependency |

---

## 8. Verification

| Check | Result |
|---|---|
| P245B JSON parses | PASS (verified before commit) |
| Prior artifacts verified | P236A/P237C/P238B/P219 all present and read |
| P245A | ABSENT — confirmed not a dependency |
| DB writes | 0 |
| Whitelisted files only | YES |
| git diff --check | PASS |

**Final Classification:** `P245B_CORRECTED_BIAS_GATE_LAYER_DESIGN_COMPLETE`
