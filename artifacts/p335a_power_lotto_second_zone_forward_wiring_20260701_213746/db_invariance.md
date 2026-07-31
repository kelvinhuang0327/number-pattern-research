# P335A — DB Invariance

**Result: PASS — no DB was written, migrated, checkpointed, restored, or backfilled.**

## Canonical DB (99MB) — byte-identical before/after

`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db`

| field | Phase-0 baseline | after all work |
|---|---|---|
| size | 99,368,960 | 99,368,960 |
| mtime | Jun 30 13:38:50 2026 | Jun 30 13:38:50 2026 |
| SHA256 | `9956c3bc303f2e38ea2cd777367f6205cf23bc2fa6f2c40e0f09213ca5c1ee95` | `9956c3bc303f2e38ea2cd777367f6205cf23bc2fa6f2c40e0f09213ca5c1ee95` |

Identical. The canonical DB was **never opened** by this task (no connection
string in any P335A code or command targeted it).

## Root DB (217KB, git-tracked) — byte-identical

`/Users/kelvin/Kelvin-WorkSpace/LotteryNew/data/lottery_v2.db`

- size 217,088 (unchanged); SHA256
  `2095c687ede4111090daf858e64f6a33569d2d8d68f1f2ec60fae7f5c6366c96` (unchanged).
- In the p335a worktree the tracked copy `data/lottery_v2.db` is **git-clean**
  (no `M` in `git status`), i.e. unmodified vs HEAD.

## Test-run side effects (contained + cleaned)

Running the DB-backed *existing* tests (`test_p48…`, `test_p93…`) caused
`sqlite3.connect()` to auto-create empty (0-byte) `.db` files at several
gitignored paths inside the p335a worktree (e.g.
`lottery_api/data/lottery_v2.db`). These:

- Are 0-byte SQLite stubs at the worktree's own paths — **not** the canonical DB.
- Are covered by `lottery_api/.gitignore` (`*.db`), so they never appear in
  `git status` / cannot be staged.
- The untracked stray (`lottery_api/data/lottery_v2.db`) was **removed**; all
  git-tracked `.db` files verified byte-identical to HEAD (git status clean).

## P335A's own code / tests

`tests/test_p335a_...py` and `power_lotto_second_zone.py` perform **zero** DB
I/O — pure in-memory synthetic history. No `sqlite3`, no file writes, no network.

**No DB mtime or hash changed. No historical replay row was read, modified, or
inserted.**
