# P341A — P333 Strategy Pick / Combination Scoreboard: Governed Integration

Task ID: `P341A_P333_SCOREBOARD_GOVERNED_INTEGRATION`
Date: 2026-07-02
Mode: read-only relative to DB; source/test/artifact port only. No merge.

## Source / target

- Source (stale interactive worktree): `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`,
  branch `task/p273a-prize-aware-inferential-validation`, HEAD `3d6df00` (uncommitted
  working tree at time of port).
- New branch: `task/p341a-p333-strategy-pick-scoreboard`, created from `origin/main`
  in a fresh worktree at `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p341a`.
- `origin/main` verified commit (fetched, unchanged before/after): `ce2c042e7f4967841e6b31e17552d55bf4717f91`.

## Hunk classification — `lottery_api/routes/replay.py`

| Hunk | Description | Classification |
|---|---|---|
| Import block reorg (`try/except DatabaseManager` moved to top) | Reverts P291U DB-path-resolution refactor merged to `main` after this branch forked | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Removal of `_p291u_repo_root` / `_p291u_default_db_path` / `_p291u_resolve_db_path` / `_p291u_connect_resolved` | Same as above — stale branch predates P291U | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| `_get_db()` / `_open_conn()` simplification | Reverts P291U resolved-path connect helpers | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Reordering of `_D3_STRATEGY_STATUS_AUDIT_PATH` and removal of `_BIG649_MEASUREMENT_EXPORT_PATH` constant | Stale branch predates BIG649 measurement-export feature | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Addition of `_STRATEGY_PICK_SCOREBOARD_PATH` constant | New P333 artifact path constant | `P333_SCOREBOARD_REQUIRED` |
| Addition of `_load_strategy_pick_scoreboard_payload()` | New P333 loader | `P333_SCOREBOARD_REQUIRED` |
| Addition of `GET /api/replay/strategy-pick-scoreboard` | New P333 read-only route | `P333_SCOREBOARD_REQUIRED` |
| Removal of `_BIG649_MEASUREMENT_EXPORT_ROUTE`, `_BIG649_MEASUREMENT_WINDOWS`, `_BIG649_MEASUREMENT_SCOPES`, `_load_big649_measurement_export_payload`, `get_big649_measurement_export` (~160 lines) | Entire BIG649 measurement-export endpoint exists on `origin/main`; stale branch simply never had it (forked before that feature merged) | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |

**Excluded (not ported):** all `UNRELATED_BRANCH_DRIFT_EXCLUDE` hunks above. The
BIG649 measurement-export endpoint and P291U DB-path-resolution helpers remain
exactly as on `origin/main`, untouched.

**Ported:** only the 3 `P333_SCOREBOARD_REQUIRED` hunks, applied on top of the
unmodified `origin/main` version of the file.

No `UNCLEAR_STOP` hunks in this file.

## Hunk classification — `index.html`

| Hunk | Description | Classification |
|---|---|---|
| `<link ... lottery-d5.css>` removal | Stale branch predates D5 UI (P300A/P326A/P327A, merged to `main` after fork) | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| RWD `@media` block removal (~170 lines) + `background-animation` `aria-hidden` removal | Stale branch predates responsive-table/RWD polish on `main` | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Addition of `策略組合命中率` nav button (`data-section="p333-scoreboard"`) | New P333 nav entry | `P333_SCOREBOARD_REQUIRED` |
| Removal of `D5 命中矩陣` and `大樂透命中量測` nav buttons | Stale branch predates D5 UI and BIG649 measurement UI nav entries | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Addition of `<section id="p333-scoreboard-section">` (~94 lines) | New P333 section markup | `P333_SCOREBOARD_REQUIRED` |
| Removal of `<section id="lottery-d5-section">` D5 MVP block + BIG649 measurement section/script (~619 lines) | Both features exist on `origin/main`; stale branch never had them | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Removal of `<script type="module" src="src/apps/lottery-d5/lottery-d5.js?v=2">` | Same — D5 script tag from a later merge | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |
| Addition of P333 inline JS IIFE (`// ===== P333 STRATEGY PICK / COMBINATION SCOREBOARD =====`, ~192 lines) | New P333 client rendering logic | `P333_SCOREBOARD_REQUIRED` |
| `bestBet`/`nBets` refactor in the P261A replay-row renderer | Belongs to the already-committed local commit `3d6df00` ("P261A: preserve best-ticket replay summary contract") — a separate task, not P333 | `UNRELATED_BRANCH_DRIFT_EXCLUDE` |

**Excluded (not ported):** all `UNRELATED_BRANCH_DRIFT_EXCLUDE` hunks above. The
D5 Strategy Hit-Rate Matrix MVP section, its nav entry, its script tag, the
BIG649 measurement UI section, the RWD CSS, and the unrelated P261A best-ticket
rendering change all remain exactly as on `origin/main`.

**Ported:** only the 3 `P333_SCOREBOARD_REQUIRED` hunks (nav button, section
markup, JS IIFE), applied on top of the unmodified `origin/main` version of the
file. Post-port diff against `origin/main` contains **zero deletions** — a pure
additive patch.

No `UNCLEAR_STOP` hunks in this file.

## Ported file manifest

New files (byte-identical to source worktree, verified via SHA-256):
- `analysis/p333_strategy_pick_combination_scoreboard.py`
- `tests/test_p333_strategy_pick_combination_scoreboard.py`
- `outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json`
- `outputs/research/p333_strategy_pick_combination_scoreboard_20260702.md`

Modified files (P333-only hunks applied on top of unmodified `origin/main` base):
- `lottery_api/routes/replay.py`
- `index.html`

## Artifact provenance and counts

- Source artifact: `outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json`
  (SHA-256 `d3a801ece9afc3efad8372ae48980bc5beb941699304b4324207f09d8504d6a5`,
  identical on source and new branch).
- `strategy_pick_records`: 603 (before port) → 603 (after port)
- `combination_leaderboard_records`: 510 (before port) → 510 (after port)
- `strategy_window_decision_counts.HISTORICAL_WINDOW_PASS`: 13 (before port) → 13 (after port)
- `strategy_window_decision_counts.HISTORICAL_WINDOW_FAIL`: 23 (before port) → 23 (after port)

No transformation of the artifact was performed; it was copied verbatim.

## Canonical DB SHA-256

- Before tests: `05cc5c15860d13b4304e8845872e45c4b2cae83a0b5a8767faf99a79a9bd46d3`
  (`lottery_api/data/lottery_v2.db`, 99368960 bytes, in the source worktree —
  the only checkout holding the canonical DB, since it is `.gitignore`d and the
  new worktree does not have a local copy).
- After tests: `05cc5c15860d13b4304e8845872e45c4b2cae83a0b5a8767faf99a79a9bd46d3` — **unchanged**.
- Pre-existing sidecars `lottery_api/data/lottery_v2.db-shm` /
  `lottery_api/data/lottery_v2.db-wal` were present before this task started,
  owned by the already-running local backend process (pid 88114, `app.py`,
  launchd-managed writer stack). Their mtimes were unchanged across the whole
  task run. No new sidecars were created by this task, and none exist in the
  new worktree (which has no DB file at all — `lottery_api/data/lottery_v2.db`
  is `.gitignore`d, so `git worktree add` does not populate it, and this task's
  scope forbids copying the DB in to fix that).

## Test results

| Command | Result |
|---|---|
| `pytest -q tests/test_p333_strategy_pick_combination_scoreboard.py tests/test_p257c_best_strategy_overview_runtime_smoke.py` | 31 passed, 10 skipped, 3 failed |
| `pytest -q tests/test_p271c_prize_aware_scorer.py tests/test_p273a_primary_window_observed_counts_export.py` | 128 passed |
| `node --check` on extracted inline `<script>` blocks from `index.html` | PASS |

### The 3 failures (both environmental, not P333 code defects)

1. `test_p333_strategy_pick_combination_scoreboard.py::test_replay_api_serves_p333_artifact`
   — `TypeError: __init__() got an unexpected keyword argument 'app'` inside
   `starlette.testclient.TestClient.__init__`. This is a pre-existing
   `httpx==0.28.1` / `starlette==0.27.0` incompatibility in this environment,
   **already known and guarded for** in this same test suite: see
   `tests/test_p257c_best_strategy_overview_runtime_smoke.py:81-84`, which
   wraps the identical `TestClient(app)` call in `try/except TypeError:
   pytest.skip("TestClient version incompatibility (pre-existing env
   issue)")`. The ported `test_p333_*.py` file (copied byte-identical from the
   source worktree) does not have that guard, so it raises instead of
   skipping. The route implementation itself is unaffected — the same file's
   other tests (constructing the payload from the artifact directly, without
   `TestClient`) all pass.
2. `test_p257c_best_strategy_overview_runtime_smoke.py::test_db_integrity`
   and `::test_db_replays_unchanged` — `sqlite3.OperationalError: unable to
   open database file`. `lottery_api/data/lottery_v2.db` is `.gitignore`d and
   is not present in the fresh `origin/main`-based worktree; this task's scope
   explicitly forbids DB copy/fixture creation, so the file was intentionally
   left absent. Confirmed this is a provisioning gap, not a code regression,
   by running `test_p257c_best_strategy_overview_runtime_smoke.py` with these
   two tests deselected: **27 passed, 10 skipped, 0 failed** in this same worktree.

Neither failure involves DB write, betting/prediction wording, or a P333 logic
defect. Both are pre-existing environment/provisioning conditions outside this
task's permitted scope to fix.

## Statements

- `prediction_success_claim=false`
- `strategy_promoted=false`
- `database_write=false`
- `pr_merged=false`

## Remaining risks / next required Owner decision

- The two environmental test failures above are not fixed by this task (fixing
  them would require either relaxing the DB-copy prohibition, or editing the
  ported test file to add the same `TestClient` version guard already used
  elsewhere in the suite — both are scope decisions for the Owner, not this
  task).
- `_BIG649_MEASUREMENT_EXPORT_PATH` in `replay.py` still points at
  `big649_measurement_export_20260621.json`; this constant and its route were
  preserved as-is from `origin/main` and were not touched by this port.
- This PR adds a new read-only route and UI section only; no existing route,
  section, or script was modified or removed.
- Next Owner decision: review and merge (or request changes to) this PR. This
  task does not merge it.
