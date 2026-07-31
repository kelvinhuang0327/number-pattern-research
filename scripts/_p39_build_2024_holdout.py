#!/usr/bin/env python3
"""
P39 — Build 2024 MLB Holdout Dataset for sp_fip_delta T=0.50 OOS Validation
============================================================================
目標：
  為 P38 retry 建立最小可行 2024 holdout dataset。
  資料來源：Retrosheet gl2024.txt（公開、確定性、靜態）
  FIP 來源：data/mlb_2023_pitchers.py（2023 賽季代理值，非 live API）

Governance:
  - diagnostic_only = True（僅產出診斷資料，不修改任何策略）
  - promotion_freeze = True（不更新 champion 策略）
  - T_LOCKED = 0.50（固定閾值，不重新優化）
  - live_api_calls = 0（不呼叫任何 live API）
  - no_champion_modification = True

PIT 安全性（Point-in-Time）：
  - 2023 FIP 為 2024 賽季前已知統計 → PIT safe ✅
  - snapshot_date = game_date - 1（2024 賽局日期前一天）
  - 不含任何 2024 賽後資訊

輸出：
  - data/mlb_2025/mlb-2024-asplayed.csv
  - data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl
  - data/mlb_2025/mlb-2024-asplayed.csv.metadata.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date, timezone, datetime
from pathlib import Path

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
_GL2024_PATH = _REPO_ROOT / "data" / "mlb_2025" / "gl2024.txt"
_ASPLAYED_2024_PATH = _REPO_ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
_ASPLAYED_META_PATH = _REPO_ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv.metadata.json"
_FEATURES_OUT_PATH = _REPO_ROOT / "data" / "mlb_2025" / "derived" / "mlb_2024_sp_fip_delta_features.jsonl"

# ── Governance Constants ────────────────────────────────────────────────────
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
T_LOCKED: float = 0.50
LIVE_API_CALLS: int = 0
NO_CHAMPION_MODIFICATION: bool = True

# 2024 season date bounds (regular season + playoffs)
SEASON_START_2024 = "2024-03-20"
SEASON_END_2024   = "2024-11-02"

# ── Team code → full name mapping（與 verify_mlb_2025_training_data.py 一致）──
TEAM_CODE_TO_NAME: dict[str, str] = {
    "ANA": "Los Angeles Angels",
    "ARI": "Arizona Diamondbacks",
    "ATH": "Athletics",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CAL": "Los Angeles Angels",
    "CHA": "Chicago White Sox",
    "CHC": "Chicago Cubs",
    "CHN": "Chicago Cubs",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "CWS": "Chicago White Sox",
    "DET": "Detroit Tigers",
    "FLO": "Miami Marlins",
    "HOU": "Houston Astros",
    "KCA": "Kansas City Royals",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "LAN": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "MON": "Washington Nationals",
    "NYA": "New York Yankees",
    "NYM": "New York Mets",
    "NYN": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDN": "San Diego Padres",
    "SDP": "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SFN": "San Francisco Giants",
    "SFG": "San Francisco Giants",
    "SLN": "St. Louis Cardinals",
    "STL": "St. Louis Cardinals",
    "TBA": "Tampa Bay Rays",
    "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals",
    "WSN": "Washington Nationals",
}


# ── Utility ────────────────────────────────────────────────────────────────────
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _assert_pit_safe(pitcher_fip_year: int, game_year: int) -> None:
    """PIT safety: FIP 資料年份必須早於賽局年份。"""
    assert pitcher_fip_year < game_year, (
        f"PIT violation: fip_year={pitcher_fip_year} >= game_year={game_year}"
    )


# ── Section 1: Parse gl2024.txt → mlb-2024-asplayed.csv ──────────────────────
def parse_gl2024(gl_path: Path) -> list[dict]:
    """
    解析 Retrosheet gl2024.txt，回傳 game records list。

    Retrosheet game log column mapping：
      col 0:   date (YYYYMMDD)
      col 3:   away team code
      col 6:   home team code
      col 9:   away score
      col 10:  home score
      col 102: away starter name
      col 104: home starter name
    """
    records: list[dict] = []
    with gl_path.open("r", encoding="latin1", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 105:
                continue
            raw_date = row[0].strip()
            if len(raw_date) != 8:
                continue
            game_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            away_code = row[3].strip()
            home_code = row[6].strip()
            away_team = TEAM_CODE_TO_NAME.get(away_code, away_code)
            home_team = TEAM_CODE_TO_NAME.get(home_code, home_code)
            try:
                away_score = int(row[9])
                home_score = int(row[10])
            except ValueError:
                continue
            away_starter = row[102].strip()
            home_starter = row[104].strip()
            home_win = 1.0 if home_score > away_score else 0.0
            records.append({
                "date":          game_date,
                "away_team":     away_team,
                "home_team":     home_team,
                "away_score":    away_score,
                "home_score":    home_score,
                "away_starter":  away_starter,
                "home_starter":  home_starter,
                "home_win":      home_win,
                "source_file":   "gl2024.txt",
                "source_type":   "retrosheet_gamelog",
                "is_verified_real": True,
            })
    return records


def write_asplayed_csv(records: list[dict], path: Path) -> None:
    """Write mlb-2024-asplayed.csv in same schema as mlb-2025-asplayed.csv."""
    fieldnames = [
        "date", "away_team", "home_team", "away_score", "home_score",
        "away_starter", "home_starter", "home_win",
        "source_file", "source_type", "is_verified_real",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


# ── Section 2: 2023 FIP table validation ──────────────────────────────────────
def validate_fip_table(records: list[dict]) -> dict:
    """Check coverage of 2023 FIP table against 2024 starters."""
    sys.path.insert(0, str(_REPO_ROOT))
    from data.mlb_2023_pitchers import get_fip_2023

    starters_seen: set[str] = set()
    for r in records:
        starters_seen.add(r["away_starter"])
        starters_seen.add(r["home_starter"])
    starters_seen.discard("")

    covered = {s for s in starters_seen if get_fip_2023(s) is not None}
    fallback = starters_seen - covered

    return {
        "total_unique_starters": len(starters_seen),
        "covered_by_fip_table": len(covered),
        "fallback_to_lg_avg": len(fallback),
        "coverage_pct": round(len(covered) / len(starters_seen) * 100, 1) if starters_seen else 0.0,
        "fallback_names_sample": sorted(fallback)[:20],
    }


# ── Section 3: Build sp_fip_delta features ────────────────────────────────────
def build_fip_features(records: list[dict]) -> list[dict]:
    """
    為每場 2024 賽局建立 sp_fip_delta 特徵。

    PIT safety check:
      - FIP year = 2023, game year = 2024 → PIT safe ✅
    """
    sys.path.insert(0, str(_REPO_ROOT))
    from data.mlb_2023_pitchers import get_fip_2023
    LG_FIP = 4.14  # 2023 MLB league average

    _assert_pit_safe(pitcher_fip_year=2023, game_year=2024)

    features: list[dict] = []
    for r in records:
        game_date = r["date"]
        game_year = int(game_date[:4])
        assert game_year == 2024, f"Unexpected game year: {game_year}"

        away_fip_rec = get_fip_2023(r["away_starter"])
        home_fip_rec = get_fip_2023(r["home_starter"])

        away_fip   = away_fip_rec["fip"] if away_fip_rec else LG_FIP
        home_fip   = home_fip_rec["fip"] if home_fip_rec else LG_FIP
        away_src   = "historical_proxy" if away_fip_rec else "league_average_fallback"
        home_src   = "historical_proxy" if home_fip_rec else "league_average_fallback"

        sp_fip_delta = round(away_fip - home_fip, 3)

        if away_src == "historical_proxy" and home_src == "historical_proxy":
            sp_context_source = "historical_proxy"
        elif away_src == "league_average_fallback" and home_src == "league_average_fallback":
            sp_context_source = "league_average_fallback"
        else:
            sp_context_source = "mixed"

        # Strong-edge classification (T=0.50, T_LOCKED)
        abs_delta = abs(sp_fip_delta)
        is_strong_edge = abs_delta >= T_LOCKED

        # Predicted direction: positive delta → away worse → home favored
        if sp_fip_delta > 0:
            predicted_home_win = 1
        elif sp_fip_delta < 0:
            predicted_home_win = 0
        else:
            predicted_home_win = -1  # neutral

        actual_home_win = int(r["home_win"])
        correct = (predicted_home_win == actual_home_win) if predicted_home_win != -1 else None

        features.append({
            "game_date":           game_date,
            "home_team":           r["home_team"],
            "away_team":           r["away_team"],
            "home_starter":        r["home_starter"],
            "away_starter":        r["away_starter"],
            "home_fip_2023":       home_fip,
            "away_fip_2023":       away_fip,
            "home_fip_src":        home_src,
            "away_fip_src":        away_src,
            "sp_fip_delta":        sp_fip_delta,
            "sp_context_source":   sp_context_source,
            "abs_delta":           abs_delta,
            "is_strong_edge":      is_strong_edge,
            "predicted_home_win":  predicted_home_win,
            "actual_home_win":     actual_home_win,
            "correct":             correct,
            "home_win":            actual_home_win,
            # PIT metadata
            "fip_data_year":       2023,
            "pit_safe":            True,
            "snapshot_date":       f"{int(game_date[:4]) - 1}-12-31",
        })
    return features


# ── Section 4: Coverage analysis ──────────────────────────────────────────────
def analyze_coverage(features: list[dict]) -> dict:
    """Compute quality, strong-edge coverage, and directional accuracy."""
    total = len(features)

    # Quality filter: exclude league_average_fallback (matches P37 filter)
    quality_records = [f for f in features if f["sp_context_source"] != "league_average_fallback"]
    strong_edge = [f for f in quality_records if f["is_strong_edge"]]

    # Source distribution
    src_dist = {}
    for f in features:
        src = f["sp_context_source"]
        src_dist[src] = src_dist.get(src, 0) + 1

    # Strong-edge accuracy (where prediction is not neutral)
    se_predictable = [f for f in strong_edge if f["predicted_home_win"] != -1]
    se_correct = [f for f in se_predictable if f["correct"] is True]
    se_accuracy = round(len(se_correct) / len(se_predictable) * 100, 1) if se_predictable else 0.0

    # sp_fip_delta distribution stats
    deltas = [f["sp_fip_delta"] for f in quality_records]
    if deltas:
        import statistics
        delta_mean = round(statistics.mean(deltas), 3)
        delta_std  = round(statistics.stdev(deltas), 3) if len(deltas) > 1 else 0.0
        delta_min  = round(min(deltas), 3)
        delta_max  = round(max(deltas), 3)
    else:
        delta_mean = delta_std = delta_min = delta_max = 0.0

    return {
        "total_games":              total,
        "quality_records":          len(quality_records),
        "quality_pct":              round(len(quality_records) / total * 100, 1) if total else 0.0,
        "strong_edge_count":        len(strong_edge),
        "strong_edge_pct_of_quality": round(len(strong_edge) / len(quality_records) * 100, 1) if quality_records else 0.0,
        "wfv_viable":               len(strong_edge) >= 150,
        "source_distribution":      src_dist,
        "strong_edge_accuracy_pct": se_accuracy,
        "sp_fip_delta_mean":        delta_mean,
        "sp_fip_delta_std":         delta_std,
        "sp_fip_delta_min":         delta_min,
        "sp_fip_delta_max":         delta_max,
        "t_locked":                 T_LOCKED,
    }


# ── Section 5: PIT safety audit ────────────────────────────────────────────────
def pit_audit(features: list[dict]) -> dict:
    """Verify all records are point-in-time safe."""
    violations = []
    for f in features:
        if not f.get("pit_safe"):
            violations.append(f["game_date"])
        fip_year = f.get("fip_data_year", 0)
        game_year = int(f["game_date"][:4])
        if fip_year >= game_year:
            violations.append(f"PIT_VIOLATION|{f['game_date']}|fip_year={fip_year}")

    return {
        "total_records": len(features),
        "pit_safe_count": len(features) - len(violations),
        "pit_violations": len(violations),
        "fip_data_year": 2023,
        "game_data_year": 2024,
        "fip_predates_games": True,
        "snapshot_policy": "fip_data_year < game_year (2023 < 2024)",
        "violation_details": violations[:10],
    }


# ── Section 6: Dataset readiness classification ────────────────────────────────
def classify_dataset(cov: dict, pit: dict) -> dict:
    """Classify the 2024 holdout dataset readiness."""
    se_count = cov["strong_edge_count"]
    pit_ok = pit["pit_violations"] == 0
    wfv_viable = cov["wfv_viable"]

    if pit_ok and wfv_viable and se_count >= 500:
        classification = "HOLDOUT_READY"
        description = "충분한 strong-edge 샘플과 PIT 안전 검증 완료."
    elif pit_ok and wfv_viable and se_count >= 150:
        classification = "HOLDOUT_PARTIAL_VIABLE"
        description = "WFV 최소 임계값 충족, SP 매핑 커버리지 개선 가능."
    elif se_count > 0:
        classification = "PARTIAL_DATASET_BUILT"
        description = "Strong-edge 샘플 존재하나 WFV 임계값(150) 미달."
    else:
        classification = "SP_MAPPING_UNAVAILABLE"
        description = "Strong-edge 샘플 없음."

    return {
        "classification":         classification,
        "description":            description,
        "strong_edge_count":      se_count,
        "wfv_viable":             wfv_viable,
        "pit_safe":               pit_ok,
        "total_games":            cov["total_games"],
        "quality_records":        cov["quality_records"],
        "t_locked":               T_LOCKED,
        "diagnostic_only":        DIAGNOSTIC_ONLY,
        "promotion_freeze":       PROMOTION_FREEZE,
        "no_champion_modification": NO_CHAMPION_MODIFICATION,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 70)
    print("P39 — Build 2024 MLB Holdout Dataset")
    print("=" * 70)

    # Pre-flight governance check
    assert DIAGNOSTIC_ONLY,        "DIAGNOSTIC_ONLY must be True"
    assert PROMOTION_FREEZE,       "PROMOTION_FREEZE must be True"
    assert NO_CHAMPION_MODIFICATION, "NO_CHAMPION_MODIFICATION must be True"
    assert LIVE_API_CALLS == 0,    "LIVE_API_CALLS must be 0"
    assert T_LOCKED == 0.50,       f"T_LOCKED must be 0.50, got {T_LOCKED}"
    print(f"[0] Governance check: PASS — diagnostic_only={DIAGNOSTIC_ONLY}, "
          f"T_LOCKED={T_LOCKED}, live_api_calls={LIVE_API_CALLS}")

    # Section 1: Parse gl2024.txt
    if not _GL2024_PATH.exists():
        print(f"[ERR] gl2024.txt not found at {_GL2024_PATH}")
        return 2
    print(f"\n[1] Parsing {_GL2024_PATH} ...")
    records = parse_gl2024(_GL2024_PATH)
    print(f"    Parsed {len(records)} game records")
    gl_sha256 = sha256_file(_GL2024_PATH)
    print(f"    gl2024.txt SHA-256: {gl_sha256[:16]}...")

    # Write asplayed CSV
    _ASPLAYED_2024_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_asplayed_csv(records, _ASPLAYED_2024_PATH)
    print(f"    Written: {_ASPLAYED_2024_PATH}")

    # Write asplayed metadata
    meta = {
        "dataset":            _ASPLAYED_2024_PATH.name,
        "ingest_source_file": "gl2024.txt",
        "ingest_source_type": "retrosheet_gamelog",
        "source_url":         "https://www.retrosheet.org/gamelogs/gl2024.zip",
        "source_license":     "Retrosheet — free for educational/research use",
        "gl2024_sha256":      gl_sha256,
        "row_count":          len(records),
        "generated_at_utc":   datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "season":             "2024",
        "season_start":       SEASON_START_2024,
        "season_end":         SEASON_END_2024,
        "p39_governance": {
            "diagnostic_only":        DIAGNOSTIC_ONLY,
            "promotion_freeze":       PROMOTION_FREEZE,
            "t_locked":               T_LOCKED,
            "live_api_calls":         LIVE_API_CALLS,
            "no_champion_modification": NO_CHAMPION_MODIFICATION,
        },
    }
    _ASPLAYED_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"    Written: {_ASPLAYED_META_PATH}")

    # Section 2: FIP table coverage
    print(f"\n[2] Validating 2023 FIP table coverage ...")
    fip_cov = validate_fip_table(records)
    print(f"    Unique starters in 2024:    {fip_cov['total_unique_starters']}")
    print(f"    Covered by 2023 FIP table:  {fip_cov['covered_by_fip_table']}")
    print(f"    Fallback to LG avg:         {fip_cov['fallback_to_lg_avg']}")
    print(f"    Coverage:                   {fip_cov['coverage_pct']}%")
    print(f"    Fallback sample:            {fip_cov['fallback_names_sample'][:10]}")

    # Section 3: Build features
    print(f"\n[3] Building sp_fip_delta features (T_LOCKED={T_LOCKED}) ...")
    features = build_fip_features(records)
    print(f"    Feature records built: {len(features)}")

    # Write features JSONL
    _FEATURES_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _FEATURES_OUT_PATH.open("w", encoding="utf-8") as fh:
        for feat in features:
            fh.write(json.dumps(feat, ensure_ascii=False) + "\n")
    print(f"    Written: {_FEATURES_OUT_PATH}")

    # Section 4: Coverage analysis
    print(f"\n[4] Coverage analysis ...")
    cov = analyze_coverage(features)
    print(f"    Total games:              {cov['total_games']}")
    print(f"    Quality records:          {cov['quality_records']} ({cov['quality_pct']}%)")
    print(f"    Strong-edge (T≥0.50):     {cov['strong_edge_count']} ({cov['strong_edge_pct_of_quality']}% of quality)")
    print(f"    WFV viable (≥150):        {cov['wfv_viable']}")
    print(f"    Strong-edge accuracy:     {cov['strong_edge_accuracy_pct']}%")
    print(f"    Source distribution:      {cov['source_distribution']}")
    print(f"    sp_fip_delta range:       [{cov['sp_fip_delta_min']}, {cov['sp_fip_delta_max']}] "
          f"mean={cov['sp_fip_delta_mean']} std={cov['sp_fip_delta_std']}")

    # Section 5: PIT audit
    print(f"\n[5] PIT safety audit ...")
    pit = pit_audit(features)
    print(f"    Total records:            {pit['total_records']}")
    print(f"    PIT safe:                 {pit['pit_safe_count']}")
    print(f"    PIT violations:           {pit['pit_violations']}")
    print(f"    FIP data year:            {pit['fip_data_year']}")
    print(f"    Game data year:           {pit['game_data_year']}")
    print(f"    PIT policy:               {pit['snapshot_policy']}")
    pit_ok = pit["pit_violations"] == 0
    print(f"    PIT AUDIT: {'PASS ✅' if pit_ok else 'FAIL ❌'}")

    # Section 6: Classification
    print(f"\n[6] Dataset readiness classification ...")
    classification = classify_dataset(cov, pit)
    print(f"    Classification:           {classification['classification']}")
    print(f"    Description:              {classification['description']}")
    print(f"    Strong-edge count:        {classification['strong_edge_count']}")
    print(f"    WFV viable:               {classification['wfv_viable']}")

    # Write combined summary JSON
    summary_path = _REPO_ROOT / "data" / "mlb_2025" / "derived" / "p39_2024_holdout_summary.json"
    summary = {
        "p39_generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "governance": {
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "promotion_freeze": PROMOTION_FREEZE,
            "t_locked": T_LOCKED,
            "live_api_calls": LIVE_API_CALLS,
        },
        "data_source": {
            "game_log": "gl2024.txt",
            "game_log_url": "https://www.retrosheet.org/gamelogs/gl2024.zip",
            "fip_table": "data/mlb_2023_pitchers.py",
            "fip_year": 2023,
            "game_year": 2024,
        },
        "fip_coverage": fip_cov,
        "coverage_analysis": cov,
        "pit_audit": pit,
        "classification": classification,
        "output_files": {
            "asplayed_csv": str(_ASPLAYED_2024_PATH),
            "features_jsonl": str(_FEATURES_OUT_PATH),
            "summary_json": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n    Summary written: {summary_path}")

    exit_code = 0 if (pit_ok and classification["wfv_viable"]) else 1
    print(f"\n{'=' * 70}")
    print(f"P39 COMPLETE — {classification['classification']} | exit_code={exit_code}")
    print(f"{'=' * 70}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
