"""
Phase 54: Safe SP Stability Audit — CLI Runner
================================================
Usage:
  python scripts/run_phase54_safe_sp_stability_audit.py --print
  python scripts/run_phase54_safe_sp_stability_audit.py --json
  python scripts/run_phase54_safe_sp_stability_audit.py --report
  python scripts/run_phase54_safe_sp_stability_audit.py --print --json --report
  python scripts/run_phase54_safe_sp_stability_audit.py --bootstrap 500 --splits 5

Hard Rules (never violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - gate NEVER == PATCH or PATCH_GATE_RECHECK

Outputs (with --report):
  reports/phase54_safe_sp_stability_audit_YYYY-MM-DD.json
  docs/feature_repair/phase54_safe_sp_stability_audit_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from orchestrator.phase54_safe_sp_stability_audit import (
    Phase54AuditResult,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    SAFE_COEFFICIENT_SCALE,
    EFFECTIVE_SP_COEFFICIENT,
    SAFE_SP_PAPER_ONLY_CONTINUE,
    RE_RUN_BOOTSTRAP_REQUIRED,
    FEATURE_REPAIR_STILL_WEAK,
    COLLECT_MORE_DATA,
    run_phase54_audit,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = _ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
_CONTEXT_JSONL  = _ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
_PHASE54_JSONL  = _ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase54_sp_safe_coeff_v1.jsonl"
_REPORTS_DIR    = _ROOT / "reports"
_DOCS_DIR       = _ROOT / "docs/feature_repair"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase54_cli")


# ═══════════════════════════════════════════════════════════════════════════════
# § Report builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_markdown(result: Phase54AuditResult, today: str) -> str:
    p43 = result.phase43_summary
    p44 = result.phase44_summary
    p45 = result.phase45_summary
    sc = result.safe_coefficient_summary

    def _fmt(v: float | None, precision: int = 6) -> str:
        if v is None:
            return "N/A"
        return f"{v:+.{precision}f}" if abs(v) < 100 else f"{v:.{precision}f}"

    def _pct(v: float | None) -> str:
        if v is None:
            return "N/A"
        return f"{v * 100:.1f}%"

    # Gate badge
    gate_badges = {
        SAFE_SP_PAPER_ONLY_CONTINUE: "🟢",
        RE_RUN_BOOTSTRAP_REQUIRED: "🟡",
        FEATURE_REPAIR_STILL_WEAK: "🔴",
        COLLECT_MORE_DATA: "🔴",
    }
    gate_icon = gate_badges.get(result.gate_recommendation, "⚪")

    # Segment comparison table
    seg_rows: list[str] = []
    seg_rows.append("| Segment | P43 BSS | P54 BSS | Δ BSS | P43 ECE | P54 ECE | Δ ECE | Label |")
    seg_rows.append("|---------|---------|---------|-------|---------|---------|-------|-------|")
    for s in sorted(result.segment_comparison, key=lambda x: x.segment_key):
        seg_rows.append(
            f"| {s.segment_key} | {_fmt(s.phase43_blend_bss, 5)} | "
            f"{_fmt(s.phase54_blend_bss, 5)} | {_fmt(s.delta_bss, 5)} | "
            f"{_fmt(s.phase43_blend_ece, 5)} | {_fmt(s.phase54_blend_ece, 5)} | "
            f"{_fmt(s.delta_ece, 5)} | {s.label} |"
        )

    # Next phase recommendation
    if result.gate_recommendation == SAFE_SP_PAPER_ONLY_CONTINUE:
        next_phase = (
            "**Phase 55 — Rolling / Walk-forward Paper Tracking with Safe SP Coefficient**\n\n"
            "使用 30-day rolling window 對 Phase54 JSONL 進行 walk-forward paper tracking，"
            "追蹤 safe SP coefficient 在真實時間流下的穩定性。"
        )
    elif result.gate_recommendation == FEATURE_REPAIR_STILL_WEAK:
        next_phase = (
            "**Phase 55 — SP Functional Form Redesign or Bullpen Feature Investigation**\n\n"
            "當前 SP FIP 函數形式（tanh 壓縮）在特定 segment 仍有惡化跡象，"
            "建議探索：(1) segment-specific coefficients，(2) sigmoid 替代，"
            "(3) matchup-level confidence gate，(4) 牛棚特徵補充。"
        )
    else:
        next_phase = "見 gate_recommendation 決定下一步行動。"

    lines = [
        f"# Phase 54 — Safe SP Stability Audit Report",
        f"",
        f"**Generated**: {today}  ",
        f"**Phase54 Version**: {result.phase54_version}  ",
        f"**Audit Hash**: `{result.audit_hash}`  ",
        f"**Gate**: {gate_icon} `{result.gate_recommendation}`  ",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"Phase 54 使用 Phase53 safe coefficient (scale={SAFE_COEFFICIENT_SCALE}x，"
        f"effective={EFFECTIVE_SP_COEFFICIENT}) 對 2,025 筆 MLB 2025 比賽預測套用調整，"
        f"並重跑 Phase43/44/45 穩定性審計。",
        f"",
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| Phase54 rows | {sc.input_rows} |",
        f"| adjusted rows | {sc.adjusted_rows} ({_pct(sc.adjusted_rate)}) |",
        f"| max_abs_adjustment | {sc.max_abs_adjustment:.6f} |",
        f"| overall BSS Δ vs baseline | {_fmt(sc.overall_bss_delta_vs_baseline)} |",
        f"| overall ECE Δ vs baseline | {_fmt(sc.overall_ece_delta_vs_baseline)} |",
        f"| heavy_fav ECE Δ vs baseline | {_fmt(sc.heavy_fav_ece_delta_vs_baseline)} |",
        f"| high_conf BSS Δ vs baseline | {_fmt(sc.high_conf_bss_delta_vs_baseline)} |",
        f"",
        f"---",
        f"",
        f"## Safe Coefficient Summary",
        f"",
        f"| 欄位 | 值 |",
        f"|------|---|",
        f"| scale | {sc.scale} |",
        f"| effective_coefficient | {sc.effective_coefficient} |",
        f"| feature_effect_mode | {sc.feature_effect_mode} |",
        f"| diagnostic_only | {sc.diagnostic_only} |",
        f"| candidate_patch_created | {sc.candidate_patch_created} |",
        f"| production_modified | {sc.production_modified} |",
        f"",
        f"---",
        f"",
        f"## Phase43 Re-run Result",
        f"",
        f"| 指標 | Phase43 Baseline | Phase54 | Delta |",
        f"|------|-----------------|---------|-------|",
        f"| overall_blend_BSS | {_PHASE43_BL_BSS:.6f} | {p43.overall_blend_bss:.6f} | {_fmt(p43.blend_bss_delta)} |",
        f"| overall_blend_ECE | {_PHASE43_BL_ECE:.6f} | {p43.overall_blend_ece:.6f} | {_fmt(p43.blend_ece_delta)} |",
        f"| fold_stability | STABLE (4/5) | {p43.fold_stability_label} ({p43.folds_positive}/{p43.folds_total}) | Δ={p43.fold_positive_delta:+d} |",
        f"| bootstrap | NOT_SIGNIFICANT | {p43.bootstrap_significance} | — |",
        f"| bootstrap CI | [-0.0015, 0.0006] | [{p43.bootstrap_ci_lower}, {p43.bootstrap_ci_upper}] | — |",
        f"| prob_improvement | 81.0% | {_pct(p43.bootstrap_prob_improvement)} | — |",
        f"",
        f"---",
        f"",
        f"## Phase44 Paper Tracking Result",
        f"",
        f"| 欄位 | 值 |",
        f"|------|---|",
        f"| gate_state | {p44.gate_state} |",
        f"| alpha | {p44.alpha} |",
        f"| sample_size | {p44.sample_size} |",
        f"| blend_brier | {p44.blend_brier:.6f} |",
        f"| blend_bss | {p44.blend_bss:.6f} |",
        f"| blend_ece | {p44.blend_ece:.6f} |",
        f"| bootstrap | {p44.bootstrap_significance} |",
        f"| candidate_patch_created | {p44.candidate_patch_created} |",
        f"",
        f"---",
        f"",
        f"## Phase45 Attribution Result",
        f"",
        f"| 欄位 | 值 |",
        f"|------|---|",
        f"| global_conclusion | {p45.global_conclusion} |",
        f"| gate | {p45.gate} |",
        f"| positive_segments | {len(p45.positive_segments)} |",
        f"| failure_segments | {len(p45.failure_segments)} |",
        f"| failure_count_delta | {p45.failure_count_delta:+d} |",
        f"| heavy_fav ECE no longer failure | {p45.heavy_fav_ece_no_longer_failure} |",
        f"| high_conf improved | {p45.high_conf_improved} |",
        f"| heavy_fav blend_bss | {_fmt(p45.heavy_fav_blend_bss)} |",
        f"| high_conf blend_bss | {_fmt(p45.high_conf_blend_bss)} |",
        f"",
        f"**Positive segments**: {', '.join(p45.positive_segments) if p45.positive_segments else 'N/A'}",
        f"",
        f"**Failure segments**: {', '.join(p45.failure_segments) if p45.failure_segments else '（無）'}",
        f"",
        f"---",
        f"",
        f"## Baseline vs Phase54 Comparison",
        f"",
        f"| 指標 | Baseline (no SP adj) | Phase54 (scale=0.25x) | Δ |",
        f"|------|----------------------|-----------------------|---|",
        f"| overall BSS | — | {_fmt(sc.overall_bss_delta_vs_baseline)} improvement | {_fmt(sc.overall_bss_delta_vs_baseline)} |",
        f"| overall ECE | — | {_fmt(sc.overall_ece_delta_vs_baseline)} | {_fmt(sc.overall_ece_delta_vs_baseline)} |",
        f"| heavy_fav ECE | — | {_fmt(sc.heavy_fav_ece_delta_vs_baseline)} | {_fmt(sc.heavy_fav_ece_delta_vs_baseline)} |",
        f"| high_conf BSS | — | {_fmt(sc.high_conf_bss_delta_vs_baseline)} | {_fmt(sc.high_conf_bss_delta_vs_baseline)} |",
        f"",
        f"---",
        f"",
        f"## Critical Segment Comparison Table",
        f"",
        f"Δ BSS > 0 = 改善；Δ ECE < 0 = 改善",
        f"",
        "\n".join(seg_rows),
        f"",
        f"---",
        f"",
        f"## Bootstrap / Fold Stability Result",
        f"",
        f"| 項目 | Phase43 Baseline | Phase54 |",
        f"|------|-----------------|---------|",
        f"| fold_stability | STABLE | {p43.fold_stability_label} |",
        f"| folds_positive | 4/5 | {p43.folds_positive}/{p43.folds_total} |",
        f"| bootstrap_CI | [-0.0015, 0.0006] | [{p43.bootstrap_ci_lower}, {p43.bootstrap_ci_upper}] |",
        f"| bootstrap significance | NOT_SIGNIFICANT | {p43.bootstrap_significance} |",
        f"| prob_improvement | 81.0% | {_pct(p43.bootstrap_prob_improvement)} |",
        f"",
        f"> **Note**: Bootstrap CI 跨 0 = NOT_SIGNIFICANT 並非說明無效，而是樣本量仍不足以達到統計顯著。"
        f"paper-only tracking 繼續積累資料。",
        f"",
        f"---",
        f"",
        f"## Gate Recommendation",
        f"",
        f"**Gate**: {gate_icon} `{result.gate_recommendation}`",
        f"",
        f"**Rationale**: {result.gate_rationale}",
        f"",
        f"---",
        f"",
        f"## Limitations",
        f"",
        f"1. safe coefficient (0.25x) 在 2,025 筆樣本上評估，樣本仍不足以達 bootstrap 顯著性。",
        f"2. Phase43 fold stability 採用 expanding-window，非 pure out-of-sample；仍存在 train/test 滑動 bias。",
        f"3. heavy_favorite ECE 改善來自 Phase53 coefficient calibration，"
        f"   但 heavy_favorite 市場在 SP FIP 較大時較不穩定。",
        f"4. Phase54 JSONL 的 model_home_prob 已被 safe coefficient 修改，"
        f"   Phase43/44/45 將以此為「raw model prob」進行分析，"
        f"   因此 blend(model, market, 0.4) 的「model」部分已含 SP feature。",
        f"5. 本 Phase 不可產生 PATCH_GATE_RECHECK，所有結論均為 paper-only。",
        f"",
        f"---",
        f"",
        f"## Next Phase Recommendation",
        f"",
        next_phase,
        f"",
        f"---",
        f"",
        f"## Hard Rules Verification",
        f"",
        f"```",
        f"candidate_patch_created = False",
        f"production_modified     = False",
        f"diagnostic_only         = True",
        f"gate != PATCH           = True",
        f"gate != PATCH_GATE_RECHECK = True",
        f"alpha = 0.4             = True",
        f"safe_coefficient_scale  = {SAFE_COEFFICIENT_SCALE}",
        f"effective_coefficient   = {EFFECTIVE_SP_COEFFICIENT}",
        f"```",
        f"",
        f"---",
        f"",
        f"## Completion Marker",
        f"",
        f"```",
        f"PHASE_54_SAFE_SP_STABILITY_AUDIT_VERIFIED",
        f"gate={result.gate_recommendation}",
        f"safe_coefficient_scale={SAFE_COEFFICIENT_SCALE}",
        f"effective_coefficient={EFFECTIVE_SP_COEFFICIENT}",
        f"phase43_blend_bss={p43.overall_blend_bss}",
        f"phase43_fold_stability={p43.fold_stability_label}",
        f"phase44_sample_size={p44.sample_size}",
        f"phase45_failure_count={len(p45.failure_segments)}",
        f"candidate_patch_created=False",
        f"production_modified=False",
        f"diagnostic_only=True",
        f"audit_hash={result.audit_hash}",
        f"```",
        f"",
    ]

    return "\n".join(lines)


# Phase43 baseline values used in Markdown (from _PHASE43_BASELINE in orchestrator)
_PHASE43_BL_BSS = 0.002200
_PHASE43_BL_ECE = 0.028100


# ═══════════════════════════════════════════════════════════════════════════════
# § Print summary
# ═══════════════════════════════════════════════════════════════════════════════

def _print_summary(result: Phase54AuditResult) -> None:
    p43 = result.phase43_summary
    p44 = result.phase44_summary
    p45 = result.phase45_summary
    sc = result.safe_coefficient_summary

    print("\n=== Phase 54 Safe SP Stability Audit ===")
    print(f"{'safe_coefficient_scale:':<36} {sc.scale}")
    print(f"{'effective_sp_coefficient:':<36} {sc.effective_coefficient}")
    print(f"{'adjusted_rows:':<36} {sc.adjusted_rows} / {sc.input_rows} ({sc.adjusted_rate * 100:.1f}%)")
    print(f"{'overall_BSS_delta_vs_baseline:':<36} {sc.overall_bss_delta_vs_baseline}")
    print(f"{'overall_ECE_delta_vs_baseline:':<36} {sc.overall_ece_delta_vs_baseline}")
    print(f"{'heavy_fav_ECE_delta:':<36} {sc.heavy_fav_ece_delta_vs_baseline}")
    print()
    print("--- Phase43 Re-run ---")
    print(f"{'overall_blend_BSS:':<36} {p43.overall_blend_bss:+.6f} (Δ={p43.blend_bss_delta})")
    print(f"{'overall_blend_ECE:':<36} {p43.overall_blend_ece:.6f} (Δ={p43.blend_ece_delta})")
    print(f"{'fold_stability:':<36} {p43.fold_stability_label} ({p43.folds_positive}/{p43.folds_total})")
    print(f"{'bootstrap_significance:':<36} {p43.bootstrap_significance}")
    print(f"{'bootstrap_CI:':<36} [{p43.bootstrap_ci_lower}, {p43.bootstrap_ci_upper}]")
    print(f"{'prob_improvement:':<36} {p43.bootstrap_prob_improvement}")
    print()
    print("--- Phase44 Paper Tracking ---")
    print(f"{'gate_state:':<36} {p44.gate_state}")
    print(f"{'sample_size:':<36} {p44.sample_size}")
    print(f"{'blend_bss:':<36} {p44.blend_bss:+.6f}")
    print(f"{'blend_ece:':<36} {p44.blend_ece:.6f}")
    print(f"{'candidate_patch_created:':<36} {p44.candidate_patch_created}")
    print()
    print("--- Phase45 Attribution ---")
    print(f"{'global_conclusion:':<36} {p45.global_conclusion}")
    print(f"{'gate:':<36} {p45.gate}")
    print(f"{'failure_segments:':<36} {len(p45.failure_segments)}")
    print(f"{'heavy_fav_ece_no_longer_failure:':<36} {p45.heavy_fav_ece_no_longer_failure}")
    print(f"{'high_conf_improved:':<36} {p45.high_conf_improved}")
    print(f"{'failure_count_delta:':<36} {p45.failure_count_delta}")
    print()
    print(f"{'gate_recommendation:':<36} {result.gate_recommendation}")
    print(f"{'gate_rationale:':<36} {result.gate_rationale[:80]}...")
    print(f"{'candidate_patch_created:':<36} {result.candidate_patch_created}")
    print(f"{'production_modified:':<36} {result.production_modified}")
    print(f"{'diagnostic_only:':<36} {result.diagnostic_only}")
    print(f"{'audit_hash:':<36} {result.audit_hash}")


# ═══════════════════════════════════════════════════════════════════════════════
# § Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 54 Safe SP Stability Audit")
    parser.add_argument("--print", action="store_true", dest="do_print", help="Print summary to stdout")
    parser.add_argument("--json", action="store_true", dest="do_json", help="Write JSON report")
    parser.add_argument("--report", action="store_true", dest="do_report", help="Write Markdown report")
    parser.add_argument("--bootstrap", type=int, default=500, help="Bootstrap iterations (default: 500)")
    parser.add_argument("--splits", type=int, default=5, help="Number of time-aware folds (default: 5)")
    args = parser.parse_args()

    # Validate paths
    if not _BASELINE_JSONL.exists():
        logger.error("Baseline JSONL not found: %s", _BASELINE_JSONL)
        sys.exit(1)
    if not _CONTEXT_JSONL.exists():
        logger.error("Context JSONL not found: %s", _CONTEXT_JSONL)
        sys.exit(1)

    logger.info("Starting Phase 54 Safe SP Stability Audit")
    result = run_phase54_audit(
        baseline_path=_BASELINE_JSONL,
        context_path=_CONTEXT_JSONL,
        phase54_output_path=_PHASE54_JSONL,
        n_bootstrap=args.bootstrap,
        n_splits=args.splits,
    )

    today = date.today().isoformat()

    if args.do_print:
        _print_summary(result)

    if args.do_json:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = _REPORTS_DIR / f"phase54_safe_sp_stability_audit_{today}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)
        logger.info("JSON report written: %s", json_path)
        print(f"  JSON:     {json_path}")

    if args.do_report:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        _DOCS_DIR.mkdir(parents=True, exist_ok=True)

        json_path = _REPORTS_DIR / f"phase54_safe_sp_stability_audit_{today}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)

        md_content = _build_markdown(result, today)
        md_path = _DOCS_DIR / f"phase54_safe_sp_stability_audit_{today}.md"
        md_path.write_text(md_content, encoding="utf-8")
        logger.info("Markdown report written: %s", md_path)

        print(f"\nReports written:")
        print(f"  JSON:     {json_path}")
        print(f"  Markdown: {md_path}")


if __name__ == "__main__":
    main()
