#!/usr/bin/env python3
"""
P229-A CLI — 建立 Run Line evidence boundary pack（純彙整，非新模型任務）。

用法（自 repo 根目錄）：
    python3 scripts/build_p229a_run_line_evidence_boundary_pack.py

本檔不重跑、不修改 P226-A / P227-A / P228-A 任何模型或報告；只讀取三者既有的
`report/*.json` 輸出（read-only 輸入），彙整成一份「已證實 / 未證實 / 缺口 /
建議下一步（未授權）」的 evidence boundary pack，供 CTO/CEO 決策參考。純本機、
無網路、無 DB/production 變更、無下注建議、無未來預測。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "report"
P226A_JSON = REPORT_DIR / "p226a_run_line_total_scorecard.json"
P227A_JSON = REPORT_DIR / "p227a_total_calibration_scorecard.json"
P228A_JSON = REPORT_DIR / "p228a_run_line_robustness_scorecard.json"

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "descriptive synthesis of already-published P226-A / P227-A / P228-A results; "
    "NOT a new model, NOT a re-run, NOT a re-derivation",
    "NO betting recommendation; NO EV/Kelly claim; NOT a proven edge",
    "NO live-market claim; NOT production; NOT real betting",
    "NO future prediction; NO CLV claim; NO tradable-odds-edge claim",
    "P226-A / P227-A / P228-A source artifacts are read-only inputs and are not "
    "modified by this pack",
    "recommended next technical step is NOT authorized by this pack; a separate "
    "explicit Owner authorization is required before any further work begins",
]

SUPPORTED_CLAIMS = [
    "Run Line signal is robust enough for further historical research "
    "(P228-A final label: `ROBUST_ENOUGH_FOR_FURTHER_HISTORICAL_RESEARCH`).",
    "Run Line is stronger than Total under the current historical, paper-only "
    "Poisson team-rate model family (Run Line beats the 0.5 coinflip Brier "
    "baseline; Total does not).",
    "Deterministic, test-covered local artifacts exist for P226-A and P228-A "
    "(reports + CSVs + passing pytest suites), so the reported figures are "
    "reproducible from tracked repo state.",
]

UNSUPPORTED_CLAIMS = [
    "NO real betting edge claim — all figures are descriptive historical "
    "backtest statistics, not a forward-looking edge claim.",
    "NO live readiness — no live market data transport exists or has been "
    "authorized for this line of work.",
    "NO production readiness — no DB / registry / production writes have "
    "occurred as part of P226-A / P227-A / P228-A / this pack.",
    "NO future prediction ability — all evaluated games are historical "
    "(already-played 2025 season games); no forward-looking game is scored.",
    "NO proof of tradable odds edge — no verified pregame odds price feed has "
    "been used; run line lines/prices are used for settlement and descriptive "
    "reference only, never as a model input feature.",
    "NO CLV evidence — the odds source (`mlb_odds_2025_real.csv`) is a "
    "post-game unverified snapshot (`is_verified_real=False`), not a "
    "point-in-time pregame capture, so no closing-line-value claim is possible.",
]

MISSING_EVIDENCE_NEXT_GATES = [
    "True point-in-time (PIT) odds with real capture timestamps (current data "
    "is a post-game unverified snapshot, not a pregame feed).",
    "Multi-season data, if locally available, to test cross-season robustness "
    "(current evidence is a single season, 2025, plus a 2024 warm-up-only set).",
    "Stronger data provenance / a verified-real odds source for run line "
    "settlement and any future market-reference use.",
    "Starter / lineup / injury point-in-time features, if made available "
    "later, to replace the current team-rate-only inputs.",
    "Final Owner decision before any future-output, live, or production work "
    "is attempted.",
]

RECOMMENDED_NEXT_TECHNICAL_STEP = {
    "candidate": "local multi-season data availability audit for Run Line",
    "alternatives": [
        "feature-ablation scorecard for Run Line",
        "true-PIT odds provenance audit",
    ],
    "authorization_status": "NOT_AUTHORIZED_YET",
    "note": "This pack recommends but does not authorize the next step; a "
    "separate explicit Owner authorization is required before any further "
    "work begins.",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_reports(report_dir: Path = REPORT_DIR) -> dict:
    return {
        "p226a": _load_json(Path(report_dir) / "p226a_run_line_total_scorecard.json"),
        "p227a": _load_json(Path(report_dir) / "p227a_total_calibration_scorecard.json"),
        "p228a": _load_json(Path(report_dir) / "p228a_run_line_robustness_scorecard.json"),
    }


def build_evidence_inventory(sources: dict) -> dict:
    """僅讀取三個上游 report JSON 的既有數值並重新整理呈現，不重新計算任何指標。"""
    p226a, p227a, p228a = sources["p226a"], sources["p227a"], sources["p228a"]

    rl = {m["model_name"]: m for m in p226a["market_comparison"]["run_line"]}
    coinflip_rl, poisson_rl = rl["baseline_coinflip_50pct"], rl["poisson_team_rate_model"]

    total = {m["model_name"]: m for m in p226a["market_comparison"]["total"]}
    coinflip_total, poisson_total = total["baseline_coinflip_50pct"], total["poisson_team_rate_model"]

    conc = p228a["robustness_conclusion"]
    cal = p228a["calibration"]

    return {
        "p226a_run_line_baseline": {
            "source": "report/p226a_run_line_total_scorecard.json",
            "test_period": list(p226a["split"]["test_period"]),
            "test_rows": p226a["split"]["test_rows"],
            "coinflip_accuracy": coinflip_rl["accuracy"],
            "coinflip_brier": coinflip_rl["brier_score"],
            "poisson_accuracy": poisson_rl["accuracy"],
            "poisson_brier": poisson_rl["brier_score"],
            "poisson_ece": poisson_rl["calibration_error"],
        },
        "p228a_split_robustness": {
            "source": "report/p228a_run_line_robustness_scorecard.json",
            "split_grid_total": conc["split_grid_total"],
            "split_grid_strict_wins": conc["split_grid_strict_wins"],
            "split_grid_not_worse_within_tolerance": conc["split_grid_not_worse_within_tolerance"],
            "splits": [
                {
                    "train_frac": e["train_frac"],
                    "test_period": list(e["test_period"]),
                    "poisson_accuracy": e["poisson_accuracy"],
                    "poisson_brier": e["poisson_brier"],
                    "beats_coinflip": e["poisson_beats_coinflip_brier"],
                }
                for e in p228a["split_grid"]
            ],
        },
        "p228a_monthly_robustness": {
            "source": "report/p228a_run_line_robustness_scorecard.json",
            "monthly_windows_evaluated": conc["monthly_windows_evaluated"],
            "monthly_windows_strict_wins": conc["monthly_windows_strict_wins"],
            "monthly_windows_not_worse_within_tolerance": conc["monthly_windows_not_worse_within_tolerance"],
            "monthly_windows_skipped": conc["monthly_windows_skipped"],
            "robustness_label": conc["label"],
        },
        "p228a_calibration": {
            "source": "report/p228a_run_line_robustness_scorecard.json",
            "raw_brier": cal["raw"]["brier_score"],
            "calibrated_brier": cal["calibrated"]["brier_score"],
            "raw_ece": cal["raw"]["calibration_error"],
            "calibrated_ece": cal["calibrated"]["calibration_error"],
            "calibration_beats_raw_brier": cal["calibration_beats_raw_brier"],
            "calibration_beats_raw_ece": cal["calibration_beats_raw_ece"],
        },
        "p227a_total_limitation": {
            "source": "report/p227a_total_calibration_scorecard.json",
            "best_by_brier": p227a["best_by_brier"],
            "beats_coinflip_brier": p227a["beats_coinflip_brier"],
            "beats_poisson_brier": p227a["beats_poisson_brier"],
            "coinflip_brier": coinflip_total["brier_score"],
            "poisson_accuracy": poisson_total["accuracy"],
            "poisson_brier": poisson_total["brier_score"],
        },
    }


def build_boundary_pack(report_dir: Path = REPORT_DIR) -> dict:
    sources = load_source_reports(report_dir)
    evidence = build_evidence_inventory(sources)
    return {
        "task": "P229-A run line evidence boundary pack",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "not_a_new_model_task": True,
        "disclaimers": DISCLAIMERS,
        "evidence_inventory": evidence,
        "supported_claims": SUPPORTED_CLAIMS,
        "unsupported_claims": UNSUPPORTED_CLAIMS,
        "missing_evidence_next_gates": MISSING_EVIDENCE_NEXT_GATES,
        "recommended_next_technical_step": RECOMMENDED_NEXT_TECHNICAL_STEP,
    }


def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def render_markdown(pack: dict) -> str:
    ev = pack["evidence_inventory"]
    rl_base = ev["p226a_run_line_baseline"]
    split = ev["p228a_split_robustness"]
    monthly = ev["p228a_monthly_robustness"]
    cal = ev["p228a_calibration"]
    total_lim = ev["p227a_total_limitation"]
    step = pack["recommended_next_technical_step"]

    md: list[str] = []
    md.append("# P229-A — Run Line Evidence Boundary Pack\n")
    md.append(
        "> **僅本機歷史 / replay 描述性彙整。** 本檔不是新模型任務，只彙整 "
        "P226-A / P227-A / P228-A 既有結果；非未來預測、非下注建議、無 EV/Kelly "
        "宣稱、無 live 市場宣稱、無 production/DB 變更、非已證實 edge。\n"
    )

    md.append("## 範疇聲明")
    for d in pack["disclaimers"]:
        md.append(f"- {d}")
    md.append("")

    md.append("## 1. Evidence Inventory")
    md.append("### 1.1 P226-A Run Line baseline")
    md.append(
        f"- 測試期 `{rl_base['test_period'][0]}`→`{rl_base['test_period'][1]}`"
        f"（{rl_base['test_rows']} 場）"
    )
    md.append(
        f"- coinflip baseline：accuracy={_fnum(rl_base['coinflip_accuracy'])}、"
        f"brier={_fnum(rl_base['coinflip_brier'])}"
    )
    md.append(
        f"- poisson_team_rate_model：accuracy={_fnum(rl_base['poisson_accuracy'])}、"
        f"brier={_fnum(rl_base['poisson_brier'])}、ECE={_fnum(rl_base['poisson_ece'])}\n"
    )

    md.append("### 1.2 P228-A Split Robustness")
    md.append(
        f"- split-grid：{split['split_grid_strict_wins']}/{split['split_grid_total']} "
        f"嚴格勝出、{split['split_grid_not_worse_within_tolerance']}/"
        f"{split['split_grid_total']} 不劣於容忍帶"
    )
    md.append("| train_frac | test_period | poisson_accuracy | poisson_brier | beats_coinflip |")
    md.append("|--:|---|--:|--:|:--:|")
    for s in split["splits"]:
        md.append(
            f"| {s['train_frac']} | {s['test_period'][0]}→{s['test_period'][1]} | "
            f"{_fnum(s['poisson_accuracy'])} | {_fnum(s['poisson_brier'])} | "
            f"{'YES' if s['beats_coinflip'] else 'no'} |"
        )
    md.append("")

    md.append("### 1.3 P228-A Monthly Robustness")
    md.append(
        f"- monthly windows：{monthly['monthly_windows_strict_wins']}/"
        f"{monthly['monthly_windows_evaluated']} 嚴格勝出、"
        f"{monthly['monthly_windows_not_worse_within_tolerance']}/"
        f"{monthly['monthly_windows_evaluated']} 不劣於容忍帶"
        f"（另有 {monthly['monthly_windows_skipped']} 個月因樣本不足被排除評分）"
    )
    md.append(f"- P228-A 穩健性最終判定：`{monthly['robustness_label']}`\n")

    md.append("### 1.4 P228-A Calibration")
    md.append(
        f"- train-fold-only Platt：raw brier={_fnum(cal['raw_brier'])} → "
        f"calibrated brier={_fnum(cal['calibrated_brier'])}"
        f"（改善 Brier：`{cal['calibration_beats_raw_brier']}`）"
    )
    md.append(
        f"- raw ECE={_fnum(cal['raw_ece'])} → calibrated ECE={_fnum(cal['calibrated_ece'])}"
        f"（改善 ECE：`{cal['calibration_beats_raw_ece']}`）\n"
    )

    md.append("### 1.5 P227-A Total Limitation")
    md.append(
        f"- best_by_brier=`{total_lim['best_by_brier']}`；"
        f"beats_coinflip_brier=`{total_lim['beats_coinflip_brier']}`；"
        f"beats_poisson_brier=`{total_lim['beats_poisson_brier']}`"
    )
    md.append(
        f"- coinflip brier={_fnum(total_lim['coinflip_brier'])}；"
        f"poisson accuracy={_fnum(total_lim['poisson_accuracy'])}、"
        f"brier={_fnum(total_lim['poisson_brier'])}\n"
    )

    md.append("## 2. What Is Supported")
    for c in pack["supported_claims"]:
        md.append(f"- {c}")
    md.append("")

    md.append("## 3. What Is Not Supported")
    for c in pack["unsupported_claims"]:
        md.append(f"- {c}")
    md.append("")

    md.append("## 4. Missing Evidence / Next Gates")
    for g in pack["missing_evidence_next_gates"]:
        md.append(f"- {g}")
    md.append("")

    md.append("## 5. Recommended Next Technical Step")
    md.append(f"- 候選：**{step['candidate']}**")
    md.append("- 其他候選（未擇定）：")
    for a in step["alternatives"]:
        md.append(f"  - {a}")
    md.append(f"- 授權狀態：`{step['authorization_status']}`")
    md.append(f"- {step['note']}\n")

    md.append("## 免責聲明")
    md.append("- **HISTORICAL**：全部數字皆為歷史回測結果（引用自 P226-A/P227-A/P228-A 既有報告）。")
    md.append("- **PAPER-ONLY**：無真實下注、無資金部署。")
    md.append("- **NOT LIVE**：無即時市場串接。")
    md.append("- **NOT PRODUCTION**：無 production/DB/registry 變更、無發布。")
    md.append("- **NOT REAL BETTING**：無下注建議、無 EV/Kelly 宣稱。")
    md.append(
        "- **NOT A PROVEN EDGE**：本報告不構成已證實的下注優勢宣稱，僅為描述性、"
        "可重現的歷史統計彙整，供後續研究與決策參考。"
    )
    return "\n".join(md) + "\n"


def write_reports(pack: dict, out_dir: Path = REPORT_DIR) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    json_p = out / "p229a_run_line_evidence_boundary_pack.json"
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    md_p = out / "p229a_run_line_evidence_boundary_pack.md"
    with open(md_p, "w", encoding="utf-8") as f:
        f.write(render_markdown(pack))
    written.append(md_p)

    return written


def main() -> int:
    missing = [p for p in (P226A_JSON, P227A_JSON, P228A_JSON) if not p.exists()]
    if missing:
        print("P229A_BLOCKED_NO_UPSTREAM_REPORTS: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    pack = build_boundary_pack(REPORT_DIR)
    written = write_reports(pack, REPORT_DIR)

    print("=" * 84)
    print("P229-A RUN LINE EVIDENCE BOUNDARY PACK  (local historical synthesis only; not a new model)")
    print("=" * 84)
    ev = pack["evidence_inventory"]
    print(
        f"P226-A run line: coinflip_brier={ev['p226a_run_line_baseline']['coinflip_brier']:.4f} "
        f"poisson_brier={ev['p226a_run_line_baseline']['poisson_brier']:.4f} "
        f"poisson_accuracy={ev['p226a_run_line_baseline']['poisson_accuracy']:.4f}"
    )
    print(f"P228-A robustness label: {ev['p228a_monthly_robustness']['robustness_label']}")
    print(
        f"P227-A total: best_by_brier={ev['p227a_total_limitation']['best_by_brier']} "
        f"beats_coinflip_brier={ev['p227a_total_limitation']['beats_coinflip_brier']}"
    )
    print(
        f"recommended next step (NOT authorized): "
        f"{pack['recommended_next_technical_step']['candidate']}"
    )
    print("-" * 84)
    print(f"wrote {len(written)} report files → {REPORT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
