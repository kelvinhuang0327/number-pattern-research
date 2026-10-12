# Task Packet: P0 Schema Stabilization & Canonical Strategy Universe Inventory Migration

```yaml
TASK_ID: P0_SCHEMA_STABILIZATION_CANONICAL_UNIVERSE_MIGRATION_R4
TASK_CLASS: STATE_CHANGING_IMPLEMENTATION
WORKER_ROUTE: FAST
JUDGE_MODE: NOT_APPLICABLE
OWNER_AUTHORIZATION_STATUS: NOT_REQUIRED
SECOND_CONFIRMATION_REQUIRED: NO
```

## Task Summary

Migrate the P0 Schema Stabilization & Canonical Strategy Universe Inventory vertical from `refs/heads/feat/p0-schema-stabilization-20260518` into the active branch `task/p273a-prize-aware-inferential-validation`.

## Authority and Source Reference

```text
Source Repository: /Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged
Source Ref: refs/heads/feat/p0-schema-stabilization-20260518
Extraction Path: _git_ref_reference/LOTTERY_BRANCH_REF_EXTRACTION_R1/by_repository/repo_1_lotterynew/by_ref/refs_heads_feat_p0-schema-stabilization-_325f854e
```

## Target Workspace Constraints

```text
Branch: task/p273a-prize-aware-inferential-validation
HEAD: 3d6df001da3a0633ab91f164d722b595ca76d2e1
```

## Exact Target Paths to Migrate

- `scripts/p0_per_draw_coverage_matrix.py`
- `tests/test_p0_canonical_universe.py`
- `tests/test_p0_schema_migration_idempotent.py`
- `docs/replay/p0_canonical_strategy_universe_20260518.md`
- `docs/replay/p0_schema_diff_20260518.md`
- `outputs/replay/p0_canonical_strategy_universe_20260518.json`
- `outputs/replay/p0_migration_log_20260518.json`
- `outputs/replay/p0_per_draw_coverage_matrix_20260518.json`
- `outputs/replay/p0_schema_diff_20260518.json`

## Excluded Paths (MUST NOT MODIFY)

- `index.html`
- `data/lottery_v2.db`
- `claude-code-showcase`
- `tools/quick_predict.py`
- `tests/test_p360b_quick_predict_ledger_entrypoint.py`
- `lottery_api/routes/replay.py`
- `tests/test_p354a_replay_lottery_type_query_normalization.py`
- `tests/test_p355a_replay_detail_enum_query_normalization.py`

## Phase 0 Pre-mutation Requirements

1. Verify live branch and HEAD (`task/p273a-prize-aware-inferential-validation` @ `3d6df001da3a0633ab91f164d722b595ca76d2e1`).
2. Verify path-scoped status for exact target paths:
   ```bash
   git status --porcelain=v1 -uall -- scripts/p0_per_draw_coverage_matrix.py tests/test_p0_canonical_universe.py tests/test_p0_schema_migration_idempotent.py
   ```

## Focused Verification Protocol

1. Run syntax parse:
   ```bash
   python3 -m py_compile scripts/p0_per_draw_coverage_matrix.py
   ```
2. Execute focused unit tests:
   ```bash
   python3 -m pytest tests/test_p0_canonical_universe.py tests/test_p0_schema_migration_idempotent.py -v
   ```
3. Execute CLI smoke test:
   ```bash
   python3 scripts/p0_per_draw_coverage_matrix.py
   ```

## Git Publication Rules

- DO NOT commit, push, or open a PR.
- DO NOT checkout, rebase, merge, or delete any Git branch.
