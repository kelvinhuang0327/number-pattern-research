# P181 — Code/Docs/Tests Parity Plan (Plan Only)

**Task**: `P181_CODE_DOCS_TESTS_PARITY_PLAN_ONLY`
**Final Classification**: `P181_CODE_DOCS_TESTS_PARITY_PLAN_READY`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start P181 code-docs-tests parity plan only`

---

## Phase 0 Verification — PASS

| Check | Actual | Status |
|-------|--------|--------|
| Repo | `zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | PASS |
| DB rows | `94924` | PASS |
| bet_index | PRESENT | PASS |
| Drift guard | PASS | PASS |
| P178A/P179/P180 tests | PASS | PASS |

---

## Part A — Parity Gap Inventory

*Based on prior audits (P163, P180). No main branch checkout performed in P181.*

| Item | zen-gates | main | Delta |
|------|-----------|------|-------|
| DB rows | **94,924** | 54,462 | **40,462** |
| bet_index | **PRESENT** | ABSENT | schema gap |
| P161–P180 test contracts | **26 files** | 0 | all missing |
| Research artifacts | **20 JSON + 20 MD** | None | all missing |
| Analysis scripts | **5 files** | Unknown | needs comparison |
| Roadmap docs | **Current P161–P181** | Stale | needs update |

**main/zen-gates split remains UNRESOLVED.**

---

## Part B — Code/Docs/Tests Parity Scope

### Code Parity

**Include** (Safe/Medium risk):
- `analysis/power_lotto/p161_effectiveness_baseline.py`
- `analysis/power_lotto/p167_ensemble_voting_research.py`
- `analysis/power_lotto/p170_threshold_sensitivity_and_signal_tracking.py`
- `analysis/power_lotto/p173_new_strategy_minimal_prototype_read_only.py`
- `analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py`
- `scripts/replay_lifecycle_drift_guard.py` (verify parity)

**Exclude** (requires separate review):
- `lottery_api/` production code (may conflict with P149–P159B main changes)
- Any tool with DB write capability

### Docs Parity

**Include** (Very low risk):
- `00-Plan/roadmap/active_task.md`
- `00-Plan/roadmap/roadmap.md`
- `00-Plan/roadmap/CTO-Analysis.md`
- `docs/replay/` markdown files (if absent in main)
- `outputs/research/power_lotto/` all 20 JSON + 20 MD artifacts (P161–P180)

### Tests Parity

**Include** (with compatibility gating):
- `tests/test_p161_*.py` through `tests/test_p180_*.py` (20 contract files)

**Risk**: MEDIUM — DB-dependent tests will FAIL against main 54,462-row DB until migration.
**Mitigation**: Part D test compatibility strategy.

### Explicitly Excluded from P181

- DB file copy, DB migration, schema migration
- Row insertion into main DB
- controlled_apply, branch merge, checkout main
- POWER_LOTTO strategy research rerun

---

## Part C — Backport Execution Design (for future P182)

*P181 does not execute any of these steps. This is the design for future authorization.*

| Step | Action | Risk |
|------|--------|------|
| 1 | Create comparison checklist (`git diff zen-gates main -- <file>`) | VERY LOW |
| 2 | Determine exact file list for backport | LOW |
| 3 | Classify into Safe / Medium / Risky tiers | LOW |
| 4 | Define P182 allowed whitelist (Safe + Medium tiers only) | LOW |
| 5 | Pre-flight checks in main: `git status`, DB row count, CI status, DB backup | MEDIUM |
| 6 | Define acceptance tests post-backport (DB-independent only) | LOW |
| 7 | Preserve main DB: all scripts run with `PRAGMA query_only=ON` | LOW |
| 8 | Gate DB-dependent tests with `@requires_zen_gates_db` marker | MEDIUM |

**Tier classification**:
- **Safe**: `00-Plan/roadmap/*.md`, `outputs/research/power_lotto/`, `docs/replay/`
- **Medium**: `analysis/power_lotto/*.py`, `scripts/replay_lifecycle_drift_guard.py`
- **Risky**: `lottery_api/**`, `tools/**` — excluded from P182 whitelist

---

## Part D — Test Compatibility Strategy

### Problem

P161–P180 contract tests assume zen-gates DB (94,924 rows, bet_index PRESENT). After backport to main, many tests would FAIL — not because tests are wrong, but because main DB is stale.

### Solution: Tiered Test Gating

| Tier | Type | Gate | On main |
|------|------|------|---------|
| T1 | DB-independent (artifact, JSON, doc checks) | None — always run | **PASS** |
| T2 | DB row-count dependent (`== 94924`) | `@pytest.mark.requires_zen_gates_db` | **SKIP** |
| T3 | bet_index dependent | `@pytest.mark.requires_bet_index` | **SKIP** |
| T4 | Analysis script execution (P161/P167/P170/P173/P176) | `@pytest.mark.requires_zen_gates_db` | **SKIP** |

**Key principle**: Tests SKIP on stale DB — they do NOT FAIL. SKIP preserves governance without false signals.

### conftest.py Extension Design

```python
# tests/conftest.py (extend, do not replace)
# Add:
# @pytest.mark.requires_zen_gates_db  → skip if db_rows != 94924
# @pytest.mark.requires_bet_index     → skip if bet_index column absent
```

### Forbidden Approaches

- Changing `== 94924` to `>= 54000` — **FORBIDDEN**
- Removing DB row count checks — **FORBIDDEN**
- Changing contract semantics — **FORBIDDEN**
- Hardcoding main-specific row counts — **FORBIDDEN**

---

## Part E — P182 Options

| Option | Authorization Phrase | Effect |
|--------|---------------------|--------|
| A | `YES start P182 code-docs-tests parity backport execution plan only` | Detailed plan. No files modified. |
| **B** | `YES start P182 code-docs-tests parity backport implementation no DB write` | **Execute Safe + Medium tier backport. No DB write. Tests gated per Part D.** (Recommended) |
| C | `YES start P182 controlled DB migration rehearsal plan only` | Rehearsal design. No migration. |
| D | `YES start P182 replay product UI backlog implementation plan only` | Plan for multi-bet UI + docs. |
| E | `YES start P182 maintain documented divergence and pause reconciliation` | Accept split. No backport. |

**P182 BLOCKED until CEO provides one of the above authorization phrases.**

---

## Part F — CTO Recommendation

**Primary**: `YES start P182 code-docs-tests parity backport implementation no DB write`  
**Timing**: Only after P181 plan is reviewed by user.

**DB migration**: Remains deferred. Sequence: code/docs/tests parity first → DB rehearsal design → DB migration only with explicit authorization.

**Implementation environment note**: If P182 backport targets main branch, it MUST be launched from the correct main repo/branch environment — NOT from zen-gates worktree.

**POWER_LOTTO research**: Remains CLOSED per P178A.

---

## Explicit Forbidden Actions

| Action | Status |
|--------|--------|
| DB write | ENFORCED — FORBIDDEN |
| DB migration | ENFORCED — FORBIDDEN |
| DB copy | ENFORCED — FORBIDDEN |
| Merge / rebase | ENFORCED — FORBIDDEN |
| Checkout main | ENFORCED — NOT performed in P181 |
| controlled_apply | ENFORCED — FORBIDDEN |
| Registry mutation | ENFORCED — FORBIDDEN |
| Champion promotion | ENFORCED — FORBIDDEN |
| Deployment | ENFORCED — FORBIDDEN |
| POWER_LOTTO research rerun | ENFORCED — P178A closure active |
| Backport execution | CONFIRMED — P181 is plan-only; no files copied to main |
| Stage/commit/push | ENFORCED — FORBIDDEN |
| Wagering recommendations | ENFORCED — FORBIDDEN |
| Win-guarantee claim | ENFORCED — FORBIDDEN |

---

## Governance Confirmations

| Item | Status |
|------|--------|
| DB rows before/after | 94,924 / 94,924 |
| DB write | 0 |
| No merge performed | Confirmed |
| No checkout performed | Confirmed |
| No backport executed | Confirmed (plan-only) |
| P178A closure policy | ACTIVE |
| POWER_LOTTO active research | CLOSED |
| main/zen-gates split | Still unresolved |

---

*P181 is a plan-only document. No files were copied, merged, or modified in main. The main/zen-gates split remains unresolved. POWER_LOTTO research remains closed per P178A. No wagering recommendations are given. No win outcome is guaranteed.*
