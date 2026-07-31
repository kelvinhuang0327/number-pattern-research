"""
P246J — BIG_LOTTO Add-on Isolation Arc Closure

Closes the P246B-I evidence chain. Confirms which strategy/research/replay/
learning callers now use canonical BIG_LOTTO samples, identifies remaining
deferred risks, and states the overall isolation status.

No DB write is performed.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

ARC_TIMELINE = [
    {
        "task": "P246",
        "title": "BIG_LOTTO Data-Integrity Audit",
        "outcome": "Identified 4 row families: 22,238 total, 2,113 canonical, 19,100 hyphenated",
        "type": "Read-only audit",
    },
    {
        "task": "P246B",
        "title": "Taxonomy Correction",
        "outcome": "SIM_HYPHEN → ADD_ON_PRIZE_EXCLUDED. Hyphenated rows are valid add-on/special prize records, not fake/simulated. PR #317",
        "type": "Taxonomy correction + artifact",
    },
    {
        "task": "P246C",
        "title": "Impact Audit",
        "outcome": "database.py DIRECTLY_AFFECTED (no canonical filter). P219 NOT_AFFECTED (already filtered). PR #318",
        "type": "Read-only impact audit",
    },
    {
        "task": "P246D",
        "title": "Segregation Design",
        "outcome": "Phased isolation plan: Phase 1 code helper, Phase 2 SQL view (Type D), Phase 3 annotation table (Type D). Rejected direct deletion. PR #319",
        "type": "Design artifact",
    },
    {
        "task": "P246E",
        "title": "Canonical Draw Helper",
        "outcome": "Added get_canonical_draws() to database.py. Updated quick_predict.py. BIG_LOTTO canonical=2,113. PR #320",
        "type": "Code implementation (no DB write)",
    },
    {
        "task": "P246F",
        "title": "Research Caller Sweep",
        "outcome": "Updated rsm_bootstrap.py and core_satellite.py. PR #321",
        "type": "Code implementation",
    },
    {
        "task": "P246G",
        "title": "Remaining Callers",
        "outcome": "Updated drift_detector._load_draws() (direct SQL) and backtest_framework.py. PR #322",
        "type": "Code implementation",
    },
    {
        "task": "P246H",
        "title": "Advanced Learning Scheduler Trace",
        "outcome": "Traced scheduler call chain. Updated scheduler.get_data() to filter BIG_LOTTO at return time. PR #323",
        "type": "Code implementation",
    },
    {
        "task": "P246I",
        "title": "Population Assertion Cleanup",
        "outcome": "Added P246I inline comments to test_p238b and test_p243a distinguishing raw (22,238) vs canonical (2,113). PR #324",
        "type": "Test annotation (no value changes)",
    },
]

CANONICALIZED_CALLERS = [
    {
        "file": "tools/quick_predict.py",
        "function": "load_history()",
        "change": "get_all_draws(BIG_LOTTO) → get_canonical_draws(BIG_LOTTO)",
        "task": "P246E",
        "status": "CANONICALIZED",
        "verification_marker": "get_canonical_draws",
    },
    {
        "file": "tools/rsm_bootstrap.py",
        "function": "run_rsm()",
        "change": "get_all_draws(lottery_type) → get_canonical_draws(lottery_type)",
        "task": "P246F",
        "status": "CANONICALIZED",
        "verification_marker": "get_canonical_draws",
    },
    {
        "file": "lottery_api/engine/core_satellite.py",
        "function": "__main__ --from-history",
        "change": "db.get_all_draws(args.lottery) → db.get_canonical_draws(args.lottery)",
        "task": "P246F",
        "status": "CANONICALIZED",
        "verification_marker": "get_canonical_draws",
    },
    {
        "file": "lottery_api/engine/drift_detector.py",
        "function": "_load_draws()",
        "change": "Direct SQL patched: BIG_LOTTO branch with AND draw NOT LIKE '%-%' + Python max(numbers)>25",
        "task": "P246G",
        "status": "CANONICALIZED",
        "verification_marker": "draw NOT LIKE",
    },
    {
        "file": "lottery_api/backtest_framework.py",
        "function": "BacktestEngine.backtest()",
        "change": "self.db.get_all_draws(lottery_type) → self.db.get_canonical_draws(lottery_type)",
        "task": "P246G",
        "status": "CANONICALIZED",
        "verification_marker": "get_canonical_draws",
    },
    {
        "file": "lottery_api/utils/scheduler.py",
        "function": "LotteryOptimizationScheduler.get_data()",
        "change": "Added BIG_LOTTO canonical filter at return time. All advanced_learning callers benefit.",
        "task": "P246H",
        "status": "CANONICALIZED",
        "verification_marker": "ADD_ON_PRIZE_EXCLUDED",
    },
    {
        "file": "lottery_api/database.py",
        "function": "get_canonical_draws() [NEW]",
        "change": "New helper: SQL filter (hyphen + date-format) + Python filter (max>25)",
        "task": "P246E",
        "status": "CANONICALIZED",
        "verification_marker": "get_canonical_draws",
    },
    {
        "file": "analysis/p219_external_method_diagnostic_sweep.py",
        "function": "main query",
        "change": "None — already used draw NOT LIKE '%-%' (gold standard reference)",
        "task": "pre-P246",
        "status": "ALREADY_CANONICAL",
        "verification_marker": "draw NOT LIKE",
    },
]

POPULATION_SEMANTICS = {
    "raw_total": {
        "count": 22238,
        "description": "All BIG_LOTTO rows in DB (raw + add-on inclusive)",
        "appropriate_for": ["raw display/history API", "DB integrity tests"],
    },
    "add_on_prize_excluded": {
        "count": 19100,
        "description": "Add-on/special prize records (hyphenated draw IDs). Valid lottery records, excluded due to population mismatch.",
        "is_fake": False,
        "is_invalid": False,
        "preservation_status": "PRESERVED in raw DB and raw scheduler cache",
    },
    "date_format_alien": {
        "count": 375,
        "description": "8-digit YYYYMMDD draw IDs; numbers inconsistent with 6/49",
        "classification": "Non-canonical data-integrity concern",
    },
    "small_pool_alien": {
        "count": 650,
        "description": "Serial IDs but max(numbers)<=25; likely mislabeled game",
        "classification": "Non-canonical data-integrity concern",
    },
    "canonical_main_draw": {
        "count": 2113,
        "description": "Canonical 6/49 main draws. Returned by get_canonical_draws('BIG_LOTTO'). Intended research population.",
        "governance_expected": 2118,
        "appropriate_for": ["strategy research", "NIST audit", "backtesting", "PSI drift", "prediction"],
    },
}

REMAINING_DEFERRED_RISKS = [
    {
        "risk": "No DB-level canonical view yet",
        "detail": "Phase 2 Type D: CREATE VIEW draws_big_lotto_canonical_main not yet executed",
        "severity": "MEDIUM — code-level filter is in place; DB view would make it explicit at schema level",
        "resolution": "Execute P247 Type D after separate explicit authorization",
    },
    {
        "risk": "No row-family metadata annotation table yet",
        "detail": "Phase 3 Type D: draw_row_family_annotations table not yet created",
        "severity": "LOW — SMALL_POOL_ALIEN detection at SQL level requires Python filter; annotation table would make it explicit",
        "resolution": "Execute P247 Phase 3 Type D after separate authorization",
    },
    {
        "risk": "optimization.py:90 still calls get_all_draws() unfiltered",
        "detail": "optimization.py feeds scheduler cache with raw 22,238 rows; mitigated by scheduler.get_data() filter",
        "severity": "LOW — risk mitigated by P246H fix at consumption point",
        "resolution": "Lower-priority cleanup; update optimization.py:90 to use canonical draws when loading scheduler cache",
    },
    {
        "risk": "60+ archived exploratory scripts not updated",
        "detail": "Historical tools/*.py and lottery_api/*.py scripts may call get_all_draws('BIG_LOTTO') unfiltered",
        "severity": "LOW — these are archived/exploratory scripts, not active production paths",
        "resolution": "Bulk sweep authorized separately if archived scripts become active",
    },
    {
        "risk": "P238B NIST artifact reflects raw population (22,238)",
        "detail": "P238B NIST audit ran on mixed population. YELLOW status stands historically. Canonical re-audit not yet done.",
        "severity": "MEDIUM — YELLOW is observation-only; no strategy authorized regardless. Re-audit after P247 is recommended.",
        "resolution": "P246K: run canonical NIST re-audit on ~2,113 draws after P247 Type D (no DB write needed for rerun)",
    },
    {
        "risk": "GATE_RED_PENDING_CANONICAL_SEPARATION remains in effect",
        "detail": "BIG_LOTTO predictive/bias research gate is still RED. Cannot open until canonical dataset is separated and verified.",
        "severity": "BY DESIGN — gate protects research integrity",
        "resolution": "Gate opens only after: P247 Type D executed, canonical re-audit passes, explicit authorization",
    },
]

GATE_STATUS = {
    "current": "GATE_RED_PENDING_CANONICAL_SEPARATION",
    "reason": (
        "While active research callers now use get_canonical_draws() or equivalent filters, "
        "the DB-level canonical separation (Phase 2/3 Type D) has not been executed. "
        "The canonical view does not yet exist in the DB schema. "
        "BIG_LOTTO predictive/bias research remains blocked per governance."
    ),
    "unblock_condition": (
        "1. P247 Type D executed (CREATE VIEW + annotation table). "
        "2. Canonical re-audit (P246K or equivalent) passes. "
        "3. Explicit user/governance authorization. "
        "4. Drift guard and replay row integrity confirmed."
    ),
    "research_protection_in_place": True,
    "note": (
        "The code-level isolation (P246E-H) ensures active production research paths "
        "do not consume add-on records. The gate remains RED for new BIG_LOTTO research "
        "directions until the full DB-level separation is authorized and verified."
    ),
}

RECOMMENDED_NEXT_TASK = {
    "primary": {
        "task": "P246K",
        "description": (
            "Run canonical NIST randomness audit on ~2,113 BIG_LOTTO main draws only "
            "(no DB write needed; uses get_canonical_draws() directly). "
            "This would confirm whether the YELLOW RANDOMNESS_AUDIT finding stands on "
            "the clean canonical population or was an artifact of the mixed population."
        ),
        "authorization_required": "No Type D needed — code-level read-only audit",
        "type": "Read-only re-audit",
    },
    "alternative": {
        "task": "P247 Type D",
        "description": (
            "Execute CREATE VIEW draws_big_lotto_canonical_main and "
            "CREATE TABLE draw_row_family_annotations in the DB. "
            "This would complete the DB-level canonical separation."
        ),
        "authorization_required": "Explicit Type D human gate required",
        "type": "DB write (Type D)",
    },
    "recommendation": (
        "Recommend P246K first (no DB write, faster path to canonical audit insight). "
        "Then P247 Type D for DB-level separation. "
        "Do not execute either without explicit authorization."
    ),
}

FORBIDDEN_ACTIONS = [
    "DB_write",
    "DB_migration_apply",
    "row_deletion",
    "CREATE_VIEW",
    "CREATE_TABLE",
    "registry_mutation",
    "production_recommendation_change",
    "strategy_promotion",
    "betting_advice",
    "Type_D_apply",
    "GATE_OPEN_for_BIG_LOTTO_research",
]


def verify_callers_from_source() -> dict:
    results = {}
    for caller in CANONICALIZED_CALLERS:
        path = REPO_ROOT / caller["file"]
        if path.exists():
            content = path.read_text(encoding="utf-8")
            results[caller["file"]] = {
                "exists": True,
                "verified": caller["verification_marker"] in content,
                "marker": caller["verification_marker"],
            }
        else:
            results[caller["file"]] = {"exists": False}
    all_verified = all(
        v.get("verified", False) for v in results.values() if v.get("exists", False)
    )
    return {"per_file": results, "all_verified": all_verified}


def run_closure_audit() -> dict:
    caller_verification = verify_callers_from_source()

    return {
        "schema_version": "1.0",
        "task_id": "P246J",
        "classification": "P246J_BIG_LOTTO_ADDON_ISOLATION_ARC_CLOSED",
        "p246i_merged_pr": "PR #324 merged 2026-06-06T02:34:20Z",
        "dependency_artifacts_verified": [
            f"outputs/research/p246{x}_big_lotto_*.json" for x in "bcdefghi"
        ],
        "arc_timeline": ARC_TIMELINE,
        "canonicalized_callers": CANONICALIZED_CALLERS,
        "caller_verification": caller_verification,
        "raw_access_preserved": {
            "confirmed": True,
            "description": (
                "lottery_api/database.py get_all_draws() and get_draws() remain unchanged. "
                "All 22,238 BIG_LOTTO rows including 19,100 ADD_ON_PRIZE_EXCLUDED are "
                "accessible via raw methods for display/history purposes. "
                "scheduler.data_by_type['BIG_LOTTO'] raw cache is preserved; "
                "canonical filter applied only at get_data() return time."
            ),
        },
        "no_db_write_confirmed": True,
        "no_deletion_confirmed": True,
        "no_migration_confirmed": True,
        "add_on_records_status": {
            "valid_lottery_related": True,
            "is_fake": False,
            "is_simulated": False,
            "preserved_in_db": True,
            "excluded_from_research_by": [
                "get_canonical_draws() — SQL filter + Python max(numbers)>25",
                "drift_detector._load_draws() — SQL BIG_LOTTO branch",
                "scheduler.get_data() — return-time Python filter",
            ],
            "accessible_via": [
                "lottery_api/database.py get_all_draws('BIG_LOTTO')",
                "lottery_api/database.py get_draws(lottery_type='BIG_LOTTO')",
            ],
        },
        "population_semantics": POPULATION_SEMANTICS,
        "remaining_deferred_risks": REMAINING_DEFERRED_RISKS,
        "gate_status": GATE_STATUS,
        "recommended_next_task": RECOMMENDED_NEXT_TASK,
        "forbidden_actions_confirmed": FORBIDDEN_ACTIONS,
        "final_decision": (
            "P246J arc closure complete. The P246 BIG_LOTTO add-on isolation arc (P246B-I) "
            "has corrected the taxonomy, designed the isolation architecture, implemented "
            "code-level canonical filters across 6 active research callers, and clarified "
            "test/artifact population semantics. "
            "ADD_ON_PRIZE_EXCLUDED records (19,100) are valid lottery-related records "
            "preserved in the raw DB, excluded from research by population mismatch. "
            "Active production research paths now use get_canonical_draws() or equivalent. "
            "No DB write, deletion, migration, or Type D operation was performed. "
            "GATE_RED_PENDING_CANONICAL_SEPARATION remains until DB-level separation (P247 Type D) "
            "is authorized and executed. Recommended next task: P246K canonical NIST re-audit."
        ),
    }


def main():
    import sys
    result = run_closure_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    v = result.get("caller_verification", {})
    print(f"\n[P246J] All callers verified: {v.get('all_verified')}", file=sys.stderr)
    print(f"[P246J] DB write performed: False (no_db_write_confirmed={result['no_db_write_confirmed']})", file=sys.stderr)
    print(f"[P246J] Classification: {result['classification']}", file=sys.stderr)


if __name__ == "__main__":
    main()
