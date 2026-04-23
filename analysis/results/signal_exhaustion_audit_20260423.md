# Signal Exhaustion Audit (2026-04-23)

**Audit Date**: 2026-04-23T15:59:40+08:00  
**Scope**: Three-game signal exhaustion review (BIG_LOTTO / DAILY_539 / POWER_LOTTO)  
**Methodology**: Cross-reference wiki game status, key lessons, and 20260423 validation artifacts

---

## Overall Conclusion

### **[SIGNAL_EXHAUSTED_ALL]**

All three lottery games have exhausted their actionable research directions within the current validation framework and data availability. No strategy candidate qualified for promotion in the 2026-04-23 cycle, and all remaining WATCH/PROVISIONAL paths show systemic inability to clear full-window validation gates.

---

## Game-by-Game Assessment

### 1. BIG_LOTTO

**Current Status**: `MAINTENANCE_MODE`

**Evidence**:
- **L90**: "BIG_LOTTO 全信號空間窮盡，進入維護模式" (full signal space exhausted, maintenance mode)
- **L91**: "完整信號邊界研究顯示 49C6 與公fair隨機不可區分" (complete signal boundary study shows 49C6 indistinguishable from fair random)
- **wiki/games/big_lotto.md**: Explicitly states maintenance mode with only reference strategies for monitoring
- **Artifact**: `analysis/results/biglotto_monitor_500p_20260423.md`
  - Overall status: `DOWNGRADE_TRIGGERED`
  - Recommendation: `SHADOW_ONLY` (no next McNemar candidate)
  - Both `p1_deviation_4bet` and `p1_dev_sum5bet` show downgrade triggers on recent_150 window

**Remaining Research Directions**: None actionable
- No new external signals identified
- No new rules/pool changes
- All frequency-based signal families exhausted
- MicroFish attempt (L89) failed to salvage low-base-rate structure

**Recommendation**: Maintain current 2/3/5-bet reference strategies for monitoring only; no new research allocation.

---

### 2. DAILY_539

**Current Status**: `MAINTENANCE_MODE`

**Evidence**:

**Frequency Family (H001~H008)**: All REJECT
- **L82**: "H001~H008 全軍覆沒，539 頻率族信號空間已高度飽和" (H001-H008 all failed, frequency family signal space saturated)

**Recent Hypothesis Tests (2026-04-22 / 2026-04-23)**:

1. **H011 (Weekday/Calendar Regime)**
   - **Status**: REJECT ✓
   - **Evidence**: wiki/games/daily_539.md (line 7)
   - **Key Finding**: Weekday global chi-square p=0.9281; calendar overlay 150/500p permutation unmet; no McNemar trigger
   - **Lesson**: L117 references this class: weekday/calendar overlays lack stable orthogonal signals

2. **H012 (Cross-Draw Cluster/Transition)**
   - **Status**: REJECT ✓
   - **Evidence**: wiki/games/daily_539.md (line 8)
   - **Key Finding**: lag-1/2/3 overlap ≈ random baseline; raw edge only in 1500p; 150/500p permutation unmet
   - **Lesson**: L118 covers this: cross-draw transitions fail 150/500p gates despite 1500p raw edge

3. **H013 (Pool-Size / Market-Behavior)**
   - **Status**: REJECT ✓ (just completed)
   - **Evidence**: `analysis/results/daily539_h013_backfill_final_report_20260423.md`
   - **Data Status**: 100% backfill completed from official Taiwan Lottery API (sell_amount, total_amount)
   - **Key Finding**: 
     - H013: edge≈0%, p=1.0, d≈0 (all windows)
     - H013b: similar null findings
     - H013c: similar null findings
     - **Verdict**: Pool-size provides no orthogonal predictive signal; not a data problem but fundamental hypothesis failure
   - **Lesson**: L129 (new, added to key_lessons.md) documents this outcome

4. **MicroFish+MidFreq 2-bet Promotion**
   - **Status**: REJECT ✓
   - **Evidence**: `analysis/results/daily539_microfish_midfreq_promotion_validation_20260423.json`
   - **Key Finding**:
     - 150p McNemar vs `midfreq_acb_2bet`: p=0.1797 (insufficient, need <0.05)
     - All three windows passed raw edge, permutation, and per-bet efficiency checks individually
     - BUT 150p McNemar failed to demonstrate stable replacement advantage
   - **Lesson**: L128 explicitly covers this: even when all gates pass individually, McNemar must confirm stability

**Current Active Strategies**: 
- `acb_1bet`, `midfreq_acb_2bet`, `acb_markov_midfreq_3bet`
- All three strategies remain unchanged post-validation
- No candidate qualified for advancement

**Remaining Research Directions**: None actionable
- H001~H008 (frequency): exhausted
- H011 (weekday/calendar): REJECT, no new axis per L117
- H012 (cluster): REJECT, no new axis per L118
- H013 (pool-size): REJECT confirmed, 100% data verified, no new hypothesis per L129
- MicroFish path: REJECT, no improvement vector identified
- L82 explicitly gates further frequency work: "existing strategies preserve stability"

**Recommendation**: Maintain `acb_1bet`, `midfreq_acb_2bet`, `acb_markov_midfreq_3bet` with continuous McNemar monitoring; do not initiate new frequency-based or pool-size variants.

---

### 3. POWER_LOTTO

**Current Status**: `MATURE_MONITORING`

**Evidence**:

**Mainline (Active Strategies)**:
- `fourier_rhythm_3bet` (3 bets): Recent downgrade triggered
- `pp3_freqort_4bet` (4 bets): Primary strategy, unchanged
- `orthogonal_5bet` (5 bets): Reference

**Recent Validations (2026-04-23 cycle)**:

1. **Fourier Rhythm 3-bet Downgrade Decision**
   - **Status**: WATCH (downgraded priority)
   - **Evidence**: `analysis/results/power_watch_downgrade_decision_20260423.json`
   - **Key Finding**:
     - 150/500p permutation failed (p=0.4975 / 0.2537)
     - 1500p permutation passed (p=0.0100)
     - Failure-aware 5x300 rolling slices: 80% permutation failure ratio
     - Not replaced by `pp3_freqort_3bet` (McNemar not triggered)
   - **Lesson**: L126 applies: WATCH with 1500p signal but ≥80% rolling failure → downweight priority
   - **Action**: Maintain WATCH but lower priority; no replacement

2. **PP3 Frequency+Orthogonal 3-bet (B-scheme, history-only)**
   - **Status**: WATCH
   - **Evidence**: `analysis/results/power_watch_downgrade_decision_20260423.json`
   - **Key Finding**:
     - 150p efficiency: 79.9% < 80% threshold
     - 150/500p permutation not passed
     - McNemar not triggered; `pp3_freqort_4bet` remains active
   - **Lesson**: L120 applies: history-only reweighting with unmet efficiency gates → WATCH only
   - **Action**: Continue monitoring; do not promote

3. **PP3 Sum Regime / Sum Reversal (2026-04-23)**
   - **Status**: WATCH
   - **Evidence**: `analysis/results/power_pp3_sum_regime_validation_20260423.json`
   - **Key Finding**:
     - Both regime detectors only pass 1500p permutation
     - 150/500p permutation: p=0.1791~0.3085 (unmet)
     - Per-bet efficiency vs 4-bet: 68.2%~102.2% (mixed)
     - McNemar not triggered
   - **Lesson**: L124 applies: 200p monitoring + 1500p signal but 150/500p gates unmet + mixed efficiency → WATCH only, no McNemar
   - **Action**: Continue monitoring; do not upgrade

4. **MidFreq+Fourier 2-bet Regime Gate V1 (2026-04-23)**
   - **Status**: REJECT
   - **Evidence**: `analysis/results/power_midfreq2bet_regime_gate_v1_20260423.json`
   - **Key Finding**:
     - History-only fixed gate (cold_residual_60 / hot_residual_60)
     - 150p permutation: p=0.0995 (≥0.05, failed)
     - No entry to 500p McNemar verification
   - **Lesson**: L122 applies: regime gate, positive raw edges, but 150p perm unmet → direct REJECT, not stable signal
   - **Action**: Do not retry this family

5. **PP3+MidFreq Orthogonal V2 (2026-04-23)**
   - **Status**: WATCH / REJECT (mixed)
   - **Evidence**: `analysis/results/power_pp3_midfreq_orthogonal_v2_20260423.json`
   - **Key Finding**:
     - 6 history-only candidates (3bet/4bet mix)
     - Best: `pp3_midfreq_residual_strata_4bet` 
       - 150/500p permutation unmet (p=0.5224 / 0.1741)
       - 1500p permutation: p=0.0448 (passed)
       - Per-bet efficiency: 71.4% / 73.1% / 65.4% (all <80%)
     - No candidate enters McNemar
   - **Lesson**: L123 applies: only 1500p perm signal + 150/500p unmet + efficiency <80% → WATCH or REJECT, no upgrade
   - **Action**: 5 WATCH, 1 REJECT; no mainline changes

6. **Non-Family Layer-1 3-bet (4 new structural families, 2026-04-23)**
   - **Status**: REJECT_ALL
   - **Evidence**: `analysis/results/power_layer1_nonfamily_3bet_validation_20260423.json`
   - **Key Finding**:
     - 4 families tested: dispersion, odd-tail, zone tensor, residue stability
     - All completed 150/500/1500p validation + leakage check PASS
     - Best raw edges maintained across windows (residue: +2.17% / +3.23% / +1.77%)
     - BUT: permutation p = 0.2587~0.5871 / 0.1194~0.5871 / 0.2189~0.4726 (no window fully <0.05)
     - Per-bet efficiency: none pass 80% across all windows vs `pp3_freqort_4bet`
     - McNemar not triggered
   - **Lesson**: L127 explicitly covers: even multi-candidate raw edge coverage + three-window test, if no candidate fully passes perm + efficiency gates → `REJECT_ALL_NONFAMILY_LAYER1_3BET`
   - **Action**: Conclude nonfamily Layer-1 3-bet line; next should be new feature source or new validation framework

7. **Special V3 Orthogonal Shortlist (2026-04-22)**
   - **Status**: WATCH
   - **Evidence**: `analysis/results/power_special_v3_research_20260422.json` (reference in wiki)
   - **Key Finding**: Three top2 candidates all show raw edge across windows but permutation p unmet on all windows
   - **Lesson**: L116 applies: raw edge all positive but permutation gates unmet → WATCH only, not upgrade
   - **Action**: Do not promote

8. **Special V4 Orthogonal Reinforcement (2026-04-23)**
   - **Status**: REJECT
   - **Evidence**: `analysis/results/power_special_v4_validation_20260423.json`
   - **Key Finding**:
     - Best V3-based candidate: +5.67% / +1.20% / +1.80% raw edge
     - Permutation: p=0.0796 / 0.2836 / 0.0547 (not all <0.05)
     - Current V3 top2 baseline: +11.67% / +4.40% / +2.33% (candidates don't exceed)
     - McNemar not triggered
   - **Lesson**: L121 applies: V3-based V4 reweight, even near-pass perm (p=0.0547), no baseline beat → REJECT, not same-family microadj
   - **Action**: Do not continue same-family V4 microtweaks

9. **Winning Quality P2-1 (2026-04-23)**
   - **Status**: REJECT
   - **Evidence**: `analysis/results/power_wq_p21_validation_20260423.md`
   - **Key Finding**:
     - 150p: raw edge +12.01%, perm p=0.0667 (borderline), d=1.281 (only window passing d>1)
     - 500p: perm p=0.6333, d=-0.246 (both fail)
     - 1500p: perm p=0.8000, d=-0.935 (both fail)
     - Per-bet efficiency mixed: 163.6% / 130.3% / 112.0%
     - Leakage check: PASS
   - **Lesson**: L130 (new, added) documents this: popularity_score proxy shows signal instability across windows; without real prize-payout data, cannot form valid cross-window signal
   - **Action**: Do not retry same approach; would require real commerce data, not model proxy

**Remaining WATCH Strategies**:
- `fourier_rhythm_3bet` (downgraded priority)
- `pp3_freqort_3bet` (history-only B-scheme)
- PP3 Sum Regime / Sum Reversal (2 variants)
- PP3+MidFreq Orthogonal V2 (5 candidates)
- Special V3 shortlist (3 candidates)

**None of these WATCH candidates qualified for McNemar replacement testing**, indicating they cannot demonstrate stable improvement over active mainline strategies within the validation framework.

**Remaining Research Directions**: None actionable
- Fourier / PP3 family: all variants tested, none exceed mainline
- MidFreq integration: regime-gating and orthogonal attempts all fail short-window gates
- Special (V3/V4): exhausted reweighting approaches; no baseline beat
- Non-family Layer-1 3-bet: 4-family exhaustive search complete with REJECT_ALL verdict
- WQ / commercial filters: signal instability across windows without real data

**Recommendation**: 
- Maintain active `fourier_rhythm_3bet` + `pp3_freqort_4bet` + `orthogonal_5bet` structure
- Continue shadow monitoring of WATCH candidates (fourier downgraded, others lower priority)
- Do NOT initiate new Power Lotto research unless:
  - New external feature source (not proxy-based)
  - Documented rule/pool size change
  - Fundamentally new signal family (not orthogonal to existing PP3/Fourier/MidFreq)

---

## Cross-Game Validation Summary

| Game | Status | Reasons for Exhaustion |
|------|--------|------------------------|
| BIG_LOTTO | SIGNAL_EXHAUSTED | L90/L91 confirm: 49C6 geometry destroys all frequency signals; MicroFish (L89) failed; maintenance mode stable |
| DAILY_539 | SIGNAL_EXHAUSTED | H001~H008 done; H011/H012/H013 all properly REJECT; MicroFish path unimprovable (McNemar unmet); frequency space saturated (L82) |
| POWER_LOTTO | SIGNAL_EXHAUSTED | Mainline mature (Fourier+PP3+Orthogonal); all extensions (MidFreq gate, Special V4, nonfamily Layer-1) REJECTED or WATCH-only; no McNemar entry for any candidate |

---

## Recent Failed Directions (Do Not Retry)

These failures stem from **validation gate failures**, not external blockers:

1. **Governance / Quota Fallback (Issue #63, #67)**: Not a research gap; environment governance issue. Archived 2026-04-22.
2. **BIG_LOTTO 500p Local Monitoring (Issue #65, #66)**: Quota blocking, not strategy gap. Will not reopen absent external environment fix.
3. **POWER_LOTTO WQ P2-1**: Completed validation cycle with clear REJECT verdict (permutation instability across windows). Do not retry without real commerce data.
4. **DAILY_539 H013 Pool-Size**: 100% data backfill completed; formal test confirms hypothesis failure (p=1.0 edge≈0). Do not retry same family.
5. **POWER_LOTTO Nonfamily Layer-1 3-bet**: 4-family exhaustive search completed with REJECT_ALL. Do not retry same structural families.

---

## Blocked Recent Failures (Execution Quality)

These were not research gaps but external execution issues:

| Item | Issue | Root | Status |
|------|-------|------|--------|
| Governance quota/rate-limit cycles | #63, #67 | Environment quota management | Documented, do not reopen strategy work until env fixed |
| Big Lotto 500p monitor local fallback | #65, #66 | API quota / rate-limit blocking | Documented, do not reopen strategy work until env fixed |

---

## Actionable Next Steps (if any)

**For all three games**: No actionable research directions remain within current:
- Validation framework (150/500/1500p windows, permutation tests, McNemar gates, per-bet efficiency thresholds)
- Data availability (all current sources exhausted; H013 pool-size fully backfilled and tested)
- Hypothesis families (frequency, pool-size, cross-draw temporal, special V3/V4, popularity filters)

**Potential Future Triggers** (not actionable now):
1. External lottery rule changes (odds, pool structure, draw frequency)
2. New authenticated data source (real prize-payout records, not popularity proxies)
3. New mathematical signal family (currently, all tested families derive from PP3/Fourier/MidFreq orthogonal axes)

---

## Evidence Artifacts Referenced

### BIG_LOTTO
- wiki/games/big_lotto.md (L90/L91, maintenance mode declaration)
- memory/lessons.md (L85, L86, L89, L90, L91)
- analysis/results/biglotto_monitor_500p_20260423.md (downgrade triggers, no McNemar)

### DAILY_539
- wiki/games/daily_539.md (H011/H012/H013 REJECT declarations, 2026-04-22/04-23)
- analysis/results/daily539_h013_backfill_final_report_20260423.md (100% data, REJECT verdict)
- analysis/results/daily539_microfish_midfreq_promotion_validation_20260423.json (McNemar p=0.1797)
- memory/lessons.md (L73~L82, L117~L118, L125, L128~L129)

### POWER_LOTTO
- wiki/games/power_lotto.md (strategy table, WATCH/PROVISIONAL status, recent 2026-04-23 updates)
- analysis/results/power_watch_downgrade_decision_20260423.json (Fourier/PP3 3bet downgrade & WATCH)
- analysis/results/power_pp3_sum_regime_validation_20260423.json (Sum Regime/Reversal WATCH)
- analysis/results/power_pp3_midfreq_orthogonal_v2_20260423.json (6 candidates, WATCH/REJECT mix)
- analysis/results/power_midfreq2bet_regime_gate_v1_20260423.json (regime gate REJECT)
- analysis/results/power_layer1_nonfamily_3bet_validation_20260423.json (4-family REJECT_ALL)
- analysis/results/power_special_v4_validation_20260423.json (V4 REJECT)
- analysis/results/power_wq_p21_validation_20260423.md (WQ P2-1 REJECT)
- memory/lessons.md (L87, L88, L93, L115~L127, L130)

---

## Handoff Actions

Since **[SIGNAL_EXHAUSTED_ALL]** conclusion is confirmed, the following wiki updates are required:

1. **wiki/games/big_lotto.md**: Add note confirming maintenance mode, no new actionable signals identified in 2026-04-23 audit.
2. **wiki/games/daily_539.md**: No strategy table changes; H013 now formally REJECT; MicroFish promotion remains declined.
3. **wiki/games/power_lotto.md**: Fourier 3bet marked WATCH_DOWNGRADED; all other recent candidatesStatus remains WATCH or REJECT; no mainline changes.
4. **wiki/lessons/key_lessons.md**: 
   - Verify L129 exists (new, pool-size exhaustion lesson)
   - Add L131+ capturing this audit conclusion: "Three games exhausted signal space under current framework; next research requires new data source, rule change, or orthogonal hypothesis family."

---

## Conclusion

All three lottery games have exhausted their research frontiers within the established validation gates and data availability. The audit confirms:

- **BIG_LOTTO**: Maintenance mode stable; L90/L91 validated.
- **DAILY_539**: Maintenance mode stable; all major hypothesis families (H001~H008, H011, H012, H013, MicroFish) properly disposed of.
- **POWER_LOTTO**: Mature monitoring state; mainline strategies unchanged; all extension paths (MidFreq, Special, nonfamily, WQ) exhausted with WATCH/REJECT verdicts.

**No further strategy research is recommended without introduction of new external signals, data sources, or lottery rule changes.**

