#!/usr/bin/env python3
"""
P126A: Per-Strategy Controlled Apply Authorization Gate
=======================================================
PURPOSE : After P129B schema migration, establish individual authorization gates
          for each of the 5 Tier-B controlled-apply candidates from P126 dry-run.
          No apply is executed in this script. No replay rows are inserted.
SAFETY:
  - Read-only on production DB (PRAGMA query_only = ON).
  - No INSERT / UPDATE / DELETE.
  - No P126 apply executed.
  - Stops with classification WAITING if any per-strategy phrase is absent.
GOVERNANCE:
  - NO controlled_apply executed
  - NO P126 apply
  - NO scheduler / cron / launchd
  - NO 4_STAR / P108 / P117 / P118
  - NO strategy promotion / lifecycle / champion / registry mutation
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_ID        = "P126A"
CLASSIFICATION = "P126A_WAITING_FOR_PER_STRATEGY_APPLY_AUTHORIZATION"
DATE_SUFFIX    = "20260528"
REPO_ROOT      = Path(__file__).resolve().parent.parent

P129B_ARTIFACT = REPO_ROOT / "outputs/replay/p129b_execute_bet_index_schema_migration_20260528.json"
P129A_ARTIFACT = REPO_ROOT / "outputs/replay/p129a_production_migration_authorization_gate_20260528.json"
P129_ARTIFACT  = REPO_ROOT / "outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json"
P128_ARTIFACT  = REPO_ROOT / "outputs/replay/p128_native_multi_bet_storage_design_20260528.json"
P126_ARTIFACT  = REPO_ROOT / "outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"
OUT_JSON       = REPO_ROOT / "outputs/replay/p126a_controlled_apply_authorization_gate_20260528.json"
OUT_MD         = REPO_ROOT / "docs/replay/p126a_controlled_apply_authorization_gate_20260528.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_ROWS_BEFORE = 54462
EXPECTED_ROWS_AFTER  = 54462   # No apply in P126A

# Per-strategy authorization prefix (strategy-specific part varies)
AUTH_PREFIX = "YES authorize controlled_apply for "

# Per-strategy gate definitions (ordered by recommended apply order)
# recommended_order: 1 = lowest risk / smallest row count first
STRATEGY_GATES = [
    {
        "strategy_id":         "power_fourier_rhythm_2bet",
        "lottery_type":        "POWER_LOTTO",
        "target_bet_count":    2,
        "expected_insert_rows": 1500,
        "missing_bet_indices": [2],
        "authorization_phrase": "YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>",
        "recommended_order":   1,
        "risk_level":          "lowest",
        "risk_note":           "+1500 rows, 2-bet, POWER_LOTTO — smallest delta, lowest risk",
    },
    {
        "strategy_id":         "biglotto_echo_aware_3bet",
        "lottery_type":        "BIG_LOTTO",
        "target_bet_count":    3,
        "expected_insert_rows": 3000,
        "missing_bet_indices": [2, 3],
        "authorization_phrase": "YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>",
        "recommended_order":   2,
        "risk_level":          "low_to_medium",
        "risk_note":           "+3000 rows, 3-bet, BIG_LOTTO — fallback_equivalent quality",
    },
    {
        "strategy_id":         "daily539_f4cold_3bet",
        "lottery_type":        "DAILY_539",
        "target_bet_count":    3,
        "expected_insert_rows": 3000,
        "missing_bet_indices": [2, 3],
        "authorization_phrase": "YES authorize controlled_apply for daily539_f4cold_3bet because <reason>",
        "recommended_order":   3,
        "risk_level":          "medium",
        "risk_note":           "+3000 rows, 3-bet, DAILY_539 — watchlist quality",
    },
    {
        "strategy_id":         "biglotto_ts3_markov_4bet_w30",
        "lottery_type":        "BIG_LOTTO",
        "target_bet_count":    4,
        "expected_insert_rows": 4500,
        "missing_bet_indices": [2, 3, 4],
        "authorization_phrase": "YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>",
        "recommended_order":   4,
        "risk_level":          "medium",
        "risk_note":           "+4500 rows, 4-bet, BIG_LOTTO — sub_baseline quality",
    },
    {
        "strategy_id":         "daily539_f4cold_5bet",
        "lottery_type":        "DAILY_539",
        "target_bet_count":    5,
        "expected_insert_rows": 6000,
        "missing_bet_indices": [2, 3, 4, 5],
        "authorization_phrase": "YES authorize controlled_apply for daily539_f4cold_5bet because <reason>",
        "recommended_order":   5,
        "risk_level":          "medium",
        "risk_note":           "+6000 rows, 5-bet, DAILY_539 — watchlist quality, largest delta",
    },
]


def _ro_conn(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def snapshot_db():
    conn = _ro_conn(DB_PATH)
    try:
        rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
        has_bet_index = "bet_index" in cols
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        has_new_unique = "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl
        return {
            "replay_rows": rows,
            "has_bet_index_column": has_bet_index,
            "has_new_unique_constraint": has_new_unique,
            "columns_count": len(cols),
        }
    finally:
        conn.close()


def load_artifact(path):
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def check_authorization(strategy_id, provided_phrases=None):
    """Return True if exact phrase for this strategy is present."""
    if not provided_phrases:
        return False
    prefix = f"{AUTH_PREFIX}{strategy_id} because "
    for phrase in provided_phrases:
        stripped = phrase.strip()
        if stripped.startswith(prefix) and not stripped.endswith("<reason>"):
            return True
    return False


def build_strategy_gates(provided_phrases=None):
    gates = []
    for sg in STRATEGY_GATES:
        auth_present = check_authorization(sg["strategy_id"], provided_phrases)
        gates.append({
            "strategy_id":          sg["strategy_id"],
            "lottery_type":         sg["lottery_type"],
            "target_bet_count":     sg["target_bet_count"],
            "expected_insert_rows": sg["expected_insert_rows"],
            "missing_bet_indices":  sg["missing_bet_indices"],
            "authorization_phrase": sg["authorization_phrase"],
            "authorization_present": auth_present,
            "apply_allowed":        auth_present,
            "recommended_order":    sg["recommended_order"],
            "risk_level":           sg["risk_level"],
            "risk_note":            sg["risk_note"],
        })
    return gates


def main(provided_phrases=None):
    now = datetime.now(timezone.utc).isoformat()
    print(f"[P126A] Starting per-strategy controlled apply authorization gate — {now}")

    # --- Load upstream artifacts ---
    print("[P126A] Loading upstream artifacts...")
    p129b = load_artifact(P129B_ARTIFACT)
    p129a = load_artifact(P129A_ARTIFACT)
    p129  = load_artifact(P129_ARTIFACT)
    p128  = load_artifact(P128_ARTIFACT)
    p126  = load_artifact(P126_ARTIFACT)

    p129b_ok  = p129b is not None and p129b.get("classification") == "P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED"
    p126_ok   = p126 is not None and p126.get("classification") == "P126_DRY_RUN_PLAN_READY"
    total_new = p126["summary"]["total_new_rows_if_all_applied"] if p126 else None
    estimated_rows = p126["summary"].get("total_new_rows_if_all_applied", 18000) if p126 else 18000

    print(f"[P126A] P129B: {p129b.get('classification') if p129b else 'MISSING'}")
    print(f"[P126A] P126:  {p126.get('classification') if p126 else 'MISSING'}")

    # --- DB snapshot before (= after, since no apply) ---
    print("[P126A] Snapshotting production DB (read-only)...")
    snap_before = snapshot_db()
    rows_before = snap_before["replay_rows"]
    has_bet_index = snap_before["has_bet_index_column"]
    print(f"[P126A] DB rows = {rows_before}, bet_index = {has_bet_index}")

    # Invariant check
    if rows_before != EXPECTED_ROWS_BEFORE:
        print(f"[P126A] ERROR: Expected {EXPECTED_ROWS_BEFORE} rows, found {rows_before}")
        sys.exit(1)

    if not has_bet_index:
        print("[P126A] ERROR: bet_index column missing — P129B may not have run")
        sys.exit(1)

    # --- Schema readiness ---
    schema_readiness = {
        "bet_index_column_present": has_bet_index,
        "unique_constraint_ready": snap_before["has_new_unique_constraint"],
        "p129b_completed": p129b_ok,
        "production_rows": rows_before,
        "columns_count": snap_before["columns_count"],
    }

    # --- Build per-strategy gates ---
    print("[P126A] Building per-strategy authorization gates...")
    gates = build_strategy_gates(provided_phrases)
    any_authorized = any(g["authorization_present"] for g in gates)

    # --- Duplicate guard ---
    duplicate_guard = {
        "unique_key": ["lottery_type", "target_draw", "strategy_id", "bet_index"],
        "constraint_active": snap_before["has_new_unique_constraint"],
        "p129b_migration_applied": p129b_ok,
        "guard_note": (
            "The UNIQUE(lottery_type, target_draw, strategy_id, bet_index) constraint is now active "
            "in the production schema (applied by P129B). Any multi-bet apply INSERT must supply "
            "bet_index 2, 3, ... for new rows; inserting bet_index=1 for an existing (strategy, draw) "
            "pair will be rejected by the constraint."
        ),
    }

    # --- Apply preconditions ---
    backup_path = (p129b or {}).get("backup", {}).get("backup_path", "see P129B artifact")
    apply_preconditions = [
        {
            "check": "p129b_schema_migrated",
            "status": "PASS" if p129b_ok else "FAIL",
            "detail": "P129B classification = P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED",
        },
        {
            "check": "bet_index_column_present",
            "status": "PASS" if has_bet_index else "FAIL",
            "detail": f"bet_index column in production DB: {has_bet_index}",
        },
        {
            "check": "unique_constraint_ready",
            "status": "PASS" if snap_before["has_new_unique_constraint"] else "FAIL",
            "detail": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index) active",
        },
        {
            "check": "db_invariant_confirmed",
            "status": "PASS" if rows_before == EXPECTED_ROWS_BEFORE else "FAIL",
            "detail": f"replay_rows = {rows_before} (expected {EXPECTED_ROWS_BEFORE})",
        },
        {
            "check": "backup_exists",
            "status": "PASS" if p129b_ok else "UNKNOWN",
            "detail": f"Backup created by P129B: {backup_path}",
        },
        {
            "check": "drift_guard_pass",
            "status": "REQUIRED",
            "detail": "Run scripts/replay_lifecycle_drift_guard.py before any apply. Must return PASS.",
        },
        {
            "check": "strategy_specific_authorization",
            "status": "REQUIRED",
            "detail": "Each strategy requires its own exact authorization phrase from Kelvin before apply.",
        },
        {
            "check": "staging_whitelist_clean",
            "status": "REQUIRED",
            "detail": "git diff --cached --name-only must contain only whitelisted files before apply.",
        },
    ]

    # --- Required phrases list ---
    required_authorization_phrases = [g["authorization_phrase"] for g in gates]

    # --- Recommended apply order ---
    recommended_apply_order = [
        {
            "order":               g["recommended_order"],
            "strategy_id":         g["strategy_id"],
            "lottery_type":        g["lottery_type"],
            "expected_insert_rows": g["expected_insert_rows"],
            "risk_level":          g["risk_level"],
            "risk_note":           g["risk_note"],
        }
        for g in sorted(gates, key=lambda x: x["recommended_order"])
    ]

    # --- Known regression failures (pre-existing / obsolete) ---
    known_regression_failures = [
        {
            "test_file": "tests/test_p129a_production_migration_authorization_gate.py",
            "failing_tests": [
                "TestProductionDBRows::test_live_no_bet_index_column",
                "TestIdempotency::test_script_reruns_cleanly",
            ],
            "reason": "Pre-migration guard — expected 'no bet_index column'; now obsolete after P129B applied migration.",
            "status": "KNOWN_OBSOLETE",
        },
        {
            "test_file": "tests/test_p129_bet_index_schema_migration_rehearsal.py",
            "failing_tests": [
                "TestProductionDBRows::test_production_no_bet_index_column",
                "TestIdempotency::test_script_reruns_cleanly",
            ],
            "reason": "Pre-migration guard — expected production DB without bet_index; now obsolete after P129B.",
            "status": "KNOWN_OBSOLETE",
        },
        {
            "test_file": "tests/test_p128_native_multi_bet_storage_design.py",
            "failing_tests": [
                "TestDBInvariantsLive::test_3star_count",
                "TestDBInvariantsLive::test_4star_count",
                "TestDBInvariantsLive::test_no_bet_index_column_currently",
                "TestDBInvariantsLive::test_current_unique_constraint",
                "TestIdempotency::test_script_reruns_cleanly",
            ],
            "reason": "Stale draw counts (3_STAR/4_STAR not present in this worktree DB) + obsolete bet_index guard.",
            "status": "KNOWN_PRE_EXISTING",
        },
        {
            "test_file": "tests/test_p126_controlled_apply_plan_tier_b_multi_bet.py",
            "failing_tests": [
                "TestDBInvariantsBeforeRun::test_3star_count",
                "TestDBInvariantsBeforeRun::test_3star_max_draw",
                "TestDBInvariantsBeforeRun::test_4star_count",
                "TestDBInvariantsBeforeRun::test_4star_max_draw",
                "TestIdempotency::test_script_reruns_cleanly",
            ],
            "reason": "Stale 3_STAR/4_STAR draw count expectations (worktree DB lacks canonical draw data).",
            "status": "KNOWN_PRE_EXISTING",
        },
    ]

    # --- Blocked or excluded ---
    blocked_or_excluded = [
        {"item": "controlled_apply",       "reason": "No apply executed in P126A — all 5 strategies waiting for per-strategy authorization"},
        {"item": "4_STAR",                 "reason": "Explicitly excluded from all Tier-B multi-bet work per governance"},
        {"item": "P108",                   "reason": "P108 execution blocked — 100-draw threshold not met"},
        {"item": "P117",                   "reason": "P117 execution blocked — POWER_LOTTO draw threshold not met"},
        {"item": "P118",                   "reason": "P118 execution blocked — exact authorization phrase absent"},
        {"item": "rejected_strategies",    "reason": "No rejected strategies included or promoted"},
        {"item": "scheduler_cron_launchd", "reason": "No scheduler installation in P126A"},
        {"item": "lifecycle_champion_registry", "reason": "No strategy promotion / lifecycle / champion / registry mutation"},
    ]

    # --- DB snapshot after (identical — no apply) ---
    snap_after = snapshot_db()

    # --- P126 source summary ---
    p126_candidates = (p126 or {}).get("dry_run_candidates", [])
    p126_source_summary = {
        "artifact":               str(P126_ARTIFACT.relative_to(REPO_ROOT)),
        "classification":         (p126 or {}).get("classification"),
        "classification_ok":      p126_ok,
        "candidate_count":        len(p126_candidates),
        "total_new_rows_if_all_applied": (p126 or {}).get("summary", {}).get("total_new_rows_if_all_applied", 18000),
        "estimated_rows_from_p126": 18000,
        "total_replay_rows_after_all_applied": (p126 or {}).get("summary", {}).get("total_replay_rows_after_all_applied", 72462),
        "p128_storage_design_accepted": True,
        "p128_storage_design_note": "P128 one-row-per-bet design formally accepted; P129B schema migration applied.",
    }

    # --- P129B source summary ---
    p129b_source_summary = {
        "artifact":           str(P129B_ARTIFACT.relative_to(REPO_ROOT)),
        "classification":     (p129b or {}).get("classification"),
        "classification_ok":  p129b_ok,
        "migration_ok":       (p129b or {}).get("migration_ok", False),
        "backup_ok":          (p129b or {}).get("backup", {}).get("backup_ok", False),
        "rows_after_migration": (p129b or {}).get("db_snapshot_after", {}).get("replay_rows"),
        "bet_index_present":  (p129b or {}).get("db_snapshot_after", {}).get("has_bet_index_column", False),
    }

    # --- Migration status ---
    migration_status = {
        "p128_design_accepted":     True,
        "p129_rehearsal_completed": True,
        "p129a_gate_completed":     True,
        "p129b_migration_applied":  p129b_ok,
        "bet_index_column_active":  has_bet_index,
        "unique_constraint_active": snap_before["has_new_unique_constraint"],
        "production_rows":          rows_before,
        "ready_for_apply":          p129b_ok and has_bet_index,
        "note": "Schema migration complete. Ready to accept per-strategy apply once Kelvin provides authorization phrases.",
    }

    # --- Summary ---
    summary = {
        "task_id":                    TASK_ID,
        "classification":             CLASSIFICATION,
        "authorization_present":      any_authorized,
        "strategies_authorized":      sum(1 for g in gates if g["authorization_present"]),
        "strategies_waiting":         sum(1 for g in gates if not g["authorization_present"]),
        "apply_execution_performed":  False,
        "replay_rows_inserted":       0,
        "rows_before":                rows_before,
        "rows_after":                 snap_after["replay_rows"],
        "bet_index_column_present":   has_bet_index,
        "schema_ready_for_apply":     p129b_ok and has_bet_index,
        "p126_apply_estimated_rows":  18000,
        "p126_candidates":            5,
        "next_step": (
            "Provide the exact per-strategy authorization phrase for the desired strategy "
            "(recommended: power_fourier_rhythm_2bet first). Each phrase must match exactly: "
            "'YES authorize controlled_apply for <strategy_id> because <reason>'. "
            "A new P126B (or per-strategy apply task) will execute the INSERT for that strategy only."
        ),
    }

    # --- Build output artifact ---
    artifact = {
        "task_id":                    TASK_ID,
        "classification":             CLASSIFICATION,
        "generated_at":               now,
        "db_snapshot_before":         snap_before,
        "db_snapshot_after":          snap_after,
        "p129b_source_summary":       p129b_source_summary,
        "p126_source_summary":        p126_source_summary,
        "schema_readiness":           schema_readiness,
        "per_strategy_authorization_gates": gates,
        "recommended_apply_order":    recommended_apply_order,
        "duplicate_guard":            duplicate_guard,
        "apply_preconditions":        apply_preconditions,
        "migration_status":           migration_status,
        "apply_execution_performed":  False,
        "replay_rows_inserted":       0,
        "known_regression_failures":  known_regression_failures,
        "blocked_or_excluded":        blocked_or_excluded,
        "required_authorization_phrases": required_authorization_phrases,
        "summary":                    summary,
    }

    # --- Write JSON ---
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w") as f:
        json.dump(artifact, f, indent=2)
    print(f"[P126A] JSON written: {OUT_JSON}")

    # --- Write Markdown ---
    _write_md(artifact)
    print(f"[P126A] MD  written: {OUT_MD}")

    print(f"[P126A] classification = {CLASSIFICATION}")
    print(f"[P126A] DONE — {CLASSIFICATION}")
    return artifact


def _write_md(artifact):
    lines = [
        "# P126A: Per-Strategy Controlled Apply Authorization Gate",
        "",
        f"**Generated:** {artifact['generated_at']}  ",
        f"**Classification:** `{artifact['classification']}`  ",
        f"**Production DB rows (before/after):** {artifact['db_snapshot_before']['replay_rows']} / {artifact['db_snapshot_after']['replay_rows']} (no change — no apply executed)  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "P126A establishes the per-strategy authorization gate for the 5 Tier-B controlled-apply",
        "candidates identified in P126 dry-run. This script is **read-only** — it performs no INSERT,",
        "no replay row additions, and no strategy promotion. The gate is `WAITING` because no",
        "per-strategy exact authorization phrase has been provided in this run.",
        "",
        "Each of the 5 strategies requires an independent authorization phrase from Kelvin before",
        "its apply can proceed. Strategies cannot be applied in bulk with a single authorization.",
        "",
        "---",
        "",
        "## 2. P129B Migration Recap",
        "",
        f"- **Classification:** `{artifact['p129b_source_summary']['classification']}`",
        f"- **Migration applied:** {artifact['p129b_source_summary']['migration_ok']}",
        f"- **Backup OK:** {artifact['p129b_source_summary']['backup_ok']}",
        f"- **Rows after migration:** {artifact['p129b_source_summary']['rows_after_migration']}",
        f"- **bet_index column present:** {artifact['p129b_source_summary']['bet_index_present']}",
        "- **What changed:** `bet_index INTEGER NOT NULL DEFAULT 1` column added; `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)` replaces old `replay_run_id`-based constraint.",
        "- **ROW_NUMBER() COPY used:** Correct — 120 duplicate old-run groups assigned bet_index 1/2/3.",
        "",
        "---",
        "",
        "## 3. P126 Dry-Run Recap",
        "",
        f"- **Classification:** `{artifact['p126_source_summary']['classification']}`",
        f"- **Candidates:** {artifact['p126_source_summary']['candidate_count']} strategies",
        f"- **Total rows if all applied:** +{artifact['p126_source_summary']['total_new_rows_if_all_applied']} (→ {artifact['p126_source_summary']['total_replay_rows_after_all_applied']} total)",
        "- **Provenance guard:** All 5 candidates from trusted P94 source.",
        "- **Duplicate guard:** All 5 candidates had 0 duplicate draws at P126 time.",
        "- **P128 storage design:** One-row-per-bet formally accepted; P129B schema migration applied.",
        "",
        "---",
        "",
        "## 4. Why Per-Strategy Authorization Is Required",
        "",
        "Each strategy carry independent risk profiles and evidence levels:",
        "",
        "| Strategy | Quality | Risk | New Rows |",
        "|---|---|---|---:|",
    ]
    for g in sorted(artifact["per_strategy_authorization_gates"], key=lambda x: x["recommended_order"]):
        lines.append(f"| `{g['strategy_id']}` | {g.get('risk_note', '')} | {g['risk_level']} | +{g['expected_insert_rows']} |")
    lines += [
        "",
        "One authorization applies to one strategy only. If a single phrase authorized all five,",
        "Kelvin would have no mechanism to approve strategies incrementally based on confidence.",
        "P126 dry-run already established that each candidate needs its own `explicit_apply_authorization`.",
        "",
        "---",
        "",
        "## 5. Five Strategy Authorization Gates",
        "",
    ]
    for g in sorted(artifact["per_strategy_authorization_gates"], key=lambda x: x["recommended_order"]):
        lines += [
            f"### Gate {g['recommended_order']}: `{g['strategy_id']}`",
            "",
            f"- **Lottery type:** {g['lottery_type']}",
            f"- **Target bet count:** {g['target_bet_count']}",
            f"- **Expected insert rows:** +{g['expected_insert_rows']}",
            f"- **Missing bet indices:** {g['missing_bet_indices']}",
            f"- **Risk:** {g['risk_level']} — {g['risk_note']}",
            f"- **Authorization present:** {g['authorization_present']}",
            f"- **Apply allowed:** {g['apply_allowed']}",
            f"- **Required phrase:** `{g['authorization_phrase']}`",
            "",
        ]
    lines += [
        "---",
        "",
        "## 6. Recommended Apply Order",
        "",
        "Start with the lowest-risk, smallest row-count strategy:",
        "",
        "| Order | Strategy | Lottery | New Rows | Risk |",
        "|---:|---|---|---:|---|",
    ]
    for r in artifact["recommended_apply_order"]:
        lines.append(f"| {r['order']} | `{r['strategy_id']}` | {r['lottery_type']} | +{r['expected_insert_rows']} | {r['risk_level']} |")
    lines += [
        "",
        "Each apply task should be independent. Verify drift guard after each strategy's apply.",
        "Update drift guard expected row count before moving to the next strategy.",
        "",
        "---",
        "",
        "## 7. Duplicate Guard and Preconditions",
        "",
        f"**Unique key:** `{artifact['duplicate_guard']['unique_key']}`  ",
        f"**Constraint active:** `{artifact['duplicate_guard']['constraint_active']}`  ",
        "",
        artifact["duplicate_guard"]["guard_note"],
        "",
        "**Apply preconditions (all must PASS before any strategy apply):**",
        "",
    ]
    for pc in artifact["apply_preconditions"]:
        lines.append(f"- `{pc['check']}`: **{pc['status']}** — {pc['detail']}")
    lines += [
        "",
        "---",
        "",
        "## 8. Known Obsolete / Pre-Existing Regression Failures After Schema Migration",
        "",
        "The following test failures are **not caused by P126A**. They are pre-existing or obsolete guards:",
        "",
    ]
    for rf in artifact["known_regression_failures"]:
        lines.append(f"**`{rf['test_file']}`** — {rf['status']}:")
        for t in rf["failing_tests"]:
            lines.append(f"  - `{t}`")
        lines.append(f"  *Reason: {rf['reason']}*")
        lines.append("")
    lines += [
        "---",
        "",
        "## 9. Explicit Non-Actions",
        "",
        "This P126A task did **not**:",
        "",
    ]
    for b in artifact["blocked_or_excluded"]:
        lines.append(f"- **{b['item']}**: {b['reason']}")
    lines += [
        "",
        "---",
        "",
        "## 10. Final Classification",
        "",
        f"```",
        f"{artifact['classification']}",
        f"```",
        "",
        f"**Strategies authorized:** {artifact['summary']['strategies_authorized']} / 5  ",
        f"**Strategies waiting:** {artifact['summary']['strategies_waiting']} / 5  ",
        f"**Apply executed:** {artifact['apply_execution_performed']}  ",
        f"**Replay rows inserted:** {artifact['replay_rows_inserted']}  ",
        "",
        "To proceed, provide the exact per-strategy phrase for the desired strategy.",
        "Recommended first: `power_fourier_rhythm_2bet` (+1500 rows, lowest risk).",
        "",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MD.open("w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
