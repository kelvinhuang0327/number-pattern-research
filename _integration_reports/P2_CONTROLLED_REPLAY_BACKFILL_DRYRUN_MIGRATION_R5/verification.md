# Verification

## Focused tests

Command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest \
  tests/test_p2_controlled_replay_backfill_dryrun.py -q \
  -o cache_dir=_integration_reports/P2_CONTROLLED_REPLAY_BACKFILL_DRYRUN_MIGRATION_R5/runtime_sandbox/pytest_cache
```

- Run 1: `9 passed, 1 failed`; the test expected argparse to prefer the
  unknown-option message, while argparse correctly reported missing required
  arguments first. The observed exit code was 2 and no DB/output was created.
- Harness correction: assert the stable argparse `error:` contract.
- Run 2: `10 passed in 1.95s` — PASS.
- Run 3 (after adding the explicit non-read-only override failure case):
  `11 passed in 3.47s`.
- Initial Fresh Judge: `REFUTED`; an invalid CSV destination could leave an
  already-published READY JSON artifact.
- Bounded remediation: preflight both output destinations before DB access or
  publishing either artifact; add an invalid-CSV partial-output regression.
- First post-remediation run: output transcript incomplete (`....`) and not
  accepted as evidence.
- Final post-remediation run: `12 passed in 12.10s` — final PASS.

The focused suite covers help-without-DB, nonexistent DB, forced read-only URI,
ready-state output parsing, adapter-missing blocked state, DB hash/size/mtime
invariance, normalized repeatability, missing schema, invalid output path,
non-read-only override rejection, invalid CLI arguments, AST structure, and
absence of mutating SQL/default DB. The invalid-CSV regression additionally
proves that a valid JSON path plus an invalid CSV path leaves neither output.

## CLI help

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  scripts/p2_controlled_replay_backfill_dryrun.py --help
```

PASS. Help exposed `--db`, `--strategy-id`, `--prediction-item-ids`,
`--json-out`, and `--csv-out`; no DB or output was opened.

## Sandbox smoke

Two foreground executions used:

```text
_integration_reports/P2_CONTROLLED_REPLAY_BACKFILL_DRYRUN_MIGRATION_R5/runtime_sandbox/smoke/fixture.sqlite
```

Both returned zero and classified the preview as
`P2_TS3_REGIME_BACKFILL_DRYRUN_READY`. The fixture SHA-256, size, and mtime were
identical before, between, and after executions. No SQLite sidecar file was
created. Normalized JSON and CSV were byte-equivalent across runs; details are
in `database_invariance.yaml`. These two smoke runs were repeated after the
bounded source remediation.

## Static and import checks

- AST parse: PASS.
- Import smoke with `sqlite3.connect` replaced by a fail sentinel: PASS.
- Ruff: NOT RUN — TOOL NOT AVAILABLE.
- Black: NOT RUN — TOOL NOT AVAILABLE.
- Mypy: NOT RUN — TOOL NOT AVAILABLE.
- Full repository suite/typecheck: NOT RUN — forbidden and not mandatory.
