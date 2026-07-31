# P179 — Replay Product Governance Backlog Decision Gate

**Task**: `P179_REPLAY_PRODUCT_GOVERNANCE_BACKLOG_DECISION_GATE`
**Final Classification**: `P179_REPLAY_PRODUCT_GOVERNANCE_BACKLOG_DECISION_GATE_READY`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start P179 replay product governance backlog decision gate`

---

## Phase 0 Verification — PASS

| Check | Actual | Status |
|-------|--------|--------|
| Repo | `zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | PASS |
| DB rows | `94924` | PASS |
| bet_index | PRESENT | PASS |
| POWER_LOTTO draws | `1913` | PASS |
| Drift guard | PASS | PASS |
| P178A test | 68/68 PASS | PASS |
| P178A classification | `P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED` | PASS |

---

## Current State Confirmation

| Item | Status |
|------|--------|
| P178A closure | `P178A_POWER_LOTTO_R2_RESEARCH_CLOSED_ARCHIVED` ✓ |
| POWER_LOTTO active research | **CLOSED** |
| R1+R2 cumulative result | 17 strategies/candidates, 0 corrected-significant OOS edge |
| Historical replay infrastructure | RETAINED (transparency + audit value) |
| DB rows (zen-gates) | 94,924 — bet_index PRESENT |
| DB rows (main) | ~54,462 — bet_index ABSENT |
| Row delta | **40,462** |
| main/zen-gates split | **UNRESOLVED** |
| DB write (P179) | 0 |
| Merge executed (P179) | None |

---

## Governance Backlog Options

### Option A — MAIN_ZEN_GATES_RECONCILIATION_PLAN_ONLY (RECOMMENDED PRIMARY)

Produce a detailed plan for reconciling the main/zen-gates split. **Plan only — no migration, no merge, no DB write.**

**Scope**:
- Enumerate code/docs/tests gaps between main and zen-gates branches
- Evaluate 3 reconcile options: (A1) promote zen-gates to main, (A2) backport research to main, (A3) document divergence
- Define per-step authorization chain for any future DB migration
- Assess bet_index column migration risk for main DB (currently ABSENT)
- Produce acceptance criteria for reconciled state

**Risks**: HIGH — main DB has 54,462 rows, no bet_index; zen-gates has 94,924 with bet_index. Any migration requires separate exact authorization.

**Output**: Plan artifact only. **No merge. No migration. No schema change.**

---

### Option B — REPLAY_PRODUCT_BACKLOG_AUDIT_PLAN_ONLY (RECOMMENDED PRIMARY)

Audit remaining replay product backlog and prioritize open items. **Plan only — no new feature implementation.**

**Scope**:
- Review P149–P159B replay product governance chain completion status
- Identify remaining UI/API polish items (multi-bet display, bet_index API exposure)
- Assess operator guide and lifecycle visibility gaps
- Evaluate provenance display completeness
- Review long-term monitoring hook readiness
- List open items with priority and acceptance criteria

**Risks**: LOW — audit only.

**Output**: Prioritized backlog list with acceptance criteria. **No implementation.**

---

### Option C — LONG_TERM_MONITORING_GOVERNANCE_PLAN_ONLY (RECOMMENDED SECONDARY)

Define passive monitoring governance for pending trigger conditions. **Plan only. No scheduler install.**

**Scope**:
- Document P108 (100 Special3 draws needed), P117 (40 POWER_LOTTO draws needed), P118 (exact auth phrase absent), 4_STAR (provenance artifact absent)
- Clarify P123 wrapper usage for each trigger
- Confirm: **no cron/launchd installed without separate authorization**
- Define human-review cadence
- POWER_LOTTO passive monitoring: ≥500 new draws required after 115000041

**Risks**: LOW — documentation only.

**Output**: Monitoring governance document. **No scheduler. No new triggers.**

---

### Option D — REOPEN_POWER_LOTTO_RESEARCH (NOT RECOMMENDED)

Reopen POWER_LOTTO active research.

**Why NOT RECOMMENDED**: P178A closure policy is active. 17 strategies/candidates all NULL. Reopen conditions not currently met (0 new draws after 115000041). No prototype authorized without meeting reopen conditions.

**Allowed only if**: ≥500 new draws after 115000041 OR documented structural change OR independent evidence OR new pre-registered hypothesis with power calculation.

---

## CTO Recommendation

**Primary**: Option A + Option B — run as plan-only tasks in sequence (or parallel)  
**Secondary**: Option C — passive monitoring governance after A+B

The highest-value near-term work is resolving the main/zen-gates governance split and auditing the replay product backlog. These are tractable, have clear business value, and require no new research capabilities.

POWER_LOTTO research remains **CLOSED**. C07 hybrid aggregation (p_bonf=0.292) was the strongest R2 signal — still far from threshold 0.0125. This does not justify reopening.

The 40,462-row delta and missing bet_index in main represent the most significant unresolved technical debt. Any reconciliation requires careful per-step authorization.

---

## Explicit Forbidden Actions

The following remain **ENFORCED** throughout P179:

| Action | Status |
|--------|--------|
| DB write | ENFORCED — FORBIDDEN |
| DB migration | ENFORCED — FORBIDDEN |
| Merge / rebase | ENFORCED — FORBIDDEN |
| Checkout other branch | ENFORCED — FORBIDDEN |
| controlled_apply | ENFORCED — FORBIDDEN |
| Champion promotion | ENFORCED — FORBIDDEN |
| Deployment | ENFORCED — FORBIDDEN |
| New POWER_LOTTO strategy | ENFORCED — FORBIDDEN |
| POWER_LOTTO research rerun | ENFORCED — P178A closure policy active |
| Scheduler (cron/launchd) install | ENFORCED — no separate authorization |
| 4_STAR backtest | ENFORCED — provenance artifact absent |
| P108/P117/P118 execution | ENFORCED — wait-state conditions not yet met |
| Wagering recommendations | ENFORCED — FORBIDDEN |
| Win-guarantee claim | ENFORCED — FORBIDDEN |

---

## Required Governance Framing

- **P178A closure policy remains active.** No POWER_LOTTO active research without meeting reopen conditions.
- **POWER_LOTTO results remain consistent with fair-random lottery behavior** across 17 evaluated strategies/candidates.
- **Historical replay remains valuable as transparency/audit layer**, not as evidence of predictive edge.
- **main/zen-gates split is independent from POWER_LOTTO research closure.** Reconciliation is a separate governance task.
- **Any future production DB migration requires separate exact authorization chain.** P179 does not authorize any migration.

---

## CEO Decision Gate

To proceed to P180, provide one of the following authorization phrases:

| Option | Authorization Phrase | Effect |
|--------|---------------------|--------|
| A | `YES start P180 main zen-gates reconciliation plan only` | Reconciliation plan for main/zen-gates split. Plan-only. |
| B | `YES start P180 replay product backlog audit plan only` | Replay product backlog audit. Plan-only. |
| C | `YES start P180 long-term monitoring governance plan only` | Passive monitoring governance. No scheduler. |
| A+B | `YES start P180 combined reconciliation and replay backlog plan only` | Options A and B run concurrently. |
| D* | `YES start P180 reopen POWER_LOTTO research governance review only` | NOT RECOMMENDED. No prototype. Requires P178A reopen conditions. |

---

## Governance Confirmations

| Item | Status |
|------|--------|
| DB rows before/after | 94,924 / 94,924 |
| DB write | 0 |
| Registry mutation | 0 |
| Merge | None |
| controlled_apply | Not executed |
| Champion promotion | Not executed |
| Wagering recommendations | None |
| No win-guarantee claim | Confirmed |
| No stage/commit/push | Confirmed |
| P178A closure policy | UNCHANGED |
| POWER_LOTTO active research | CLOSED |
| main/zen-gates split | Still unresolved |

---

**P180 BLOCKED — requires explicit user authorization.** Provide one of the authorization phrases above to proceed.

---

*P179 is a decision gate only. No actions were executed. POWER_LOTTO research remains closed. Historical replay retains governance transparency value. All lottery games remain deeply negative EV. No wagering recommendations are given.*
