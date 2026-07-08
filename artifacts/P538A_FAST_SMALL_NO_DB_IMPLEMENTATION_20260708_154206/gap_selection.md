# P538A_FAST_SMALL_NO_DB_IMPLEMENTATION Gap Selection

## Phase 0 summary

- origin/main tip: `0e7768a0618ef1b5ca7767dc34fba414028ee84d`
- PR #608 merge commit `0e7768a0618ef1b5ca7767dc34fba414028ee84d` is an ancestor of origin/main.
- Open PR inventory: only PR #444 was open; PR #444 is hard-excluded by task rule.
- DB handling: DB files were hashed with `shasum -a 256`; no SQLite open, service startup, migration, backup, import, scheduler, or DB write was performed.

## Task-relevant constraints

- risk_domains: data-ingestion, canonical-db, scheduled-jobs, timezone-date, stats-methodology, compliance-disclaimer, worktree-debt.
- do_not_touch: canonical DB/data paths, pid/runtime files, outputs, existing artifacts outside this task artifact, governance/docs/memory/roadmap areas, dirty p273a checkout, PR #444.
- hard_gates: canonical DB writes require named authorization; tests/services/scheduler/DB writes require explicit authorization; replay/evidence dashboard semantics require evidence before claims.
- allowed writes: source and focused tests for exactly one small gap, this P538A evidence artifact, branch push/PR/normal merge if gates pass.
- forbidden actions: p273a mutation, DB write/open/migration/backup/generated rows, service startup, scheduler, deploy/release, force operations, governance edits, dependency additions without justification.

## Selected gap

`src/ui/AutoFetchManager.js` has a shared `_setBtnLoading(btn, loading)` helper used by no-DB AutoFetch UI controls. It disables the active button and restores the original icon markup after completion, but while the request is in flight it does not expose a machine-readable busy state. The visible source gap is that assistive technology cannot distinguish a disabled idle button from a disabled in-progress button.

## Why this is safe and small

- Frontend-only DOM attribute change.
- No DB, SQLite, migration, data import, scheduler, service startup, or backend behavior.
- Uses native `aria-busy`; no external dependency is needed.
- Focused static validation can assert the helper sets and removes the attribute.

## Implementation

- Set `aria-busy="true"` when `_setBtnLoading` enters loading state.
- Remove `aria-busy` when the helper restores the button after loading.
- Add one focused static test in the existing AutoFetch test file.

## Validation

- `node --check src/ui/AutoFetchManager.js`: PASS
- `pytest tests/test_p536a_ingest_source_health_panel.py -q`: PASS, 7 passed

## DB hash gate

Before and after hashes matched:

```text
214f05870e741164495cd0dbf46158ba1e92835d7a7c072df47a20a0795896c1  ./backups/p213h_lottery_v2_backup_20260605_20260605_142219.db
1b2abd793a3ea3f2d300337eb2db6d2621b52e1600453bc20141377fa6475485  ./backups/p213l_lottery_v2_backup_20260605_20260605_151715.db
9b839fb35b4b793c8b33e6563f239f859b1f108a39988db3236cc506c11639c6  ./data/lottery.db
a552351a5c7d77a6e678c5636fb2da6d2fc8814eaa9f79241b4b9fc4faa83554  ./data/lottery_v2.db
0f54823b3900654fc2bb7d703b274deea17cbdecde4359618ba06d4ad9d4be27  ./lottery-api/data/lottery_v2.db
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  ./lottery.db
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  ./lottery_v2.db
12949072cbc71ace577220e12e8643a183e6020c4d6864a81ad1dda7d9d68faa  ./tools/data/lottery_v2.db
```

## Changed-file gate

- `src/ui/AutoFetchManager.js`
- `tests/test_p536a_ingest_source_health_panel.py`
- `artifacts/P538A_FAST_SMALL_NO_DB_IMPLEMENTATION_20260708_154206/gap_selection.md`

No forbidden DB/data/runtime/governance files were modified.
