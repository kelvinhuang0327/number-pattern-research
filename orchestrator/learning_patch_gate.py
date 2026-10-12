"""
Phase 21 — Learning Patch Gate
================================
Evaluates a learning insight against the patch gate policy and decides
whether a production-adjacent patch task should be created.

Design principles:
  - Sandbox evidence NEVER directly creates a production patch.
  - Small-sample CLV (<5 records) is ALWAYS rejected as insufficient evidence.
  - CANDIDATE_PATCH requires a much higher evidence bar (≥20 sandbox / ≥50 production).
  - Gate output is purely advisory — actual task creation is the planner's responsibility.
  - No external LLM is called; all decisions are deterministic rule-based logic.

Decision tree (in priority order):
  1. REJECT_INSUFFICIENT_EVIDENCE — computed_count < _MIN_COUNT or variance missing
  2. HOLD                         — recommendation=HOLD with acceptable positive metrics
  3. INVESTIGATE_ONLY             — recommendation=INVESTIGATE with enough evidence
  4. ALLOW_PATCH_CANDIDATE        — CANDIDATE_PATCH with strong evidence + correct source thresholds
  5. REJECT_INSUFFICIENT_EVIDENCE — all other cases

Typical usage:
    from orchestrator.learning_patch_gate import evaluate_patch_gate

    decision = evaluate_patch_gate(
        signal_state_type="learning_clv_quality",
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=25,
        mean_clv=-0.025,
        median_clv=-0.022,
        clv_variance=0.0003,
        positive_rate=0.20,
        source="sandbox/test",
    )
    print(decision["gate_decision"])   # → "ALLOW_PATCH_CANDIDATE"
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Gate decisions ───────────────────────────────────────────────────────────
GATE_ALLOW_PATCH       = "ALLOW_PATCH_CANDIDATE"
GATE_INVESTIGATE_ONLY  = "INVESTIGATE_ONLY"
GATE_HOLD              = "HOLD"
GATE_REJECT            = "REJECT_INSUFFICIENT_EVIDENCE"

# ── Recommendation values (matches safe_task_executor output) ────────────────
REC_HOLD             = "HOLD"
REC_INVESTIGATE      = "INVESTIGATE"
REC_CANDIDATE_PATCH  = "CANDIDATE_PATCH"

# ── Thresholds ───────────────────────────────────────────────────────────────
# Minimum absolute computed count to be considered at all
_MIN_COUNT = 5

# Minimum counts for ALLOW_PATCH_CANDIDATE by source
_ALLOW_COUNT_SANDBOX    = 20   # sandbox/test source
_ALLOW_COUNT_PRODUCTION = 50   # production source

# CLV signal thresholds for ALLOW_PATCH_CANDIDATE
_PATCH_MAX_MEAN_CLV    = -0.010   # mean_clv must be ≤ this (edge is clearly negative)
_PATCH_MAX_POSITIVE_RATE = 0.30   # OR positive_rate must be < this

# ── Allowed task families by source ─────────────────────────────────────────
_SANDBOX_FAMILIES = ["model-validation-atomic", "calibration-patch-evaluation"]
_PRODUCTION_FAMILIES = ["model-validation-atomic", "calibration-patch-evaluation",
                        "model-patch-atomic", "calibration-atomic"]

# ── Source constants ─────────────────────────────────────────────────────────
_SOURCE_SANDBOX = "sandbox/test"


def _is_sandbox_source(source: str) -> bool:
    """Return True if the source string indicates sandbox / test mode."""
    s = (source or "").lower()
    return s.startswith("sandbox") or s.startswith("test")


def evaluate_patch_gate(
    *,
    signal_state_type: str,
    recommendation: str,
    computed_clv_count: int,
    mean_clv: float | None,
    median_clv: float | None = None,
    clv_variance: float | None,
    positive_rate: float,
    source: str = _SOURCE_SANDBOX,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluate a learning insight against the patch gate policy.

    Args:
        signal_state_type:  Must be "learning_clv_quality" (future types TBD).
        recommendation:     "HOLD" | "INVESTIGATE" | "CANDIDATE_PATCH".
        computed_clv_count: Number of COMPUTED CLV records analysed.
        mean_clv:           Mean CLV value (None ↔ empty sample).
        median_clv:         Median CLV value (optional, informational only).
        clv_variance:       CLV sample variance (None ↔ unknown / empty).
        positive_rate:      Fraction of COMPUTED CLV records with value > 0.
        source:             "sandbox/test" | "production" — MUST match origin.
        evidence:           Raw evidence dict from the learning cycle (optional).

    Returns:
        {
          "gate_decision":        str,   # one of the GATE_* constants
          "reason":               str,
          "allowed_task_family":  str | None,
          "confidence":           "low" | "medium" | "high",
          "requires_human_review": bool,
          "source":               str,   # echoed from input
          "computed_clv_count":   int,
          "recommendation":       str,
        }

    Hard rules enforced here:
      - sandbox source NEVER yields a production patch family.
      - computed_count < _MIN_COUNT always → REJECT.
      - variance must be known and non-None for ALLOW_PATCH_CANDIDATE.
    """
    is_sandbox = _is_sandbox_source(source)

    # ── Step 1: REJECT — insufficient evidence (always first) ────────────────
    if computed_clv_count < _MIN_COUNT:
        return _make_result(
            gate=GATE_REJECT,
            reason=(
                f"Insufficient evidence: computed_clv_count={computed_clv_count} "
                f"< minimum required {_MIN_COUNT}. "
                "Accumulate more COMPUTED CLV records before patching."
            ),
            family=None,
            confidence="low",
            human_review=False,
            source=source,
            count=computed_clv_count,
            rec=recommendation,
        )

    if clv_variance is None:
        return _make_result(
            gate=GATE_REJECT,
            reason=(
                "Insufficient evidence: clv_variance is unknown (None). "
                "Variance is required to validate signal stability before patching."
            ),
            family=None,
            confidence="low",
            human_review=False,
            source=source,
            count=computed_clv_count,
            rec=recommendation,
        )

    # ── Step 2: HOLD ──────────────────────────────────────────────────────────
    if recommendation == REC_HOLD:
        positive_signal = (mean_clv is None or mean_clv >= 0) and positive_rate >= 0.5
        reason_parts = [
            f"recommendation={REC_HOLD}",
            f"mean_clv={_fmt(mean_clv)}",
            f"positive_rate={positive_rate:.0%}",
        ]
        if positive_signal:
            reason_parts.append("positive edge confirmed — no patch warranted")
        return _make_result(
            gate=GATE_HOLD,
            reason="HOLD: " + ", ".join(reason_parts),
            family=None,
            confidence=_confidence(computed_clv_count),
            human_review=False,
            source=source,
            count=computed_clv_count,
            rec=recommendation,
        )

    # ── Step 3: INVESTIGATE_ONLY ──────────────────────────────────────────────
    if recommendation == REC_INVESTIGATE:
        family = _sandbox_family_for_investigate(is_sandbox)
        return _make_result(
            gate=GATE_INVESTIGATE_ONLY,
            reason=(
                f"INVESTIGATE_ONLY: recommendation=INVESTIGATE with "
                f"computed_clv_count={computed_clv_count} (>= {_MIN_COUNT}). "
                "Investigation task allowed; no patch until signal is stronger."
            ),
            family=family,
            confidence=_confidence(computed_clv_count),
            human_review=False,
            source=source,
            count=computed_clv_count,
            rec=recommendation,
        )

    # ── Step 4: ALLOW_PATCH_CANDIDATE (only for CANDIDATE_PATCH) ─────────────
    if recommendation == REC_CANDIDATE_PATCH:
        min_count = _ALLOW_COUNT_SANDBOX if is_sandbox else _ALLOW_COUNT_PRODUCTION

        # Check sample size
        if computed_clv_count < min_count:
            source_label = "sandbox" if is_sandbox else "production"
            return _make_result(
                gate=GATE_REJECT,
                reason=(
                    f"REJECT: CANDIDATE_PATCH evidence is too weak for {source_label} patch. "
                    f"computed_clv_count={computed_clv_count} < "
                    f"required {min_count} for {source_label} source."
                ),
                family=None,
                confidence="low",
                human_review=False,
                source=source,
                count=computed_clv_count,
                rec=recommendation,
            )

        # Check signal strength
        negative_edge = (mean_clv is not None and mean_clv <= _PATCH_MAX_MEAN_CLV)
        low_positive_rate = positive_rate < _PATCH_MAX_POSITIVE_RATE

        if not (negative_edge or low_positive_rate):
            return _make_result(
                gate=GATE_REJECT,
                reason=(
                    f"REJECT: CANDIDATE_PATCH signal not strong enough. "
                    f"mean_clv={_fmt(mean_clv)} (required <= {_PATCH_MAX_MEAN_CLV}) "
                    f"or positive_rate={positive_rate:.0%} "
                    f"(required < {_PATCH_MAX_POSITIVE_RATE:.0%}). "
                    "Signal must show clearly negative edge before patching."
                ),
                family=None,
                confidence="low",
                human_review=False,
                source=source,
                count=computed_clv_count,
                rec=recommendation,
            )

        # Check variance (must be non-zero — ensures signal is not degenerate)
        if clv_variance == 0.0:
            return _make_result(
                gate=GATE_REJECT,
                reason=(
                    "REJECT: clv_variance=0.0 — all CLV values are identical. "
                    "This suggests a data-quality issue; patching is not safe."
                ),
                family=None,
                confidence="low",
                human_review=True,
                source=source,
                count=computed_clv_count,
                rec=recommendation,
            )

        # All checks passed — allow patch candidate
        families = _SANDBOX_FAMILIES if is_sandbox else _PRODUCTION_FAMILIES
        # Always pick the safest family: model-validation-atomic first, then calibration
        allowed_family = families[0]  # "model-validation-atomic"

        human_review = is_sandbox  # sandbox patches always need human sign-off
        return _make_result(
            gate=GATE_ALLOW_PATCH,
            reason=(
                f"ALLOW_PATCH_CANDIDATE: strong evidence of negative edge. "
                f"computed_clv_count={computed_clv_count} >= {min_count}, "
                f"mean_clv={_fmt(mean_clv)}, "
                f"positive_rate={positive_rate:.0%}. "
                f"Allowed task family: {allowed_family}. "
                + ("Sandbox source — requires human review before production promotion." if is_sandbox
                   else "Production source — high-confidence patch candidate.")
            ),
            family=allowed_family,
            confidence=_confidence(computed_clv_count),
            human_review=human_review,
            source=source,
            count=computed_clv_count,
            rec=recommendation,
        )

    # ── Step 5: Fallback REJECT for unknown recommendation ────────────────────
    return _make_result(
        gate=GATE_REJECT,
        reason=(
            f"REJECT: Unknown recommendation value {recommendation!r}. "
            "Only HOLD/INVESTIGATE/CANDIDATE_PATCH are accepted."
        ),
        family=None,
        confidence="low",
        human_review=True,
        source=source,
        count=computed_clv_count,
        rec=recommendation,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_result(
    *,
    gate: str,
    reason: str,
    family: str | None,
    confidence: str,
    human_review: bool,
    source: str,
    count: int,
    rec: str,
) -> dict[str, Any]:
    logger.info(
        "[PatchGate] gate_decision=%s  recommendation=%s  computed_count=%d  "
        "family=%s  confidence=%s  requires_human_review=%s",
        gate, rec, count, family, confidence, human_review,
    )
    return {
        "gate_decision": gate,
        "reason": reason,
        "allowed_task_family": family,
        "confidence": confidence,
        "requires_human_review": human_review,
        "source": source,
        "computed_clv_count": count,
        "recommendation": rec,
    }


def _confidence(count: int) -> str:
    if count >= 30:
        return "high"
    if count >= 10:
        return "medium"
    return "low"


def _fmt(v: float | None) -> str:
    return f"{v:.4f}" if v is not None else "N/A"


def _sandbox_family_for_investigate(is_sandbox: bool) -> str:
    """Return the safest allowed investigation task family."""
    return "model-validation-atomic"
