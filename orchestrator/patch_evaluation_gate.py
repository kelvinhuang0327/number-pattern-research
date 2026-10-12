"""
orchestrator/patch_evaluation_gate.py
======================================
Phase 23 — Sandbox Patch Evaluation Decision Gate.

This is the SECOND-STAGE gate that processes outcomes from the Phase 22
calibration_patch_evaluation sandbox executor.  It decides what the system
should do *next* given a KEEP / REJECT / NEED_MORE_DATA evaluation result.

CRITICAL DESIGN CONSTRAINTS
----------------------------
- Sandbox KEEP results NEVER automatically become production patches.
- PROMOTE_TO_PRODUCTION_PROPOSAL always requires human review (requires_human_review=True).
- No external LLM is invoked.  All logic is deterministic and rule-based.
- Production source results are held to a stricter evidence threshold than sandbox.
- The gate is a pure function — no DB writes, no file I/O.

Decision rules (deterministic priority order)
----------------------------------------------
1. REJECT_SANDBOX_CANDIDATE  → next_decision = REJECT
2. NEED_MORE_DATA             → next_decision = REQUEST_MORE_DATA
                                allowed_next_task_family = clv-quality-analysis
3. KEEP_SANDBOX_CANDIDATE with source sandbox/test:
     a. sample_count < _PROMOTE_MIN_SANDBOX  → next_decision = REQUEST_MORE_DATA
        (or HUMAN_REVIEW_REQUIRED if delta > 0 but not enough evidence)
     b. sample_count >= _PROMOTE_MIN_SANDBOX AND delta > _MATERIAL_DELTA_THRESHOLD
        → next_decision = PROMOTE_TO_PRODUCTION_PROPOSAL
           requires_human_review = True   (ALWAYS)
     c. otherwise → next_decision = HOLD
4. KEEP_SANDBOX_CANDIDATE with production source:
     a. sample_count < _PROMOTE_MIN_PRODUCTION → next_decision = HUMAN_REVIEW_REQUIRED
     b. sample_count >= _PROMOTE_MIN_PRODUCTION AND delta > _MATERIAL_DELTA_PRODUCTION
        → next_decision = PROMOTE_TO_PRODUCTION_PROPOSAL
           requires_human_review = True   (ALWAYS)
     c. otherwise → next_decision = HUMAN_REVIEW_REQUIRED

Outputs
-------
{
  "next_decision":           "PROMOTE_TO_PRODUCTION_PROPOSAL|REJECT|REQUEST_MORE_DATA|
                              HUMAN_REVIEW_REQUIRED|HOLD",
  "reason":                  "...",
  "allowed_next_task_family":"...|null",
  "requires_human_review":   true/false,
  "confidence":              "low|medium|high",
  "evaluation_decision":     (echo of input),
  "source":                  (echo of input),
  "sample_count":            (echo of input),
  "delta":                   (echo of input),
}
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Next-decision constants ──────────────────────────────────────────────────
ND_PROMOTE        = "PROMOTE_TO_PRODUCTION_PROPOSAL"
ND_REJECT         = "REJECT"
ND_REQUEST_MORE   = "REQUEST_MORE_DATA"
ND_HUMAN_REVIEW   = "HUMAN_REVIEW_REQUIRED"
ND_HOLD           = "HOLD"

# ── Evaluation-decision constants (Phase 22 executor output) ─────────────────
ED_KEEP   = "KEEP_SANDBOX_CANDIDATE"
ED_REJECT = "REJECT_SANDBOX_CANDIDATE"
ED_MORE   = "NEED_MORE_DATA"

# ── Task family constants ────────────────────────────────────────────────────
TF_CLV_QUALITY          = "clv-quality-analysis"
TF_MANUAL_REVIEW        = "manual-review"
TF_PRODUCTION_PROPOSAL  = "production-proposal"

# ── Evidence thresholds ──────────────────────────────────────────────────────
# Minimum sample_count to even consider a PROMOTE decision from sandbox/test
_PROMOTE_MIN_SANDBOX    = 50

# Minimum sample_count from production source
_PROMOTE_MIN_PRODUCTION = 100

# Minimum positive delta (candidate_metric - baseline_metric) to materially improve.
# Below this → more data needed, not a promotion.
_MATERIAL_DELTA_THRESHOLD   = 0.005   # sandbox
_MATERIAL_DELTA_PRODUCTION  = 0.010   # production (stricter)

# ── Source identifiers ───────────────────────────────────────────────────────
_SANDBOX_SOURCES = frozenset({"sandbox/test", "sandbox"})


def evaluate_patch_evaluation_gate(evaluation_record: dict[str, Any]) -> dict[str, Any]:
    """
    Process a sandbox patch evaluation outcome and decide the next system action.

    Args:
        evaluation_record: Output dict from _execute_calibration_patch_evaluation()
                           or from training_memory.get_latest_patch_evaluation().
                           Must contain at minimum:
                             - "evaluation_decision": str
                             - "sample_count": int
                             - "delta": float | None
                             - "source": str

    Returns:
        Gate decision dict (see module docstring for schema).
    """
    ev_decision: str = evaluation_record.get("evaluation_decision", "")
    sample_count: int = int(evaluation_record.get("sample_count", 0))
    delta: float | None = evaluation_record.get("delta")
    source: str = str(evaluation_record.get("source", "sandbox/test"))
    gate_decision_id: str = str(evaluation_record.get("gate_decision_id", ""))
    task_id: str = str(evaluation_record.get("task_id", ""))
    baseline: float | None = evaluation_record.get("baseline_metric") or evaluation_record.get("baseline_mean_clv")
    candidate: float | None = evaluation_record.get("candidate_metric") or evaluation_record.get("candidate_mean_clv")

    is_sandbox = _is_sandbox(source)

    # ── Case 1: REJECT ───────────────────────────────────────────────────────
    if ev_decision == ED_REJECT:
        return _build(
            next_decision=ND_REJECT,
            reason=(
                f"Sandbox evaluation rejected candidate patch: "
                f"delta={_fmt(delta)}, sample_count={sample_count}. "
                "No further patch tasks generated."
            ),
            allowed_next_task_family=None,
            requires_human_review=False,
            confidence="high",
            evaluation_record=evaluation_record,
        )

    # ── Case 2: NEED_MORE_DATA ───────────────────────────────────────────────
    if ev_decision == ED_MORE:
        return _build(
            next_decision=ND_REQUEST_MORE,
            reason=(
                f"Insufficient CLV data for evaluation (sample_count={sample_count}). "
                "Requesting additional CLV quality analysis before any patch decision."
            ),
            allowed_next_task_family=TF_CLV_QUALITY,
            requires_human_review=False,
            confidence="medium",
            evaluation_record=evaluation_record,
        )

    # ── Case 3: KEEP ─────────────────────────────────────────────────────────
    if ev_decision == ED_KEEP:
        if is_sandbox:
            return _evaluate_keep_sandbox(
                sample_count=sample_count,
                delta=delta,
                evaluation_record=evaluation_record,
            )
        else:
            return _evaluate_keep_production(
                sample_count=sample_count,
                delta=delta,
                evaluation_record=evaluation_record,
            )

    # ── Fallback: unknown evaluation_decision ─────────────────────────────────
    logger.warning(
        "[PatchEvalGate] Unknown evaluation_decision=%r — defaulting to HOLD", ev_decision
    )
    return _build(
        next_decision=ND_HOLD,
        reason=f"Unrecognised evaluation_decision '{ev_decision}'. Holding until manual review.",
        allowed_next_task_family=None,
        requires_human_review=True,
        confidence="low",
        evaluation_record=evaluation_record,
    )


# ── Private helpers ───────────────────────────────────────────────────────────

def _evaluate_keep_sandbox(
    sample_count: int,
    delta: float | None,
    evaluation_record: dict,
) -> dict:
    """Decision logic for KEEP from a sandbox/test source."""
    delta_ok = delta is not None and delta > _MATERIAL_DELTA_THRESHOLD
    count_ok  = sample_count >= _PROMOTE_MIN_SANDBOX

    if not count_ok:
        # Sample too small to promote; decide between REQUEST_MORE or HUMAN_REVIEW
        if delta_ok:
            # Candidate looks promising but evidence too thin → human review
            return _build(
                next_decision=ND_HUMAN_REVIEW,
                reason=(
                    f"KEEP with promising delta ({_fmt(delta)}) but sample_count={sample_count} "
                    f"< {_PROMOTE_MIN_SANDBOX} required for promotion. "
                    "Human review needed before any further action."
                ),
                allowed_next_task_family=TF_MANUAL_REVIEW,
                requires_human_review=True,
                confidence="medium",
                evaluation_record=evaluation_record,
            )
        else:
            # Delta not material — request more CLV data
            return _build(
                next_decision=ND_REQUEST_MORE,
                reason=(
                    f"KEEP but delta ({_fmt(delta)}) is below material threshold "
                    f"({_MATERIAL_DELTA_THRESHOLD}) and sample_count={sample_count} "
                    f"< {_PROMOTE_MIN_SANDBOX}. Requesting more CLV data."
                ),
                allowed_next_task_family=TF_CLV_QUALITY,
                requires_human_review=False,
                confidence="medium",
                evaluation_record=evaluation_record,
            )

    if count_ok and delta_ok:
        # Sufficient evidence — but ALWAYS require human review for production proposal
        return _build(
            next_decision=ND_PROMOTE,
            reason=(
                f"KEEP with sample_count={sample_count} >= {_PROMOTE_MIN_SANDBOX} "
                f"and delta={_fmt(delta)} > {_MATERIAL_DELTA_THRESHOLD}. "
                "Proposing for production consideration. HUMAN REVIEW REQUIRED — "
                "no production patch applied automatically."
            ),
            allowed_next_task_family=TF_PRODUCTION_PROPOSAL,
            requires_human_review=True,  # ALWAYS True for production proposal
            confidence="high",
            evaluation_record=evaluation_record,
        )

    # count_ok but delta not material
    return _build(
        next_decision=ND_HOLD,
        reason=(
            f"KEEP with sample_count={sample_count} but delta ({_fmt(delta)}) "
            f"< material threshold ({_MATERIAL_DELTA_THRESHOLD}). Holding."
        ),
        allowed_next_task_family=None,
        requires_human_review=False,
        confidence="medium",
        evaluation_record=evaluation_record,
    )


def _evaluate_keep_production(
    sample_count: int,
    delta: float | None,
    evaluation_record: dict,
) -> dict:
    """Decision logic for KEEP from a production source (stricter thresholds)."""
    delta_ok = delta is not None and delta > _MATERIAL_DELTA_PRODUCTION
    count_ok  = sample_count >= _PROMOTE_MIN_PRODUCTION

    if not count_ok or not delta_ok:
        return _build(
            next_decision=ND_HUMAN_REVIEW,
            reason=(
                f"Production KEEP but insufficient for auto-promotion: "
                f"sample_count={sample_count} (need {_PROMOTE_MIN_PRODUCTION}), "
                f"delta={_fmt(delta)} (need >{_MATERIAL_DELTA_PRODUCTION}). "
                "Human review required."
            ),
            allowed_next_task_family=TF_MANUAL_REVIEW,
            requires_human_review=True,
            confidence="medium" if not count_ok else "high",
            evaluation_record=evaluation_record,
        )

    return _build(
        next_decision=ND_PROMOTE,
        reason=(
            f"Production KEEP with sample_count={sample_count} >= {_PROMOTE_MIN_PRODUCTION} "
            f"and delta={_fmt(delta)} > {_MATERIAL_DELTA_PRODUCTION}. "
            "Proposing for production consideration. HUMAN REVIEW REQUIRED."
        ),
        allowed_next_task_family=TF_PRODUCTION_PROPOSAL,
        requires_human_review=True,  # ALWAYS True
        confidence="high",
        evaluation_record=evaluation_record,
    )


def _build(
    next_decision: str,
    reason: str,
    allowed_next_task_family: str | None,
    requires_human_review: bool,
    confidence: str,
    evaluation_record: dict,
) -> dict:
    """Assemble the gate output dict."""
    return {
        "next_decision": next_decision,
        "reason": reason,
        "allowed_next_task_family": allowed_next_task_family,
        "requires_human_review": requires_human_review,
        "confidence": confidence,
        # Echo selected input fields for traceability
        "evaluation_decision": evaluation_record.get("evaluation_decision"),
        "source": evaluation_record.get("source"),
        "sample_count": evaluation_record.get("sample_count"),
        "delta": evaluation_record.get("delta"),
        "gate_decision_id": evaluation_record.get("gate_decision_id"),
        "task_id": evaluation_record.get("task_id"),
        # Production safety contract
        "production_patch_allowed": False,
        "production_model_modified": False,
        "external_llm_called": False,
    }


def _is_sandbox(source: str) -> bool:
    """Return True if source originates from a sandbox environment."""
    return source in _SANDBOX_SOURCES or source.startswith("sandbox")


def _fmt(value: float | None, places: int = 4) -> str:
    """Format a float for human-readable output, handling None gracefully."""
    if value is None:
        return "N/A"
    return f"{value:.{places}f}"
