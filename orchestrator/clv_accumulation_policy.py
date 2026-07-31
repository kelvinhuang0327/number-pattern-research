"""
orchestrator/clv_accumulation_policy.py
Phase 32 — CLV Accumulation & Monitoring Policy

Tracks progress toward the 50-record patch gate threshold.
All logic is pure / read-only; no mutations, no LLM calls, no production changes.

Evidence state thresholds:
  INSUFFICIENT  : computed_count <  30
  APPROACHING   : computed_count >= 30 and < 50
  SUFFICIENT    : computed_count >= 50

HARD RULES:
  - Do not generate patch candidates
  - Do not modify production models
  - Do not trigger live betting
  - Do not call external LLMs
  - n=14 is INSUFFICIENT; do not treat it as sufficient
  - Do not bypass human review
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Evidence state constants ──────────────────────────────────────────────
EVIDENCE_INSUFFICIENT: str = "INSUFFICIENT"
EVIDENCE_APPROACHING:  str = "APPROACHING"
EVIDENCE_SUFFICIENT:   str = "SUFFICIENT"

# ── Threshold constants ───────────────────────────────────────────────────
EVIDENCE_THRESHOLD_APPROACHING: int = 30
EVIDENCE_THRESHOLD_SUFFICIENT:  int = 50   # production patch gate

# ── Default paths ─────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MEMORY_PATH = _ROOT / "runtime" / "agent_orchestrator" / "training_memory.json"
_DEFAULT_REPORTS_DIR  = _ROOT / "data" / "wbc_backend" / "reports"


# ─────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────

def _determine_evidence_state(computed_count: int) -> str:
    if computed_count >= EVIDENCE_THRESHOLD_SUFFICIENT:
        return EVIDENCE_SUFFICIENT
    if computed_count >= EVIDENCE_THRESHOLD_APPROACHING:
        return EVIDENCE_APPROACHING
    return EVIDENCE_INSUFFICIENT


def _get_scheduler_recommendations(evidence_state: str) -> list[str]:
    """Return list of recommended scheduler actions given the current evidence state."""
    if evidence_state == EVIDENCE_INSUFFICIENT:
        return [
            "CONTINUE_CLOSING_MONITOR",
            "CONTINUE_CLV_GENERATION",
            "CONTINUE_PAPER_LEARNING",
            "NO_PATCH_TASKS",
            "NO_PRODUCTION_PROPOSALS",
        ]
    if evidence_state == EVIDENCE_APPROACHING:
        return [
            "CONTINUE_CLOSING_MONITOR",
            "CONTINUE_CLV_GENERATION",
            "CONTINUE_PAPER_LEARNING",
            "RERUN_CLV_INVESTIGATION",
            "NO_PATCH_TASKS",
        ]
    # SUFFICIENT
    return [
        "RUN_PATCH_GATE_RECHECK",
        "ESCALATE_FOR_HUMAN_REVIEW",
    ]


def _get_recommended_next_action(evidence_state: str, computed_count: int, threshold: int) -> str:
    if computed_count >= threshold:
        return "RUN_PATCH_GATE_RECHECK"
    if computed_count >= EVIDENCE_THRESHOLD_APPROACHING:
        return f"COLLECT_MORE_DATA (need {threshold - computed_count} more to reach threshold)"
    # INSUFFICIENT: also suggest when to re-run investigation
    remaining_to_approaching = EVIDENCE_THRESHOLD_APPROACHING - computed_count
    return (
        f"COLLECT_MORE_DATA "
        f"(need {threshold - computed_count} more to gate; "
        f"re-run investigation at +{remaining_to_approaching} records or crossing {EVIDENCE_THRESHOLD_APPROACHING}/{threshold})"
    )


def _load_priority_segments_from_memory(
    memory_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Load the latest CLV investigation entry from training_memory and return
    weak_segments + promising_segments marked as observation_only_until_threshold=True.
    Returns [] if no investigation data is found.
    """
    path = memory_path or _DEFAULT_MEMORY_PATH
    try:
        raw = path.read_text(encoding="utf-8")
        mem: dict = json.loads(raw)
    except Exception as exc:
        logger.debug("[CLVAccumulationPolicy] Could not read training_memory: %s", exc)
        return []

    investigations: list[dict] = mem.get("clv_investigations", [])
    if not investigations:
        return []

    latest: dict = investigations[-1]
    segments: list[dict[str, Any]] = []

    for seg in latest.get("weak_segments", []):
        segments.append({
            "segment_type": seg.get("segment_type", "unknown"),
            "segment_value": seg.get("segment_value", "unknown"),
            "reliability": seg.get("reliability", "unknown"),
            "mean_clv": seg.get("mean_clv"),
            "positive_rate": seg.get("positive_rate"),
            "count": seg.get("count"),
            "classification": "weak",
            "observation_only_until_threshold": True,
        })

    for seg in latest.get("promising_segments", []):
        segments.append({
            "segment_type": seg.get("segment_type", "unknown"),
            "segment_value": seg.get("segment_value", "unknown"),
            "reliability": seg.get("reliability", "unknown"),
            "mean_clv": seg.get("mean_clv"),
            "positive_rate": seg.get("positive_rate"),
            "count": seg.get("count"),
            "classification": "promising",
            "observation_only_until_threshold": True,
        })

    return segments


# ─────────────────────────────────────────────────────────────────────────
# Core evaluation functions
# ─────────────────────────────────────────────────────────────────────────

def evaluate_clv_accumulation(
    records: list[dict[str, Any]],
    threshold: int = EVIDENCE_THRESHOLD_SUFFICIENT,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    """
    Pure function: evaluate CLV accumulation state from a list of COMPUTED records.

    Args:
        records:    List of COMPUTED CLV record dicts (pre-filtered).
        threshold:  Gate threshold (default 50, production).
        memory_path: Override path to training_memory.json (for testing).

    Returns:
        Accumulation state dict.
    """
    computed_count = len(records)
    remaining_needed = max(0, threshold - computed_count)
    progress_pct = round(min(100.0, computed_count / threshold * 100), 1) if threshold > 0 else 100.0

    evidence_state = _determine_evidence_state(computed_count)
    learning_cycle_allowed = computed_count >= 1
    patch_gate_recheck_allowed = computed_count >= threshold

    recommended_next_action = _get_recommended_next_action(
        evidence_state, computed_count, threshold
    )
    scheduler_recommendations = _get_scheduler_recommendations(evidence_state)
    priority_segments = _load_priority_segments_from_memory(memory_path)

    return {
        "computed_count":            computed_count,
        "threshold":                 threshold,
        "remaining_needed":          remaining_needed,
        "progress_pct":              progress_pct,
        "evidence_state":            evidence_state,
        "learning_cycle_allowed":    learning_cycle_allowed,
        "patch_gate_recheck_allowed": patch_gate_recheck_allowed,
        "recommended_next_action":   recommended_next_action,
        "scheduler_recommendations": scheduler_recommendations,
        "priority_segments":         priority_segments,
        "patch_candidate_allowed":   False,   # HARD RULE: always False until gate clears
    }


def evaluate_clv_accumulation_from_count(
    computed_count: int,
    threshold: int = EVIDENCE_THRESHOLD_SUFFICIENT,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    """
    Convenience wrapper — same as evaluate_clv_accumulation but accepts an int count
    instead of a record list (useful for integration layers that only have the count).
    """
    return evaluate_clv_accumulation(
        records=[{}] * computed_count,
        threshold=threshold,
        memory_path=memory_path,
    )


def get_clv_accumulation_summary(
    reports_dir: Path | None = None,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    """
    High-level summary for readiness / ops / decision card surfaces.
    Reads the CLV validation records file and training_memory, then evaluates.
    Returns a merged accumulation state dict.
    Falls back gracefully on any I/O error.
    """
    rdir = reports_dir or _DEFAULT_REPORTS_DIR
    mpath = memory_path or _DEFAULT_MEMORY_PATH

    # Locate the production CLV validation records file
    computed_records: list[dict] = []
    try:
        clv_files = sorted(rdir.glob("clv_validation_records_*.jsonl"))
        if clv_files:
            latest_file = clv_files[-1]
            for line in latest_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("clv_status") == "COMPUTED":
                        computed_records.append(rec)
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.debug("[CLVAccumulationPolicy] Could not load CLV records: %s", exc)

    result = evaluate_clv_accumulation(
        records=computed_records,
        memory_path=mpath,
    )
    result["available"] = True
    return result
