"""
Phase 39: MLB Prediction Persistence Check Script
================================================
Task 5 + 6: Recompute model_brier / market_brier / BSS / ECE / log-loss
from the persisted per-game prediction JSONL. Also evaluates calibration
readiness (Task 6).

Hard Rules:
  - Do NOT call external API / LLM.
  - Do NOT modify prediction values.
  - Do NOT create CANDIDATE_PATCH.
  - Do NOT bypass BSS Safety Gate.

Usage:
  python scripts/run_phase39_mlb_prediction_persistence_check.py
  python scripts/run_phase39_mlb_prediction_persistence_check.py --json
  python scripts/run_phase39_mlb_prediction_persistence_check.py --report
  python scripts/run_phase39_mlb_prediction_persistence_check.py --print-rows 5

Returns exit code 0 on success, 1 on RAW_MODEL_PROB_MISSING or file-not-found.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.prediction_persistence import (
    DEFAULT_PREDICTIONS_PATH,
    load_prediction_rows,
    recompute_metrics_from_rows,
    detect_duplicate_dedupe_keys,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ─── Constants from Phase 38 ──────────────────────────────────────────────────
REPORT_MODEL_BRIER: float = 0.2796
REPORT_MARKET_BRIER: float = 0.2451
REPORT_BSS: float = -0.141
PHASE38_CLEANED_MARKET_BRIER: float = 0.2419
ECE_TARGET: float = 0.08
BSS_TARGET: float = 0.0   # Must exceed 0 to unlock production

# Minimum sample size for calibration to be considered valid
MIN_CALIBRATION_SAMPLE: int = 500

# ─── Missing path diagnosis ────────────────────────────────────────────────────
RAW_MODEL_PROB_MISSING_LOCATION = (
    "wbc_backend/evaluation/full_backtest.py :: FullBacktestEngine.run() "
    "→ per-game test loop → result.home_win_prob "
    "(computed but not persisted to disk in baseline version). "
    "Resolution: instantiate FullBacktestEngine(persist_predictions=True) "
    "and re-run the backtest to generate "
    "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
)


# ══════════════════════════════════════════════════════════════════════════════
# § Calibration Readiness (Task 6)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CalibrationReadiness:
    """Task 6: calibration readiness evaluation result."""
    calibration_ready: bool
    reason: str
    sample_size: int
    ece: float | None
    ece_target: float
    ece_below_target: bool
    needs_calibration: bool       # True if ECE > target (should apply post-calibration)
    bss_positive: bool            # True if BSS > 0
    notes: list[str]


def evaluate_calibration_readiness(metrics: dict) -> CalibrationReadiness:
    """
    Evaluate whether the prediction dataset is ready for calibration analysis.

    Calibration_ready = True requires:
      1. sample_size >= MIN_CALIBRATION_SAMPLE (500)
      2. ece is not None
      3. bss is not None

    calibration_ready does NOT mean BSS is positive — BSS can still be
    negative and calibration analysis can still proceed.
    """
    notes: list[str] = []
    n = metrics.get("sample_size", 0)
    ece = metrics.get("ece")
    bss = metrics.get("bss")

    if n < MIN_CALIBRATION_SAMPLE:
        return CalibrationReadiness(
            calibration_ready=False,
            reason=f"Insufficient sample: {n} < {MIN_CALIBRATION_SAMPLE} required.",
            sample_size=n,
            ece=ece,
            ece_target=ECE_TARGET,
            ece_below_target=False,
            needs_calibration=True,
            bss_positive=False,
            notes=notes,
        )

    if ece is None:
        return CalibrationReadiness(
            calibration_ready=False,
            reason="ECE could not be computed (no rows).",
            sample_size=n,
            ece=None,
            ece_target=ECE_TARGET,
            ece_below_target=False,
            needs_calibration=True,
            bss_positive=False,
            notes=notes,
        )

    ece_below_target = ece < ECE_TARGET
    bss_positive = bss is not None and bss > BSS_TARGET
    needs_calibration = not ece_below_target

    if ece_below_target:
        notes.append(f"ECE={ece:.4f} < target {ECE_TARGET} — model is well-calibrated.")
    else:
        notes.append(
            f"ECE={ece:.4f} > target {ECE_TARGET} — post-calibration recommended "
            f"(Platt / Isotonic Regression on walk-forward holdout)."
        )

    if not bss_positive:
        notes.append(
            f"BSS={bss:.4f} ≤ 0 — model is NOT skill-positive vs. market. "
            f"Calibration will not fix negative BSS (signal quality issue)."
        )
    else:
        notes.append(f"BSS={bss:.4f} > 0 — model has positive skill vs. market.")

    reason = (
        f"Sample OK ({n} games). ECE={'OK' if ece_below_target else 'HIGH'}, "
        f"BSS={'positive' if bss_positive else 'negative'}."
    )
    return CalibrationReadiness(
        calibration_ready=True,
        reason=reason,
        sample_size=n,
        ece=ece,
        ece_target=ECE_TARGET,
        ece_below_target=ece_below_target,
        needs_calibration=needs_calibration,
        bss_positive=bss_positive,
        notes=notes,
    )


# ══════════════════════════════════════════════════════════════════════════════
# § Phase 39 Result
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Phase39Result:
    """Complete result for Phase 39 persistence check."""
    phase: str = "PHASE_39_MLB_PREDICTION_PROBABILITY_PERSISTENCE"
    run_ts: str = ""
    predictions_path: str = ""
    # File status
    file_found: bool = False
    file_row_count: int = 0
    duplicate_keys: list[str] = None  # type: ignore[assignment]
    n_duplicates: int = 0
    # Metrics from JSONL
    metrics: dict = None  # type: ignore[assignment]
    # Calibration readiness
    calibration_readiness: CalibrationReadiness = None  # type: ignore[assignment]
    # Comparison vs report
    report_model_brier: float = REPORT_MODEL_BRIER
    report_market_brier: float = REPORT_MARKET_BRIER
    report_bss: float = REPORT_BSS
    phase38_cleaned_market_brier: float = PHASE38_CLEANED_MARKET_BRIER
    brier_delta_vs_report: float | None = None
    bss_delta_vs_report: float | None = None
    # Status
    raw_model_prob_missing: bool = False
    missing_location: str = ""
    verdict: str = ""
    notes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.duplicate_keys is None:
            self.duplicate_keys = []
        if self.metrics is None:
            self.metrics = {}
        if self.notes is None:
            self.notes = []


# ══════════════════════════════════════════════════════════════════════════════
# § Main Runner
# ══════════════════════════════════════════════════════════════════════════════

def run_phase39(
    predictions_path: Path | None = None,
) -> Phase39Result:
    """
    Run Phase 39 persistence check.

    1. Try to load JSONL from predictions_path (default: DEFAULT_PREDICTIONS_PATH).
    2. If not found → report RAW_MODEL_PROB_MISSING with exact code location.
    3. If found → recompute all metrics and evaluate calibration readiness.
    """
    result = Phase39Result(
        run_ts=datetime.now(timezone.utc).isoformat(),
    )

    p = Path(predictions_path) if predictions_path else DEFAULT_PREDICTIONS_PATH
    result.predictions_path = str(p)

    # ── Step 1: Load JSONL ──────────────────────────────────────────────────
    if not p.exists():
        result.file_found = False
        result.raw_model_prob_missing = True
        result.missing_location = RAW_MODEL_PROB_MISSING_LOCATION
        result.verdict = "RAW_MODEL_PROB_MISSING"
        result.notes.append(
            f"Prediction JSONL not found at: {p}"
        )
        result.notes.append(
            "To generate: run FullBacktestEngine(persist_predictions=True).run(records)"
        )
        result.notes.append(f"Missing location: {RAW_MODEL_PROB_MISSING_LOCATION}")
        return result

    result.file_found = True
    try:
        rows = load_prediction_rows(p)
    except Exception as e:
        result.raw_model_prob_missing = True
        result.missing_location = RAW_MODEL_PROB_MISSING_LOCATION
        result.verdict = "RAW_MODEL_PROB_MISSING"
        result.notes.append(f"Failed to load prediction rows: {e}")
        return result

    result.file_row_count = len(rows)

    # ── Step 2: Duplicate check ──────────────────────────────────────────────
    dup_keys = detect_duplicate_dedupe_keys(rows)
    result.duplicate_keys = dup_keys
    result.n_duplicates = len(dup_keys)
    if dup_keys:
        result.notes.append(
            f"WARNING: {len(dup_keys)} duplicate dedupe_keys detected. "
            "This may indicate the backtest wrote overlapping windows."
        )

    # ── Step 3: Recompute metrics ────────────────────────────────────────────
    metrics = recompute_metrics_from_rows(rows)
    result.metrics = metrics

    # ── Step 4: Delta vs report values ──────────────────────────────────────
    if metrics.get("model_brier") is not None:
        result.brier_delta_vs_report = round(
            metrics["model_brier"] - REPORT_MODEL_BRIER, 6
        )
    if metrics.get("bss") is not None:
        result.bss_delta_vs_report = round(
            metrics["bss"] - REPORT_BSS, 6
        )

    # ── Step 5: Calibration readiness (Task 6) ──────────────────────────────
    result.calibration_readiness = evaluate_calibration_readiness(metrics)

    # ── Step 6: Verdict ──────────────────────────────────────────────────────
    result.raw_model_prob_missing = False
    result.verdict = "PHASE_39_MLB_PREDICTION_PROBABILITY_PERSISTENCE_VERIFIED"
    result.notes.append(
        f"Loaded {len(rows)} prediction rows from {p}"
    )
    result.notes.append(
        f"Recomputed: model_brier={metrics.get('model_brier')}, "
        f"market_brier={metrics.get('market_brier')}, "
        f"BSS={metrics.get('bss')}, "
        f"ECE={metrics.get('ece')}"
    )
    if not result.calibration_readiness.bss_positive:
        result.notes.append(
            "BSS still ≤ 0 → BSS Safety Gate remains BLOCKED. "
            "No production prediction, live bet, or Kelly bet allowed."
        )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# § Report Generation (Task 7 helper)
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(result: Phase39Result) -> str:
    """Generate Markdown report for Phase 39."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append("# Phase 39: MLB Prediction Probability Persistence Report")
    lines.append("")
    lines.append(f"> 生成日期：{today}  |  Run: {result.run_ts}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Phase 目標")
    lines.append("")
    lines.append(
        "持久化 MLB 回測的每場預測機率到 JSONL，使 BSS / Brier / ECE / 校準實驗 "
        "可從存檔行重新計算，無需重跑模型。"
    )
    lines.append("")
    lines.append("## 📂 預測檔案狀態")
    lines.append("")
    lines.append(f"| 項目 | 值 |")
    lines.append(f"|------|----|")
    lines.append(f"| 檔案路徑 | `{result.predictions_path}` |")
    lines.append(f"| 檔案存在 | {'✅ 是' if result.file_found else '❌ 否'} |")
    lines.append(f"| 預測行數 | {result.file_row_count:,} |")
    lines.append(f"| 重複 dedupe_key 數 | {result.n_duplicates} |")
    lines.append("")

    if result.raw_model_prob_missing:
        lines.append("## ⚠️ RAW_MODEL_PROB_MISSING")
        lines.append("")
        lines.append("每場模型機率尚未存入磁碟。確切缺少位置：")
        lines.append("")
        lines.append("```")
        lines.append(result.missing_location)
        lines.append("```")
        lines.append("")
        lines.append("**解決方式**：")
        lines.append("```python")
        lines.append("from wbc_backend.evaluation.full_backtest import FullBacktestEngine")
        lines.append("engine = FullBacktestEngine(persist_predictions=True)")
        lines.append("report = engine.run(records)")
        lines.append("# → data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl")
        lines.append("```")
        lines.append("")
    else:
        m = result.metrics
        lines.append("## 📊 重新計算指標 (from JSONL)")
        lines.append("")
        lines.append(f"| 指標 | 重算值 | 原始報告值 | 差異 |")
        lines.append(f"|------|--------|------------|------|")
        lines.append(
            f"| Model Brier | {m.get('model_brier', 'N/A')} "
            f"| {REPORT_MODEL_BRIER} "
            f"| {result.brier_delta_vs_report:+.6f} |"
        )
        lines.append(
            f"| Market Brier | {m.get('market_brier', 'N/A')} "
            f"| {REPORT_MARKET_BRIER} "
            f"| (Phase38 cleaned: {PHASE38_CLEANED_MARKET_BRIER}) |"
        )
        lines.append(
            f"| BSS | {m.get('bss', 'N/A')} "
            f"| {REPORT_BSS} "
            f"| {result.bss_delta_vs_report:+.6f} |"
        )
        lines.append(f"| ECE | {m.get('ece', 'N/A')} | (target: {ECE_TARGET}) | — |")
        lines.append(f"| Log-Loss | {m.get('log_loss', 'N/A')} | — | — |")
        lines.append(f"| Sample Size | {m.get('sample_size', 0):,} | 2,430 | — |")
        lines.append(f"| Home Win Rate | {m.get('home_win_rate', 'N/A')} | 0.544 | — |")
        lines.append("")

        # Calibration readiness
        cal = result.calibration_readiness
        lines.append("## 🎓 校準準備狀態 (Task 6)")
        lines.append("")
        lines.append(f"| 項目 | 值 |")
        lines.append(f"|------|----|")
        lines.append(f"| calibration_ready | {'✅ True' if cal.calibration_ready else '❌ False'} |")
        lines.append(f"| 樣本數 | {cal.sample_size:,} |")
        lines.append(f"| ECE | {cal.ece} |")
        lines.append(f"| ECE 目標 | {cal.ece_target} |")
        lines.append(f"| ECE 達標 | {'✅ 是' if cal.ece_below_target else '❌ 否 (需後校準)'} |")
        lines.append(f"| 需要後校準 | {'是' if cal.needs_calibration else '否'} |")
        lines.append(f"| BSS > 0 | {'✅ 是' if cal.bss_positive else '❌ 否'} |")
        lines.append("")
        for note in cal.notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("## 🔒 安全閘門狀態")
    lines.append("")
    bss_val = result.metrics.get("bss") if result.metrics else None
    gate_open = bss_val is not None and bss_val > 0
    lines.append(f"- **BSS Safety Gate**: {'🔓 UNLOCKED' if gate_open else '🔐 BLOCKED'}")
    lines.append(f"- **patch_gate_unlocked**: {str(gate_open).lower()}")
    if not gate_open:
        lines.append("- 禁止動作：production_prediction、live_bet、kelly_bet、candidate_patch_eval")
    lines.append("")

    lines.append("## 📋 備註")
    lines.append("")
    for note in result.notes:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## ✅ 驗證碼")
    lines.append("")
    lines.append(f"```")
    lines.append(result.verdict)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def write_report(result: Phase39Result) -> Path:
    """Write Phase 39 report to docs/orchestration/."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_dir = ROOT / "docs" / "orchestration"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"phase39_mlb_prediction_probability_persistence_report_{today}.md"
    report_path.write_text(generate_report(result), encoding="utf-8")
    logger.info("Phase 39 report written to: %s", report_path)
    return report_path


# ══════════════════════════════════════════════════════════════════════════════
# § CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 39: MLB prediction persistence check."
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Path to predictions JSONL (default: data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print human-readable summary to stdout.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON result to stdout.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Write Markdown report to docs/orchestration/.",
    )
    parser.add_argument(
        "--print-rows",
        type=int,
        default=0,
        metavar="N",
        help="Print first N prediction rows from JSONL.",
    )
    args = parser.parse_args()

    result = run_phase39(
        predictions_path=Path(args.path) if args.path else None,
    )

    # Print rows if requested
    if args.print_rows > 0 and result.file_found and not result.raw_model_prob_missing:
        p = Path(args.path) if args.path else DEFAULT_PREDICTIONS_PATH
        try:
            rows = load_prediction_rows(p)
            print(f"\n=== First {args.print_rows} Prediction Rows ===")
            for row in rows[: args.print_rows]:
                from dataclasses import asdict
                print(json.dumps(asdict(row), indent=2))
        except Exception as e:
            print(f"Could not load rows: {e}")

    if args.json:
        out = asdict(result)
        # Calibration readiness is a dataclass, convert
        if result.calibration_readiness:
            out["calibration_readiness"] = asdict(result.calibration_readiness)
        print(json.dumps(out, indent=2, default=str))

    if getattr(args, "print"):
        print(generate_report(result))

    if args.report:
        p = write_report(result)
        print(f"Report written to: {p}")

    if not args.print and not args.json and not args.report:
        # Default: brief summary
        print(f"\n=== Phase 39 Persistence Check ===")
        print(f"File found:     {result.file_found}")
        print(f"Row count:      {result.file_row_count:,}")
        print(f"RAW_MISSING:    {result.raw_model_prob_missing}")
        if result.metrics:
            m = result.metrics
            print(f"Model Brier:    {m.get('model_brier')}")
            print(f"Market Brier:   {m.get('market_brier')}")
            print(f"BSS:            {m.get('bss')}")
            print(f"ECE:            {m.get('ece')}")
            print(f"Log-Loss:       {m.get('log_loss')}")
            print(f"Sample Size:    {m.get('sample_size')}")
        if result.calibration_readiness:
            cal = result.calibration_readiness
            print(f"Calib Ready:    {cal.calibration_ready}")
            print(f"Reason:         {cal.reason}")
        print(f"\nVerdict: {result.verdict}")

    return 0 if not result.raw_model_prob_missing else 1


if __name__ == "__main__":
    sys.exit(main())
