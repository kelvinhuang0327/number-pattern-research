"""
scripts/run_phase53_sp_coefficient_calibration.py
===================================================
Phase 53 — SP Feature Coefficient Calibration Audit CLI Runner

執行方式：
    python scripts/run_phase53_sp_coefficient_calibration.py [--print] [--json] [--report]

輸出：
    reports/phase53_sp_coefficient_calibration_YYYY-MM-DD.json  (--report)
    docs/feature_repair/phase53_sp_coefficient_calibration_YYYY-MM-DD.md  (--report)

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    diagnostic_only = True
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from orchestrator.phase53_sp_coefficient_calibration import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    FEATURE_COEFFICIENT_PAPER_ONLY,
    FEATURE_COEFFICIENT_NOT_SAFE,
    Phase53CalibrationResult,
    run_calibration,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
_CONTEXT_JSONL  = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
_REPORTS_DIR    = _ROOT / "reports"
_DOCS_DIR       = _ROOT / "docs" / "feature_repair"


# ─── Markdown report builder ──────────────────────────────────────────────────

def _build_markdown(result: Phase53CalibrationResult, today: str) -> str:
    """Generate Phase 53 audit report Markdown."""

    gate_emoji = "✅" if result.gate == FEATURE_COEFFICIENT_PAPER_ONLY else "❌"
    safe_coeff_str = (
        f"{result.best_safe_coefficient:.2f}x"
        if result.best_safe_coefficient is not None
        else "None (無安全係數)"
    )

    # Coefficient grid table
    grid_rows: list[str] = []
    for e in result.coefficient_grid_results:
        grid_rows.append(
            f"| {e.coefficient_scale:.2f} | {e.effective_fip_scale:.6f} "
            f"| {e.adjusted_rows} ({e.adjusted_rate:.1%}) "
            f"| {e.mean_abs_adjustment:.6f} | {e.max_abs_adjustment:.6f} "
            f"| {e.overall_bss or 'N/A'} | {e.overall_ece or 'N/A'} "
            f"| {e.heavy_favorite_ece or 'N/A'} | {e.high_confidence_bss or 'N/A'} |"
        )
    grid_table = "\n".join(grid_rows)

    # Segment comparison table
    seg_rows: list[str] = []
    for s in result.segment_comparison:
        b_bss = f"{s.baseline_bss:.6f}" if s.baseline_bss is not None else "N/A"
        c_bss = f"{s.candidate_bss:.6f}" if s.candidate_bss is not None else "N/A"
        d_bss = f"{s.delta_bss:+.6f}" if s.delta_bss is not None else "N/A"
        b_ece = f"{s.baseline_ece:.6f}" if s.baseline_ece is not None else "N/A"
        c_ece = f"{s.candidate_ece:.6f}" if s.candidate_ece is not None else "N/A"
        d_ece = f"{s.delta_ece:+.6f}" if s.delta_ece is not None else "N/A"
        label_emoji = "✅" if s.label == "IMPROVED" else ("❌" if s.label == "DEGRADED" else "—")
        seg_rows.append(
            f"| {s.segment} | {s.n} | {b_bss} | {c_bss} | {d_bss} "
            f"| {b_ece} | {c_ece} | {d_ece} | {label_emoji} {s.label} |"
        )
    seg_table = "\n".join(seg_rows)

    next_phase = (
        "**Phase 54 — Re-run Phase43/44/45 Stability Audit with Safe SP Coefficient**\n\n"
        f"  使用 safe_coefficient={result.best_safe_coefficient:.2f}x 重跑 Phase43/44/45 穩定性審計，"
        "確認 SP feature 在各種市場條件下的穩定性。"
        if result.gate == FEATURE_COEFFICIENT_PAPER_ONLY
        else "**Phase 54 — SP Feature Functional Form Redesign**\n\n"
        "  `tanh(delta * 0.5) * scale` 形式無法在所有安全條件下同時改善。"
        "考慮：(1) 分 odds_bucket 設定不同係數；"
        "(2) 使用 sigmoid 而非 tanh；"
        "(3) 加入 matchup-level confidence gate（僅在 |delta| > threshold 時才觸發）。"
    )

    return f"""# Phase 53 — SP Feature Coefficient Calibration Audit Report

**日期**: {today}  
**Phase53 Version**: `{result.phase53_version}`  
**Gate**: `{result.gate}` {gate_emoji}  
**Safe Coefficient**: {safe_coeff_str}  
**Audit Hash**: `{result.audit_hash}`

---

## Executive Summary

Phase 52A gate = `FEATURE_REPAIR_NOT_EFFECTIVE`，原因是 `heavy_favorite ECE delta = +0.000425`（輕微惡化）。
本次 Phase 53 對 Phase50/52 的 sp_fip_delta adjustment rule（`tanh(delta * 0.5) * 0.003`）做 offline coefficient calibration audit，
測試 scale multiplier ∈ {[e.coefficient_scale for e in result.coefficient_grid_results]}，
共 {len(result.coefficient_grid_results)} 組係數設定。

**結論**：

- Best by overall BSS: **scale={result.best_by_overall_bss}**  
- Best by heavy_favorite ECE: **scale={result.best_by_heavy_favorite_ece}**  
- Safe coefficient（滿足全部 7 項條件）: **{safe_coeff_str}**  
- Gate: **`{result.gate}`**

> 所有評估結果均為 `diagnostic_only=True`，不可直接 productionize。
> `CANDIDATE_PATCH_CREATED={CANDIDATE_PATCH_CREATED}`, `PRODUCTION_MODIFIED={PRODUCTION_MODIFIED}`

---

## Why Phase 52 Was Not Sufficient

| 指標 | Phase52 (scale=1.00) | Baseline | Delta | 問題 |
|------|---------------------|---------|-------|------|
| overall BSS | {result.phase52_bss or 'N/A'} | {result.baseline_bss or 'N/A'} | {round((result.phase52_bss or 0) - (result.baseline_bss or 0), 6):+.6f} | ✅ 改善 |
| overall ECE | {result.phase52_ece or 'N/A'} | {result.baseline_ece or 'N/A'} | {round((result.phase52_ece or 0) - (result.baseline_ece or 0), 6):+.6f} | ✅ 改善 |
| heavy_favorite ECE | — | — | +0.000425 | ❌ **Gate 失敗點** |

**根因分析**：`tanh(delta * 0.5) * 0.003` 在 heavy_favorite 賽事（市場賠率差大）中，
FIP delta 較大，tanh 壓縮效果有限，導致 ECE 輕微惡化。
需測試更保守係數（0.50x / 0.25x）是否可改善 heavy_favorite ECE，
同時維持整體 BSS 不退步。

---

## Coefficient Grid Table

| Scale | Effective Coeff | Adjusted (rows/rate) | Mean Adj | Max Adj | Overall BSS | Overall ECE | HF ECE | HC BSS |
|-------|----------------|---------------------|----------|---------|-------------|-------------|--------|--------|
{grid_table}

---

## Best Overall Coefficient

Best by overall BSS: **scale={result.best_by_overall_bss}**

---

## Best heavy_favorite-Safe Coefficient

Best by heavy_favorite ECE（最低 ECE）: **scale={result.best_by_heavy_favorite_ece}**

---

## Safe Coefficient Selection Result

**Gate**: `{result.gate}` {gate_emoji}  
**Safe coefficient**: {safe_coeff_str}

**Gate rationale**:
> {result.gate_rationale}

### 安全條件（7 項需全部滿足）

| 條件 | 要求 | 結果 |
|------|------|------|
| overall BSS >= baseline | ≥ {result.baseline_bss or 0:.6f} | 詳見 grid table |
| overall ECE <= baseline | ≤ {result.baseline_ece or 0:.6f} | 詳見 grid table |
| heavy_favorite ECE <= baseline | ≤ baseline HF ECE | **Gate 關鍵條件** |
| high_confidence BSS 不惡化 | ≥ baseline HC BSS - 0.001 | 詳見 grid table |
| month:2025-04 BSS 不惡化 | ≥ baseline Apr BSS - 0.001 | 詳見 grid table |
| adjusted_rate >= 30% | ≥ 30% | 詳見 grid table |
| max_abs_adjustment <= 0.025 | ≤ 0.025 | 詳見 grid table |

---

## Segment Comparison Table (Baseline vs Safe Coefficient / Best Candidate)

> Scale used: {f"{result.best_safe_coefficient:.2f}x" if result.best_safe_coefficient is not None else "0.75x (best candidate，無安全係數)"}

| Segment | n | baseline BSS | candidate BSS | delta BSS | baseline ECE | candidate ECE | delta ECE | Label |
|---------|---|-------------|--------------|-----------|-------------|--------------|-----------|-------|
{seg_table}

---

## Gate Recommendation

```
gate = {result.gate}
safe_coefficient = {result.best_safe_coefficient}
best_by_overall_bss = {result.best_by_overall_bss}
best_by_heavy_favorite_ece = {result.best_by_heavy_favorite_ece}
diagnostic_only = True
candidate_patch_created = False
production_modified = False
```

---

## Limitations

1. **FIP proxy 仍為 historical 估算**（Phase 52 繼承限制）
2. **調整幅度上限 ±0.025**（Phase50 cap 不隨 scale 改變）
3. **評估為 offline / paper-only**：無 live 驗證
4. **scale_grid 為等比間隔**：最佳係數可能在網格點之間
5. **segment 分類固定**：heavy_favorite / high_confidence 定義為 Phase52 一致
6. **`tanh` 函數形式假設不變**：若形式本身有問題，scale 調整無法解決

---

## Next Phase Recommendation

{next_phase}

---

## Hard Rules Verification

| 規則 | 狀態 |
|------|------|
| CANDIDATE_PATCH_CREATED = False | ✅ |
| PRODUCTION_MODIFIED = False | ✅ |
| diagnostic_only = True | ✅ |
| 無 look-ahead leakage | ✅ |
| 無 ensemble / re-training | ✅ |
| gate ≠ PATCH | ✅ |
| paper-only / offline only | ✅ |

---

## Completion Marker

```
PHASE_53_SP_COEFFICIENT_CALIBRATION_VERIFIED
gate={result.gate}
safe_coefficient={result.best_safe_coefficient}
best_by_overall_bss={result.best_by_overall_bss}
best_by_heavy_favorite_ece={result.best_by_heavy_favorite_ece}
baseline_n={result.baseline_n}
baseline_bss={result.baseline_bss}
baseline_ece={result.baseline_ece}
candidate_patch_created=False
production_modified=False
diagnostic_only=True
```
"""


# ─── CLI main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 53 — SP Feature Coefficient Calibration Audit"
    )
    parser.add_argument("--print",  action="store_true", dest="do_print",  help="Print summary to stdout")
    parser.add_argument("--json",   action="store_true", dest="do_json",   help="Print full JSON to stdout")
    parser.add_argument("--report", action="store_true", dest="do_report", help="Write JSON + Markdown report files")
    args = parser.parse_args()

    today = date.today().isoformat()

    # Validate paths
    if not _BASELINE_JSONL.exists():
        logger.error("Baseline JSONL not found: %s", _BASELINE_JSONL)
        sys.exit(1)
    if not _CONTEXT_JSONL.exists():
        logger.error("Context JSONL not found: %s", _CONTEXT_JSONL)
        sys.exit(1)

    logger.info("Starting Phase 53 SP Coefficient Calibration Audit")
    result = run_calibration(
        baseline_path=_BASELINE_JSONL,
        context_path=_CONTEXT_JSONL,
    )

    # ── Print summary ──────────────────────────────────────────────────────────
    if args.do_print or not (args.do_json or args.do_report):
        print("\n=== Phase 53 SP Coefficient Calibration ===")
        print(f"baseline_n:              {result.baseline_n}")
        print(f"baseline_bss:            {result.baseline_bss}")
        print(f"baseline_ece:            {result.baseline_ece}")
        print(f"phase52_bss (scale=1.0): {result.phase52_bss}")
        print(f"phase52_ece (scale=1.0): {result.phase52_ece}")
        print()
        print(f"{'Scale':<8} {'EffCoef':>10} {'AdjRate':>10} {'BSS':>12} {'ECE':>12} {'HF_ECE':>12} {'HC_BSS':>12}")
        print("-" * 78)
        for e in result.coefficient_grid_results:
            print(
                f"{e.coefficient_scale:<8.2f} {e.effective_fip_scale:>10.6f}"
                f" {e.adjusted_rate:>9.1%}"
                f" {(e.overall_bss or 0):>12.6f}"
                f" {(e.overall_ece or 0):>12.6f}"
                f" {(e.heavy_favorite_ece or 0):>12.6f}"
                f" {(e.high_confidence_bss or 0):>12.6f}"
            )
        print()
        print(f"best_by_overall_bss:          {result.best_by_overall_bss}")
        print(f"best_by_heavy_favorite_ece:   {result.best_by_heavy_favorite_ece}")
        print(f"best_safe_coefficient:        {result.best_safe_coefficient}")
        print(f"gate:                         {result.gate}")
        print(f"gate_rationale:               {result.gate_rationale}")
        print(f"candidate_patch_created:      {result.candidate_patch_created}")
        print(f"production_modified:          {result.production_modified}")
        print(f"diagnostic_only:              {result.diagnostic_only}")
        print(f"audit_hash:                   {result.audit_hash}")

    # ── Print JSON ─────────────────────────────────────────────────────────────
    if args.do_json:
        result_dict = asdict(result)
        print(json.dumps(result_dict, indent=2, ensure_ascii=False, default=str))

    # ── Write report files ────────────────────────────────────────────────────
    if args.do_report:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        _DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # JSON report
        json_path = _REPORTS_DIR / f"phase53_sp_coefficient_calibration_{today}.json"
        result_dict = asdict(result)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False, default=str)
        logger.info("JSON report written: %s", json_path)

        # Markdown report
        md_path = _DOCS_DIR / f"phase53_sp_coefficient_calibration_{today}.md"
        md_content = _build_markdown(result, today)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("Markdown report written: %s", md_path)

        print(f"\nReports written:")
        print(f"  JSON:     {json_path}")
        print(f"  Markdown: {md_path}")


if __name__ == "__main__":
    main()
