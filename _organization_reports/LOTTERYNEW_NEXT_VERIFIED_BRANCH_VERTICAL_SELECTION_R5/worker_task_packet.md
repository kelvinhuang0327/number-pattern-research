Owner Authorization: LOTTERYNEW_P2_CONTROLLED_REPLAY_BACKFILL_DRYRUN_R5

# Worker Task Packet — P2 Controlled Replay Backfill Dry-run

```yaml
TASK_CLASS: STATE_CHANGING_IMPLEMENTATION
TASK_ID: P2_CONTROLLED_REPLAY_BACKFILL_DRYRUN_MIGRATION_R5
WORKER_ROUTE: STANDARD_JUDGED
JUDGE_MODE: FRESH_CONTEXT
JUDGE_DEPTH: BOUNDED
OWNER_AUTHORIZATION_STATUS: PRESENT
SECOND_CONFIRMATION_REQUIRED: NO
STANDALONE_AUTHORIZATION_REQUIRED: false
```

## Goal

Migrate one bounded read-only audit CLI from the exact source ref, add focused contract tests, and prove in a sandbox that it cannot mutate SQLite state and writes only caller-selected JSON/CSV outputs. Do not claim production runtime capability.

## Repository and exact authority

```yaml
repository: /Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged
required_branch: task/p273a-prize-aware-inferential-validation
required_head: 3d6df001da3a0633ab91f164d722b595ca76d2e1
source_ref: refs/heads/chore/p2-controlled-replay-backfill-dryrun-20260515
source_commit: fb49ae6b7a34ebf9b1ed0cd7b9c56fce82982636
source_tree: d5ee3335506325b3fcc395c17de3a6a0ed4ef879
```

Stop if repository, branch, or HEAD differs. Do not checkout, reset, stash, clean, rebase, merge, create/delete branches, commit, push, open a PR, or merge.

## Exact source and target paths

Read source only from:

```text
_git_ref_reference/LOTTERY_BRANCH_REF_EXTRACTION_R1/by_repository/
repo_1_lotterynew/by_ref/
refs_heads_chore_p2-controlled-replay-ba_e82364b7/
files/scripts/p2_controlled_replay_backfill_dryrun.py
```

Ordinary files allowed to change:

```text
scripts/p2_controlled_replay_backfill_dryrun.py
tests/test_p2_controlled_replay_backfill_dryrun.py
```

Runtime outputs allowed only under a newly created task sandbox within the implementation report directory. Historical source report/JSON/CSV files are evidence only; do not copy them into ordinary docs or outputs.

## Phase 0

Run only the exact repository identity commands from the R5 packet, then:

```bash
git -C /Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged \
  status --porcelain=v1 -uall -- \
  scripts/p2_controlled_replay_backfill_dryrun.py \
  tests/test_p2_controlled_replay_backfill_dryrun.py \
  lottery_api/models/replay_strategy_registry.py
```

Stop on any unexpected collision. Do not run global status or scan the workspace.

## Required behavior

- Preserve the source CLI contract: `--db`, `--strategy-id`, `--prediction-item-ids`, `--json-out`, and `--csv-out`.
- Open SQLite only with `file:<path>?mode=ro` and `uri=True`.
- Never execute SQL mutation statements or call migration/backfill apply functions.
- Preserve `get_adapter(strategy_id)` validation and the blocked classification when binding is unavailable.
- Write JSON and CSV only to explicit caller paths.
- Make output directories the caller's responsibility; do not silently write to repository `outputs/`.
- Keep the default strategy identity `ts3_regime_3bet`; do not add or mutate registry identities.
- Do not import the historical source JSON/CSV as current evidence.

## Focused tests

Create `tests/test_p2_controlled_replay_backfill_dryrun.py` covering:

1. CLI help exposes all five required flags.
2. `_open_db_ro` rejects a nonexistent DB and cannot create one.
3. A minimal copied SQLite fixture remains byte-identical before/after a functional dry-run.
4. Adapter-missing state emits `P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED` without preview rows.
5. Ready-state fixture writes parseable JSON and CSV only inside the sandbox.
6. No SQL mutation verb or production DB default exists in the implementation.

Run only:

```bash
.venv/bin/pytest tests/test_p2_controlled_replay_backfill_dryrun.py -q
.venv/bin/python scripts/p2_controlled_replay_backfill_dryrun.py --help
```

The functional run must use a copied minimal fixture and output paths under:

```text
_integration_reports/P2_CONTROLLED_REPLAY_BACKFILL_DRYRUN_MIGRATION_R5/runtime_sandbox/
```

Before running tests, inspect pytest cache settings and Python bytecode behavior. Set `PYTHONDONTWRITEBYTECODE=1` and disable pytest cache only if those exact established flags are confirmed by local configuration; otherwise include those runtime writes in the allowed implementation report directory or stop before execution.

## Forbidden paths and actions

Do not modify or read the production DB. Do not modify any completed or dirty paths listed in the R5 packet, including `index.html`, `data/lottery_v2.db`, Predraw, Replay normalization, Quick Predict, and P0 inventory paths. Do not use a language server, workspace indexer, background command, global Git status, full repository test/typecheck, or candidate branch checkout.

No production DB write, schema migration, backfill apply, registry mutation, strategy identity change, dependency/lockfile change, or ordinary `outputs/` generation is authorized.

## Acceptance

```yaml
source_ref_and_blob_verified: PASS
target_paths_collision_free: PASS
focused_tests: PASS
cli_help: PASS
fixture_db_sha256_invariance: PASS
json_output_parseable: PASS
csv_output_parseable: PASS
runtime_writes_confined_to_sandbox: PASS
production_db_accessed: false
sql_mutation_path_present: false
registry_modified: false
dependency_manifest_modified: false
completed_vertical_paths_modified: false
bounded_fresh_judge: PASS | PASS_WITH_CAVEATS
```

The Fresh Judge must verify repository identity, actual diff, no test weakening, exact runtime-write ledger, fixture hash invariance, output parsing, and the claim boundary that this is an audit tool only.

