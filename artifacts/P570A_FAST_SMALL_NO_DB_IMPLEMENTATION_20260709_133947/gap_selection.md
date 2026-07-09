# P570A Gap Selection Note

## Phase 0 Constraints

- risk_domains: data-ingestion, canonical-db, scheduled-jobs, timezone-date, stats-methodology, compliance-disclaimer, worktree-debt.
- do_not_touch: canonical DB files, data DBs, pid/runtime files, outputs, unrelated artifacts, governance docs, p273a dirty files, legacy overlays, README/CLAUDE/memory/docs/wiki/00-Plan unless separately authorized.
- hard_gates: no canonical DB writes without named authorization; no services, scheduler, migration, seed, import, backfill, or broad test run that may require DB; dashboard semantics require focused evidence.
- allowed writes for this task: selected source file, focused test file, P570A evidence artifact, branch push, PR creation, normal merge if gates pass.
- forbidden actions: no SQLite open/write, no DB backup/migration/generated rows, no p273a mutation, no PR #444 action, no force push/delete, no deploy/release, no roadmap/governance edits, no new dependency.
- DB/data/runtime restriction: DB validation uses file hashes only; no service startup or scheduler interaction.
- branch/worktree restriction: implementation only in `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P570A-FAST-SMALL-NO-DB` on `p570a-fast-small-no-db-implementation`.

## Selected Gap

Best Strategy Overview `bsoLoad()` renders the `SOURCE_UNAVAILABLE` empty-state fallback with `innerHTML` and interpolates `LOTTERY_LABELS[lottery] || lottery` directly. The label normally comes from a controlled selector, but the value can be DOM-manipulated and the section already has `bsoEscapeHtml()`. Escaping before interpolation is a small, local render-safety fix.

## Why This Is Safe

- It is separate from P557A next-prediction render safety and P569A ranking error render safety.
- It changes only frontend fallback text rendering; no API, DB, scheduler, service, or data semantics are changed.
- It uses an existing local escape helper; no dependency is added.
- It is covered by focused static pytest assertions.
