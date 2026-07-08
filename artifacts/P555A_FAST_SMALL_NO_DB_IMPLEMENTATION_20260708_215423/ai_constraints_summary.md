# Task-relevant .ai constraints

risk_domains:
- data-ingestion
- canonical-db
- scheduled-jobs
- timezone-date
- stats-methodology
- compliance-disclaimer
- worktree-debt

do_not_touch:
- lottery_api/data/lottery_v2.db and data/*.db except separately authorized read-only/copy strategy
- *.pid, runtime/, outputs/ except selected committed artifact source was only read by existing tests
- existing artifacts except this task evidence bundle
- worktree/branch/stash cleanup outside this task worktree/branch
- task/p273a dirty canonical files
- governance docs: README.md, CLAUDE.md, lottery_api/CLAUDE.md, memory/, docs/, wiki/, 00-Plan/

hard_gates:
- no canonical DB write without named authorization
- no tests/services/scheduler/DB writes unless task-authorized; this task authorizes focused no-DB tests only
- no replay/evidence denominator, scope, freshness, or filter semantic changes
- no service startup, no stop_all/start_all, no scheduler

allowed writes used:
- index.html P536L client-side loader
- tests/test_p536l_shortlist_ui_contract.py focused static tests
- task evidence bundle under artifacts/P555A_FAST_SMALL_NO_DB_IMPLEMENTATION_20260708_215423

forbidden actions avoided:
- no p273a mutation, reset, rebase, pull, checkout, stage, commit, or edit
- no PR #444 action
- no DB open/write, migration, backup, generated rows, scheduler, deploy, force push/delete
- no roadmap/governance/handoff edits
- no new external dependency
