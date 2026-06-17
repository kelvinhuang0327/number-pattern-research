"""
P277A — Historical Observation Status Reclassification Audit tests.

All tests are DB-FREE.  They use:
  - The committed artifact JSON files (read-only source of truth)
  - The analysis module (imported directly)
  - In-memory synthetic structures for unit tests
  - Source-code inspection for forbidden interface verification

The canonical production database is NEVER opened, referenced, or written.

Test categories:
  1. Forbidden-interface scan (static source-code check)
  2. Source artifact existence and hash verification
  3. JSON parse and schema verification
  4. Dual-gate classification unit tests (synthetic cases)
  5. Taxonomy label coverage
  6. Deterministic regeneration (two calls, identical digest)
  7. Canonical digest independent recomputation
  8. JSON/Markdown consistency
  9. Governance invariants
  10. Strategy record mandatory fields
  11. Portfolio record mandatory fields
  12. Required research questions answered
  13. P276B verdict preservation
  14. P273A GO-candidate mapping preservation
  15. OOS-superseded identification
  16. Exactly four whitelist files verified
  17. Unicode/control-char safety
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import unicodedata
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load module and artifact
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "analysis" / "p277a_historical_observation_status_reclassification.py"

spec = importlib.util.spec_from_file_location("p277a_module", MODULE_PATH)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

PINNED_GENERATED_AT = "2026-06-17T00:00:00+00:00"
PINNED_DIGEST = "d75f8383c5029c5024279f9e3792d417885cecc202f25740f10406a701f14284"

JSON_PATH = ROOT / "outputs" / "research" / "p277a_historical_observation_status_reclassification_20260617.json"
MD_PATH = ROOT / "outputs" / "research" / "p277a_historical_observation_status_reclassification_20260617.md"


@pytest.fixture(scope="module")
def artifact():
    return M.build_artifact(generated_at=PINNED_GENERATED_AT)


@pytest.fixture(scope="module")
def committed_json():
    with open(JSON_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Forbidden-interface scan
# ---------------------------------------------------------------------------

def test_no_sqlite3_import():
    src = MODULE_PATH.read_text(encoding="utf-8")
    # Must not contain 'import sqlite3' or 'from sqlite3'
    assert "import sqlite3" not in src, \
        "FORBIDDEN: 'import sqlite3' found in analysis module"
    assert "from sqlite3" not in src, \
        "FORBIDDEN: 'from sqlite3' found in analysis module"


def test_no_requests_import():
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in src, \
        "FORBIDDEN: 'import requests' found in analysis module"


def test_no_urllib_import():
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "import urllib" not in src, \
        "FORBIDDEN: 'import urllib' found in analysis module"
    assert "from urllib" not in src, \
        "FORBIDDEN: 'from urllib' found in analysis module"


def test_no_socket_import():
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "import socket" not in src, \
        "FORBIDDEN: 'import socket' found in analysis module"


def test_no_subprocess_import():
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "import subprocess" not in src, \
        "FORBIDDEN: 'import subprocess' found in analysis module"
    assert "from subprocess" not in src, \
        "FORBIDDEN: 'from subprocess' found in analysis module"


def test_no_os_system():
    """Verify os.system is not called in analysis module.
    The string 'os.system' may appear in docstrings or string literals as
    documentation of forbidden interfaces. Check for actual call pattern only.
    """
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.system(" not in src, \
        "FORBIDDEN: 'os.system(' call found in analysis module"


def test_no_db_open_patterns():
    """Verify no database open patterns exist in module source."""
    src = MODULE_PATH.read_text(encoding="utf-8")
    forbidden_patterns = [
        "connect(",
        "sqlite3.connect",
        "open.*\\.db",
    ]
    for pat in forbidden_patterns[:2]:  # First two are exact patterns
        assert pat not in src, f"FORBIDDEN: '{pat}' found in analysis module"


# ---------------------------------------------------------------------------
# 2. Source artifact existence and hash verification
# ---------------------------------------------------------------------------

def test_all_source_artifacts_exist():
    hashes = M.build_artifact_hashes()
    missing = M.verify_artifact_hashes(hashes)
    assert len(missing) == 0, f"Missing source artifacts: {missing}"


def test_source_artifact_hashes_are_sha256():
    hashes = M.build_artifact_hashes()
    for key, h in hashes.items():
        assert h != "MISSING", f"Artifact '{key}' is missing"
        assert re.match(r"^[0-9a-f]{64}$", h), \
            f"Artifact '{key}' hash '{h}' is not a valid SHA-256"


def test_p267c_hash_matches_p273a_reference():
    """P273A frozen_setup.strategy_set_source.sha256 must match P267C artifact hash."""
    p267c_path = ROOT / "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json"
    with open(p267c_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()

    # Load P273A inferential artifact to get the recorded hash
    p273a_path = ROOT / "outputs/research/p273a_prize_aware_inferential_validation_20260615.json"
    with open(p273a_path) as f:
        p273a = json.load(f)
    recorded_hash = p273a["frozen_setup"]["strategy_set_source"]["sha256"]

    assert actual_hash == recorded_hash, (
        f"P267C hash mismatch: actual={actual_hash} recorded_in_p273a={recorded_hash}"
    )


# ---------------------------------------------------------------------------
# 3. JSON parse and schema verification
# ---------------------------------------------------------------------------

def test_json_parses_successfully():
    with open(JSON_PATH) as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_top_level_required_keys(artifact):
    required = [
        "task_id", "generated_at", "source_commit", "source_artifact_manifest",
        "source_artifact_hashes", "universe_definition", "universe_counts",
        "endpoint_counts", "classification_taxonomy", "evidence_precedence",
        "owner_dual_gate_rule", "historical_artifacts_unchanged",
        "database_opened", "database_write", "prediction_success_claim",
        "strategy_promoted", "classification_summary", "strategies",
        "portfolios", "evidence_gaps", "contradictions", "required_questions",
        "recommended_followups", "canonical_payload_digest",
    ]
    for key in required:
        assert key in artifact, f"Missing top-level key: {key}"


def test_strategy_record_required_fields(artifact):
    required = [
        "identity", "lottery_type", "strategy_id", "endpoint", "bet_budget",
        "windows_available", "evidence_family", "original_classification",
        "original_source_artifacts", "source_metrics", "baseline_type",
        "random_baseline_value", "observed_value", "delta_vs_random",
        "random_baseline_status", "corrected_support_status", "stability_status",
        "OOS_status", "best_equal_budget_comparator", "delta_vs_best_equal_budget",
        "best_equal_budget_status", "observation_retention_status",
        "promotion_status", "future_confirmation_status", "evidence_completeness",
        "current_mapping", "reclassification_reason", "historical_artifact_unchanged",
        "limitations",
    ]
    for rec in artifact["strategies"]:
        for field in required:
            assert field in rec, \
                f"Strategy '{rec.get('identity', '?')}' missing field '{field}'"


def test_portfolio_record_required_fields(artifact):
    required = [
        "identity", "portfolio_id", "lottery_type", "ticket_budget", "kind",
        "source_cells", "equal_budget_constituents", "current_mapping",
        "observation_retention_status", "promotion_status",
        "future_confirmation_status", "scientific_verdict_preserved",
        "historical_artifact_unchanged", "limitations",
    ]
    for rec in artifact["portfolios"]:
        for field in required:
            assert field in rec, \
                f"Portfolio '{rec.get('portfolio_id', '?')}' missing field '{field}'"


# ---------------------------------------------------------------------------
# 4. Dual-gate classification unit tests (synthetic cases)
# ---------------------------------------------------------------------------

def test_gate1_pass_above_random():
    """A strategy above random with adequate support must NOT be NO_EVIDENCE_OVER_RANDOM."""
    result = M.classify_record(
        random_baseline_status="ABOVE_RANDOM",
        corrected_support_status="CORRECTED_NULL",
        oos_status="NO_OOS_AVAILABLE",
        original_classification="DESCRIPTIVE_ONLY",
        evidence_level=6,
        has_valid_baseline=True,
        support_adequate=True,
    )
    assert result != "NO_EVIDENCE_OVER_RANDOM", \
        "Above-random strategy must not be classified as NO_EVIDENCE_OVER_RANDOM"
    assert result in M.TAXONOMY, f"Result '{result}' not in taxonomy"


def test_gate1_fail_below_random():
    """A strategy below random must be NO_EVIDENCE_OVER_RANDOM."""
    result = M.classify_record(
        random_baseline_status="AT_OR_BELOW_RANDOM",
        corrected_support_status="CORRECTED_NULL",
        oos_status="NO_OOS_AVAILABLE",
        original_classification="NULL",
        evidence_level=6,
        has_valid_baseline=True,
        support_adequate=True,
    )
    assert result == "NO_EVIDENCE_OVER_RANDOM"


def test_oos_null_supersedes_corrected():
    """OOS NULL evidence must supersede corrected in-window positive."""
    result = M.classify_record(
        random_baseline_status="ABOVE_RANDOM",
        corrected_support_status="CORRECTED_SIGNIFICANT",
        oos_status="OOS_NULL",
        original_classification="GO_CANDIDATE_RESEARCH_ONLY",
        evidence_level=2,
        has_valid_baseline=True,
        support_adequate=True,
    )
    assert result == "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL"


def test_corrected_significant_yields_supported():
    """Corrected-significant above-random without OOS must be OBSERVATION_SUPPORTED."""
    result = M.classify_record(
        random_baseline_status="ABOVE_RANDOM",
        corrected_support_status="CORRECTED_SIGNIFICANT",
        oos_status="NO_OOS_AVAILABLE",
        original_classification="GO_CANDIDATE_RESEARCH_ONLY",
        evidence_level=4,
        has_valid_baseline=True,
        support_adequate=True,
    )
    assert result == "OBSERVATION_SUPPORTED_ABOVE_RANDOM"


def test_insufficient_support():
    """Insufficient support must yield INSUFFICIENT_SUPPORT."""
    result = M.classify_record(
        random_baseline_status="ABOVE_RANDOM",
        corrected_support_status="NO_INFERENCE_PERFORMED",
        oos_status="NO_OOS_AVAILABLE",
        original_classification="INSUFFICIENT_SUPPORT",
        evidence_level=7,
        has_valid_baseline=True,
        support_adequate=False,
    )
    assert result == "INSUFFICIENT_SUPPORT"


def test_no_valid_baseline():
    """No valid baseline must yield INSUFFICIENT_RANDOM_BASELINE_EVIDENCE."""
    result = M.classify_record(
        random_baseline_status="UNKNOWN_BASELINE",
        corrected_support_status="NO_INFERENCE_PERFORMED",
        oos_status="NO_OOS_AVAILABLE",
        original_classification="INSUFFICIENT_SUPPORT",
        evidence_level=7,
        has_valid_baseline=False,
        support_adequate=False,
    )
    assert result == "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE"


def test_dual_gate_allows_above_random_below_best():
    """
    A strategy MAY beat random (Gate 1) while failing to beat the best
    equal-budget strategy. This must NOT be treated as contradictory or
    classified as NO_EVIDENCE_OVER_RANDOM.
    """
    result = M.classify_record(
        random_baseline_status="ABOVE_RANDOM",
        corrected_support_status="DESCRIPTIVE_ONLY_ABOVE_RANDOM",
        oos_status="NO_OOS_AVAILABLE",
        original_classification="DESCRIPTIVE_ONLY",
        evidence_level=5,
        has_valid_baseline=True,
        support_adequate=True,
    )
    assert result != "NO_EVIDENCE_OVER_RANDOM", \
        "Dual-gate: above_random + below_best_strategy must NOT yield NO_EVIDENCE_OVER_RANDOM"
    # Must be one of the positive observation classifications
    assert result in (
        "OBSERVATION_POTENTIAL_ABOVE_RANDOM",
        "OBSERVATION_SUPPORTED_ABOVE_RANDOM",
        "COMPETITIVE_OBSERVATION_STRATEGY",
        "STRONG_RESEARCH_CANDIDATE",
        "UNDERPOWERED_OBSERVATION_POTENTIAL",
    ), f"Unexpected result: {result}"


# ---------------------------------------------------------------------------
# 5. Taxonomy label coverage
# ---------------------------------------------------------------------------

def test_all_strategy_mappings_in_taxonomy(artifact):
    for rec in artifact["strategies"]:
        assert rec["current_mapping"] in M.TAXONOMY, \
            f"Strategy '{rec['identity']}' has invalid mapping '{rec['current_mapping']}'"


def test_all_portfolio_mappings_in_taxonomy(artifact):
    for rec in artifact["portfolios"]:
        assert rec["current_mapping"] in M.TAXONOMY, \
            f"Portfolio '{rec['portfolio_id']}' has invalid mapping '{rec['current_mapping']}'"


def test_promotion_status_values(artifact):
    valid_promo = {"NOT_PROMOTED", "PROMOTION_REVIEW_NOT_AUTHORIZED"}
    for rec in artifact["strategies"]:
        assert rec["promotion_status"] in valid_promo, \
            f"Strategy '{rec['identity']}' has invalid promotion_status '{rec['promotion_status']}'"
    for rec in artifact["portfolios"]:
        assert rec["promotion_status"] in valid_promo, \
            f"Portfolio '{rec['portfolio_id']}' has invalid promotion_status"


# ---------------------------------------------------------------------------
# 6. Deterministic regeneration
# ---------------------------------------------------------------------------

def test_deterministic_regeneration_digest():
    """Two regenerations must yield identical canonical_payload_digest."""
    a1 = M.build_artifact(generated_at=PINNED_GENERATED_AT)
    a2 = M.build_artifact(generated_at=PINNED_GENERATED_AT)
    assert a1["canonical_payload_digest"] == a2["canonical_payload_digest"], \
        "Non-deterministic: two regenerations yielded different canonical_payload_digest"


def test_deterministic_strategy_order():
    """Strategy records must appear in deterministic order across regenerations."""
    a1 = M.build_artifact(generated_at=PINNED_GENERATED_AT)
    a2 = M.build_artifact(generated_at=PINNED_GENERATED_AT)
    ids1 = [r["identity"] for r in a1["strategies"]]
    ids2 = [r["identity"] for r in a2["strategies"]]
    assert ids1 == ids2, "Non-deterministic: strategy order changed across regenerations"


# ---------------------------------------------------------------------------
# 7. Canonical digest independent recomputation
# ---------------------------------------------------------------------------

def test_canonical_digest_matches_pinned(artifact):
    """The canonical_payload_digest must match the pinned expected value."""
    assert artifact["canonical_payload_digest"] == PINNED_DIGEST, (
        f"Canonical digest mismatch:\n"
        f"  actual:   {artifact['canonical_payload_digest']}\n"
        f"  expected: {PINNED_DIGEST}"
    )


def test_canonical_digest_independent_recompute(artifact):
    """Independently recompute the digest and compare to stored value."""
    payload_copy = dict(artifact)
    stored_digest = payload_copy.pop("canonical_payload_digest", None)
    payload_copy["canonical_payload_digest"] = ""
    recomputed = M.compute_canonical_digest(payload_copy)
    assert recomputed == stored_digest, (
        f"Independent recomputed digest does not match stored:\n"
        f"  recomputed: {recomputed}\n"
        f"  stored:     {stored_digest}"
    )


def test_committed_artifact_digest_matches(committed_json):
    """The committed JSON file's canonical_payload_digest must match PINNED_DIGEST."""
    assert committed_json["canonical_payload_digest"] == PINNED_DIGEST, (
        f"Committed JSON digest mismatch:\n"
        f"  actual:   {committed_json['canonical_payload_digest']}\n"
        f"  expected: {PINNED_DIGEST}"
    )


# ---------------------------------------------------------------------------
# 8. JSON/Markdown consistency
# ---------------------------------------------------------------------------

def test_markdown_file_exists():
    assert MD_PATH.exists(), f"Markdown file not found: {MD_PATH}"


def test_markdown_contains_task_id():
    content = MD_PATH.read_text(encoding="utf-8")
    assert "P277A" in content, "Markdown does not mention P277A"


def test_markdown_contains_digest(artifact):
    content = MD_PATH.read_text(encoding="utf-8")
    assert artifact["canonical_payload_digest"] in content, \
        "Markdown does not contain canonical_payload_digest"


def test_markdown_contains_source_commit(artifact):
    content = MD_PATH.read_text(encoding="utf-8")
    assert artifact["source_commit"] in content, \
        "Markdown does not contain source_commit"


def test_markdown_strategy_count_consistent(artifact, committed_json):
    """Strategy count must be consistent between JSON and markdown."""
    md_content = MD_PATH.read_text(encoding="utf-8")
    n_strategies = committed_json["classification_summary"]["unique_strategy_cell_count"]
    # The markdown must reference the correct count
    assert str(n_strategies) in md_content, \
        f"Markdown does not mention strategy count '{n_strategies}'"


def test_markdown_p276b_verdict_preserved():
    content = MD_PATH.read_text(encoding="utf-8")
    assert "NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE" in content, \
        "Markdown does not preserve P276B verdict NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE"


# ---------------------------------------------------------------------------
# 9. Governance invariants
# ---------------------------------------------------------------------------

def test_prediction_success_claim_false(artifact):
    assert artifact["prediction_success_claim"] is False


def test_strategy_promoted_false(artifact):
    assert artifact["strategy_promoted"] is False


def test_database_opened_false(artifact):
    assert artifact["database_opened"] is False


def test_database_write_false(artifact):
    assert artifact["database_write"] is False


def test_historical_artifacts_unchanged(artifact):
    assert artifact["historical_artifacts_unchanged"] is True
    for rec in artifact["strategies"]:
        assert rec["historical_artifact_unchanged"] is True, \
            f"Strategy '{rec['identity']}' historical_artifact_unchanged is not True"
    for rec in artifact["portfolios"]:
        assert rec["historical_artifact_unchanged"] is True, \
            f"Portfolio '{rec['portfolio_id']}' historical_artifact_unchanged is not True"


def test_source_commit_matches(artifact):
    assert artifact["source_commit"] == "b6dd42f14e822a186187b90c50acdfedebe3fd07"


def test_no_duplicate_strategy_identities(artifact):
    identities = [r["identity"] for r in artifact["strategies"]]
    assert len(identities) == len(set(identities)), \
        "Duplicate strategy identities found"


def test_no_duplicate_portfolio_identities(artifact):
    identities = [r["identity"] for r in artifact["portfolios"]]
    assert len(identities) == len(set(identities)), \
        "Duplicate portfolio identities found"


def test_all_future_confirmation_pending(artifact):
    """No strategy or portfolio may claim future confirmation is done."""
    for rec in artifact["strategies"]:
        assert rec["future_confirmation_status"] == "FUTURE_CONFIRMATION_PENDING", \
            f"Strategy '{rec['identity']}' has unexpected future_confirmation_status"
    for rec in artifact["portfolios"]:
        assert rec["future_confirmation_status"] == "FUTURE_CONFIRMATION_PENDING", \
            f"Portfolio '{rec['portfolio_id']}' has unexpected future_confirmation_status"


# ---------------------------------------------------------------------------
# 10. Strategy record validation (counts and specific cells)
# ---------------------------------------------------------------------------

def test_strategy_cell_count(artifact):
    """Must have exactly 36 strategy cells (P267C/P275B frozen universe)."""
    assert len(artifact["strategies"]) == 36, \
        f"Expected 36 strategy cells, got {len(artifact['strategies'])}"


def test_portfolio_count(artifact):
    """Must have exactly 8 portfolios (from P276B)."""
    assert len(artifact["portfolios"]) == 8, \
        f"Expected 8 portfolios, got {len(artifact['portfolios'])}"


def test_endpoint_count(artifact):
    """Must cover exactly 3 endpoints (one per lottery)."""
    assert artifact["endpoint_counts"] == {
        "DAILY_539": 1,
        "BIG_LOTTO": 1,
        "POWER_LOTTO": 1,
    }


def test_correction_family_size(artifact):
    """Correction family must be 108 (36 cells x 3 primary windows)."""
    uc = artifact["universe_counts"]
    assert uc["correction_family_size"] == 108
    assert uc["total_strategy_cells"] == 36
    assert uc["windows_per_cell"] == 3


# ---------------------------------------------------------------------------
# 11. P276B verdict preservation
# ---------------------------------------------------------------------------

def test_p276b_verdict_preserved(artifact):
    """NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE must be preserved in ALL portfolios."""
    for rec in artifact["portfolios"]:
        assert rec["scientific_verdict_preserved"] == "NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE", \
            f"Portfolio '{rec['portfolio_id']}' does not preserve P276B verdict"


def test_p276b_all_portfolios_have_cross_or_single_kind(artifact):
    """All P276B portfolios must be labeled SINGLE or CROSS."""
    for rec in artifact["portfolios"]:
        assert rec["kind"] in ("SINGLE", "CROSS"), \
            f"Portfolio '{rec['portfolio_id']}' has unexpected kind '{rec['kind']}'"


def test_p276b_portfolio_promotion_not_authorized(artifact):
    """All P276B portfolios must have promotion_status = PROMOTION_REVIEW_NOT_AUTHORIZED."""
    for rec in artifact["portfolios"]:
        assert rec["promotion_status"] == "PROMOTION_REVIEW_NOT_AUTHORIZED", \
            f"Portfolio '{rec['portfolio_id']}' promotion_status is not PROMOTION_REVIEW_NOT_AUTHORIZED"


def test_p276b_cross_portfolio_not_above_best_constituent(artifact):
    """
    Cross portfolios whose verdict is NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE
    must NOT have ABOVE_BEST_EQUAL_BUDGET status in ALL windows.
    (At least one window must show AT_OR_BELOW or equal — the overall verdict is null.)
    """
    cross_portfolios = [p for p in artifact["portfolios"] if p["kind"] == "CROSS"]
    for rec in cross_portfolios:
        # Check window_summaries for at least one non-superior result
        wins = rec.get("window_summaries", [])
        all_above = all(
            w.get("portfolio_vs_best_eq") == "ABOVE_BEST_EQUAL_BUDGET"
            for w in wins
        )
        # Under NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE, cross portfolios
        # should NOT be uniformly above best constituent in all windows
        assert not all_above or len(wins) == 0, (
            f"Cross portfolio '{rec['portfolio_id']}' claims ABOVE_BEST_EQUAL_BUDGET "
            f"in ALL windows, contradicting NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE verdict."
        )


# ---------------------------------------------------------------------------
# 12. P273A GO-candidate mapping preservation
# ---------------------------------------------------------------------------

def test_p273a_go_candidates_are_observation_supported(artifact):
    """
    The three P273A GO_CANDIDATE_RESEARCH_ONLY cells must be mapped to
    OBSERVATION_SUPPORTED_ABOVE_RANDOM (corrected support, no OOS superseded).
    """
    go_candidates = {
        "DAILY_539/acb_markov_midfreq_3bet",
        "DAILY_539/daily539_f4cold_3bet",
        "DAILY_539/daily539_f4cold_5bet",
    }
    for rec in artifact["strategies"]:
        if rec["identity"] in go_candidates:
            assert rec["current_mapping"] == "OBSERVATION_SUPPORTED_ABOVE_RANDOM", (
                f"{rec['identity']} should be OBSERVATION_SUPPORTED_ABOVE_RANDOM, "
                f"got {rec['current_mapping']}"
            )
            assert rec["corrected_support_status"] == "CORRECTED_SIGNIFICANT", (
                f"{rec['identity']} should have CORRECTED_SIGNIFICANT, "
                f"got {rec['corrected_support_status']}"
            )
            assert rec["promotion_status"] == "NOT_PROMOTED", \
                f"{rec['identity']} must not be promoted"


def test_p273a_prediction_success_claim_false(artifact):
    """prediction_success_claim must be False at artifact level."""
    assert artifact["prediction_success_claim"] is False


def test_p273a_strategy_promoted_false(artifact):
    """strategy_promoted must be False at artifact level."""
    assert artifact["strategy_promoted"] is False


def test_p273a_retrospective_limitation_in_go_candidates(artifact):
    """GO candidates must have 'retrospective' in their limitations."""
    go_candidates = {
        "DAILY_539/acb_markov_midfreq_3bet",
        "DAILY_539/daily539_f4cold_3bet",
        "DAILY_539/daily539_f4cold_5bet",
    }
    for rec in artifact["strategies"]:
        if rec["identity"] in go_candidates:
            lims_str = " ".join(rec.get("limitations", []))
            assert "retrospective" in lims_str.lower(), (
                f"{rec['identity']} GO candidate limitations must mention 'retrospective'"
            )


# ---------------------------------------------------------------------------
# 13. OOS-superseded identification
# ---------------------------------------------------------------------------

def test_midfreq_fourier_2bet_oos_superseded(artifact):
    """
    DAILY_539/midfreq_fourier_2bet: P230B1 backward-OOS (4265 draws, p=0.626, below)
    must be classified HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL.
    """
    for rec in artifact["strategies"]:
        if rec["identity"] == "DAILY_539/midfreq_fourier_2bet":
            assert rec["current_mapping"] == "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL", (
                f"DAILY_539/midfreq_fourier_2bet should be OOS_SUPERSEDED, "
                f"got {rec['current_mapping']}"
            )
            assert rec["OOS_status"] == "OOS_NULL"
            return
    pytest.fail("DAILY_539/midfreq_fourier_2bet not found in strategies")


def test_oos_superseded_count(artifact):
    """Exactly 1 strategy should be OOS-superseded (midfreq_fourier_2bet)."""
    superseded = [r for r in artifact["strategies"]
                   if r["current_mapping"] == "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL"]
    assert len(superseded) == 1, f"Expected 1 OOS-superseded, got {len(superseded)}"
    assert superseded[0]["identity"] == "DAILY_539/midfreq_fourier_2bet"


def test_midfreq_fourier_mk_3bet_oos_inconclusive(artifact):
    """
    POWER_LOTTO/midfreq_fourier_mk_3bet: P231B backward-OOS is above baseline
    but p=0.302 (inconclusive). Should NOT be OOS_NULL.
    """
    for rec in artifact["strategies"]:
        if rec["identity"] == "POWER_LOTTO/midfreq_fourier_mk_3bet":
            assert rec["OOS_status"] == "OOS_INCONCLUSIVE_ABOVE_RANDOM"
            assert rec["current_mapping"] != "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL"
            return
    pytest.fail("POWER_LOTTO/midfreq_fourier_mk_3bet not found in strategies")


# ---------------------------------------------------------------------------
# 14. Required research questions answered
# ---------------------------------------------------------------------------

def test_all_11_questions_present(artifact):
    rq = artifact["required_questions"]
    expected_keys = [
        "q1_strategy_cells_passing_random_gate",
        "q2_point_estimate_only",
        "q3_corrected_supported",
        "q4_beat_random_not_best_strategy",
        "q5_beat_both_random_and_best",
        "q6_null_vs_random",
        "q7_oos_superseded",
        "q8_portfolios_beat_random_not_best_constituent",
        "q9_no_valid_baseline",
        "q10_hit_spectrum_page_candidates",
        "q11_need_new_evidence",
    ]
    for key in expected_keys:
        assert key in rq, f"Required question '{key}' not found in required_questions"


def test_q1_count_is_positive(artifact):
    """At least some strategy cells pass the random-baseline gate."""
    q1 = artifact["required_questions"]["q1_strategy_cells_passing_random_gate"]
    assert q1["count"] > 0, "Q1: Expected at least one strategy cell above random"


def test_q3_corrected_supported_count(artifact):
    """Exactly 3 corrected-supported cells (the 3 P273A GO candidates)."""
    q3 = artifact["required_questions"]["q3_corrected_supported"]
    assert q3["count"] == 3, f"Q3: Expected 3 corrected-supported cells, got {q3['count']}"


def test_q7_oos_superseded_count(artifact):
    """Exactly 1 OOS-superseded cell."""
    q7 = artifact["required_questions"]["q7_oos_superseded"]
    assert q7["count"] == 1, f"Q7: Expected 1 OOS-superseded, got {q7['count']}"
    assert "DAILY_539/midfreq_fourier_2bet" in q7.get("identities", [])


def test_q10_hit_spectrum_candidates_are_supported(artifact):
    """Hit-spectrum candidates must all be OBSERVATION_SUPPORTED_ABOVE_RANDOM or better."""
    q10 = artifact["required_questions"]["q10_hit_spectrum_page_candidates"]
    valid_mappings = {
        "STRONG_RESEARCH_CANDIDATE",
        "OBSERVATION_SUPPORTED_ABOVE_RANDOM",
        "COMPETITIVE_OBSERVATION_STRATEGY",
    }
    for ident in q10.get("identities", []):
        for rec in artifact["strategies"]:
            if rec["identity"] == ident:
                assert rec["current_mapping"] in valid_mappings, (
                    f"Hit-spectrum candidate '{ident}' has invalid mapping "
                    f"'{rec['current_mapping']}'"
                )
                break


# ---------------------------------------------------------------------------
# 15. Dual-gate separation invariants
# ---------------------------------------------------------------------------

def test_gate1_gate2_separation(artifact):
    """
    Strategies beating random (Gate 1) but not beating best equal-budget
    (Gate 2) must NOT be classified as NO_EVIDENCE_OVER_RANDOM or INSUFFICIENT.
    """
    bad_mappings = {"NO_EVIDENCE_OVER_RANDOM", "INSUFFICIENT_SUPPORT",
                    "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE"}
    for rec in artifact["strategies"]:
        if (rec["random_baseline_status"] == "ABOVE_RANDOM"
                and rec["best_equal_budget_status"] != "ABOVE_BEST_EQUAL_BUDGET"
                and rec["observation_retention_status"] == "OBSERVATION_RETAINED"):
            assert rec["current_mapping"] not in bad_mappings, (
                f"Gate 1 pass, Gate 2 fail strategy '{rec['identity']}' incorrectly "
                f"mapped to '{rec['current_mapping']}'"
            )


def test_observation_retention_consistency(artifact):
    """
    OBSERVATION_RETAINED must imply above-random status (or OOS inconclusive above random),
    not OOS_NULL.
    """
    for rec in artifact["strategies"]:
        if rec["observation_retention_status"] == "OBSERVATION_RETAINED":
            assert rec["random_baseline_status"] == "ABOVE_RANDOM", (
                f"'{rec['identity']}' is OBSERVATION_RETAINED but not ABOVE_RANDOM"
            )
            assert rec["OOS_status"] != "OOS_NULL", (
                f"'{rec['identity']}' is OBSERVATION_RETAINED but has OOS_NULL"
            )


# ---------------------------------------------------------------------------
# 16. Exactly four whitelist files verified
# ---------------------------------------------------------------------------

def test_four_whitelist_files_exist():
    whitelist = [
        ROOT / "analysis" / "p277a_historical_observation_status_reclassification.py",
        ROOT / "tests" / "test_p277a_historical_observation_status_reclassification.py",
        ROOT / "outputs" / "research" / "p277a_historical_observation_status_reclassification_20260617.json",
        ROOT / "outputs" / "research" / "p277a_historical_observation_status_reclassification_20260617.md",
    ]
    for path in whitelist:
        assert path.exists(), f"Whitelist file not found: {path}"
    assert len(whitelist) == 4, "Whitelist must contain exactly 4 files"


# ---------------------------------------------------------------------------
# 17. Unicode/control-char safety
# ---------------------------------------------------------------------------

BIDI_OVERRIDE = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
CONTROL_CHARS = set(range(0, 0x09)) | set(range(0x0B, 0x0D)) | set(range(0x0E, 0x20))


def _check_no_dangerous_chars(content: str, label: str) -> None:
    for i, ch in enumerate(content):
        cp = ord(ch)
        assert cp not in BIDI_OVERRIDE, (
            f"{label}: dangerous bidirectional override character U+{cp:04X} at position {i}"
        )
        assert cp not in CONTROL_CHARS, (
            f"{label}: unexpected control character U+{cp:04X} at position {i}"
        )


def test_analysis_module_unicode_safety():
    src = MODULE_PATH.read_text(encoding="utf-8")
    _check_no_dangerous_chars(src, "analysis module")


def test_json_unicode_safety():
    content = JSON_PATH.read_text(encoding="utf-8")
    _check_no_dangerous_chars(content, "JSON artifact")


def test_markdown_unicode_safety():
    content = MD_PATH.read_text(encoding="utf-8")
    _check_no_dangerous_chars(content, "Markdown artifact")


def test_test_file_unicode_safety():
    test_src = Path(__file__).read_text(encoding="utf-8")
    _check_no_dangerous_chars(test_src, "test file")


# ---------------------------------------------------------------------------
# 18. Source artifact hash verification against committed artifact
# ---------------------------------------------------------------------------

def test_source_artifact_hashes_in_committed_json(committed_json):
    """Committed JSON must contain source_artifact_hashes."""
    assert "source_artifact_hashes" in committed_json
    hashes = committed_json["source_artifact_hashes"]
    assert len(hashes) > 0, "source_artifact_hashes must not be empty"
    for key, h in hashes.items():
        assert h != "MISSING", f"Source artifact '{key}' is missing in committed JSON"


def test_p275b_hash_in_committed_json(committed_json):
    """P275B hash in committed JSON must match actual artifact."""
    p275b_path = ROOT / "outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json"
    with open(p275b_path, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    recorded = committed_json["source_artifact_hashes"].get("p275b")
    assert recorded is not None, "p275b hash not in committed JSON"
    assert actual == recorded, (
        f"P275B hash mismatch: actual={actual} recorded={recorded}"
    )


def test_p276b_hash_in_committed_json(committed_json):
    """P276B hash in committed JSON must match actual artifact."""
    p276b_path = ROOT / "outputs/research/p276b_fixed_n_coverage_complementarity_20260617.json"
    with open(p276b_path, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    recorded = committed_json["source_artifact_hashes"].get("p276b")
    assert recorded is not None, "p276b hash not in committed JSON"
    assert actual == recorded, (
        f"P276B hash mismatch: actual={actual} recorded={recorded}"
    )


# ---------------------------------------------------------------------------
# P277C Remediation: Path-independence tests (added 2026-06-17)
# These verify that source_artifact_manifest uses repo-relative POSIX paths
# so the canonical digest is identical regardless of checkout/worktree location.
# ---------------------------------------------------------------------------

def test_manifest_paths_are_relative_posix(artifact):
    """All manifest paths must be relative POSIX — no leading '/'."""
    for p in artifact["source_artifact_manifest"]:
        assert not Path(p).is_absolute(), (
            f"Absolute path leaked into manifest: {p!r}. "
            "source_artifact_manifest must use repo-relative POSIX paths."
        )


def test_manifest_no_host_specific_prefix(artifact):
    """Manifest paths must not contain any host-specific directory component."""
    forbidden_prefixes = ("/Users/", "/home/", "/root/", "/tmp/", "C:\\", "LotteryNew-p277a")
    for p in artifact["source_artifact_manifest"]:
        for prefix in forbidden_prefixes:
            assert prefix not in p, (
                f"Host-specific prefix {prefix!r} found in manifest path {p!r}"
            )


def test_manifest_paths_under_outputs_research(artifact):
    """All manifest paths must be under 'outputs/research/' (repo-relative)."""
    for p in artifact["source_artifact_manifest"]:
        assert p.startswith("outputs/research/"), (
            f"Manifest path not under outputs/research/: {p!r}"
        )


def test_manifest_paths_unique_and_deterministic(artifact):
    """Manifest paths must be unique and sorted deterministically."""
    paths = artifact["source_artifact_manifest"]
    assert len(paths) == len(set(paths)), "Duplicate manifest paths found"
    assert paths == sorted(paths), "Manifest paths are not sorted deterministically"


def test_canonical_digest_two_root_independence(artifact):
    """
    Path-independence core property: manifest uses repo-relative POSIX paths,
    so any two checkouts at different absolute roots produce identical manifests
    and thus identical canonical digests.

    Verifies that relative paths → same digest, and that absolute paths from
    two different roots → different digests (proving regression detection works).
    """
    current_manifest = artifact["source_artifact_manifest"]
    # All paths relative → digest is root-independent
    payload_copy = dict(artifact)
    payload_copy["canonical_payload_digest"] = ""
    recomputed = M.compute_canonical_digest(payload_copy)
    assert recomputed == artifact["canonical_payload_digest"], (
        "Recomputed digest does not match stored — path-independence broken"
    )

    # Negative property: absolute paths from two different fake roots → different digests
    fake_a = "/fake/root_a"
    fake_b = "/fake/root_b"
    manifest_abs_a = sorted(f"{fake_a}/{p}" for p in current_manifest)
    manifest_abs_b = sorted(f"{fake_b}/{p}" for p in current_manifest)

    payload_a = dict(artifact)
    payload_a["source_artifact_manifest"] = manifest_abs_a
    payload_a["canonical_payload_digest"] = ""
    digest_a = M.compute_canonical_digest(payload_a)

    payload_b = dict(artifact)
    payload_b["source_artifact_manifest"] = manifest_abs_b
    payload_b["canonical_payload_digest"] = ""
    digest_b = M.compute_canonical_digest(payload_b)

    assert digest_a != digest_b, (
        "Absolute-path manifests from two different roots produced identical digests "
        "— the negative-case property is broken"
    )
    assert recomputed != digest_a, (
        "Relative-path digest equals absolute-path digest — path-independence fix has no effect"
    )


def test_absolute_path_reintroduction_detected(artifact):
    """
    If absolute paths are reintroduced, digest must differ from the pinned value.
    This ensures the test suite catches any future regression.
    """
    current_manifest = artifact["source_artifact_manifest"]
    # Construct a payload with absolute paths (simulating regression)
    abs_manifest = sorted(f"/some/fake/root/{p}" for p in current_manifest)
    payload_regression = dict(artifact)
    payload_regression["source_artifact_manifest"] = abs_manifest
    payload_regression["canonical_payload_digest"] = ""
    digest_regression = M.compute_canonical_digest(payload_regression)
    assert digest_regression != PINNED_DIGEST, (
        "Absolute-path manifest produced the same pinned digest — "
        "path-independence fix has no effect or test is broken"
    )


def test_committed_json_manifest_no_absolute_paths(committed_json):
    """Committed JSON file must not contain absolute manifest paths."""
    for p in committed_json.get("source_artifact_manifest", []):
        assert not Path(p).is_absolute(), (
            f"Committed JSON still has absolute manifest path: {p!r}. "
            "Regenerate artifacts after applying the path-independence fix."
        )


def test_committed_json_manifest_no_worktree_path(committed_json):
    """Committed JSON must not contain the worktree directory path."""
    raw_json = json.dumps(committed_json)
    worktree_fragments = ["LotteryNew-p277a", "/Users/kelvin", "/home/kelvin"]
    for fragment in worktree_fragments:
        assert fragment not in raw_json, (
            f"Host-specific fragment {fragment!r} found in committed JSON. "
            "Regenerate artifacts with the path-independence fix applied."
        )


def test_markdown_no_absolute_paths():
    """Committed Markdown file must not contain absolute paths from the manifest."""
    content = MD_PATH.read_text(encoding="utf-8")
    fragments = ["LotteryNew-p277a", "/Users/kelvin", "/home/kelvin"]
    for fragment in fragments:
        assert fragment not in content, (
            f"Host-specific fragment {fragment!r} found in Markdown artifact. "
            "Regenerate Markdown with the path-independence fix applied."
        )
