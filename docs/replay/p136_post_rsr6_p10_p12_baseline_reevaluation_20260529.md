# P136: Post-RSR6 Re-evaluation for P10/P12 Baseline Rows

**Generated:** 2026-05-29T02:54:42.597823+00:00
**Classification:** `P136_POST_RSR6_P10_P12_REEVALUATION_READY`

## 1. Executive Summary
P136 completes a read-only post-RSR6 re-evaluation for `power_precision_3bet` and `power_orthogonal_5bet`. Both strategies remain apply-blocked. No DB mutation, no controlled_apply, and no replay-row insertion was executed.

## 2. P135 Recap
- Classification: `P135_WAVE2_SAFE_CANDIDATES_CLOSED_P10_P12_REEVALUATION_PLAN_READY`
- Pass: True
- Commit: `25c8d2b71ca958bd17cf52d0b6c516739745812e`

## 3. RSR-6 Cleanup Recap
- Classification: `RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED`
- Pass: True
- Deleted rows in RSR6 cleanup: 40
- DB rows after cleanup: 72422

## 4. Why P10/P12 Need Post-cleanup Re-evaluation
RSR6 removed orphan bet-index=2 rows, but each strategy still has 50 bet-index=1 rows with NULL provenance fields. They must be governed before any future dry-run/apply gate.

## 5. Current P10/P12 Row Distribution
- `power_precision_3bet`: bet-1=1550, bet-2+=0
- `power_orthogonal_5bet`: bet-1=1550, bet-2+=0

## 6. Baseline Row Audit
- production_baseline_rows_per_strategy = 1500
- null_provenance_legacy_rows_per_strategy = 50
- total_rows_per_strategy = 1550
- db_write_in_p136 = False

## 7. NULL-provenance Legacy Row Audit
{
  "power_precision_3bet": {
    "replay_run_id_counts": {
      "NULL": 1500,
      "2": 20,
      "6": 30
    },
    "controlled_apply_id_counts": {
      "NULL": 50,
      "P20_POWERLOTTO_REMAINING_1500_PROD_20260520": 1500
    },
    "truth_level_counts": {
      "NULL": 50,
      "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED": 1500
    },
    "source_counts": {
      "NULL": 50,
      "P20_POWERLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY": 1500
    },
    "provenance_hash_null_rows": 50,
    "provenance_hash_non_null_rows": 1500,
    "production_baseline_rows": 1500,
    "null_provenance_legacy_rows": 50
  },
  "power_orthogonal_5bet": {
    "replay_run_id_counts": {
      "NULL": 1500,
      "2": 20,
      "6": 30
    },
    "controlled_apply_id_counts": {
      "NULL": 50,
      "P20_POWERLOTTO_REMAINING_1500_PROD_20260520": 1500
    },
    "truth_level_counts": {
      "NULL": 50,
      "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED": 1500
    },
    "source_counts": {
      "NULL": 50,
      "P20_POWERLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY": 1500
    },
    "provenance_hash_null_rows": 50,
    "provenance_hash_non_null_rows": 1500,
    "production_baseline_rows": 1500,
    "null_provenance_legacy_rows": 50
  },
  "summary": {
    "null_legacy_rows_per_strategy": 50,
    "production_baseline_rows_per_strategy": 1500,
    "legacy_rows_keepable_in_p136": true,
    "keep_reason": "P136 is read-only and only produces governance recommendations."
  }
}

## 8. Per-strategy Re-evaluation Matrix
{
  "power_precision_3bet": {
    "strategy_id": "power_precision_3bet",
    "baseline_valid_for_future_dry_run": true,
    "requires_remark_plan": true,
    "requires_quarantine_plan": true,
    "requires_cleanup_authorization": true,
    "remains_apply_blocked": true,
    "reason": "null_provenance_legacy_rows_present_after_rsr6_cleanup",
    "guard_before_any_mutation": [
      "read_only_revalidation_on_same_worktree",
      "authorization_phrase_required",
      "no_controlled_apply_until_resolution",
      "post_mutation_drift_guard_required"
    ]
  },
  "power_orthogonal_5bet": {
    "strategy_id": "power_orthogonal_5bet",
    "baseline_valid_for_future_dry_run": true,
    "requires_remark_plan": true,
    "requires_quarantine_plan": true,
    "requires_cleanup_authorization": true,
    "remains_apply_blocked": true,
    "reason": "null_provenance_legacy_rows_present_after_rsr6_cleanup",
    "guard_before_any_mutation": [
      "read_only_revalidation_on_same_worktree",
      "authorization_phrase_required",
      "no_controlled_apply_until_resolution",
      "post_mutation_drift_guard_required"
    ]
  }
}

## 9. Recommended Resolution
{
  "global_decision": "KEEP_AS_IS_IN_P136_AND_PREPARE_MUTATION_GATE",
  "per_strategy": {
    "power_precision_3bet": {
      "recommendation": "prepare_authorization_gate_for_quarantine_or_re_mark_decision",
      "apply_ready_now": false,
      "why_not_apply_ready": "null_provenance_legacy_rows_present_after_rsr6_cleanup",
      "safe_keep_decision_in_p136": true,
      "safe_keep_rationale": "P136 is read-only; keeping 50 NULL-provenance rows unchanged avoids ungoverned mutation. Mutation must move to a separate authorized task."
    },
    "power_orthogonal_5bet": {
      "recommendation": "prepare_authorization_gate_for_quarantine_or_re_mark_decision",
      "apply_ready_now": false,
      "why_not_apply_ready": "null_provenance_legacy_rows_present_after_rsr6_cleanup",
      "safe_keep_decision_in_p136": true,
      "safe_keep_rationale": "P136 is read-only; keeping 50 NULL-provenance rows unchanged avoids ungoverned mutation. Mutation must move to a separate authorized task."
    }
  }
}

## 10. Future Dry-run Gate Checklist
{
  "preconditions": [
    "worktree_and_branch_check_pass",
    "production_db_rows_still_85924_before_any_new_task",
    "drift_guard_pass_before_and_after_any_mutation_task",
    "p10_p12_bet_index_gt1_rows_remain_zero_until_authorized_mutation"
  ],
  "governance_checks": [
    "authorization_phrase_present_for_any_mutation",
    "mutation_scope_limited_to_p10_p12_legacy_rows",
    "no_wave2_safe_candidate_rows_touched",
    "no_P126B_to_P126F_rows_touched",
    "no_p131_to_p134_rows_touched"
  ],
  "apply_gate_checks": [
    "rebuild_distribution_after_resolution",
    "recompute_apply_ready_flags",
    "run_dry_run_only_first_if_apply_gate_reopened",
    "controlled_apply_requires_separate_phrase_even_after_dry_run"
  ]
}

## 11. Authorization Gate If Mutation Is Needed
{
  "required_before_mutation": true,
  "suggested_authorization_phrase": "P136_AUTHORIZED_P10_P12_BASELINE_LEGACY_ROW_RESOLUTION_PLAN_V20260529",
  "allowed_actions_in_future_task_only": [
    "quarantine_null_provenance_rows",
    "re_mark_with_explicit_provenance_metadata",
    "or_noop_keep_decision_with_documented_waiver"
  ],
  "mutation_forbidden_in_p136": true
}

## 12. Explicit Non-actions
- No DB write in P136
- No controlled_apply in P136
- No replay rows inserted
- 4_STAR excluded
- P108 not run
- P117 not run
- P118 not run
- Rejected strategies no_action
- No scheduler install
- No lifecycle / champion / registry mutation

## 13. Remaining Risks
- P10/P12 still have 50 NULL-provenance bet-1 rows per strategy; they are governance debt until a separate authorized mutation task resolves them.
- Any mutation without an explicit authorization gate risks touching validated production baseline rows.
- Apply readiness remains blocked until legacy row governance is finalized.

## 14. Recommended Next Task
P137 authorization gate task for P10/P12 legacy-row resolution (quarantine or re-mark decision), then reassess dry-run readiness.

## 15. Final Classification
```text
P136_POST_RSR6_P10_P12_REEVALUATION_READY
```
