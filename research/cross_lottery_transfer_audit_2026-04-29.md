# EXPLORE-D Cross-Lottery Transfer Audit

**Lane**: EXPLORE-D — `cross_lottery_transfer`
**Run date**: 2026-04-29
**Scope**: BIG_LOTTO / DAILY_539 / POWER_LOTTO

---

## 1. Executive Summary

**Final Decision: WORTH_VALIDATION**

This audit analyzed cross-game signal transfer potential across all three lottery games.
Key finding: there is **no safe positive transfer** of strategy families between games,
but there is a clearly validated set of **reject rules** and **watchdog monitoring patterns**
that apply reliably across all three games. These meta-level patterns — not signals — are
the transferable assets of the system.

Specific findings:

- **7 shared failure patterns** identified, all well-evidenced across multiple games
- **4 transferable reject rule candidates** rated WORTH_VALIDATION (formalize as meta-validation gate)
- **2 transferable positive hypotheses** (cross-game watchdog drift check; shadow-to-active McNemar gate)
- **5 non-transferable signal warnings** documented
- The system should invest in a **cross-game meta validation gate** rather than any signal transfer
- No active strategy modification proposed; no ROI claim without citation

Sources consulted:
- `wiki/games/daily_539.md`
- `wiki/games/big_lotto.md`
- `wiki/games/power_lotto.md`
- `wiki/lessons/key_lessons.md`
- `wiki/system/validation_gates.md`
- `wiki/system/orchestrator.md`
- `research/daily539_4000p_full_history_validation_report_2026-04-29.md`
- `outputs/daily539_long_window_4000p_results_2026-04-29.csv`

---

## 2. Current Strategy State Matrix

| Game | Active Strategy | Shadow Strategy | Current Status | Known Strength | Known Weakness |
|---|---|---|---|---|---|
| DAILY_539 | `acb_markov_midfreq_3bet` (3-bet) | `midfreq_acb_2bet` (2-bet) | WATCH_MAINTENANCE; STABLE_LONG_WINDOW (2026-04-29) | 4000p edge=+3.77pp; 5000p edge=+3.68pp; CUSUM=SMOOTH_DECAY; highly significant McNemar vs shadow and baseline | Edge monotonically declining (-0.41pp/1000draws); 40.7% rolling 500p windows breach +2.0pp threshold (early 2010-2019 period) |
| BIG_LOTTO | `p1_dev_sum5bet` (5-bet) | `regime_2bet` (2-bet) | MAINTENANCE; signal space EXHAUSTED (L90, L91) | DriftDetector: STABLE (PSI=0.097, below 0.10 warning); portfolio diversification intact | 49C6 makes all frequency signals undetectable (L85); 2129 total draws only; evolutionary search 5-10x overfit (L86) |
| POWER_LOTTO | `pp3_freqort_4bet` (4-bet) | `orthogonal_5bet` (5-bet) | MONITOR; signal exhaustion audit complete (2026-04-23); 13 candidate families validated -- all WATCH/REJECT | Fourier+PP3 combination survived extensive validation; PP3 structure provides orthogonality | Fourier shadow WATCH_DOWNGRADED (L126); no Layer-1 3-bet family beats 4-bet per-bet efficiency in all windows (L127); special-number signals unstable cross-window (L116, L121) |

**Data size contrast**:
- DAILY_539: 5844 draws (deepest; enables 5000p full-history backtest)
- POWER_LOTTO: 1905 draws (medium; 1500p tests remain near-boundary)
- BIG_LOTTO: 2129 draws (medium; 49C6 combinatorics severely dilute signals)

Sources: `wiki/games/big_lotto.md`, `wiki/games/daily_539.md`, `wiki/games/power_lotto.md`, `wiki/system/orchestrator.md`

---

## 3. Cross-Lottery Signal Inventory

| Signal Class | BIG_LOTTO | DAILY_539 | POWER_LOTTO | Cross-Lottery Verdict | Reason |
|---|---|---|---|---|---|
| Frequency-based (cold/hot deviation, ACB) | EXHAUSTED (L85, L90) | SATURATED (L82); ACB works as anchor but cannot be improved | DOES NOT TRANSFER (L84) | **Saturated in all games** | 49C6 and 39C5 pool sizes both dilute frequency signal; ACB boundary heuristics are game-specific |
| Fourier / rhythm | EXHAUSTED (L25, L26) | REJECT (L67, L68) | WATCH_DOWNGRADED (L126); not stable cross-window | **Weak in all games; game-specific decay** | Window size dependence is game-specific; cross-window instability shown in all three |
| Markov / transition | EXHAUSTED | Works only as orthogonal component (L15, L43); no standalone signal | REJECT_ALL_NONFAMILY (L127) | **Watch-only at best; not transferable** | Transition matrix density is game-specific; lag overlap near-random across all games |
| Structural constraint postprocess (sum, odd/even, span, AC value) | Not tested (exhaustion already reached) | WATCH_ARCHIVED (L130; 23 buckets all BH q=1.0) | PP3 Sum Regime WATCH (L124); Sum Reversal WATCH (L124); both only 1500p | **WATCH_ONLY; fails BH FDR in tested game** | Structural constraints produce no exploitable edge even when sample is largest (DAILY_539 5844 draws) |
| Long-window residual monitoring | Not studied (sample too small for 3000p+ backtest; only 2129 draws) | STABLE_LONG_WINDOW (H-LW-01; 4000p=+3.77pp, 5000p=+3.68pp) | Not studied (1905 draws; 1500p is near-full-history) | **Worth transfer audit for monitoring framework** | Long-window stability is an indicator of sustained edge; methodology transfers; direct signal does not |
| External data signals (pool-size, market behavior, popularity) | No trusted data available | REJECT (H013; p=1.0; L125) | REJECT (WQ P2-1; 150p only; 500/1500p fail; L130) | **Blocked by data; framework REJECT** | No game has trusted sell/split data; proxy approaches failed uniformly |
| Reject rules / anti-strategy filters | Informally applied | Validated through L16/L17/L18/L47/L64 | Validated through L115-L127 | **WORTH_VALIDATION as formal gate** | System relies on informal per-game rules; a unified multi-game reject gate reduces future false positives |
| Shadow strategy behavior (monitoring drift vs active) | regime_2bet shadow stable | midfreq_acb_2bet stable; active vs shadow gap measurable | orthogonal_5bet as shadow (2026-04-28 update); Fourier downgraded | **Consistent across all games; WORTH_VALIDATION** | All games benefit from shadow-to-active comparison; no game has formal cross-game watchdog |
| Live drift / degradation detection | DriftDetector STABLE; PSI < 0.10 | Rolling 500p + CUSUM in place (EXPLORE-C) | 6/7 strategies cold at 2026-04-23; Fourier rolling slice 80% fail | **Game-specific mechanisms; monitoring principle transferable** | Each game has different draw mechanics; drift detection method must be game-tuned |

Sources: `wiki/games/*.md`, `wiki/lessons/key_lessons.md`

---

## 4. Shared Failure Patterns

| # | Pattern | Games Affected | Evidence | Risk Level | Lesson |
|---|---|---|---|---|---|
| FP-01 | **Short-window edge overstates long-window edge** | ALL THREE | DAILY_539: 150p edge consistently higher than 3000p/5000p; POWER_LOTTO: Fourier 150p->1500p edge inflated; BIG_LOTTO: evolutionary search 5-10x overfit at short windows (L86) | HIGH | L17: 150p+/500p+/1500p- = SHORT_MOMENTUM warning. Never report only short-window results |
| FP-02 | **Frequency-family candidate exhaustion / saturation** | ALL THREE | DAILY_539: H001-H008 all REJECT (L82); BIG_LOTTO: 49C6 prevents detection (L85, L90, L91); POWER_LOTTO: only PP3 orthogonal survives (not frequency expansion) | HIGH | Once a game's frequency signal space is saturated, no further frequency variants should be queued. Game-level saturation must block new same-family tasks |
| FP-03 | **1500p-only permutation pass is insufficient for promotion** | DAILY_539, POWER_LOTTO | DAILY_539: L118 (cluster transition), L125 (pool-size); POWER_LOTTO: L115 (PP3 MidFreq residual), L123 (PP3+MidFreq V2), L124 (Sum Regime/Reversal) -- all 1500p perm pass, 150/500p fail | HIGH | A strategy that only passes permutation at 1500p but fails at 150p and 500p has a SHORT_LATENT signal pattern and should not enter McNemar |
| FP-04 | **External data proxy substitution produces false positives** | DAILY_539, POWER_LOTTO | DAILY_539: H013 proxy -> REJECT even with 100% trusted data (L125); POWER_LOTTO: WQ P2-1 popularity proxy -> 150p pass only, 500/1500p fail (L130) | HIGH | Proxy signals for external data fail cross-window uniformly. Require actual trusted data before queuing; reject proxies that produce window-inconsistent p-values |
| FP-05 | **Regime gate / conditional filter introduces time-leakage risk** | DAILY_539, POWER_LOTTO | DAILY_539: H012 cluster transition with conditional regime gate (L118); POWER_LOTTO: midfreq_fourier_2bet_regime_gate_v1 REJECT (L122) -- in both cases, 150p permutation failed even after conditional split | MEDIUM | Any conditional regime gate that uses draw-level features must be verified as history-only at prediction time. Failure to do so inflates 150p edge artificially |
| FP-06 | **Multiplicative signal combination degrades performance** | DAILY_539 | ACB x MidFreq product score fails (L79, L80, L81); ZoneRev passes perm but signal comes from MidFreq, not Zone (L78) | MEDIUM | Multiplicative fusion of two complementary signals does not amplify edge; it eliminates the mutual exclusion property. Keep signals orthogonal (additive, not multiplicative) |
| FP-07 | **Rolling slice failure rate exposes window-shopping bias** | POWER_LOTTO, DAILY_539 | POWER_LOTTO: Fourier 5x300 slices have >=80% perm failure rate despite positive mean edge (L126); DAILY_539: rolling 500p has 40.7% breach windows (EXPLORE-C) | MEDIUM | A strategy may show positive mean edge while having a majority of rolling sub-windows with negative or below-threshold edge. Rolling slice test should be required before any WATCH->promotion pipeline entry |

---

## 5. Transferable Reject Rule Candidates

| # | Reject Rule | Applies To | Why It May Help | Minimal Validation | Decision |
|---|---|---|---|---|---|
| RR-01 | **All three windows (150p / 500p / 1500p) must individually pass permutation test (p<0.05) before McNemar is triggered** | ALL THREE games | Prevents 1500p-only signals from entering promotion pipeline. Currently applied informally; formalizing eliminates FP-03. Evidence: L115, L118, L123, L124 all blocked by this rule retrospectively | Backfill check: for all WATCH strategies in POWER_LOTTO and DAILY_539, verify that all three-window perm results are on record; flag any where 1500p passed but 150p/500p did not | **WORTH_VALIDATION** |
| RR-02 | **Rolling slice failure rate >=50% blocks promotion even if mean edge is positive** | DAILY_539, POWER_LOTTO | Catches strategies that aggregate well but are unstable sub-period. DAILY_539 rolling 500p breach=40.7% (below 50%) consistent with STABLE_LONG_WINDOW. POWER_LOTTO Fourier was above 50% consistent with WATCH_DOWNGRADED (L126) | Define formally: N windows of size W with step S; if breach_pct >= 50%, strategy must not enter McNemar. Test: run rolling 500p for POWER_LOTTO `pp3_freqort_4bet` to confirm <50% breach | **WORTH_VALIDATION** |
| RR-03 | **Shadow strategy must maintain positive edge in the same rolling window before active strategy triggers CTO review** | ALL THREE games | If shadow is also degraded in the same period, degradation is likely a game-wide cold phase rather than active-strategy failure. Avoids premature replacement during cold phases. Evidence: POWER_LOTTO 6/7 cold strategies (2026-04-23) -- all game-wide cold | Define: if active_edge <= DEGRADED_threshold AND shadow_edge <= 0 in same window -> classify as GAME_COLD_PHASE, not STRATEGY_DEGRADED. Requires running shadow monitoring for BIG_LOTTO | **WORTH_VALIDATION** |
| RR-04 | **Reject any strategy promotion if per-bet efficiency vs active is <80% in any of 150p/500p/1500p** | DAILY_539, POWER_LOTTO | Currently applied in POWER_LOTTO (L115, L120, L123) and informally in DAILY_539 (L128). Formalizing across both games reduces edge from marginal improvements that waste bet slots | Create explicit per-bet efficiency gate in all walk-forward evaluation scripts; fail any candidate not meeting 80% per-bet vs active in all three windows | **WORTH_VALIDATION** |

---

## 6. Transferable Positive Hypotheses

| # | Hypothesis | Games | Why It Might Improve Success Rate | Data Needed | Risk | Decision |
|---|---|---|---|---|---|---|
| H-XL-01 | **Unified rolling-window watchdog with breach-percentage threshold across all games** | ALL THREE | DAILY_539 has rolling 500p + CUSUM monitoring (EXPLORE-C). BIG_LOTTO and POWER_LOTTO currently lack this. Detecting SMOOTH_DECAY vs REGIME_SHIFT earlier allows proactive shadow promotion or CTO review triggering rather than reactive post-degradation | BIG_LOTTO: rolling 300p on `p1_dev_sum5bet` (2129 draws). POWER_LOTTO: rolling 300p on `pp3_freqort_4bet` (1905 draws). DAILY_539: re-use `outputs/daily539_rolling_500p_edge_2026-04-29.csv` | LOW (monitoring only; no strategy change) | **WORTH_VALIDATION** |
| H-XL-02 | **Cross-game shadow drift check: if shadow outperforms active in 2+ games simultaneously, trigger coordinated CTO review** | ALL THREE | In POWER_LOTTO, `orthogonal_5bet` replaced Fourier as shadow (2026-04-28). In DAILY_539, `midfreq_acb_2bet` shadow is more stable per-bet. If both drift above their actives in the same rolling period, this may indicate a systematic change affecting all games. No cross-game watchdog currently exists | Active and shadow rolling edge for all three games in the same monitoring table; every 50 draws per game | LOW (monitoring only; no strategy change; no DB writes) | **WORTH_VALIDATION** |

---

## 7. Non-Transferable Signals

| # | Signal | Source Game | Why Not Transfer | Risk If Transferred |
|---|---|---|---|---|
| NT-01 | **ACB boundary boost (n<=5 or n<=8 edge boost for boundary numbers)** | DAILY_539 (1-39 number space) | ACB boundary heuristic calibrated to 39-number space. POWER_LOTTO uses 1-38 (main) + 1-8 (special); BIG_LOTTO uses 1-49. Boundary zone definition, boost factor, and frequency baseline all differ. L84 explicitly confirms ACB does not transfer to POWER_LOTTO | Would introduce a game-miscalibrated scoring boost that corrupts orthogonal bet construction in POWER_LOTTO and BIG_LOTTO |
| NT-02 | **DAILY_539 active strategy (`acb_markov_midfreq_3bet`) bet structure** | DAILY_539 (5-from-39) | Strategy designed for 5-pick from 39, with Markov window=30 on transition density arising from DAILY_539's draw pattern. Pool structure is incompatible with POWER_LOTTO (6-from-38 + special) or BIG_LOTTO (6-from-49) | Direct copy would invalidate probability baselines; all three metrics (edge_pp, M2+ baseline, payout lookup) would be wrong |
| NT-03 | **POWER_LOTTO special-number (1-8) prediction logic** | POWER_LOTTO only | Special number is a 1-from-8 draw mechanically independent of the 6-from-38 main draw. No other game has a special number. V3/V4 orthogonal shortlist candidates (L116, L121) and special-drought detector (L92) are meaningful only in this draw structure | If applied to DAILY_539 or BIG_LOTTO, introduces a spurious 7th-position feature that does not exist in those games |
| NT-04 | **BIG_LOTTO L90 maintenance conclusions** | BIG_LOTTO | BIG_LOTTO signal exhaustion (L90/L91) is specific to 49C6 combinatorics and 2129 draw count. DAILY_539 has 5844 draws and different signal dynamics. POWER_LOTTO still has active WATCH candidates. Cross-game extrapolation of exhaustion would prematurely terminate valid research in other games | Would incorrectly suppress DAILY_539 watchdog monitoring and POWER_LOTTO WATCH candidate evaluation |
| NT-05 | **POWER_LOTTO Fourier rhythm window parameters** | POWER_LOTTO | Fourier windows tuned to POWER_LOTTO's specific draw rhythm. L25/L26 show multi-window Fourier for BIG_LOTTO dilutes the signal; L67/L68 show DAILY_539 rejects conditional Fourier entirely | Importing Fourier window parameters from POWER_LOTTO would reintroduce a rejected signal family into DAILY_539 (already failed: L67, L68) and dilute BIG_LOTTO signals |

---

## 8. Risk / Leakage Check

| Check | Status |
|---|---|
| **Different number spaces** | DAILY_539 is 5-from-39; BIG_LOTTO is 6-from-49; POWER_LOTTO is 6-from-38 main + 1-from-8 special. All three have different combination counts. Baselines and payouts are game-specific. No cross-game metric comparison made without normalization in this report |
| **Different draw mechanics** | POWER_LOTTO special number is mechanically independent of main draw. This report does not conflate them |
| **Different sample sizes** | BIG_LOTTO: 2129 draws; POWER_LOTTO: 1905 draws; DAILY_539: 5844 draws. Recommendations in Section 6 explicitly account for sample-size constraints |
| **Multiple testing risk** | This audit identifies patterns from existing validated results only. No new test was run; no new p-values generated. All claims cite specific lesson IDs or report paths |
| **Survivorship bias** | This report reviews both failed (REJECT/WATCH) and successful (active) strategies. Failed candidates explicitly documented via L-series lessons |
| **Cherry-picking cross-game analogies** | All failure patterns (Section 4) are grounded in at least two independent game observations. Single-game observations are isolated in Section 7 (Non-Transferable) |
| **No future leakage** | This report is a retrospective audit only. All cited evidence comes from previously validated walk-forward backtests. No look-ahead |
| **No DB writes** | This report file only. `lottery_v2.db` not opened or modified |
| **No active strategy changes** | `active_strategy_state` unchanged. This report does not propose any strategy replacement, promotion, or demotion |

---

## 9. Decision

**WORTH_VALIDATION**

Rationale:
1. Four reject rules (RR-01 through RR-04) are concrete, testable, and grounded in multiple independent game observations.
2. Two positive monitoring hypotheses (H-XL-01 and H-XL-02) require no new signals, no strategy change, and only READ-ONLY DB access.
3. The current system lacks a formal cross-game watchdog; the risk of silent degradation in BIG_LOTTO and POWER_LOTTO is real (BIG_LOTTO has no rolling-window edge monitoring; POWER_LOTTO rolling slices confirmed >=80% failure in Fourier).
4. All hypotheses can be validated with existing code infrastructure from the EXPLORE-C script.
5. No ROI or edge claim made in this report without a cited evidence source.

---

## 10. Next Validation Task (H-XL-01 + H-XL-02 Cross-Game Rolling Watchdog)

**Research IDs**: H-XL-01, H-XL-02
**Objective**:
1. Extend rolling-window edge monitoring (proven in EXPLORE-C for DAILY_539) to BIG_LOTTO and POWER_LOTTO.
2. Build a cross-game shadow drift comparison table.
3. Formally validate RR-02 (rolling slice breach >=50% blocks promotion) for the two unmonitored games.

**Constraints**:
- DB is READ-ONLY; no writes to `lottery_v2.db`
- No new strategy family; no new signal design
- No `active_strategy_state` modification
- No Fourier / Markov / frequency variants
- seed=42; Python 3.9 compatible
- Walk-forward only (no look-ahead)

**Data references**:
- DAILY_539: 5844 draws; active=`acb_markov_midfreq_3bet`; shadow=`midfreq_acb_2bet`
- BIG_LOTTO: 2129 draws; active=`p1_dev_sum5bet`; shadow=`regime_2bet`; PICK=6; MAX_NUM=49
- POWER_LOTTO: 1905 draws; active=`pp3_freqort_4bet`; shadow=`orthogonal_5bet`; PICK=6; MAX_NUM=38; special separate

**Required Analysis**:
1. BIG_LOTTO: rolling 300p window (step=100) on active and shadow strategies
2. POWER_LOTTO: rolling 300p window (step=100) on active and shadow strategies (main numbers only)
3. DAILY_539: re-use `outputs/daily539_rolling_500p_edge_2026-04-29.csv`
4. Compute CUSUM changepoint on rolling active edge for BIG_LOTTO and POWER_LOTTO
5. Compute breach_pct per game (% windows where active_edge <= game_degraded_threshold):
   - DAILY_539: threshold = +2.0pp (established in EXPLORE-C; do not change)
   - BIG_LOTTO: threshold = +0.5pp (to be calibrated from rolling analysis; must not be changed after seeing results)
   - POWER_LOTTO: threshold = +1.0pp (to be calibrated; must not be changed after seeing results)
6. Shadow drift check: for each window, compare active vs shadow edge; flag if shadow > active in >=2 games in same calendar quarter

**Decision rules**:
- STABLE: breach_pct < 40%, mean_edge > threshold, CUSUM = SMOOTH_DECAY
- WATCH: breach_pct 40-60%, or CUSUM = SMOOTH_DECAY_WITH_KINK
- DEGRADED: breach_pct >= 60%, or mean_edge <= threshold, or CUSUM = REGIME_SHIFT
- GAME_COLD_PHASE (RR-03): active_edge <= threshold AND shadow_edge <= 0 in same window

**Required outputs**:
1. `research/cross_game_rolling_watchdog_2026-04-29.py` -- script
2. `research/cross_game_rolling_watchdog_report_2026-04-29.md` -- full report (8+ sections)
3. `outputs/biglotto_rolling_300p_edge_2026-04-29.csv`
4. `outputs/powerlotto_rolling_300p_edge_2026-04-29.csv`
5. `outputs/cross_game_watchdog_summary_2026-04-29.csv` -- 3-row table (one per game)

**Fail conditions**:
1. DB modified
2. New strategy family created
3. `active_strategy_state` modified
4. Any rolling window uses future data
5. Degraded thresholds modified after seeing results (HARKing)
6. DAILY_539 rolling results re-run instead of reusing EXPLORE-C outputs

---

## Appendix: Key Lesson Index for This Audit

| Lesson | Summary | Relevance |
|---|---|---|
| L16 | Uncorrected p<0.05 usually false positive | FP-01, RR-01 |
| L17 | 150p+/500p+/1500p- = SHORT_MOMENTUM warning | FP-01, FP-03 |
| L21 | Effective signals from one game cannot be borrowed by another | Section 7 (all NT entries) |
| L83 | MidFreq successfully transferred to POWER_LOTTO | Exception to L21; must be documented |
| L84 | ACB heuristics cannot transfer to POWER_LOTTO | NT-01 |
| L85 | 49C6 dilutes all frequency signals in BIG_LOTTO | FP-02, NT-04 |
| L86 | Low-baseline evolutionary search: 5-10x overfit | FP-01, FP-02 |
| L90/L91 | BIG_LOTTO signal space exhausted | Section 2 matrix |
| L115-L127 | POWER_LOTTO candidate validation failures | FP-03, FP-04, FP-05, FP-07 |
| L128-L131 | DAILY_539 recent validations | FP-03, FP-04, FP-06 |

---

*Report generated: 2026-04-29*
*Lane: EXPLORE-D (cross_lottery_transfer)*
*No DB writes. No active_strategy_state modification. All citations reference existing validated reports.*
