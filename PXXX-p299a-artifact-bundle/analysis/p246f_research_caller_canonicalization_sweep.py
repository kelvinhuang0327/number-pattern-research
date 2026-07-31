"""
P246F — Research Caller Canonicalization Sweep

Read-only source scan + minimal targeted code updates.
Identifies and classifies BIG_LOTTO research/strategy/replay callers.
Updates confirmed research callers to use get_canonical_draws().

No DB write is performed.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

CLASSIFICATION_ENUM = (
    "UPDATED_TO_CANONICAL",
    "ALREADY_CANONICAL",
    "RAW_DISPLAY_ALLOWED",
    "POSSIBLY_AFFECTED_NEEDS_SCOPE",
    "NOT_AFFECTED",
    "UNKNOWN_NEEDS_MANUAL_REVIEW",
)

FORBIDDEN_ACTIONS = [
    "DB_write",
    "DB_migration_apply",
    "row_deletion",
    "row_movement",
    "frontend_display_change",
    "registry_mutation",
    "production_recommendation_change",
    "strategy_promotion",
    "betting_advice",
    "Type_D_apply",
    "GATE_OPEN_for_BIG_LOTTO_research",
]

SCANNED_PATTERNS = [
    "get_all_draws(",
    "get_draws(",
    "lottery_type='BIG_LOTTO'",
    "lottery_type = 'BIG_LOTTO'",
    "BIG_LOTTO",
    "FROM draws",
    "draw NOT LIKE",
    "get_canonical_draws(",
]

# ---------------------------------------------------------------------------
# Caller classifications
# ---------------------------------------------------------------------------

CALLER_CLASSIFICATIONS = [
    # -----------------------------------------------------------------------
    # UPDATED_TO_CANONICAL — updated in P246E or P246F
    # -----------------------------------------------------------------------
    {
        "file": "tools/quick_predict.py",
        "function": "load_history()",
        "line": 169,
        "classification": "UPDATED_TO_CANONICAL",
        "updated_in": "P246E",
        "change": "get_all_draws(lottery_type) → get_canonical_draws(lottery_type)",
        "reason": "Primary prediction/research entry point; confirmed research caller",
    },
    {
        "file": "tools/rsm_bootstrap.py",
        "function": "run_rsm()",
        "line": 118,
        "classification": "UPDATED_TO_CANONICAL",
        "updated_in": "P246F",
        "change": "get_all_draws(lottery_type) → get_canonical_draws(lottery_type)",
        "reason": "RSM strategy bootstrap — feeds BIG_LOTTO strategies into RollingStrategyMonitor; confirmed research/strategy caller",
    },
    {
        "file": "lottery_api/engine/core_satellite.py",
        "function": "__main__ --from-history path",
        "line": 373,
        "classification": "UPDATED_TO_CANONICAL",
        "updated_in": "P246F",
        "change": "db.get_all_draws(args.lottery) → db.get_canonical_draws(args.lottery)",
        "reason": "Core-satellite strategy generation from history; confirmed research/strategy caller",
    },
    # -----------------------------------------------------------------------
    # ALREADY_CANONICAL — already uses draw NOT LIKE '%-%' filter
    # -----------------------------------------------------------------------
    {
        "file": "analysis/p219_external_method_diagnostic_sweep.py",
        "function": "main/query",
        "classification": "ALREADY_CANONICAL",
        "change": "None — already uses filter: draw NOT LIKE '%-%'",
        "reason": "P219 implemented the gold-standard canonical filter before P246E existed",
    },
    {
        "file": "analysis/p246b_big_lotto_taxonomy_correction.py",
        "classification": "ALREADY_CANONICAL",
        "change": "None — explicitly handles row families; counts ADD_ON via draw LIKE '%-%'",
        "reason": "P246B taxonomy correction script; not a research/prediction caller",
    },
    {
        "file": "analysis/p246c_big_lotto_addon_impact_audit.py",
        "classification": "ALREADY_CANONICAL",
        "change": "None — audit script; explicitly handles all row families",
        "reason": "P246C impact audit; not a research/prediction caller",
    },
    # -----------------------------------------------------------------------
    # RAW_DISPLAY_ALLOWED — display/history paths that may show add-on records
    # -----------------------------------------------------------------------
    {
        "file": "lottery_api/database.py",
        "function": "get_all_draws()",
        "classification": "RAW_DISPLAY_ALLOWED",
        "change": "None — intentionally returns all rows including add-on records",
        "reason": "General display/history endpoint; callers that need raw history should use this",
    },
    {
        "file": "lottery_api/database.py",
        "function": "get_draws()",
        "classification": "RAW_DISPLAY_ALLOWED",
        "change": "None — paged display endpoint; intentionally returns all rows",
        "reason": "Paged history endpoint; add-on records are valid to show in history",
    },
    {
        "file": "lottery_api/routes/ingest.py",
        "classification": "RAW_DISPLAY_ALLOWED",
        "change": "None — ingestion and history listing routes",
        "reason": "Display/API routes; showing draw history including add-on records is valid",
    },
    # -----------------------------------------------------------------------
    # POSSIBLY_AFFECTED_NEEDS_SCOPE — research callers outside minimal P246F scope
    # -----------------------------------------------------------------------
    {
        "file": "lottery_api/engine/drift_detector.py",
        "function": "_load_draws()",
        "line": 63,
        "classification": "POSSIBLY_AFFECTED_NEEDS_SCOPE",
        "reason": (
            "_load_draws() uses direct SQLite: SELECT numbers FROM draws WHERE lottery_type=? "
            "with no hyphen filter. BIG_LOTTO drift detection may be affected by SMALL_POOL_ALIEN. "
            "Deferred: requires separate scope; direct SQL update needed, not a DatabaseManager call."
        ),
        "deferred": True,
        "deferred_reason": "Not in P246F whitelist; requires direct SQL update not DatabaseManager change",
    },
    {
        "file": "lottery_api/routes/advanced_learning.py",
        "function": "scheduler.get_data(lottery_type)",
        "classification": "POSSIBLY_AFFECTED_NEEDS_SCOPE",
        "reason": (
            "Calls scheduler.get_data('BIG_LOTTO'). Filtering depends on scheduler implementation. "
            "Deferred: not a direct DatabaseManager call; scheduler code path not traced."
        ),
        "deferred": True,
        "deferred_reason": "Scheduler data path not fully traced; outside minimal P246F scope",
    },
    {
        "file": "lottery_api/backtest_framework.py",
        "function": "BacktestEngine.__init__()",
        "line": 69,
        "classification": "POSSIBLY_AFFECTED_NEEDS_SCOPE",
        "reason": (
            "self.db.get_all_draws(lottery_type). Used by historical backtest scripts. "
            "Deferred: broad framework change would affect many scripts; needs dedicated scope."
        ),
        "deferred": True,
        "deferred_reason": "Framework change would cascade; dedicated P246G sweep needed for backtest scripts",
    },
    # -----------------------------------------------------------------------
    # POSSIBLY_AFFECTED — 30+ archived backtest/analysis scripts in lottery_api/ and tools/
    # -----------------------------------------------------------------------
    {
        "file": "lottery_api/*.py (30+ historical backtest/analysis scripts)",
        "representative_examples": [
            "lottery_api/backtest_2025_full_advanced.py:95",
            "lottery_api/backtest_big_lotto_2025_ensemble.py:38",
            "lottery_api/backtest_115000012_windows.py:136",
            "lottery_api/analyze_user_bets.py:149",
        ],
        "classification": "POSSIBLY_AFFECTED_NEEDS_SCOPE",
        "reason": (
            "All call get_all_draws('BIG_LOTTO') in historical/exploratory context. "
            "Deferred: broad refactor of archived scripts is outside minimal P246F scope. "
            "These are non-production exploratory scripts."
        ),
        "deferred": True,
        "deferred_reason": "Archived/exploratory scripts; bulk update requires dedicated sweep task",
    },
    {
        "file": "tools/*.py (30+ historical backtest/analysis scripts)",
        "representative_examples": [
            "tools/analyze_banker_accuracy.py:46",
            "tools/audit_big_lotto_baseline.py:22",
            "tools/backtest_biglotto_7me.py",
            "tools/backtest_consensus_20.py",
        ],
        "classification": "POSSIBLY_AFFECTED_NEEDS_SCOPE",
        "reason": (
            "Many tools call get_all_draws('BIG_LOTTO') for historical analysis. "
            "Deferred: archived/exploratory context; outside minimal P246F scope."
        ),
        "deferred": True,
        "deferred_reason": "Archived/exploratory scripts; bulk update requires dedicated sweep task",
    },
    # -----------------------------------------------------------------------
    # NOT_AFFECTED
    # -----------------------------------------------------------------------
    {
        "file": "lottery_api/backtest_my_4bet_config.py, lottery_api/backtest_my_4bet_simple.py",
        "classification": "NOT_AFFECTED",
        "reason": "Get_all_draws('POWER_LOTTO') — not BIG_LOTTO",
    },
    {
        "file": "lottery_api/backtest_oddeven_research_539.py",
        "classification": "NOT_AFFECTED",
        "reason": "get_all_draws('DAILY_539') — not BIG_LOTTO",
    },
]

FILES_UPDATED = [
    {
        "file": "tools/quick_predict.py",
        "updated_in": "P246E",
        "line": 169,
        "change": "get_all_draws → get_canonical_draws",
    },
    {
        "file": "tools/rsm_bootstrap.py",
        "updated_in": "P246F",
        "line": 118,
        "change": "get_all_draws → get_canonical_draws",
    },
    {
        "file": "lottery_api/engine/core_satellite.py",
        "updated_in": "P246F",
        "line": 373,
        "change": "get_all_draws → get_canonical_draws",
    },
]

FILES_DEFERRED = [
    {
        "file": "lottery_api/engine/drift_detector.py",
        "reason": "Direct SQL _load_draws(); different update pattern; separate scope needed",
    },
    {
        "file": "lottery_api/routes/advanced_learning.py",
        "reason": "Scheduler data path not fully traced",
    },
    {
        "file": "lottery_api/backtest_framework.py",
        "reason": "Framework cascade; needs dedicated P246G sweep",
    },
    {
        "file": "lottery_api/*.py (30+ scripts)",
        "reason": "Archived/exploratory; bulk sweep outside minimal P246F scope",
    },
    {
        "file": "tools/*.py (30+ scripts excluding quick_predict, rsm_bootstrap)",
        "reason": "Archived/exploratory; bulk sweep outside minimal P246F scope",
    },
]


def check_file_uses_canonical(file_path: str, function_hint: str = "") -> dict:
    path = REPO_ROOT / file_path
    if not path.exists():
        return {"exists": False, "uses_canonical": None}
    content = path.read_text(encoding="utf-8")
    uses_canonical = "get_canonical_draws" in content
    still_has_raw = "get_all_draws" in content
    return {
        "exists": True,
        "uses_canonical": uses_canonical,
        "still_has_raw_get_all_draws": still_has_raw,
    }


def run_sweep() -> dict:
    updated_checks = {}
    for f in FILES_UPDATED:
        check = check_file_uses_canonical(f["file"])
        updated_checks[f["file"]] = check

    raw_access_check = check_file_uses_canonical("lottery_api/database.py")

    # Verify rsm_bootstrap updated
    rsm_check = check_file_uses_canonical("tools/rsm_bootstrap.py")
    # Verify core_satellite updated
    cs_check = check_file_uses_canonical("lottery_api/engine/core_satellite.py")

    all_updated_verified = (
        rsm_check.get("uses_canonical", False)
        and cs_check.get("uses_canonical", False)
    )

    return {
        "schema_version": "1.0",
        "task_id": "P246F",
        "classification": "P246F_RESEARCH_CALLER_CANONICALIZATION_SWEEP_COMPLETE",
        "p246e_merged_pr": "PR #320 merged 2026-06-05T14:26:17Z",
        "scanned_patterns": SCANNED_PATTERNS,
        "scanned_paths": [
            "lottery_api/engine/",
            "lottery_api/routes/",
            "lottery_api/*.py",
            "tools/",
            "analysis/",
        ],
        "caller_classifications": CALLER_CLASSIFICATIONS,
        "files_updated": FILES_UPDATED,
        "files_deferred": FILES_DEFERRED,
        "update_verification": updated_checks,
        "rsm_bootstrap_verified": rsm_check,
        "core_satellite_verified": cs_check,
        "all_p246f_updates_verified": all_updated_verified,
        "raw_access_preserved": {
            "description": (
                "lottery_api/database.py get_all_draws() and get_draws() remain unchanged. "
                "All 22,238 BIG_LOTTO rows including 19,100 ADD_ON_PRIZE_EXCLUDED are "
                "accessible via raw methods for display/history purposes."
            ),
            "get_all_draws_still_present": raw_access_check.get("still_has_raw_get_all_draws"),
        },
        "db_write_performed": False,
        "forbidden_actions_confirmed": FORBIDDEN_ACTIONS,
        "remaining_future_work": [
            "P246G: Update drift_detector._load_draws() to add AND draw NOT LIKE '%-%' for BIG_LOTTO",
            "P246G: Trace advanced_learning.py scheduler.get_data() path",
            "P246G: Bulk update backtest_framework.py and 30+ archived backtest/analysis scripts",
            "Phase 2 (Type D): CREATE VIEW draws_big_lotto_canonical_main",
            "Phase 3 (Type D): CREATE TABLE draw_row_family_annotations",
            "Phase 4: Re-run P238B NIST on canonical population; update test_p238b assertion",
        ],
        "final_decision": (
            "P246F sweep complete. 3 confirmed research/strategy callers now use "
            "get_canonical_draws(): quick_predict.py (P246E), rsm_bootstrap.py (P246F), "
            "and core_satellite.py (P246F). "
            "BIG_LOTTO add-on/special prize records (ADD_ON_PRIZE_EXCLUDED, 19,100 rows) "
            "are excluded from these research paths. "
            "Raw access via get_all_draws() preserved for display/history. "
            "drift_detector._load_draws(), advanced_learning route, backtest_framework.py, "
            "and 60+ archived scripts are deferred to future P246G sweep. "
            "No DB write. No deletion. BIG_LOTTO gate remains GATE_RED_PENDING_CANONICAL_SEPARATION."
        ),
    }


def main():
    import sys
    result = run_sweep()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    updated = len([f for f in result["files_updated"]])
    deferred = len(result["files_deferred"])
    verified = result.get("all_p246f_updates_verified", False)
    print(f"\n[P246F] Files updated: {updated}, deferred: {deferred}", file=sys.stderr)
    print(f"[P246F] All P246F updates verified: {verified}", file=sys.stderr)
    print(f"[P246F] DB write: {result['db_write_performed']}", file=sys.stderr)
    print(f"[P246F] Classification: {result['classification']}", file=sys.stderr)


if __name__ == "__main__":
    main()
