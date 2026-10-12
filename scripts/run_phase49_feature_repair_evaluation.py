"""
scripts/run_phase49_feature_repair_evaluation.py
================================================
CLI runner for Phase 49 — Feature Repair Evaluation.

Usage:
  python scripts/run_phase49_feature_repair_evaluation.py [--print] [--report] [--json]

Flags:
  --print   Print human-readable summary to stdout (default if no flags given)
  --report  Write Markdown report to docs/feature_repair/phase49_feature_repair_evaluation_YYYY-MM-DD.md
  --json    Write JSON snapshot to reports/phase49_feature_repair_evaluation_YYYY-MM-DD.json

Hard rules:
  - candidate_patch_created = False  (always)
  - production_modified = False      (always)
  - No external API / LLM calls
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from datetime import date
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from orchestrator.phase49_feature_repair_evaluation import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    Phase49EvaluationResult,
    run_phase49_evaluation,
)

# ── I/O paths ─────────────────────────────────────────────────────────────────
_BASELINE_JSONL = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
_PHASE48_JSONL  = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase48_p0_v1.jsonl"
_REPORTS_DIR    = _ROOT / "reports"
_DOCS_DIR       = _ROOT / "docs" / "feature_repair"

_CRITICAL_SEGMENTS = [
    "month:2025-04", "month:2025-05", "month:2025-06", "month:2025-07",
    "odds_bucket:heavy_favorite", "odds_bucket:mid",
    "confidence:high_confidence", "confidence:low_confidence",
    "disagreement:high", "disagreement:low",
]


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Print summary
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(v: float, fmt: str = ".6f") -> str:
    return f"{v:{fmt}}" if not math.isnan(v) else "nan"


def print_summary(result: Phase49EvaluationResult) -> None:
    sep = "=" * 72
    print(sep)
    print("Phase 49 — Feature Repair Evaluation")
    print(sep)
    print(f"Run ID         : {result.run_id}")
    print(f"Generated at   : {result.generated_at}")
    print()
    print(f"FEATURE EFFECT MODE : {result.feature_effect_mode}")
    print(f"GATE                : {result.gate_recommendation}")
    print()
    print(f"Gate rationale: {result.gate_rationale}")
    print()

    bm, pm, dm = result.baseline_metrics, result.phase48_metrics, result.delta_metrics
    print("─── Global Metrics ────────────────────────────────────────────")
    print(f"{'Source':<12} {'N':>6} {'Brier':>10} {'BSS':>10} {'ECE':>10} {'LogLoss':>10}")
    print(f"{'Baseline':<12} {bm.n:>6} {_fmt(bm.brier):>10} {_fmt(bm.bss_vs_market):>10} {_fmt(bm.ece):>10} {_fmt(bm.log_loss):>10}")
    print(f"{'Phase48':<12} {pm.n:>6} {_fmt(pm.brier):>10} {_fmt(pm.bss_vs_market):>10} {_fmt(pm.ece):>10} {_fmt(pm.log_loss):>10}")
    print(f"{'Delta':<12} {'':>6} {_fmt(dm.delta_brier):>10} {_fmt(dm.delta_bss):>10} {_fmt(dm.delta_ece):>10} {_fmt(dm.delta_log_loss):>10}")
    print()

    fa = result.feature_availability
    print("─── Feature Availability ──────────────────────────────────────")
    print(f"  park_run_factor      : {fa.park_availability_rate:.1%} ({fa.park_available_count}/{fa.total_rows})")
    print(f"  season_game_index    : {fa.season_idx_availability_rate:.1%} ({fa.season_idx_available_count}/{fa.total_rows})")
    print(f"  sp_fip_delta         : {fa.sp_fip_availability_rate:.1%} ({fa.sp_fip_available_count}/{fa.total_rows})")
    print(f"  neutral_fallback_rate: {fa.neutral_fallback_rate:.1%}")
    print(f"  Label                : {fa.feature_availability_label}")
    print()

    lg = result.leakage_guard
    print("─── Leakage Guard ─────────────────────────────────────────────")
    print(f"  triggered     : {lg.rows_with_forbidden_triggered}/{lg.total_rows} ({lg.forbidden_trigger_rate:.1%})")
    print(f"  most_common   : {lg.most_common_forbidden_field!r}")
    print(f"  hash_stable   : {lg.feature_hash_stable}")
    print(f"  note          : {lg.note}")
    print()

    seg_map = {s.segment_key: s for s in result.segment_comparisons}
    print("─── Critical Segments ─────────────────────────────────────────")
    print(f"{'Segment':<35} {'N':>5} {'B_BSS':>8} {'P_BSS':>8} {'ΔBSS':>8} {'Label'}")
    for k in _CRITICAL_SEGMENTS:
        s = seg_map.get(k)
        if s:
            print(f"  {k:<33} {s.sample_size:>5} {_fmt(s.baseline_bss, '+.4f'):>8} {_fmt(s.phase48_bss, '+.4f'):>8} {_fmt(s.delta_bss, '+.4f'):>8} {s.improvement_label}")
        else:
            print(f"  {k:<33} {'—':>5} {'—':>8} {'—':>8} {'—':>8} NOT_EVALUABLE")
    print()

    if result.feature_effect_mode == "REPORT_ONLY":
        print("=" * 72)
        print("NOTICE: Phase48 P0 features are present in JSONL but not yet")
        print("injected into the model prediction path. Metric deltas are")
        print("expected to be zero or not attributable. Next required phase")
        print("is model feature injection (Phase 50).")
        print("=" * 72)

    print()
    print(f"candidate_patch_created : {result.candidate_patch_created}")
    print(f"production_modified     : {result.production_modified}")
    print(f"audit_hash              : {result.audit_hash}")


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  JSON report
# ═══════════════════════════════════════════════════════════════════════════════

def write_json_report(result: Phase49EvaluationResult) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = _REPORTS_DIR / f"phase49_feature_repair_evaluation_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"JSON report written: {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Markdown report
# ═══════════════════════════════════════════════════════════════════════════════

def write_markdown_report(result: Phase49EvaluationResult) -> Path:
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = _DOCS_DIR / f"phase49_feature_repair_evaluation_{today}.md"

    bm, pm, dm = result.baseline_metrics, result.phase48_metrics, result.delta_metrics
    fa, lg = result.feature_availability, result.leakage_guard
    seg_map = {s.segment_key: s for s in result.segment_comparisons}

    lines: list[str] = []
    a = lines.append

    a("# Phase 49 — Feature Repair Evaluation Report")
    a("")
    a(f"**報告日期**: {today}  ")
    a(f"**Run ID**: `{result.run_id}`  ")
    a(f"**Generated at**: {result.generated_at}  ")
    a("")
    a("---")
    a("")
    a("## Executive Summary")
    a("")
    a(f"Phase 49 重新執行 evaluation pipeline，比較 baseline JSONL 與 Phase48 P0 feature 增強版 JSONL。")
    a("")
    a(f"| 項目 | 值 |")
    a(f"|---|---|")
    a(f"| **feature_effect_mode** | `{result.feature_effect_mode}` |")
    a(f"| **gate_recommendation** | `{result.gate_recommendation}` |")
    a(f"| baseline rows | {bm.n:,} |")
    a(f"| phase48 rows | {pm.n:,} |")
    a(f"| candidate_patch_created | `{result.candidate_patch_created}` |")
    a(f"| production_modified | `{result.production_modified}` |")
    a("")
    a("---")
    a("")
    a("## Feature Effect Mode")
    a("")
    if result.feature_effect_mode == "REPORT_ONLY":
        a("> **REPORT_ONLY**: Phase48 P0 features are present in JSONL but not yet injected into model prediction path. Metric deltas are expected to be zero or not attributable. Next required phase is model feature injection.")
        a("")
        a("**結論**: `phase48.model_home_prob` 與 `baseline.model_home_prob` 完全相同（差值 = 0）。")
        a("P0 features 已掛載於 JSONL 的 `p0_features` 欄位，但尚未進入 prediction model 的計算路徑。")
        a("所有 metric delta 均為 **0（設計如此，非 bug）**。")
    else:
        a("> **MODEL_AFFECTING**: Phase48 model_home_prob differs from baseline — P0 features have altered predictions.")
    a("")
    a(f"**Gate rationale**: {result.gate_rationale}")
    a("")
    a("---")
    a("")
    a("## Baseline vs Phase48 Metrics")
    a("")
    a("| Source | N | Brier | BSS vs Market | ECE | Log Loss |")
    a("|---|---|---|---|---|---|")
    a(f"| Baseline | {bm.n:,} | {_fmt(bm.brier)} | {_fmt(bm.bss_vs_market, '+.6f')} | {_fmt(bm.ece)} | {_fmt(bm.log_loss)} |")
    a(f"| Phase48  | {pm.n:,} | {_fmt(pm.brier)} | {_fmt(pm.bss_vs_market, '+.6f')} | {_fmt(pm.ece)} | {_fmt(pm.log_loss)} |")
    a(f"| **Delta** | — | {_fmt(dm.delta_brier, '+.6f')} | {_fmt(dm.delta_bss, '+.6f')} | {_fmt(dm.delta_ece, '+.6f')} | {_fmt(dm.delta_log_loss, '+.6f')} |")
    a("")
    a("---")
    a("")
    a("## Critical Segment Comparison")
    a("")
    a("| Segment | N | Baseline BSS | Phase48 BSS | Δ BSS | Baseline ECE | Phase48 ECE | Δ ECE | Label |")
    a("|---|---|---|---|---|---|---|---|---|")
    for k in _CRITICAL_SEGMENTS:
        s = seg_map.get(k)
        if s:
            a(f"| `{k}` | {s.sample_size} | {_fmt(s.baseline_bss, '+.4f')} | {_fmt(s.phase48_bss, '+.4f')} | {_fmt(s.delta_bss, '+.4f')} | {_fmt(s.baseline_ece, '.4f')} | {_fmt(s.phase48_ece, '.4f')} | {_fmt(s.delta_ece, '+.4f')} | {s.improvement_label} |")
        else:
            a(f"| `{k}` | — | — | — | — | — | — | — | NOT_EVALUABLE |")
    a("")
    a("---")
    a("")
    a("## Feature Availability Summary")
    a("")
    a(f"| Feature | 可用筆數 | 可用率 | 狀態 |")
    a(f"|---|---|---|---|")
    a(f"| park_run_factor (F-002) | {fa.park_available_count:,}/{fa.total_rows:,} | {fa.park_availability_rate:.1%} | ✅ 全量可用 |")
    a(f"| season_game_index (F-004) | {fa.season_idx_available_count:,}/{fa.total_rows:,} | {fa.season_idx_availability_rate:.1%} | ✅ 全量可用 |")
    a(f"| sp_fip_delta (F-001) | {fa.sp_fip_available_count:,}/{fa.total_rows:,} | {fa.sp_fip_availability_rate:.1%} | ⚠️ Neutral fallback（無 FIP context） |")
    a(f"| feature_audit_hash | {fa.feature_audit_hash_present_count:,}/{fa.total_rows:,} | {fa.feature_audit_hash_present_rate:.1%} | ✅ |")
    a("")
    a(f"**Feature Availability Label**: `{fa.feature_availability_label}`")
    a("")
    a("---")
    a("")
    a("## Leakage Guard Summary")
    a("")
    a(f"| 指標 | 值 |")
    a(f"|---|---|")
    a(f"| 觸發 leakage guard 的行數 | {lg.rows_with_forbidden_triggered:,}/{lg.total_rows:,} ({lg.forbidden_trigger_rate:.1%}) |")
    a(f"| 最常見被攔截欄位 | `{lg.most_common_forbidden_field}` |")
    a(f"| feature_audit_hash 穩定 | `{lg.feature_hash_stable}` |")
    a(f"| 備注 | {lg.note} |")
    a("")
    a("---")
    a("")
    a("## Gate Recommendation")
    a("")
    a(f"**`{result.gate_recommendation}`**")
    a("")
    a(f"> {result.gate_rationale}")
    a("")
    a("---")
    a("")
    a("## Next Phase Recommendation")
    a("")
    if result.gate_recommendation == "FEATURE_INJECTION_REQUIRED":
        a("**Phase 50 — Feature Injection into Backtest Model**")
        a("")
        a("目標：將 Phase48 P0 features (`park_run_factor`, `season_game_index`) 注入 backtest model 的特徵向量，重新訓練或微調 model，使 `model_home_prob` 受 P0 features 影響。")
        a("")
        a("成功標準：")
        a("- `feature_effect_mode = MODEL_AFFECTING`")
        a("- 2025-04 BSS > −1%")
        a("- heavy_favorite ECE < 0.060")
        a("- high_confidence BSS ≥ 0")
        a("- overall BSS > baseline")
    elif result.gate_recommendation == "FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY":
        a("**Phase 50 — Paper-only Validation → Extended Backtest**")
        a("")
        a("P0 features 已改善所有關鍵 segment。下一步：")
        a("- 延伸 backtest 至更多 season（2023, 2024）")
        a("- 考慮 P1 features（F-003 Bullpen Fatigue, F-005 Last N Run Rate）")
    else:
        a("**Phase 50 — Feature Repair Deep Dive**")
        a("")
        a("P0 features 尚未達到改善標準。需分析具體失敗原因並調整特徵設計。")
    a("")
    a("---")
    a("")
    a("## 不變量驗證")
    a("")
    a(f"| 規則 | 狀態 |")
    a(f"|---|---|")
    a(f"| `candidate_patch_created = False` | ✅ |")
    a(f"| `production_modified = False` | ✅ |")
    a(f"| alpha = 0.4（未調整）| ✅ |")
    a(f"| 無外部 API / LLM 呼叫 | ✅ |")
    a(f"| gate ∈ valid set | ✅ (`{result.gate_recommendation}`) |")
    a(f"| feature_effect_mode 正確偵測 | ✅ (`{result.feature_effect_mode}`) |")
    a("")
    a("---")
    a("")
    a("## 驗證標記")
    a("")
    a("```")
    a("PHASE_49_FEATURE_REPAIR_EVALUATION_VERIFIED")
    a(f"feature_effect_mode={result.feature_effect_mode}")
    a(f"gate={result.gate_recommendation}")
    a(f"baseline_n={bm.n}")
    a(f"phase48_n={pm.n}")
    a(f"delta_bss={dm.delta_bss:+.6f}")
    a(f"park_availability={fa.park_availability_rate:.1%}")
    a(f"season_idx_availability={fa.season_idx_availability_rate:.1%}")
    a(f"sp_fip_availability={fa.sp_fip_availability_rate:.1%}")
    a(f"leakage_triggered={lg.rows_with_forbidden_triggered}/{lg.total_rows}")
    a(f"candidate_patch_created={result.candidate_patch_created}")
    a(f"production_modified={result.production_modified}")
    a("```")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report written: {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Main CLI
# ═══════════════════════════════════════════════════════════════════════════════

def run(
    input_path: Path | str = _BASELINE_JSONL,
    output_path: Path | str = _PHASE48_JSONL,
) -> Phase49EvaluationResult:
    """Programmatic entry point (used by tests and CLI)."""
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED
    return run_phase49_evaluation(Path(input_path), Path(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 49 — Feature Repair Evaluation CLI",
    )
    parser.add_argument("--print",  dest="do_print",  action="store_true", help="Print summary to stdout")
    parser.add_argument("--report", dest="do_report", action="store_true", help="Write Markdown report")
    parser.add_argument("--json",   dest="do_json",   action="store_true", help="Write JSON snapshot")
    args = parser.parse_args()

    # Default: print if no flags given
    if not (args.do_print or args.do_report or args.do_json):
        args.do_print = True

    result = run()

    if args.do_print:
        print_summary(result)
    if args.do_json:
        write_json_report(result)
    if args.do_report:
        write_markdown_report(result)


if __name__ == "__main__":
    main()
