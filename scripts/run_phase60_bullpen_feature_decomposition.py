#!/usr/bin/env python3
"""
Phase 60 Runner — Bullpen Feature Decomposition and PIT-safe Attribution

Usage:
    python scripts/run_phase60_bullpen_feature_decomposition.py [--print] [--json] [--report]

Outputs:
    reports/phase60_bullpen_feature_decomposition_20260506.json
    00-BettingPlan/phase60_bullpen_feature_decomposition_report_20260506.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.phase60_bullpen_feature_decomposition import (
    ALPHA,
    BULLPEN_FEATURE_NOT_PROMISING,
    BULLPEN_FEATURE_PROMISING,
    DATA_LIMITED,
    DIAGNOSTIC_ONLY,
    DIAGNOSTIC_ONLY_SIGNAL,
    PHASE_VERSION,
    result_to_dict,
    run_phase60_decomposition,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
_DEFAULT_PREDICTIONS = "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
_DEFAULT_BULLPEN = "data/mlb_context/bullpen_usage_3d.jsonl"
_DEFAULT_REST = "data/mlb_context/injury_rest.jsonl"
_REPORT_DATE = "20260506"
_JSON_OUT = f"reports/phase60_bullpen_feature_decomposition_{_REPORT_DATE}.json"
_MD_OUT = f"00-BettingPlan/phase60_bullpen_feature_decomposition_report_{_REPORT_DATE}.md"


# ---------------------------------------------------------------------------
# Markdown Report Generator
# ---------------------------------------------------------------------------

def _gate_emoji(gate: str) -> str:
    return {
        BULLPEN_FEATURE_PROMISING: "✅",
        DIAGNOSTIC_ONLY_SIGNAL: "⚠️",
        DATA_LIMITED: "🔶",
        BULLPEN_FEATURE_NOT_PROMISING: "❌",
    }.get(gate, "❓")


def generate_markdown_report(data: dict) -> str:
    """Generate a human-readable Markdown report from the JSON result dict."""
    gate = data["gate"]
    emoji = _gate_emoji(gate)
    run_ts = data["run_timestamp"][:19].replace("T", " ")

    lines: list[str] = []
    a = lines.append

    # ---------------------------------------------------------------------------
    # Section 1: Header
    # ---------------------------------------------------------------------------
    a("# Phase 60 — Bullpen Feature Decomposition and PIT-safe Attribution")
    a("")
    a(f"**版本**: `{data['phase_version']}`  ")
    a(f"**執行時間**: {run_ts} UTC  ")
    a(f"**Audit Hash**: `{data['audit_hash']}`  ")
    a(f"**Gate**: {emoji} `{gate}`")
    a("")

    # ---------------------------------------------------------------------------
    # Section 2: Safety Constants
    # ---------------------------------------------------------------------------
    a("## Section 2 — 安全常數快照 (Safety Constants)")
    a("")
    a("| 常數 | 值 |")
    a("|------|-----|")
    a(f"| CANDIDATE_PATCH_CREATED | `{data['candidate_patch_created']}` |")
    a(f"| PRODUCTION_MODIFIED | `{data['production_modified']}` |")
    a(f"| ALPHA_MODIFIED | `{data['alpha_modified']}` |")
    a(f"| DIAGNOSTIC_ONLY | `{data['diagnostic_only']}` |")
    a(f"| ALPHA | `{data['alpha']}` (FROZEN) |")
    a("")
    a("> 本 Phase 為純診斷分析，不產生任何生產補丁。")
    a("")

    # ---------------------------------------------------------------------------
    # Section 3: Data Summary
    # ---------------------------------------------------------------------------
    a("## Section 3 — 資料摘要 (Data Summary)")
    a("")
    a(f"- **預測樣本數**: {data['n_predictions']:,}")
    a(f"- **牛棚資料筆數**: {data['n_bullpen_rows']:,}")
    a(f"- **成功對齊 (aligned)**: {data['n_aligned']:,}")
    a(f"- **對齊率**: {data['alignment_rate']:.1%}")
    a("")
    a("### Segment 大小")
    a("")
    a("| Segment | N |")
    a("|---------|---|")
    a(f"| All (usable predictions) | {data['segment_n_all']:,} |")
    a(f"| heavy_favorite (fav ≥ 0.70) | {data['segment_n_heavy_fav']} |")
    a(f"| high_confidence (fav ≥ 0.75) | {data['segment_n_high_conf']} |")
    a(f"| phase45_failure (hf + low_disagree) | {data['segment_n_phase45_failure']} |")
    a("")
    a(f"> **高信心閾值說明**: {data['high_conf_note']}")
    a("")

    # ---------------------------------------------------------------------------
    # Section 4: Feature Family Metadata
    # ---------------------------------------------------------------------------
    a("## Section 4 — 特徵家族清單 (Feature Families)")
    a("")
    a(f"**可用特徵數**: {data['n_available_features']}  ")
    a(f"**DATA_LIMITED 特徵數**: {data['n_data_limited_features']}")
    a("")
    a("| 特徵名稱 | 可用? | Coverage | N Usable | 說明 |")
    a("|---------|------|---------|---------|------|")
    for fm in data["feature_families"]:
        status = "✅" if fm["available"] else "🔶 DATA_LIMITED"
        cov = f"{fm['coverage_pct']:.1%}" if fm["available"] else "—"
        n_use = fm["n_usable"] if fm["available"] else "—"
        desc = fm["description"]
        if not fm["available"] and fm["data_limited_reason"]:
            desc += f" *(原因: {fm['data_limited_reason']})*"
        a(f"| `{fm['feature_name']}` | {status} | {cov} | {n_use} | {desc} |")
    a("")

    # ---------------------------------------------------------------------------
    # Section 5: Attribution by Segment
    # ---------------------------------------------------------------------------
    a("## Section 5 — Segment Attribution 分析")
    a("")
    a("### 5A — heavy_favorite Segment (fav ≥ 0.70)")
    a("")
    hf_attrs = [x for x in data["attributions"] if x["segment"] == "heavy_favorite"]
    if hf_attrs:
        a("| 特徵 | N | Coverage | ECE | BSS | Calib Residual | win_rate Δ | Bootstrap Sig |")
        a("|------|---|---------|-----|-----|---------------|-----------|--------------|")
        for attr in hf_attrs:
            ba = attr.get("bucket_attribution") or {}
            delta = f"{ba.get('win_rate_delta', 0):+.4f}" if ba else "N/A"
            sig = "**YES**" if ba and ba.get("bootstrap_significant") else "no"
            a(
                f"| `{attr['feature_name']}` "
                f"| {attr['n']} "
                f"| {attr['coverage_pct']:.1%} "
                f"| {attr['ece']:.4f} "
                f"| {attr['baseline_bss']:+.4f} "
                f"| {attr['calibration_residual']:+.4f} "
                f"| {delta} "
                f"| {sig} |"
            )
    else:
        a("*(無資料)*")
    a("")

    a("### 5B — all Segment")
    a("")
    all_attrs = [x for x in data["attributions"] if x["segment"] == "all"]
    if all_attrs:
        # Summarize key features only
        key_features = ["fav_vs_dog_delta_3d", "fav_fatigue_3d", "bull_delta_3d"]
        a("| 特徵 | N | ECE | BSS | win_rate Δ |")
        a("|------|---|-----|-----|-----------|")
        for attr in all_attrs:
            if attr["feature_name"] in key_features:
                ba = attr.get("bucket_attribution") or {}
                delta = f"{ba.get('win_rate_delta', 0):+.4f}" if ba else "N/A"
                a(
                    f"| `{attr['feature_name']}` "
                    f"| {attr['n']} "
                    f"| {attr['ece']:.4f} "
                    f"| {attr['baseline_bss']:+.4f} "
                    f"| {delta} |"
                )
    a("")

    a("### 5C — phase45_failure Segment (hf + low_disagreement)")
    a("")
    p45_attrs = [x for x in data["attributions"] if x["segment"] == "phase45_failure"]
    if p45_attrs:
        a("| 特徵 | N | ECE | win_rate Δ | Bootstrap Sig |")
        a("|------|---|-----|-----------|--------------|")
        for attr in p45_attrs:
            ba = attr.get("bucket_attribution") or {}
            delta = f"{ba.get('win_rate_delta', 0):+.4f}" if ba else "N/A"
            sig = "**YES**" if ba and ba.get("bootstrap_significant") else "no"
            a(f"| `{attr['feature_name']}` | {attr['n']} | {attr['ece']:.4f} | {delta} | {sig} |")
    a("")

    # ---------------------------------------------------------------------------
    # Section 6: OOF Validation
    # ---------------------------------------------------------------------------
    a("## Section 6 — Rolling Monthly OOF Validation")
    a("")
    oof = data["oof_summary"]
    a(f"**特徵**: `fav_vs_dog_delta_3d` (最佳候選)  ")
    a(f"**Segment**: heavy_favorite  ")
    a(f"**Folds**: {oof['n_folds']}  ")
    a(f"**OOF 平均 win_rate_delta**: `{oof['oof_mean_delta']:+.4f}`  ")
    a(f"**Consistent Sign**: `{oof['oof_consistent_sign']}`  ")
    a(f"**OOF Significant (≥{0.02})**: `{oof['oof_significant']}`")
    a("")
    if oof["n_folds"] > 0:
        a("| 測試月份 | win_rate_delta | N |")
        a("|---------|---------------|---|")
        for month, delta, n in zip(oof["fold_months"], oof["fold_win_rate_deltas"], oof["fold_n"]):
            a(f"| {month} | `{delta:+.4f}` | {n} |")
        a("")

    # ---------------------------------------------------------------------------
    # Section 7: Negative Control
    # ---------------------------------------------------------------------------
    a("## Section 7 — Negative Control (Shuffle Test)")
    a("")
    nc = data["negative_control"]
    a(f"**特徵**: `fav_vs_dog_delta_3d` on heavy_fav  ")
    a(f"**真實 win_rate_delta**: `{nc['real_win_rate_delta_heavy_fav']:+.4f}`  ")
    a(f"**Shuffled mean delta**: `{nc['shuffled_mean_delta']:+.4f}`  ")
    a(f"**Shuffled std**: `{nc['shuffled_std_delta']:.4f}`  ")
    a(f"**Null Rejected (real > mean+1.5σ)**: `{nc['null_rejected']}`")
    a("")
    if nc["null_rejected"]:
        a("> 真實訊號超過隨機排列 1.5σ 閾值，具有一定的統計可分性。")
    else:
        a("> 真實訊號無法與隨機排列顯著區分，signal 可能源自噪音。")
    a("")

    # ---------------------------------------------------------------------------
    # Section 8: DATA_LIMITED Features Summary
    # ---------------------------------------------------------------------------
    a("## Section 8 — DATA_LIMITED 特徵說明")
    a("")
    dl_features = [fm for fm in data["feature_families"] if not fm["available"]]
    if dl_features:
        for fm in dl_features:
            a(f"- **`{fm['feature_name']}`**: {fm['data_limited_reason']}")
    a("")
    a("這些特徵需要更細粒度的資料源（逐日 boxscore 或 play-by-play 等）才能實現。")
    a("建議在未來數據擴充計劃中列入需求。")
    a("")

    # ---------------------------------------------------------------------------
    # Section 9: PIT Safety Validation
    # ---------------------------------------------------------------------------
    a("## Section 9 — PIT 安全性驗證")
    a("")
    a("- **PIT 安全原則**: `entry_date < game_date`（嚴格隔離）")
    a("- **bullpen_usage_last_3d_***: 累計 D-1 + D-2 + D-3 局數（開賽前）✅")
    a("- **rest_days_***: 賽前狀態資料 ✅")
    a("- **home_win 欄位**: 僅作為預測標籤 `_label_home_win`，絕不作為特徵 ✅")
    a("- **禁用特徵模式**: `home_win`, `result`, `final`, `winning` — 自動拒絕 ✅")
    a("")

    # ---------------------------------------------------------------------------
    # Section 10: Root Cause Attribution (Phase 45 Failure)
    # ---------------------------------------------------------------------------
    a("## Section 10 — Phase 45 Failure Segment 根因歸因")
    a("")
    a("Phase 45 的 failure segments 包含：")
    a("- `odds_bucket:heavy_favorite` (fav_prob ≥ 0.70)")
    a("- `disagreement:low` (|model - market| ≤ 中位數 0.0414)")
    a("")

    p45_fav = next(
        (x for x in p45_attrs if x["feature_name"] == "fav_vs_dog_delta_3d"),
        None
    )
    if p45_fav and p45_fav.get("bucket_attribution"):
        ba = p45_fav["bucket_attribution"]
        a(f"**phase45_failure 段 `fav_vs_dog_delta_3d` attribution**:")
        a(f"- N = {p45_fav['n']}")
        a(f"- win_rate_high (fav tired) = {ba['win_rate_high']:.4f}")
        a(f"- win_rate_low (fav rested) = {ba['win_rate_low']:.4f}")
        a(f"- win_rate_delta = {ba['win_rate_delta']:+.4f}")
        a(f"- Bootstrap 95% CI: [{ba['bootstrap_ci_lower']:+.4f}, {ba['bootstrap_ci_upper']:+.4f}]")
        a(f"- Bootstrap Significant: {ba['bootstrap_significant']}")
        a("")
        if abs(ba["win_rate_delta"]) < 0.02:
            a("> bullpen 疲勞特徵對於 phase45 failure segment 的影響微弱，")
            a("> 不足以解釋 Phase 45 重熱門偏差的根源。根因可能來自其他因素")
            a("> （如 SP 品質指標缺漏、市場均衡噪音、樣本過小）。")
        else:
            a("> bullpen 疲勞特徵顯示一定方向性，但樣本過小，需謹慎解讀。")
    else:
        a(f"*(phase45_failure segment 樣本數不足，無法計算 bucket attribution)*")
    a("")

    # ---------------------------------------------------------------------------
    # Section 11: Gate Decision
    # ---------------------------------------------------------------------------
    a("## Section 11 — Gate 決策")
    a("")
    a(f"### {emoji} Gate: `{gate}`")
    a("")
    a(f"**理由**: {data['gate_rationale']}")
    a("")
    a("### 後續行動建議")
    a("")
    if gate == BULLPEN_FEATURE_PROMISING:
        a("1. 將 `fav_vs_dog_delta_3d` 納入模型候選特徵集")
        a("2. 在 Phase 61 執行正式的特徵注入實驗（Walk-Forward）")
        a("3. 確保所有特徵在 walk-forward 分割中均保持 PIT 安全")
    elif gate == DIAGNOSTIC_ONLY_SIGNAL:
        a("1. 訊號方向一致，但 OOF 驗證樣本不足（heavy_fav n 偏小）")
        a("2. **不建議立即注入生產模型**")
        a("3. 建議繼續累積 2025 賽季資料至 ≥ 100 heavy_fav 場次後重新驗證")
        a("4. 或探索更細粒度的牛棚資料（1d / closer 特定資料）")
    elif gate == DATA_LIMITED:
        a("1. 關鍵 segment 樣本數不足")
        a("2. 等待更多資料或放寬 heavy_fav 閾值後重新評估")
    else:  # NOT_PROMISING
        a("1. 牛棚 3d 使用量特徵對預測無顯著貢獻")
        a("2. 考慮探索其他資料源（進階 boxscore、球員層級資料等）")
    a("")

    # ---------------------------------------------------------------------------
    # Completion Marker
    # ---------------------------------------------------------------------------
    a("---")
    a("")
    a(f"*Report generated by `{PHASE_VERSION}` at {run_ts} UTC*  ")
    a(f"*Audit hash: `{data['audit_hash']}`*  ")
    a("*CANDIDATE_PATCH_CREATED=False | PRODUCTION_MODIFIED=False | DIAGNOSTIC_ONLY=True*")
    a("")
    a("`PHASE_60_BULLPEN_FEATURE_DECOMPOSITION_VERIFIED`")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 60: Bullpen Feature Decomposition and PIT-safe Attribution"
    )
    parser.add_argument(
        "--input", default=_DEFAULT_PREDICTIONS,
        help="Path to predictions JSONL"
    )
    parser.add_argument(
        "--bullpen", default=_DEFAULT_BULLPEN,
        help="Path to bullpen_usage_3d JSONL"
    )
    parser.add_argument(
        "--rest", default=_DEFAULT_REST,
        help="Path to injury_rest JSONL"
    )
    parser.add_argument(
        "--print", dest="print_summary", action="store_true",
        help="Print summary to stdout"
    )
    parser.add_argument(
        "--json", dest="write_json", action="store_true",
        help=f"Write JSON report to {_JSON_OUT}"
    )
    parser.add_argument(
        "--report", dest="write_report", action="store_true",
        help=f"Write Markdown report to {_MD_OUT}"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print(f"[Phase 60] Running {PHASE_VERSION}...")
    print(f"  Input: {args.input}")
    print(f"  Bullpen: {args.bullpen}")
    print(f"  Rest: {args.rest}")

    result = run_phase60_decomposition(
        predictions_path=args.input,
        bullpen_path=args.bullpen,
        rest_path=args.rest,
    )
    data = result_to_dict(result)

    if args.print_summary:
        print()
        print("=" * 70)
        print(f"  Phase 60 Summary")
        print("=" * 70)
        print(f"  Gate:            {result.gate}")
        print(f"  Audit Hash:      {result.audit_hash}")
        print(f"  N aligned:       {result.n_aligned:,}")
        print(f"  heavy_fav N:     {result.segment_n_heavy_fav}")
        print(f"  high_conf N:     {result.segment_n_high_conf}")
        print(f"  phase45_fail N:  {result.segment_n_phase45_failure}")
        print(f"  Available feats: {result.n_available_features}")
        print(f"  DATA_LIMITED:    {result.n_data_limited_features}")
        print()
        print("  OOF Validation (fav_vs_dog_delta_3d, heavy_fav):")
        print(f"    n_folds:     {result.oof_summary.n_folds}")
        print(f"    mean_delta:  {result.oof_summary.oof_mean_delta:+.4f}")
        print(f"    significant: {result.oof_summary.oof_significant}")
        print()
        print("  Negative Control:")
        print(f"    real_delta:     {result.negative_control.real_win_rate_delta_heavy_fav:+.4f}")
        print(f"    null_rejected:  {result.negative_control.null_rejected}")
        print()
        print("  heavy_fav Attribution (fav_vs_dog_delta_3d):")
        hf_key = next(
            (a for a in result.attributions
             if a.feature_name == "fav_vs_dog_delta_3d" and a.segment == "heavy_favorite"),
            None
        )
        if hf_key and hf_key.bucket_attribution:
            ba = hf_key.bucket_attribution
            print(f"    win_rate_high: {ba.win_rate_high:.4f}")
            print(f"    win_rate_low:  {ba.win_rate_low:.4f}")
            print(f"    delta:         {ba.win_rate_delta:+.4f}")
            print(f"    bootstrap_sig: {ba.bootstrap_significant}")
        print("=" * 70)
        print()

    if args.write_json:
        Path(_JSON_OUT).parent.mkdir(parents=True, exist_ok=True)
        with open(_JSON_OUT, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"[Phase 60] JSON report written → {_JSON_OUT}")

    if args.write_report:
        md = generate_markdown_report(data)
        Path(_MD_OUT).parent.mkdir(parents=True, exist_ok=True)
        with open(_MD_OUT, "w") as f:
            f.write(md)
        print(f"[Phase 60] Markdown report written → {_MD_OUT}")

    # Final gate echo
    print(f"[Phase 60] Gate: {result.gate}")
    print("[Phase 60] CANDIDATE_PATCH_CREATED=False | PRODUCTION_MODIFIED=False | DIAGNOSTIC_ONLY=True")


if __name__ == "__main__":
    main()
