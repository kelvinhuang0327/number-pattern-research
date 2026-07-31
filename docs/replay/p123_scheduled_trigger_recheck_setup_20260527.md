# P123: Scheduled Trigger Recheck Setup

**Date**: 2026-05-27  
**Task ID**: P123_SCHEDULED_TRIGGER_RECHECK_SETUP  
**Final Classification**: `P123_SCHEDULED_TRIGGER_RECHECK_SETUP_READY`

---

## PROJECT_CONTEXT_LOCK

Project = LotteryNew  
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew  
Canonical Branch = main

This document applies ONLY to LotteryNew. Any artifact, context, or governance instruction from another project (Betting-pool, Stock-Prediction-System, Stock, Novel, SCB, etc.) must be treated as context contamination and this task must be classified `P123_BLOCKED_BY_CONTEXT_CONTAMINATION`.

---

## Why P123 Exists

P120, P121, and P122 all produced identical `ALL_TRIGGERS_STILL_BLOCKED` results with no change across three consecutive ad-hoc PRs. Continuing to create new P-task PRs for no-change periodic rechecks adds governance noise without value. P123 introduces a reusable read-only wrapper script that operators can run manually or schedule, so future no-change rechecks do not require a new PR or P-task each time.

---

## Why Repeated No-Change PRs Should Stop

| Task | Classification | Change vs Previous |
|------|---------------|-------------------|
| P120 | P120_ALL_TRIGGERS_BLOCKED | Baseline |
| P121 | P121_ALL_TRIGGERS_STILL_BLOCKED | None |
| P122 | P122_ALL_TRIGGERS_STILL_BLOCKED | None (+ contamination guard) |

Three consecutive no-change rechecks confirms: triggers are blocked pending external events (new draw data or operator authorization). A scheduled or manual wrapper is more appropriate than ad-hoc P-tasks.

---

## Worktree Branch Guard

| Field | Value |
|-------|-------|
| git_dir_expected | `.git` |
| worktree_branches_allowed | **false** |
| claude_codex_worktree_allowed | **false** |
| branch_prefixes_rejected | `claude/`, `codex/` |

Implementation tasks must run from the canonical repo (`/Users/kelvin/Kelvin-WorkSpace/LotteryNew`) on the canonical branch (`main`) or an authorized feature branch. Claude/Codex auto-created worktree branches are NOT authorized.

If `git rev-parse --git-dir` returns a path containing `.git/worktrees/` or the current branch starts with `claude/` or `codex/`, implementation must STOP and the operator must restart from Terminal CLI:

```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
git branch --show-current  # expected: main
git rev-parse --git-dir     # expected: .git
claude
```

---

## Current Post-P122 Baseline

| Metric | Value |
|--------|-------|
| P122 merge commit | `9dcef2e` |
| replay_rows | 54462 |
| 3_STAR count / max draw | 4179 / 115000106 |
| 4_STAR count / max draw | 2922 / 115000103 |
| POWER_LOTTO count / max draw | 1913 / 115000041 |
| Drift guard | PASS |
| Branch governance guard | PASS |

---

## Scheduled Trigger Recheck Design

**Wrapper script**: `scripts/p123_scheduled_trigger_recheck.py`

| Property | Value |
|----------|-------|
| Read-only | Yes |
| Default output dir | `outputs/replay/trigger_rechecks/` |
| Timestamped output | Yes |
| --json-out support | Yes |
| --output-dir support | Yes |
| --operator-input support | Yes |
| --timestamp support | Yes (deterministic tests) |
| Installs OS scheduler | **NO** |
| Mutates crontab | **NO** |
| Creates launchd plist | **NO** |

### Wrapper Script Usage

Manual run (default output dir):
```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
python3 scripts/p123_scheduled_trigger_recheck.py
```

With explicit output path:
```bash
python3 scripts/p123_scheduled_trigger_recheck.py \
  --json-out outputs/replay/trigger_rechecks/recheck_$(date +%Y%m%d).json
```

With custom output directory:
```bash
python3 scripts/p123_scheduled_trigger_recheck.py \
  --output-dir outputs/replay/trigger_rechecks
```

With BIG_LOTTO authorization (to unblock P118):
```bash
python3 scripts/p123_scheduled_trigger_recheck.py \
  --operator-input "YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence"
```

### Optional Cron Example — NOT INSTALLED

The following is provided for future operator reference only. **P123 does NOT install this.**

```
# Example only — NOT INSTALLED by P123
# Run trigger recheck every morning at 09:00
0 9 * * * cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew && .venv/bin/python scripts/p123_scheduled_trigger_recheck.py >> outputs/replay/trigger_rechecks/cron.log 2>&1
```

To install manually (operator decision only):
```bash
crontab -e
# Add the line above, save and exit
```

---

## First Smoke Recheck Result

Script run: `scripts/p123_scheduled_trigger_recheck.py --json-out outputs/replay/trigger_rechecks/p123_trigger_recheck_smoke_20260527.json --timestamp 20260527_000000`

| Field | Value |
|-------|-------|
| Classification | **P122_ALL_TRIGGERS_STILL_BLOCKED** |
| P108 remaining | 37 more Special3 draws |
| P117 partial remaining | 30 more POWER_LOTTO draws |
| P117 full remaining | 40 more POWER_LOTTO draws |
| P118 authorization | absent |
| 4_STAR provenance | not found |
| Contamination | CLEAN |
| Worktree guard | PASS |

Artifact: `outputs/replay/trigger_rechecks/p123_trigger_recheck_smoke_20260527.json`

---

## Current DB Snapshot

| Field | Value |
|-------|-------|
| replay_rows | 54462 |
| 3_STAR draws after P99 cutoff `115000024` | **63** |
| POWER_LOTTO draws after P116 baseline `115000041` | **0** |
| P118 authorization phrase present | **False** |
| 4_STAR provenance acceptance artifact | **Not found** |

---

## Explicit Statements

**P108 was NOT run.** Special3 100-draw re-evaluation remains blocked (63/100 draws). No re-evaluation was executed.

**P117 OOS execution was NOT run.** POWER_LOTTO OOS checkpoint remains blocked (0 new draws). No OOS analysis was performed.

**Actual BIG_LOTTO quarantine was NOT applied.** Authorization phrase was not provided. `fourier30_markov30_biglotto` remains in governance design state only (P115).

**4_STAR backtest was NOT run.** Source remains unknown; no provenance artifact exists. Backtest is not authorized.

**No strategy promotion was authorized.** Promotion is not authorized from P123. No classification in this task permits any strategy promotion.

**No crontab was installed.** P123 provides a sample cron command for future operator use only. No OS scheduler was modified.

**No launchd plist was created.** P123 does not create any launchd service files.

---

## Limitations

1. P118 authorization_present defaults to false unless `--operator-input` supplies the exact phrase.
2. 4_STAR provenance check is file-system based; no live provenance registry exists.
3. P108 count uses P99 cutoff draw `115000024`; if this cutoff changes the count will differ.
4. No change detected since P122: Special3=63, POWER_LOTTO new draws=0.
5. Contamination check is keyword-based on operator_input only; does not scan staged files.
6. This script does NOT install any OS scheduler; operator must install cron/launchd manually if desired.
7. Worktree branch guard is informational in the runtime script; does not block execution.

---

## Forbidden-Staging Scan

Staged files for this commit (whitelist only):

```
outputs/replay/p123_scheduled_trigger_recheck_setup_20260527.json
docs/replay/p123_scheduled_trigger_recheck_setup_20260527.md
tests/test_p123_scheduled_trigger_recheck_setup.py
scripts/p123_scheduled_trigger_recheck.py
outputs/replay/trigger_rechecks/p123_trigger_recheck_smoke_20260527.json
```

No DB files (`.db`, `.wal`, `.shm`), history files, runtime files, or backup files are staged.

---

## Test Summary

Tests file: `tests/test_p123_scheduled_trigger_recheck_setup.py`  
Minimum 60 tests covering: JSON/MD artifact existence, classification validity, invariant guards, worktree branch guard fields, scheduled_recheck_design fields, smoke result fields, script content checks, runtime artifact checks, live DB check, forbidden-staging compliance.

---

## Guard Summary

| Guard | Status |
|-------|--------|
| Drift guard (`--strict`) | PASS |
| Branch governance guard (pre-flight on `p123-scheduled-trigger-recheck-setup`) | PASS |

---

## Final Classification

```
P123_SCHEDULED_TRIGGER_RECHECK_SETUP_READY
```

Scheduled trigger recheck wrapper created. First smoke run confirms `P122_ALL_TRIGGERS_STILL_BLOCKED`. No change since P122. Contamination: CLEAN. No crontab installed. No launchd plist created.

---

## Next Recommended Operator Action

Use `scripts/p123_scheduled_trigger_recheck.py` for all future no-change trigger rechecks instead of creating new P-task PRs. Run it manually after each new draw ingestion:

```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
python3 scripts/p123_scheduled_trigger_recheck.py
```

Output will be written to `outputs/replay/trigger_rechecks/trigger_recheck_<timestamp>.json`.

Create a new P-task PR only when a trigger becomes ELIGIBLE (i.e., classification is no longer `P122_ALL_TRIGGERS_STILL_BLOCKED`).

Nearest unblock conditions:
- **37 more Special3 (3_STAR) draws** → P108 becomes eligible
- **30 more POWER_LOTTO draws** → P117 partial checkpoint becomes eligible
- **Operator provides exact P118 phrase** → P118 BIG_LOTTO quarantine becomes eligible
