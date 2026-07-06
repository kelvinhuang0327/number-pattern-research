# POWER_LOTTO Exclusion Note

This note is based on actual P298A artifacts read from `/Users/kelvin/Kelvin-WorkSpace/p298a_powerlotto_canonical_view_audit_20260630_155049`, including `powerlotto_source_audit.md`, `predicted_second_zone_audit.csv`, `powerlotto_readiness_matrix.csv`, `contract_mapping_patch.md`, and `handoff_report.md`.

## P298A Confirmed Blocker
- P298A confirms no POWER_LOTTO canonical DB view/source contract is present. The only canonical DB view found there was `draws_big_lotto_canonical_main`.
- P298A confirms POWER_LOTTO full prize-aware replay is blocked because `27104` of `36104` replay rows have `predicted_special IS NULL`.
- Missing second-zone predictions must be excluded with `exclusion_reason=predicted_second_zone_missing`; they must not be filled, substituted, or manufactured.

## Research-Only Subset
P298A confirms a research-only subset: `strategy_prediction_replays WHERE lottery_type='POWER_LOTTO' AND predicted_special IS NOT NULL`.

Observed subset from P298A: `9000` rows, `1500` distinct target draws, target range `101000002..115000040`.

## P299A Scope Decision
P299A excludes POWER_LOTTO full scoring and does not compute or optimize POWER_LOTTO. The D5 MVP matrix is limited to BIG_LOTTO and DAILY_539.
