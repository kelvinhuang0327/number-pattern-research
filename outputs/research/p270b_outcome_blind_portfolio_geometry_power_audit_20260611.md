# P270B — Outcome-Blind Portfolio Geometry & Power Audit

Generated: 2026-06-11T08:25:17.824910+00:00  |  repo_head: `d4b56c8da42963d0f79110c25250d54c62fa4dca`  |  branch: `task/p270b-outcome-blind-geometry-power-audit`

## Outcome-Blind Contract

- This audit is **outcome-blind**: `actual_numbers`, `hit_count`, `special_hit`, and all derived outcome columns were **never read or loaded**.
- **No backtest was run.**
- **No DB write happened.**
- **No registry mutation happened.**
- **No strategy was generated.**
- **No hit-rate improvement is claimed.**

## Pre-Registered Parameters

- N (fixed) = 3
- Eligibility: pool size |P_d| >= 5
- Primary window n = 1000, alpha = 0.0167 (Bonferroni, m=3), power = 0.8
- Kill criterion 1: best-case MDE-increment exceeds the largest P267C uncorrected per-lottery single-cell excess in ALL three lotteries ({'DAILY_539': 1.32, 'BIG_LOTTO': 1.23, 'POWER_LOTTO': 1.48})
- Kill criterion 2: best-case projected discordance < 1% in any lottery (degenerate / untestable)

## Per-Lottery Summary

### BIG_LOTTO

- Eligible draws (|P_d|>=5): 1501 / 1552 (ineligible: 51, leading-prefix ineligible run: 51)
- Coverage band T(S): min(mean)=48.755496, median(mean)=59.935043, max(mean)=60, portfolios enumerated=254023
- G_d coverage T(G_d): mean=60; G_d - median(mean)=0.064957
- Pairwise ticket overlap: mean Jaccard similarity=0.104394, mean shared-number count=0.957372
- Projected discordance (union bound, p_ticket=0.018638): central=0.081916, best-case=0.111828, worst-case=0.037276; rule-R = NOT_RUN_OUTCOME_FORBIDDEN
- MDE-increment (n=1000, alpha=0.0167, power=0.8): central=2.9279pp, best-case=3.421pp, worst-case=1.9751pp vs P267C uncorrected excess=1.23pp
- Roster: 11 strategies, 18 (strategy,bet_index) cells, 7 strategies with only bet_index=1

### DAILY_539

- Eligible draws (|P_d|>=5): 1500 / 1550 (ineligible: 50, leading-prefix ineligible run: 50)
- Coverage band T(S): min(mean)=26.408, median(mean)=30.0, max(mean)=30, portfolios enumerated=189393
- G_d coverage T(G_d): mean=30; G_d - median(mean)=0.0
- Pairwise ticket overlap: mean Jaccard similarity=0.071431, mean shared-number count=0.553582
- Projected discordance (union bound, p_ticket=0.010041): central=0.042695, best-case=0.060246, worst-case=0.020082; rule-R = NOT_RUN_OUTCOME_FORBIDDEN
- MDE-increment (n=1000, alpha=0.0167, power=0.8): central=2.1138pp, best-case=2.511pp, worst-case=1.4497pp vs P267C uncorrected excess=1.32pp
- Roster: 15 strategies, 27 (strategy,bet_index) cells, 10 strategies with only bet_index=1

### POWER_LOTTO

- Eligible draws (|P_d|>=5): 1501 / 1551 (ineligible: 50, leading-prefix ineligible run: 50)
- Coverage band T(S): min(mean)=48.244504, median(mean)=59.55563, max(mean)=60, portfolios enumerated=128306
- G_d coverage T(G_d): mean=60; G_d - median(mean)=0.44437
- Pairwise ticket overlap: mean Jaccard similarity=0.151979, mean shared-number count=1.393076
- Projected discordance (union bound, p_ticket=0.038698): central=0.156381, best-case=0.232136, worst-case=0.077396; rule-R = NOT_RUN_OUTCOME_FORBIDDEN
- MDE-increment (n=1000, alpha=0.0167, power=0.8): central=4.0454pp, best-case=4.9289pp, worst-case=2.846pp vs P267C uncorrected excess=1.48pp
- Roster: 10 strategies, 24 (strategy,bet_index) cells, 4 strategies with only bet_index=1

## Causality Check

- rows checked: 94924, violations found: 0, result: **PASS**

## Kill Criterion Result

### Criterion 1 — best-case MDE exceeds P267C uncorrected excess in ALL lotteries

Triggered: **True**

- BIG_LOTTO: MDE_best=3.421pp vs P267C excess=1.23pp -> exceeds=True
- DAILY_539: MDE_best=2.511pp vs P267C excess=1.32pp -> exceeds=True
- POWER_LOTTO: MDE_best=4.9289pp vs P267C excess=1.48pp -> exceeds=True

### Criterion 2 — best-case projected discordance < 1% (degenerate) in any lottery

Triggered (any): **False**

- BIG_LOTTO: pi_disc_best_case=0.111828 -> below_1pct=False
- DAILY_539: pi_disc_best_case=0.060246 -> below_1pct=False
- POWER_LOTTO: pi_disc_best_case=0.232136 -> below_1pct=False

## Final Classification

`P270B_GEOMETRY_POWER_INSUFFICIENT_NO_GO`

**P270C is NOT allowed.** Direction A (cross-strategy fixed-N M3+ portfolio) closes per the pre-registered kill criterion. State set to HOLD pending user authorization for any next direction.

## Limitations

- Outcome-blind by construction: actual_numbers, hit_count, special_hit, and all derived outcome fields were never read or loaded.
- rule-R (trailing per-strategy M3+ rate selector) cannot be computed without outcome history; reported as NOT_RUN_OUTCOME_FORBIDDEN in projected_discordance.
- Discordance bounds use a union-bound on the THEORETICAL (closed-form hypergeometric) 1-bet M3+ probability per lottery, not an empirical estimate; they ignore positive correlation between tickets sharing numbers, which would tend to make the true discordance probability lower (i.e. MDE higher) than the union bound suggests. The bound is therefore optimistic for Direction A.
- Best-case (sym_diff=6, fully-disjoint alternative portfolio) was used for the kill-criterion comparison to give Direction A the most favorable possible reading; even this optimistic bound is reported in mde_summary alongside the central and worst-case estimates.
- G_d tie-breaking (max-min pairwise Jaccard distance, then lexicographic order) is deterministic and outcome-independent.
- No claim of hit-rate improvement, no betting action, no strategy is implied or generated by this artifact.

## Disclaimers

- This report does not improve win rate and does not authorize betting action.
- 本報告為幾何/檢定力審計，不構成投注建議，不保證任何中獎結果。
- No DB write, no registry mutation, no strategy generation occurred in this task.
