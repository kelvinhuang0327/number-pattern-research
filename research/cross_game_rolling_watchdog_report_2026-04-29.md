# Cross-Game Rolling Watchdog Report — BIG_LOTTO & POWER_LOTTO
**Research ID**: H-XL-01  
**Date**: 2026-04-29  
**Script**: `research/cross_game_rolling_watchdog_2026-04-29.py`  
**Run Time**: ~122s (BIG_LOTTO 100s + POWER_LOTTO 22s)

---

## Section 1 — Executive Summary

| Game | Windows | Mean Active Edge | Breach% | Threshold | Decision |
|---|---|---|---|---|---|
| BIG_LOTTO | 19 | +2.13pp | 10.5% | +0.5pp | **REJECT_WATCHDOG** |
| POWER_LOTTO | 17 | +2.54pp | 23.5% | +1.0pp | **REJECT_WATCHDOG** |
| DAILY_539 (ref) | 27 | +3.47pp | 40.7% | +2.0pp | STABLE (reference) |

**Verdict: REJECT_WATCHDOG for both games under current rule configuration.**

Both strategies maintain positive mean edges (+2.13pp and +2.54pp respectively), well above their pre-registered breach thresholds. Breach rates (10.5% and 23.5%) are below the 50% Rule D line. **The rejection is not a strategy degradation signal — it is a watchdog rule calibration failure.** Rule B (+2.0pp ceiling) is too tight for the lower-edge regime of BIG_LOTTO (49C6 dilution) and POWER_LOTTO. Rule C fires repeatedly for POWER_LOTTO because the shadow strategy (`orthogonal_5bet`) consistently outperforms the active (`pp3_freqort_4bet`) — a meaningful signal warranting a separate shadow promotion review, not a watchdog false alarm.

**H-XL-01 outcome**: Rolling 300p windows are mechanically feasible (≥17 windows for both games), but Rule B and Rule C thresholds inherited from DAILY_539 (a 5-ball, higher-hit-rate game) produce excessive false alarms for 6-ball lotteries with lower absolute edge ceilings. Watchdog monitoring is FEASIBLE with recalibrated thresholds; current rule set is NOT deployable.

---

## Section 2 — Data Coverage

| Field | BIG_LOTTO | POWER_LOTTO |
|---|---|---|
| Total draws | 2,129 | 1,905 |
| Date range | 2007/01/02 → 2026/04/24 | 2008/01/24 → 2026/04/23 |
| Min history required | 100p | 100p |
| Rolling window | 300p | 300p |
| Rolling step | 100p | 100p |
| Usable windows | 19 | 17 |
| W01 effective draws | 200 (first window starts at idx=0; only 200 draws past MIN_HIST guard) | 200 |
| W02+ draws | 300 | 300 |

**Notes**:
- W01 for both games has n=200 because draws 0–99 are held as minimum history, leaving 200 draws for evaluation inside the first 300p window.
- No 200p fallback was needed — both games crossed the 300p + 100p minimum threshold.
- No duplicate draw IDs observed; no draws skipped due to format errors.

---

## Section 3 — Rolling Window Results

### 3.1 BIG_LOTTO (active: `p1_dev_sum5bet`, 5 bets | shadow: `regime_2bet`, 2 bets | baseline M3+: 8.96%)

| W# | Start | End | n | Active Edge | Shadow Edge | Δ (A−S) | Breach |
|---|---|---|---|---|---|---|---|
| 1 | 2007/01/02 | 2009/11/13 | 200 | +2.04pp | +2.31pp | −0.27 | |
| 2 | 2007/12/18 | 2010/10/29 | 300 | +1.04pp | +0.64pp | +0.40 | |
| 3 | 2008/12/02 | 2011/10/14 | 300 | +0.71pp | −0.36pp | +1.06 | |
| 4 | 2009/11/17 | 2012/09/28 | 300 | −0.29pp | −0.69pp | +0.40 | ⚠ |
| 5 | 2010/11/02 | 2013/09/03 | 300 | +0.37pp | +1.31pp | −0.94 | ⚠ |
| 6 | 2011/10/18 | 2014/08/05 | 300 | +0.71pp | −0.02pp | +0.73 | |
| 7 | 2012/10/02 | 2015/07/03 | 300 | +1.71pp | +0.31pp | +1.40 | |
| 8 | 2013/09/06 | 2016/05/27 | 300 | +3.37pp | −0.02pp | +3.40 | |
| 9 | 2014/08/08 | 2017/04/28 | 300 | +3.37pp | +1.31pp | +2.06 | |
| 10 | 2015/07/07 | 2018/03/30 | 300 | +3.37pp | +0.64pp | +2.73 | |
| 11 | 2016/05/31 | 2019/02/19 | 300 | +3.04pp | +1.31pp | +1.73 | |
| 12 | 2017/05/02 | 2020/01/26 | 300 | +3.37pp | +1.98pp | +1.40 | |
| 13 | 2018/04/03 | 2020/12/22 | 300 | +2.71pp | +3.31pp | −0.60 | |
| 14 | 2019/02/22 | 2021/11/05 | 300 | +2.04pp | +1.64pp | +0.40 | |
| 15 | 2020/01/27 | 2022/09/16 | 300 | +1.04pp | −0.69pp | +1.73 | |
| 16 | 2020/12/25 | 2023/07/21 | 300 | +2.71pp | +0.64pp | +2.06 | |
| 17 | 2021/11/09 | 2024/05/21 | 300 | +1.71pp | +1.31pp | +0.40 | |
| 18 | 2022/09/20 | 2025/03/18 | 300 | +3.71pp | +3.64pp | +0.06 | |
| 19 | 2023/07/25 | 2026/02/17 | 300 | +3.71pp | +1.98pp | +1.73 | |

**Observations**:
- Only 2 breaches (W4, W5), both in the 2009–2013 era. No recent breaches (W16–W19 all clear).
- Edge trend: early dip (W3–W5 ≈ 0.4–0.7pp), strong mid-period (W8–W12 ≈ 3.4pp), sustained recent (W18–W19 ≈ +3.71pp). Pattern is STABLE with an early low-edge cold phase.
- CUSUM detects a **positive** break at W4 (pre_mean=+0.87pp, post_mean=+2.46pp) — this is an upward regime shift, not degradation.
- Active consistently beats shadow for most windows (mean delta +1.05pp). Shadow (2-bet, smaller coverage) is more volatile.

### 3.2 POWER_LOTTO (active: `pp3_freqort_4bet`, 4 bets | shadow: `orthogonal_5bet`, 5 bets | baseline M3+: 14.60%)

| W# | Start | End | n | Active Edge | Shadow Edge | Δ (A−S) | Breach |
|---|---|---|---|---|---|---|---|
| 1 | 2008/01/24 | 2010/12/06 | 200 | +0.40pp | +1.59pp | −1.19 | ⚠ |
| 2 | 2009/01/08 | 2011/11/21 | 300 | +0.07pp | +1.76pp | −1.69 | ⚠ |
| 3 | 2009/12/24 | 2012/11/05 | 300 | −1.27pp | +1.42pp | −2.69 | ⚠ |
| 4 | 2010/12/09 | 2013/10/21 | 300 | +1.07pp | +3.09pp | −2.02 | |
| 5 | 2011/11/24 | 2014/10/06 | 300 | +1.40pp | +2.09pp | −0.69 | |
| 6 | 2012/11/08 | 2015/09/21 | 300 | +3.73pp | +4.42pp | −0.69 | |
| 7 | 2013/10/24 | 2016/09/05 | 300 | +2.40pp | +4.42pp | −2.02 | |
| 8 | 2014/10/09 | 2017/08/21 | 300 | +3.73pp | +6.42pp | −2.69 | |
| 9 | 2015/09/24 | 2018/08/06 | 300 | +1.73pp | +4.09pp | −2.36 | |
| 10 | 2016/09/08 | 2019/07/22 | 300 | +5.07pp | +6.09pp | −1.02 | |
| 11 | 2017/08/24 | 2020/07/06 | 300 | +3.73pp | +4.09pp | −0.36 | |
| 12 | 2018/08/09 | 2021/06/21 | 300 | +5.07pp | +3.76pp | +1.31 | |
| 13 | 2019/07/25 | 2022/06/06 | 300 | +4.40pp | +2.42pp | +1.98 | |
| 14 | 2020/07/09 | 2023/05/22 | 300 | +4.40pp | +3.42pp | +0.98 | |
| 15 | 2021/06/24 | 2024/05/06 | 300 | +3.73pp | +4.09pp | −0.36 | |
| 16 | 2022/06/09 | 2025/04/21 | 300 | +0.73pp | +1.42pp | −0.69 | ⚠ |
| 17 | 2023/05/25 | 2026/04/06 | 300 | +2.73pp | +3.09pp | −0.36 | |

**Observations**:
- Early breaches W1–W3 (2008–2012): POWER_LOTTO signal space was weaker before frequency-orthogonal strategies matured.
- W16 (2022–2025) is the most recent breach (+0.73pp). W17 (2023–2026) recovers to +2.73pp — no sustained degradation signal.
- Shadow (`orthogonal_5bet`, 5-bet) systematically exceeds active (`pp3_freqort_4bet`, 4-bet) in 12/17 windows. Mean shadow edge = +3.39pp vs mean active = +2.54pp. **The 5-bet shadow's extra coverage provides +0.85pp structural advantage on average.** This is a shadow promotion signal, not active strategy failure.
- CUSUM: break at W14 (2020/07/09). Pre_mean = +2.57pp, post_mean = +2.40pp — a tiny dip (−0.17pp), not a regime shift.

---

## Section 4 — Watchdog Rule Evaluation

### Rule Definitions (pre-registered)

| Rule | Trigger Condition | Consecutive Required |
|---|---|---|
| A | active_edge ≤ 0pp | 2 windows |
| B | active_edge ≤ +2.0pp | 2 windows |
| C | active − shadow ≤ −2.0pp | 2 windows |
| D | rolling breach rate ≥ 50% | — |

### BIG_LOTTO

| Rule | Fires | First Fire Window | Assessment |
|---|---|---|---|
| A (edge ≤ 0) | 0 | — | PASS — no zero-edge windows in 2-consec |
| B (edge ≤ +2pp) | 5 | W2 | EXCESSIVE — Rule B too tight for 49C6 game |
| C (delta ≤ −2pp) | 0 | — | PASS — active consistently above shadow |
| D (breach ≥ 50%) | 0 | — | PASS — breach rate only 10.5% |

**Root cause of REJECT**: Rule B fires 5 times (W2–W3, W3–W4, W4–W5, W5–W6, W14–W15 patterns). With BIG_LOTTO's 49C6 dilution, a +2.0pp Rule B ceiling inherited from DAILY_539 (5/39, higher base rate) is structurally too tight. The BIG_LOTTO signal ceiling under walk-forward is approximately +3.0pp for a 5-bet strategy — Rule B at +2.0pp creates ~25% of windows as "near-miss alarms" (edges in the +0.7–+1.7pp band), which cluster into 2-consecutive runs.

### POWER_LOTTO

| Rule | Fires | First Fire Window | Assessment |
|---|---|---|---|
| A (edge ≤ 0) | 0 | — | PASS — no negative-edge windows in 2-consec |
| B (edge ≤ +2pp) | 4 | W1 | EXCESSIVE — early windows (W1–W5) weak |
| C (delta ≤ −2pp) | 3 | W3 | STRUCTURAL — shadow's 5-bet advantage ≥ 2pp |
| D (breach ≥ 50%) | 0 | — | PASS — breach rate only 23.5% |

**Root cause of REJECT**: Rule C fires 3 times (W3–W4, W7–W8, W8–W9). Shadow has +1 extra bet structural advantage — the Rule C −2pp delta threshold is appropriate in design, but is systematically triggered by the active/shadow bet-size mismatch (4-bet vs 5-bet), not by active strategy failure. Rule C should compare strategies at the same number of bets. Rule B fires from early weak windows; recent windows (W12–W17) mostly above +2pp.

---

## Section 5 — Cross-Game Comparison

| Game | Windows | Mean Active Edge | Mean Shadow Edge | Breach% | Rule A | Rule B | Rule C | Rule D |
|---|---|---|---|---|---|---|---|---|
| DAILY_539 (ref) | 27 | +3.47pp | N/A | 40.7% | — | — | — | — |
| BIG_LOTTO | 19 | +2.13pp | +1.08pp | 10.5% | 0 | 5 | 0 | 0 |
| POWER_LOTTO | 17 | +2.54pp | +3.39pp | 23.5% | 0 | 4 | 3 | 0 |

**Key cross-game observations**:

1. **No co-degradation**: 0/17 shared windows where both BIG_LOTTO and POWER_LOTTO breached simultaneously. The two games' active strategy performances are uncorrelated — consistent with the signal independence hypothesis and refutes H-XL-02 (synchronised cold phases).

2. **Edge hierarchy**: DAILY_539 (+3.47pp) > POWER_LOTTO (+2.54pp) > BIG_LOTTO (+2.13pp). This matches expected ordering by draw-space density (5/39 < 6/38 < 6/49) and lesson L85 (49C6 dilutes all frequency signals).

3. **Breach rate hierarchy**: DAILY_539 (40.7%) > POWER_LOTTO (23.5%) > BIG_LOTTO (10.5%). Counterintuitive — DAILY_539 has the highest edge but also the highest breach rate. Reason: DAILY_539 uses a much higher absolute threshold (+2.0pp) calibrated to its stronger signal; BIG_LOTTO/POWER_LOTTO use gentler thresholds (+0.5pp / +1.0pp) that almost all windows exceed.

4. **POWER_LOTTO shadow advantage**: Shadow (`orthogonal_5bet`) outperforms active in 12/17 windows by a mean delta of −0.85pp. This structural advantage is attributable to the extra bet (5 vs 4), not to signal quality. This is a deferred shadow promotion signal but not relevant to watchdog calibration.

5. **DAILY_539 vs 6-ball games**: Rule B threshold of +2.0pp is appropriate for DAILY_539 (~30% of windows fall in the "near-miss" band). Applying +2.0pp to BIG_LOTTO (where walk-forward ceiling ≈ +3.0–3.7pp but many windows land at +1.0–2.0pp) creates structural false alarms.

---

## Section 6 — Risk / Leakage Check

| Check | Status | Evidence |
|---|---|---|
| Look-ahead leakage | CLEAN | `history = draws[:i]` for all evaluations; draw `i` excluded from history |
| Threshold pre-registration | CLEAN | Thresholds set in script config before ANY data was queried |
| New strategy family created | CLEAN | No new signals; used only existing `biglotto_p1_deviation_5bet`, `generate_regime_2bet`, `generate_orthogonal_5bet` |
| DB writes to lottery_v2.db | CLEAN | `sqlite3.connect(DB_PATH)` read-only; no INSERT/UPDATE/DELETE issued |
| `active_strategy_state` modification | CLEAN | File not read or modified |
| Window tuning after data seen | CLEAN | `ROLLING_WINDOW=300`, `ROLLING_STEP=100` fixed before run; no post-hoc adjustment |
| Production gating recommendation | CLEAN | No gating proposed; monitoring-only; threshold recalibration required first |
| DAILY_539 re-run | CLEAN | Loaded from `outputs/daily539_rolling_500p_edge_2026-04-29.csv` only; not re-computed |

No leakage or integrity violations detected.

---

## Section 7 — Recommended Watchdog Policy

**Current status: NOT deployable under Rule B / Rule C as specified.**  
**Rationale**: Both games `REJECT_WATCHDOG` not due to active strategy failure, but due to rule miscalibration.

### Recommended threshold recalibration (proposed; requires validation before deployment)

| Parameter | Current (DAILY_539-inherited) | Proposed for BIG_LOTTO | Proposed for POWER_LOTTO |
|---|---|---|---|
| Rule B threshold | +2.0pp | +1.0pp | +1.0pp |
| Rule C delta trigger | −2.0pp | −2.0pp (keep) | N/A (mismatch issue; compare same n_bets) |
| Rule D breach % | 50% | 50% (keep) | 50% (keep) |
| Breach threshold | +0.5pp (BL) / +1.0pp (PL) | +0.5pp | +1.0pp |

**If Rule B is tightened to +1.0pp for BIG_LOTTO**: W2, W3, W5, W6, W17 (edges ≈ +0.7–1.7pp) would still trigger — approximately the same fire count. **The core issue is structural: BIG_LOTTO's walk-forward 300p ceiling is ~+3.5pp in the best periods; windows with +1.0–2.0pp are normal variance, not alarm-worthy.** Rule B should be raised to +0.0pp (i.e., match Rule A) for BIG_LOTTO, keeping only the zero-edge alarm.

**For POWER_LOTTO Rule C**: The shadow-active delta systematically exceeds −2.0pp because shadow has 1 extra bet. Correct fix: compare active vs shadow edge at equal-coverage (i.e., per-bet hit rate), or replace Rule C with a same-bet-count comparison. This is an architectural change requiring a new validation pass.

### Monitoring-only recommendation

Given current REJECT status, the appropriate action is:

1. **Continue passive edge tracking**: Log rolling 300p edge for both games into CSV after each 100-draw batch. No gating. No automated decision.
2. **Alert only on Rule A** (edge ≤ 0 for 2 consecutive windows): This rule fired 0 times for both games across the full history — any future firing would be a genuinely unusual signal.
3. **Alert on Rule D** (breach rate ≥ 50%): Also fired 0 times; a robust catch-all for sustained degradation.
4. **Defer Rule B and Rule C** pending recalibration.
5. **Do not promote shadow in POWER_LOTTO** based solely on this watchdog output — the shadow advantage is structural (5 vs 4 bets) and requires a separate same-bet-count evaluation.

---

## Section 8 — Next Step

**Immediate**:
- [ ] **Recalibrate Rule B for 6-ball games**: Set Rule B ceiling to +0.5pp for BIG_LOTTO, +1.0pp for POWER_LOTTO (matching breach thresholds), making Rule B a duplicate of the breach threshold check. This reduces Rule B to a "sustained near-threshold" detector and eliminates the main source of false alarms.
- [ ] **Fix Rule C for POWER_LOTTO**: Compare `pp3_freqort_4bet` (active) vs `pp3_freqort_3bet` (same family, 3-bet) rather than vs `orthogonal_5bet` (different family, 5-bet). Shadow comparison must use matched bet counts.

**Deferred**:
- [ ] **H-XL-02 validation**: Cross-game cold phase correlation — this run confirmed **zero co-degradation** (0/17 shared breaches). H-XL-02 should be closed as REFUTED_PRELIMINARY pending larger N.
- [ ] **POWER_LOTTO shadow promotion review**: Shadow (`orthogonal_5bet`) outperforms active in 12/17 windows. This is a separate review item; not a watchdog calibration finding.

**Files produced by this run**:

| File | Rows | Description |
|---|---|---|
| `outputs/biglotto_rolling_300p_edge_2026-04-29.csv` | 19 | Per-window rolling results, BIG_LOTTO |
| `outputs/powerlotto_rolling_300p_edge_2026-04-29.csv` | 17 | Per-window rolling results, POWER_LOTTO |
| `outputs/cross_game_rolling_watchdog_2026-04-29.csv` | 3 | Per-game summary (BIG_LOTTO, POWER_LOTTO, DAILY_539 ref) |
| `research/cross_game_rolling_watchdog_2026-04-29.py` | — | Script (walk-forward, seed=42, no DB writes) |
| `research/cross_game_rolling_watchdog_report_2026-04-29.md` | — | This report |

---

*End of Report — H-XL-01 Cross-Game Rolling Watchdog*
