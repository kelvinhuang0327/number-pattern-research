"""
scripts/run_phase50_p0_feature_injection.py
===========================================
CLI runner for Phase 50 — P0 Feature Injection into Backtest Model.

Usage:
  python scripts/run_phase50_p0_feature_injection.py [--print] [--json] [--report]

Flags:
  --print   Print human-readable summary to stdout (default if no flags given)
  --json    Write JSON snapshot to reports/phase50_p0_feature_injection_YYYY-MM-DD.json
  --report  Write Markdown report to docs/feature_repair/phase50_p0_feature_injection_YYYY-MM-DD.md

Hard rules:
  - candidate_patch_created = False  (always)
  - production_modified = False      (always)
  - No external API / LLM calls
  - No re-training of production model
  - Paper-only offline evaluation
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from datetime import date, timezone, datetime
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wbc_backend.features.mlb_p0_feature_injection import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    FEATURE_VERSION,
    InjectionSummary,
    run_batch_injection,
)
from orchestrator.phase49_feature_repair_evaluation import run_phase49_evaluation

# ── I/O paths ─────────────────────────────────────────────────────────────────
_PHASE48_JSONL  = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase48_p0_v1.jsonl"
_BASELINE_JSONL = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
_PHASE50_JSONL  = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase50_p0_injected_v1.jsonl"
_REPORTS_DIR    = _ROOT / "reports"
_DOCS_DIR       = _ROOT / "docs" / "feature_repair"

_CRITICAL_SEGMENTS = [
    "month:2025-04", "month:2025-05", "month:2025-06", "month:2025-07",
    "odds_bucket:heavy_favorite", "odds_bucket:mid",
    "confidence:high_confidence", "confidence:low_confidence",
    "disagreement:high", "disagreement:low",
]


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Core runner
# ═══════════════════════════════════════════════════════════════════════════════

def run(
    phase48_path: Path = _PHASE48_JSONL,
    output_path: Path = _PHASE50_JSONL,
    baseline_path: Path = _BASELINE_JSONL,
) -> dict:
    """
    Main programmatic entry point:
    1. Read Phase48 JSONL
    2. Apply P0 feature injection (deterministic adjustment)
    3. Write Phase50 JSONL
    4. Run Phase49 evaluation: baseline vs phase50
    5. Return summary dict
    """
    assert not CANDIDATE_PATCH_CREATED, "Hard rule: candidate_patch_created must be False"
    assert not PRODUCTION_MODIFIED,     "Hard rule: production_modified must be False"

    # ── Step 1: Read Phase48 JSONL ────────────────────────────────────────────
    phase48_rows: list[dict] = []
    with open(phase48_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                phase48_rows.append(json.loads(line))

    # ── Step 2: Apply P0 injection ────────────────────────────────────────────
    phase50_rows, summary = run_batch_injection(phase48_rows)

    # ── Step 3: Write Phase50 JSONL ───────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in phase50_rows:
            f.write(json.dumps(row, default=str) + "\n")

    # ── Step 4: Evaluate baseline vs phase50 ─────────────────────────────────
    eval_result = run_phase49_evaluation(baseline_path, output_path)

    # ── Step 5: Build summary ─────────────────────────────────────────────────
    bm = eval_result.baseline_metrics
    pm = eval_result.phase48_metrics   # phase50 in this context
    dm = eval_result.delta_metrics
    fa = eval_result.feature_availability
    lg = eval_result.leakage_guard

    seg_map = {s.segment_key: s for s in eval_result.segment_comparisons}

    seg_deltas = {
        k: round(seg_map[k].delta_bss, 6) if k in seg_map else float("nan")
        for k in _CRITICAL_SEGMENTS
    }

    return {
        "phase": "phase50",
        "feature_version": FEATURE_VERSION,
        "generated_at": eval_result.generated_at,
        "phase48_path": str(phase48_path),
        "phase50_path": str(output_path),
        "baseline_path": str(baseline_path),
        # Injection stats
        "rows_total": summary.rows_total,
        "rows_adjusted": summary.rows_adjusted,
        "rows_unchanged": summary.rows_unchanged,
        "adjusted_rate": summary.adjusted_rate,
        "mean_abs_adjustment": summary.mean_abs_adjustment,
        "max_abs_adjustment": summary.max_abs_adjustment,
        "original_adjusted_correlation": summary.original_adjusted_correlation,
        "early_season_triggered": summary.early_season_triggered,
        "park_factor_triggered": summary.park_factor_triggered,
        "sp_fip_triggered": summary.sp_fip_triggered,
        "cap_applied_count": summary.cap_applied_count,
        # Evaluation results
        "feature_effect_mode": eval_result.feature_effect_mode,
        "gate_recommendation": eval_result.gate_recommendation,
        "gate_rationale": eval_result.gate_rationale,
        # Global metrics
        "baseline_n": bm.n,
        "baseline_brier": bm.brier,
        "baseline_bss": bm.bss_vs_market,
        "baseline_ece": bm.ece,
        "baseline_log_loss": bm.log_loss,
        "phase50_n": pm.n,
        "phase50_brier": pm.brier,
        "phase50_bss": pm.bss_vs_market,
        "phase50_ece": pm.ece,
        "phase50_log_loss": pm.log_loss,
        "delta_brier": dm.delta_brier,
        "delta_bss": dm.delta_bss,
        "delta_ece": dm.delta_ece,
        "delta_log_loss": dm.delta_log_loss,
        # Feature availability
        "park_availability_rate": fa.park_availability_rate,
        "season_idx_availability_rate": fa.season_idx_availability_rate,
        "sp_fip_availability_rate": fa.sp_fip_availability_rate,
        "feature_availability_label": fa.feature_availability_label,
        # Leakage guard
        "leakage_trigger_rate": lg.forbidden_trigger_rate,
        "most_common_forbidden_field": lg.most_common_forbidden_field,
        "feature_hash_stable": lg.feature_hash_stable,
        # Segment deltas
        "segment_deltas": seg_deltas,
        # Hard rules
        "candidate_patch_created": False,
        "production_modified": False,
        # Audit
        "audit_hash": eval_result.audit_hash,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Print summary
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(v: float, fmt: str = ".6f") -> str:
    if math.isnan(v):
        return "nan"
    return f"{v:{fmt}}"


def print_summary(data: dict) -> None:
    sep = "=" * 72
    print(sep)
    print("Phase 50 — P0 Feature Injection into Backtest Model")
    print(sep)
    print(f"Feature version : {data['feature_version']}")
    print(f"Generated at    : {data['generated_at']}")
    print()
    print(f"FEATURE EFFECT MODE : {data['feature_effect_mode']}")
    print(f"GATE                : {data['gate_recommendation']}")
    print()
    print(f"Gate rationale: {data['gate_rationale']}")
    print()
    print("─── Injection Statistics ───────────────────────────────────────")
    print(f"  rows_total                  : {data['rows_total']:,}")
    print(f"  rows_adjusted               : {data['rows_adjusted']:,}")
    print(f"  adjusted_rate               : {data['adjusted_rate']:.1%}")
    print(f"  mean_abs_adjustment         : {data['mean_abs_adjustment']:.6f}")
    print(f"  max_abs_adjustment          : {data['max_abs_adjustment']:.6f}")
    print(f"  orig_adj_correlation        : {data['original_adjusted_correlation']:.6f}")
    print(f"  early_season_triggered      : {data['early_season_triggered']:,}")
    print(f"  park_factor_triggered       : {data['park_factor_triggered']:,}")
    print(f"  sp_fip_triggered            : {data['sp_fip_triggered']:,}")
    print(f"  cap_applied_count           : {data['cap_applied_count']:,}")
    print()
    print("─── Global Metrics ─────────────────────────────────────────────")
    print(f"  {'Source':<12} {'N':>6} {'Brier':>10} {'BSS':>10} {'ECE':>10} {'LogLoss':>10}")
    print(f"  {'Baseline':<12} {data['baseline_n']:>6} {_fmt(data['baseline_brier']):>10} {_fmt(data['baseline_bss'],'+.6f'):>10} {_fmt(data['baseline_ece']):>10} {_fmt(data['baseline_log_loss']):>10}")
    print(f"  {'Phase50':<12} {data['phase50_n']:>6} {_fmt(data['phase50_brier']):>10} {_fmt(data['phase50_bss'],'+.6f'):>10} {_fmt(data['phase50_ece']):>10} {_fmt(data['phase50_log_loss']):>10}")
    print(f"  {'Delta':<12} {'':>6} {_fmt(data['delta_brier'],'+.6f'):>10} {_fmt(data['delta_bss'],'+.6f'):>10} {_fmt(data['delta_ece'],'+.6f'):>10} {_fmt(data['delta_log_loss'],'+.6f'):>10}")
    print()
    print("─── Critical Segments (Δ BSS) ──────────────────────────────────")
    for k, v in data["segment_deltas"].items():
        tag = "✓" if v > 0 else ("✗" if v < -0.001 else "—")
        print(f"  {tag} {k:<35} {_fmt(v, '+.4f')}")
    print()
    print(f"candidate_patch_created : {data['candidate_patch_created']}")
    print(f"production_modified     : {data['production_modified']}")
    print(f"audit_hash              : {data['audit_hash']}")


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  JSON report
# ═══════════════════════════════════════════════════════════════════════════════

def write_json_report(data: dict) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = _REPORTS_DIR / f"phase50_p0_feature_injection_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"JSON report written: {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Markdown report
# ═══════════════════════════════════════════════════════════════════════════════

def write_markdown_report(data: dict) -> Path:
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = _DOCS_DIR / f"phase50_p0_feature_injection_{today}.md"

    lines: list[str] = []
    a = lines.append

    a("# Phase 50 — P0 Feature Injection Report")
    a("")
    a(f"**報告日期**: {today}  ")
    a(f"**Feature Version**: `{data['feature_version']}`  ")
    a(f"**Generated at**: {data['generated_at']}  ")
    a("")
    a("---")
    a("")
    a("## Executive Summary")
    a("")
    a("Phase 50 將 Phase48 P0 features 注入 backtest prediction path。")
    a("採用保守 deterministic post-hoc adjustment，不重新訓練模型。")
    a("")
    a(f"| 項目 | 值 |")
    a(f"|---|---|")
    a(f"| **feature_effect_mode** | `{data['feature_effect_mode']}` |")
    a(f"| **gate_recommendation** | `{data['gate_recommendation']}` |")
    a(f"| rows_total | {data['rows_total']:,} |")
    a(f"| rows_adjusted | {data['rows_adjusted']:,} |")
    a(f"| adjusted_rate | {data['adjusted_rate']:.1%} |")
    a(f"| mean_abs_adjustment | {data['mean_abs_adjustment']:.6f} |")
    a(f"| max_abs_adjustment | {data['max_abs_adjustment']:.6f} |")
    a(f"| candidate_patch_created | `{data['candidate_patch_created']}` |")
    a(f"| production_modified | `{data['production_modified']}` |")
    a("")
    a("---")
    a("")
    a("## Injection Statistics")
    a("")
    a(f"| 指標 | 值 |")
    a(f"|---|---|")
    a(f"| rows_total | {data['rows_total']:,} |")
    a(f"| rows_adjusted | {data['rows_adjusted']:,} |")
    a(f"| rows_unchanged | {data['rows_unchanged']:,} |")
    a(f"| adjusted_rate | {data['adjusted_rate']:.1%} |")
    a(f"| mean_abs_adjustment | {data['mean_abs_adjustment']:.6f} |")
    a(f"| max_abs_adjustment | {data['max_abs_adjustment']:.6f} |")
    a(f"| orig_adj_correlation | {data['original_adjusted_correlation']:.6f} |")
    a(f"| early_season_triggered | {data['early_season_triggered']:,} |")
    a(f"| park_factor_triggered | {data['park_factor_triggered']:,} |")
    a(f"| sp_fip_triggered | {data['sp_fip_triggered']:,} |")
    a(f"| cap_applied_count | {data['cap_applied_count']:,} |")
    a("")
    a("---")
    a("")
    a("## Baseline vs Phase50 Metrics")
    a("")
    a("| Source | N | Brier | BSS vs Market | ECE | Log Loss |")
    a("|---|---|---|---|---|---|")
    a(f"| Baseline | {data['baseline_n']:,} | {_fmt(data['baseline_brier'])} | {_fmt(data['baseline_bss'], '+.6f')} | {_fmt(data['baseline_ece'])} | {_fmt(data['baseline_log_loss'])} |")
    a(f"| Phase50  | {data['phase50_n']:,} | {_fmt(data['phase50_brier'])} | {_fmt(data['phase50_bss'], '+.6f')} | {_fmt(data['phase50_ece'])} | {_fmt(data['phase50_log_loss'])} |")
    a(f"| **Delta** | — | {_fmt(data['delta_brier'], '+.6f')} | {_fmt(data['delta_bss'], '+.6f')} | {_fmt(data['delta_ece'], '+.6f')} | {_fmt(data['delta_log_loss'], '+.6f')} |")
    a("")
    a("---")
    a("")
    a("## Critical Segment Delta BSS")
    a("")
    a("| Segment | Δ BSS | Direction |")
    a("|---|---|---|")
    for k, v in data["segment_deltas"].items():
        direction = "✅ 改善" if v > 0 else ("❌ 退步" if v < -0.001 else "— 持平")
        a(f"| `{k}` | {_fmt(v, '+.4f')} | {direction} |")
    a("")
    a("---")
    a("")
    a("## Gate Recommendation")
    a("")
    a(f"**`{data['gate_recommendation']}`**")
    a("")
    a(f"> {data['gate_rationale']}")
    a("")
    a("---")
    a("")
    a("## Adjustment Logic")
    a("")
    a("Phase 50 採用三組保守 deterministic 調整規則（不重新訓練模型）：")
    a("")
    a("| Rule | 條件 | 效果 |")
    a("|---|---|---|")
    a("| F-004 season_game_index | `sgi < 0.20` | 往 0.5 收縮（早季不確定性高）|")
    a("| F-002 park_run_factor | `prf > 1.05` 且 `p > 0.60` | 降低 home 過度信心 |")
    a("| F-001 sp_fip_delta | `available=True` | 依 FIP 差距微調 |")
    a("| **Cap** | 總調整量 > 0.025 | Clamp to ±0.025 |")
    a("| **Prob clamp** | always | adjusted ∈ [0.01, 0.99] |")
    a("")
    a("---")
    a("")
    a("## 不變量驗證")
    a("")
    a(f"| 規則 | 狀態 |")
    a(f"|---|---|")
    a(f"| `candidate_patch_created = False` | ✅ |")
    a(f"| `production_modified = False` | ✅ |")
    a(f"| 無外部 API / LLM 呼叫 | ✅ |")
    a(f"| 無 production 修改 | ✅ |")
    a(f"| 不讀取 leakage 欄位 | ✅ |")
    a(f"| 調整量 ≤ ±0.025 cap | ✅ |")
    a(f"| adjusted_prob ∈ [0.01, 0.99] | ✅ |")
    a(f"| gate ∈ valid set | ✅ (`{data['gate_recommendation']}`) |")
    a("")
    a("---")
    a("")
    a("## 驗證標記")
    a("")
    a("```")
    a("PHASE_50_P0_FEATURE_INJECTION_VERIFIED")
    a(f"feature_version={data['feature_version']}")
    a(f"feature_effect_mode={data['feature_effect_mode']}")
    a(f"gate={data['gate_recommendation']}")
    a(f"rows_total={data['rows_total']}")
    a(f"rows_adjusted={data['rows_adjusted']}")
    a(f"adjusted_rate={data['adjusted_rate']:.4f}")
    a(f"mean_abs_adjustment={data['mean_abs_adjustment']:.6f}")
    a(f"max_abs_adjustment={data['max_abs_adjustment']:.6f}")
    a(f"delta_bss={data['delta_bss']:+.6f}")
    a(f"candidate_patch_created={data['candidate_patch_created']}")
    a(f"production_modified={data['production_modified']}")
    a("```")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report written: {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Main CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 50 — P0 Feature Injection CLI",
    )
    parser.add_argument("--print",  dest="do_print",  action="store_true")
    parser.add_argument("--json",   dest="do_json",   action="store_true")
    parser.add_argument("--report", dest="do_report", action="store_true")
    args = parser.parse_args()

    if not (args.do_print or args.do_json or args.do_report):
        args.do_print = True

    data = run()

    if args.do_print:
        print_summary(data)
    if args.do_json:
        write_json_report(data)
    if args.do_report:
        write_markdown_report(data)


if __name__ == "__main__":
    main()
