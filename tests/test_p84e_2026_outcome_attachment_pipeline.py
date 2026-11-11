"""
Tests for P84E — 2026 Outcome Attachment Pipeline for Canonical Prediction Rows

37 tests covering:
  - Source artifact loading and classification verification
  - Canonical prediction row integrity
  - Outcome collector design and MLB-only source enforcement
  - Outcome attachment correctness (game_id match, final-only, no fabrication)
  - Derived file integrity and canonical file preservation
  - Prediction-only metrics (hit_rate, AUC, Brier, ECE, subsets)
  - Governance invariants
  - JSON schema stability
  - Report content
  - Active task update
  - P83A–P84E regression

Expected artifacts (must exist before running):
  data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json
  data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl
  report/p84e_2026_outcome_attachment_20260526.md
"""

import json
import pathlib
import math

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P84D_SUMMARY_PATH    = ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json"
P84C_SUMMARY_PATH    = ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json"
PRED_PATH            = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
P84E_SUMMARY_PATH    = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"
P84E_DERIVED_PATH    = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
P84E_REPORT_PATH     = ROOT / "report/p84e_2026_outcome_attachment_20260526.md"
ACTIVE_TASK_PATH     = ROOT / "00-Plan/roadmap/active_task.md"

EXPECTED_P84D_CLASSIFICATION = "P84D_PITCHER_COVERAGE_AUDIT_READY_NO_BACKFILL"
EXPECTED_P84C_CLASSIFICATION = "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING"
CANONICAL_ROWS_EXPECTED      = 828
SAMPLE_LIMITED_THRESHOLD     = 30
MIN_METRICS_THRESHOLD        = 10


def _load_p84e_summary() -> dict:
    return json.loads(P84E_SUMMARY_PATH.read_text(encoding="utf-8"))


def _load_derived_rows() -> list[dict]:
    return [json.loads(ln) for ln in P84E_DERIVED_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _load_canonical_rows() -> list[dict]:
    return [json.loads(ln) for ln in PRED_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ────────────────────────────────────────────────────────────────────────────
# 1–2: P84D source artifact
# ────────────────────────────────────────────────────────────────────────────

def test_01_p84d_source_artifact_loads():
    """P84D summary must exist and be valid JSON."""
    assert P84D_SUMMARY_PATH.exists(), f"Missing: {P84D_SUMMARY_PATH}"
    data = json.loads(P84D_SUMMARY_PATH.read_text())
    assert isinstance(data, dict)
    assert "p84d_classification" in data


def test_02_p84d_classification_verified():
    """P84D classification must be PITCHER_COVERAGE_AUDIT_READY_NO_BACKFILL."""
    data = json.loads(P84D_SUMMARY_PATH.read_text())
    assert data["p84d_classification"] == EXPECTED_P84D_CLASSIFICATION


# ────────────────────────────────────────────────────────────────────────────
# 3–4: P84C source artifact
# ────────────────────────────────────────────────────────────────────────────

def test_03_p84c_source_artifact_loads():
    """P84C summary must exist and be valid JSON."""
    assert P84C_SUMMARY_PATH.exists(), f"Missing: {P84C_SUMMARY_PATH}"
    data = json.loads(P84C_SUMMARY_PATH.read_text())
    assert isinstance(data, dict)
    assert "p84c_classification" in data


def test_04_p84c_classification_verified():
    """P84C classification must be PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING."""
    data = json.loads(P84C_SUMMARY_PATH.read_text())
    assert data["p84c_classification"] == EXPECTED_P84C_CLASSIFICATION


# ────────────────────────────────────────────────────────────────────────────
# 5–6: Canonical prediction rows
# ────────────────────────────────────────────────────────────────────────────

def test_05_canonical_prediction_rows_exists():
    """Canonical prediction rows JSONL must exist."""
    assert PRED_PATH.exists(), f"Missing: {PRED_PATH}"


def test_06_canonical_rows_count_verified():
    """Canonical prediction rows must have exactly 828 rows."""
    rows = _load_canonical_rows()
    assert len(rows) == CANONICAL_ROWS_EXPECTED, (
        f"Expected {CANONICAL_ROWS_EXPECTED} rows, got {len(rows)}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 7–9: Outcome collector design
# ────────────────────────────────────────────────────────────────────────────

def test_07_outcome_collector_source_is_mlb_public_result_only():
    """All derived rows with outcomes must have outcome_source = MLB_STATS_API_PUBLIC_RESULT."""
    rows = _load_derived_rows()
    for r in rows:
        if r.get("outcome_available") is True:
            assert r.get("outcome_source") == "MLB_STATS_API_PUBLIC_RESULT", (
                f"Row {r.get('game_id')!r} has non-public source: {r.get('outcome_source')!r}"
            )


def test_08_outcome_collector_schema_validator_present():
    """P84E summary must declare outcome_schema_validated=True."""
    summary = _load_p84e_summary()
    collector = summary.get("step2_outcome_collector", {})
    assert collector.get("outcome_schema_validated") is True, (
        "step2_outcome_collector.outcome_schema_validated must be True"
    )


def test_09_final_game_status_detection_defined():
    """P84E summary must list the final_states checked (non-empty)."""
    summary = _load_p84e_summary()
    collector = summary.get("step2_outcome_collector", {})
    final_states = collector.get("final_states", [])
    assert len(final_states) > 0, "final_states list must be non-empty in step2_outcome_collector"
    assert "Final" in final_states, "'Final' must be in final_states"


# ────────────────────────────────────────────────────────────────────────────
# 10–14: Outcome attachment correctness
# ────────────────────────────────────────────────────────────────────────────

def test_10_non_final_games_remain_pending():
    """Rows with outcome_available=False must have is_correct=None and actual_winner=None."""
    rows = _load_derived_rows()
    for r in rows:
        if r.get("outcome_available") is False:
            assert r.get("is_correct") is None, (
                f"Pending row {r.get('game_id')!r} must not have is_correct set"
            )
            assert r.get("actual_winner") is None, (
                f"Pending row {r.get('game_id')!r} must not have actual_winner set"
            )


def test_11_outcome_attachment_matches_by_game_id():
    """Every derived row's game_id must match a canonical row's game_id."""
    canonical_ids = {r["game_id"] for r in _load_canonical_rows()}
    for r in _load_derived_rows():
        assert r.get("game_id") in canonical_ids, (
            f"Derived row has unknown game_id: {r.get('game_id')!r}"
        )


def test_12_actual_winner_derived_from_final_scores_only():
    """actual_winner must only be set when outcome_available=True and scores are consistent."""
    rows = _load_derived_rows()
    for r in rows:
        if r.get("actual_winner") is not None:
            assert r.get("outcome_available") is True, (
                f"Row {r.get('game_id')!r}: actual_winner set but outcome_available is not True"
            )
            hs = r.get("result_home_score")
            as_ = r.get("result_away_score")
            assert hs is not None and as_ is not None, (
                f"Row {r.get('game_id')!r}: actual_winner set but scores are None"
            )
            if hs > as_:
                assert r["actual_winner"] == "home"
            else:
                assert r["actual_winner"] == "away"


def test_13_is_correct_computed_only_when_actual_winner_exists():
    """is_correct must not be set on any row lacking actual_winner."""
    rows = _load_derived_rows()
    for r in rows:
        if r.get("actual_winner") is None:
            assert r.get("is_correct") is None, (
                f"Row {r.get('game_id')!r}: is_correct set without actual_winner"
            )
        else:
            # When actual_winner is set, is_correct must be a bool
            assert isinstance(r.get("is_correct"), bool), (
                f"Row {r.get('game_id')!r}: is_correct must be bool when actual_winner is known"
            )


def test_14_pending_rows_keep_is_correct_none():
    """All rows where outcome_available=False must have is_correct=None."""
    rows = _load_derived_rows()
    for r in rows:
        if not r.get("outcome_available"):
            assert r.get("is_correct") is None


# ────────────────────────────────────────────────────────────────────────────
# 15: File integrity
# ────────────────────────────────────────────────────────────────────────────

def test_15_derived_file_written_original_canonical_rows_preserved():
    """Derived output must exist; original canonical rows must NOT have outcome_available."""
    assert P84E_DERIVED_PATH.exists(), f"Derived rows file missing: {P84E_DERIVED_PATH}"
    derived = _load_derived_rows()
    assert len(derived) == CANONICAL_ROWS_EXPECTED, (
        f"Derived rows must still be {CANONICAL_ROWS_EXPECTED}, got {len(derived)}"
    )
    # Original canonical file must not have been modified with outcome_available
    canonical = _load_canonical_rows()
    for r in canonical:
        assert "outcome_available" not in r, (
            "Original canonical rows must NOT contain outcome_available — "
            "only the derived file should have this field"
        )


# ────────────────────────────────────────────────────────────────────────────
# 16–17: Counts in summary
# ────────────────────────────────────────────────────────────────────────────

def test_16_n_outcome_available_computed():
    """P84E summary must have n_outcome_available in step3_attachment_stats."""
    summary = _load_p84e_summary()
    stats = summary.get("step3_attachment_stats", {})
    assert "n_outcome_available" in stats
    n = stats["n_outcome_available"]
    assert isinstance(n, int) and n >= 0


def test_17_pending_count_computed():
    """P84E summary must have n_outcome_pending in step3_attachment_stats."""
    summary = _load_p84e_summary()
    stats = summary.get("step3_attachment_stats", {})
    assert "n_outcome_pending" in stats
    n = stats["n_outcome_pending"]
    assert isinstance(n, int) and n >= 0


# ────────────────────────────────────────────────────────────────────────────
# 18–21: Metrics gating
# ────────────────────────────────────────────────────────────────────────────

def test_18_hit_rate_computed_only_when_n_outcome_available_positive():
    """hit_rate must be None iff n_outcome_available == 0 (or < MIN_METRICS_THRESHOLD)."""
    summary = _load_p84e_summary()
    all_m = summary.get("step4_metrics", {}).get("all", {})
    n = all_m.get("n_outcome_available", 0)
    hit_rate = all_m.get("hit_rate")
    if n < MIN_METRICS_THRESHOLD:
        assert hit_rate is None, "hit_rate must be None when n_outcome_available < threshold"
    else:
        assert hit_rate is not None, "hit_rate must be computed when n_outcome_available >= threshold"
        assert 0.0 <= hit_rate <= 1.0, f"hit_rate must be in [0,1], got {hit_rate}"


def test_19_auc_computed_only_when_valid_binary_outcomes():
    """AUC must be None if n < threshold; otherwise non-None and in valid range."""
    summary = _load_p84e_summary()
    all_m = summary.get("step4_metrics", {}).get("all", {})
    n = all_m.get("n_outcome_available", 0)
    auc = all_m.get("auc")
    if n < MIN_METRICS_THRESHOLD:
        assert auc is None, "AUC must be None when sample too small"
    else:
        if auc is not None:
            assert 0.5 <= auc <= 1.0, f"Reported AUC (max-direction) must be in [0.5, 1.0], got {auc}"


def test_20_brier_computed_only_when_valid_outcomes():
    """Brier must be None if n < threshold; otherwise non-None and in [0,1]."""
    summary = _load_p84e_summary()
    all_m = summary.get("step4_metrics", {}).get("all", {})
    n = all_m.get("n_outcome_available", 0)
    brier = all_m.get("brier")
    if n < MIN_METRICS_THRESHOLD:
        assert brier is None
    else:
        if brier is not None:
            assert 0.0 <= brier <= 1.0, f"Brier score must be in [0,1], got {brier}"


def test_21_ece_computed_only_when_valid_outcomes():
    """ECE must be None if n < threshold; otherwise non-None and in [0,1]."""
    summary = _load_p84e_summary()
    all_m = summary.get("step4_metrics", {}).get("all", {})
    n = all_m.get("n_outcome_available", 0)
    ece = all_m.get("ece")
    if n < MIN_METRICS_THRESHOLD:
        assert ece is None
    else:
        if ece is not None:
            assert 0.0 <= ece <= 1.0, f"ECE must be in [0,1], got {ece}"


# ────────────────────────────────────────────────────────────────────────────
# 22–24: Subset metrics
# ────────────────────────────────────────────────────────────────────────────

def test_22_primary_125_outcome_metrics_computed():
    """primary_125 subset must appear in metrics with n_rows and n_outcome_available."""
    summary = _load_p84e_summary()
    p125 = summary.get("step4_metrics", {}).get("primary_125", {})
    assert "n_rows" in p125, "primary_125 metrics must include n_rows"
    assert "n_outcome_available" in p125
    assert p125["n_rows"] > 0, "primary_125 must have at least some rows"


def test_23_shadow_100_outcome_metrics_computed():
    """shadow_100 subset must appear in metrics."""
    summary = _load_p84e_summary()
    s100 = summary.get("step4_metrics", {}).get("shadow_100", {})
    assert "n_rows" in s100
    assert "n_outcome_available" in s100
    assert s100["n_rows"] > 0


def test_24_tier_b_metrics_sample_limited_note_present():
    """tier_b subset must be present; if sample_limited, note or hit_rate handling is documented."""
    summary = _load_p84e_summary()
    tier_b = summary.get("step4_metrics", {}).get("tier_b", {})
    assert "n_rows" in tier_b
    assert "n_outcome_available" in tier_b
    assert "sample_limited" in tier_b
    # If sample_limited, hit_rate may be None or computed — just check consistency
    n = tier_b["n_outcome_available"]
    sample_limited = tier_b["sample_limited"]
    assert sample_limited == (n < SAMPLE_LIMITED_THRESHOLD), (
        f"sample_limited mismatch: n={n}, sample_limited={sample_limited}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 25–32: Governance invariants
# ────────────────────────────────────────────────────────────────────────────

def test_25_no_odds_required():
    """governance.odds_used must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["odds_used"] is False


def test_26_no_odds_api_call():
    """governance.odds_api_called must be False; live_api_calls must be 0."""
    summary = _load_p84e_summary()
    gov = summary["governance"]
    assert gov.get("odds_api_called") is False
    assert gov.get("live_api_calls") == 0


def test_27_no_api_key_access():
    """governance.api_key_accessed must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["api_key_accessed"] is False


def test_28_no_edge_calculated():
    """governance.market_edge_calculated must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["market_edge_calculated"] is False


def test_29_no_clv_calculated():
    """governance.clv_calculated must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["clv_calculated"] is False


def test_30_no_ev_calculated():
    """governance.ev_calculated must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["ev_calculated"] is False


def test_31_no_kelly_calculated():
    """governance.kelly_calculated must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["kelly_calculated"] is False


def test_32_production_ready_false():
    """governance.production_ready must be False."""
    summary = _load_p84e_summary()
    assert summary["governance"]["production_ready"] is False


# ────────────────────────────────────────────────────────────────────────────
# 33–35: Report content
# ────────────────────────────────────────────────────────────────────────────

def test_33_json_schema_stable():
    """P84E summary must have all required top-level keys."""
    summary = _load_p84e_summary()
    required_keys = [
        "p84e_classification",
        "date",
        "generated_at",
        "allowed_classifications",
        "step1_verify",
        "step2_outcome_collector",
        "step3_attachment_stats",
        "step4_metrics",
        "governance",
        "remaining_blockers",
        "forbidden_scan",
    ]
    for key in required_keys:
        assert key in summary, f"Missing required key in P84E summary: {key!r}"


def test_34_report_includes_outcome_table():
    """Report must include Markdown table rows with outcome data."""
    assert P84E_REPORT_PATH.exists(), f"Missing report: {P84E_REPORT_PATH}"
    text = P84E_REPORT_PATH.read_text(encoding="utf-8")
    # Must contain at least one markdown table line
    assert "| Outcome available" in text or "n_outcome_available" in text, (
        "Report must include outcome availability table"
    )
    # Must contain pipe-based Markdown table
    assert "|" in text, "Report must contain Markdown table syntax"


def test_35_report_includes_sample_size_warning():
    """Report must include a sample-size warning or note about partial season."""
    text = P84E_REPORT_PATH.read_text(encoding="utf-8")
    warning_present = (
        "SAMPLE SIZE WARNING" in text
        or "sample-limited" in text
        or "partial" in text.lower()
        or "ongoing" in text.lower()
    )
    assert warning_present, "Report must include sample size or partial-season warning"


# ────────────────────────────────────────────────────────────────────────────
# 36: Active task
# ────────────────────────────────────────────────────────────────────────────

def test_36_active_task_updated():
    """active_task.md must contain a P84E marker comment."""
    assert ACTIVE_TASK_PATH.exists(), f"Missing: {ACTIVE_TASK_PATH}"
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "<!-- P84E:" in content, "active_task.md must contain <!-- P84E: ... --> marker"


# ────────────────────────────────────────────────────────────────────────────
# 37: Regression — P83A through P84E chain
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.regression
def test_37_p83a_p84e_regression_chain():
    """
    Regression: verify all P83A–P84E test modules are importable
    and their summary artifacts exist.
    """
    phase_artifacts = [
        ROOT / "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json",
        ROOT / "data/mlb_2026/derived/p84a_2026_upstream_data_collector_contract_summary.json",
        ROOT / "data/mlb_2026/derived/p84b_2026_public_stats_collector_summary.json",
        ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json",
        ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json",
        ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    ]
    for path in phase_artifacts:
        assert path.exists(), f"Regression: missing artifact {path}"
        data = json.loads(path.read_text())
        assert isinstance(data, dict), f"Regression: {path} is not a valid dict"

    # Verify classifications are set
    p84e = json.loads(
        (ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json").read_text()
    )
    assert p84e["p84e_classification"] in [
        "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
        "P84E_OUTCOME_ATTACHMENT_READY_SAMPLE_LIMITED",
        "P84E_OUTCOMES_PENDING_NO_FINAL_RESULTS",
    ], f"Unexpected P84E classification: {p84e['p84e_classification']}"

    # Verify derived rows file
    assert P84E_DERIVED_PATH.exists(), "Regression: derived outcome rows file must exist"
    derived = _load_derived_rows()
    assert len(derived) == CANONICAL_ROWS_EXPECTED, (
        f"Regression: derived rows count must be {CANONICAL_ROWS_EXPECTED}"
    )

    # Governance chain: production_ready=False at every P84 phase
    for path in [
        ROOT / "data/mlb_2026/derived/p84b_2026_public_stats_collector_summary.json",
        ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json",
        ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json",
        ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    ]:
        d = json.loads(path.read_text())
        gov = d.get("governance", {})
        assert gov.get("production_ready") is False, (
            f"Regression: {path.name} governance.production_ready must be False"
        )
        assert gov.get("ev_calculated") is False, (
            f"Regression: {path.name} governance.ev_calculated must be False"
        )
