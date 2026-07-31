"""
P243A Diagnostic Report Fixture Pack.

Applies the P242 schema module to 4 historical completed cases.
All fixture data is sourced from actual project governance/artifact evidence.
No DB access. No production side effects. No invented results.

Evidence sources:
  F1 — P238B NIST YELLOW: outputs/research/p238b_nist_randomness_audit_artifact_20260604.json
  F2 — P231B POWER_LOTTO NULL: CURRENT_STATE.md / roadmap.md P231B confirmed line
  F3 — P227C 3_STAR/4_STAR UNDERPOWERED: CURRENT_STATE.md P227C confirmed line
  F4 — P230C DAILY_539 REJECTED: CURRENT_STATE.md P230C confirmed line
"""
import json
import os
import pytest

from lottery_api.diagnostics.statistical_diagnostics_schema import (
    REQUIRED_SCHEMA_FIELDS,
    LotteryType,
    LifecycleStatus,
    CorrectionMethod,
    PsiStatus,
    NistAlertLevel,
    DriftGuardResult,
    build_diagnostic_report,
    validate_diagnostic_report,
    classify_nist_alert,
    default_safety_fields,
)

JSON_PATH = "outputs/research/p243a_diagnostic_report_fixture_pack_20260605.json"
MD_PATH = "outputs/research/p243a_diagnostic_report_fixture_pack_20260605.md"

# ---------------------------------------------------------------------------
# Fixtures: evidenced-only historical cases
# ---------------------------------------------------------------------------

def make_f1_nist_yellow():
    """
    F1: P238B NIST Randomness Audit — YELLOW observation-only.

    Evidence: outputs/research/p238b_nist_randomness_audit_artifact_20260604.json
    - classification: RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY
    - 3 YELLOW alerts across BIG_LOTTO frequency / serial tests
    - predictability_claim: False
    - betting_advice: False
    - strategy_authorized: False
    - Governance: observation-only; no strategy, production, or DB write authorized
    """
    return build_diagnostic_report(
        task_id="P238B",
        report_date="2026-06-04",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id=None,
        diagnostic_subject="NIST-style randomness audit — draw sequence",
        lifecycle_status=LifecycleStatus.OBSERVATION,
        # P246I NOTE: sample_size=22238 = all BIG_LOTTO rows at P238B run time (2026-06-04),
        # including 19,100 ADD_ON_PRIZE_EXCLUDED add-on/special prize records (valid but
        # excluded from canonical 6/49 research). Canonical research population ~2,113.
        # This fixture preserves the historical P238B state. Do not change the value;
        # a canonical-population re-run requires separate authorization. See P246I.
        sample_size=22238,  # historical: raw total (add-on-inclusive); canonical ~2,113
        window_definition="all_history",
        is_oos=False,
        split_boundary=None,
        family_size_k=3,
        baseline_method="theoretical_uniform",
        baseline_value=None,
        observed_metric=None,
        delta_vs_baseline=None,
        n_blocks=None,
        blocks_above_baseline=None,
        p_value_raw=0.0,
        correction_method=CorrectionMethod.BONFERRONI,
        corrected_threshold=0.05,
        is_corrected_significant=True,
        mc_null_99th_pct=None,
        is_above_mc_noise_floor=None,
        robustness_check_description="Historical anomaly capped at YELLOW; ORANGE/RED require independent confirmation",
        robustness_metric=None,
        robustness_sign_stable=None,
        drift_guard_result=DriftGuardResult.NOT_RUN,
        psi_value=None,
        psi_status=PsiStatus.NOT_RUN,
        feature_bottleneck="randomness_observation_only",
        min_detectable_effect=None,
        power_at_observed_effect=None,
        overfit_ratio=None,
        classification="RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY",
        blocker_classification="NIST_YELLOW_OBSERVATION_ONLY_NO_STRATEGY_AUTHORIZED",
        allowed_next_action=[
            "observation_only",
            "future_confirmation_design_with_explicit_authorization",
        ],
        forbidden_next_action=[
            "strategy_promotion",
            "production_change",
            "betting_advice",
            "db_write",
            "registry_write",
            "p211_restart_based_on_nist_result",
        ],
        confidence_language=(
            "NIST YELLOW is observation-only. Historical anomalies capped at YELLOW. "
            "Does not constitute a predictability claim or win-rate claim. "
            "ORANGE/RED require independent future confirmation. "
            "RED authorizes human diagnostic review only. No wagering recommendation."
        ),
        human_review_required=False,
        nist_alert_level=NistAlertLevel.YELLOW,
    )


def make_f2_power_lotto_null():
    """
    F2: P231B POWER_LOTTO first-zone backward-OOS NULL.

    Evidence: CURRENT_STATE.md P231B confirmed line:
    - strategy: midfreq_fourier_mk_3bet / POWER_LOTTO
    - 382 draws (2008–2012), bet-1 only
    - mean 0.96859 vs baseline 0.94737
    - CI crosses baseline; p=0.3018
    - both robustness checks fail; block stability mixed
    - classification: P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL
    """
    return build_diagnostic_report(
        task_id="P231B",
        report_date="2026-06-04",
        lottery_type=LotteryType.POWER_LOTTO,
        strategy_id="midfreq_fourier_mk_3bet",
        diagnostic_subject="POWER_LOTTO first-zone backward-OOS dry-run — bet_index=1",
        lifecycle_status=LifecycleStatus.OBSERVATION,
        sample_size=382,
        window_definition="backward_oos_382_draws_2008_2012",
        is_oos=True,
        split_boundary="101000002",
        family_size_k=1,
        baseline_method="empirical_full",
        baseline_value=0.94737,
        observed_metric=0.96859,
        delta_vs_baseline=0.02122,
        n_blocks=5,
        blocks_above_baseline=3,
        p_value_raw=0.3018,
        correction_method=CorrectionMethod.NONE,
        corrected_threshold=0.05,
        is_corrected_significant=False,
        mc_null_99th_pct=None,
        is_above_mc_noise_floor=None,
        robustness_check_description="exclude hit>=3 rows; exclude strongest block",
        robustness_metric=0.9113,
        robustness_sign_stable=False,
        drift_guard_result=DriftGuardResult.PASS,
        psi_value=None,
        psi_status=PsiStatus.NOT_RUN,
        feature_bottleneck="backward_oos_not_confirmed_robustness_failed",
        min_detectable_effect=None,
        power_at_observed_effect=None,
        overfit_ratio=None,
        classification="P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL",
        blocker_classification="P221F_OOS_NOT_SIGNIFICANT_ROBUSTNESS_FAILED",
        allowed_next_action=[
            "future_oos_monitoring_only_with_explicit_authorization_and_p221f_gate",
            "wait_for_significant_new_draws",
        ],
        forbidden_next_action=[
            "strategy_promotion",
            "production_change",
            "betting_advice",
            "db_write",
            "registry_write",
        ],
        confidence_language=(
            "POWER_LOTTO first-zone backward-OOS result: mean 0.96859 vs baseline 0.94737; "
            "p=0.3018 (not significant); CI crosses baseline; both robustness checks fail. "
            "Non-deployable. Observation-only. Historical research evidence; not betting advice."
        ),
        human_review_required=False,
        nist_alert_level=NistAlertLevel.NOT_RUN,
    )


def make_f3_star_underpowered():
    """
    F3: P227C 3_STAR / 4_STAR box-play — UNDERPOWERED_NO_SIGNAL.

    Evidence: CURRENT_STATE.md P227C confirmed line:
    - 120 hypotheses (10 features x 6 windows x 2 lotteries)
    - 3_STAR: 0 Bonferroni, 1 BH-FDR weak (UNDERPOWERED, F7_high_low/w750 p=0.0008)
    - 4_STAR: 0 Bonferroni, 0 BH-FDR
    - 3_STAR draws: 4,179 (need >=10,000); 4_STAR draws: 2,922 (need >=17,000)
    - Straight-play BLOCKED (sorted DB storage, positional order lost)
    - classification: P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL
    """
    return build_diagnostic_report(
        task_id="P227C",
        report_date="2026-06-03",
        lottery_type=LotteryType.STAR_3,
        strategy_id="box_play_scan_f7_high_low",
        diagnostic_subject="3_STAR box-play 120-hypothesis scan (strongest candidate)",
        lifecycle_status=LifecycleStatus.DRY_RUN,
        sample_size=4179,
        window_definition="window_750",
        is_oos=False,
        split_boundary=None,
        family_size_k=120,
        baseline_method="theoretical",
        baseline_value=0.00833,
        observed_metric=None,
        delta_vs_baseline=None,
        n_blocks=None,
        blocks_above_baseline=None,
        p_value_raw=0.0008,
        correction_method=CorrectionMethod.BENJAMINI_HOCHBERG,
        corrected_threshold=0.000417,
        is_corrected_significant=False,
        mc_null_99th_pct=None,
        is_above_mc_noise_floor=None,
        robustness_check_description="0 Bonferroni passes; 1 BH-FDR weak observation (UNDERPOWERED)",
        robustness_metric=None,
        robustness_sign_stable=None,
        drift_guard_result=DriftGuardResult.PASS,
        psi_value=None,
        psi_status=PsiStatus.NOT_RUN,
        feature_bottleneck="sample_too_small",
        min_detectable_effect=None,
        power_at_observed_effect=None,
        overfit_ratio=None,
        classification="P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL",
        blocker_classification="SAMPLE_TOO_SMALL_NEED_10000_DRAWS",
        allowed_next_action=[
            "wait_until_3_star_draws_reach_10000",
            "positional_reingest_design_with_explicit_authorization_for_straight_play",
        ],
        forbidden_next_action=[
            "strategy_promotion",
            "production_change",
            "betting_advice",
            "db_write",
            "deploy_underpowered_result",
        ],
        confidence_language=(
            "3_STAR box-play scan: 0 Bonferroni passes; 1 BH-FDR weak (p=0.0008, UNDERPOWERED). "
            "Current draws: 4,179 (need >=10,000). Not deployable. Historical evidence; not betting advice."
        ),
        human_review_required=False,
        nist_alert_level=NistAlertLevel.NOT_RUN,
    )


def make_f4_daily539_rejected():
    """
    F4: P230C DAILY_539 survivor — REJECTED_BY_BACKWARD_OOS.

    Evidence: CURRENT_STATE.md P230B1/P230C confirmed lines:
    - strategy: midfreq_fourier_2bet / DAILY_539
    - backward-OOS 4,265 draws (2007/05–2021/08)
    - mean 0.6375 < baseline 0.6410 (z=-0.32, p=0.626)
    - all era/robustness checks fail
    - reclassified from WAIT_FOR_OOS to REJECTED_BY_BACKWARD_OOS / HISTORICAL_ARTIFACT_DIRECTION
    """
    return build_diagnostic_report(
        task_id="P230B1",
        report_date="2026-06-03",
        lottery_type=LotteryType.DAILY_539,
        strategy_id="midfreq_fourier_2bet",
        diagnostic_subject="DAILY_539 backward-OOS extension — full historical window",
        lifecycle_status=LifecycleStatus.REJECTED,
        sample_size=4265,
        window_definition="backward_oos_4265_draws_2007_05_to_2021_08",
        is_oos=True,
        split_boundary="99000212",
        family_size_k=1,
        baseline_method="empirical_full",
        baseline_value=0.641,
        observed_metric=0.6375,
        delta_vs_baseline=-0.0035,
        n_blocks=3,
        blocks_above_baseline=1,
        p_value_raw=0.626,
        correction_method=CorrectionMethod.NONE,
        corrected_threshold=0.05,
        is_corrected_significant=False,
        mc_null_99th_pct=None,
        is_above_mc_noise_floor=False,
        robustness_check_description="exclude hit>=3 rows; exclude strongest block; early era 0.632; late era 0.621",
        robustness_metric=0.612,
        robustness_sign_stable=False,
        drift_guard_result=DriftGuardResult.PASS,
        psi_value=None,
        psi_status=PsiStatus.NOT_RUN,
        feature_bottleneck="historical_artifact_backward_oos_below_baseline",
        min_detectable_effect=None,
        power_at_observed_effect=None,
        overfit_ratio=None,
        classification="REJECTED_BY_BACKWARD_OOS_HISTORICAL_ARTIFACT_DIRECTION",
        blocker_classification="BACKWARD_OOS_MEAN_BELOW_BASELINE_ALL_ERA_CHECKS_FAIL",
        allowed_next_action=[
            "passive_monitoring_wait_for_300_new_live_draws",
            "future_gate_review_when_p224b_threshold_met",
        ],
        forbidden_next_action=[
            "strategy_promotion",
            "production_change",
            "betting_advice",
            "db_write",
            "registry_write",
            "immediate_deployment",
        ],
        confidence_language=(
            "DAILY_539 backward-OOS (4,265 draws): mean 0.6375 < baseline 0.6410; p=0.626; "
            "all era and robustness checks fail. In-window edge is a historical artifact. "
            "Reclassified REJECTED_BY_BACKWARD_OOS. Historical evidence; not betting advice."
        ),
        human_review_required=False,
        nist_alert_level=NistAlertLevel.NOT_RUN,
    )


# All fixtures as a dict for parametrize
ALL_FIXTURES = {
    "F1_nist_yellow": make_f1_nist_yellow(),
    "F2_power_lotto_null": make_f2_power_lotto_null(),
    "F3_star_underpowered": make_f3_star_underpowered(),
    "F4_daily539_rejected": make_f4_daily539_rejected(),
}


# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

def test_p242_module_imports():
    from lottery_api.diagnostics import statistical_diagnostics_schema
    assert statistical_diagnostics_schema is not None


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_is_dict(fid, report):
    assert isinstance(report, dict), f"{fid}: report must be a dict"


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_validates(fid, report):
    ok, errors = validate_diagnostic_report(report)
    assert ok is True, f"{fid} validation errors: {errors}"


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_db_write_false(fid, report):
    assert report.get("db_write_authorized") is False, f"{fid}: db_write_authorized must be False"


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_registry_write_false(fid, report):
    assert report.get("registry_write_authorized") is False


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_production_false(fid, report):
    assert report.get("production_authorized") is False


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_no_betting_advice(fid, report):
    assert report.get("betting_advice") is False


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_has_allowed_next_action(fid, report):
    assert "allowed_next_action" in report
    assert isinstance(report["allowed_next_action"], list)
    assert len(report["allowed_next_action"]) >= 1


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_has_forbidden_next_action(fid, report):
    assert "forbidden_next_action" in report
    assert isinstance(report["forbidden_next_action"], list)
    assert "strategy_promotion" in report["forbidden_next_action"]
    assert "betting_advice" in report["forbidden_next_action"]


@pytest.mark.parametrize("fid,report", list(ALL_FIXTURES.items()))
def test_fixture_confidence_language_no_prediction_edge(fid, report):
    lang = report.get("confidence_language", "") or ""
    bad_phrases = ("prediction edge", "win rate improvement", "betting recommendation")
    for phrase in bad_phrases:
        assert phrase.lower() not in lang.lower(), (
            f"{fid}: confidence_language must not contain '{phrase}'; got: {lang!r}"
        )


# ---------------------------------------------------------------------------
# P238B NIST YELLOW specific
# ---------------------------------------------------------------------------

def test_f1_nist_yellow_alert_level():
    r = ALL_FIXTURES["F1_nist_yellow"]
    assert r["nist_alert_level"] == NistAlertLevel.YELLOW


def test_f1_nist_yellow_semantics():
    result = classify_nist_alert(NistAlertLevel.YELLOW)
    assert result["strategy_authorized"] is False
    assert result["production_authorized"] is False
    assert result["betting_advice"] is False
    assert "observation" in result["interpretation"].lower()


def test_f1_forbidden_includes_strategy():
    r = ALL_FIXTURES["F1_nist_yellow"]
    assert "strategy_promotion" in r["forbidden_next_action"]


# ---------------------------------------------------------------------------
# Fixture count
# ---------------------------------------------------------------------------

def test_fixture_count_in_range():
    assert 2 <= len(ALL_FIXTURES) <= 5


# ---------------------------------------------------------------------------
# Artifact validation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def json_artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


def test_json_artifact_exists():
    assert os.path.exists(JSON_PATH), f"Missing: {JSON_PATH}"


def test_markdown_artifact_exists():
    assert os.path.exists(MD_PATH), f"Missing: {MD_PATH}"


def test_json_classification(json_artifact):
    assert json_artifact["classification"] == "P243A_DIAGNOSTIC_REPORT_FIXTURE_PACK_COMPLETE"


def test_json_fixture_count(json_artifact):
    assert 2 <= json_artifact["fixture_count"] <= 5


def test_json_no_db_write(json_artifact):
    assert json_artifact["no_db_write"] is True


def test_json_no_registry_mutation(json_artifact):
    assert json_artifact["no_registry_mutation"] is True


def test_json_no_production_change(json_artifact):
    assert json_artifact["no_production_change"] is True


def test_json_no_betting_advice(json_artifact):
    assert json_artifact["no_betting_advice"] is True


def test_json_p211_not_restarted(json_artifact):
    assert json_artifact["p211_restarted"] is False


def test_json_p238b_interpretation(json_artifact):
    assert "YELLOW" in json_artifact["p238b_interpretation"]


def test_markdown_no_db_write(json_artifact):
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "no db write" in content or "db_write_authorized" in content


def test_markdown_no_betting_advice(json_artifact):
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "betting advice" in content


def test_markdown_type_c():
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "type c" in content


def test_markdown_no_separate_closeout():
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "no separate" in content or "same-pr" in content or "same pr" in content
