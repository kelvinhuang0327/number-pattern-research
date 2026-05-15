# DAILY_539 4000p / Full-History Long-Window Validation Report

**Research IDs**: H-LW-01 (4000p + full-history), H-LW-02 (rolling 500p trend)
**Run date**: 2026-04-29 10:40:19
**Script**: `research/daily539_4000p_full_history_validation_2026-04-29.py`

---

## 1. Executive Summary

**Final Status: STABLE_LONG_WINDOW**

- Active strategy (`acb_markov_midfreq_3bet`) evaluated at [3000, 4000, 5000]p windows
- 4000p active edge: **+3.77 pp**
- Full-history (5000p) active edge: **+3.68 pp**
- DEGRADED threshold: +2.00 pp
- Watchdog threshold breached at 4000p: **False**
- CUSUM classification: **SMOOTH_DECAY**
- Rolling 500p breach rate: **40.7%** (11/27 windows)
- CTO review required: **False**

---

## 2. Data Coverage

- Lottery type   : `DAILY_539`
- Total draws    : 5844
- Oldest date    : 2007/01/01
- Newest date    : 2026/04/23
- Skipped/dupes  : 0
- Max backtest   : 5744p
- DB             : `lottery_api/data/lottery_v2.db` (READ-ONLY)
- No writes to DB: CONFIRMED

---

## 3. Long Window Result Table

| Window | Active Edge (pp) | Shadow Edge (pp) | Baseline Edge (pp) | Active vs Shadow | Active vs Baseline | CI (active, 95%) | Watchdog |
|---|---|---|---|---|---|---|---|
| 3000p | +4.50 | +3.23 | +1.77 | +1.27 | +2.73 | [33.33, 36.70] | OK |
| 4000p | +3.77 | +2.61 | +1.28 | +1.16 | +2.50 | [32.80, 35.73] | OK |
| 5000p | +3.68 | +2.24 | +1.00 | +1.44 | +2.68 | [32.90, 35.54] | OK |

**Edge trend slope**: -0.41 pp / 1000 draws  (monotonic decline: True)

---

## 4. Rolling 500p Edge Trend

Rolling window size: 500p, step: 200 draws, total windows: 27

| # | Start Date | End Date | Active Edge | Shadow Edge | Baseline Edge | A−S | Breach |
|---|---|---|---|---|---|---|---|
| 0 | 2007/01/01 | 2008/11/28 | +5.50 | +2.71 | +1.10 | +2.79 | no |
| 1 | 2007/10/08 | 2009/09/04 | +0.90 | +0.66 | +0.00 | +0.24 | YES |
| 2 | 2008/07/14 | 2010/06/11 | -0.10 | +0.06 | -1.60 | -0.16 | YES |
| 3 | 2009/04/20 | 2011/03/05 | +2.10 | +1.26 | -1.80 | +0.84 | no |
| 4 | 2010/01/25 | 2011/10/25 | +1.70 | +0.26 | -1.40 | +1.44 | YES |
| 5 | 2010/11/01 | 2012/06/14 | +3.90 | +1.46 | -0.20 | +2.44 | no |
| 6 | 2011/07/01 | 2013/02/02 | +7.10 | +3.66 | +2.80 | +3.44 | no |
| 7 | 2012/02/20 | 2013/09/24 | +3.70 | +1.46 | +0.40 | +2.24 | no |
| 8 | 2012/10/10 | 2014/05/15 | +1.30 | +0.06 | -0.40 | +1.24 | YES |
| 9 | 2013/05/31 | 2015/01/03 | +1.90 | -0.54 | -1.40 | +2.44 | YES |
| 10 | 2014/01/20 | 2015/08/25 | +0.90 | -1.94 | -1.00 | +2.84 | YES |
| 11 | 2014/09/10 | 2016/04/14 | +1.90 | +1.06 | +0.00 | +0.84 | YES |
| 12 | 2015/05/01 | 2016/12/03 | +2.10 | +1.86 | +0.60 | +0.24 | no |
| 13 | 2015/12/21 | 2017/07/25 | +3.10 | +2.26 | +0.60 | +0.84 | no |
| 14 | 2016/08/10 | 2018/03/15 | +1.90 | +1.46 | +1.40 | +0.44 | YES |
| 15 | 2017/03/31 | 2018/11/03 | +2.10 | +2.26 | +2.20 | -0.16 | no |
| 16 | 2017/11/20 | 2019/06/25 | +1.50 | +1.46 | +2.20 | +0.04 | YES |
| 17 | 2018/07/11 | 2020/02/13 | +1.30 | +1.06 | +1.20 | +0.24 | YES |
| 18 | 2019/03/01 | 2020/10/03 | +1.90 | -0.14 | -1.00 | +2.04 | YES |
| 19 | 2019/10/21 | 2021/05/25 | +4.90 | +0.26 | -0.60 | +4.64 | no |
| 20 | 2020/06/10 | 2022/01/13 | +7.10 | +2.66 | +2.60 | +4.44 | no |
| 21 | 2021/01/29 | 2022/09/03 | +7.70 | +3.66 | +2.80 | +4.04 | no |
| 22 | 2021/09/20 | 2023/04/25 | +10.30 | +6.46 | +3.00 | +3.84 | no |
| 23 | 2022/05/11 | 2023/12/14 | +7.90 | +5.06 | +3.00 | +2.84 | no |
| 24 | 2022/12/30 | 2024/08/03 | +3.50 | +3.26 | +2.80 | +0.24 | no |
| 25 | 2023/08/21 | 2025/03/21 | +3.10 | +4.26 | +3.00 | -1.16 | no |
| 26 | 2024/04/10 | 2025/11/10 | +4.50 | +5.46 | +2.80 | -0.96 | no |

**Rolling summary**:
- Total windows : 27
- Breach (≤+2.0pp): 11 (40.7%)
- Edge range    : [-0.10, +10.30] pp
- Mean edge     : +3.47 pp

---

## 5. Change Detection

- CUSUM break index   : 22
- Break date          : 2021/09/20
- Pre-break mean edge : +2.93 pp
- Post-break mean edge: +5.86 pp
- Shift magnitude     : +2.93 pp
- Bootstrap p (post<pre): 0.9855
- Classification      : **SMOOTH_DECAY**
- Rolling slope       : +0.1396 pp/window (p=0.0269)

---

## 6. Statistical Tests

### Window: 4000p

| Comparison | McNemar p | Perm p | Delta (pp) |
|---|---|---|---|
| Active vs Shadow   | 0.0000 | 0.0000 | +1.16 |
| Active vs Baseline | 0.0000   | 0.0000   | +2.50 |

### Window: 5000p

| Comparison | McNemar p | Perm p | Delta (pp) |
|---|---|---|---|
| Active vs Shadow   | 0.0000 | 0.0000 | +1.44 |
| Active vs Baseline | 0.0000   | 0.0000   | +2.68 |

---

## 7. Watchdog Interpretation

| Question | Answer |
|---|---|
| Is DAILY_539 still WATCH_MAINTENANCE? | YES — no change to status |
| Is DEGRADED threshold (≤+2.0pp) breached at 4000p? | NO |
| Is DEGRADED threshold breached at full history (5000p)? | NO |
| Should active strategy remain unchanged? | YES |
| Should CTO review be triggered? | NO |

---

## 8. Risk / Leakage Check

| Check | Status |
|---|---|
| Chronological split (no shuffle) | PASS — windows use last N draws in order |
| No future leakage (strategy sees only past draws) | PASS — walk-forward: `hist = draws[:i]` |
| No writes to lottery_v2.db | PASS — READ ONLY (sqlite3, no execute writes) |
| No active_strategy_state modification | PASS — monitoring/reporting only |
| No new strategy family | PASS — existing strategies only |
| No Fourier / Markov variants introduced | PASS |
| seed=42 for all bootstrap/permutation | PASS |

---

## 9. Next Step

**STABLE_LONG_WINDOW** — continue weekly / every-50-draws watchdog monitoring.

- Rerun this script every 50 new DAILY_539 draws or weekly, whichever is sooner.
- Watchdog trigger remains: 3000p or long-window active edge ≤ +2.0pp.
- No strategy change required.

---

*Report generated: 2026-04-29 10:40:19*
*Script: `research/daily539_4000p_full_history_validation_2026-04-29.py`*
*Lane: EXPLORE-C (long_window_residual)*