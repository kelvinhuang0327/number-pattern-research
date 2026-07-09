# P561A Gap Selection

Selected gap: `src/ui/UIManager.js` rendered API-derived stats/count values through `innerHTML` without local HTML escaping.

Why this is safe and small:
- Frontend-only render-safety fix in `UIManager`.
- No DB read/write, SQLite open, migration, service startup, scheduler, deploy, generated rows, or runtime file mutation.
- Distinct from recent repeated areas: not AutoFetch accessibility, not ApiClient timeout/empty success, not AutoLearning strategy-name escaping, not BSO next-prediction, not ChartManager, and not replay error fallback escaping.
- Native local escaping is sufficient; no external dependency is justified for four scalar stats/count insertions.
- Focused static tests assert the changed render paths escape API-derived values before `innerHTML`.

Relevant `.ai` constraints observed:
- Risk domains: data-ingestion, canonical-db, scheduled-jobs, timezone-date, stats-methodology, compliance-disclaimer, worktree-debt.
- Do not touch: canonical DB paths, `data/*.db`, pid/runtime/outputs cleanup, roadmap/governance docs, `.ai`, p273a dirty checkout, PR #444.
- Hard gates: no canonical DB write without named authorization; no service/scheduler startup; no data import/migration/backfill; focused tests only.

Open PR inventory:
- Only PR #444 open; excluded by task rule.

DB handling:
- DB files were byte-hashed before source edits. No SQLite connection/open was used.

Commands/results:
- `git status --short` in canonical checkout: dirty pre-existing p273a/runtime/data/artifact state recorded read-only.
- `git branch --show-current` in canonical checkout: `task/p273a-prize-aware-inferential-validation`.
- `git fetch origin --prune`: PASS.
- `git merge-base --is-ancestor f472a1daa436ced98abec27931e31fe775d008d6 origin/main`: PASS.
- `gh pr list --state open --limit 100 ...`: only PR #444 open; excluded by rule.
- `node --check src/ui/UIManager.js`: PASS.
- `pytest -q tests/test_p561a_ui_manager_stats_render_safety.py`: PASS (`4 passed`).
- `git diff --check`: PASS.

DB SHA-256 before/after:

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

Changed-file gate:
- `src/ui/UIManager.js`
- `tests/test_p561a_ui_manager_stats_render_safety.py`
- `artifacts/P561A_FAST_SMALL_NO_DB_IMPLEMENTATION_20260709_104830/gap_selection.md`
