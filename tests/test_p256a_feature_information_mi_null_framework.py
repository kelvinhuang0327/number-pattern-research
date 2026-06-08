"""Tests for P256A — Feature-Information MI Null-Framework Assessment.

Read-only artifact validation tests.
No DB write, no registry mutation, no strategy promotion, no betting advice.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Artifact path
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p256a_feature_information_mi_null_framework_20260608.json"
ARTIFACT_MD   = REPO_ROOT / "outputs" / "research" / "p256a_feature_information_mi_null_framework_20260608.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_JSON.exists(), f"Artifact missing: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text() -> str:
    assert ARTIFACT_MD.exists(), f"Markdown missing: {ARTIFACT_MD}"
    return ARTIFACT_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. JSON parses and top-level structure
# ---------------------------------------------------------------------------

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_task_id(artifact):
    assert artifact["task_id"] == "P256A"


def test_classification_exists(artifact):
    assert "classification" in artifact
    assert artifact["classification"]


def test_schema_version(artifact):
    assert "schema_version" in artifact


# ---------------------------------------------------------------------------
# 2. Pre-registration declared before results
# ---------------------------------------------------------------------------

def test_pre_registration_exists(artifact):
    assert "pre_registration" in artifact


def test_pre_registration_before_results_in_key_order(artifact):
    """pre_registration must appear before per_lottery_results in JSON key order."""
    keys = list(artifact.keys())
    pr_idx = keys.index("pre_registration")
    results_idx = keys.index("per_lottery_results")
    assert pr_idx < results_idx, (
        f"pre_registration (pos {pr_idx}) must precede per_lottery_results (pos {results_idx})"
    )


def test_feature_vocabulary_declared(artifact):
    pr = artifact["pre_registration"]
    assert "feature_vocabulary" in pr
    vocab = pr["feature_vocabulary"]
    assert isinstance(vocab, list)
    assert len(vocab) >= 4
    # Must include these mandatory concepts
    vocab_str = " ".join(vocab)
    for expected in ("number_frequency", "sequence_lag_mi", "feature_to_hit_mi", "blocking_factor"):
        assert expected in vocab_str, f"Missing vocab concept: {expected}"


def test_family_size_declared(artifact):
    pr = artifact["pre_registration"]
    assert "family_size" in pr
    assert isinstance(pr["family_size"], int)
    assert pr["family_size"] > 0


def test_windows_declared(artifact):
    pr = artifact["pre_registration"]
    assert "windows_short" in pr
    assert "windows_mid" in pr
    assert pr["windows_short"] == [100, 125, 150]
    assert pr["windows_mid"] == [500, 750, 1000]


def test_acceptance_taxonomy_declared(artifact):
    pr = artifact["pre_registration"]
    assert "acceptance_taxonomy" in pr
    taxonomy = pr["acceptance_taxonomy"]
    for required in (
        "NULL_OR_BASELINE_LIKE",
        "UNDERPOWERED_NO_SIGNAL",
        "EXPLORATORY_WEAK_UNCONFIRMED",
        "SURVIVOR_NEEDS_P221F_OOS",
    ):
        assert required in taxonomy, f"Missing taxonomy class: {required}"


def test_strict_gate_is_bonferroni(artifact):
    pr = artifact["pre_registration"]
    assert "strict_gate" in pr
    assert "bonferroni" in pr["strict_gate"].lower()


def test_exploratory_gate_is_bh_fdr(artifact):
    pr = artifact["pre_registration"]
    assert "exploratory_gate" in pr
    assert "bh" in pr["exploratory_gate"].lower() or "fdr" in pr["exploratory_gate"].lower()


# ---------------------------------------------------------------------------
# 3. Null specification — L96 binding
# ---------------------------------------------------------------------------

def test_null_spec_uses_monte_carlo_binomial(artifact):
    pr = artifact["pre_registration"]
    ns = pr["null_spec"]
    method = ns["method"].lower()
    assert "monte" in method or "binomial" in method or "mc" in method, (
        f"null_spec.method must reference Monte-Carlo/Binomial, got: {ns['method']!r}"
    )


def test_null_spec_forbids_label_shuffle(artifact):
    pr = artifact["pre_registration"]
    ns = pr["null_spec"]
    assert ns.get("label_shuffle_forbidden") is True, (
        "null_spec.label_shuffle_forbidden must be True (L96 binding)"
    )
    # Must also have a reason string
    reason = ns.get("label_shuffle_forbidden_reason", "")
    assert len(reason) > 10, "label_shuffle_forbidden_reason must be substantive"


def test_seed_declared(artifact):
    pr = artifact["pre_registration"]
    assert "seed" in pr
    assert isinstance(pr["seed"], int)


# ---------------------------------------------------------------------------
# 4. Correction applied
# ---------------------------------------------------------------------------

def test_correction_summary_exists(artifact):
    assert "correction_summary" in artifact


def test_bonferroni_applied(artifact):
    cs = artifact["correction_summary"]
    assert "bonferroni" in cs, "correction_summary must include bonferroni key"


def test_bh_fdr_is_exploratory_only(artifact):
    cs = artifact["correction_summary"]
    assert "bh_fdr" in cs, "correction_summary must include bh_fdr key"
    # The artifact family_size_declared should match pre_registration
    pr_family = artifact["pre_registration"]["family_size"]
    cs_family = cs.get("family_size_declared", pr_family)
    assert cs_family == pr_family, (
        f"correction_summary family_size_declared ({cs_family}) != pre_registration family_size ({pr_family})"
    )


def test_no_edge_claim_in_correction(artifact):
    cs = artifact["correction_summary"]
    assert cs.get("no_edge_claim") is True


# ---------------------------------------------------------------------------
# 5. Baseline values
# ---------------------------------------------------------------------------

def test_current_accepted_baseline_exists(artifact):
    assert "current_accepted_baseline" in artifact
    cab = artifact["current_accepted_baseline"]
    assert cab["BIG_LOTTO_raw"] == 22239
    assert cab["BIG_LOTTO_canonical"] == 2114
    assert cab["POWER_LOTTO"] == 1917
    assert cab["DAILY_539"] == 5882
    assert cab["3_STAR"] == 5850
    assert cab["4_STAR"] == 5850
    assert cab["strategy_prediction_replays"] == 94924


def test_phase0_baseline_matches(artifact):
    p0 = artifact["phase0_summary"]
    assert p0["BIG_LOTTO_raw"] == 22239
    assert p0["BIG_LOTTO_canonical"] == 2114


# ---------------------------------------------------------------------------
# 6. No-* governance flags all True
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", [
    "no_db_write_confirmed",
    "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed",
    "no_betting_advice_confirmed",
    "no_production_write_confirmed",
])
def test_no_flags_all_true(artifact, flag):
    assert artifact.get(flag) is True, f"Flag {flag!r} must be True"


# ---------------------------------------------------------------------------
# 7. Final decision is HOLD-class or exactly one P221F+OOS follow-up
# ---------------------------------------------------------------------------

VALID_FINAL_DECISIONS = {
    "HOLD_NULL_RESULT",
    "HOLD_UNDERPOWERED_NO_SIGNAL",
    "SURVIVOR_NEEDS_P221F_OOS",
}


def test_final_decision_valid(artifact):
    fd = artifact["final_decision"]
    assert fd in VALID_FINAL_DECISIONS, (
        f"final_decision must be one of {VALID_FINAL_DECISIONS}, got {fd!r}"
    )


def test_survivor_has_single_follow_up(artifact):
    """If SURVIVOR, exactly one follow-up task must be named."""
    if artifact["final_decision"] == "SURVIVOR_NEEDS_P221F_OOS":
        follow_up = artifact.get("follow_up_task")
        assert follow_up is not None
        assert len(str(follow_up)) > 3
    else:
        # HOLD: follow_up may be None or absent
        follow_up = artifact.get("follow_up_task")
        assert follow_up is None or follow_up == "" or isinstance(follow_up, type(None))


# ---------------------------------------------------------------------------
# 8. No strategy promotion or betting advice language in artifact JSON
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES = [
    "deployable strategy",
    "production strategy",
    "betting advice",
    "buy tickets",
    "guaranteed win",
    "increase win rate",
    "predict winning",
    "promotion approved",
]


def test_no_strategy_promotion_language(artifact):
    artifact_str = json.dumps(artifact).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in artifact_str, (
            f"Forbidden phrase found in artifact: {phrase!r}"
        )


def test_no_betting_advice_in_markdown(md_text):
    # Check for actual betting-advice *claims* (not the explicit prohibition disclaimers)
    lower = md_text.lower()
    for phrase in ("buy tickets", "guaranteed win", "predict winning numbers"):
        assert phrase not in lower, f"Forbidden phrase in markdown: {phrase!r}"
    # "betting advice" is allowed only as a prohibition/disclaimer, never as a recommendation
    # Check it doesn't appear in a positive recommendation context
    for line in lower.splitlines():
        if "betting advice" in line:
            # Acceptable: appears in prohibition phrases ("no betting advice", "must not be used", "not betting advice")
            assert any(neg in line for neg in ("no ", "not ", "must not", "never", "explicit non")), (
                f"'betting advice' found outside a prohibition context: {line!r}"
            )


# ---------------------------------------------------------------------------
# 9. Per-lottery results structure
# ---------------------------------------------------------------------------

def test_per_lottery_results_exist(artifact):
    assert "per_lottery_results" in artifact
    results = artifact["per_lottery_results"]
    assert isinstance(results, list)
    assert len(results) >= 3  # BIG_LOTTO, DAILY_539, POWER_LOTTO at minimum


def test_each_lottery_has_classification(artifact):
    for lot in artifact["per_lottery_results"]:
        assert "classification" in lot, f"Lottery {lot.get('lottery')} missing classification"
        assert lot["classification"] in {
            "NULL_OR_BASELINE_LIKE",
            "UNDERPOWERED_NO_SIGNAL",
            "EXPLORATORY_WEAK_UNCONFIRMED",
            "SURVIVOR_NEEDS_P221F_OOS",
        }


def test_star_lotteries_marked_underpowered(artifact):
    lot_map = {r["lottery"]: r for r in artifact["per_lottery_results"]}
    for label in ("3_STAR", "4_STAR"):
        lot = lot_map.get(label)
        assert lot is not None, f"Missing lottery entry for {label}"
        assert lot["classification"] == "UNDERPOWERED_NO_SIGNAL", (
            f"{label} should be UNDERPOWERED_NO_SIGNAL"
        )


# ---------------------------------------------------------------------------
# 10. Measurability map exists
# ---------------------------------------------------------------------------

def test_measurability_map_exists(artifact):
    assert "measurability_map" in artifact
    mm = artifact["measurability_map"]
    assert isinstance(mm, list)
    assert len(mm) >= 5


def test_position_frequency_blocked_for_sorted_lotteries(artifact):
    """Position frequency must be marked BLOCKED for BIG_LOTTO/DAILY_539/POWER_LOTTO."""
    blocked = [
        e for e in artifact["measurability_map"]
        if e.get("feature") == "position_frequency" and e.get("status") == "BLOCKED"
    ]
    assert len(blocked) >= 3, (
        "position_frequency should be BLOCKED for at least 3 sorted-storage lotteries"
    )
