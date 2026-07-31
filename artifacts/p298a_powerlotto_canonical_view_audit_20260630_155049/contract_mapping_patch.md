# Contract Mapping Patch Proposal

This is a proposal only. P297A contract files were not modified.

## POWER_LOTTO Row Semantics
- `eligibility_status=PARTIAL`: use only for rows where `lottery='POWER_LOTTO'`, `predicted_special IS NOT NULL`, replay identity fields are present, and the row is explicitly scoped to research-only partial subset evaluation.
- `eligibility_status=EXCLUDED`: use for rows where `lottery='POWER_LOTTO'` and `predicted_special IS NULL`; set `exclusion_reason=predicted_second_zone_missing`.
- `eligibility_status=NOT_READY`: use for POWER_LOTTO strategy rows with no replay rows or no eligible non-null second-zone replay subset.
- `eligibility_status=ELIGIBLE`: do not use for full POWER_LOTTO prize-aware replay until a validated POWER_LOTTO canonical source/view exists and second-zone predictions are structurally complete for the intended scope.

## Required Fields
- `exclusion_reason`: `predicted_second_zone_missing` for the 27,104 NULL rows. Use `powerlotto_canonical_view_absent` when the row/scope is blocked by absent canonical source rather than row-level missing second-zone.
- `canonical_source_status`: `ABSENT` for current full POWER_LOTTO replay readiness; `PARTIAL` only if a future contract explicitly scopes raw draw source use to research-only subset; `PRESENT` only after a verified POWER_LOTTO canonical view/source contract exists.
- `inferential_status`: `NOT_READY` for rows lacking canonical source or prospective threshold/horizon. `NULL` or `NO_GO` may represent retrospective-only evidence, but must not imply future prediction ability.
- `readiness_status`: `NOT_READY` for full POWER_LOTTO prize-aware replay today. `PARTIAL_SUBSET_ONLY` may be used in downstream matrices for the 9,000-row non-null subset, but not as production readiness.

## Mapping
| Condition | eligibility_status | exclusion_reason | canonical_source_status | inferential_status | readiness_status |
|---|---|---|---|---|---|
| POWER_LOTTO `predicted_special IS NULL` | EXCLUDED | predicted_second_zone_missing | ABSENT | NOT_READY | NOT_READY |
| POWER_LOTTO `predicted_special IS NOT NULL`, no canonical view | PARTIAL |  | ABSENT | NULL_OR_NO_GO_RETROSPECTIVE_ONLY | PARTIAL_SUBSET_ONLY |
| POWER_LOTTO strategy has no replay rows | NOT_READY | no_replay_rows | ABSENT | NOT_READY | NOT_READY |
| Future validated canonical source and complete predicted second zone | ELIGIBLE |  | PRESENT | per prospective contract | per prospective contract |
