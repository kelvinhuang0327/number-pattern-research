# POWER_LOTTO WATCH downgrade decision (2026-04-23)

- Final status: **WATCH**
- Target strategy: `fourier_rhythm_3bet`
- Downgrade action: **DOWNWEIGHT_WATCH_PRIORITY**
- Replacement decision: **DO_NOT_REPLACE**
- Target 150/500/1500 Edge: +1.50% / +1.63% / +2.57%
- Target 150/500/1500 permutation p: 0.4975 / 0.2537 / 0.0100
- Rolling 5x300 target summary: 5/5 slices edge>0, perm fail ratio=0.80, max consecutive non-positive slices=0
- Candidate `pp3_freqort_3bet` status: **WATCH** (150/500/1500 Edge +2.83% / +2.83% / +3.17%)
- Candidate efficiency vs `pp3_freqort_4bet`: 79.9% / 118.2% / 129.4%
- McNemar: NOT_TRIGGERED (permutation p gate not fully passed, Cohen's d gate not fully passed, per-bet efficiency gate not fully passed)
- Leakage check: PASS
- Planner recommendation: POWER_LOTTO 新 Layer-1 3bet 訊號家族探索：避開 WQ / midfreq regime-gate / special V3-V4 / 現有 PP3-FreqOrt 重排，直接尋找非同家族替代主線。
- Handoff notes: updated wiki/games/power_lotto.md and wiki/lessons/key_lessons.md
