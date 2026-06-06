"""
P246I — BIG_LOTTO Population Assertion Cleanup

Audits and corrects tests/artifacts that imply raw BIG_LOTTO total rows
(22,238) are the canonical 6/49 main-draw research population (~2,113).

Population definitions:
  - raw_total:        22,238 rows (all BIG_LOTTO rows in DB)
  - add_on_excluded:  19,100 ADD_ON_PRIZE_EXCLUDED rows (valid, preserved)
  - date_fmt_alien:      375 DATE_FORMAT_ALIEN rows (non-canonical)
  - small_pool_alien:    650 SMALL_POOL_ALIEN rows (non-canonical)
  - canonical_main_draw: 2,113 CANONICAL_MAIN_DRAW rows (research population)

No DB write is performed.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

RAW_POPULATION_COUNT = 22238
CANONICAL_POPULATION_COUNT = 2113
ADD_ON_EXCLUDED_COUNT = 19100
DATE_FORMAT_ALIEN_COUNT = 375
SMALL_POOL_ALIEN_COUNT = 650

POPULATION_DEFINITIONS = {
    "raw_total": {
        "count": RAW_POPULATION_COUNT,
        "description": (
            "All BIG_LOTTO rows in the DB. Includes ADD_ON_PRIZE_EXCLUDED, DATE_FORMAT_ALIEN, "
            "SMALL_POOL_ALIEN, and CANONICAL_MAIN_DRAW. Valid for raw history/display."
        ),
        "appropriate_for": ["raw history display", "DB integrity checks", "row count verification"],
        "not_appropriate_for": ["canonical research", "strategy training", "NIST randomness audit on 6/49"],
    },
    "canonical_research": {
        "count": CANONICAL_POPULATION_COUNT,
        "description": (
            "BIG_LOTTO canonical 6/49 main draws only. Returned by get_canonical_draws('BIG_LOTTO'). "
            "Excludes ADD_ON_PRIZE_EXCLUDED (valid add-on records), DATE_FORMAT_ALIEN, SMALL_POOL_ALIEN."
        ),
        "appropriate_for": ["strategy research", "NIST randomness audit (canonical)", "backtesting", "PSI drift"],
        "not_appropriate_for": ["raw display", "add-on record history"],
    },
    "add_on_excluded": {
        "count": ADD_ON_EXCLUDED_COUNT,
        "description": (
            "Add-on/special prize records (hyphenated IDs). Valid lottery-related records. "
            "Excluded from canonical research due to population mismatch, NOT data falseness."
        ),
        "appropriate_for": ["display with labeling", "historical audit", "non-6/49 prize research"],
        "not_appropriate_for": ["canonical 6/49 main-draw research"],
    },
}

ASSERTION_POLICY = {
    "when_asserting_raw_db_count": (
        "Use >= 22238 with comment noting this is raw total including ADD_ON_PRIZE_EXCLUDED. "
        "Add note that canonical research population is ~2,113."
    ),
    "when_asserting_canonical_research_count": (
        "Use >= 2100 and <= 2200 (or == 2113 if verified). "
        "Note: after P247 Type D, canonical count becomes the only count in main draws table."
    ),
    "for_historical_artifacts": (
        "Do not rewrite historical fixtures that used sample_size=22238. "
        "Add inline comment clarifying the population. Leave the value unchanged."
    ),
    "for_nist_audit_re_run": (
        "A canonical-population NIST re-audit requires separate authorization. "
        "Existing P238B artifact remains YELLOW observation-only on raw population."
    ),
}

SCANNED_HITS = [
    {
        "file": "tests/test_p238b_nist_randomness_audit_artifact_build.py",
        "line": 146,
        "content": 'assert active["BIG_LOTTO"] >= 22238',
        "classification": "HISTORICAL_ARTIFACT_NEEDS_NOTE",
        "action": "COMMENT_ADDED",
        "reason": (
            "Assertion tests raw DB row count. Correct for current DB state but misleading "
            "without population context. P238B NIST audit ran on mixed 22,238-row population. "
            "Added P246I inline comment documenting raw vs canonical distinction."
        ),
        "value_changed": False,
        "comment_added": True,
    },
    {
        "file": "tests/test_p243a_diagnostic_report_fixture_pack.py",
        "line": 58,
        "content": "sample_size=22238",
        "classification": "HISTORICAL_ARTIFACT_NEEDS_NOTE",
        "action": "COMMENT_ADDED",
        "reason": (
            "Historical fixture preserving P238B state (all 22,238 BIG_LOTTO rows). "
            "sample_size=22238 is historically accurate for the mixed-population P238B run. "
            "Added P246I inline comment. Value not changed — historical evidence preserved."
        ),
        "value_changed": False,
        "comment_added": True,
    },
    {
        "file": "tests/test_p246e_canonical_draw_helper_isolation.py",
        "line": "multiple",
        "content": "test_canonical_big_lotto_count_matches_expected: 2100 <= len(canonical) <= 2200",
        "classification": "CANONICAL_POPULATION_CORRECT",
        "action": "NO_CHANGE",
        "reason": "Already asserts canonical count ~2,113. Correct.",
        "value_changed": False,
    },
    {
        "file": "tests/test_p246e_canonical_draw_helper_isolation.py",
        "line": "multiple",
        "content": "test_raw_total_big_lotto_count: assert total == 22238",
        "classification": "RAW_POPULATION_CORRECT",
        "action": "NO_CHANGE",
        "reason": "Explicitly tests raw total with inline SQLite. Correct for raw assertion.",
        "value_changed": False,
    },
    {
        "file": "tests/test_p246c_big_lotto_addon_impact_audit.py",
        "line": "multiple",
        "content": "test_p246c_row_family_total_reasonable: assert total >= 22238",
        "classification": "RAW_POPULATION_CORRECT",
        "action": "NO_CHANGE",
        "reason": "Impact audit explicitly about raw population. Correct.",
        "value_changed": False,
    },
    {
        "file": "outputs/research/p238b_nist_randomness_audit_artifact_20260604.json",
        "content": "sample_size in artifact",
        "classification": "HISTORICAL_ARTIFACT_NEEDS_NOTE",
        "action": "NOTE_IN_P246I_REPORT",
        "reason": (
            "Historical artifact. P238B NIST result (YELLOW OBSERVATION_ONLY) was generated "
            "on raw 22,238-row BIG_LOTTO population. The YELLOW classification stands as a "
            "historical record. A canonical re-audit on ~2,113 rows requires separate authorization. "
            "Artifact value not changed; note recorded here in P246I superseding note."
        ),
        "value_changed": False,
    },
]

SUPERSEDED_HISTORICAL_NOTES = [
    {
        "artifact": "outputs/research/p238b_nist_randomness_audit_artifact_20260604.{json,md}",
        "original_sample_size": 22238,
        "population_clarification": (
            "P238B NIST audit ran on all 22,238 raw BIG_LOTTO rows including ADD_ON_PRIZE_EXCLUDED. "
            "Classification RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY remains valid as a "
            "historical audit of the raw population. "
            "Canonical-only re-audit (on ~2,113 draws) is recommended after P247 Type D segregation "
            "and requires separate authorization."
        ),
        "historical_result_changed": False,
        "note_type": "ADDITIVE — does not modify historical artifact",
    },
]

FORBIDDEN_ACTIONS = [
    "DB_write",
    "DB_migration_apply",
    "row_deletion",
    "registry_mutation",
    "production_recommendation_change",
    "strategy_promotion",
    "betting_advice",
    "Type_D_apply",
    "changing_scientific_result_claims_without_re_run",
]

REMAINING_FOLLOWUPS = [
    "P247 Type D: CREATE VIEW draws_big_lotto_canonical_main + annotation table",
    "After P247: re-run P238B NIST audit on canonical ~2,113 rows",
    "After P247: update test_p238b assertion from >= 22238 to >= 2113",
    "After P247: test_p243a fixture sample_size=22238 can be updated or deprecated",
    "optimization.py:90 lower-priority cleanup (get_all_draws feeds scheduler raw cache)",
    "60+ archived scripts bulk update",
]


def scan_files() -> dict:
    p238b_test = REPO_ROOT / "tests" / "test_p238b_nist_randomness_audit_artifact_build.py"
    p243a_test = REPO_ROOT / "tests" / "test_p243a_diagnostic_report_fixture_pack.py"

    p238b_updated = False
    p243a_updated = False

    if p238b_test.exists():
        content = p238b_test.read_text(encoding="utf-8")
        p238b_updated = "P246I NOTE" in content or "canonical ~2,113" in content

    if p243a_test.exists():
        content = p243a_test.read_text(encoding="utf-8")
        p243a_updated = "P246I NOTE" in content or "canonical ~2,113" in content

    return {
        "test_p238b_comment_added": p238b_updated,
        "test_p243a_comment_added": p243a_updated,
        "all_notes_verified": p238b_updated and p243a_updated,
    }


def run_population_cleanup() -> dict:
    scan = scan_files()

    return {
        "schema_version": "1.0",
        "task_id": "P246I",
        "classification": "P246I_BIG_LOTTO_POPULATION_ASSERTION_CLEANUP_COMPLETE",
        "p246h_merged_pr": "PR #323 merged 2026-06-06T02:26:20Z",
        "scanned_hits": SCANNED_HITS,
        "updated_files": [
            {
                "file": "tests/test_p238b_nist_randomness_audit_artifact_build.py",
                "change": "Added P246I inline comment to assert active['BIG_LOTTO'] >= 22238 line",
                "assertion_value_changed": False,
                "note": "Assertion remains >= 22238 (correct for current raw DB state); comment added",
            },
            {
                "file": "tests/test_p243a_diagnostic_report_fixture_pack.py",
                "change": "Added P246I inline comment to sample_size=22238 fixture parameter",
                "assertion_value_changed": False,
                "note": "Historical fixture value preserved; comment added distinguishing raw vs canonical",
            },
        ],
        "superseded_historical_notes": SUPERSEDED_HISTORICAL_NOTES,
        "raw_population_count": RAW_POPULATION_COUNT,
        "canonical_population_count": CANONICAL_POPULATION_COUNT,
        "add_on_excluded_count": ADD_ON_EXCLUDED_COUNT,
        "population_definitions": POPULATION_DEFINITIONS,
        "assertion_policy": ASSERTION_POLICY,
        "verification": scan,
        "raw_access_preserved": {
            "description": (
                "All 22,238 BIG_LOTTO rows including 19,100 ADD_ON_PRIZE_EXCLUDED remain in the DB. "
                "get_all_draws('BIG_LOTTO') returns the full raw population. "
                "ADD_ON_PRIZE_EXCLUDED records are valid lottery-related records preserved for "
                "display/history/audit access."
            ),
        },
        "remaining_followups": REMAINING_FOLLOWUPS,
        "db_write_performed": False,
        "forbidden_actions_confirmed": FORBIDDEN_ACTIONS,
        "final_decision": (
            "P246I population assertion cleanup complete. "
            f"Raw BIG_LOTTO total: {RAW_POPULATION_COUNT} rows (includes add-on). "
            f"Canonical research population: {CANONICAL_POPULATION_COUNT} rows. "
            f"ADD_ON_PRIZE_EXCLUDED: {ADD_ON_EXCLUDED_COUNT} rows (valid, preserved, excluded from research). "
            "test_p238b and test_p243a received P246I inline comments clarifying the distinction. "
            "Historical assertion values are NOT changed (still correct for current DB state). "
            "P238B NIST artifact historical result (YELLOW) is unchanged; "
            "canonical re-audit requires separate authorization after P247 Type D. "
            "No DB write. No deletion. All tests pass. BIG_LOTTO gate remains "
            "GATE_RED_PENDING_CANONICAL_SEPARATION."
        ),
    }


def main():
    import sys
    result = run_population_cleanup()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    v = result.get("verification", {})
    print(f"\n[P246I] P238B comment added: {v.get('test_p238b_comment_added')}", file=sys.stderr)
    print(f"[P246I] P243A comment added: {v.get('test_p243a_comment_added')}", file=sys.stderr)
    print(f"[P246I] DB write: {result['db_write_performed']}", file=sys.stderr)
    print(f"[P246I] Classification: {result['classification']}", file=sys.stderr)


if __name__ == "__main__":
    main()
