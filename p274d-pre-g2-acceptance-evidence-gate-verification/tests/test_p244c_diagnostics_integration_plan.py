"""
Targeted tests for P244C Diagnostics Integration Plan artifacts.
No DB access. No production side effects.
"""
import json
import os
import pytest

JSON_PATH = "outputs/research/p244c_diagnostics_integration_plan_20260605.json"
MD_PATH = "outputs/research/p244c_diagnostics_integration_plan_20260605.md"

REQUIRED_CONFIDENCE_TEMPLATES = [
    "OBSERVATION_ONLY",
    "NULL_NO_EDGE",
    "UNDERPOWERED_NO_SIGNAL",
    "WAIT_FOR_OOS_GATE_NOT_OPEN",
]

REQUIRED_FORBIDDEN_CLAIMS = [
    "betting advice",
    "improved win rate",
    "production-ready",
    "recommended numbers",
]

REQUIRED_BLOCKERS = [
    "P221F_GATE_NOT_PASSED",
    "SAMPLE_TOO_SMALL",
    "MULTIPLE_TESTING_NOT_CORRECTED",
    "ROBUSTNESS_FAILED",
    "P211_HELD_BY_USER",
]

REQUIRED_CHECKPOINT_KEYS = [
    "Phase_0_verification",
    "pre_registration",
    "multiple_testing",
    "robustness",
    "feature_bottleneck",
    "allowed_forbidden_next_action",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_exists():
    assert os.path.exists(JSON_PATH)


def test_markdown_exists():
    assert os.path.exists(MD_PATH)


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# ---------------------------------------------------------------------------
# Classification and type
# ---------------------------------------------------------------------------

def test_classification(artifact):
    assert artifact["classification"] == "P244C_DIAGNOSTICS_INTEGRATION_PLAN_COMPLETE"


def test_task_type_is_b(artifact):
    assert artifact["task_type"] == "Type B"


# ---------------------------------------------------------------------------
# No-claim booleans
# ---------------------------------------------------------------------------

def test_no_code_changes(artifact):
    assert artifact["no_code_changes"] is True


def test_no_db_write(artifact):
    assert artifact["no_db_write"] is True


def test_no_registry_mutation(artifact):
    assert artifact["no_registry_mutation"] is True


def test_no_production_change(artifact):
    assert artifact["no_production_change"] is True


def test_no_monitoring_change(artifact):
    assert artifact["no_monitoring_change"] is True


def test_no_strategy_authorization(artifact):
    assert artifact["no_strategy_authorization"] is True


def test_no_betting_advice(artifact):
    assert artifact["no_betting_advice"] is True


def test_p211_not_restarted(artifact):
    assert artifact["p211_restarted"] is False


def test_p238b_interpretation(artifact):
    assert "YELLOW" in artifact["p238b_interpretation"]


def test_prompt_snippet_included(artifact):
    assert artifact["prompt_snippet_included"] is True


def test_same_pr_closeout(artifact):
    assert artifact["same_pr_closeout"] is True


def test_no_separate_closeout(artifact):
    assert artifact["separate_closeout_pr_required"] is False


# ---------------------------------------------------------------------------
# Confidence templates
# ---------------------------------------------------------------------------

def test_confidence_templates_present(artifact):
    templates = artifact.get("confidence_templates", [])
    for t in REQUIRED_CONFIDENCE_TEMPLATES:
        assert t in templates, f"Missing confidence template: {t}"


# ---------------------------------------------------------------------------
# Forbidden claim types
# ---------------------------------------------------------------------------

def test_forbidden_claims_present(artifact):
    claims = artifact.get("forbidden_claim_types", [])
    for c in REQUIRED_FORBIDDEN_CLAIMS:
        assert any(c.lower() in item.lower() for item in claims), (
            f"Missing forbidden claim type: {c}"
        )


# ---------------------------------------------------------------------------
# Blocker vocabulary
# ---------------------------------------------------------------------------

def test_blocker_vocabulary_present(artifact):
    vocab = artifact.get("blocker_vocabulary", [])
    for b in REQUIRED_BLOCKERS:
        assert b in vocab, f"Missing blocker: {b}"


# ---------------------------------------------------------------------------
# Schema to research checkpoint map
# ---------------------------------------------------------------------------

def test_checkpoint_map_keys(artifact):
    mapping = artifact.get("schema_to_research_checkpoint_map", {})
    for key in REQUIRED_CHECKPOINT_KEYS:
        assert key in mapping, f"Missing checkpoint key: {key}"
        assert len(mapping[key]) >= 1


# ---------------------------------------------------------------------------
# Required before claim fields
# ---------------------------------------------------------------------------

def test_required_before_claim_nonempty(artifact):
    fields = artifact.get("required_before_claim_fields", [])
    assert len(fields) >= 10
    for f in ("p_value_raw", "correction_method", "is_corrected_significant",
               "robustness_sign_stable", "feature_bottleneck", "classification"):
        assert f in fields, f"Missing required-before-claim field: {f}"


# ---------------------------------------------------------------------------
# Markdown content checks
# ---------------------------------------------------------------------------

def test_markdown_no_code_changes(md_content):
    lower = md_content.lower()
    assert "no code changes" in lower or "no code change" in lower


def test_markdown_no_db_write(md_content):
    lower = md_content.lower()
    assert "no db write" in lower or "db_write_authorized" in lower


def test_markdown_no_registry(md_content):
    assert "registry mutation" in md_content.lower()


def test_markdown_no_production(md_content):
    assert "no production" in md_content.lower() or "production" in md_content.lower()


def test_markdown_no_strategy_promotion(md_content):
    assert "strategy promotion" in md_content.lower() or "no strategy" in md_content.lower()


def test_markdown_no_p211_restart(md_content):
    lower = md_content.lower()
    assert "p211 remains held" in lower or "p211 remains held_by_user" in lower or "does not restart p211" in lower or "not restart p211" in lower


def test_markdown_p211_requires_explicit_authorization(md_content):
    assert "Start P211" in md_content


def test_markdown_no_betting_advice(md_content):
    assert "betting advice" in md_content.lower()


def test_markdown_has_prompt_snippet(md_content):
    assert "build_diagnostic_report" in md_content
    assert "validate_diagnostic_report" in md_content


def test_markdown_confidence_templates(md_content):
    lower = md_content.lower()
    for t in ("observation_only", "null", "underpowered", "wait_for_oos"):
        assert t.lower() in lower, f"Missing confidence template section: {t}"


def test_markdown_type_b(md_content):
    assert "Type B" in md_content


def test_markdown_no_separate_closeout(md_content):
    lower = md_content.lower()
    assert "no separate" in lower or "same-pr" in lower or "same pr" in lower
