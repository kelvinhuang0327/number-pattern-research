"""
tests/test_p67_2024_data_gap_free_source_search.py
===================================================
Test suite for P67 — 2024 Closing-Line Data Gap Free-Source Search (PATH_B).
Governance: paper_only=True, diagnostic_only=True, promotion_freeze=True
NO live API calls. NO paid API. NO TSL. NO web requests during test run.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import _p67_2024_data_gap_free_source_search as p67  # noqa: E402

SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p67_2024_data_gap_free_source_search_summary.json"
)
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def candidates() -> list[dict]:
    return p67.load_candidates()


@pytest.fixture(scope="module")
def summary(tmp_path_factory: pytest.TempPathFactory) -> dict:
    tmp = tmp_path_factory.mktemp("p67") / "summary.json"
    return p67.run_p67(output_path=tmp)


@pytest.fixture(scope="module")
def summary_from_disk() -> dict:
    """Load the committed JSON summary if present."""
    if SUMMARY_PATH.exists():
        with open(SUMMARY_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    pytest.skip("p67 summary JSON not yet generated — run scripts/_p67 first")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Candidate source inventory exists and is non-empty
# ═══════════════════════════════════════════════════════════════════════════════

def test_candidate_inventory_exists(candidates: list[dict]) -> None:
    """Candidate source inventory must not be empty."""
    assert len(candidates) >= 1, "CANDIDATE_SOURCES must contain at least one entry"


def test_candidate_inventory_has_minimum_sources(candidates: list[dict]) -> None:
    """Must document at least 5 sources to demonstrate exhaustive search."""
    assert len(candidates) >= 5, (
        f"Expected ≥5 candidate sources, got {len(candidates)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Each candidate has source_name
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_source_name(candidates: list[dict]) -> None:
    missing = [i for i, s in enumerate(candidates) if not s.get("source_name")]
    assert not missing, f"Candidates at indices {missing} missing 'source_name'"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Each candidate has source_type
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_source_type(candidates: list[dict]) -> None:
    missing = [s["source_name"] for s in candidates if not s.get("source_type")]
    assert not missing, f"Missing 'source_type' in: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Cost classification present on every candidate
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_cost(candidates: list[dict]) -> None:
    missing = [s["source_name"] for s in candidates if "cost" not in s]
    assert not missing, f"Missing 'cost' in: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Availability classification present on every candidate
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_availability(candidates: list[dict]) -> None:
    missing = [s["source_name"] for s in candidates if not s.get("availability")]
    assert not missing, f"Missing 'availability' in: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Field coverage classification present on every candidate
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_fields_visible(candidates: list[dict]) -> None:
    """Each candidate must declare its visible fields (even if empty list)."""
    missing = [s["source_name"] for s in candidates if "fields_visible" not in s]
    assert not missing, f"Missing 'fields_visible' in: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Year coverage classification present on every candidate
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_years_covered(candidates: list[dict]) -> None:
    missing = [s["source_name"] for s in candidates if not s.get("years_covered")]
    assert not missing, f"Missing 'years_covered' in: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Market coverage classification present on every candidate
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_candidates_have_market_coverage(candidates: list[dict]) -> None:
    missing = [s["source_name"] for s in candidates if not s.get("market_coverage")]
    assert not missing, f"Missing 'market_coverage' in: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Source-level classification is from allowed set
# ═══════════════════════════════════════════════════════════════════════════════

def test_source_classifications_are_valid(candidates: list[dict]) -> None:
    invalid = [
        (s["source_name"], s.get("classification"))
        for s in candidates
        if s.get("classification") not in p67.VALID_SOURCE_CLASSIFICATIONS
    ]
    assert not invalid, f"Invalid source classifications: {invalid}"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Final P67 classification is from the allowed set
# ═══════════════════════════════════════════════════════════════════════════════

def test_p67_final_classification_is_valid(summary: dict) -> None:
    cls = summary.get("p67_classification")
    assert cls in p67.VALID_P67_CLASSIFICATIONS, (
        f"P67 classification {cls!r} not in allowed set"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 11. No paid API called
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_paid_api_called_module_flag() -> None:
    assert p67.PAID_API_CALLED is False, "PAID_API_CALLED must be False"


def test_no_paid_api_called_in_summary(summary: dict) -> None:
    gov = summary.get("governance", {})
    assert gov.get("paid_api_called") is False, (
        "governance.paid_api_called must be False in summary"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 12. No live API calls
# ═══════════════════════════════════════════════════════════════════════════════

def test_live_api_calls_zero_module_flag() -> None:
    assert p67.LIVE_API_CALLS == 0, "LIVE_API_CALLS must be 0"


def test_live_api_calls_zero_in_summary(summary: dict) -> None:
    gov = summary.get("governance", {})
    assert gov.get("live_api_calls") == 0, (
        "governance.live_api_calls must be 0 in summary"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 13. No TSL crawler called
# ═══════════════════════════════════════════════════════════════════════════════

def test_tsl_crawler_not_called_module_flag() -> None:
    assert p67.TSL_CRAWLER_CALLED is False, "TSL_CRAWLER_CALLED must be False"


def test_tsl_crawler_not_called_in_summary(summary: dict) -> None:
    gov = summary.get("governance", {})
    assert gov.get("tsl_crawler_called") is False, (
        "governance.tsl_crawler_called must be False in summary"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Runtime recommendation logic unchanged
# ═══════════════════════════════════════════════════════════════════════════════

def test_runtime_recommendation_logic_unchanged_module_flag() -> None:
    assert p67.RUNTIME_RECOMMENDATION_LOGIC_CHANGED is False, (
        "RUNTIME_RECOMMENDATION_LOGIC_CHANGED must be False"
    )


def test_runtime_recommendation_logic_unchanged_in_summary(summary: dict) -> None:
    gov = summary.get("governance", {})
    assert gov.get("runtime_recommendation_logic_changed") is False, (
        "governance.runtime_recommendation_logic_changed must be False in summary"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 15. 2024 data gap status explicitly documented in summary
# ═══════════════════════════════════════════════════════════════════════════════

def test_data_year_2024_gap_status_present(summary: dict) -> None:
    """Summary must explicitly document 2024 gap status."""
    status = summary.get("data_year_2024_gap_status")
    assert status, "data_year_2024_gap_status must be non-empty"
    # Gap must NOT be marked as resolved — no source was confirmed downloadable
    assert "RESOLVED" not in status or "UNRESOLVED" in status or "PENDING" in status, (
        f"Unexpected resolved status with no confirmed downloadable source: {status!r}"
    )


def test_data_year_2024_gap_remains_flag_in_module() -> None:
    assert p67.DATA_YEAR_2024_GAP_REMAINS is True, (
        "DATA_YEAR_2024_GAP_REMAINS must be True (gap not yet resolved in P67)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Recommendation is consistent with final classification
# ═══════════════════════════════════════════════════════════════════════════════

def test_recommendation_consistent_with_classification(summary: dict) -> None:
    cls = summary.get("p67_classification", "")
    rec = summary.get("recommendation", "")
    assert rec, "recommendation must be non-empty"

    if cls == "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW":
        assert "P68" in rec or "oddsportal" in rec.lower(), (
            f"When partial source found, recommendation should reference P68 probe; got {rec!r}"
        )
    elif cls == "P67_PATH_B_NO_USABLE_FREE_SOURCE_FOUND":
        assert "P61" in rec or "PATH_A" in rec or "paid" in rec.lower(), (
            f"When no source found, recommendation should reference P61 PATH_A; got {rec!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 17. Forbidden affirmative scan — no live/production/bet claims
# ═══════════════════════════════════════════════════════════════════════════════

FORBIDDEN_PHRASES: list[str] = [
    "production_ready = True",
    "production_ready=True",
    "kelly_deploy_allowed = True",
    "kelly_deploy_allowed=True",
    "real_bet_allowed = True",
    "real_bet_allowed=True",
    "PRODUCTION_READY: bool = True",
    "KELLY_DEPLOY_ALLOWED: bool = True",
    "REAL_BET_ALLOWED: bool = True",
    "paid_api_called = True",
    "paid_api_called=True",
    "PAID_API_CALLED: bool = True",
    "LIVE_API_CALLS: int = 1",
    "TSL_CRAWLER_CALLED: bool = True",
]


def test_forbidden_affirmative_scan_in_script() -> None:
    """The P67 script must not contain any forbidden production-readiness claims."""
    script_path = REPO_ROOT / "scripts" / "_p67_2024_data_gap_free_source_search.py"
    assert script_path.exists(), "P67 script not found"
    content = script_path.read_text(encoding="utf-8")
    violations = [phrase for phrase in FORBIDDEN_PHRASES if phrase in content]
    assert not violations, (
        f"Forbidden affirmative phrases found in P67 script: {violations}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 18. active_task.md updated with P67 completion entry
# ═══════════════════════════════════════════════════════════════════════════════

def test_active_task_md_exists() -> None:
    assert ACTIVE_TASK_PATH.exists(), "00-Plan/roadmap/active_task.md not found"


def test_active_task_md_contains_p67_completed() -> None:
    """active_task.md must include P67 COMPLETED section after P67 execution."""
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P67" in content, "active_task.md must reference P67"
    assert "COMPLETED" in content or "P67_PATH_B" in content, (
        "active_task.md must contain P67 completion marker or P67 classification"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 19. Summary JSON structure integrity
# ═══════════════════════════════════════════════════════════════════════════════

def test_summary_has_required_top_level_keys(summary: dict) -> None:
    required = {
        "p67_version", "p67_classification", "search_date",
        "candidate_sources", "governance", "recommendation",
        "data_year_2024_gap_status",
    }
    missing = required - set(summary.keys())
    assert not missing, f"Summary missing required keys: {missing}"


def test_summary_governance_has_required_flags(summary: dict) -> None:
    gov = summary.get("governance", {})
    required_flags = {
        "paper_only", "diagnostic_only", "promotion_freeze",
        "kelly_deploy_allowed", "live_api_calls", "paid_api_called",
        "tsl_crawler_called", "runtime_recommendation_logic_changed",
        "real_bet_allowed", "production_ready",
    }
    missing = required_flags - set(gov.keys())
    assert not missing, f"governance block missing flags: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 20. SBRO archive year boundary correctly classified as SOURCE_NO_2024
# ═══════════════════════════════════════════════════════════════════════════════

def test_sbro_classified_as_no_2024(candidates: list[dict]) -> None:
    sbro = next(
        (s for s in candidates if "SportsbookReview" in s.get("source_name", "")),
        None,
    )
    assert sbro is not None, "SBRO source not found in candidate inventory"
    assert sbro["classification"] == "SOURCE_NO_2024", (
        f"SBRO should be SOURCE_NO_2024 (archive stops 2021), got {sbro['classification']!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 21. OddsPortal classified as SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE
# ═══════════════════════════════════════════════════════════════════════════════

def test_oddsportal_classified_as_partial(candidates: list[dict]) -> None:
    op = next(
        (s for s in candidates if "OddsPortal" in s.get("source_name", "")),
        None,
    )
    assert op is not None, "OddsPortal source not found in candidate inventory"
    assert op["classification"] == "SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE", (
        f"OddsPortal should be SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE, "
        f"got {op['classification']!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 22. Synthetic Kaggle dataset classified as SOURCE_UNUSABLE
# ═══════════════════════════════════════════════════════════════════════════════

def test_synthetic_kaggle_dataset_classified_unusable(candidates: list[dict]) -> None:
    synthetic = next(
        (
            s for s in candidates
            if "pratyushpuri" in s.get("url", "").lower()
            or "synthetic" in s.get("notes", "").lower()
        ),
        None,
    )
    assert synthetic is not None, "Synthetic Kaggle dataset not found in inventory"
    assert synthetic["classification"] == "SOURCE_UNUSABLE", (
        f"Synthetic dataset should be SOURCE_UNUSABLE, "
        f"got {synthetic['classification']!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 23. No SOURCE_USABLE_FOR_2024_CLOSING_ML — no confirmed downloadable source
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_confirmed_usable_source_for_2024(candidates: list[dict]) -> None:
    """P67 search confirmed no directly downloadable 2024 MLB moneyline CSV."""
    usable = [
        s["source_name"]
        for s in candidates
        if s["classification"] == "SOURCE_USABLE_FOR_2024_CLOSING_ML"
    ]
    assert not usable, (
        f"Unexpected SOURCE_USABLE classification found — "
        f"must be validated before upgrading: {usable}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 24. Search scope is non-empty and documents search terms used
# ═══════════════════════════════════════════════════════════════════════════════

def test_search_scope_is_documented(summary: dict) -> None:
    scope = summary.get("search_scope", [])
    assert len(scope) >= 5, (
        f"Search scope must document ≥5 search terms, got {len(scope)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 25. Paper-only / diagnostic-only governance flags all True in summary
# ═══════════════════════════════════════════════════════════════════════════════

def test_paper_and_diagnostic_flags_are_true(summary: dict) -> None:
    gov = summary.get("governance", {})
    assert gov.get("paper_only") is True, "governance.paper_only must be True"
    assert gov.get("diagnostic_only") is True, "governance.diagnostic_only must be True"
    assert gov.get("promotion_freeze") is True, "governance.promotion_freeze must be True"
