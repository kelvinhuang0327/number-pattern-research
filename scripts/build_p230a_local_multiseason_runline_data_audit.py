#!/usr/bin/env python3
"""
P230-A CLI — 本機多球季 Run Line 資料可用性盤點（read-only audit，非新模型任務）。

用法（自 repo 根目錄）：
    python3 scripts/build_p230a_local_multiseason_runline_data_audit.py

本檔只讀取 repo 內既有本機檔案（asplayed/schedule/odds/metadata），逐球季盤點
是否具備延伸 Run Line 評估（P226-A/P228-A/P229-A 既有 2025 證據之外）所需欄位：
最終比分、主客隊、比賽日期、run line 讓分、run line 賠率、metadata/來源證明。
純本機、無網路擷取、無 pybaseball、無 DB 寫入、不修改任何資料檔、不新增依賴、
不產生未來預測、不產生下注建議、不宣稱已證實 edge、不改動 P226-A/P227-A/
P228-A/P229-A 既有產出。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "report"

DISCLAIMERS = [
    "LOCAL DATA AVAILABILITY AUDIT ONLY — not a modeling task, not a prediction task, "
    "not a production/live/real-betting task",
    "read-only inventory of already-present local files under data/; NO remote fetch, "
    "NO pybaseball, NO DB writes, NO data file modification, NO new dependency",
    "NO future prediction; NO betting recommendation; NO EV/Kelly claim; NOT a proven edge",
    "NO live-market claim; NOT production; NOT real betting; NO model implementation",
    "P226-A / P227-A / P228-A / P229-A source artifacts are read-only reference inputs "
    "and are not modified by this audit",
    "recommended next technical step is NOT authorized by this audit; a separate "
    "explicit Owner authorization is required before any further work begins",
]

CLASSIFICATIONS = (
    "FULL_RUNLINE_EVAL_READY",
    "LABEL_ONLY_NO_ODDS",
    "SCORES_ONLY",
    "MISSING_OR_UNUSABLE",
    "AMBIGUOUS_REQUIRES_REVIEW",
)

RECOMMENDATION_CHOICES = (
    "multi_season_run_line_backtest",
    "data_normalization",
    "true_pit_odds_provenance_audit",
    "stop_data_gap",
)


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _count_csv_data_rows(path: Path) -> Optional[int]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _count_lines(path: Path) -> Optional[int]:
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def inspect_file(path: Path, counter: Optional[str] = None) -> dict:
    """單一檔案存在性 + row_count 盤點（read-only；不解析內容除計數用途）。"""
    exists = path.is_file()
    row_count: Optional[int] = None
    if exists and counter == "csv_data_rows":
        row_count = _count_csv_data_rows(path)
    elif exists and counter == "lines":
        row_count = _count_lines(path)
    return {"path": _rel(path), "exists": exists, "row_count": row_count}


def _has_column(csv_path: Path, column: str) -> bool:
    if not csv_path.is_file():
        return False
    with open(csv_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    return column in header


def classify_season(fields: dict) -> str:
    """依既定規則（非依結果調整）將單一球季分類為五種狀態之一。"""
    has_scores = fields["final_scores"]
    has_teams = fields["home_away_teams"]
    has_date = fields["game_date"]
    has_spread = fields["run_line_spread"]
    has_prices = fields["run_line_prices"]

    if has_scores and has_teams and has_date and has_spread and has_prices:
        return "FULL_RUNLINE_EVAL_READY"
    if has_scores and has_teams and has_date and not has_spread and not has_prices:
        return "LABEL_ONLY_NO_ODDS"
    if has_scores and not (has_teams and has_date) and not has_spread and not has_prices:
        return "SCORES_ONLY"
    if has_spread != has_prices:
        # run line 讓分與賠率兩者只出現其中一項 → 資料不完整，需人工複核
        return "AMBIGUOUS_REQUIRES_REVIEW"
    if not has_scores:
        return "MISSING_OR_UNUSABLE"
    return "AMBIGUOUS_REQUIRES_REVIEW"


def audit_season_2024() -> dict:
    base = DATA_DIR / "mlb_2025"
    asplayed = inspect_file(base / "mlb-2024-asplayed.csv", "csv_data_rows")
    metadata = inspect_file(base / "mlb-2024-asplayed.csv.metadata.json")
    gl_source = inspect_file(base / "gl2024.txt", "lines")
    gl_zip = inspect_file(base / "gl2024.zip")
    missing_odds = inspect_file(base / "mlb_odds_2024_real.csv")

    fields = {
        "final_scores": asplayed["exists"] and asplayed["row_count"] not in (None, 0),
        "home_away_teams": asplayed["exists"],
        "game_date": asplayed["exists"],
        "run_line_spread": missing_odds["exists"],
        "run_line_prices": missing_odds["exists"],
        "metadata_provenance": metadata["exists"],
    }
    classification = classify_season(fields)

    blockers = [
        "missing_run_line_spread — no local run line odds/spread file exists for 2024 "
        "(data/mlb_2025/mlb_odds_2024_real.csv does not exist)",
        "missing_run_line_prices — same as above; no RL price fields locally available",
        "no_local_odds_file_2024 — P70 (The Odds API historical pull) ran DRY_RUN only "
        "with 0 rows written and no API key configured "
        "(data/mlb_2025/derived/p70_path_a_the_odds_api_historical_pull_summary.json); "
        "P67 free-source search found no downloadable 2024 MLB odds source "
        "(report/p67_2024_data_gap_free_source_search_20260526.md, classification "
        "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW); even if P70 had run, its scope "
        "was moneyline (h2h) only, not run line",
    ]

    return {
        "season": "2024",
        "classification": classification,
        "fields_present": fields,
        "files": [asplayed, metadata, gl_source, gl_zip, missing_odds],
        "blockers": blockers,
        "notes": "final scores + home/away + date are Retrosheet-verified "
        "(sha256-checked against gl2024.txt per metadata); this is a warm-up/label-only "
        "dataset with no locally available run line odds of any kind.",
    }


def audit_season_2025() -> dict:
    base = DATA_DIR / "mlb_2025"
    asplayed = inspect_file(base / "mlb-2025-asplayed.csv", "csv_data_rows")
    asplayed_meta = inspect_file(base / "mlb-2025-asplayed.csv.metadata.json")
    odds = inspect_file(base / "mlb_odds_2025_real.csv", "csv_data_rows")
    odds_meta = inspect_file(base / "mlb_odds_2025_real.csv.metadata.json")
    gl_source = inspect_file(base / "gl2025.txt", "lines")

    has_spread = _has_column(base / "mlb_odds_2025_real.csv", "Home RL Spread")
    has_prices = _has_column(base / "mlb_odds_2025_real.csv", "RL Away") and _has_column(
        base / "mlb_odds_2025_real.csv", "RL Home"
    )

    fields = {
        "final_scores": asplayed["exists"] and asplayed["row_count"] not in (None, 0),
        "home_away_teams": asplayed["exists"],
        "game_date": asplayed["exists"],
        "run_line_spread": has_spread,
        "run_line_prices": has_prices,
        "metadata_provenance": asplayed_meta["exists"] and odds_meta["exists"],
    }
    classification = classify_season(fields)

    blockers = [
        "unverified_odds_provenance — mlb_odds_2025_real.csv.metadata.json declares "
        "source_chain_verified=false and the CSV rows carry is_verified_real=False "
        "(source_type=user_supplied_xlsx from mlb-odds.xlsx); already documented as a "
        "post-game unverified snapshot in P226-A/P229-A, NOT a point-in-time pregame "
        "feed — this is the same known limitation carried into this season, not new.",
    ]

    return {
        "season": "2025",
        "classification": classification,
        "fields_present": fields,
        "files": [asplayed, asplayed_meta, odds, odds_meta, gl_source],
        "blockers": blockers,
        "notes": "this is the existing P226-A/P228-A/P229-A evidence base itself — "
        "already fully utilized, not additional/unused local coverage.",
    }


def audit_season_2026() -> dict:
    base = DATA_DIR / "mlb_2026"
    schedule = inspect_file(base / "schedule" / "mlb_2026_schedule.jsonl", "lines")
    predictions = inspect_file(base / "predictions" / "mlb_2026_prediction_rows.jsonl", "lines")

    scored_rows = 0
    pred_path = base / "predictions" / "mlb_2026_prediction_rows.jsonl"
    if pred_path.is_file():
        with open(pred_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("result_home_score") is not None:
                    scored_rows += 1

    fields = {
        "final_scores": scored_rows > 0,
        "home_away_teams": schedule["exists"] or predictions["exists"],
        "game_date": schedule["exists"] or predictions["exists"],
        "run_line_spread": False,
        "run_line_prices": False,
        "metadata_provenance": False,
    }
    classification = classify_season(fields)

    blockers = [
        "missing_final_scores — 0 of "
        f"{predictions['row_count'] or 0} local prediction rows have "
        "result_home_score populated; season 2026 is in progress as of this audit "
        "(no local asplayed/final-score file exists for 2026)",
        "missing_run_line_spread — schedule/prediction jsonl schemas carry no run "
        "line spread field",
        "missing_run_line_prices — schedule/prediction jsonl schemas carry no run "
        "line price field (prediction rows explicitly set odds_used=false)",
        "no_metadata_provenance_file — no *.metadata.json provenance file exists for "
        "the 2026 schedule/prediction jsonl inputs",
    ]

    return {
        "season": "2026",
        "classification": classification,
        "fields_present": fields,
        "files": [schedule, predictions],
        "blockers": blockers,
        "notes": f"schedule has {schedule['row_count']} scheduled games; predictions "
        f"jsonl has {predictions['row_count']} rows but {scored_rows} with an observed "
        "final score — current in-season data, not usable as a completed evaluation "
        "season.",
    }


EXCLUDED_LOCAL_DATA = [
    {
        "path": "data/tsl_odds_history.jsonl",
        "reason": "non_mlb_league — sampled team names are NPB/KBO clubs "
        "(e.g. 羅德海洋/Chiba Lotte Marines, 西武獅/Seibu Lions, 起亞老虎/KIA Tigers, "
        "SSG登陸者/SSG Landers), not MLB; out of scope for an MLB run line audit",
    },
    {
        "path": "data/tsl_odds_snapshot.json",
        "reason": "non_mlb_league — sampled game entries are NPB clubs "
        "(e.g. 樂天金鷲/Rakuten Eagles, 西武獅/Seibu Lions); also a single-day "
        "snapshot (9 games), not season coverage",
    },
    {
        "path": "data/mlb_context/odds_timeline.jsonl",
        "reason": "derived_duplicate — moneyline-only re-projection of the same "
        "2025 mlb_odds_2025_real.csv rows (source field cites "
        "mlb_odds_2025_real.csv); no run line field; not a new season",
    },
    {
        "path": "data/mlb_context_sources/odds_timeline_canonical.jsonl",
        "reason": "derived_duplicate — same underlying 2025 moneyline rows as "
        "odds_timeline.jsonl; carries validation_flags including "
        "missing_closing/missing_decision/missing_latest_pregame; no run line field; "
        "not a new season",
    },
]

RECOMMENDED_NEXT_TECHNICAL_STEP = {
    "chosen": "stop_data_gap",
    "authorization_status": "NOT_AUTHORIZED_YET",
    "rationale": "Only 1 of 3 locally discoverable candidate seasons (2025) carries "
    "both final scores AND run line spread/prices; 2024 has verified final scores but "
    "no locally available run line odds of any kind (two prior dedicated tasks, "
    "P67 free-source search and P70 paid-API dry-run, already confirmed this is a "
    "structural gap, not a missed lookup); 2026 has zero locally observed final "
    "scores (season in progress). Multi-season Run Line backtest expansion is "
    "therefore not locally supportable today — this is a genuine local data gap, "
    "not a schema or normalization problem.",
    "note": "This audit recommends but does not authorize the next step; a separate "
    "explicit Owner authorization is required before any further work begins. If "
    "further work is desired despite this gap, the most locally-actionable "
    "alternative (not chosen here) would be a true-PIT odds provenance audit of the "
    "existing 2025 season odds source, since that does not require new season data.",
}


def build_audit() -> dict:
    seasons = [audit_season_2024(), audit_season_2025(), audit_season_2026()]
    return {
        "task": "P230-A local multi-season run line data availability audit",
        "scope": "LOCAL_DATA_AVAILABILITY_AUDIT_ONLY",
        "not_a_modeling_task": True,
        "not_a_prediction_task": True,
        "disclaimers": DISCLAIMERS,
        "seasons": seasons,
        "excluded_local_data": EXCLUDED_LOCAL_DATA,
        "recommended_next_technical_step": RECOMMENDED_NEXT_TECHNICAL_STEP,
    }


def _yesno(v: bool) -> str:
    return "YES" if v else "no"


def render_markdown(audit: dict) -> str:
    md: list[str] = []
    md.append("# P230-A — Local Multi-Season Run Line Data Availability Audit\n")
    md.append(
        "> **本機資料可用性盤點（read-only）。** 非模型任務、非預測任務、非 "
        "production/live/real-betting 任務；純盤點本機既有檔案是否足以將 Run Line "
        "評估延伸至 2025（P226-A/P228-A/P229-A）既有證據之外。\n"
    )

    md.append("## 範疇聲明")
    for d in audit["disclaimers"]:
        md.append(f"- {d}")
    md.append("")

    md.append("## 1. Season Inventory & Classification")
    md.append("| season | classification | final_scores | teams | date | RL spread | RL prices | metadata |")
    md.append("|---|---|:--:|:--:|:--:|:--:|:--:|:--:|")
    for s in audit["seasons"]:
        f = s["fields_present"]
        md.append(
            f"| {s['season']} | `{s['classification']}` | {_yesno(f['final_scores'])} | "
            f"{_yesno(f['home_away_teams'])} | {_yesno(f['game_date'])} | "
            f"{_yesno(f['run_line_spread'])} | {_yesno(f['run_line_prices'])} | "
            f"{_yesno(f['metadata_provenance'])} |"
        )
    md.append("")

    for s in audit["seasons"]:
        md.append(f"### Season {s['season']}")
        md.append(f"- **Classification**: `{s['classification']}`")
        md.append("- Files:")
        for fobj in s["files"]:
            rc = fobj["row_count"]
            rc_str = "—" if rc is None else str(rc)
            md.append(f"  - `{fobj['path']}` — exists={_yesno(fobj['exists'])}, row_count={rc_str}")
        md.append("- Blockers:")
        for b in s["blockers"]:
            md.append(f"  - {b}")
        md.append(f"- Notes: {s['notes']}\n")

    md.append("## 2. Excluded / Out-of-Scope Local Data")
    md.append(
        "已於 data/ 下找到但不計入本次球季盤點（原因：非 MLB 聯盟或為既有 2025 "
        "資料的重複衍生檢視）："
    )
    for e in audit["excluded_local_data"]:
        md.append(f"- `{e['path']}` — {e['reason']}")
    md.append("")

    md.append("## 3. Recommended Next Technical Step")
    step = audit["recommended_next_technical_step"]
    md.append(f"- **候選（chosen）**：`{step['chosen']}`")
    md.append(f"- 授權狀態：`{step['authorization_status']}`")
    md.append(f"- Rationale: {step['rationale']}")
    md.append(f"- {step['note']}\n")

    md.append("## 免責聲明")
    md.append("- **NOT A MODELING TASK**：本檔不訓練、不重跑、不修改任何模型。")
    md.append("- **NOT A PREDICTION TASK**：無未來預測、無 upcoming game 宣稱。")
    md.append("- **NOT PRODUCTION / LIVE / REAL BETTING**：無 production/DB 變更、無即時市場串接、無真實下注。")
    md.append("- **NOT A PROVEN EDGE**：本報告不構成已證實的下注優勢宣稱，僅為本機資料可用性盤點。")
    md.append(
        "- **P226-A/P227-A/P228-A/P229-A UNCHANGED**：本任務未讀寫任何上述任務的既有產出檔案。"
    )
    return "\n".join(md) + "\n"


def write_reports(audit: dict, out_dir: Path = REPORT_DIR) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    json_p = out / "p230a_local_multiseason_runline_data_audit.json"
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    md_p = out / "p230a_local_multiseason_runline_data_audit.md"
    with open(md_p, "w", encoding="utf-8") as f:
        f.write(render_markdown(audit))
    written.append(md_p)

    return written


def main() -> int:
    audit = build_audit()
    written = write_reports(audit, REPORT_DIR)

    print("=" * 84)
    print("P230-A LOCAL MULTI-SEASON RUN LINE DATA AVAILABILITY AUDIT  (read-only; not a model)")
    print("=" * 84)
    for s in audit["seasons"]:
        print(f"season={s['season']:<6} classification={s['classification']}")
    step = audit["recommended_next_technical_step"]
    print(f"recommended next step (NOT authorized): {step['chosen']}")
    print("-" * 84)
    print(f"wrote {len(written)} report files -> {REPORT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
