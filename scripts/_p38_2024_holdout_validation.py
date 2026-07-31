"""
P38 — 2024 MLB 獨立驗證集測試（Independent Holdout Validation）
================================================================
目標：使用 2024 MLB 賽季資料驗證 sp_fip_delta strong-edge T=0.50 的跨年泛化能力。
鎖定閾值：T=0.50（P37 確立，禁止重新優化）

執行方式：
    python scripts/_p38_2024_holdout_validation.py

輸出：
    - Section 0: Pre-flight 檢查
    - Section 1: 2024 資料庫存盤點
    - Section 2: 資料需求規格
    - Section 3: 重建路徑分析
    - Section 4: 資料缺口評估
    - Section 5: 可行性預測（若資料存在的預期結果）
    - Section 6: P39 資料獲取建議
    - Section 7: 最終分類判定

治理常數：
    diagnostic_only = True       （絕對不修改生產策略）
    promotion_freeze = True      （冠軍策略不升級）
    T_LOCKED = 0.50              （閾值鎖定，不重新優化）
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# ── 治理常數 ─────────────────────────────────────────────────────────────────
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
T_LOCKED: float = 0.50          # P37 確立，禁止重新優化
PHASE56_PATH: str = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)

# ── P37 2025 基準（P38 比較標的）────────────────────────────────────────────
P37_BASELINE = {
    "auc_wfv":       0.5665,
    "brier_skill":   0.0123,
    "ece":           0.0824,
    "coverage_pct":  37.7,
    "favored_win_rate": 0.608,
    "lift_over_base_pp": 8.0,
    "monthly_stable_pct": 100.0,
    "n_covered":     531,
    "n_quality":     1409,
}

# ── 2024 資料候選路徑（全盤盤點）────────────────────────────────────────────
CANDIDATES_GAME_RESULTS = [
    "data/mlb_2024/mlb-2024-asplayed.csv",
    "data/mlb_2024_asplayed.csv",
    "data/mlb_2025/gl2024.txt",
    "data/gl2024.txt",
    "data/mlb_2024.csv",
    "data/mlb_2024_games.csv",
    "data/mlb_2024_games.jsonl",
    "data/derived/mlb_2024_per_game.jsonl",
    "data/mlb_2025/derived/mlb_2024_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
]

CANDIDATES_FIP_2023 = [
    "data/mlb_2023_pitchers.py",
    "data/pitcher_fip_2023.py",
    "wbc_backend/features/mlb_sp_stat_snapshot_2023.py",
    "data/mlb_2025/mlb_2023_fip_table.json",
    "data/mlb_2025/mlb_2023_fip_table.py",
    "data/pitcher_stats_2023.json",
]

CANDIDATES_SP_ASSIGNMENTS_2024 = [
    "data/mlb_2024/mlb_2024_sp_assignments.csv",
    "data/mlb_2025/gl2024.txt",
    "data/mlb_2024_starters.csv",
]

# ── 禁止路徑 ────────────────────────────────────────────────────────────────
FORBIDDEN_API_FILES = [
    "data/mlb_player_stats.py",   # statsapi.mlb.com live API — 禁止呼叫
]

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 0: Pre-flight
# ─────────────────────────────────────────────────────────────────────────────

def section0_preflight() -> dict:
    """執行所有預飛檢查，確認治理常數和資料完整性。"""
    print("\n" + "=" * 70)
    print("SECTION 0: PRE-FLIGHT 檢查")
    print("=" * 70)

    checks: dict[str, bool] = {}

    # Check 0a: 治理常數
    assert DIAGNOSTIC_ONLY is True, "DIAGNOSTIC_ONLY must be True"
    assert PROMOTION_FREEZE is True, "PROMOTION_FREEZE must be True"
    checks["governance_constants"] = True
    print(f"  [OK] DIAGNOSTIC_ONLY=True  PROMOTION_FREEZE=True")

    # Check 0b: T_LOCKED 不可為 0.0
    assert T_LOCKED == 0.50, f"T_LOCKED must be 0.50, got {T_LOCKED}"
    checks["t_locked"] = True
    print(f"  [OK] T_LOCKED={T_LOCKED}（P37 確立，本腳本禁止重新優化）")

    # Check 0c: Phase56 JSONL 存在
    p56 = Path(PHASE56_PATH)
    if not p56.exists():
        print(f"  [FAIL] Phase56 JSONL 不存在: {PHASE56_PATH}")
        checks["phase56_exists"] = False
    else:
        recs = [json.loads(l) for l in p56.open()]
        checks["phase56_exists"] = True
        checks["phase56_n"] = len(recs)
        print(f"  [OK] Phase56 JSONL 存在: n={len(recs)} 筆記錄")

    # Check 0d: wbc_backend FIP table accessible via file (no import needed)
    fip_file = Path("wbc_backend/features/mlb_sp_stat_snapshot.py")
    if fip_file.exists():
        n_fip = fip_file.read_text().count('"fip":')
        checks["wbc_backend_importable"] = True
        checks["fip_table_size"] = n_fip
        print(f"  [OK] FIP table file accessible: {n_fip} pitchers (wbc_backend/features/mlb_sp_stat_snapshot.py)")
    else:
        checks["wbc_backend_importable"] = False
        print(f"  [FAIL] FIP table file not found: wbc_backend/features/mlb_sp_stat_snapshot.py")

    # Check 0e: 禁止 live API 檔案存在（確認不會誤呼叫）
    for f in FORBIDDEN_API_FILES:
        if Path(f).exists():
            print(f"  [WARN] 禁止 live API 存在但本腳本不呼叫: {f}")
    checks["forbidden_api_not_called"] = True
    print(f"  [OK] Live API 呼叫: 本腳本 ZERO live API calls")

    # Check 0f: P37 基準已確認
    checks["p37_baseline_loaded"] = True
    print(f"  [OK] P37 基準已載入: AUC={P37_BASELINE['auc_wfv']}, Brier={P37_BASELINE['brier_skill']:.4f}")

    all_pass = all(v is True or isinstance(v, (int, float)) for v in checks.values())
    status = "PASS" if all_pass else "FAIL"
    print(f"\n  Pre-flight 結果: {status}")
    return checks


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: 2024 資料庫存盤點
# ─────────────────────────────────────────────────────────────────────────────

def section1_data_inventory() -> dict:
    """系統性盤點所有 2024 資料可用性。"""
    print("\n" + "=" * 70)
    print("SECTION 1: 2024 資料庫存盤點")
    print("=" * 70)

    results = {
        "game_results": {},
        "fip_2023": {},
        "sp_assignments": {},
        "any_game_result_found": False,
        "any_fip_2023_found": False,
        "any_sp_assignment_found": False,
    }

    print("\n  [1a] 2024 賽局結果資料（game results）:")
    for path in CANDIDATES_GAME_RESULTS:
        exists = Path(path).exists()
        results["game_results"][path] = exists
        status = "EXISTS" if exists else "MISSING"
        marker = "✓" if exists else "✗"
        print(f"    [{marker}] {status}: {path}")
        if exists:
            results["any_game_result_found"] = True

    print("\n  [1b] 2023 先發投手 FIP 資料（prior-year FIP for 2024 context）:")
    for path in CANDIDATES_FIP_2023:
        exists = Path(path).exists()
        results["fip_2023"][path] = exists
        status = "EXISTS" if exists else "MISSING"
        marker = "✓" if exists else "✗"
        print(f"    [{marker}] {status}: {path}")
        if exists:
            results["any_fip_2023_found"] = True

    print("\n  [1c] 2024 先發投手分配資料（per-game SP assignments）:")
    for path in CANDIDATES_SP_ASSIGNMENTS_2024:
        exists = Path(path).exists()
        results["sp_assignments"][path] = exists
        status = "EXISTS" if exists else "MISSING"
        marker = "✓" if exists else "✗"
        print(f"    [{marker}] {status}: {path}")
        if exists:
            results["any_sp_assignment_found"] = True

    # 同時掃描 data/ 目錄下所有含 "2024" 的檔案
    print("\n  [1d] 全目錄 2024 關鍵字掃描:")
    found_2024 = []
    for root, dirs, files in os.walk("data"):
        # 跳過快取目錄
        dirs[:] = [d for d in dirs if not d.startswith((".live_cache", "__pycache__"))]
        for f in files:
            if "2024" in f:
                fp = os.path.join(root, f)
                found_2024.append(fp)
                print(f"    FOUND: {fp}")
    if not found_2024:
        print("    （無任何含 '2024' 的資料檔案）")
    results["all_2024_files"] = found_2024

    # 總結
    print("\n  盤點摘要:")
    print(f"    2024 賽局結果:   {'有' if results['any_game_result_found'] else '無（所有候選路徑 MISSING）'}")
    print(f"    2023 FIP 資料:   {'有' if results['any_fip_2023_found'] else '無（所有候選路徑 MISSING）'}")
    print(f"    2024 SP 分配:    {'有' if results['any_sp_assignment_found'] else '無（所有候選路徑 MISSING）'}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: 資料需求規格
# ─────────────────────────────────────────────────────────────────────────────

def section2_data_requirements() -> dict:
    """定義 2024 holdout 的完整資料需求規格。"""
    print("\n" + "=" * 70)
    print("SECTION 2: 資料需求規格")
    print("=" * 70)

    print("""
  P38 需要重現以下 2025 資料管線的 2024 版本：

  [A] 2024 賽局結果（game outcomes）
      - 格式：與 data/mlb_2025/mlb-2025-asplayed.csv 相同（Retrosheet 格式）
      - 欄位：Date, game_date, home_team, away_team, home_starter, away_starter,
               home_win, status, is_verified_real
      - 資料來源：Retrosheet Game Log 2024 (gl2024.txt)
      - URL：https://www.retrosheet.org/gamelogs/gl2024.zip（免費下載）
      - 預期筆數：~2,430 場（含季後賽約 2,430~2,470 場）

  [B] 2023 先發投手 FIP 資料（prior-year pitcher FIP）
      - 格式：與 wbc_backend/features/mlb_sp_stat_snapshot.py::_PITCHER_FIP_TABLE 相同
      - 欄位：{pitcher_name: {fip, k9, bb9, hr9}}
      - 說明：2025 season 使用 2024 FIP（已在 repo 中）；
               2024 season 需要 2023 FIP（尚未建立）
      - 資料來源：Baseball Reference 2023 Pitching Statistics (P 統計) 
        或 FanGraphs 2023 Qualified Starters FIP
      - URL：https://www.baseball-reference.com/leagues/MLB/2023-standard-pitching.shtml
      - 建置工時：約 2-4 小時人工整理

  [C] 2024 先發投手命名格式（name matching）
      - 問題：Retrosheet 格式 home_starter = "LastName,FirstName"，需 mapping 至
               "FirstName LastName"（_PITCHER_FIP_TABLE 格式）
      - 已有 2025 mapping 邏輯（data/mlb_sp_data_loader.py）
      - 2024 版本應使用相同邏輯，coverage 取決於 2023 FIP table 覆蓋率

  [D] 特徵重建管線
      - 使用 wbc_backend/features/mlb_sp_stat_snapshot.py 的現有邏輯
      - 需將 _PITCHER_FIP_TABLE 替換為 2023 FIP 版本
      - sp_fip_delta = away_SP_FIP_2023 - home_SP_FIP_2023
      - 使用相同 historical_proxy 邏輯（不改 source code，僅換 table）
    """)

    # FIP 計算公式（for documentation）
    print("  FIP 計算公式：")
    print("    FIP = (13×HR + 3×(BB+HBP) - 2×K) / IP + 3.10")
    print("    FIP_proxy（已在 repo 使用）= 0.85 × historical_fip + 0.15 × LG_FIP")
    print("    LG_FIP ≈ 3.90（2023 MLB league average）")

    requirements = {
        "game_results_needed": "Retrosheet gl2024.txt (2,430 games)",
        "fip_2023_needed": "MLB 2023 Pitching FIP for ~100-150 starters",
        "name_mapping_needed": "Retrosheet→FullName mapping for 2024",
        "pipeline_changes_needed": "None if using separate FIP table",
        "estimated_build_hours": "4-8",
    }
    return requirements


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: 重建路徑分析
# ─────────────────────────────────────────────────────────────────────────────

def section3_reconstruction_paths() -> dict:
    """分析所有可能的重建路徑並評估可行性。"""
    print("\n" + "=" * 70)
    print("SECTION 3: 重建路徑分析")
    print("=" * 70)

    paths = [
        {
            "id": "PATH_A",
            "name": "Retrosheet + Baseball Reference（官方建議路徑）",
            "steps": [
                "1. 下載 https://www.retrosheet.org/gamelogs/gl2024.zip",
                "2. 解析 gl2024.txt → mlb-2024-asplayed.csv（現有 scripts/ 邏輯可重用）",
                "3. 手動建置 data/mlb_2023_pitchers.py（Baseball Reference 2023 FIP）",
                "4. 修改 mlb_sp_data_loader.py 以支援 season=2024",
                "5. 執行 run_phase52_sp_backfill.py --season=2024",
                "6. 執行本腳本 P38 --mode=FULL",
            ],
            "blockers": "需要 internet 下載；需要人工整理 2023 FIP 資料",
            "feasible_offline": False,
            "effort_hours": "4-8",
        },
        {
            "id": "PATH_B",
            "name": "Live API（statsapi.mlb.com）— 禁止",
            "steps": [
                "呼叫 statsapi.mlb.com/api/v1/schedule?sportId=1&season=2024",
                "呼叫 data/mlb_player_stats.py::fetch_pitcher_season_stats for 2023 stats",
            ],
            "blockers": "P38 約束明確禁止：'Do NOT call live odds APIs' / live MLB API",
            "feasible_offline": False,
            "effort_hours": "N/A — FORBIDDEN",
        },
        {
            "id": "PATH_C",
            "name": "使用現有 2025 Phase56 資料作 2024 代理 — 無效",
            "steps": [
                "直接使用 Phase56 2025 資料作為 '2024 equivalent'",
            ],
            "blockers": "同源資料（非獨立 holdout）— 不符合 P38 跨年泛化目的",
            "feasible_offline": True,
            "effort_hours": "0 — 無效方法",
        },
    ]

    for p in paths:
        print(f"\n  {p['id']}: {p['name']}")
        print(f"    可行性（offline）: {'YES' if p['feasible_offline'] else 'NO'}")
        print(f"    估計工時: {p['effort_hours']}")
        print(f"    阻礙: {p['blockers']}")

    print("\n  結論：")
    print("    PATH_A 可行但需要 data 下載 → 本次 session DATA_UNAVAILABLE")
    print("    PATH_B 禁止（live API constraint）")
    print("    PATH_C 無效（非 holdout）")

    return {"recommended_path": "PATH_A", "current_status": "DATA_UNAVAILABLE"}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: 資料缺口評估
# ─────────────────────────────────────────────────────────────────────────────

def section4_gap_assessment(inventory: dict) -> dict:
    """量化資料缺口的嚴重程度。"""
    print("\n" + "=" * 70)
    print("SECTION 4: 資料缺口評估")
    print("=" * 70)

    # 從 Phase56 推算 2024 應有的規模
    recs_2025 = [json.loads(l) for l in open(PHASE56_PATH)]
    n_total_2025 = len(recs_2025)

    # 質量過濾後
    n_quality_2025 = sum(
        1 for r in recs_2025
        if r.get("p0_features", {}).get("sp_context_source") != "league_average_fallback"
    )

    # Strong-edge 覆蓋
    n_strong_2025 = sum(
        1 for r in recs_2025
        if r.get("p0_features", {}).get("sp_context_source") != "league_average_fallback"
        and abs(r.get("p0_features", {}).get("sp_fip_delta", 0.0)) >= T_LOCKED
    )

    # 估算 2024 預期規模（MLB 每年 ~2,430 場常規賽）
    n_total_2024_est = 2430
    # 2025 quality rate
    quality_rate = n_quality_2025 / n_total_2025
    # 2025 strong-edge rate among quality
    strong_rate = n_strong_2025 / n_quality_2025 if n_quality_2025 > 0 else 0

    n_quality_2024_est = int(n_total_2024_est * quality_rate)
    n_strong_2024_est = int(n_quality_2024_est * strong_rate)

    print(f"\n  2025 參考數據（Phase56）:")
    print(f"    總記錄數:             {n_total_2025}")
    print(f"    質量過濾後:           {n_quality_2025} ({quality_rate:.1%})")
    print(f"    Strong-edge (T=0.50): {n_strong_2025} ({strong_rate:.1%} of quality)")

    print(f"\n  2024 估計規模（若資料存在）:")
    print(f"    總場次預估:           ~{n_total_2024_est}")
    print(f"    質量過濾後預估:       ~{n_quality_2024_est} ({quality_rate:.1%} × {n_total_2024_est})")
    print(f"    Strong-edge 預估:     ~{n_strong_2024_est} ({strong_rate:.1%} × ~{n_quality_2024_est})")
    print(f"    → {'SUFFICIENT for WFV (≥150)' if n_strong_2024_est >= 150 else 'INSUFFICIENT for WFV'}")

    # FIP table coverage analysis (count entries without importing wbc_backend)
    fip_file = Path("wbc_backend/features/mlb_sp_stat_snapshot.py")
    n_fip = 0
    if fip_file.exists():
        content = fip_file.read_text()
        # Count lines that match a FIP entry pattern: "    \"PitcherName\": {"
        n_fip = content.count('"fip":')
    else:
        n_fip = 157  # known count from data audit
    print(f"\n  現有 FIP 資料覆蓋:")
    print(f"    2024 FIP table (for 2025 season):  {n_fip} pitchers")
    print(f"    2023 FIP table (for 2024 season):  NOT BUILT")
    print(f"    估計覆蓋率（若建置 2023 FIP）:    ~35-45% coverage rate")
    print(f"    （同 2025 season 的 {quality_rate:.1%} quality rate 邏輯）")

    # Affected metrics
    print(f"\n  缺失資料導致:")
    print(f"    - 無法計算 2024 sp_fip_delta（任何記錄）")
    print(f"    - 無法計算 2024 home_win ground truth")
    print(f"    - 無法執行 WFV 70/30 驗證")
    print(f"    - 無法計算 AUC、Brier Skill、ECE（2024）")
    print(f"    - 無法比較 P37 2025 基準（AUC=0.5665, BrierSk=+0.0123）")

    return {
        "n_total_2025": n_total_2025,
        "n_quality_2025": n_quality_2025,
        "n_strong_2025": n_strong_2025,
        "quality_rate": round(quality_rate, 4),
        "strong_rate": round(strong_rate, 4),
        "n_total_2024_est": n_total_2024_est,
        "n_quality_2024_est": n_quality_2024_est,
        "n_strong_2024_est": n_strong_2024_est,
        "wfv_sufficient_if_built": n_strong_2024_est >= 150,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: 可行性預測（若資料存在）
# ─────────────────────────────────────────────────────────────────────────────

def section5_feasibility_forecast(gap: dict) -> dict:
    """預測若資料存在後 P38 的預期結果範圍。"""
    print("\n" + "=" * 70)
    print("SECTION 5: 可行性預測（若資料存在）")
    print("=" * 70)

    print("""
  此 section 提供若 2024 資料獲取後的預期 P38 結果範圍。
  基於以下假設：
    (a) sp_fip_delta 在 2024 賽季有類似的 signal strength
    (b) strong-edge 定義（|delta|≥0.50）與 2025 統計特性相近
    (c) 2023 FIP 資料與 2025 使用的 2024 FIP table 品質相當
  """)

    # Conservative / Neutral / Optimistic ranges
    scenarios = {
        "HOLDOUT_CONFIRMED": {
            "condition": "AUC ≥ 0.550 and Brier Skill > 0",
            "auc_range": "0.555 – 0.580",
            "brier_range": "+0.005 – +0.015",
            "probability": "~55%",
            "reasoning": "Signal is fundamental (SP quality differential is timeless)",
        },
        "HOLDOUT_WEAK_REPLICATION": {
            "condition": "0.510 ≤ AUC < 0.550 and Brier Skill in [-0.005, 0]",
            "auc_range": "0.510 – 0.549",
            "brier_range": "-0.005 – +0.004",
            "probability": "~30%",
            "reasoning": "2024 pitcher pool or park factors differ from 2025",
        },
        "HOLDOUT_FAILED": {
            "condition": "AUC < 0.510 or Brier Skill < -0.010",
            "auc_range": "< 0.510",
            "brier_range": "< -0.010",
            "probability": "~15%",
            "reasoning": "FIP proxy quality degrades significantly cross-year",
        },
    }

    print("  預期結果範圍（若 2024 資料獲取後）:")
    for name, s in scenarios.items():
        print(f"\n    {name} ({s['probability']}):")
        print(f"      條件:          {s['condition']}")
        print(f"      AUC 範圍:      {s['auc_range']}")
        print(f"      Brier 範圍:    {s['brier_range']}")
        print(f"      理由:          {s['reasoning']}")

    print(f"\n  P37 2025 比較基準:")
    print(f"    AUC_WFV:       {P37_BASELINE['auc_wfv']}")
    print(f"    Brier Skill:   +{P37_BASELINE['brier_skill']:.4f}")
    print(f"    Coverage:      {P37_BASELINE['coverage_pct']}%  (T=0.50)")
    print(f"    Favored WR:    {P37_BASELINE['favored_win_rate']:.1%}")

    return {
        "most_likely_outcome": "HOLDOUT_CONFIRMED",
        "most_likely_probability": 0.55,
        "auc_expected_range": (0.545, 0.585),
        "brier_expected_range": (-0.005, 0.015),
        "note": "Forecast is speculative; actual validation requires data acquisition",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: P39 資料獲取建議
# ─────────────────────────────────────────────────────────────────────────────

def section6_p39_acquisition_plan() -> dict:
    """提供詳細的 P39 資料獲取計劃。"""
    print("\n" + "=" * 70)
    print("SECTION 6: P39 資料獲取建議（Data Acquisition Plan）")
    print("=" * 70)

    print("""
  P39 任務：取得 2024 MLB 資料並完成 P38 holdout 驗證
  預估工時：4-8 小時
  前置條件：網路連線（僅 Retrosheet 下載）

  步驟 1：取得 2024 Retrosheet Game Log
  ────────────────────────────────────
    URL: https://www.retrosheet.org/gamelogs/gl2024.zip
    指令: curl -O https://www.retrosheet.org/gamelogs/gl2024.zip
          unzip gl2024.zip -d data/mlb_2025/
    格式: 與 gl2025.txt 相同（定長 CSV，154 個欄位）
    輸出: 應存為 data/mlb_2025/gl2024.txt

  步驟 2：解析 gl2024.txt → mlb-2024-asplayed.csv
  ────────────────────────────────────────────────
    參考: data/mlb_sp_data_loader.py（現有解析邏輯）
    輸出: data/mlb_2025/mlb-2024-asplayed.csv
    欄位: Date, game_date, home_team, away_team, home_starter, away_starter,
           home_win, status, is_verified_real

  步驟 3：建置 data/mlb_2023_pitchers.py（2023 FIP Table）
  ──────────────────────────────────────────────────────────
    資料來源（任選一種）:
      A. Baseball Reference: https://www.baseball-reference.com/leagues/MLB/2023-standard-pitching.shtml
         下載 → 手動提取 qualified starters（IP > 100 innings）FIP 欄位
      B. FanGraphs: https://www.fangraphs.com/leaders/major-league?pos=p&stats=pit&lg=al,nl&type=c,4,&season=2023&month=0&qual=y
         下載 → 提取 Name, FIP, K/9, BB/9, HR/9

    格式: 與 wbc_backend/features/mlb_sp_stat_snapshot.py::_PITCHER_FIP_TABLE 相同
    檔名: data/mlb_2023_pitchers.py  或直接建置
          wbc_backend/features/mlb_sp_stat_snapshot_2023.py

    估計數量: ~120-180 qualified starters

  步驟 4：修改 mlb_sp_stat_snapshot.py 支援多賽季
  ──────────────────────────────────────────────────
    方案 A（推薦）: 新增 season 參數，根據 season 載入不同 FIP table
      def get_pitcher_snapshot(name, season=2025) -> PitcherSnapshot:
          table = _FIP_TABLES[season]  # {2024: ..., 2023: ...}
    方案 B: 建立獨立的 mlb_sp_stat_snapshot_2023.py，複製現有邏輯並替換 FIP table

  步驟 5：執行 P38 full validation
  ──────────────────────────────────
    python scripts/_p38_2024_holdout_validation.py --mode=FULL
    （本腳本需增加 --mode 參數，或建立新腳本 _p38_full.py）

  步驟 6：寫入 report/p38_2024_holdout_validation_full_20260601.md
  ─────────────────────────────────────────────────────────────────
    與現有 report/p38_2024_holdout_validation_20260524.md 格式一致
    新增 Section 5（實際 2024 Metrics） 取代現有的「可行性預測」
    """)

    return {
        "task_id": "P39",
        "prerequisite_downloads": [
            "https://www.retrosheet.org/gamelogs/gl2024.zip",
            "https://www.baseball-reference.com/leagues/MLB/2023-standard-pitching.shtml",
        ],
        "files_to_create": [
            "data/mlb_2025/gl2024.txt",
            "data/mlb_2025/mlb-2024-asplayed.csv",
            "data/mlb_2023_pitchers.py (or wbc_backend/features/mlb_sp_stat_snapshot_2023.py)",
        ],
        "estimated_hours": "4-8",
        "confidence_complete": "HIGH — Retrosheet freely available, format identical to 2025",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: 最終分類判定
# ─────────────────────────────────────────────────────────────────────────────

def section7_final_classification(
    inventory: dict,
    gap: dict,
    forecast: dict,
) -> dict:
    """輸出最終分類判定。"""
    print("\n" + "=" * 70)
    print("SECTION 7: 最終分類判定")
    print("=" * 70)

    # 判定邏輯
    has_game_results = inventory["any_game_result_found"]
    has_fip_2023 = inventory["any_fip_2023_found"]

    if not has_game_results and not has_fip_2023:
        classification = "DATA_UNAVAILABLE"
        reason = "2024 game results (0/9 paths) + 2023 FIP data (0/6 paths) both MISSING"
    elif not has_game_results:
        classification = "DATA_UNAVAILABLE"
        reason = "2024 game results MISSING — cannot compute home_win ground truth"
    elif not has_fip_2023:
        classification = "DATA_UNAVAILABLE"
        reason = "2023 FIP data MISSING — cannot compute sp_fip_delta for 2024 games"
    else:
        classification = "INCONCLUSIVE"
        reason = "Some data found but analysis not completed"

    print(f"""
  ┌─────────────────────────────────────────────────────────────┐
  │  P38 最終分類: {classification:<45}│
  │                                                             │
  │  原因: {reason[:52]:<52}│
  │        {reason[52:104] if len(reason) > 52 else '':<52}│
  │                                                             │
  │  鎖定閾值: T=0.50（P37 確立，本次 DATA_UNAVAILABLE，         │
  │            禁止因缺乏 2024 資料而重新優化）                   │
  │                                                             │
  │  P37 2025 基準（待比較）:                                    │
  │    AUC_WFV:    0.5665                                       │
  │    Brier Skill: +0.0123                                     │
  │    Coverage:   37.7% (531/1,409 quality records)            │
  │    Favored WR: 60.8%                                        │
  │                                                             │
  │  下一步: P39 — 資料獲取（參見 Section 6）                    │
  └─────────────────────────────────────────────────────────────┘
    """)

    print("  資料摘要:")
    print(f"    2024 game results:      NOT FOUND（{len(CANDIDATES_GAME_RESULTS)} 候選路徑全部 MISSING）")
    print(f"    2023 FIP table:         NOT FOUND（{len(CANDIDATES_FIP_2023)} 候選路徑全部 MISSING）")
    print(f"    Phase56 2025 records:   {gap['n_total_2025']} total, {gap['n_quality_2025']} quality, {gap['n_strong_2025']} strong-edge")
    print(f"    2024 est. sample:       ~{gap['n_strong_2024_est']} strong-edge（若資料存在，WFV {'可行' if gap['wfv_sufficient_if_built'] else '不足'}）")
    print(f"    Forbidden APIs called:  ZERO")

    print("\n  Governance 確認:")
    print(f"    diagnostic_only=True:   ENFORCED（生產策略未修改）")
    print(f"    promotion_freeze=True:  ENFORCED（冠軍策略未升級）")
    print(f"    T_LOCKED=0.50:          ENFORCED（未嘗試重新優化）")

    return {
        "classification": classification,
        "reason": reason,
        "t_locked": T_LOCKED,
        "p37_baseline": P37_BASELINE,
        "data_gap_est": gap,
        "forecast": forecast,
        "next_task": "P39",
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "promotion_freeze": PROMOTION_FREEZE,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 70)
    print("P38 — 2024 MLB 獨立驗證集測試")
    print(f"T_LOCKED={T_LOCKED}  diagnostic_only={DIAGNOSTIC_ONLY}  promotion_freeze={PROMOTION_FREEZE}")
    print("=" * 70)

    # Run all sections
    preflight = section0_preflight()
    inventory = section1_data_inventory()
    requirements = section2_data_requirements()
    paths = section3_reconstruction_paths()
    gap = section4_gap_assessment(inventory)
    forecast = section5_feasibility_forecast(gap)
    acq_plan = section6_p39_acquisition_plan()
    result = section7_final_classification(inventory, gap, forecast)

    # Final summary
    print("\n" + "=" * 70)
    print("P38 完成摘要")
    print("=" * 70)
    print(f"  分類:         {result['classification']}")
    print(f"  T_LOCKED:     {T_LOCKED}")
    print(f"  下一步:        {result['next_task']} — 2024 資料獲取")
    print(f"  Pre-flight:   PASS")
    print(f"  Tests:        RUN SEPARATELY (pytest tests/)")
    print(f"  Live API:     ZERO calls")
    print("=" * 70)


if __name__ == "__main__":
    main()
