# P545D — No-Force Launchd Quiescence Playbook

> task_id: P545D_EXACT_NO_FORCE_LAUNCHD_QUIESCENCE_PLAYBOOK
> classification: `PLAYBOOK_READY_WITH_RUNTIME_MAPPING_DEPENDENCIES`
> evidence_base: `origin/main` @ `22fe144a827c133bbfd1765670a09f82703c788e`
> canonical_db_family: `lottery_api/data/lottery_v2.db` (+ `-wal`, `-shm`, `-journal` sidecars)
> generated_by: read-only committed + local runtime inspection only. No service, DB, PID, or sidecar state was changed to produce this playbook.

This is an **operational contract**, not an execution log. Building this document does **not**
execute any step below. Execution is a **separately authorized** task.

Every executable command block in this playbook is fenced as ```` ```bash ````. Every STOP rule,
forbidden-action list, and unresolved-mapping template is fenced as ```` ```text ```` (or written as
prose) and is **not** an executable instruction. A companion read-only validator
(`analysis/p545d_launchd_quiescence_playbook_validator.py`) statically enforces that no ```` ```bash ````
block contains a dangerous or ambiguous command.

---

## A. Purpose and Scope

**Purpose.** Provide an exact, reversible, fail-closed procedure for *quiescing* (bringing to a
verified stopped state) and later *restoring* the LotteryNew launchd/runtime stack, so that a
**separately authorized** SQLite evidence probe can run against the canonical database with zero
live writers and stable on-disk state.

**In scope.** Discovery, attribution, evidence capture, launchd-native respawn control and graceful
stop, bounded quiescence verification, probe handoff, reverse restore, and the exhaustive list of
always-forbidden actions.

**Out of scope.** This playbook does **not** open, read as SQLite, checkpoint, back up, copy, or
modify the database or its sidecars. It does **not** prove DB row content, schema, or coverage.
It makes **no** prediction, betting, or production-readiness claim. The evidence probe that follows
requires its own authorization and its own playbook.

**Managed surface (evidence-backed).** Exactly one launchd label is defined in the repository:
`com.kelvin.lottery.dev` (see Section C evidence table). The canonical DB writer is the FastAPI
backend (`lottery_api/app.py`, port 8002); the frontend is a static HTTP server (port 8081). Both
backend and frontend are started as detached `nohup` children of `start_all.sh`, which is the
program the `com.kelvin.lottery.dev` plist wraps.

---

## B. Preconditions

All preconditions are mandatory. If any cannot be satisfied, do not proceed; record the reason.

1. **Explicit owner authorization** for the *quiescence execution* task exists in its own message
   (this documentation task does not authorize execution).
2. **Canonical repo/path proof**:
   ```bash
   test "$(git -C /Users/kelvin/Kelvin-WorkSpace/LotteryNew rev-parse --show-toplevel)" \
     = /Users/kelvin/Kelvin-WorkSpace/LotteryNew && echo REPO_OK
   ```
3. **Exact DB path family** confirmed present (metadata only, no open):
   ```bash
   ls -la /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db \
          /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db-wal \
          /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db-shm 2>&1
   ```
4. **Clean protected-worktree proof**: the retained P545B worktree and the dirty P273A checkout are
   untouched. Verify with read-only `git -C <path> status --porcelain` (empty = clean for P545B; the
   P273A checkout is expected dirty and must remain read-only).
5. **No unrelated maintenance in progress**: no ingest, backfill, migration, replay-write, or backup
   job is running (Section C process/handle discovery must show none).

---

## C. Service Discovery

Discovery is **read-only**. Promote a historical label to a current service **only** with live
evidence. If any process or open handle on the DB family cannot be attributed to a known service,
emit `STOP_UNIDENTIFIED_DB_HOLDER` (Section J).

### C.1 Exact read-only discovery commands

```bash
# Loaded launchd jobs (expected: none matching lottery at the observed baseline)
launchctl list | grep -i -E 'lottery|kelvin' || echo NO_LOADED_LOTTERY_JOBS

# Persistent enable/disable overrides in the user GUI domain (read-only)
launchctl print-disabled gui/$(id -u) | grep -i 'com.kelvin.lottery' || echo NO_LOTTERY_OVERRIDES

# Is the one defined label actually loaded? (read-only; nonzero exit == not loaded)
launchctl print gui/$(id -u)/com.kelvin.lottery.dev > /dev/null 2>&1 \
  && echo DEV_LABEL_LOADED || echo DEV_LABEL_NOT_LOADED

# Installed plists in every standard launchd directory (read-only)
for d in "$HOME/Library/LaunchAgents" /Library/LaunchAgents /Library/LaunchDaemons; do
  ls -1 "$d" 2>/dev/null | grep -i -E 'lottery|kelvin' && echo "^ in $d" || echo "no lottery plist in $d"
done

# Running service processes (read-only; ps only, never a signal)
ps -Ao pid,args | grep -iE 'lottery_api/app\.py|http\.server 808|uvicorn app:app|start_all\.sh' \
  | grep -viE 'grep|validator' || echo NO_LOTTERY_SERVICE_PROCESSES

# Port listeners (read-only)
for p in 8002 8081 8080; do lsof -nP -iTCP:$p -sTCP:LISTEN 2>/dev/null || echo "port $p: no listener"; done
```

### C.2 Evidence table (managed service attribution)

| Candidate | Label / identity | Executable / entry | Domain | Committed plist | Installed plist | PID file | KeepAlive | RunAtLoad | Opens DB? | Evidence source (`origin/main` @ `22fe144`) | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dev wrapper | `com.kelvin.lottery.dev` | `/bin/bash .../start_all.sh --foreground` | `gui/$(id -u)` (only if loaded) | `com.kelvin.lottery.dev.plist` (repo root) | **none found** | (via children) | `true` | `true` | via backend child | `com.kelvin.lottery.dev.plist`; `.ai/ai-context/RUNBOOK.md` §5 | `PROVEN` definition, but `NOT_INSTALLED` / unloaded |
| backend | `lottery_api/app.py` (port 8002) | `/usr/bin/python3 app.py` (cwd `lottery_api/`) | n/a (not a launchd label) | n/a | n/a | `backend.pid` | n/a | n/a | **YES (canonical writer)** | `start_all.sh`; `lottery_api/start.sh` | `STALE_PID_ONLY` at baseline (no live proc) |
| frontend | `python3 -m http.server 8081` | `python3 -m http.server 8081` | n/a (not a launchd label) | n/a | n/a | `frontend.pid` | n/a | n/a | no | `start_all.sh` | `STALE_PID_ONLY` at baseline (no live proc) |
| historical labels | `com.kelvin.lottery.{agent-light-worker,agent-planner,agent-worker,copilot-daemon,backend,frontend,weekly}` | unknown | n/a | **none** | **none** | n/a | ? | ? | ? | only in `launchctl print-disabled` (disabled overrides); **no committed plist, no install script** | `HISTORICAL_ONLY` / `NOT_INSTALLED` |
| unrelated | `com.novel.orchestrator.*`, `com.personalhealthos.*`, `com.bettingpool.orchestrator.*` | unknown | n/a | n/a | n/a | n/a | ? | ? | ? | non-lottery labels in disabled db | `UNRELATED` |

**Attribution rule.** A candidate may appear in the executable stop/restore sequence **only** when it
is `PROVEN` *and* currently loaded *and* mapped to an installed plist path (or an exact committed
install mapping) *and* its DB-open possibility is known. At the observed baseline, **no candidate
satisfies this** (the one defined label is `NOT_INSTALLED`/unloaded; backend/frontend are stale). This
is why the playbook is fail-closed: see Sections F and J.

**Unidentified-holder STOP rule.** If Section C.1 / Section D reveals *any* process holding a handle on
the DB family, or any listener on 8002/8081/8080, that cannot be attributed to `com.kelvin.lottery.dev`
→ backend/frontend, do not touch it. Emit `STOP_UNIDENTIFIED_DB_HOLDER` and hand the decision to the
owner.

---

## D. Pre-Stop Evidence Capture

Capture a baseline **before** any respawn-control or stop step. All commands are read-only.
Persist outputs to the task's terminal report (Section L). Sample at three points: `T0` (pre-stop),
`T1` (immediately after stop settles), and `final` (before probe handoff).

```bash
DB=/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db

# launchd state
launchctl list | grep -i lottery || echo NO_LOADED_LOTTERY_JOBS
launchctl print-disabled gui/$(id -u) | grep -i com.kelvin.lottery || true

# process + listener table
ps -Ao pid,ppid,args | grep -iE 'app\.py|http\.server 808|uvicorn|start_all' | grep -v grep || echo NO_PROCS
for p in 8002 8081 8080; do lsof -nP -iTCP:$p -sTCP:LISTEN 2>/dev/null || echo "port $p idle"; done

# open-handle table on the DB family (read-only)
lsof -nP -- "$DB" "$DB-wal" "$DB-shm" "$DB-journal" 2>/dev/null || echo ZERO_OPEN_HANDLES

# DB + sidecar metadata: size / inode / mode / mtime (stat only — the DB file is never opened by a database client)
for f in "$DB" "$DB-wal" "$DB-shm" "$DB-journal"; do
  test -e "$f" && stat -f '%N size=%z inode=%i mode=%Sp mtime=%Sm' "$f" || echo "$f ABSENT"
done

# content-hash of the DB file bytes (sha256 of the file; does NOT open a SQLite connection)
shasum -a 256 "$DB" | awk '{print "sha256="$1}'

# PID-file validation (read-only: read value, test liveness with ps — never signal a process)
for pf in backend.pid frontend.pid; do
  f=/Users/kelvin/Kelvin-WorkSpace/LotteryNew/$pf
  test -f "$f" || { echo "$pf absent"; continue; }
  pid=$(cat "$f"); if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
    echo "$pf=$pid ALIVE"; else echo "$pf=$pid STALE"; fi
done
```

Record, at minimum: launchd loaded/disabled state; the process/listener table; the DB-family open-handle
table; and for the DB the tuple (`sha256`, size, `inode`, mode, mtime) plus WAL/SHM/journal metadata.

---

## E. Safe Respawn Control

Goal: guarantee the wrapper cannot auto-respawn during the window, using **only** launchd-native
mechanisms. **Do not edit the plist. Do not delete PID files.**

The `com.kelvin.lottery.dev` plist declares `KeepAlive=true` and `RunAtLoad=true`, so a *loaded*
instance would relaunch `start_all.sh` on exit. Respawn is controlled by removing the job from its
domain (which also removes KeepAlive supervision) and persistently disabling re-bootstrap:

```bash
# Precondition: only if the label is actually loaded (Section C.1 == DEV_LABEL_LOADED).
# bootout removes the job from the user GUI domain; KeepAlive no longer applies once booted out.
launchctl bootout gui/$(id -u)/com.kelvin.lottery.dev

# Persistently prevent re-launch at next login for the duration of the window (reverse of `enable`).
launchctl disable gui/$(id -u)/com.kelvin.lottery.dev

# Verify respawn is disabled: label must be absent from the loaded list.
launchctl print gui/$(id -u)/com.kelvin.lottery.dev > /dev/null 2>&1 \
  && echo STILL_LOADED_INVESTIGATE || echo RESPAWN_CONTROL_OK
```

```text
If DEV_LABEL_NOT_LOADED (the observed baseline): there is nothing to boot out. Do NOT bootstrap the
repo-root plist to "manage" it — that would install/start a service and is forbidden by this task
family. Respawn control is vacuously satisfied for launchd; proceed to confirm no orphaned nohup
backend/frontend children exist (Section F).
```

Respawn control **must** be re-checked in Section G. Enabling/re-bootstrapping is reserved for the
restore procedure (Section I), and only in the exact reverse order.

---

## F. Graceful Stop Order

Stop order is **dependency-aware**: supervisor first, then supervised children, most-dependent last
holder of the DB released before verification. For this stack the dependency chain is:

**Stop order:** (1) `com.kelvin.lottery.dev` launchd supervision → (2) backend `lottery_api/app.py`
(port 8002, canonical DB writer) → (3) frontend `http.server` (port 8081, no DB).

```bash
# (1) Supervisor: covered by Section E (bootout + disable), only if loaded.

# (2)+(3) Confirm the children are already gone. This stack starts backend/frontend as detached
# `nohup` children of start_all.sh, so they are NOT launchd-supervised jobs. There is no launchd-native
# "stop" for a bare nohup child, and this task family forbids sending it any signal.
ps -Ao pid,args | grep -iE 'lottery_api/app\.py|http\.server 808|uvicorn app:app' | grep -v grep \
  && echo CHILDREN_PRESENT || echo CHILDREN_ABSENT
```

```text
STOP_GRACEFUL_STOP_FAILED — if CHILDREN_PRESENT:
A backend/frontend process is alive but is a detached nohup child, not a launchd job. A graceful,
launchd-native stop is IMPOSSIBLE without a process signal, and signals are forbidden by this task.
Do NOT send TERM/INT/HUP/KILL. Do NOT run stop_all.sh. Emit STOP_GRACEFUL_STOP_FAILED, capture the
process/handle evidence, and hand the decision to the owner (the resolution is a separately authorized
maintenance decision about the orphaned child, not part of quiescence).
```

**Bounded wait.** After respawn control, poll for child exit with a bounded loop — never an unbounded
wait, never a signal:

```bash
max_attempts=12; interval=5; n=0
while [ "$n" -lt "$max_attempts" ]; do
  if ! ps -Ao args | grep -iE 'lottery_api/app\.py|http\.server 808|uvicorn app:app' | grep -qv grep; then
    echo "children exited by attempt $n"; break
  fi
  n=$((n+1)); sleep "$interval"
done
[ "$n" -lt "$max_attempts" ] || echo BOUNDED_WAIT_EXPIRED_EMIT_STOP_GRACEFUL_STOP_FAILED
```

At the observed baseline (`CHILDREN_ABSENT`, all ports idle, PID files stale), the stack is already
stopped and this section is a no-op confirmation.

---

## G. Quiescence Verification

Confirm the quiesced state with repeated, bounded sampling. Quiescence requires **all** of: zero
service processes, zero listeners, zero DB-family open handles, and a stable DB file across samples.
Sidecars are **observed, never modified**.

```bash
DB=/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db

verify_sample () {              # $1 = label (T0 / T1 / final)
  echo "== quiescence sample $1 =="
  ps -Ao args | grep -iE 'lottery_api/app\.py|http\.server 808|uvicorn app:app' | grep -qv grep \
    && echo "$1 PROC_PRESENT" || echo "$1 PROC_ZERO"
  for p in 8002 8081 8080; do lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 \
    && echo "$1 port $p BUSY" || echo "$1 port $p idle"; done
  if lsof -nP -- "$DB" "$DB-wal" "$DB-shm" "$DB-journal" >/dev/null 2>&1; then
    echo "$1 DB_HANDLES_PRESENT"; else echo "$1 ZERO_OPEN_HANDLES"; fi
  shasum -a 256 "$DB" | awk -v s="$1" '{print s" sha256="$1}'
  stat -f "$1 wal_size=%z wal_inode=%i" "$DB-wal" 2>/dev/null || echo "$1 wal ABSENT"
  stat -f "$1 shm_size=%z shm_inode=%i" "$DB-shm" 2>/dev/null || echo "$1 shm ABSENT"
  stat -f "$1 db_inode=%i db_size=%z" "$DB"
}

# Sample at least twice, spaced, plus a final sample before handoff.
verify_sample T0
sleep 5
verify_sample T1
verify_sample final
```

Quiescence is `CONFIRMED` only when every sample reports `PROC_ZERO`, all ports idle, `ZERO_OPEN_HANDLES`,
and identical (`sha256`, `inode`, size) for the DB across `T0`/`T1`/`final`.

```text
STOP_PERSISTENT_SIDECAR — the WAL (`-wal`) or SHM (`-shm`) sidecar must disappear naturally when the
last writer detaches, or remain provably static with ZERO_OPEN_HANDLES. If a sidecar keeps changing
size/inode/mtime while ZERO_OPEN_HANDLES holds — the anomaly observed at baseline (WAL 0B, SHM 32KiB,
SHM mtime advancing with no handle) — DO NOT delete, rename, truncate, copy, or checkpoint it. Emit
STOP_PERSISTENT_SIDECAR and hand to the owner; the sidecar is itself evidence for the probe.
```

```text
STOP_DB_DRIFT — if the DB `sha256` or `inode` changes across T0/T1/final while quiescence is asserted,
a writer is still active or the file was replaced. Do NOT proceed to probe handoff. Emit STOP_DB_DRIFT,
preserve all samples, and hand to the owner.
```

---

## H. Probe Handoff

Handoff is a classification, not an action. Quiescence may be classified `CONFIRMED` only when
Section G passes at every sample and no STOP fired.

```text
On CONFIRMED:
- State explicitly: "launchd/runtime stack quiesced; ZERO_OPEN_HANDLES on the DB family; DB sha256/inode
  stable across T0/T1/final."
- State explicitly: "DB coverage, schema, and row content remain UNPROVEN by this playbook."
- State explicitly: "The SQLite evidence probe is a separate task requiring its own owner authorization
  and its own playbook. This quiescence task does not open the database."
On any STOP (Section J): probe handoff is BLOCKED; restore (Section I) or owner decision follows.
```

---

## I. Restore Procedure

Restore is the **exact reverse** of the stop/respawn-control order, using only launchd-native
mechanisms, and only for what was actually changed. Because the baseline made **no** launchd change
(nothing was loaded to boot out), the baseline restore is correspondingly a no-op — restore only what
Section E/F actually altered.

**Restore order (reverse of Stop order):** (3) frontend → (2) backend → (1) `com.kelvin.lottery.dev`
supervision (re-enable, then re-bootstrap). Start the DB writer (backend) **after** re-enabling
supervision only if supervision was the thing that starts it; never force-start a bare process.

```bash
# (1a) Re-enable the label that was disabled in Section E (reverse of `disable`).
launchctl enable gui/$(id -u)/com.kelvin.lottery.dev
```

```text
(1b) Re-bootstrap — RUNTIME MAPPING DEPENDENCY (unresolved at this evidence base):
`launchctl bootstrap gui/$(id -u) <INSTALLED_PLIST_PATH>` requires an INSTALLED plist path. At the
observed baseline NO installed plist exists in ~/Library/LaunchAgents or any standard directory, and the
repo-root `com.kelvin.lottery.dev.plist` is NOT an installed location. Do NOT bootstrap the repo-root
plist to "restore" — that would newly INSTALL a service that was not previously installed. If the label
was never booted out (baseline case), there is nothing to re-bootstrap and this step is skipped. If a
real installed plist path is later confirmed by the owner, bootstrap it in reverse order; otherwise the
restore of supervision is BLOCKED pending that mapping.
```

```bash
# Bounded start confirmation (only meaningful if a service was actually (re)bootstrapped).
# Health is verified by listener + process + launchd state — NEVER by a network request.
max_attempts=12; interval=5; n=0
while [ "$n" -lt "$max_attempts" ]; do
  if lsof -nP -iTCP:8002 -sTCP:LISTEN >/dev/null 2>&1; then echo "backend listener up at attempt $n"; break; fi
  n=$((n+1)); sleep "$interval"
done
[ "$n" -lt "$max_attempts" ] || echo BOUNDED_START_EXPIRED_EMIT_STOP_RESTORE_FAILED
```

Post-restore evidence: process present for backend/frontend, listeners on 8002/8081, launchd state
shows the label loaded (`launchctl print gui/$(id -u)/com.kelvin.lottery.dev`), and a re-observation of
DB handles/sidecars (a restored backend is expected to hold a DB handle again — that is normal and is
noted, not "fixed").

```text
STOP_RESTORE_FAILED — if the bounded start confirmation expires, or the label cannot be re-enabled /
re-bootstrapped from a confirmed installed plist path, or a required listener never appears: do NOT
force-start, do NOT kill, do NOT retry unbounded. Emit STOP_RESTORE_FAILED, capture evidence, and hand
to the owner.
```

---

## J. Rollback and STOP Classifications

STOP is fail-closed: on any STOP, take no mutating action, preserve all captured evidence, and hand the
decision to the owner. The defined STOP classifications are:

- `STOP_UNIDENTIFIED_DB_HOLDER` — a process/handle/listener on the DB family or service ports cannot be
  attributed to `com.kelvin.lottery.dev` → backend/frontend (Section C).
- `STOP_GRACEFUL_STOP_FAILED` — a service child is alive but only stoppable via a forbidden signal, or
  the bounded stop wait expired (Section F).
- `STOP_PERSISTENT_SIDECAR` — a `-wal`/`-shm` sidecar will not settle / keeps mutating with
  `ZERO_OPEN_HANDLES`, and must not be deleted or checkpointed (Section G).
- `STOP_DB_DRIFT` — DB `sha256`/`inode` changed across samples while quiescence was asserted (Section G).
- `STOP_RESTORE_FAILED` — restore could not complete via launchd-native reverse steps within bounds
  (Section I).

Rollback principle: the only rollback is Section I (reverse-order launchd-native restore of exactly what
was changed). There is no "force rollback." If restore itself STOPs, escalate to the owner.

---

## K. Always-Forbidden Actions

These are forbidden in **every** phase of the quiescence-execution task. They must never appear as an
executable instruction. (Listed here as prohibited documentation, not as commands.)

- `kill -9` / `kill -KILL`, and force-killing any process by any signal (`TERM`, `INT`, `HUP`, `KILL`).
- `pkill -9` / `pkill` against service or DB-holding processes.
- Deleting, editing, or truncating any PID file (`backend.pid`, `frontend.pid`, or any `*.pid`).
- Deleting, renaming, truncating, or copying the WAL/SHM/journal sidecars (`-wal`, `-shm`, `-journal`).
- Opening the database with `sqlite3` or any SQLite client/driver during this quiescence-only task.
- `PRAGMA wal_checkpoint`, `wal_checkpoint`, `VACUUM`, `ATTACH`, `DETACH`, or any DB write/maintenance.
- Copying, dumping, `cp`/`dd`, or backing up the DB file as part of quiescence (the probe/backup is a
  separate authorized task).
- Editing installed plist files, or bootstrapping the repo-root plist to newly install a service.
- Guessing a launchd domain or label; using the ambiguous `launchctl load` / `launchctl unload` forms
  without an exact evidence-backed domain, label, and (for bootstrap) installed path.
- `--force` / force flags on any command; `launchctl kickstart -k` (which kills).
- Stopping, signalling, or otherwise touching any **unidentified** process.
- Executing `stop_all.sh`. **`stop_all.sh` is NONCOMPLIANT**: it deletes PID files (`rm backend.pid` /
  `rm frontend.pid`), sends `kill`, and force-kills ports with `kill -9`. It MUST NOT be used, invoked,
  referenced as an execution step, or copied. `tools/scripts/stop_all.sh` (also deletes PID files) and
  `tools/scripts/stop_mcp_servers.sh` (`pkill -9`) are likewise noncompliant and out of scope.
- Any network access other than none (health checks use `lsof`/`ps`/`launchctl print`, never `curl`).

---

## L. Evidence Retention

- The execution task must emit a terminal report containing: the Section C discovery output, the Section
  D pre-stop baseline, the Section G `T0`/`T1`/`final` samples, the final quiescence classification, and
  any STOP classification with its evidence.
- Report the DB as (`sha256`, size, `inode`, mode, mtime) plus WAL/SHM/journal metadata. Never include
  database **row content**, query results, or any decoded record.
- No secrets, credentials, or tokens in the report.
- No predictive, betting, ROI, or production-readiness claim anywhere in the report.
- Reproducibility: commands are deterministic and read-only; record `origin/main` HEAD, `id -u`, and the
  observed DB `sha256` so a later run can detect drift.

---

## Appendix — Normative vs. example vs. STOP

- **Normative command** (```` ```bash ````): evidence-backed, safe-by-construction, may be executed in
  the separately authorized task **after** its precondition passes.
- **Unresolved mapping** (```` ```text ````): a template that cannot be executed until an owner confirms
  the missing fact (e.g., an installed plist path). Never execute a template with a placeholder.
- **STOP condition** (```` ```text ````): a fail-closed halt; take no mutating action and hand to the owner.

At the current evidence base (`22fe144`), the executable path reduces to **read-only discovery +
verification**: the one defined launchd label is `NOT_INSTALLED`/unloaded, backend/frontend are not
running, and the DB family already reports `ZERO_OPEN_HANDLES`. The state-changing launchd steps
(bootout/disable/enable) apply only if a future observation shows the label actually loaded; the
re-bootstrap step is blocked on an unresolved installed-plist mapping. Hence:
`PLAYBOOK_READY_WITH_RUNTIME_MAPPING_DEPENDENCIES`.
