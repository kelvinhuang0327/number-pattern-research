"""Tests for P270B outcome-blind portfolio geometry & power audit.

These tests verify the *artifact contract* (governance fields, outcome-blind
guard, classification, no actionable wording) and the *script's* static
outcome-forbidden guard. They do not run a backtest and do not access
outcome columns.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "analysis" / "p270b_outcome_blind_portfolio_geometry_power_audit.py"
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p270b_outcome_blind_portfolio_geometry_power_audit_20260611.md"

ALLOWED_CLASSIFICATIONS = {
    "P270B_GEOMETRY_POWER_SUFFICIENT_GO_DESIGN",
    "P270B_GEOMETRY_POWER_INSUFFICIENT_NO_GO",
    "P270B_BLOCKED_OUTCOME_ACCESS_REQUIRED",
    "P270B_BLOCKED_SCHEMA_MISMATCH",
    "P270B_BLOCKED_GOVERNANCE_CONFLICT",
}

FORBIDDEN_OUTCOME_COLUMNS = ("actual_numbers", "hit_count", "special_hit")

# Positive claim phrasing that would assert an improvement/recommendation —
# distinct from the required negation disclaimers ("no hit-rate improvement
# is claimed", "不構成投注建議") which legitimately contain these substrings.
FORBIDDEN_HIT_RATE_PHRASES = (
    "improves hit rate",
    "improves the hit rate",
    "hit rate is improved",
    "提升了中獎率",
    "中獎率提升至",
)

FORBIDDEN_BETTING_PHRASES = (
    "建議投注",
    "we recommend betting",
    "buy this ticket",
    "recommended numbers",
)


def _load_artifact():
    assert JSON_PATH.exists(), f"missing artifact: {JSON_PATH}"
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_script_text():
    assert SCRIPT_PATH.exists(), f"missing script: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text(encoding="utf-8")


def _load_md_text():
    assert MD_PATH.exists(), f"missing artifact: {MD_PATH}"
    return MD_PATH.read_text(encoding="utf-8")


def test_artifact_exists_and_required_fields():
    a = _load_artifact()
    required_fields = [
        "task_id",
        "generated_at",
        "repo_head",
        "branch",
        "mode",
        "outcome_columns_read",
        "db_write",
        "registry_write",
        "strategy_generated",
        "backtest_run",
        "n_fixed",
        "lotteries_analyzed",
        "eligible_draw_counts",
        "ineligible_draw_counts",
        "pool_size_histograms",
        "pool_size_time_trends",
        "pairwise_overlap_summary",
        "coverage_band_summary",
        "g_d_enumeration_summary",
        "causality_check",
        "projected_discordance_summary",
        "mde_summary",
        "kill_criterion_result",
        "final_classification",
        "limitations",
    ]
    for field in required_fields:
        assert field in a, f"missing required field: {field}"

    assert a["task_id"] == "P270B_OUTCOME_BLIND_PORTFOLIO_GEOMETRY_POWER_AUDIT"
    assert set(a["lotteries_analyzed"]) == {"BIG_LOTTO", "DAILY_539", "POWER_LOTTO"}


def test_governance_flags_false():
    a = _load_artifact()
    assert a["outcome_columns_read"] is False
    assert a["db_write"] is False
    assert a["registry_write"] is False
    assert a["strategy_generated"] is False
    assert a["backtest_run"] is False


def test_n_fixed_at_3():
    a = _load_artifact()
    assert a["n_fixed"] == 3


def test_final_classification_is_allowed():
    a = _load_artifact()
    assert a["final_classification"] in ALLOWED_CLASSIFICATIONS


def test_kill_criterion_fields_exist():
    a = _load_artifact()
    kc = a["kill_criterion_result"]
    assert "criterion_1_mde_exceeds_p267c_excess_in_all_lotteries" in kc
    assert "criterion_2_projected_discordance_below_1pct_degenerate" in kc
    assert "kill_triggered" in kc

    c1 = kc["criterion_1_mde_exceeds_p267c_excess_in_all_lotteries"]
    assert "triggered" in c1
    assert "per_lottery" in c1
    for lottery in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO"):
        assert lottery in c1["per_lottery"]
        assert "mde_increment_pp_best_case" in c1["per_lottery"][lottery]
        assert "p267c_best_uncorrected_excess_pp" in c1["per_lottery"][lottery]
        assert "mde_exceeds_excess" in c1["per_lottery"][lottery]


def test_causality_check_passes():
    a = _load_artifact()
    cc = a["causality_check"]
    assert cc["result"] == "PASS"
    assert cc["violations_found"] == 0


def test_no_outcome_columns_in_script_query():
    """The script's SQL query text must not reference any outcome column."""
    text = _load_script_text()

    # Extract the QUERY string literal
    match = re.search(r'QUERY\s*=\s*f?"""(.*?)"""', text, re.DOTALL)
    assert match, "could not locate QUERY string in script"
    query_text = match.group(1)

    for col in FORBIDDEN_OUTCOME_COLUMNS:
        assert col not in query_text, f"forbidden outcome column '{col}' found in QUERY"


def test_outcome_forbidden_guard_present_in_script():
    """A static guard/assertion against outcome columns must exist in the script."""
    text = _load_script_text()
    assert "FORBIDDEN_COLUMNS" in text
    assert "ABORTING" in text or "assert" in text
    for col in FORBIDDEN_OUTCOME_COLUMNS:
        assert col in text  # listed in FORBIDDEN_COLUMNS for the guard to check


def test_artifact_does_not_reference_outcome_columns():
    """Defense-in-depth: the produced JSON/MD artifacts should not contain raw
    outcome-column values (they were never loaded, so this should trivially hold)."""
    a = _load_artifact()
    raw = json.dumps(a, ensure_ascii=False)
    # The literal column names may appear in 'limitations' prose (explaining
    # they were NOT read) - that's fine. Check no outcome data keys exist
    # anywhere in the artifact structure itself.
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in FORBIDDEN_OUTCOME_COLUMNS, f"forbidden key '{k}' present in artifact"
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(a)


def test_no_hit_rate_improvement_claim_wording():
    md = _load_md_text()
    a = _load_artifact()
    raw = md + json.dumps(a, ensure_ascii=False)
    lowered = raw.lower()
    for phrase in FORBIDDEN_HIT_RATE_PHRASES:
        assert phrase.lower() not in lowered, f"forbidden phrase found: {phrase}"
    # explicit "no hit-rate improvement" disclaimer must be present
    assert "no hit-rate improvement is claimed" in lowered or "does not improve win rate" in lowered


def test_no_betting_actionable_wording():
    md = _load_md_text()
    a = _load_artifact()
    raw = md + json.dumps(a, ensure_ascii=False)
    lowered = raw.lower()
    for phrase in FORBIDDEN_BETTING_PHRASES:
        assert phrase.lower() not in lowered, f"forbidden phrase found: {phrase}"


def test_md_outcome_blind_disclaimers_present():
    md = _load_md_text()
    assert "outcome-blind" in md.lower()
    assert "no backtest was run" in md.lower()
    assert "no db write happened" in md.lower()
    assert "no registry mutation happened" in md.lower()
    assert "no strategy was generated" in md.lower()
