"""
Phase 52 — SP Feature Injection Wrapper
========================================
使用 phase52_sp_context_v1 JSONL 重跑 Phase50 injection pipeline，
產出 phase52_sp_injected_v1 JSONL。

執行方式：
    python scripts/run_phase52_sp_feature_injection.py [--print] [--json] [--report]

輸出：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_injected_v1.jsonl
    reports/phase52_sp_feature_injection_YYYY-MM-DD.json（--report 模式）
    docs/feature_repair/phase52_sp_feature_injection_YYYY-MM-DD.md（--report 模式）

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    feature_effect_mode = MODEL_AFFECTING
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from wbc_backend.features.mlb_p0_feature_injection import (
    run_batch_injection,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
)
from orchestrator.phase49_feature_repair_evaluation import (
    FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY,
    FEATURE_REPAIR_NOT_EFFECTIVE,
    COLLECT_MORE_DATA,
    MODEL_AFFECTING,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_PHASE52_CONTEXT = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
_BASELINE_JSONL  = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
_OUTPUT_JSONL    = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase52_sp_injected_v1.jsonl"
_REPORTS_DIR     = _ROOT / "reports"
_DOCS_DIR        = _ROOT / "docs" / "feature_repair"

FEATURE_VERSION: str = "phase52_sp_injected_v1"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _compute_metrics(rows: list[dict]) -> dict:
    """計算 Brier Score / BSS / ECE / Log Loss。"""
    from wbc_backend.evaluation.metrics import (
        brier_score,
        brier_skill_score,
        expected_calibration_error,
        log_loss_score,
    )
    probs = [r.get("model_home_prob", 0.5) for r in rows]
    outcomes = [float(r.get("home_win", 0.5)) for r in rows]
    valid = [(p, o) for p, o in zip(probs, outcomes) if o in (0.0, 1.0)]
    if not valid:
        return {"n": 0, "brier": None, "bss": None, "ece": None, "log_loss": None}
    ps, os_ = zip(*valid)
    ps_list = list(ps)
    os_list = list(os_)
    bs = brier_score(ps_list, os_list)
    # BSS: 以 coin-flip baseline (0.25) 為基準
    _coin_flip_baseline = 0.25
    bss_val = brier_skill_score(bs, _coin_flip_baseline)
    ece_result = expected_calibration_error(ps_list, os_list)
    ece_val = ece_result["ece"] if isinstance(ece_result, dict) else float(ece_result)
    return {
        "n": len(valid),
        "brier": round(bs, 6),
        "bss": round(bss_val, 6) if bss_val is not None else None,
        "ece": round(ece_val, 6),
        "log_loss": round(log_loss_score(ps_list, os_list), 6),
    }


def _segment_metrics(rows: list[dict]) -> dict:
    """計算分段指標（month / odds_bucket / confidence / disagreement）。"""
    segments: dict[str, list[dict]] = {
        "month:2025-04": [], "month:2025-05": [],
        "month:2025-06": [], "month:2025-07": [],
        "odds_bucket:heavy_favorite": [], "odds_bucket:mid": [],
        "confidence:high_confidence": [], "confidence:low_confidence": [],
        "disagreement:high": [], "disagreement:low": [],
    }

    for r in rows:
        gd = r.get("game_date", "")[:7]
        if gd in ("2025-04", "2025-05", "2025-06", "2025-07"):
            segments[f"month:{gd}"].append(r)

        mkt = r.get("market_home_prob_no_vig", 0.5)
        if mkt > 0.65 or mkt < 0.35:
            segments["odds_bucket:heavy_favorite"].append(r)
        elif 0.45 <= mkt <= 0.55:
            segments["odds_bucket:mid"].append(r)

        mdl = r.get("model_home_prob", 0.5)
        conf = abs(mdl - 0.5)
        if conf > 0.15:
            segments["confidence:high_confidence"].append(r)
        elif conf < 0.08:
            segments["confidence:low_confidence"].append(r)

        disagreement = abs(mdl - mkt)
        if disagreement > 0.10:
            segments["disagreement:high"].append(r)
        elif disagreement < 0.03:
            segments["disagreement:low"].append(r)

    return {k: _compute_metrics(v) for k, v in segments.items()}


def _determine_gate(
    sp_avail_rate: float,
    baseline_m: dict,
    phase52_m: dict,
    seg_baseline: dict,
    seg_phase52: dict,
) -> tuple[str, str]:
    """決定 gate 與 rationale。"""
    if sp_avail_rate < 0.80:
        return (
            "DATA_GAP_REMAINS",
            f"sp_fip_delta availability {sp_avail_rate:.1%} < 80% 目標 — 資料缺口仍存在",
        )

    # 取得各指標
    base_bss = baseline_m.get("bss") or 0.0
    p52_bss  = phase52_m.get("bss") or 0.0
    delta_bss = round(p52_bss - base_bss, 6)

    apr_base = (seg_baseline.get("month:2025-04") or {}).get("bss") or 0.0
    apr_p52  = (seg_phase52.get("month:2025-04") or {}).get("bss") or 0.0
    delta_apr = apr_p52 - apr_base

    hf_base_ece = (seg_baseline.get("odds_bucket:heavy_favorite") or {}).get("ece") or 1.0
    hf_p52_ece  = (seg_phase52.get("odds_bucket:heavy_favorite") or {}).get("ece") or 1.0
    delta_hf_ece = hf_p52_ece - hf_base_ece

    hc_base_bss = (seg_baseline.get("confidence:high_confidence") or {}).get("bss") or 0.0
    hc_p52_bss  = (seg_phase52.get("confidence:high_confidence") or {}).get("bss") or 0.0
    hc_regression = hc_p52_bss < hc_base_bss - 0.001

    if (
        delta_apr > 0
        and delta_hf_ece < 0
        and not hc_regression
        and delta_bss > 0
    ):
        return (
            FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY,
            f"availability {sp_avail_rate:.1%}≥80%, "
            f"delta_bss={delta_bss:+.6f}, "
            f"delta_apr_bss={delta_apr:+.6f}, "
            f"delta_hf_ece={delta_hf_ece:+.6f} (改善)",
        )

    return (
        FEATURE_REPAIR_NOT_EFFECTIVE,
        f"availability {sp_avail_rate:.1%}≥80%, "
        f"delta_bss={delta_bss:+.6f} — 未達顯著改善",
    )


def run(
    phase52_context_path: Path = _PHASE52_CONTEXT,
    baseline_path: Path = _BASELINE_JSONL,
    output_path: Path = _OUTPUT_JSONL,
) -> dict:
    """
    Phase 52 SP Feature Injection。

    Returns:
        summary dict（含 gate, metric deltas, segment deltas）
    """
    logger.info("Phase 52 SP Feature Injection 開始")

    # 1. 載入 phase52 context（含更新後 sp_fip_delta）
    phase52_rows = _load_jsonl(phase52_context_path)
    logger.info("phase52 context 載入：%d 行", len(phase52_rows))

    # 2. 跑 Phase50 injection（複用既有 adapter）
    output_rows, summary = run_batch_injection(phase52_rows)
    logger.info("injection 完成：%d 行，調整 %d 行", summary.rows_total, summary.rows_adjusted)

    # 3. 計算 sp_fip_delta availability（來自輸入 rows）
    sp_avail = sum(
        1 for r in phase52_rows
        if r.get("p0_features", {}).get("sp_fip_delta_available", False)
    )
    sp_avail_rate = sp_avail / max(len(phase52_rows), 1)

    # 4. 載入 baseline 計算 metric delta
    baseline_rows = _load_jsonl(baseline_path)
    baseline_m = _compute_metrics(baseline_rows)
    phase52_m  = _compute_metrics(output_rows)

    delta_brier   = round((phase52_m.get("brier") or 0) - (baseline_m.get("brier") or 0), 6)
    delta_bss     = round((phase52_m.get("bss") or 0) - (baseline_m.get("bss") or 0), 6)
    delta_ece     = round((phase52_m.get("ece") or 0) - (baseline_m.get("ece") or 0), 6)
    delta_log_loss = round((phase52_m.get("log_loss") or 0) - (baseline_m.get("log_loss") or 0), 6)

    # 5. 分段指標
    seg_baseline = _segment_metrics(baseline_rows)
    seg_phase52  = _segment_metrics(output_rows)

    segment_deltas: dict[str, dict] = {}
    for seg_key in seg_baseline:
        b = seg_baseline[seg_key]
        p = seg_phase52[seg_key]
        segment_deltas[seg_key] = {
            "baseline_n":   b.get("n", 0),
            "baseline_bss": b.get("bss"),
            "baseline_ece": b.get("ece"),
            "phase52_n":    p.get("n", 0),
            "phase52_bss":  p.get("bss"),
            "phase52_ece":  p.get("ece"),
            "delta_bss": round((p.get("bss") or 0) - (b.get("bss") or 0), 6) if b.get("bss") is not None else None,
            "delta_ece": round((p.get("ece") or 0) - (b.get("ece") or 0), 6) if b.get("ece") is not None else None,
        }

    # 6. Gate decision
    gate, gate_rationale = _determine_gate(
        sp_avail_rate, baseline_m, phase52_m, seg_baseline, seg_phase52,
    )

    # 7. 寫出 output JSONL（更新 feature_version）
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in output_rows:
            if "p0_features" in row:
                row["p0_features"]["feature_version"] = FEATURE_VERSION
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    logger.info("寫出 %d 行至 %s", len(output_rows), output_path)

    result = {
        # 注入統計
        "rows_total": summary.rows_total,
        "rows_adjusted": summary.rows_adjusted,
        "rows_unchanged": summary.rows_unchanged,
        "adjusted_rate": round(summary.adjusted_rate, 4),
        "mean_abs_adjustment": round(summary.mean_abs_adjustment, 6),
        "max_abs_adjustment": round(summary.max_abs_adjustment, 6),
        "original_adjusted_correlation": round(summary.original_adjusted_correlation, 6),

        # 特徵觸發統計
        "early_season_triggered": summary.early_season_triggered,
        "park_factor_triggered": summary.park_factor_triggered,
        "sp_fip_triggered": summary.sp_fip_triggered,
        "cap_applied_count": summary.cap_applied_count,

        # SP availability
        "sp_fip_delta_available": sp_avail,
        "sp_fip_delta_availability_rate": round(sp_avail_rate, 4),

        # Feature mode
        "feature_effect_mode": MODEL_AFFECTING,
        "feature_version": FEATURE_VERSION,

        # Gate
        "gate_recommendation": gate,
        "gate_rationale": gate_rationale,

        # Metric delta
        "baseline_n":    baseline_m.get("n"),
        "baseline_brier": baseline_m.get("brier"),
        "baseline_bss":  baseline_m.get("bss"),
        "baseline_ece":  baseline_m.get("ece"),
        "baseline_log_loss": baseline_m.get("log_loss"),
        "phase52_n":     phase52_m.get("n"),
        "phase52_brier": phase52_m.get("brier"),
        "phase52_bss":   phase52_m.get("bss"),
        "phase52_ece":   phase52_m.get("ece"),
        "phase52_log_loss": phase52_m.get("log_loss"),
        "delta_brier":    delta_brier,
        "delta_bss":      delta_bss,
        "delta_ece":      delta_ece,
        "delta_log_loss": delta_log_loss,

        # 分段指標
        "segment_deltas": segment_deltas,

        # Hard rules
        "candidate_patch_created": False,
        "production_modified": False,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    logger.info("=== Phase 52 SP Feature Injection 完成 ===")
    logger.info("  feature_effect_mode: %s", MODEL_AFFECTING)
    logger.info("  gate:                %s", gate)
    logger.info("  sp_fip_availability: %.1f%%", sp_avail_rate * 100)
    logger.info("  adjusted_rate:       %.1f%%", summary.adjusted_rate * 100)
    logger.info("  delta_bss:           %+.6f", delta_bss)

    return result


def _write_report(result: dict) -> None:
    """寫出 JSON report 與 Markdown report。"""
    today = date.today().isoformat()

    # JSON report
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = _REPORTS_DIR / f"phase52_sp_feature_injection_{today}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info("JSON report: %s", json_path)

    # Markdown report
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = _DOCS_DIR / f"phase52_sp_feature_injection_{today}.md"
    gate = result["gate_recommendation"]
    avail_rate = result["sp_fip_delta_availability_rate"]
    adjusted_rate = result["adjusted_rate"]
    delta_bss = result["delta_bss"]

    lines = [
        f"# Phase 52 SP Feature Injection Report",
        f"",
        f"**日期**: {today}  ",
        f"**Feature Version**: {result['feature_version']}  ",
        f"**Gate**: `{gate}`  ",
        f"",
        f"## Executive Summary",
        f"",
        f"- sp_fip_delta_availability: **{avail_rate:.1%}**",
        f"- adjusted_rate: **{adjusted_rate:.1%}** (Phase50: 0.9%)",
        f"- delta_bss: **{delta_bss:+.6f}**",
        f"- gate: **{gate}**",
        f"",
        f"## Metric Delta",
        f"",
        f"| Metric | Baseline | Phase52 | Delta |",
        f"|--------|----------|---------|-------|",
        f"| Brier  | {result['baseline_brier']} | {result['phase52_brier']} | {result['delta_brier']:+.6f} |",
        f"| BSS    | {result['baseline_bss']} | {result['phase52_bss']} | {result['delta_bss']:+.6f} |",
        f"| ECE    | {result['baseline_ece']} | {result['phase52_ece']} | {result['delta_ece']:+.6f} |",
        f"| LogLoss| {result['baseline_log_loss']} | {result['phase52_log_loss']} | {result['delta_log_loss']:+.6f} |",
        f"",
        f"## Feature Trigger Statistics",
        f"",
        f"- rows_total: {result['rows_total']}",
        f"- rows_adjusted: {result['rows_adjusted']}",
        f"- sp_fip_triggered: {result['sp_fip_triggered']}",
        f"- park_factor_triggered: {result['park_factor_triggered']}",
        f"- early_season_triggered: {result['early_season_triggered']}",
        f"- cap_applied_count: {result['cap_applied_count']}",
        f"",
        f"## Critical Segment Deltas",
        f"",
    ]

    for seg_key, seg_data in result.get("segment_deltas", {}).items():
        d_bss = seg_data.get("delta_bss")
        d_ece = seg_data.get("delta_ece")
        d_bss_str = f"{d_bss:+.6f}" if d_bss is not None else "N/A"
        d_ece_str = f"{d_ece:+.6f}" if d_ece is not None else "N/A"
        lines.append(f"- **{seg_key}**: delta_bss={d_bss_str}, delta_ece={d_ece_str}")

    lines += [
        f"",
        f"## Gate Rationale",
        f"",
        f"{result['gate_rationale']}",
        f"",
        f"## Hard Rules",
        f"",
        f"- candidate_patch_created: `False`",
        f"- production_modified: `False`",
        f"",
        f"```",
        f"PHASE_52_STARTING_PITCHER_BACKFILL_VERIFIED",
        f"gate={gate}",
        f"sp_fip_delta_availability_rate={avail_rate:.4f}",
        f"adjusted_rate={adjusted_rate:.4f}",
        f"delta_bss={delta_bss:+.6f}",
        f"candidate_patch_created=False",
        f"production_modified=False",
        f"```",
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Markdown report: %s", md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 52 SP Feature Injection")
    parser.add_argument("--phase52-context", type=Path, default=_PHASE52_CONTEXT)
    parser.add_argument("--baseline",        type=Path, default=_BASELINE_JSONL)
    parser.add_argument("--output",          type=Path, default=_OUTPUT_JSONL)
    parser.add_argument("--print", action="store_true", dest="print_summary")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    result = run(
        phase52_context_path=args.phase52_context,
        baseline_path=args.baseline,
        output_path=args.output,
    )

    if args.report:
        _write_report(result)

    if args.print_summary or args.json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
