# Corrected Worker Task Packet — P0 Canonical Strategy Universe Inventory Migration

```yaml
TASK_ID: P0_CANONICAL_STRATEGY_UNIVERSE_INVENTORY_MIGRATION_R4
TASK_CLASS: STATE_CHANGING_IMPLEMENTATION
WORKER_ROUTE: STANDARD_JUDGED

JUDGE_MODE: FRESH_CONTEXT
JUDGE_DEPTH: BOUNDED

OWNER_AUTHORIZATION_STATUS: PRESENT
SECOND_CONFIRMATION_REQUIRED: NO
STANDALONE_OWNER_AUTHORIZATION_REQUIRED: false

RESOURCE_SAFE_EXECUTION_MODE: ENABLED
LANGUAGE_SERVER_REQUIRED: false
BACKGROUND_COMMANDS_ALLOWED: false
PARALLEL_COMMANDS_ALLOWED: false
FULL_WORKSPACE_SCAN_ALLOWED: false
GLOBAL_GIT_STATUS_ALLOWED: false
```

## 1. Goal

Migrate `cand_059a_canonical_strategy_universe_inventory` (Read-only Canonical Strategy Universe Inventory & Coverage Matrix) as a strictly bounded single functional vertical.

The DDL schema migration engine (`cand_059b_p0_schema_migration_engine`) is excluded from this task packet and must be executed in a separate, isolated task packet requiring explicit standalone owner authorization.

## 2. Allowed Ordinary Scope

```text
scripts/p0_per_draw_coverage_matrix.py
tests/test_p0_canonical_universe.py
docs/replay/p0_canonical_strategy_universe_20260518.md
```

JSON output artifacts (`outputs/replay/p0_canonical_strategy_universe_20260518.json` and `outputs/replay/p0_per_draw_coverage_matrix_20260518.json`) are first regenerated in task sandbox, and then promoted or retained as test fixtures as determined by the Judge.

## 3. Forbidden Actions

- DO NOT execute DDL queries (`ALTER TABLE`, `CREATE INDEX`) or DML write queries on `lottery_api/data/lottery_v2.db`.
- DO NOT import or depend on `scripts/apply_p0_schema_migration.py` or `tests/test_p0_schema_migration_idempotent.py`.
- DO NOT modify existing core source code outside allowed scope.
- DO NOT use Language Server or full workspace scans.

## 4. Required Verification

- Path-scoped focused test: `.venv/bin/pytest tests/test_p0_canonical_universe.py -v`
- AST parse validation on `scripts/p0_per_draw_coverage_matrix.py`
- Sandbox output directory check.
