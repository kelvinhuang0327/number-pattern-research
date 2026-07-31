# P25 Production Replay Backfill Decision Memo

**Date:** 2026-05-12  
**Author:** AI Agent (P25 Mission)  
**Status:** DECISION MADE — NO BACKFILL  
**Scope:** Strategy Historical Replay section — non-ONLINE lifecycle strategies

---

## 1. Context

The Production DB (`lottery_api/data/lottery_v2.db`) currently contains **460 replay rows** across **6 ONLINE strategies only**. The canonical strategy registry has **16 strategies total** (6 ONLINE, 4 REJECTED, 5 RETIRED, 1 OBSERVATION, 0 OFFLINE).

P24 identified the gap: non-ONLINE strategies (10 total) have zero production replay rows, making them invisible in the Replay UI despite being formally registered.

P25 closes this gap via **display-only catalog mode** (frontend-only, no DB write). This memo records the explicit decision NOT to backfill the production DB.

---

## 2. Three Options Considered

### Option A — Display-Only Catalog (Recommended ✅ SELECTED)
**What it is:** Frontend shows registered strategies as catalog rows when `lifecycle_status ≠ ONLINE` filter returns 0 records. Fetches from `/api/replay/strategies` (read-only). No DB write.

**Pros:**
- Zero production risk — no DB mutations
- Immediate: delivers CTO-evaluable UI in current sprint
- Reversible: can be toggled off with a 3-line JS change
- Honest: clearly labels rows as "無歷史回放資料", no fake data
- Passes all governance safety checks

**Cons:**
- Non-ONLINE strategies show no prediction numbers, hit counts, or causal chain data (by design — they were never run against production draws)
- Does not add real historical context for rejected/retired strategies

**Risk:** None. Read-only, no generation, no DB write.

---

### Option B — Dry-Run Manifest (Informational, No Execution)
**What it is:** Generate an offline JSON manifest listing what a backfill WOULD cover (strategy IDs, draw ranges, estimated row counts) — for CTO review only, not executed.

**Pros:**
- Gives CTO full information for a future YES/NO gate
- No production risk at generation time
- Can be queued for a controlled future sprint

**Cons:**
- Does not solve the current UI gap (strategies still invisible without Option A)
- Requires additional work (manifest generator script)
- Manifest may become stale if registry changes

**Risk:** Low. Manifest is documentation only.

---

### Option C — Controlled Backfill (Requires CEO YES Gate, NOT NOW)
**What it is:** Execute replay generation for non-ONLINE strategies using historical draw data, INSERT results into production DB.

**Pros:**
- Would provide real historical replay numbers for all 16 strategies
- Full audit trail possible

**Cons:**
- Requires explicit YES gate from authorized stakeholder (CTO/CEO level)
- Production DB mutation — irreversible without manual rollback
- Non-ONLINE strategies (REJECTED/RETIRED) were explicitly excluded from production runs — backfilling them retroactively may introduce misleading data
- REJECTED strategies failed governance gates — showing their replay numbers as equivalent to ONLINE strategies is misleading to users
- Would require strategy execution engine modifications to run REJECTED/RETIRED adapters
- **NOT appropriate for current sprint**

**Risk:** High. DB write to production. Requires explicit authorization.

---

## 3. Decision

**Selected: Option A only (Display-Only Catalog).**

Option B (dry-run manifest) is noted as a preparatory step for any future C consideration, but is not required for P25 completion.

**Option C is explicitly deferred indefinitely.** It requires a separate CEO/CTO written YES authorization and a dedicated sprint with:
- Governance review
- Staging DB test run
- Rollback plan
- Data quality audit

---

## 4. Rationale

1. **REJECTED strategies should not show replay numbers without clear context.** These strategies failed the governance gate. Displaying their historical numbers alongside ONLINE strategies without clear differentiation could mislead stakeholders about their relative quality.

2. **RETIRED strategies are legacy.** Their historical context is preserved in `legacy/` directories and analysis reports. Adding DB rows without governance review would create audit confusion.

3. **The display-only catalog achieves the stated goal:** "所有系統開發過策略在 Replay 頁面可見." Non-ONLINE strategies are now visible in the UI with their correct lifecycle badge and clear "無歷史回放資料" labeling.

4. **Safety first.** This system is governed by hard rules: no production DB write, no strategy promotion, no replay generation without authorization. Option A respects all these rules.

---

## 5. Production DB State Post-P25

| Field | Value |
|-------|-------|
| DB path | `lottery_api/data/lottery_v2.db` |
| Total replay rows | 460 (unchanged) |
| Strategies with rows | 6 (ONLINE only, unchanged) |
| DB write operations | 0 (none in P25) |
| Schema changes | None |

**P25_POST_RUN_DB_CLEAN confirmed:** No production DB rows were added, modified, or deleted during P25 implementation.

---

## 6. Future Backfill Gate (If Needed)

If a future sprint considers Option C, the following must be satisfied before any execution:

- [ ] Written YES from CTO/CEO (in writing, not inferred)
- [ ] Staging DB dry-run with full diff review
- [ ] Separate governance PR (not bundled with feature PRs)
- [ ] Clear UI differentiation between ONLINE rows and backfill rows
- [ ] Rollback plan documented and tested
- [ ] No REJECTED/RETIRED strategy backfill without separate per-strategy authorization

**This gate is NOT satisfied as of P25.**

---

## 7. Markers

- `P25_BACKFILL_DECISION_MEMO_COMPLETE_NO_WRITE`
- `P25_POST_RUN_DB_CLEAN`
- `WAITING_FOR_USER_YES_GATE_BACKFILL_OPTION_C`
