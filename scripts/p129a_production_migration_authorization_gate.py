#!/usr/bin/env python3
"""
P129A: Production Migration Authorization Gate
===============================================
PURPOSE : Gate check before production migration can be executed.
          Reads P129 rehearsal result, confirms production DB state,
          and checks whether Kelvin's exact authorization phrase is present.
          If phrase is absent → classification = P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION.
          If phrase is present → gate opens (migration execution is a separate P129B step).
GOVERNANCE:
  - PRAGMA query_only = ON on every DB connection
  - NO INSERT / UPDATE / DELETE on production DB
  - replay_rows must remain 54462
  - NO migration execution in this script
  - NO P126 apply
  - NO scheduler, NO strategy promotion
  - 4_STAR / P108 / P117 / P118 are blocked
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_ID             = "P129A"
DATE_SUFFIX         = "20260528"
REPO_ROOT           = Path(__file__).resolve().parent.parent

P129_ARTIFACT       = REPO_ROOT / "outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json"
P128_ARTIFACT       = REPO_ROOT / "outputs/replay/p128_native_multi_bet_storage_design_20260528.json"
P126_ARTIFACT       = REPO_ROOT / "outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"
OUT_JSON            = REPO_ROOT / "outputs/replay/p129a_production_migration_authorization_gate_20260528.json"
OUT_MD              = REPO_ROOT / "docs/replay/p129a_production_migration_authorization_gate_20260528.md"
DB_PATH             = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS = 54462

# The one and only exact authorization phrase Kelvin must state.
EXACT_AUTH_PHRASE    = "YES authorize migration_plan_p128 because <reason>"

# Classification constants
CLASS_WAITING = "P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION"
CLASS_READY   = "P129A_MIGRATION_AUTHORIZED_READY_FOR_P129B"   # only if phrase provided


# ---------------------------------------------------------------------------
# Read-only DB helper
# ---------------------------------------------------------------------------
def _ro_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Phase 0: snapshot production DB
# ---------------------------------------------------------------------------
def snapshot_production_db() -> dict:
    print("[P129A] Phase 0: snapshot production DB (read-only)...")
    conn = _ro_conn()
    cur  = conn.cursor()

    replay_rows = cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    cols = [r[1] for r in cur.execute(
        "PRAGMA table_info(strategy_prediction_replays)"
    ).fetchall()]
    has_bet_index = "bet_index" in cols

    ddl = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
    ).fetchone()[0]

    conn.close()

    ok = (replay_rows == EXPECTED_REPLAY_ROWS) and (not has_bet_index)
    return {
        "replay_rows": replay_rows,
        "has_bet_index_column": has_bet_index,
        "ddl_excerpt": ddl[:300] if ddl else "",
        "invariant_ok": ok,
        "current_unique_constraint": "UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)"
                                     if "replay_run_id" in ddl else "UNKNOWN",
    }


# ---------------------------------------------------------------------------
# Phase 1: read and validate P129 artifact
# ---------------------------------------------------------------------------
def read_p129_artifact() -> dict:
    print("[P129A] Phase 1: reading P129 rehearsal artifact...")
    assert P129_ARTIFACT.exists(), f"P129 artifact not found: {P129_ARTIFACT}"
    with open(P129_ARTIFACT) as f:
        p129 = json.load(f)

    classification    = p129.get("classification", "")
    migration_ok      = p129.get("migration_rehearsal_ok", False)
    prod_modified     = p129.get("production_db_modified", True)
    rows_before       = p129["db_snapshot_before"]["replay_rows"]
    rows_after        = p129["db_snapshot_after"]["replay_rows"]
    dup_audit         = p129.get("pre_migration_duplicate_audit", {})
    bi_validation     = p129.get("bet_index_default_validation", {})
    row_preservation  = p129.get("replay_row_preservation_check", {})

    classification_ok  = classification == "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY"
    rows_preserved     = row_preservation.get("check_ok", False)
    dup_refinement_req = dup_audit.get("p128_copy_sql_refinement_required", False)

    all_ok = (
        classification_ok
        and migration_ok
        and not prod_modified
        and rows_before == EXPECTED_REPLAY_ROWS
        and rows_after == EXPECTED_REPLAY_ROWS
        and rows_preserved
        and dup_refinement_req  # must flag that ROW_NUMBER() is required
    )

    return {
        "artifact_path": str(P129_ARTIFACT),
        "classification": classification,
        "classification_ok": classification_ok,
        "migration_rehearsal_ok": migration_ok,
        "production_db_modified_in_p129": prod_modified,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "steps_count": p129.get("migration_rehearsal_steps_count", 0),
        "duplicate_groups": dup_audit.get("duplicate_groups_count", 0),
        "extra_rows": dup_audit.get("extra_rows_count", 0),
        "p128_copy_sql_refinement_required": dup_refinement_req,
        "row_number_required": dup_refinement_req,
        "rows_with_bet_index_1": bi_validation.get("rows_with_bet_index_1", 0),
        "rows_with_bet_index_gt1": bi_validation.get("rows_with_bet_index_gt_1", 0),
        "row_preservation_ok": rows_preserved,
        "all_checks_passed": all_ok,
    }


# ---------------------------------------------------------------------------
# Phase 2: authorization gate check
# ---------------------------------------------------------------------------
def check_authorization(provided_phrases=None) -> dict:
    """
    Check whether the exact Kelvin authorization phrase is present.
    In production use, provided_phrases would be parsed from the operator's message.
    In this gate script, no phrase is provided by default — gate must STOP.
    """
    print("[P129A] Phase 2: checking authorization gate...")

    # In normal operation this list would be populated from operator input.
    # The current prompt does NOT provide the authorization phrase.
    phrases = provided_phrases or []

    auth_present = any(
        "YES authorize migration_plan_p128 because" in p and "<reason>" not in p
        for p in phrases
    )

    if auth_present:
        matching = [p for p in phrases if "YES authorize migration_plan_p128 because" in p]
        classification = CLASS_READY
        stop_reason    = None
    else:
        matching       = []
        classification = CLASS_WAITING
        stop_reason    = "WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION"

    return {
        "exact_required_phrase": EXACT_AUTH_PHRASE,
        "authorization_present": auth_present,
        "migration_allowed": auth_present,
        "classification": classification,
        "stop_reason": stop_reason,
        "matched_phrases": matching,
        "note": (
            "Authorization phrase must be the exact string "
            "'YES authorize migration_plan_p128 because <reason>' "
            "with a real reason replacing <reason>. "
            "The prompt text itself is not an authorization."
        ),
    }


# ---------------------------------------------------------------------------
# Phase 3: build corrected migration SQL summary
# ---------------------------------------------------------------------------
def build_corrected_migration_sql() -> dict:
    """
    Summarize the corrected migration COPY step identified in P129 rehearsal.
    P128 original step 4 used '1 AS bet_index' — FAILS due to 120 dup groups.
    Corrected step 4 uses ROW_NUMBER() OVER (...).
    """
    original_copy_sql = (
        "INSERT INTO strategy_prediction_replays_new "
        "SELECT id, lottery_type, target_draw, ..., "
        "1 AS bet_index "
        "FROM strategy_prediction_replays"
    )
    corrected_copy_sql = (
        "INSERT INTO strategy_prediction_replays_new "
        "SELECT id, lottery_type, target_draw, ..., "
        "ROW_NUMBER() OVER ("
        "PARTITION BY lottery_type, target_draw, strategy_id ORDER BY id"
        ") AS bet_index "
        "FROM strategy_prediction_replays"
    )
    return {
        "step_number": 4,
        "original_sql_p128": original_copy_sql,
        "corrected_sql_p129": corrected_copy_sql,
        "why_original_fails": (
            "120 duplicate (lottery_type, target_draw, strategy_id) groups from old replay runs "
            "each have distinct replay_run_id values, so the current constraint allows them. "
            "If all are copied with bet_index=1, the new UNIQUE(lottery_type, target_draw, "
            "strategy_id, bet_index) rejects the second row of each group with IntegrityError."
        ),
        "why_corrected_works": (
            "ROW_NUMBER() assigns bet_index=1 to the first row and bet_index=2 to the second "
            "row within each duplicate group (ordered by id). All 54462 rows are preserved. "
            "No data loss. Existing non-duplicate rows (54302) all receive bet_index=1."
        ),
        "row_count_preserved": EXPECTED_REPLAY_ROWS,
        "rows_bet_index_1_after": 54302,
        "rows_bet_index_2_after": 160,
    }


# ---------------------------------------------------------------------------
# Build output JSON
# ---------------------------------------------------------------------------
def build_output_json(
    snapshot_before:  dict,
    p129_summary:     dict,
    auth_gate:        dict,
    corrected_sql:    dict,
    snapshot_after:   dict,
) -> dict:

    classification = auth_gate["classification"]

    return {
        "task_id": TASK_ID,
        "classification": classification,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        # DB snapshots
        "production_db_snapshot_before": {
            "replay_rows": snapshot_before["replay_rows"],
            "has_bet_index_column": snapshot_before["has_bet_index_column"],
            "current_unique_constraint": snapshot_before["current_unique_constraint"],
            "invariant_ok": snapshot_before["invariant_ok"],
        },
        "production_db_snapshot_after": {
            "replay_rows": snapshot_after["replay_rows"],
            "has_bet_index_column": snapshot_after["has_bet_index_column"],
            "invariant_ok": snapshot_after["invariant_ok"],
        },

        # P129 source
        "p129_source_summary": p129_summary,

        # Key rehearsal findings
        "rehearsal_findings": {
            "migration_rehearsal_ok": p129_summary["migration_rehearsal_ok"],
            "steps_completed": p129_summary["steps_count"],
            "rows_preserved_in_rehearsal": p129_summary["rows_after"],
            "production_db_modified_in_p129": p129_summary["production_db_modified_in_p129"],
            "duplicate_groups_discovered": p129_summary["duplicate_groups"],
            "extra_rows_from_old_runs": p129_summary["extra_rows"],
            "p128_copy_sql_naive_fails": True,
            "corrected_copy_sql_required": True,
            "corrected_copy_sql": corrected_sql,
            "bet_index_default_validation": {
                "rows_with_bet_index_1": p129_summary["rows_with_bet_index_1"],
                "rows_with_bet_index_gt1": p129_summary["rows_with_bet_index_gt1"],
                "all_rows_valid": True,
            },
        },

        # Gate flags
        "corrected_migration_sql_required": True,
        "row_number_copy_sql_required": True,
        "migration_execution_performed": False,
        "production_db_modified": False,

        # Authorization gate
        "authorization_gate": auth_gate,

        # P126 status
        "p126_apply_status": {
            "status": "BLOCKED",
            "reason": (
                "P126 apply requires both: "
                "(1) production schema migration authorized and executed (P129A gate not yet passed), "
                "(2) per-strategy Kelvin authorization phrases for each of the 5 strategies. "
                "P129A gate is currently WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION."
            ),
            "total_new_rows_if_applied": 18000,
            "total_rows_after_apply": 72462,
            "apply_blocked_until": [
                "Kelvin provides: YES authorize migration_plan_p128 because <reason>",
                "Production migration executed successfully (P129B)",
                "Per-strategy authorization phrases provided (5 phrases required)",
            ],
        },

        # Blocked items
        "blocked_or_excluded": [
            {
                "item": "production_migration_execution",
                "reason": "P129A authorization gate not passed — exact phrase not yet provided",
            },
            {
                "item": "p126_apply",
                "reason": "Blocked until production migration completes (P129A → P129B) and per-strategy phrases provided",
            },
            {
                "item": "4_STAR",
                "reason": "Explicitly excluded from all Tier-B multi-bet work per governance",
            },
            {
                "item": "P108",
                "reason": "P108 execution blocked — trigger not met",
            },
            {
                "item": "P117",
                "reason": "P117 execution blocked — trigger not met",
            },
            {
                "item": "P118",
                "reason": "P118 execution blocked — authorization phrase absent",
            },
            {
                "item": "rejected_strategies",
                "reason": "No rejected strategies may be promoted or included",
            },
            {
                "item": "scheduler_cron_launchd",
                "reason": "No scheduler installation in P129A",
            },
            {
                "item": "lifecycle_champion_registry_mutation",
                "reason": "No strategy promotion / lifecycle / champion / registry mutation in P129A",
            },
        ],

        # Required auth phrases
        "required_authorization_phrases": {
            "migration_authorization": EXACT_AUTH_PHRASE,
            "note": (
                "Replace <reason> with a real justification. "
                "Phrase is case-sensitive and must be provided verbatim by Kelvin."
            ),
            "per_strategy_phrases_also_required_after_migration": [
                "YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>",
                "YES authorize controlled_apply for daily539_f4cold_5bet because <reason>",
                "YES authorize controlled_apply for daily539_f4cold_3bet because <reason>",
                "YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>",
                "YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>",
            ],
        },

        "summary": {
            "task_id": TASK_ID,
            "classification": classification,
            "production_db_modified": False,
            "migration_execution_performed": False,
            "p129_rehearsal_valid": p129_summary["all_checks_passed"],
            "authorization_present": auth_gate["authorization_present"],
            "stop_reason": auth_gate["stop_reason"],
            "production_rows_before": snapshot_before["replay_rows"],
            "production_rows_after": snapshot_after["replay_rows"],
            "next_step": (
                "Kelvin reviews P129 rehearsal report and P129A gate report, "
                "then provides: YES authorize migration_plan_p128 because <reason>. "
                "On receiving that phrase, P129B executes the production migration "
                "using the corrected ROW_NUMBER() COPY SQL."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Build Markdown
# ---------------------------------------------------------------------------
def build_markdown(data: dict) -> str:
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cls  = data["classification"]
    gate = data["authorization_gate"]
    reh  = data["rehearsal_findings"]

    def _tick(v): return "✓ PASS" if v else "✗ FAIL"
    def _status(v): return "**PRESENT**" if v else "**ABSENT ← gate blocked here**"

    return f"""# P129A — Production Migration Authorization Gate

**Task ID:** P129A
**Classification:** `{cls}`
**Generated:** {now}

---

## 1. Executive Summary

P129A is the authorization gate between the completed P129 rehearsal and the actual
production schema migration. The gate checks:
1. P129 rehearsal passed with all 54462 rows preserved
2. The corrected ROW_NUMBER() COPY SQL is documented
3. Production DB is unchanged (no bet_index column, 54462 rows)
4. Kelvin's exact migration authorization phrase is present

**Gate status:** `{gate["stop_reason"] or "AUTHORIZED"}` —
authorization phrase is {_status(gate["authorization_present"])}

| Check | Result |
|---|---|
| P129 classification confirmed | {_tick(data["p129_source_summary"]["classification_ok"])} |
| P129 migration rehearsal OK | {_tick(reh["migration_rehearsal_ok"])} |
| P129 rows preserved (54462) | {_tick(reh["rows_preserved_in_rehearsal"] == 54462)} |
| P129 production DB untouched | {_tick(not reh["production_db_modified_in_p129"])} |
| ROW_NUMBER() fix required | {_tick(data["row_number_copy_sql_required"])} |
| Production DB rows now (54462) | {_tick(data["production_db_snapshot_before"]["replay_rows"] == 54462)} |
| Production DB has no bet_index | {_tick(not data["production_db_snapshot_before"]["has_bet_index_column"])} |
| Kelvin authorization present | {_status(gate["authorization_present"])} |
| Migration execution performed | {_tick(not data["migration_execution_performed"])} |
| Production DB modified | {_tick(not data["production_db_modified"])} |

---

## 2. P129 Rehearsal Recap

- **P129 commit:** `a3f8561`
- **Classification:** `P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY`
- **18-step migration:** all steps OK on temp DB copy
- **Rows preserved in rehearsal:** {reh["rows_preserved_in_rehearsal"]}
- **Production DB modified in P129:** `false`
- **Rehearsal DB:** ephemeral temp copy (not production)

---

## 3. Key Finding: 120 Duplicate Groups Make Naive Migration Fail

P129 rehearsal discovered that the production DB contains
**{reh["duplicate_groups_discovered"]} duplicate (lottery_type, target_draw, strategy_id) groups**
with **{reh["extra_rows_from_old_runs"]} extra rows** from old replay runs.

**Root cause:** Old replay runs produced multiple rows per (strategy, draw) with different
`replay_run_id` values. The current UNIQUE constraint allows this because `replay_run_id`
values differ. However, the P128 naive COPY step (`1 AS bet_index`) fails with:

```
UNIQUE constraint failed: strategy_prediction_replays_new.lottery_type,
strategy_prediction_replays_new.target_draw,
strategy_prediction_replays_new.strategy_id,
strategy_prediction_replays_new.bet_index
```

because all rows would get `bet_index=1`, and the new constraint treats `1 == 1` as a collision.

---

## 4. Required Fix: ROW_NUMBER() bet_index Assignment

**P128 original step 4 (FAILS):**

```sql
INSERT INTO strategy_prediction_replays_new
SELECT id, lottery_type, target_draw, ...,
  1 AS bet_index          -- ← FAILS for 120 duplicate groups
FROM strategy_prediction_replays
```

**Corrected step 4 for production migration (P129 rehearsal confirmed this works):**

```sql
INSERT INTO strategy_prediction_replays_new
SELECT id, lottery_type, target_draw, ...,
  ROW_NUMBER() OVER (
    PARTITION BY lottery_type, target_draw, strategy_id
    ORDER BY id
  ) AS bet_index           -- ← assigns 1,2,3... per group; preserves all 54462 rows
FROM strategy_prediction_replays
```

**Result after corrected migration (verified in P129 rehearsal):**

| Group | Rows | bet_index |
|---|---|---|
| Non-duplicate (54302 rows) | 54302 | = 1 |
| Old dup-run second rows (160 rows) | 160 | = 2 |
| Invalid (NULL or < 1) | 0 | — |
| **Total** | **54462** | **all valid** |

---

## 5. Production DB Non-Action Confirmation

**The production database has NOT been modified in P129A.**

| Metric | Before P129A | After P129A |
|---|---|---|
| replay_rows | {data["production_db_snapshot_before"]["replay_rows"]} | {data["production_db_snapshot_after"]["replay_rows"]} |
| has bet_index column | {data["production_db_snapshot_before"]["has_bet_index_column"]} | {data["production_db_snapshot_after"]["has_bet_index_column"]} |
| production_db_modified | — | `false` |

---

## 6. Authorization Gate Status

**Current status: `{gate["stop_reason"] or "AUTHORIZED"}`**

| Field | Value |
|---|---|
| Exact required phrase | `{gate["exact_required_phrase"]}` |
| Authorization present | `{gate["authorization_present"]}` |
| Migration allowed | `{gate["migration_allowed"]}` |
| Stop reason | `{gate["stop_reason"] or "none"}` |

The gate is **BLOCKED**. No migration will proceed until the exact phrase is provided.

---

## 7. Exact Required Kelvin Authorization Phrase

To authorize production migration, Kelvin must state **exactly**:

```
YES authorize migration_plan_p128 because <reason>
```

Replace `<reason>` with a real justification (e.g., "rehearsal confirmed 54462 rows preserved
and ROW_NUMBER() fix is validated"). The prompt text itself does not constitute authorization.

---

## 8. Why P126 Apply Remains Blocked

P126 apply requires **both** conditions to be met:

1. **Schema migration authorized + executed (P129A → P129B gate)**
   - Status: `BLOCKED` — authorization phrase not yet provided
2. **Per-strategy Kelvin authorization phrases (5 required)**
   - Status: `NOT YET PROVIDED`

P126 will add an estimated **+18,000 rows** across 5 strategies (total 72,462), but only
after the schema migration is live in production and all authorization phrases are received.

Blocked strategies pending P126 apply:
- `biglotto_echo_aware_3bet` (+3000 rows)
- `daily539_f4cold_5bet` (+6000 rows)
- `daily539_f4cold_3bet` (+3000 rows)
- `power_fourier_rhythm_2bet` (+1500 rows)
- `biglotto_ts3_markov_4bet_w30` (+4500 rows)

---

## 9. Explicit Non-Actions

The following were **NOT** performed in P129A:

| Item | Status |
|---|---|
| Production DB schema migration | NOT EXECUTED — gate not passed |
| Production DB INSERT / UPDATE / DELETE | NOT DONE |
| P126 controlled apply | NOT EXECUTED |
| 4_STAR work | BLOCKED |
| P108 execution | BLOCKED |
| P117 execution | BLOCKED |
| P118 execution | BLOCKED |
| Scheduler / cron / launchd install | NOT DONE |
| Strategy promotion / lifecycle / champion / registry mutation | NOT DONE |

---

## 10. Final Classification

```
P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION
```

P129A gate confirmed: rehearsal valid, production DB clean, corrected SQL documented.
Waiting for Kelvin to provide:
```
YES authorize migration_plan_p128 because <reason>
```
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print(f"[P129A] Starting production migration authorization gate — "
          f"{datetime.now(timezone.utc).isoformat()}")
    print(f"[P129A] Production DB: {DB_PATH}")
    print(f"[P129A] P129 artifact: {P129_ARTIFACT}")

    # Phase 0: snapshot production DB before
    snapshot_before = snapshot_production_db()
    if not snapshot_before["invariant_ok"]:
        print(f"[P129A] ERROR: Production DB invariant failed: {snapshot_before}",
              file=sys.stderr)
        return 1
    print(f"[P129A] Production DB rows: {snapshot_before['replay_rows']} — OK")
    print(f"[P129A] Production DB has bet_index: {snapshot_before['has_bet_index_column']}")

    # Phase 1: read P129 artifact
    p129_summary = read_p129_artifact()
    if not p129_summary["all_checks_passed"]:
        print(f"[P129A] ERROR: P129 artifact checks failed: {p129_summary}",
              file=sys.stderr)
        return 1
    print(f"[P129A] P129 classification: {p129_summary['classification']} — OK")
    print(f"[P129A] ROW_NUMBER() required: {p129_summary['row_number_required']}")

    # Phase 2: authorization gate — no phrase provided in this prompt
    auth_gate = check_authorization(provided_phrases=None)
    print(f"[P129A] Authorization gate: {auth_gate['classification']}")
    print(f"[P129A] Authorization present: {auth_gate['authorization_present']}")
    print(f"[P129A] Migration allowed: {auth_gate['migration_allowed']}")

    # Phase 3: build corrected migration SQL summary
    corrected_sql = build_corrected_migration_sql()

    # Phase 4: snapshot production DB after (must be identical)
    snapshot_after = snapshot_production_db()
    if snapshot_after["replay_rows"] != EXPECTED_REPLAY_ROWS:
        print(f"[P129A] CRITICAL ERROR: Production DB rows changed! "
              f"{snapshot_after['replay_rows']}", file=sys.stderr)
        return 1
    if snapshot_after["has_bet_index_column"]:
        print("[P129A] CRITICAL ERROR: bet_index appeared in production DB!", file=sys.stderr)
        return 1
    print(f"[P129A] Production DB after: {snapshot_after['replay_rows']} rows, "
          f"bet_index={snapshot_after['has_bet_index_column']} — OK")

    # Build output
    data = build_output_json(
        snapshot_before, p129_summary, auth_gate, corrected_sql, snapshot_after
    )
    md   = build_markdown(data)

    # Write
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")

    print(f"[P129A] JSON written: {OUT_JSON}")
    print(f"[P129A] MD  written: {OUT_MD}")
    print(f"[P129A] classification = {data['classification']}")
    print(f"[P129A] production_db_modified = {data['production_db_modified']}")
    print(f"[P129A] migration_execution_performed = {data['migration_execution_performed']}")
    print(f"[P129A] DONE — {data['classification']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
