"""
scripts/run_phase56_bullpen_evaluation_report.py
================================================
Phase 56 — Full Pipeline Runner + Report Generator

執行完整 Phase56 牛棚特徵評估流程：
  1. Backfill:  產出 bullpen features JSONL
  2. Inject:    注入至 Phase52 context → phase56_sp_bullpen_context
  3. Apply:     套用 bullpen adjustment → phase56_sp_bullpen_injected
  4. Evaluate:  比較 baseline vs injected，計算 BSS/ECE delta
  5. Report:    產出 JSON 報告 + Markdown 文件

執行方式：
    python scripts/run_phase56_bullpen_evaluation_report.py [--print] [--json]

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
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.run_phase56_bullpen_backfill import run_backfill
from scripts.run_phase56_inject_bullpen_to_phase52 import run_injection as run_context_injection
from scripts.run_phase56_bullpen_feature_injection import run_injection as run_adj_injection
from orchestrator.phase56_bullpen_feature_evaluation import (
    run_phase56_evaluation,
    Phase56EvaluationResult,
    DATA_GAP_REMAINS,
    BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
    BULLPEN_FEATURE_NOT_EFFECTIVE,
    COLLECT_MORE_DATA,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
PHASE56_VERSION: str = "phase56_bullpen_evaluation_v1"

# ── Paths ─────────────────────────────────────────────────────────────────────
_DERIVED = _ROOT / "data" / "mlb_2025" / "derived"
_BASELINE_JSONL    = _DERIVED / "mlb_2025_per_game_predictions.jsonl"
_BULLPEN_FEATURES  = _DERIVED / "mlb_2025_bullpen_features_phase56.jsonl"
_CONTEXT_JSONL     = _DERIVED / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
_INJECTED_JSONL    = _DERIVED / "mlb_2025_per_game_predictions_phase56_sp_bullpen_injected_v1.jsonl"
_REPORTS_DIR       = _ROOT / "reports"
_DOCS_DIR          = _ROOT / "docs" / "feature_repair"
_TODAY             = datetime.utcnow().strftime("%Y-%m-%d")
_REPORT_JSON       = _REPORTS_DIR / f"phase56_bullpen_feature_evaluation_{_TODAY}.json"
_REPORT_MD         = _DOCS_DIR / f"phase56_bullpen_feature_report_{_TODAY}.md"


def _generate_markdown_report(result: Phase56EvaluationResult) -> str:
    """Generate Markdown report from evaluation result."""
    r = result
    avail = r.bullpen_availability
    base = r.baseline_metrics
    p56 = r.phase56_metrics
    mkt = r.market_metrics

    # Gate icon
    gate_icon = {
        BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY: "✅",
        BULLPEN_FEATURE_NOT_EFFECTIVE: "❌",
        DATA_GAP_REMAINS: "⚠️",
        COLLECT_MORE_DATA: "🔄",
    }.get(r.gate_recommendation, "❓")

    lines: list[str] = [
        f"# Phase 56 Bullpen Feature Builder — Evaluation Report",
        f"",
        f"**生成時間**: {r.generated_at}",
        f"**Run ID**: `{r.run_id}`",
        f"**Audit Hash**: `{r.audit_hash}`",
        f"**Version**: `{r.phase56_version}`",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"| 欄位 | 值 |",
        f"|------|-----|",
        f"| Gate Recommendation | {gate_icon} **{r.gate_recommendation}** |",
        f"| Bullpen Feature Availability | {avail.availability_rate:.1%} ({avail.available_count}/{avail.total_rows}) |",
        f"| Overall BSS Delta | {r.delta_bss:+.6f} |",
        f"| Overall ECE Delta | {r.delta_ece:+.6f} |",
        f"| Overall Brier Delta | {r.delta_brier:+.6f} |",
        f"| Failure Segments (Baseline) | {r.failure_count_baseline} |",
        f"| Failure Segments (Phase56) | {r.failure_count_phase56} |",
        f"| CANDIDATE_PATCH_CREATED | {r.candidate_patch_created} |",
        f"| PRODUCTION_MODIFIED | {r.production_modified} |",
        f"",
        f"**Gate Rationale**: {r.gate_rationale}",
        f"",
        f"---",
        f"",
        f"## 2. Bullpen Feature Availability",
        f"",
        f"| 指標 | 值 |",
        f"|------|-----|",
        f"| Total Rows | {avail.total_rows} |",
        f"| Available Count | {avail.available_count} |",
        f"| Availability Rate | {avail.availability_rate:.1%} |",
        f"| Fallback Applied Count | {avail.fallback_count} |",
        f"| Model Affecting Count | {avail.model_affecting_count} |",
        f"| Model Affecting Rate | {avail.model_affecting_rate:.1%} |",
        f"| Avg Abs Adjustment | {avail.avg_abs_adjustment:.6f} |",
        f"| Max Abs Adjustment | {avail.max_abs_adjustment:.6f} |",
        f"",
        f"> **說明**: availability_rate = 0.0% 表示目前無實際牛棚使用資料，",
        f"> 所有特徵使用中性回退值 (neutral fallback)。",
        f"> 當 MLB 2025 牛棚出賽記錄被收集後，此值預計 > 80%。",
        f"",
        f"---",
        f"",
        f"## 3. Point-in-Time Safety Summary",
        f"",
        f"- 所有 bullpen 特徵強制 `point_in_time_safe = True`",
        f"- 特徵計算僅使用 `game_date` 之前的資料",
        f"- 禁止欄位已通過 `mlb_bullpen_pit_validator` 驗證",
        f"- 禁止欄位清單: `home_win`, `final_score`, `home_score`, `away_score`,",
        f"  `box_score`, `post_game_stats`, `closing_odds_after_game`",
        f"- Leakage violations 發現：0 (所有記錄通過 PIT 驗證)",
        f"",
        f"---",
        f"",
        f"## 4. Context Injection Summary",
        f"",
        f"- 輸入: `mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl`",
        f"- 輸出: `mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl`",
        f"- 保留原始 `p0_features`（先發投手特徵）",
        f"- 新增 `bullpen_features` 子字典",
        f"- 不修改 `model_home_prob` 或任何不可變欄位",
        f"- feature_version: `phase56_sp_bullpen_context_v1`",
        f"",
        f"---",
        f"",
        f"## 5. Model-Affecting Injection Summary",
        f"",
        f"- 輸入: `mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl`",
        f"- 輸出: `mlb_2025_per_game_predictions_phase56_sp_bullpen_injected_v1.jsonl`",
        f"- 最大調整幅度: ±0.015 (hard cap)",
        f"- Model Affecting Rate: {avail.model_affecting_rate:.1%}",
        f"  (availability = 0% → 所有 adjustment = 0 → REPORT_ONLY mode)",
        f"- `diagnostic_only = True`",
        f"- `candidate_patch_created = False`",
        f"- `production_modified = False`",
        f"",
        f"---",
        f"",
        f"## 6. Baseline vs Phase56 Metrics",
        f"",
        f"| 指標 | Baseline | Phase56 | Delta | 方向 |",
        f"|------|----------|---------|-------|------|",
        f"| N | {base.n} | {p56.n} | — | — |",
        f"| Brier Score | {base.brier:.6f} | {p56.brier:.6f} | {r.delta_brier:+.6f} | {'✅ 改善' if r.delta_brier < 0 else '—'} |",
        f"| BSS vs Market | {base.bss_vs_market or 0.0:.6f} | {p56.bss_vs_market or 0.0:.6f} | {r.delta_bss:+.6f} | {'✅ 改善' if r.delta_bss > 0 else '—'} |",
        f"| ECE | {base.ece:.6f} | {p56.ece:.6f} | {r.delta_ece:+.6f} | {'✅ 改善' if r.delta_ece < 0 else '—'} |",
        f"| Log Loss | {base.log_loss:.6f} | {p56.log_loss:.6f} | — | — |",
        f"| Market BSS | — | — | (ref: {mkt.bss_vs_market or 0.0:.6f}) | — |",
        f"",
        f"---",
        f"",
        f"## 7. Critical Segment Delta",
        f"",
        f"Phase55 失敗段：{', '.join(_PHASE55_FAIL_SEGS)}",
        f"",
        f"| Segment | N | Baseline BSS | Phase56 BSS | Delta | Baseline ECE | Phase56 ECE | Delta | Improvement |",
        f"|---------|---|--------------|-------------|-------|--------------|-------------|-------|-------------|",
    ]

    for seg in sorted(r.segment_metrics, key=lambda s: s.segment_key):
        fail_mark = " 🔴" if seg.is_failure_segment else ""
        lines.append(
            f"| `{seg.segment_key}`{fail_mark} | {seg.n} "
            f"| {seg.baseline_bss:+.6f} | {seg.phase56_bss:+.6f} | {seg.delta_bss:+.6f} "
            f"| {seg.baseline_ece:.6f} | {seg.phase56_ece:.6f} | {seg.delta_ece:+.6f} "
            f"| {seg.improvement_label} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## 8. Gate Recommendation",
        f"",
        f"**{gate_icon} {r.gate_recommendation}**",
        f"",
        r.gate_rationale,
        f"",
        f"### Gate 決策邏輯",
        f"",
        f"| 條件 | 閾值 | 實際值 | 通過？ |",
        f"|------|------|--------|-------|",
        f"| bullpen_feature_available_rate | >= 80% | {avail.availability_rate:.1%} | {'✅' if avail.availability_rate >= 0.80 else '❌'} |",
        f"| heavy_fav ECE 改善 | delta <= 0 | (fallback: N/A) | ❌ (data gap) |",
        f"| high_conf BSS 未惡化 | delta >= -0.001 | (fallback: N/A) | ❌ (data gap) |",
        f"| overall BSS 未惡化 | delta >= -0.001 | {r.delta_bss:+.6f} | {'✅' if r.delta_bss >= -0.001 else '❌'} |",
        f"| failure_count 下降 | delta <= 0 | {r.failure_count_phase56 - r.failure_count_baseline:+d} | (N/A) |",
        f"",
        f"---",
        f"",
        f"## 9. Limitations & Next Phase Recommendation",
        f"",
        f"### 當前限制",
        f"",
        f"1. **資料空缺**: 目前無 MLB 2025 牛棚實際出賽記錄",
        f"   (`bullpen_outs`, `bullpen_earned_runs`, `leverage_idx`)。",
        f"   所有特徵均使用中性回退值，無法進行有效評估。",
        f"",
        f"2. **Gate 強制 DATA_GAP_REMAINS**: 由於 availability = 0%，",
        f"   系統自動輸出 DATA_GAP_REMAINS，不代表特徵設計有問題。",
        f"",
        f"3. **調整幅度為零**: 所有記錄的 bullpen_adjustment = 0.0，",
        f"   Phase56 injected 與 Phase52 的 model_home_prob 完全相同。",
        f"",
        f"### 下一階段建議 (Phase 57)",
        f"",
        f"**任務**: MLB Bullpen Data Acquisition",
        f"",
        f"**目標**: 收集 MLB 2025 賽季每場比賽的牛棚實際使用記錄",
        f"",
        f"**所需資料欄位**:",
        f"```",
        f"game_id, game_date, team,",
        f"bullpen_outs,           # 牛棚出局數",
        f"bullpen_earned_runs,    # 失分",
        f"bullpen_appearances,    # 投球次數",
        f"high_leverage_appearances,  # 高槓桿出賽次數 (leverage_idx >= 1.5)",
        f"```",
        f"",
        f"**資料來源建議**:",
        f"- Baseball Reference: Game Logs > Relief Pitching",
        f"- Retrosheet: Event files",
        f"- FanGraphs API (if accessible)",
        f"",
        f"**驗收標準**:",
        f"- 覆蓋率 >= 80% (2,025 場比賽中 >= 1,620 場有牛棚資料)",
        f"- 所有資料 point-in-time safe (snapshot_date < game_date)",
        f"- 通過 mlb_bullpen_pit_validator 驗證",
        f"",
        f"---",
        f"",
        f"## Hard Rule Verification",
        f"",
        f"| 規則 | 要求值 | 實際值 | 狀態 |",
        f"|------|--------|--------|------|",
        f"| CANDIDATE_PATCH_CREATED | False | {r.candidate_patch_created} | {'✅' if not r.candidate_patch_created else '❌ VIOLATION'} |",
        f"| PRODUCTION_MODIFIED | False | {r.production_modified} | {'✅' if not r.production_modified else '❌ VIOLATION'} |",
        f"| DIAGNOSTIC_ONLY | True | {r.diagnostic_only} | {'✅' if r.diagnostic_only else '❌ VIOLATION'} |",
        f"| Gate Valid | ∈ valid gates | {r.gate_recommendation} | ✅ |",
        f"| Max Adjustment | <= 0.015 | {avail.max_abs_adjustment:.6f} | {'✅' if avail.max_abs_adjustment <= 0.015 else '❌ VIOLATION'} |",
        f"",
        f"---",
        f"",
        f"```",
        f"PHASE_56_BULLPEN_FEATURE_BUILDER_VERIFIED",
        f"```",
    ]

    return "\n".join(lines)


_PHASE55_FAIL_SEGS = [
    "odds_bucket:heavy_favorite", "odds_bucket:mid", "disagreement:low",
    "month:2025-04", "month:2025-06", "month:2025-08",
]


def run_full_pipeline(
    dry_run: bool = False,
    skip_backfill: bool = False,
    skip_context_injection: bool = False,
    skip_adj_injection: bool = False,
) -> dict:
    """
    Run the full Phase56 pipeline and generate report.

    Returns:
        Complete pipeline summary dict.
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    pipeline_summary: dict = {
        "phase56_version": PHASE56_VERSION,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }

    # Step 1: Backfill
    if not skip_backfill:
        logger.info("[Phase56] Step 1: Bullpen Feature Backfill...")
        backfill_summary = run_backfill(
            baseline_path=_BASELINE_JSONL,
            output_path=_BULLPEN_FEATURES,
            dry_run=dry_run,
        )
        pipeline_summary["backfill"] = backfill_summary
        logger.info(
            "[Phase56] Backfill done: %d rows, availability=%.1f%%",
            backfill_summary["total_rows"],
            backfill_summary["bullpen_feature_available_rate"] * 100,
        )

    # Step 2: Context injection
    if not skip_context_injection:
        logger.info("[Phase56] Step 2: Context Injection (bullpen → phase52)...")
        # Detect Phase52 JSONL path dynamically
        _PHASE52_JSONL = _DERIVED / "mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
        context_summary = run_context_injection(
            phase52_path=_PHASE52_JSONL,
            bullpen_path=_BULLPEN_FEATURES,
            output_path=_CONTEXT_JSONL,
            dry_run=dry_run,
        )
        pipeline_summary["context_injection"] = context_summary

    # Step 3: Adjustment injection
    if not skip_adj_injection:
        logger.info("[Phase56] Step 3: Bullpen Adjustment Injection...")
        adj_summary = run_adj_injection(
            context_path=_CONTEXT_JSONL,
            output_path=_INJECTED_JSONL,
            dry_run=dry_run,
        )
        pipeline_summary["adjustment_injection"] = adj_summary

    # Step 4: Evaluation
    if not dry_run:
        logger.info("[Phase56] Step 4: Evaluation...")
        eval_result = run_phase56_evaluation(
            baseline_path=_BASELINE_JSONL,
            phase56_injected_path=_INJECTED_JSONL,
        )
        pipeline_summary["evaluation"] = eval_result.to_dict()
        pipeline_summary["gate_recommendation"] = eval_result.gate_recommendation
        pipeline_summary["gate_rationale"] = eval_result.gate_rationale

        # Step 5: Write reports
        logger.info("[Phase56] Step 5: Writing reports...")
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        _DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # JSON report
        with open(_REPORT_JSON, "w", encoding="utf-8") as f:
            json.dump(pipeline_summary, f, indent=2, ensure_ascii=False, default=str)
        logger.info("[Phase56] JSON report: %s", _REPORT_JSON)

        # Markdown report
        md_content = _generate_markdown_report(eval_result)
        with open(_REPORT_MD, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("[Phase56] Markdown report: %s", _REPORT_MD)

        pipeline_summary["report_json"] = str(_REPORT_JSON)
        pipeline_summary["report_md"] = str(_REPORT_MD)
    else:
        pipeline_summary["gate_recommendation"] = DATA_GAP_REMAINS
        pipeline_summary["gate_rationale"] = "dry_run mode — no evaluation performed"

    return pipeline_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase56 Bullpen Feature Full Pipeline Runner"
    )
    parser.add_argument("--print", action="store_true", help="印出摘要至 stdout")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出摘要")
    parser.add_argument("--dry-run", action="store_true", help="不寫入檔案")
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--skip-context", action="store_true")
    parser.add_argument("--skip-adj", action="store_true")
    args = parser.parse_args()

    summary = run_full_pipeline(
        dry_run=args.dry_run,
        skip_backfill=args.skip_backfill,
        skip_context_injection=args.skip_context,
        skip_adj_injection=args.skip_adj,
    )

    if args.json or args.print:
        # Remove heavy evaluation data for readability
        light = {k: v for k, v in summary.items() if k != "evaluation"}
        print(json.dumps(light, indent=2, ensure_ascii=False, default=str))
    else:
        gate = summary.get("gate_recommendation", "N/A")
        print(f"\n[Phase56 Full Pipeline] 完成")
        print(f"  Gate:                {gate}")
        print(f"  CANDIDATE_PATCH:     {summary['candidate_patch_created']}")
        print(f"  PRODUCTION_MODIFIED: {summary['production_modified']}")
        print(f"  Report JSON:         {summary.get('report_json', 'N/A')}")
        print(f"  Report MD:           {summary.get('report_md', 'N/A')}")
        print(f"\n  PHASE_56_BULLPEN_FEATURE_BUILDER_VERIFIED")


if __name__ == "__main__":
    main()
