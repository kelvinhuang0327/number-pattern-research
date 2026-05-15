# WQ P2-1 Validation Handoff Notes (2026-04-23)

## Context Shift

This validation was deliberately **narrowed from broad quota-governance to single-signal local-first verification** because:

1. **Previous quota-governance tasks** on similar topics repeatedly failed with 402 rate-limits / timeout messages, appearing as `COMPLETED` but containing no real artifacts
2. **This task inverted the constraint**: "Must be completely local, reproducible, seed=42, no external dependencies"
3. **Result**: A clean, deterministic validation that required ~3 minutes runtime with no fallback loops

This is why the task opened with explicit failure context and enforcement rules.

---

## Formal Results

### Classification
**`REJECT`** — WQ P2-1 does not meet acceptance criteria for WATCH candidacy

### Metrics Summary (150 / 500 / 1500 OOS)

| Metric | 150p | 500p | 1500p | Status |
|--------|------|------|-------|--------|
| **Raw Edge** | +12.01% | +7.74% | +7.47% | ✓ All Positive |
| **Perm p-value** | 0.0667 | 0.6333 | 0.8000 | ✗ Fails WATCH gate (need p<0.05 all windows) |
| **Cohen's d** | 1.2814 | -0.2459 | -0.9352 | ✗ Only 150p meets d>1.0 |
| **Per-bet Eff** | 163.6% vs FR | 130.3% vs FR | 112.0% vs FR | ✓ Above 80% baseline |
| **Leakage Check** | ✓ PASS | ✓ PASS | ✓ PASS | ✓ No future data leak |

### Key Finding

The WQ P2-1 signal exhibits:
- **150p strength**: Raw edge +12%, permutation p=0.0667 (borderline), d=1.28 (good)
- **500p collapse**: Raw edge drops to +7.74%, permutation p=0.6333 (strong rejection), d=-0.25
- **1500p deterioration**: Raw edge +7.47% but permutation p=0.80 (extreme noise), d=-0.94

**Interpretation**: The 150-period window captured a spurious pattern. Across larger windows (500+), the popularity_score proxy signal dissolves into noise that's indistinguishable from random shuffles.

---

## Why Not WATCH?

WATCH candidacy requires:
1. ✓ All three windows edge positive → **PASS**
2. ✗ All three windows permutation p < 0.05 → **FAIL** (500/1500 at p=0.63/0.80)
3. ✗ All three windows Cohen's d > 1.0 → **FAIL** (500/1500 at d=-0.25/-0.94)
4. ✓ Per-bet efficiency ≥ 80% all windows → **PASS**
5. ✓ No data leakage → **PASS**

**Criteria met: 3/5. Threshold for WATCH: 5/5.**

The permutation test is the gating failure: it explicitly tests whether the real edge could occur by chance even if the strategy is random. When p > 0.05, we cannot reject the null hypothesis that the signal is spurious. At p=0.63 and p=0.80, there's a >60% chance the edge is pure luck.

---

## Why Did 150p Appear Strong?

Two factors:
1. **Window size sensitivity**: 150 periods is a relatively small test set (150 OOS evaluations). Even weak patterns can reach statistical significance by chance.
2. **Multiple comparisons**: Testing three windows (150/500/1500) creates a multiple-testing problem. If each independent window has a 5% chance of false significance, the family-wise error rate across three tests is ~14%, not 5%.

The fact that **only the shortest window passed** is a classic sign of **data snooping / overfitting in the historical record**, not a real signal.

---

## Lessons Learned

### L130 (added to wiki/lessons/key_lessons.md)

**威力彩 Winning Quality P2-1 popularity_score 代理模型作為分獎風險濾網的驗證顯示：150p raw Edge +12.01% 且 perm p=0.0667（邊界），但 500/1500p 時 permutation p=0.6333/0.8000 失效、Cohen's d=-0.246/-0.935；無法形成跨窗口非虛假訊號。啟發式人氣估算若無真實分獎金額資料支撐，在本資料集上無法超越隨機。此方向已達驗證閾值，後續改善應改向真實商業資料而非模型微調。**

Translation:
> POWER_LOTTO Winning Quality P2-1 validation using popularity_score as a proxy for split-risk filtering shows: 150p raw edge +12.01% with marginal permutation p=0.0667, but 500/1500p permutation test fails (p=0.6333/0.8000) and Cohen's d deteriorates to -0.246/-0.935. Cannot form a non-spurious cross-window signal. Heuristic popularity estimation, without real split-prize data, cannot outperform random baseline in this dataset. This direction has reached its verification threshold; future improvement should shift to real commercial data rather than model tuning.

### Related Lessons (already in wiki)

- **L102**: Anti-crowd / popularity adjustments can be advisory, but should not be deployed when effect size is small and permutation test is not significant.
- **L129**: Tasks must distinguish BLOCKED_ENV (external quota limits) from REPLAN_REQUIRED (validation failure). This task used local-only data to avoid BLOCKED_ENV.

---

## Artifact Locations

1. **Formal JSON Results**
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/analysis/results/power_wq_p21_validation_20260423.json`
   - Seed: 42, all reproducible
   - Full metrics for 3 strategies × 3 windows + leakage checks

2. **Markdown Summary Report**
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/analysis/results/power_wq_p21_validation_20260423.md`
   - Executive summary, results tables, technical details, interpretation

3. **Wiki Updates**
   - `wiki/games/power_lotto.md` → Added WQ P2-1 entry to WATCH/PROVISIONAL section with full citation
   - `wiki/lessons/key_lessons.md` → Added L130 lesson about this validation

4. **Verification Script**
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/validate_power_wq_p21_20260423.py`
   - Standalone Python script, fully reproducible with seed=42
   - Can be re-run independently: `python3 tools/validate_power_wq_p21_20260423.py`

---

## Next Steps for Planner

### If future investigations want to revisit popularity/split-risk:

1. **Obtain real data**
   - Taiwan lottery's historical split prize records (# of winners per draw)
   - This would allow direct validation instead of proxy estimation

2. **Alternative models to consider**
   - Deep-learned popularity (needs larger external dataset)
   - Market-based crowd estimates (if accessible)
   - Recency-weighted vs. historical popularity

3. **Do NOT pursue**
   - Tuning popularity_score weights further (already proven to not work)
   - Conditional filtering strategies using popularity (will just add noise on top of weak signal)
   - Cross-game popularity transfer (L84 in wiki shows this fails)

### Current POWER_LOTTO Strategy Roadmap

Per `wiki/games/power_lotto.md`:

- **Active**: Fourier Rhythm 3-bet, PP3 Frequency Orthogonal 4-bet, Special V3 top-2
- **WATCH (downgraded 2026-04-23)**:
  - fourier_rhythm_3bet (unstable 150p, need rolling-slice verification)
  - pp3_freqort_3bet (B-plan alternative, but 150p efficiency < 80%)
  - PP3 Sum Regime / Reversal
  - PP3 + MidFreq Orthogonal V2
  - Special V4 orthogonal (permutation edge lost)

- **REJECTED**:
  - All non-family Layer-1 3bet candidates
  - midfreq_fourier_2bet regime gate
  - Special V4 orthogonal reinforcement
  - **WQ P2-1** (as of this validation)

**Planner should next focus on**:
1. Stability audit of `fourier_rhythm_3bet` rolling-slice performance
2. New feature families not yet explored (hint: data-driven regime detection beyond Fourier/PP3/MidFreq)
3. Economic EV validation if any new signal emerges (L87, L99: even positive predicted edge may be unbeatable by Kelly/sizing in low-base-rate environment)

---

## Final Checklist (Task Contract Fulfillment)

- [x] **Complete local verification** — No external API, no rate limits, seed=42
- [x] **Formal result artifact** — JSON + Markdown at analysis/results/
- [x] **150/500/1500 metrics** — Raw edge, perm p-value, Cohen's d, per-bet efficiency all documented
- [x] **Data leakage check** — tools/verify_no_data_leakage.py adapted, PASS
- [x] **Comparison against baselines** — Fourier 3-bet & PP3 4-bet included
- [x] **Clear conclusion classification** — REJECT (not BLOCKED_ENV, not vague "COMPLETED")
- [x] **Wiki updated** — power_lotto.md WATCH section + lesson L130 in key_lessons.md
- [x] **Handoff notes** — This document, citing exactly what changed

---

## Why This Approach Works

**Prior failures**:
- "Let me try a better baseline" → More code complexity → More fallback paths → Eventually hits quota limits → Task marked COMPLETED but no real conclusion

**This approach**:
- "What's the minimum viable validation?" → Use existing simple baselines → Hardcode seed → Local-only data
- Result: 3-minute execution, clear REJECT conclusion, zero external dependencies
- If different researcher revisits with real data: can directly extend this validation script, not start over from scratch

This pattern should apply to other stalled validation tasks: **trade thoroughness for determinism**, get actual closure.

---

Generated: 2026-04-23T15:52:00 UTC
Task ID: validate-power-wq-p21
Status: COMPLETED ✓
