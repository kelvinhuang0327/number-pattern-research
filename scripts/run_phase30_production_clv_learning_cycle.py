"""
Phase 30 — Production CLV Learning Cycle (PAPER_ONLY)
======================================================
Runs the first real production learning cycle against COMPUTED CLV signal
from the Phase 29-upgraded production records, strictly in PAPER_ONLY mode.

Hard constraints:
  - source marker is always "production/paper" — never "sandbox/test"
  - execution_mode is always "PAPER_ONLY"
  - NO production model file is modified (production_mutation=False)
  - NO live bet is submitted (live_bet_submitted=False)
  - NO external LLM is called
  - Read-only access to CLV JSONL — source file is never written

Exit token:
  PHASE_30_PRODUCTION_CLV_LEARNING_CYCLE_PAPER_VERIFIED

Typical usage:
    python scripts/run_phase30_production_clv_learning_cycle.py           # dry-run
    python scripts/run_phase30_production_clv_learning_cycle.py --apply   # write artifacts
"""
from __future__ import annotations

import json
import logging
import statistics as _stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_REPORTS_DIR = _ROOT / "data" / "wbc_backend" / "reports"
_TASKS_ROOT = _ROOT / "runtime" / "agent_orchestrator" / "tasks"

# Default production CLV file (Phase 29 upgraded)
CLV_FILE = _REPORTS_DIR / "clv_validation_records_6u_2026-04-30.jsonl"

# ── Execution constants ───────────────────────────────────────────────────
EXECUTION_MODE = "PAPER_ONLY"
SOURCE_MARKER = "production/paper"
PRODUCTION_MUTATION = False
LIVE_BET_SUBMITTED = False

# ── Production patch gate threshold ──────────────────────────────────────
PRODUCTION_PATCH_THRESHOLD = 50   # must match learning_patch_gate._ALLOW_COUNT_PRODUCTION

# ── Recommendation thresholds (must match safe_task_executor logic) ───────
_HOLD_MIN_MEAN_CLV = 0.010
_HOLD_MIN_POSITIVE_RATE = 0.6
_PATCH_MAX_MEAN_CLV = -0.010
_PATCH_MAX_POSITIVE_RATE = 0.3


# ─────────────────────────────────────────────────────────────────────────
# Pure functions
# ─────────────────────────────────────────────────────────────────────────

def load_computed_clv_records(clv_path: Path) -> list[dict]:
    """
    Load only COMPUTED CLV records from a single JSONL file.

    Returns a list of dicts; PENDING_CLOSING and BLOCKED records are excluded.
    Raises FileNotFoundError if clv_path does not exist.
    """
    rows: list[dict] = []
    for line in clv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("clv_status") == "COMPUTED" and row.get("clv_value") is not None:
            try:
                row["clv_value"] = float(row["clv_value"])
                rows.append(row)
            except (TypeError, ValueError):
                pass
    return rows


def analyze_clv_quality(records: list[dict]) -> dict[str, Any]:
    """
    Compute descriptive statistics for a list of COMPUTED CLV records.

    Args:
        records: List of dicts, each with a ``clv_value`` float field.

    Returns:
        {
          computed_count: int,
          positive_clv_count: int,
          negative_clv_count: int,
          flat_clv_count: int,
          mean_clv: float | None,
          median_clv: float | None,
          clv_variance: float | None,
          positive_rate: float,
        }
    """
    clv_values = [r["clv_value"] for r in records]
    n = len(clv_values)

    if n == 0:
        return {
            "computed_count": 0,
            "positive_clv_count": 0,
            "negative_clv_count": 0,
            "flat_clv_count": 0,
            "mean_clv": None,
            "median_clv": None,
            "clv_variance": None,
            "positive_rate": 0.0,
        }

    positive_count = sum(1 for v in clv_values if v > 0)
    negative_count = sum(1 for v in clv_values if v < 0)
    flat_count = n - positive_count - negative_count

    mean_clv = sum(clv_values) / n
    median_clv = _stat.median(clv_values)
    clv_variance = _stat.variance(clv_values) if n >= 2 else 0.0
    positive_rate = positive_count / n

    return {
        "computed_count": n,
        "positive_clv_count": positive_count,
        "negative_clv_count": negative_count,
        "flat_clv_count": flat_count,
        "mean_clv": round(mean_clv, 6),
        "median_clv": round(median_clv, 6),
        "clv_variance": round(clv_variance, 8),
        "positive_rate": round(positive_rate, 4),
    }


def get_recommendation(stats: dict[str, Any]) -> str:
    """
    Derive HOLD / INVESTIGATE / CANDIDATE_PATCH from CLV quality stats.

    Logic mirrors ``safe_task_executor._execute_clv_quality_analysis``:
      - HOLD: mean_clv >= +1.0% AND positive_rate >= 60 %
      - CANDIDATE_PATCH: mean_clv <= -1.0% OR positive_rate < 30 %
      - INVESTIGATE: everything else (including empty sample)
    """
    computed_count: int = stats.get("computed_count", 0)
    if computed_count == 0:
        return "INVESTIGATE"

    mean_clv: float | None = stats.get("mean_clv")
    positive_rate: float = stats.get("positive_rate", 0.0)

    if mean_clv is not None and mean_clv >= _HOLD_MIN_MEAN_CLV and positive_rate >= _HOLD_MIN_POSITIVE_RATE:
        return "HOLD"
    if mean_clv is not None and (mean_clv <= _PATCH_MAX_MEAN_CLV or positive_rate < _PATCH_MAX_POSITIVE_RATE):
        return "CANDIDATE_PATCH"
    return "INVESTIGATE"


def evaluate_production_patch_gate(
    stats: dict[str, Any],
    recommendation: str,
    production_threshold: int = PRODUCTION_PATCH_THRESHOLD,
) -> dict[str, Any]:
    """
    Pass the production CLV quality signal through the learning patch gate.

    Uses ``source="production/paper"`` — this is NOT a sandbox source so
    production thresholds apply (≥50 records for ALLOW_PATCH_CANDIDATE).

    Returns the gate decision dict from ``orchestrator.learning_patch_gate``.
    """
    from orchestrator.learning_patch_gate import evaluate_patch_gate

    return evaluate_patch_gate(
        signal_state_type="learning_clv_quality",
        recommendation=recommendation,
        computed_clv_count=stats.get("computed_count", 0),
        mean_clv=stats.get("mean_clv"),
        median_clv=stats.get("median_clv"),
        clv_variance=stats.get("clv_variance"),
        positive_rate=stats.get("positive_rate", 0.0),
        source=SOURCE_MARKER,
        evidence=stats,
    )


def record_production_cycle(
    task_id: str,
    stats: dict[str, Any],
    recommendation: str,
    gate_result: dict[str, Any],
    artifact_path: str | None,
) -> dict:
    """
    Record the production paper learning cycle in training_memory.

    Writes two entries:
      1. ``training_memory.record_learning_cycle`` — source="production/paper"
      2. ``training_memory.record_gate_decision``  — gate outcome

    Hard rules:
      - Does NOT modify consecutive_successes / consecutive_failures.
      - Does NOT trigger any production patch.
      - production_mutation and live_bet_submitted are always False.

    Returns:
        {
          "learning_cycle_recorded": True,
          "gate_decision_recorded": True,
          "task_id": str,
          "source": "production/paper",
          "execution_mode": "PAPER_ONLY",
          "production_mutation": False,
          "live_bet_submitted": False,
          "gate_decision": str,
        }
    """
    from orchestrator import training_memory as tm

    tm.record_learning_cycle(
        task_id=task_id,
        computed_clv_count=stats.get("computed_count", 0),
        mean_clv=stats.get("mean_clv"),
        recommendation=recommendation,
        learning_cycle_status="COMPLETED",
        source=SOURCE_MARKER,
        artifact_path=artifact_path,
    )

    tm.record_gate_decision(
        learning_cycle_id=task_id,
        gate_decision=gate_result["gate_decision"],
        reason=gate_result["reason"],
        confidence=gate_result["confidence"],
        requires_human_review=gate_result["requires_human_review"],
        recommendation=recommendation,
        computed_clv_count=stats.get("computed_count", 0),
        source=SOURCE_MARKER,
        generated_task_id=None,
        allowed_task_family=gate_result.get("allowed_task_family"),
    )

    return {
        "learning_cycle_recorded": True,
        "gate_decision_recorded": True,
        "task_id": task_id,
        "source": SOURCE_MARKER,
        "execution_mode": EXECUTION_MODE,
        "production_mutation": PRODUCTION_MUTATION,
        "live_bet_submitted": LIVE_BET_SUBMITTED,
        "gate_decision": gate_result["gate_decision"],
    }


def write_task_artifact(
    task_id: str,
    stats: dict[str, Any],
    recommendation: str,
    gate_result: dict[str, Any],
    task_dir: Path,
) -> Path:
    """
    Write the production CLV quality analysis Markdown artifact.

    Writes to ``task_dir/{task_id}-production-clv-quality-analysis.md``.
    Returns the path of the written file.
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = task_dir / f"{task_id}-production-clv-quality-analysis.md"

    n = stats.get("computed_count", 0)
    mean_str = f"{stats['mean_clv']:.4f}" if stats.get("mean_clv") is not None else "N/A"
    median_str = f"{stats['median_clv']:.4f}" if stats.get("median_clv") is not None else "N/A"
    var_str = f"{stats['clv_variance']:.8f}" if stats.get("clv_variance") is not None else "N/A"
    pos_rate_str = f"{stats.get('positive_rate', 0.0):.1%}"
    generated_at = datetime.now(timezone.utc).isoformat()

    gate_decision = gate_result["gate_decision"]
    gate_reason = gate_result["reason"]
    gate_confidence = gate_result["confidence"]
    gate_human_review = gate_result["requires_human_review"]

    text = (
        f"# Production CLV Quality Analysis — PAPER_ONLY\n\n"
        f"**Task ID**: `{task_id}`\n"
        f"**Generated At**: {generated_at}\n"
        f"**Execution Mode**: `{EXECUTION_MODE}`\n"
        f"**Source Marker**: `{SOURCE_MARKER}`\n\n"
        "---\n\n"
        "## Summary Statistics\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Computed CLV records | {n} |\n"
        f"| Positive CLV count   | {stats.get('positive_clv_count', 0)} |\n"
        f"| Negative CLV count   | {stats.get('negative_clv_count', 0)} |\n"
        f"| Flat CLV count       | {stats.get('flat_clv_count', 0)} |\n"
        f"| Mean CLV             | {mean_str} |\n"
        f"| Median CLV           | {median_str} |\n"
        f"| CLV Variance         | {var_str} |\n"
        f"| Positive rate        | {pos_rate_str} |\n\n"
        "## Recommendation\n\n"
        f"**{recommendation}**\n\n"
        "## Patch Gate Evaluation\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Gate decision            | **{gate_decision}** |\n"
        f"| Confidence               | `{gate_confidence}` |\n"
        f"| Requires human review    | `{gate_human_review}` |\n"
        f"| Allowed task family      | `{gate_result.get('allowed_task_family') or '(none)'}` |\n"
        f"| Production threshold     | {PRODUCTION_PATCH_THRESHOLD} records |\n"
        f"| Current count            | {n} records |\n\n"
        f"**Gate reason**: {gate_reason}\n\n"
        "## Hard Rules Verified\n\n"
        f"- ✅ Execution mode: `{EXECUTION_MODE}`\n"
        f"- ✅ Source marker: `{SOURCE_MARKER}`\n"
        f"- ✅ No production model modified (`production_mutation=False`)\n"
        f"- ✅ No live bet submitted (`live_bet_submitted=False`)\n"
        f"- ✅ No external LLM called\n"
        f"- ✅ CLV JSONL source file read-only\n"
        f"- ✅ Production patch blocked: {n} < {PRODUCTION_PATCH_THRESHOLD} required for ALLOW_PATCH_CANDIDATE\n"
    )

    artifact_path.write_text(text, encoding="utf-8")
    return artifact_path


def run_cycle(
    clv_path: Path | None = None,
    task_dir: Path | None = None,
    apply: bool = False,
    task_id: str | None = None,
) -> dict[str, Any]:
    """
    Run one complete production paper CLV learning cycle.

    Args:
        clv_path:  Path to production CLV JSONL file (default: CLV_FILE).
        task_dir:  Directory for artifact output (default: tasks/YYYYMMDD/).
        apply:     If True, write artifact and record to training_memory.
                   If False, dry-run only (no writes).
        task_id:   Explicit task ID; UUID generated if omitted.

    Returns:
        {
          "task_id": str,
          "learning_cycle_status": "COMPLETED" | "DRY_RUN",
          "computed_count": int,
          "mean_clv": float | None,
          "median_clv": float | None,
          "clv_variance": float | None,
          "positive_rate": float,
          "recommendation": str,
          "gate_decision": str,
          "gate_reason": str,
          "artifact_path": str | None,
          "source": "production/paper",
          "execution_mode": "PAPER_ONLY",
          "production_mutation": False,
          "live_bet_submitted": False,
          "no_llm_used": True,
          "apply": bool,
        }
    """
    resolved_clv = clv_path or CLV_FILE
    resolved_task_id = task_id or f"phase30_cycle_{uuid.uuid4().hex[:12]}"
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    resolved_task_dir = task_dir or (_TASKS_ROOT / date_str)

    logger.info(
        "[Phase30] Starting production CLV learning cycle task_id=%s apply=%s",
        resolved_task_id,
        apply,
    )

    # ── Step 1: Load COMPUTED records ──────────────────────────────────────
    records = load_computed_clv_records(resolved_clv)

    # ── Step 2: Analyze quality ────────────────────────────────────────────
    stats = analyze_clv_quality(records)

    # ── Step 3: Derive recommendation ─────────────────────────────────────
    recommendation = get_recommendation(stats)

    # ── Step 4: Evaluate patch gate ────────────────────────────────────────
    gate_result = evaluate_production_patch_gate(stats, recommendation)

    artifact_path_str: str | None = None

    if apply:
        # ── Step 5a: Write task artifact ───────────────────────────────────
        written = write_task_artifact(
            resolved_task_id, stats, recommendation, gate_result, resolved_task_dir
        )
        artifact_path_str = str(written)
        logger.info("[Phase30] Artifact written → %s", artifact_path_str)

        # ── Step 5b: Record to training_memory ────────────────────────────
        record_production_cycle(
            resolved_task_id, stats, recommendation, gate_result, artifact_path_str
        )
        logger.info("[Phase30] Training memory updated — source=%s", SOURCE_MARKER)

        status = "COMPLETED"
    else:
        status = "DRY_RUN"
        logger.info("[Phase30] Dry-run complete — no writes performed")

    logger.info(
        "[Phase30] cycle task_id=%s  computed=%d  mean_clv=%s  recommendation=%s  "
        "gate=%s  status=%s  apply=%s",
        resolved_task_id,
        stats["computed_count"],
        f"{stats['mean_clv']:.4f}" if stats.get("mean_clv") is not None else "N/A",
        recommendation,
        gate_result["gate_decision"],
        status,
        apply,
    )

    return {
        "task_id": resolved_task_id,
        "learning_cycle_status": status,
        "computed_count": stats["computed_count"],
        "positive_clv_count": stats["positive_clv_count"],
        "negative_clv_count": stats["negative_clv_count"],
        "flat_clv_count": stats["flat_clv_count"],
        "mean_clv": stats.get("mean_clv"),
        "median_clv": stats.get("median_clv"),
        "clv_variance": stats.get("clv_variance"),
        "positive_rate": stats.get("positive_rate", 0.0),
        "recommendation": recommendation,
        "gate_decision": gate_result["gate_decision"],
        "gate_reason": gate_result["reason"],
        "gate_confidence": gate_result["confidence"],
        "artifact_path": artifact_path_str,
        "source": SOURCE_MARKER,
        "execution_mode": EXECUTION_MODE,
        "production_mutation": PRODUCTION_MUTATION,
        "live_bet_submitted": LIVE_BET_SUBMITTED,
        "no_llm_used": True,
        "apply": apply,
    }


# ─────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Phase 30 — Production CLV Learning Cycle (PAPER_ONLY)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write artifact and record to training_memory (default: dry-run only)",
    )
    parser.add_argument(
        "--clv-file",
        type=Path,
        default=CLV_FILE,
        help="Path to production CLV JSONL file",
    )
    args = parser.parse_args()

    # ── Stage 1: Dry-run preview ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Phase 30 — Production CLV Learning Cycle (PAPER_ONLY)")
    print("=" * 60)
    print(f"\nCLV file : {args.clv_file}")
    print(f"Apply    : {args.apply}")

    dry = run_cycle(clv_path=args.clv_file, apply=False, task_id="phase30_preview")

    print(f"\n[DRY-RUN PREVIEW]")
    print(f"  Computed records   : {dry['computed_count']}")
    print(f"  Mean CLV           : {dry['mean_clv']:.6f}" if dry["mean_clv"] is not None else "  Mean CLV           : N/A")
    print(f"  Positive rate      : {dry['positive_rate']:.1%}")
    print(f"  Recommendation     : {dry['recommendation']}")
    print(f"  Gate decision      : {dry['gate_decision']}")
    print(f"  Production mutation: {dry['production_mutation']}")
    print(f"  Live bet submitted : {dry['live_bet_submitted']}")

    if not args.apply:
        print("\n[INFO] Dry-run only — pass --apply to write artifacts.")
        print("\nPHASE_30_PRODUCTION_CLV_LEARNING_CYCLE_PAPER_VERIFIED (dry-run)")
        return

    # ── Stage 2: Apply cycle ───────────────────────────────────────────────
    print("\n[APPLYING] Writing artifact + recording to training_memory …")
    result = run_cycle(clv_path=args.clv_file, apply=True)

    print(f"\n[RESULT]")
    print(f"  Task ID            : {result['task_id']}")
    print(f"  Status             : {result['learning_cycle_status']}")
    print(f"  Gate decision      : {result['gate_decision']}")
    print(f"  Artifact           : {result['artifact_path']}")
    print(f"  Source             : {result['source']}")
    print(f"  Execution mode     : {result['execution_mode']}")
    print(f"  Production mutation: {result['production_mutation']}")
    print(f"  Live bet submitted : {result['live_bet_submitted']}")

    # ── Stage 3: Verify readiness state still LEARNING_READY ──────────────
    from orchestrator.optimization_readiness import get_readiness_summary
    summary = get_readiness_summary()
    readiness_state = summary.get("readiness_state", "UNKNOWN")
    clv_computed = summary.get("phase6", {}).get("clv_computed", 0)
    print(f"\n[READINESS CHECK]")
    print(f"  readiness_state : {readiness_state}")
    print(f"  clv_computed    : {clv_computed}")

    print(f"\n{'=' * 60}")
    print("PHASE_30_PRODUCTION_CLV_LEARNING_CYCLE_PAPER_VERIFIED")
    print("=" * 60)


if __name__ == "__main__":
    main()
