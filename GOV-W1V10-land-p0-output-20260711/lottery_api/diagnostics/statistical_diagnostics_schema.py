"""
P242 Read-Only Statistical Diagnostics Schema.

Pure Python module — no DB access, no filesystem writes, no network calls,
no production registry imports. Implements the P241B feature-bottleneck
report schema as typed constants, helpers, and validators.

This module does NOT:
- Connect to any database
- Read or write the production SQLite database
- Modify strategy registry
- Affect production recommendation logic
- Run statistical scans
- Calculate predictions
- Claim prediction edge
- Provide betting advice
"""

# ---------------------------------------------------------------------------
# Enums / allowed value sets
# ---------------------------------------------------------------------------

class LotteryType:
    BIG_LOTTO = "BIG_LOTTO"
    DAILY_539 = "DAILY_539"
    POWER_LOTTO = "POWER_LOTTO"
    STAR_3 = "3_STAR"
    STAR_4 = "4_STAR"
    ALL = (BIG_LOTTO, DAILY_539, POWER_LOTTO, STAR_3, STAR_4)


class LifecycleStatus:
    ONLINE = "ONLINE"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"
    OBSERVATION = "OBSERVATION"
    DRY_RUN = "DRY_RUN"
    NON_EXECUTABLE_STUB = "NON_EXECUTABLE_STUB"
    ALL = (ONLINE, RETIRED, REJECTED, OBSERVATION, DRY_RUN, NON_EXECUTABLE_STUB)


class CorrectionMethod:
    BONFERRONI = "bonferroni"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    NONE = "none"
    ALL = (BONFERRONI, BENJAMINI_HOCHBERG, NONE)


class PsiStatus:
    STABLE = "STABLE"
    WARNING = "WARNING"
    DRIFT = "DRIFT"
    NOT_RUN = "NOT_RUN"
    ALL = (STABLE, WARNING, DRIFT, NOT_RUN)
    # PSI thresholds from RSM production code (documented here for research use)
    THRESHOLD_STABLE = 0.1
    THRESHOLD_WARNING = 0.2


class NistAlertLevel:
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    NOT_RUN = "NOT_RUN"
    ALL = (GREEN, YELLOW, ORANGE, RED, NOT_RUN)


class DriftGuardResult:
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    ALL = (PASS, FAIL, NOT_RUN)


class TaskType:
    A = "Type A"
    B = "Type B"
    C = "Type C"
    D = "Type D"
    E = "Type E"


# ---------------------------------------------------------------------------
# Canonical required schema fields (from P241B inventory)
# ---------------------------------------------------------------------------

REQUIRED_SCHEMA_FIELDS = (
    # Identity
    "task_id",
    "report_date",
    "lottery_type",
    "strategy_id",
    "diagnostic_subject",
    "lifecycle_status",
    # Sample and window
    "sample_size",
    "window_definition",
    "is_oos",
    "split_boundary",
    "family_size_k",
    # Baseline and metric
    "baseline_method",
    "baseline_value",
    "observed_metric",
    "delta_vs_baseline",
    "n_blocks",
    "blocks_above_baseline",
    # Statistical
    "p_value_raw",
    "correction_method",
    "corrected_threshold",
    "is_corrected_significant",
    "mc_null_99th_pct",
    "is_above_mc_noise_floor",
    # Robustness
    "robustness_check_description",
    "robustness_metric",
    "robustness_sign_stable",
    "drift_guard_result",
    "psi_value",
    "psi_status",
    # Feature bottleneck
    "feature_bottleneck",
    "min_detectable_effect",
    "power_at_observed_effect",
    "overfit_ratio",
    # Classification and gate
    "classification",
    "blocker_classification",
    "allowed_next_action",
    "forbidden_next_action",
    # Confidence and safety
    "confidence_language",
    "human_review_required",
    "db_write_authorized",
    "registry_write_authorized",
    "production_authorized",
    "betting_advice",
    "nist_alert_level",
)

# Safety fields that must remain False by default
_SAFETY_BOOLEAN_FIELDS = (
    "db_write_authorized",
    "registry_write_authorized",
    "production_authorized",
    "betting_advice",
    "strategy_authorized",
    "monitoring_authorized",
    "controlled_apply_authorized",
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def default_safety_fields():
    """Return a dict of all safety boolean fields set to their safe defaults (False)."""
    return {field: False for field in _SAFETY_BOOLEAN_FIELDS}


def classify_nist_alert(level):
    """
    Return a dict describing the semantics and authorization limits for a NIST alert level.

    YELLOW: observation-only — no strategy, no production, no recommendation,
            no DB write, no betting advice.
    RED:    human diagnostic review only — no strategy, no production, no recommendation,
            no DB write, no betting advice.

    No NIST alert level authorizes strategy, production, or betting advice.
    """
    if level not in NistAlertLevel.ALL:
        raise ValueError(f"Unknown NIST alert level: {level!r}. Must be one of {NistAlertLevel.ALL}")

    base = {
        "alert_level": level,
        "strategy_authorized": False,
        "production_authorized": False,
        "recommendation_change_authorized": False,
        "db_write_authorized": False,
        "registry_write_authorized": False,
        "betting_advice": False,
    }

    if level == NistAlertLevel.GREEN:
        base["interpretation"] = "No anomalies detected. Observation-only."
        base["human_review_required"] = False
    elif level == NistAlertLevel.YELLOW:
        base["interpretation"] = (
            "Observation-only. Historical anomalies capped at YELLOW. "
            "Does not constitute a predictability claim, win-rate claim, or betting advice. "
            "ORANGE/RED require independent future confirmation."
        )
        base["human_review_required"] = False
    elif level == NistAlertLevel.ORANGE:
        base["interpretation"] = (
            "Elevated observation. Requires independent future confirmation. "
            "Does not authorize strategy, production, or betting advice."
        )
        base["human_review_required"] = True
    elif level == NistAlertLevel.RED:
        base["interpretation"] = (
            "Human diagnostic review only. Does NOT authorize prediction, strategy, "
            "production, registry, recommendation, monitoring, DB write, or betting advice."
        )
        base["human_review_required"] = True
    else:  # NOT_RUN
        base["interpretation"] = "NIST randomness audit not run."
        base["human_review_required"] = False

    return base


def build_diagnostic_report(**kwargs):
    """
    Build a diagnostic report dict from keyword arguments.

    Required fields must be supplied. Safety fields default to False
    if not provided. Unknown fields are included as-is.

    Returns a plain dict — no DB access, no side effects.
    Raises ValueError if a safety field is provided as True.
    """
    safety = default_safety_fields()
    # Merge: caller may override non-safety fields; safety overrides are checked below
    report = dict(safety)
    report.update(kwargs)

    # Enforce safety defaults cannot be overridden to True without explicit intent
    for field in _SAFETY_BOOLEAN_FIELDS:
        if report.get(field) is True:
            raise ValueError(
                f"Safety field '{field}' must not be True. "
                f"This module produces read-only research diagnostics only."
            )

    # Populate delta_vs_baseline if baseline_value and observed_metric are provided
    if (
        "delta_vs_baseline" not in kwargs
        and "baseline_value" in report
        and "observed_metric" in report
        and report["baseline_value"] is not None
        and report["observed_metric"] is not None
    ):
        try:
            report["delta_vs_baseline"] = round(
                float(report["observed_metric"]) - float(report["baseline_value"]), 6
            )
        except (TypeError, ValueError):
            pass

    return report


def validate_diagnostic_report(report):
    """
    Validate a diagnostic report dict.

    Returns (True, []) if valid.
    Returns (False, [error_messages]) if invalid.

    Checks:
    - All required fields present
    - Safety booleans are False
    - NIST YELLOW confidence_language does not imply prediction edge
    - betting_advice is False
    """
    errors = []

    # Check required fields
    for field in REQUIRED_SCHEMA_FIELDS:
        if field not in report:
            errors.append(f"Missing required field: '{field}'")

    # Check safety booleans
    for field in _SAFETY_BOOLEAN_FIELDS:
        if report.get(field) is True:
            errors.append(f"Safety field '{field}' must be False in read-only diagnostics.")

    # Check NIST YELLOW confidence_language
    nist_level = report.get("nist_alert_level")
    confidence_lang = report.get("confidence_language", "") or ""
    prediction_keywords = ("prediction edge", "win rate improvement", "betting advice", "deployable edge")
    if nist_level == NistAlertLevel.YELLOW:
        for kw in prediction_keywords:
            if kw.lower() in confidence_lang.lower():
                errors.append(
                    f"NIST YELLOW confidence_language must not imply prediction edge; "
                    f"found keyword: '{kw}'."
                )

    return (len(errors) == 0), errors
