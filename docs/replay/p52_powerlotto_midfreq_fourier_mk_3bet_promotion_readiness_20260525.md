# P52: POWER_LOTTO midfreq_fourier_mk_3bet Promotion Readiness Decision

**Classification**: `P52_PROMOTION_READINESS_WAIVER_REQUIRED`  
**Date**: 2026-05-25  
**Branch**: `p52-powerlotto-promotion-readiness`  
**P51 Source**: `0415cc8` — merged into main

---

## Governance Declaration

P52 is **promotion-readiness decision only**. No lifecycle promotion performed.  
P53 requires separate explicit authorization before any promotion proceeds.

- No DB write ✓
- No lifecycle promotion ✓
- No registry mutation ✓
- No champion replacement ✓
- No live API call ✓
- Production rows before: `42460`
- Production rows after: `42460`

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✓ |
| Branch (at start) | `main` ✓ |
| HEAD | `0415cc8` (P51 merge confirmed) ✓ |
| Production rows | `42460` ✓ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✓ |
| Branch governance guard | `BRANCH_GOVERNANCE_PASS` (main) ✓ |

**P51 merge**: Fast-forward clean merge of `p51-powerlotto-wave4-promotion-gate` into `main`  
at commit `0415cc8` before P52 work commenced.

---

## P51 Evidence Review

Files inspected:
- `docs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.md` ✓
- `outputs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.json` ✓
- `tests/test_p51_powerlotto_wave4_rolling_window_mcnemar_gate.py` ✓
- `scripts/p51_powerlotto_wave4_rolling_window_mcnemar_gate.py` ✓

Evidence verified:
- G1/G2/G3/G5/G6/G7 PASS for `midfreq_fourier_mk_3bet` ✓
- G4 McNemar FAIL: p=0.4655, b=42, c=50 (champion wins more on rare event) ✓
- No test or script overstates promotion readiness ✓
- `special_hit` is **not** folded into `hit_count` (semantics verified) ✓
- Production rows: `42460` unchanged through P51 ✓

---

## P51 Gate Summary for `midfreq_fourier_mk_3bet`

| Gate | Requirement | Result | Pass? |
|---|---|---|---|
| G1 Sample size | >= 1500 rows | 1500 | ✓ |
| G2 Three-window | W150/W500/W1500 all > 0.9474 | 0.9867 / 1.0080 / 1.0273 | ✓ |
| G3 Permutation | p < 0.05 | p=0.0003 | ✓ |
| G4 McNemar | p < 0.05 vs `fourier_rhythm_3bet` | p=0.4655, **b=42 < c=50** | ✗ |
| G5 Special hit CI | within 2σ of 1/8 | 0.1187 in [0.1079, 0.1421] | ✓ |
| G6 Rolling stability | all windows positive delta | +0.039 / +0.061 / +0.080 | ✓ |
| G7 Governance | no promotion | read-only P51 | ✓ |

---

## Decision Matrix: `midfreq_fourier_mk_3bet`

### Evidence Strength

| Dimension | Value | Assessment |
|---|---|---|
| Mean hit (overall) | 1.027333 | Above theoretical baseline 0.9474 by +0.080 |
| Mean hit vs champion | 1.027333 vs 0.9927 | Candidate leads by +0.0346 |
| W150 | 0.9867 | Above baseline (+0.039) |
| W500 | 1.0080 | Above baseline (+0.061) |
| W1500 | 1.0273 | Above baseline (+0.080) |
| Rolling stability | Monotonically improving | All three windows positive, increasing delta |
| Permutation p | 0.0003 | Highly significant vs theoretical null |
| t-test p (one-tailed) | 0.000135 | Highly significant vs 0.9474 |
| Effect size (Cohen's d vs theoretical) | ~0.088 | Small |
| Effect size (Cohen's d vs champion) | ~0.038 | Negligible |

### McNemar Weakness (G4 Failure Analysis)

| Item | Value | Implication |
|---|---|---|
| Event | `hit_count >= 3` | All-or-nothing rare event for 3-bet strategy |
| b (candidate wins) | 42 | Draws where candidate hits 3, champion does not |
| c (champion wins) | 50 | Draws where champion hits 3, candidate does not |
| Direction | Champion favored (c > b) | **Not merely a power issue** |
| χ² | 0.5326 | Far from significant |
| p-value | 0.4655 | No evidence candidate beats champion on rare event |
| Discordant pairs | 92 / 1500 (6.1%) | Rare event confirmed; low absolute discordant count |

**Critical finding**: b=42 < c=50. The champion `fourier_rhythm_3bet` achieves  
the maximum-hit event (`hit_count >= 3`) more frequently than the candidate.  
This is **not** a statistical-power problem — the direction favors the champion.  
The candidate achieves higher mean_hit through moderate (1-2 hit) draws,  
not through high-value (all-3-hit) draws.

### Practical Significance

The candidate's mean-hit advantage over the champion (+0.0346) is real and  
statistically confirmed. However, Cohen's d vs champion is ~0.038 (negligible  
effect size). In a high-variance lottery environment, this small advantage may  
not be reliably detectable in live operations. A regime shift or data-generating  
process change could plausibly erase this difference.

### Lottery High-Variance Caveat

Lottery outcomes are inherently high-variance. 1500 draws spans approximately  
3 years of POWER_LOTTO draws. Effect sizes are small. There is non-trivial  
probability that the observed mean-hit advantage reverts under a regime change  
(jackpot reset cycle, rule modification, or draw frequency change).

### Comparison vs Champion

`midfreq_fourier_mk_3bet` (mean 1.027) outperforms `fourier_rhythm_3bet` (mean 0.993)  
on average, but `fourier_rhythm_3bet` outperforms on the high-value `hit_count=3` event.

This creates a prize-tier tradeoff:
- Higher average hits → more moderate prize coverage
- Champion wins more 3-hit events → potentially stronger on highest prize tier

### Governance Risk

Promoting without resolving the G4 directional weakness would:
1. Replace a champion that is stronger on the highest-tier event
2. Accept a strategy that is better only in average terms (small negligible Cohen's d)
3. Leave open the risk that mean-hit advantage is regime-dependent

---

## G4 McNemar Policy Decision

**P52 policy choice: `G4_REQUIRES_WAIVER`**

**Rationale:**

The G4 failure is not primarily a rare-event power issue. With b=42 and c=50,  
the champion wins the `hit_count >= 3` event more frequently than the candidate.  
The McNemar p=0.4655 is not simply "lacking power" — the effect is directionally  
adverse to the candidate on the high-value metric.

`G4_NOT_BLOCKING_FOR_RARE_EVENT` would be incorrect because that rationale applies  
when b > c (candidate shows advantage but lacks power). Here b < c.

`G4_BLOCKS_PROMOTION` would be overly conservative — the mean-hit advantage  
(p=0.0003, G2/G3/G6 all PASS) is real and practically meaningful for moderate-prize  
coverage.

`G4_REQUIRES_WAIVER` is the appropriate policy: promotion may be considered only  
with explicit CEO/CTO sign-off acknowledging that:
1. The candidate is weaker than the champion on the `hit_count = 3` prize tier
2. The mean-hit advantage is real but of negligible Cohen's d effect size
3. The lottery high-variance environment makes small advantages unreliable

---

## Per-Strategy Classification

### `midfreq_fourier_mk_3bet`

**P51**: `P52_PROMOTION_CANDIDATE`  
**P52**: `PROMOTION_WITH_WAIVER_REQUIRED`

Requirements before P53 can proceed:
1. CEO/CTO explicit waiver acknowledging G4 directional weakness
2. P53 scope: WATCHLIST only (not ONLINE) as first promotion step
3. McNemar supplementary test with `hit_count >= 2` threshold in P53
4. 500-draw additional OOS holdout recommended before WATCHLIST→ONLINE

### `pp3_freqort_4bet`

**P51**: `INCONCLUSIVE`  
**P52**: `INCONCLUSIVE`

W1500 delta positive (+0.055) but W150 and W500 below baseline. Not promotion-ready.  
Recommend 500 additional draws then re-evaluation.

### `midfreq_fourier_2bet`

**P51**: `INCONCLUSIVE`  
**P52**: `INCONCLUSIVE`

G2/G3/G6 all FAIL. Mean hit 0.9727 does not significantly exceed theoretical  
baseline. Not a promotion candidate at this time.

---

## Overall P52 Classification

**`P52_PROMOTION_READINESS_WAIVER_REQUIRED`**

`midfreq_fourier_mk_3bet` passes 6 of 7 gates (G1/G2/G3/G5/G6/G7) but fails G4  
with an adverse direction. Promotion requires explicit CEO/CTO waiver. No promotion  
may occur in P52 or without separate authorization.

---

## P53 Recommendation (Conditional)

If waiver is granted, P53 should:

1. **Promote to WATCHLIST first** (not ONLINE) — controlled canary promotion
2. **Supplementary McNemar** with `hit_count >= 2` threshold — tests the moderate-hit  
   advantage where the candidate actually excels
3. **500-draw OOS holdout** — validate mean-hit advantage holds on unseen data
4. **90-day WATCHLIST monitoring** — compare live mean_hit vs champion before ONLINE
5. **No champion replacement** in P53 — WATCHLIST coexistence with `fourier_rhythm_3bet`

P53 should NOT proceed without the waiver. Creating a P53 task does not imply  
promotion authorization.

---

## Online Promotion Justified Now?

**No.**

G4 McNemar fails with adverse direction (champion wins on high-value event more  
often). Promoting directly to ONLINE would replace a champion that outperforms  
on the maximum prize tier. Explicit waiver required.

---

## WATCHLIST as Safer Alternative

**Yes, WATCHLIST is the safer classification than ONLINE.**

If waiver is granted, WATCHLIST allows:
- Live monitoring of mean_hit vs champion
- Early detection of regime change reverting the mean-hit advantage
- Low-risk coexistence alongside champion
- Reversible (can be reverted to DRY_RUN if performance degrades)

---

## Files Created

| File | Purpose |
|---|---|
| `docs/replay/p52_powerlotto_midfreq_fourier_mk_3bet_promotion_readiness_20260525.md` | P52 formal report (this file) |
| `outputs/replay/p52_powerlotto_midfreq_fourier_mk_3bet_promotion_readiness_20260525.json` | P52 machine-readable decision |
| `tests/test_p52_powerlotto_promotion_readiness.py` | P52 test suite |
| `scripts/p52_powerlotto_promotion_readiness.py` | P52 read-only analysis script |

---

## Governance Confirmation

- No DB write ✓
- No registry mutation ✓
- No lifecycle promotion ✓
- No champion replacement ✓
- No live API call ✓
- Production rows remain `42460` ✓
- P53 authorization required before any promotion ✓
- Waiver required before P53 can begin ✓
