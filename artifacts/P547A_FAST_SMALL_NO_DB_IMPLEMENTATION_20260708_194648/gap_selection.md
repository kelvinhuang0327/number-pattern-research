# P547A Gap Selection Evidence

## Phase 0 Constraints

- risk_domains: data-ingestion, canonical-db, scheduled-jobs, timezone-date, stats-methodology, compliance-disclaimer, worktree-debt.
- do_not_touch: DB/data files, pid/runtime files, outputs, existing artifacts outside this task evidence path, governance/roadmap/memory/docs, `.ai`, p273a dirty canonical checkout, PR #444.
- hard_gates: no DB write/open/migration/import/backfill; no service or scheduler start/stop; no deploy/release; focused static validation only.
- allowed writes used: task worktree source/test files required for the selected gap and this task evidence directory.
- forbidden actions observed: no staging/committing in canonical checkout, no PR #444 action, no DB open/write, no new dependency, no prediction/betting/edge claim.
- branch/worktree: implementation isolated to `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P547A-FAST-SMALL-NO-DB` on `p547a-fast-small-no-db-implementation`.

## Selected Gap

The newly merged P536E/P536G lift-extension UI renders artifact-backed string fields into `innerHTML` by concatenating values such as `strategy_id`, `feature_family`, `lottery_type`, and `combo_id` without a local HTML escaping helper. The route is read-only and artifact-backed, but these strings still cross a data-to-HTML boundary in the browser.

## Why This Is Safe And Small

- Scope is one static frontend hardening fix in the P536E UI block.
- No API behavior, DB access, scheduler, service startup, generated rows, migration, or artifact regeneration is required.
- It is distinct from the repeated AutoFetch/progress visibility fixes.
- It is testable with existing focused static-test style by asserting the P536E render paths use an escaping helper for dynamic string fields.
- No external package is justified: native string replacement is sufficient for HTML text escaping and avoids dependency risk.

## Local Validation

- `pytest tests/test_p536g_lift_extension_ui_filter_export.py`: PASS, 12 tests.
- `python3 -m py_compile tests/test_p536g_lift_extension_ui_filter_export.py`: PASS.
- `node --check` on extracted P536E script block: PASS.
- `git diff --check`: PASS.
- Open PR inventory: only PR #444 open; excluded by task rule.
- Changed-file gate before staging: `index.html`, `tests/test_p536g_lift_extension_ui_filter_export.py`, this task evidence file.

## DB Hash Evidence

Pre-edit and post-validation hashes matched exactly:

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
