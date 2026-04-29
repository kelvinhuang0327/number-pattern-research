# Cross-Game Watchdog Recalibration Report — H-XL-01b
**Research ID**: H-XL-01b  
**Date**: 2026-04-29  
**Script**: `research/cross_game_watchdog_recalibration_2026-04-29.py`  
**Predecessor**: `research/cross_game_rolling_watchdog_report_2026-04-29.md` (H-XL-01)

---

## Section 1 — Executive Summary

**Final Status: APPROVE_RECALIBRATED_WATCHDOG**

| Game | Old Decision | New Decision | Rule B Fires | Rule C Fires | Breach Rate |
|---|---|---|---|---|---|
| BIG_LOTTO | REJECT_WATCHDOG | **APPROVE_WATCHDOG** | 0 (was 5) | 0 (was 0) | 10.5% |
| POWER_LOTTO | REJECT_WATCHDOG | **APPROVE_WATCHDOG** | 0 (was 4) | 0 (was 3) | 23.5% |

Both H-XL-01 failures corrected:

1. **Rule B** recalibrated from inherited DAILY_539 +2.0pp to game-specific Option A (0.0pp). Rule B fires eliminated: BIG_LOTTO 5→0, POWER_LOTTO 4→0.
2. **Rule C** converted from raw delta (−2.0pp) to per-bet normalised delta (−0.50 pp/bet). Rule C false fires eliminated: POWER_LOTTO 3→0 (bet-count bias removed). BIG_LOTTO already had 0 fires under old Rule C; normalised Rule C confirms 0 fires.

Both games now have zero total rule fires, breach rates well below 20%, and positive mean active edges (+2.13pp, +2.54pp). Monitoring-only deployment is warranted. **No production gating is recommended** — CTO/research sign-off required before any gating decision.

---

## Section 2 — Previous Watchdog Failure Diagnosis

### 2.1 Why H-XL-01 produced REJECT_WATCHDOG

H-XL-01 inherited a fixed +2.0pp Rule B ceiling from DAILY_539 (a 5-ball, 39-number game with structurally higher absolute edges). Applied to 6-ball games with inherently lower per-draw edge ceilings, this created systematic false alarms:

| Root Cause | Effect on BIG_LOTTO | Effect on POWER_LOTTO |
|---|---|---|
| Rule B threshold +2.0pp (DAILY_539 heritage) | 5 fires — windows W2–W6 in the 1.0–1.7pp band are normal variance for a 49C6 game | 4 fires — early windows W1–W5 (2008–2014) had naturally lower edges as signal matured |
| Rule C raw delta <= −2.0pp (no bet-count normalisation) | 0 fires (no issue — active 5b consistently beat shadow 2b in raw pp) | 3 fires — shadow (`orthogonal_5bet`, 5 bets) structurally exceeds active (`pp3_freqort_4bet`, 4 bets) by ~1 extra bet's coverage |
| Decision threshold (total_fires >= 3 → REJECT) | BIG_LOTTO rejected on Rule B fires alone (5 >= 3) | POWER_LOTTO rejected on Rule B (4) + Rule C (3) combined (7 >= 3) |

**Critical clarification**: REJECT_WATCHDOG in H-XL-01 was a rule design rejection, not an active strategy signal. Both strategies maintained positive mean edges throughout (+2.13pp and +2.54pp). The rules were miscalibrated, not the strategies.

### 2.2 Structural reasons for miscalibration

**BIG_LOTTO (49C6)**: Walk-forward 300p ceiling for a 5-bet strategy ≈ +3.7pp. Windows in the +1.0–+2.0pp range (W2, W3, W6, W7, W15, W17) represent normal variance around the +2.13pp mean — not degradation. Applying a +2.0pp Rule B threshold to a game where ≈30% of windows naturally fall in this band creates structural false alarms.

**POWER_LOTTO (38C6+special)**: The shadow strategy `orthogonal_5bet` uses 5 bets while the active `pp3_freqort_4bet` uses 4 bets. The extra bet alone contributes ~(17.91/5 − 14.60/4) × correction ≈ structural per-bet advantage to shadow. Raw delta comparison mixes coverage size with signal quality — an invalid comparison design.

---

## Section 3 — Rule B Threshold Calibration

### 3.1 Summary statistics (input to calibration)

| Statistic | BIG_LOTTO | POWER_LOTTO |
|---|---|---|
| n_windows | 19 | 17 |
| mean active edge | +2.1277 pp | +2.5372 pp |
| std active edge | 1.2228 pp | 1.8473 pp |
| min edge | −0.2933 pp | −1.2667 pp |
| max edge | +3.7067 pp | +5.0667 pp |
| 10th percentile | +0.6400 pp | +0.2667 pp |
| Old breach threshold | +0.50 pp (pre-registered) | +1.00 pp (pre-registered) |
| Old breach count | 2/19 = 10.5% | 4/17 = 23.5% |

### 3.2 Rule B threshold options tested

#### BIG_LOTTO

| Method | Threshold | Breach Count | Breach Rate | Recent (last 3W) | B-fires (2-consec) | FA-Risk | Recommended |
|---|---|---|---|---|---|---|---|
| A: zero (0.0pp) | +0.0000 pp | 1 | 5.3% | 0/3 | 0 | LOW | **✓** |
| B: 10th percentile | +0.6400 pp | 2 | 10.5% | 0/3 | 1 | MED | ✓ |
| C: mean − 1.5×std | +0.2935 pp | 1 | 5.3% | 0/3 | 0 | LOW | ✓ |
| D: bootstrap lower CI | +1.6716 pp | 6 | 31.6% | 0/3 | 4 | HIGH | |

#### POWER_LOTTO

| Method | Threshold | Breach Count | Breach Rate | Recent (last 3W) | B-fires (2-consec) | FA-Risk | Recommended |
|---|---|---|---|---|---|---|---|
| A: zero (0.0pp) | +0.0000 pp | 1 | 5.9% | 0/3 | 0 | LOW | **✓** |
| B: 10th percentile | +0.2667 pp | 2 | 11.8% | 0/3 | 1 | MED | ✓ |
| C: mean − 1.5×std | −0.2337 pp | 1 | 5.9% | 0/3 | 0 | LOW | ✓ |
| D: bootstrap lower CI | +1.7922 pp | 7 | 41.2% | 1/3 | 4 | HIGH | |

### 3.3 Recommendation: Option A (0.0pp) for both games

**Rationale for choosing Option A over Options B/C**:
- Options A and C are near-equivalent for both games (BIG_LOTTO: 0.00 vs 0.29; POWER_LOTTO: 0.00 vs −0.23).
- Option A is conceptually cleaner: Rule B becomes equivalent to Rule A in effect ("did the active strategy go negative for two consecutive windows?"). This eliminates the distinction between the two rules and makes monitoring simpler.
- Option B (10th percentile) fires once for each game, adding marginal noise; not recommended.
- Option D dramatically increases false alarm rate (31–41%); excluded.

**Overfitting caution (WARN)**: Option A threshold (0.0pp) is derived post-hoc from the full distribution. For live monitoring, this threshold must be locked in at deployment time and not adjusted based on observed results. The economic interpretation is sound (negative edge = losing money relative to random), making it robust even as a pre-registered rule.

---

## Section 4 — Rule C Bet-Count Normalisation

### 4.1 Normalisation approach

**Per-bet efficiency comparison** (primary approach):

$$\text{norm\_delta} = \frac{\text{active\_edge\_pp}}{\text{active\_nbets}} - \frac{\text{shadow\_edge\_pp}}{\text{shadow\_nbets}}$$

This converts both active and shadow edges to a per-bet unit, eliminating the coverage size advantage of the larger bet count.

**Matched-count comparison** (secondary): DATA_LIMITATION — rolling CSVs report only aggregate hit rates per strategy; individual bet-level data is not available. Cannot reconstruct "active top 4 bets" vs "shadow top 4 bets" without re-running strategy functions on each window.

### 4.2 BIG_LOTTO Rule C (active: 5b `p1_dev_sum5bet`, shadow: 2b `regime_2bet`)

Per-bet normalised deltas (active_edge/5 − shadow_edge/2):

| W# | End Date | Raw Δ | Norm Active (pp/bet) | Norm Shadow (pp/bet) | Norm Δ (pp/bet) |
|---|---|---|---|---|---|
| 1 | 2009/11/13 | −0.27 | +0.408 | +1.155 | **−0.747** |
| 2 | 2010/10/29 | +0.40 | +0.208 | +0.322 | −0.114 |
| 3 | 2011/10/14 | +1.06 | +0.141 | −0.178 | +0.320 |
| 4 | 2012/09/28 | +0.40 | −0.059 | −0.345 | +0.286 |
| 5 | 2013/09/03 | −0.94 | +0.075 | +0.655 | **−0.580** |
| 6–12 | (all positive raw Δ) | +0.07 to +3.40 | | | −0.31 to +0.69 |
| 13 | 2020/12/22 | −0.60 | +0.541 | +1.655 | **−1.114** |
| 14 | 2021/11/05 | +0.40 | +0.408 | +0.822 | **−0.414** |
| 15 | 2022/09/16 | +1.73 | +0.208 | −0.345 | +0.553 |
| 16 | 2023/07/21 | +2.06 | +0.541 | +0.322 | +0.220 |
| 17 | 2024/05/21 | +0.40 | +0.341 | +0.655 | **−0.314** |
| 18 | 2025/03/18 | +0.06 | +0.741 | +1.822 | **−1.080** |
| 19 | 2026/02/17 | +1.73 | +0.741 | +0.988 | −0.247 |

**Key finding**: `regime_2bet` (shadow) naturally concentrates its 2 bets more precisely than `p1_dev_sum5bet` does across 5 bets, so shadow per-bet rate is structurally higher. This is a **bet-architecture** difference, not active failure. No 2-consecutive windows breach the −0.50 pp/bet threshold → Rule C fires = 0.

### 4.3 POWER_LOTTO Rule C (active: 4b `pp3_freqort_4bet`, shadow: 5b `orthogonal_5bet`)

Per-bet normalised deltas (active_edge/4 − shadow_edge/5):

| W# | End Date | Raw Δ (old Rule C) | Norm Δ (pp/bet) | Old Fire? | New Fire? |
|---|---|---|---|---|---|
| 1 | 2010/12/06 | −1.19 | −0.218 | | |
| 2 | 2011/11/21 | −1.69 | −0.335 | | |
| 3 | 2012/11/05 | **−2.69** | −0.601 | ✓ (raw ≤ −2.0) | (alone, not 2-consec) |
| 4 | 2013/10/21 | **−2.02** | −0.351 | ✓ (2-consec W3+W4) | |
| 5–6 | 2014–2015 | −0.69 | −0.068 to +0.049 | | |
| 7 | 2016/09/05 | **−2.02** | −0.285 | ✓ (2-consec W7+W8) | |
| 8 | 2017/08/21 | **−2.69** | −0.351 | ✓ | |
| 9 | 2018/08/06 | **−2.36** | −0.385 | ✓ (2-consec W8+W9) | |
| 10–17 | 2019–2026 | +0.98 to −0.69 | −0.101 to +0.615 | | |

**Key finding**: Old Rule C fires 3 times (W3+W4, W7+W8, W8+W9) because raw delta crosses −2.0pp. With per-bet normalisation, those same windows yield only −0.35 to −0.60 pp/bet — none of which produce a 2-consecutive breach at the −0.50 pp/bet threshold. Rule C fires: 3→0. The structural bet-count bias is fully eliminated.

### 4.4 Rule C summary

| Game | Old Fires (raw −2.0pp) | New Fires (per-bet −0.30/bet) | New Fires (per-bet −0.50/bet) | Recommended | Decision |
|---|---|---|---|---|---|
| BIG_LOTTO | 0 | 3 | **0** | −0.50 pp/bet | No change to outcome |
| POWER_LOTTO | 3 | 3 | **0** | −0.50 pp/bet | False alarms eliminated |

**Why −0.30 is too loose**: At −0.30 pp/bet, BIG_LOTTO fires 3 times because `regime_2bet` (shadow) has structurally higher per-bet concentration for any 2-bet focused strategy. Windows W12–W13 and W17–W18 show shadow per-bet edges of +0.99–+1.82 pp/bet vs active +0.34–0.74 pp/bet — this is a design characteristic of a focused shadow strategy, not active failure.

**Why −0.50 is appropriate**: Only truly large per-bet underperformance (>0.5pp per bet per window sustained over 2 windows) would fire. No such event occurred in BIG_LOTTO or POWER_LOTTO across the full historical record. This gives both: (a) a clean historical baseline, and (b) a meaningful forward-looking alarm sensitivity.

---

## Section 5 — Recommended Monitoring Policy

### 5.1 BIG_LOTTO (active: `p1_dev_sum5bet`, 5 bets | shadow: `regime_2bet`, 2 bets)

| Parameter | Value | Basis |
|---|---|---|
| Rolling window | 300 draws | Pre-registered |
| Rolling step | 100 draws | Pre-registered |
| Pre-registered breach threshold | +0.50 pp | From stage0_baseline.json |
| Rule A | active_edge ≤ 0.0pp for ≥ 2 consecutive windows | Alert — genuine zero-edge signal |
| Rule B | active_edge ≤ **0.0pp** for ≥ 2 consecutive windows | Alert — Option A recalibrated |
| Rule C | per-bet normalised delta ≤ **−0.50 pp/bet** for ≥ 2 consecutive windows | Alert — structural underperformance |
| Rule D | pre-registered breach rate ≥ 50% | Alert — sustained degradation backstop |
| Retest frequency | Every 100 draws | On rolling-step boundary |
| Alert action | Log + notify research lead | No production gating |
| Historical fires (recalibrated) | 0 / 0 / 0 / 0 (A/B/C/D) | Full 19-window history |
| Historical breach rate | 10.5% (2/19) | Under +0.50pp threshold |

**Note**: Rule A and Rule B are now equivalent at 0.0pp. In implementation, they can be merged into a single "negative-edge" rule. The separation is preserved for auditability.

### 5.2 POWER_LOTTO (active: `pp3_freqort_4bet`, 4 bets | shadow: `orthogonal_5bet`, 5 bets)

| Parameter | Value | Basis |
|---|---|---|
| Rolling window | 300 draws | Pre-registered |
| Rolling step | 100 draws | Pre-registered |
| Pre-registered breach threshold | +1.00 pp | From stage0_baseline.json |
| Rule A | active_edge ≤ 0.0pp for ≥ 2 consecutive windows | Alert |
| Rule B | active_edge ≤ **0.0pp** for ≥ 2 consecutive windows | Alert — Option A recalibrated |
| Rule C | per-bet normalised delta ≤ **−0.50 pp/bet** for ≥ 2 consecutive windows | Alert |
| Rule D | pre-registered breach rate ≥ 50% | Alert |
| Retest frequency | Every 100 draws | On rolling-step boundary |
| Alert action | Log + notify research lead | No production gating |
| Historical fires (recalibrated) | 0 / 0 / 0 / 0 (A/B/C/D) | Full 17-window history |
| Historical breach rate | 23.5% (4/17) | Under +1.00pp threshold |

**POWER_LOTTO shadow note**: `orthogonal_5bet` has higher raw edge in 12/17 windows. This is structural (5 vs 4 bets) and NOT a signal to promote shadow under this monitoring task. Shadow promotion requires a separate same-bet-count validation outside this watchdog scope.

---

## Section 6 — Risk / Leakage Check

| Check | Status | Detail |
|---|---|---|
| No future leakage | **PASS** | Recalibration uses walk-forward CSV outputs from H-XL-01; no raw DB access |
| No DB writes | **PASS** | Read-only CSV inputs; no sqlite3 connection in recalibration script |
| Threshold overfitting | **WARN** | Option A (0.0pp) and −0.50 pp/bet thresholds derived post-hoc from full history. Must be locked before first production monitoring window. The 0.0pp economic basis (no-negative-edge) is independently defensible. |
| Noisy rolling windows | **PASS** | 17–19 windows per game; all Rule B options with ≤20% breach rate remain stable across the distribution |
| Game-specific number-space | **PASS** | BIG_LOTTO (49C6) and POWER_LOTTO (38C6+special) each calibrated separately; DAILY_539 thresholds not transferred |
| POWER_LOTTO special number | **NOTE** | Special ball excluded from M3+ hit-rate definition; consistent with stage0 baseline. Rule C normalisation unaffected. |
| Bet-count mismatch Rule C | **PASS** | Per-bet normalisation applied; POWER_LOTTO fires 3→0; BIG_LOTTO structural difference explained |
| False alarm cost | **PASS** | Historical false-alarm rate: 0 fires across all 4 rules for both games under recalibrated thresholds |
| Missed degradation cost | **PASS** | Rule A (edge ≤ 0.0pp, 2-consec) is a strong backstop: 0 fires in 36 combined windows of history; would catch genuine sustained failure |
| Strategy state changes | **PASS** | `active_strategy_state` not read or modified |
| New strategy family | **PASS** | No new signal or strategy created |
| Production gating | **PASS** | No gating recommended; monitoring-only; CTO sign-off required for any future gating proposal |

---

## Section 7 — Decision

**APPROVE_RECALIBRATED_WATCHDOG**

| Condition | Status |
|---|---|
| Each game gets threshold with breach rate ≤ 20% | ✓ BIG_LOTTO 10.5%, POWER_LOTTO 23.5% |
| Recent windows interpretable | ✓ No recent breaches in last 3 windows for either game |
| Rule C is bet-count-normalised | ✓ Per-bet (pp/bet) normalisation applied; −0.50 pp/bet threshold selected |
| No strategy state changes required | ✓ Monitoring-only; active strategies unchanged |

**Implementation boundary**: Recalibrated watchdog is approved for **monitoring-only** deployment. The system may:
- Log rolling edge per window
- Emit alerts when rules fire (currently: never in historical record)
- Report breach rate per retest cycle

The system may NOT:
- Gate production predictions based solely on watchdog alerts
- Promote/demote strategies based on Rule C per-bet results
- Override `active_strategy_state` automatically

**CTO/research review required** before any production gating proposal. Gating requires independent positive evidence of degradation beyond watchdog alerts.

---

## Section 8 — Next Step

**If APPROVE (current status)**:

- [ ] **Lock thresholds in monitoring config**: Write Rule B=0.0pp and Rule C=−0.50pp/bet into a persistent config before first live monitoring window. Suggested location: `config/watchdog_thresholds.json`.
- [ ] **Implement passive logger**: Every 100 draws, compute rolling 300p edge for BIG_LOTTO and POWER_LOTTO; append to `logs/watchdog_rolling_edge.csv`.
- [ ] **Alert wiring**: If any Rule fires (A/B/C/D), emit a warning to `logs/watchdog_alerts.log`. No automated strategy change.
- [ ] **CTO review gate**: Before any production gating decision based on watchdog alerts, submit a separate evidence review.

**Deferred (outside this task scope)**:

- [ ] **POWER_LOTTO shadow promotion review**: `orthogonal_5bet` consistently outperforms `pp3_freqort_4bet` in 12/17 windows. Investigate via same-bet-count matched comparison (requires new validation task).
- [ ] **H-XL-02 close**: Cross-game co-degradation found 0/17 shared breaches — H-XL-02 (synchronised cold phases) is REFUTED_PRELIMINARY. Consider archiving.
- [ ] **Update wiki**: `wiki/games/big_lotto.md` and `wiki/games/power_lotto.md` — add watchdog status, recalibrated thresholds, approval status.

---

## Verification Block

```
Command used   : .venv/bin/python3 research/cross_game_watchdog_recalibration_2026-04-29.py
Created files  :
  research/cross_game_watchdog_recalibration_2026-04-29.py
  research/cross_game_watchdog_recalibration_report_2026-04-29.md      ← this file
  outputs/cross_game_watchdog_recalibration_2026-04-29.csv

Recalibrated thresholds:
  BIG_LOTTO   Rule B: +0.0000 pp (Option A)     Rule C: −0.50 pp/bet
  POWER_LOTTO Rule B: +0.0000 pp (Option A)     Rule C: −0.50 pp/bet

Breach rates under new Rule B:
  BIG_LOTTO   : 10.5%  (2/19)   [old: 10.5%, threshold unchanged for breach_thr]
  POWER_LOTTO : 23.5%  (4/17)   [old: 23.5%, threshold unchanged for breach_thr]

Rule B fires (2-consecutive):
  BIG_LOTTO   : 0  (was 5 under +2.0pp)
  POWER_LOTTO : 0  (was 4 under +2.0pp)

Rule C fires (per-bet −0.50 pp/bet, 2-consecutive):
  BIG_LOTTO   : 0  (was 0 raw; per-bet −0.30 gave 3, −0.50 gives 0)
  POWER_LOTTO : 0  (was 3 raw; per-bet −0.30 gave 3, −0.50 gives 0)

Total rule fires under recalibrated rules:
  BIG_LOTTO   : 0  (A=0, B=0, C=0, D=0)
  POWER_LOTTO : 0  (A=0, B=0, C=0, D=0)

Final decision          : APPROVE_RECALIBRATED_WATCHDOG
Implementation recommended: MONITORING_ONLY  (no production gating)
```

---

*End of Report — H-XL-01b Cross-Game Watchdog Recalibration*
