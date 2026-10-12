# Corrected Worker Task Packet — P0 Schema Stabilization / Next Vertical

```yaml
TASK_ID: P0_SCHEMA_STABILIZATION_CANONICAL_UNIVERSE_MIGRATION_R4
TASK_CLASS: STATE_CHANGING_IMPLEMENTATION
WORKER_ROUTE: STANDARD_JUDGED

JUDGE_MODE: FRESH_CONTEXT
JUDGE_DEPTH: BOUNDED

OWNER_AUTHORIZATION_STATUS: PRESENT
SECOND_CONFIRMATION_REQUIRED: NO
STANDALONE_OWNER_AUTHORIZATION_REQUIRED: true

RESOURCE_SAFE_EXECUTION_MODE: ENABLED
LANGUAGE_SERVER_REQUIRED: false
BACKGROUND_COMMANDS_ALLOWED: false
PARALLEL_COMMANDS_ALLOWED: false
FULL_WORKSPACE_SCAN_ALLOWED: false
GLOBAL_GIT_STATUS_ALLOWED: false
```

## 1. Goal

Implement `cand_059a_canonical_strategy_universe_inventory` (Read-only Canonical Strategy Universe Inventory & Coverage Matrix) as a strictly bounded single vertical.

If `cand_059b_p0_schema_migration_engine` (DDL Schema Migration) is authorized by Owner, it MUST be executed in a separate, isolated task packet with explicit standalone owner authorization and dry-run verification first.

## 2. Allowed Paths

```text
scripts/p0_per_draw_coverage_matrix.py
tests/test_p0_canonical_universe.py
docs/replay/p0_canonical_strategy_universe_20260518.md
outputs/replay/p0_canonical_strategy_universe_20260518.json
outputs/replay/p0_per_draw_coverage_matrix_20260518.json
```

## 3. Forbidden Actions

- DO NOT execute DDL queries or DML writes on `lottery_api/data/lottery_v2.db`.
- DO NOT modify existing core source code outside allowed scope.
- DO NOT execute candidate scripts outside sandboxed output paths.
- DO NOT use Language Server or full workspace scans.

## 4. Required Verification

- Path-scoped focused test: `.venv/bin/pytest tests/test_p0_canonical_universe.py -v`
- AST parse validation on `scripts/p0_per_draw_coverage_matrix.py`
- Sandbox output directory check.
