# Lottery D5 Artifact-Backed UI

This module implements the P300A read-only D5 demo slice for the P299A hit-rate matrix MVP.

## Source Artifacts

Source evidence root:

`/Users/kelvin/Kelvin-WorkSpace/p299a_d5_big_daily_hit_rate_matrix_mvp_20260630_160533`

Browser-loaded copies live under:

`public/demo-data/lottery-d5/p299a`

Copied inputs:

- `manifest.json`
- `d5_hit_rate_matrix.csv`
- `strategy_coverage_summary.csv`
- `optimizer_input_contract.json`
- `powerlotto_exclusion_note.md`

## Boundaries

- Read-only static artifact display.
- No DB write, migration, checkpoint, production apply, registry publication, commit, push, or PR.
- Retrospective-only.
- No future prediction claim.
- No betting recommendation.
- No production readiness claim.
- Baselines are not computed and deltas remain `NULL`.
- POWER_LOTTO full scoring is excluded.
