"""Tests for P268B drawNumberAppear ingestion + positional-bias audit prototype.

These tests check the produced artifact (read-only). They do not re-fetch
external data and do not write to the production DB.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p268b_official_draw_order_positional_bias_audit_20260610.json"
SCRIPT_PATH = REPO_ROOT / "analysis" / "p268b_official_draw_order_positional_bias_audit.py"

ALLOWED_FINAL_CLASSIFICATIONS = {
    "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_COMPLETE_DIAGNOSTICS_ONLY",
    "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_BLOCKED_STATE_MISMATCH",
    "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_BLOCKED_EXTERNAL_API_UNAVAILABLE",
    "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_BLOCKED_SCHEMA_MISMATCH",
    "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_BLOCKED_SCOPE_CONFLICT",
}

# Phrases that would indicate banned betting-recommendation language.
BANNED_PATTERNS = [
    r"建議下注",
    r"建議購買",
    r"推薦號碼",
    r"買.*注",
    r"\bbet\b",
    r"\bwager\b",
    r"recommended numbers",
    r"buy ticket",
]


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_JSON.exists(), f"Artifact not found: {ARTIFACT_JSON}"
    with open(ARTIFACT_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def test_artifact_exists_and_valid_json(artifact):
    assert isinstance(artifact, dict)
    assert artifact.get("task_id") == "P268B_OFFICIAL_DRAW_ORDER_INGESTION_AND_POSITIONAL_BIAS_AUDIT_PROTOTYPE"


def test_p267c_boundary_present(artifact):
    boundary = artifact.get("p267c_conclusion_boundary", "")
    assert "P267C" in boundary
    assert "NO_VALIDATED_M3_EDGE" in boundary or "no_validated_m3_edge" in boundary.lower()


def test_draw_number_appear_explicitly_represented(artifact):
    # Field must be referenced in rationale and in per-game parse results.
    assert "drawNumberAppear" in artifact.get("p268a_top1_rationale", "")
    parse_results = artifact.get("parse_results", {})
    assert parse_results, "parse_results must be non-empty"
    for lottery_type, pr in parse_results.items():
        assert "drawNumberAppear_present" in pr, f"{lottery_type} missing drawNumberAppear_present"


def test_no_production_db_write_in_script():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    # Script must not open the DB in a writable mode.
    assert "mode=ro" in source, "DB must be opened read-only (mode=ro)"
    # Disallow common write-triggering SQL/connection patterns.
    forbidden = ["INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE", "ALTER TABLE"]
    for token in forbidden:
        assert token not in source, f"Forbidden DB-write token found in script: {token!r}"


def test_sample_scope_is_bounded(artifact):
    scope = artifact.get("sample_scope", {})
    months = scope.get("months_sampled", [])
    assert isinstance(months, list)
    assert 1 <= len(months) <= 3, "sample scope must be a small bounded window, not full history"
    games = scope.get("games_sampled", [])
    assert len(games) >= 1


def test_no_banned_betting_recommendation_language(artifact):
    text_blob = json.dumps(artifact, ensure_ascii=False)
    for pattern in BANNED_PATTERNS:
        assert not re.search(pattern, text_blob, flags=re.IGNORECASE), (
            f"Banned betting-recommendation pattern found: {pattern!r}"
        )


def test_disclaimer_present(artifact):
    disclaimer = artifact.get("disclaimer", "")
    assert "DIAGNOSTICS ONLY" in disclaimer
    assert "betting" in disclaimer.lower()
    assert "no validated" in disclaimer.lower() or "NO_VALIDATED" in disclaimer


def test_final_classification_is_allowed(artifact):
    final_classification = artifact.get("final_classification")
    assert final_classification in ALLOWED_FINAL_CLASSIFICATIONS


def test_no_hit_rate_improvement_claim(artifact):
    text_blob = json.dumps(artifact, ensure_ascii=False).lower()
    banned_claims = [
        "hit-rate improved",
        "hit rate improved",
        "success rate improved",
        "validated edge",
        "proven edge",
    ]
    for claim in banned_claims:
        assert claim not in text_blob, f"Banned hit-rate claim found: {claim!r}"
