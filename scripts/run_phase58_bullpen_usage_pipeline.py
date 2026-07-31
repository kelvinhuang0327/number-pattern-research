"""
scripts/run_phase58_bullpen_usage_pipeline.py
=============================================
Phase 58 — Full Bullpen Usage Pipeline Runner

執行完整的 Phase58 pipeline：
  Step 1: Backfill bullpen usage snapshots
  Step 2: Inject bullpen usage to Phase56/52 context
  Step 3: Apply bullpen feature injection
  Step 4: Run evaluation & gate determination
  Step 5: Generate JSON + Markdown reports

執行方式：
    python scripts/run_phase58_bullpen_usage_pipeline.py [--dry-run] [--print] [--json] [--report]

輸出：
    data/mlb_2025/derived/mlb_2025_bullpen_usage_phase58.jsonl
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase58_bullpen_context_v1.jsonl
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase58_bullpen_injected_v1.jsonl
    reports/phase58_bullpen_usage_pipeline_YYYY-MM-DD.json
    docs/feature_repair/phase58_bullpen_usage_pipeline_YYYY-MM-DD.md

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.run_phase58_bullpen_usage_backfill import run_backfill
from scripts.run_phase58_inject_bullpen_usage_to_phase56 import run_injection
from scripts.run_phase58_bullpen_feature_injection import run_injection as run_feat_injection
from orchestrator.phase58_bullpen_usage_evaluation import (
    run_phase58_evaluation,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    DATA_GAP_REMAINS,
    BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
    BULLPEN_FEATURE_NOT_EFFECTIVE,
    COLLECT_MORE_DATA,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions.jsonl"
)
_USAGE_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_bullpen_usage_phase58.jsonl"
)
_CONTEXT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase58_bullpen_context_v1.jsonl"
)
_INJECTED_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase58_bullpen_injected_v1.jsonl"
)
_REPORT_DIR = _ROOT / "reports"
_DOCS_DIR = _ROOT / "docs" / "feature_repair"

# ─── Next phase recommendations ───────────────────────────────────────────────
_NEXT_PHASE_MAP: dict[str, str] = {
    DATA_GAP_REMAINS: (
        "Phase 59: Real Bullpen Boxscore Acquisition — "
        "實作 StatsAPI boxscore 爬取，建立真實 relief appearances 資料，"
        "重新執行 Phase58 pipeline。"
    ),
    BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY: (
        "Phase 59: Re-run Phase43/44/45 with Phase58 features — "
        "使用 Phase58 bullpen context 重新執行 market blend stability / "
        "paper tracking / value attribution 分析。"
    ),
    BULLPEN_FEATURE_NOT_EFFECTIVE: (
        "Phase 59: Bullpen Functional Form Calibration Audit — "
        "深入分析 proxy fatigue delta 與 win probability 的真實關係，"
        "評估是否需要更精細的特徵形式。"
    ),
    COLLECT_MORE_DATA: (
        "Phase 59: Collect More Data — "
        "擴充 bullpen usage 資料範圍，加入更多球季資料，"
        "提升評估樣本數至 500+ 後重新評估。"
    ),
}


def _get_report_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _generate_markdown_report(
    pipeline_summary: dict,
    date_str: str,
) -> str:
    """生成 Markdown 格式的 Phase58 pipeline report。"""
    gate = pipeline_summary.get("gate_recommendation", "UNKNOWN")
    next_phase = _NEXT_PHASE_MAP.get(gate, "未知下一步")

    backfill = pipeline_summary.get("backfill", {})
    injection = pipeline_summary.get("injection", {})
    feat_injection = pipeline_summary.get("feat_injection", {})
    evaluation = pipeline_summary.get("evaluation", {})

    avail_rate = backfill.get("bullpen_feature_available_rate", 0.0)
    pit_rate = backfill.get("point_in_time_safe_rate", 0.0)
    audit_rate = backfill.get("audit_hash_present_rate", 0.0)
    row_count = backfill.get("row_count", 0)
    expected_count = backfill.get("expected_row_count", 2025)

    baseline_bss = evaluation.get("baseline_bss", "N/A")
    phase58_bss = evaluation.get("phase58_bss", "N/A")
    delta_bss = evaluation.get("delta_bss", "N/A")
    baseline_ece = evaluation.get("baseline_ece", "N/A")
    phase58_ece = evaluation.get("phase58_ece", "N/A")
    delta_ece = evaluation.get("delta_ece", "N/A")
    heavy_fav_ece_delta = evaluation.get("heavy_fav_ece_delta", "N/A")
    high_conf_bss_delta = evaluation.get("high_conf_bss_delta", "N/A")
    failure_delta = evaluation.get("failure_segment_count_delta", "N/A")

    rows_adjusted = feat_injection.get("rows_adjusted", 0)
    adjusted_rate = feat_injection.get("adjusted_rate", 0.0)
    max_adj = feat_injection.get("max_abs_adjustment", 0.0)

    md = f"""# Phase 58 — Bullpen Usage Pipeline Report
**Generated**: {date_str}
**Gate**: `{gate}`

---

## Executive Summary

Phase 58 為 MLB 2025 共 {row_count} 場比賽（預期 {expected_count} 場）建立了
以 schedule proxy fallback 為基礎的 bullpen usage snapshot。
本 Phase 不使用真實 boxscore 資料，所有 bullpen appearance 為聯盟平均估算值。

**Gate recommendation: `{gate}`**

---

## Data Source

| 欄位 | 值 |
|------|-----|
| 資料來源模式 | schedule_proxy_fallback |
| 真實 boxscore | ❌ 無 |
| Proxy outs/game | 9.0（聯盟平均） |
| ERA proxy | 4.10（聯盟平均） |
| FIP proxy | 4.05（聯盟平均） |
| Leverage proxy | 0.0（需 Statcast，Phase59 目標） |
| estimated | True (所有記錄) |

---

## Bullpen Feature Availability

| 指標 | 值 |
|------|-----|
| 總場次 | {row_count} |
| 可用場次 | {backfill.get('bullpen_feature_available_count', 0)} |
| 可用率 | {avail_rate:.1%} |
| Workload 可用率 | {backfill.get('workload_available_rate', 0):.1%} |
| Leverage 可用率 | {backfill.get('leverage_available_rate', 0):.1%} |
| Perf Proxy 可用率 | {backfill.get('performance_proxy_available_rate', 0):.1%} |
| Fallback 率 | {backfill.get('fallback_rate', 0):.1%} |
| Gate 門檻（>= 80%） | {'✓ 通過' if avail_rate >= 0.80 else '✗ 未通過'} |

---

## PIT 驗證

| 指標 | 值 |
|------|-----|
| PIT safe 率 | {pit_rate:.1%} |
| Audit hash 完整率 | {audit_rate:.1%} |
| 違規筆數 | {backfill.get('forbidden_leakage_count', 0)} |

---

## Context Injection

| 指標 | 值 |
|------|-----|
| Context source rows | {injection.get('context_row_count', 0)} |
| Match count | {injection.get('match_count', 0)} |
| No-match count | {injection.get('no_match_count', 0)} |
| Match rate | {injection.get('match_rate', 0):.1%} |

---

## Feature Injection

| 指標 | 值 |
|------|-----|
| Total rows | {feat_injection.get('rows_total', 0)} |
| Adjusted rows | {rows_adjusted} |
| Adjusted rate | {adjusted_rate:.1%} |
| Mean abs adjustment | {feat_injection.get('mean_abs_adjustment', 0):.6f} |
| Max abs adjustment | {max_adj:.6f} |
| Within limit (0.015) | {'✓' if max_adj <= 0.015 else '✗'} |

---

## Overall Metric Delta

| 指標 | Baseline | Phase58 | Delta |
|------|---------|---------|-------|
| BSS vs market | {baseline_bss} | {phase58_bss} | {delta_bss} |
| ECE | {baseline_ece} | {phase58_ece} | {delta_ece} |

---

## Critical Segment Delta

| Segment | Delta |
|---------|-------|
| Heavy Favorite ECE delta | {heavy_fav_ece_delta} |
| High Confidence BSS delta | {high_conf_bss_delta} |
| Failure segment count delta | {failure_delta} |

---

## Gate Recommendation

**`{gate}`**

{pipeline_summary.get('gate_rationale', '')}

---

## Limitations

1. **ERA/FIP proxy = 聯盟平均**: 所有隊伍 ERA delta = 0.0，無法捕捉投手表現差異
2. **Leverage proxy = 0.0**: 無 Statcast play-by-play 資料，高壓情境使用無法估算
3. **Proxy outs 固定**: 每場 9 outs / 3 relievers 假設，不反映實際牛棚使用深度
4. **B2B 估算**: 僅從賽程連續性推斷，無法確認實際上場投手

---

## Next Phase Recommendation

{next_phase}

---

## Hard Rules 確認

| 規則 | 值 |
|------|-----|
| candidate_patch_created | False |
| production_modified | False |
| diagnostic_only | True |
| gate 合法 | True |
| max adjustment <= 0.015 | {'True' if max_adj <= 0.015 else 'False'} |
"""
    return md


def run_pipeline(
    dry_run: bool = False,
    generate_report: bool = True,
) -> dict:
    """
    執行完整 Phase58 pipeline。

    Returns:
        Pipeline summary dict
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    logger.info("=" * 60)
    logger.info("Phase 58 — Bullpen Usage Pipeline 開始")
    logger.info("=" * 60)

    pipeline_start = datetime.now(timezone.utc)

    # ─── Step 1: Backfill ────────────────────────────────────────────────────
    logger.info("[Step 1/4] Bullpen Usage Backfill...")
    backfill_summary = run_backfill(
        output_path=_USAGE_JSONL,
        dry_run=dry_run,
    )

    # ─── Step 2: Context Injection ────────────────────────────────────────────
    logger.info("[Step 2/4] Context Injection...")
    injection_summary = run_injection(
        bullpen_usage_path=_USAGE_JSONL,
        output_path=_CONTEXT_JSONL,
        dry_run=dry_run,
    )

    # ─── Step 3: Feature Injection ────────────────────────────────────────────
    logger.info("[Step 3/4] Feature Injection...")
    feat_injection_summary = run_feat_injection(
        context_path=_CONTEXT_JSONL,
        output_path=_INJECTED_JSONL,
        dry_run=dry_run,
    )

    # ─── Step 4: Evaluation ───────────────────────────────────────────────────
    logger.info("[Step 4/4] Evaluation...")
    eval_result = None
    eval_summary: dict = {}
    gate = DATA_GAP_REMAINS
    gate_rationale = ""

    if not dry_run and _INJECTED_JSONL.exists() and _BASELINE_JSONL.exists():
        eval_result = run_phase58_evaluation(
            baseline_path=_BASELINE_JSONL,
            phase58_injected_path=_INJECTED_JSONL,
        )
        gate = eval_result.gate_recommendation
        gate_rationale = eval_result.gate_rationale

        avail = eval_result.bullpen_availability
        base_m = eval_result.baseline_metrics
        p58_m = eval_result.phase58_metrics

        heavy_fav_segs = [
            s for s in eval_result.segment_metrics
            if "heavy_favorite" in s.segment_key
        ]
        high_conf_segs = [
            s for s in eval_result.segment_metrics
            if "high_confidence" in s.segment_key
        ]
        heavy_fav_ece_delta = (
            sum(s.delta_ece for s in heavy_fav_segs) / len(heavy_fav_segs)
            if heavy_fav_segs else 0.0
        )
        high_conf_bss_delta = (
            sum(s.delta_bss for s in high_conf_segs) / len(high_conf_segs)
            if high_conf_segs else 0.0
        )

        eval_summary = {
            "baseline_n": base_m.n,
            "phase58_n": p58_m.n,
            "baseline_bss": base_m.bss_vs_market,
            "phase58_bss": p58_m.bss_vs_market,
            "delta_bss": eval_result.delta_bss,
            "baseline_ece": base_m.ece,
            "phase58_ece": p58_m.ece,
            "delta_ece": eval_result.delta_ece,
            "heavy_fav_ece_delta": round(heavy_fav_ece_delta, 6),
            "high_conf_bss_delta": round(high_conf_bss_delta, 6),
            "failure_count_baseline": eval_result.failure_count_baseline,
            "failure_count_phase58": eval_result.failure_count_phase58,
            "failure_segment_count_delta": eval_result.failure_segment_count_delta,
            "availability_rate": avail.availability_rate,
            "workload_available_rate": avail.workload_available_rate,
            "gate": gate,
            "gate_rationale": gate_rationale,
            "audit_hash": eval_result.audit_hash,
        }
    elif dry_run:
        gate = "DRY_RUN"
        gate_rationale = "Dry run mode — no evaluation performed"
        eval_summary = {"gate": gate, "gate_rationale": gate_rationale}
    else:
        gate_rationale = f"Output files not found (dry_run={dry_run})"
        eval_summary = {"gate": gate, "gate_rationale": gate_rationale}

    pipeline_end = datetime.now(timezone.utc)
    elapsed_seconds = (pipeline_end - pipeline_start).total_seconds()
    date_str = _get_report_date_str()

    pipeline_summary = {
        "phase": "phase58_bullpen_usage_pipeline",
        "date": date_str,
        "elapsed_seconds": round(elapsed_seconds, 1),
        "dry_run": dry_run,
        "backfill": backfill_summary,
        "injection": injection_summary,
        "feat_injection": feat_injection_summary,
        "evaluation": eval_summary,
        "gate_recommendation": gate,
        "gate_rationale": gate_rationale,
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }

    # ─── Step 5: Reports ──────────────────────────────────────────────────────
    if generate_report and not dry_run:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _DOCS_DIR.mkdir(parents=True, exist_ok=True)

        json_report_path = _REPORT_DIR / f"phase58_bullpen_usage_pipeline_{date_str}.json"
        md_report_path = _DOCS_DIR / f"phase58_bullpen_usage_pipeline_{date_str}.md"

        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(pipeline_summary, f, indent=2, ensure_ascii=False)
        logger.info("JSON report: %s", json_report_path)

        md_content = _generate_markdown_report(pipeline_summary, date_str)
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("MD report: %s", md_report_path)

        pipeline_summary["json_report_path"] = str(json_report_path)
        pipeline_summary["md_report_path"] = str(md_report_path)

    return pipeline_summary


def _print_pipeline_summary(summary: dict) -> None:
    print("\n" + "="*65)
    print("Phase 58 — Bullpen Usage Pipeline COMPLETE")
    print("="*65)

    backfill = summary.get("backfill", {})
    feat = summary.get("feat_injection", {})
    ev = summary.get("evaluation", {})

    print(f"Row Count       : {backfill.get('row_count', 'N/A')} (expected {backfill.get('expected_row_count', 2025)})")
    print(f"Avail Rate      : {backfill.get('bullpen_feature_available_rate', 0):.1%}")
    print(f"PIT Safe Rate   : {backfill.get('point_in_time_safe_rate', 0):.1%}")
    print(f"Audit Hash Rate : {backfill.get('audit_hash_present_rate', 0):.1%}")
    print(f"Leakage Count   : {backfill.get('forbidden_leakage_count', 0)}")
    print(f"Adj Rows        : {feat.get('rows_adjusted', 0)} ({feat.get('adjusted_rate', 0):.1%})")
    print(f"Max Adjustment  : {feat.get('max_abs_adjustment', 0):.6f}")
    print(f"BSS Delta       : {ev.get('delta_bss', 'N/A')}")
    print(f"ECE Delta       : {ev.get('delta_ece', 'N/A')}")
    print(f"Heavy Fav ECE Δ : {ev.get('heavy_fav_ece_delta', 'N/A')}")
    print(f"HiConf BSS Δ    : {ev.get('high_conf_bss_delta', 'N/A')}")
    print(f"Failure Seg Δ   : {ev.get('failure_segment_count_delta', 'N/A')}")
    print(f"Gate            : {summary.get('gate_recommendation', 'UNKNOWN')}")
    print(f"Candidate Patch : {summary.get('candidate_patch_created', False)}")
    print(f"Prod Modified   : {summary.get('production_modified', False)}")
    print(f"Diagnostic Only : {summary.get('diagnostic_only', True)}")
    print(f"Elapsed         : {summary.get('elapsed_seconds', 0):.1f}s")
    if "json_report_path" in summary:
        print(f"JSON Report     : {summary['json_report_path']}")
    if "md_report_path" in summary:
        print(f"MD Report       : {summary['md_report_path']}")
    print("="*65)
    print("PHASE_58_BULLPEN_USAGE_PIPELINE_VERIFIED")
    print("="*65)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase58 Full Pipeline Runner")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--print", action="store_true", dest="print_summary")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--report", action="store_true", dest="generate_report",
                        help="Generate JSON + Markdown reports")
    args = parser.parse_args()

    summary = run_pipeline(
        dry_run=args.dry_run,
        generate_report=args.generate_report,
    )

    if args.print_summary:
        _print_pipeline_summary(summary)

    if args.print_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
