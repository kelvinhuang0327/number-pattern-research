# P325A Phase 0 State

- Analysis timestamp: `20260701_145150` (Asia/Taipei, UTC+0800).
- Target repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui`
- Branch: `main`
- HEAD: `fce02f0dc271274f7cffc54de527f0262e4f4830`
- `git fetch origin` executed; `origin/main` = `fce02f0dc271274f7cffc54de527f0262e4f4830`.
- `origin/main` contains the expected commit: YES (merge-base --is-ancestor).
- `main...origin/main` = `0 0`; working tree clean; no staged files.
- Write targets NOT used: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`, `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main`.
- DB `lottery_api/data/lottery_v2.db`: not created, not opened, not modified (this analysis opens no DB).
- P320A static artifact SHA256 verification (repo `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a`):
  - strategy_combination_metrics.csv: MATCH (0141b53f135a456fb3c2d02fe15f17aa5728a7ff8f47c88d26777c025e855ec5)
  - top_descriptive_candidates.csv: MATCH (e1b074aed742eab0306cdcd002082635899c215e289d2dd1208a61353087cabd)
  - window_summary.csv: MATCH (63e72bf7362542e072e4244361a1bc9b70fd5dd01e0067ff64a697c8e785a985)
- `source_provenance.json` present: YES.
- Original P320A evidence root present: `/Users/kelvin/Kelvin-WorkSpace/p320a_d5_per_draw_combination_analysis_20260701_131917` (read-only reference; not mutated).
- Evidence root (external, repo-external): `/Users/kelvin/Kelvin-WorkSpace/p325a_d5_equal_budget_baseline_analysis_20260701_145150`.
