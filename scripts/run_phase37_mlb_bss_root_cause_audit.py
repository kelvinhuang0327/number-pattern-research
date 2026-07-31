#!/usr/bin/env python3
"""
Phase 37: MLB BSS 負值根因審計腳本
=====================================
執行完整的 10 步根因審計，確定 MLB 2025 BSS = -14.1% 的根因。

使用方式:
  python scripts/run_phase37_mlb_bss_root_cause_audit.py
  python scripts/run_phase37_mlb_bss_root_cause_audit.py --json
  python scripts/run_phase37_mlb_bss_root_cause_audit.py --report
  python scripts/run_phase37_mlb_bss_root_cause_audit.py --section bss_formula

規則 (硬性):
  - 僅讀取 (read-only)，不修改任何模型或生產資料
  - 不呼叫外部 API / LLM
  - 不創建 Patch 候選
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent

import sys as _sys
_sys.path.insert(0, str(ROOT))
from wbc_backend.evaluation.metrics import (
    american_odds_to_implied_prob as _m_american_to_prob,
    normalize_no_vig as _m_normalize_no_vig,
    brier_score as _m_brier,
    brier_skill_score as _m_bss,
)

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
ODDS_CSV = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
OUTCOMES_CSV = ROOT / "data" / "mlb_2025" / "mlb-2025-asplayed.csv"
REPORT_MD = ROOT / "report" / "mlb_2025_full_backtest.md"
METADATA_JSON = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv.metadata.json"

# 報告中的已知值（Phase 37 基準）
REPORT_MODEL_BRIER = 0.2796
REPORT_MARKET_BRIER = 0.2451
REPORT_BSS = -0.141  # = 1 - 0.2796/0.2451


# ══════════════════════════════════════════════════════════════════════════════
# 資料結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AuditFinding:
    """單一根因審計發現"""
    check_id: str
    status: str  # PASS / WARN / FAIL / INFO / SKIP
    summary: str
    detail: str = ""
    root_cause_candidate: bool = False
    severity: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL


@dataclass
class AuditReport:
    """完整根因審計報告"""
    phase: str = "Phase 37"
    dataset: str = "MLB 2025 (2,430 games)"
    report_bss: float = REPORT_BSS
    report_model_brier: float = REPORT_MODEL_BRIER
    report_market_brier: float = REPORT_MARKET_BRIER
    recomputed_market_brier: float = 0.0
    recomputed_n_games: int = 0
    recomputed_duplicates: int = 0
    findings: list[AuditFinding] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    verdict: str = "INCOMPLETE"


# ══════════════════════════════════════════════════════════════════════════════
# 工具函式
# ══════════════════════════════════════════════════════════════════════════════

def _american_to_prob(ml_str: str) -> float:
    """美式賠率 → 含 vig 隱含機率 (delegates to metrics SSOT)"""
    return _m_american_to_prob(ml_str, safe=True)


def _remove_vig(p_home: float, p_away: float) -> tuple[float, float]:
    """比例去除 vig（Pinnacle 方法）(delegates to metrics SSOT)"""
    try:
        return _m_normalize_no_vig(p_home, p_away)
    except ValueError:
        return 0.5, 0.5


def _brier(probs: list[float], outcomes: list[float]) -> float:
    """計算 Brier Score (delegates to metrics SSOT)"""
    if not probs:
        return float("nan")
    return _m_brier(probs, outcomes)


def _bss(model_brier: float, market_brier: float) -> float:
    """BSS = 1 - model_brier / market_brier (delegates to metrics SSOT)"""
    result = _m_bss(model_brier, market_brier)
    return float("nan") if result is None else result


# ══════════════════════════════════════════════════════════════════════════════
# 各審計步驟
# ══════════════════════════════════════════════════════════════════════════════

def _check_bss_formula(report: AuditReport) -> AuditFinding:
    """C01: 驗證 BSS 公式"""
    computed = _bss(REPORT_MODEL_BRIER, REPORT_MARKET_BRIER)
    match = abs(computed - REPORT_BSS) < 0.001
    return AuditFinding(
        check_id="C01_BSS_FORMULA",
        status="PASS" if match else "FAIL",
        summary=f"BSS 公式驗證: 1 - {REPORT_MODEL_BRIER}/{REPORT_MARKET_BRIER} = {computed:+.4f} (報告: {REPORT_BSS:+.4f})",
        detail=(
            "公式 BSS = 1 - model_brier / market_brier 計算結果與報告吻合。"
            if match else
            f"公式計算值 {computed:.4f} 與報告值 {REPORT_BSS:.4f} 不符，差異 {abs(computed-REPORT_BSS):.4f}"
        ),
        root_cause_candidate=not match,
        severity="CRITICAL" if not match else "LOW",
    )


def _check_raw_data_availability(report: AuditReport) -> AuditFinding:
    """C02: 確認原始資料可用"""
    odds_ok = ODDS_CSV.exists()
    outcomes_ok = OUTCOMES_CSV.exists()
    metadata_ok = METADATA_JSON.exists()

    if odds_ok and outcomes_ok:
        # Count rows
        with open(ODDS_CSV) as f:
            odds_n = sum(1 for _ in f) - 1
        with open(OUTCOMES_CSV) as f:
            outcomes_n = sum(1 for _ in f) - 1

        status = "PASS"
        summary = f"原始資料可用: odds={odds_n}行, outcomes={outcomes_n}行"
        detail = f"ODDS: {ODDS_CSV}\nOUTCOMES: {OUTCOMES_CSV}"
    else:
        status = "FAIL"
        summary = "原始資料缺失 (RAW_DATA_MISSING)"
        detail = f"odds_csv_exists={odds_ok}, outcomes_csv_exists={outcomes_ok}"

    return AuditFinding(
        check_id="C02_RAW_DATA_AVAILABILITY",
        status=status,
        summary=summary,
        detail=detail,
        root_cause_candidate=(status == "FAIL"),
        severity="CRITICAL" if status == "FAIL" else "INFO",
    )


def _check_odds_provenance(report: AuditReport) -> AuditFinding:
    """C03: 確認賠率來源可信度"""
    if not METADATA_JSON.exists():
        return AuditFinding(
            check_id="C03_ODDS_PROVENANCE",
            status="SKIP",
            summary="Metadata 檔案不存在，跳過來源驗證",
            detail=str(METADATA_JSON),
        )

    with open(METADATA_JSON) as f:
        meta = json.load(f)

    chain_verified = meta.get("source_chain_verified", False)
    source_type = meta.get("ingest_source_type", "unknown")
    notes = meta.get("notes", "")

    status = "WARN" if not chain_verified else "PASS"
    summary = f"賠率來源: {source_type}, 可信鏈驗證={chain_verified}"

    return AuditFinding(
        check_id="C03_ODDS_PROVENANCE",
        status=status,
        summary=summary,
        detail=f"source_chain_verified={chain_verified}\nnotes={notes}",
        root_cause_candidate=not chain_verified,
        severity="MEDIUM" if not chain_verified else "LOW",
    )


def _check_duplicate_records(report: AuditReport) -> AuditFinding:
    """C04: 檢查重複賽事記錄"""
    if not OUTCOMES_CSV.exists():
        return AuditFinding(
            check_id="C04_DUPLICATE_RECORDS",
            status="SKIP",
            summary="Outcomes CSV 不存在，跳過重複檢查",
        )

    with open(OUTCOMES_CSV) as f:
        rows = list(csv.DictReader(f))

    keys = [(r.get("Date", ""), r.get("Away", ""), r.get("Home", "")) for r in rows]
    seen: set[tuple[str, str, str]] = set()
    duplicates: list[tuple[str, str, str]] = []
    for k in keys:
        if k in seen:
            duplicates.append(k)
        seen.add(k)

    dup_count = len(duplicates)
    report.recomputed_duplicates = dup_count

    if dup_count == 0:
        status = "PASS"
        summary = f"無重複記錄 (總計 {len(rows)} 行)"
        detail = ""
    else:
        status = "WARN"
        summary = f"發現 {dup_count} 筆重複賽事記錄（總計 {len(rows)} 行）"
        detail = f"重複範例: {duplicates[:3]}"

    return AuditFinding(
        check_id="C04_DUPLICATE_RECORDS",
        status=status,
        summary=summary,
        detail=detail,
        root_cause_candidate=(dup_count > 0),
        severity="MEDIUM" if dup_count > 0 else "LOW",
    )


def _check_market_brier_recomputation(report: AuditReport) -> AuditFinding:
    """C05: 從原始資料重新計算市場 Brier Score"""
    if not ODDS_CSV.exists() or not OUTCOMES_CSV.exists():
        return AuditFinding(
            check_id="C05_MARKET_BRIER_RECOMPUTE",
            status="SKIP",
            summary="原始資料不完整，跳過重算",
            root_cause_candidate=True,
            severity="CRITICAL",
        )

    with open(ODDS_CSV) as f:
        odds_rows = list(csv.DictReader(f))
    with open(OUTCOMES_CSV) as f:
        outcome_rows = list(csv.DictReader(f))

    # Build odds map (date, away, home) → row
    odds_map: dict[tuple[str, str, str], dict] = {}
    for o in odds_rows:
        key = (o.get("Date", ""), o.get("Away", ""), o.get("Home", ""))
        odds_map[key] = o

    mkt_probs: list[float] = []
    outcomes: list[float] = []
    seen_keys: set[tuple[str, str, str]] = set()
    unmatched = 0

    for res in outcome_rows:
        key = (res.get("Date", ""), res.get("Away", ""), res.get("Home", ""))
        if key in seen_keys:
            continue  # skip duplicates
        seen_keys.add(key)

        od = odds_map.get(key)
        if od is None:
            unmatched += 1
            continue

        try:
            hw = float(res.get("home_win", 0))
            raw_home = _american_to_prob(od.get("Home ML", "0"))
            raw_away = _american_to_prob(od.get("Away ML", "0"))
            mkt_home, _ = _remove_vig(raw_home, raw_away)
            mkt_probs.append(mkt_home)
            outcomes.append(hw)
        except (ValueError, TypeError):
            continue

    n = len(mkt_probs)
    report.recomputed_n_games = n

    if n < 100:
        return AuditFinding(
            check_id="C05_MARKET_BRIER_RECOMPUTE",
            status="FAIL",
            summary=f"有效比對筆數過少: {n}（最低需 100）",
            root_cause_candidate=True,
            severity="CRITICAL",
        )

    mkt_brier = _brier(mkt_probs, outcomes)
    report.recomputed_market_brier = round(mkt_brier, 4)

    brier_diff = abs(mkt_brier - REPORT_MARKET_BRIER)
    pct_diff = brier_diff / REPORT_MARKET_BRIER * 100

    # Recomputed BSS if model_brier is 0.2796
    recomputed_bss = _bss(REPORT_MODEL_BRIER, mkt_brier)

    if brier_diff < 0.005:
        status = "PASS"
    else:
        status = "WARN"

    summary = (
        f"市場 Brier 重算: {mkt_brier:.4f} (報告: {REPORT_MARKET_BRIER:.4f}, 差異 {brier_diff:.4f} / {pct_diff:.1f}%)"
    )
    detail = (
        f"n={n}, unmatched={unmatched}\n"
        f"重算後 BSS (若 model_brier=0.2796): {recomputed_bss:+.4f} ({recomputed_bss*100:+.1f}%)\n"
        f"報告 BSS: {REPORT_BSS:+.1%}"
    )

    return AuditFinding(
        check_id="C05_MARKET_BRIER_RECOMPUTE",
        status=status,
        summary=summary,
        detail=detail,
        root_cause_candidate=(status == "WARN"),
        severity="MEDIUM" if status == "WARN" else "LOW",
    )


def _check_outcome_label_mapping(report: AuditReport) -> AuditFinding:
    """C06: 確認 home_win 標籤正確性"""
    if not OUTCOMES_CSV.exists():
        return AuditFinding(
            check_id="C06_OUTCOME_LABEL",
            status="SKIP",
            summary="Outcomes CSV 不存在，跳過標籤驗證",
        )

    with open(OUTCOMES_CSV) as f:
        rows = list(csv.DictReader(f))

    hw_one = sum(1 for r in rows if r.get("home_win", "").strip() == "1.0")
    hw_zero = sum(1 for r in rows if r.get("home_win", "").strip() == "0.0")
    hw_other = len(rows) - hw_one - hw_zero

    # Cross-validate: home_win=1 should match rows where home_score > away_score
    mismatch = 0
    for r in rows:
        try:
            hw = float(r.get("home_win", -1))
            hs = float(r.get("Home Score", r.get("home_score", -1)))
            as_ = float(r.get("Away Score", r.get("away_score", -1)))
            if hs < 0 or as_ < 0:
                continue
            expected = 1.0 if hs > as_ else 0.0
            if hw >= 0 and abs(hw - expected) > 0.01:
                mismatch += 1
        except (ValueError, TypeError):
            continue

    status = "PASS" if mismatch == 0 and hw_other == 0 else "WARN"
    summary = f"home_win 標籤: 1={hw_one}, 0={hw_zero}, 其他={hw_other}, 交叉驗證不一致={mismatch}"

    return AuditFinding(
        check_id="C06_OUTCOME_LABEL",
        status=status,
        summary=summary,
        detail=f"home_win=1 表示主場勝, 0 表示客場勝（符合預期）\nmismatch={mismatch}",
        root_cause_candidate=(mismatch > 10),
        severity="HIGH" if mismatch > 10 else "LOW",
    )


def _check_no_vig_formula(report: AuditReport) -> AuditFinding:
    """C07: 驗證 no-vig 公式正確性"""
    # Test cases: (home_ml, away_ml, expected_home, expected_away)
    # Computed correctly via _american_to_prob + _remove_vig:
    #   -150/+130: raw_h=0.60, raw_a=0.4348, total=1.0348 → h=0.5798, a=0.4202
    #   -110/-110: raw_h=0.5238, raw_a=0.5238, total=1.0476 → h=0.5, a=0.5
    #   +200/-250: raw_h=0.3333, raw_a=0.7143, total=1.0476 → h=0.3182, a=0.6818
    test_cases = [
        ("-150", "+130", 0.5798, 0.4202),   # Favorite/underdog
        ("-110", "-110", 0.5, 0.5),          # Symmetric (perfect)
        ("+200", "-250", 0.3182, 0.6818),    # Large spread
    ]

    errors = []
    for home_ml, away_ml, expected_home, expected_away in test_cases:
        raw_h = _american_to_prob(home_ml)
        raw_a = _american_to_prob(away_ml)
        nh, na = _remove_vig(raw_h, raw_a)
        if abs(nh - expected_home) > 0.001 or abs(na - expected_away) > 0.001:
            errors.append(
                f"{home_ml}/{away_ml}: got ({nh:.4f},{na:.4f}), expected ({expected_home},{expected_away})"
            )

    # Check vig percentage for real data
    if ODDS_CSV.exists():
        with open(ODDS_CSV) as f:
            odds_rows = list(csv.DictReader(f))
        vigs = []
        for o in odds_rows:
            raw_h = _american_to_prob(o.get("Home ML", "0"))
            raw_a = _american_to_prob(o.get("Away ML", "0"))
            vigs.append(raw_h + raw_a - 1.0)
        avg_vig = sum(vigs) / len(vigs) if vigs else 0
        vig_detail = f"平均 vig={avg_vig*100:.2f}% (合理範圍: 3-8%)"
        vig_status = "PASS" if 0.02 <= avg_vig <= 0.09 else "WARN"
    else:
        vig_detail = "無賠率資料"
        vig_status = "SKIP"

    status = "FAIL" if errors else vig_status
    summary = (
        f"No-vig 公式: {'有誤差' if errors else '正確'}, {vig_detail}"
    )

    return AuditFinding(
        check_id="C07_NO_VIG_FORMULA",
        status=status,
        summary=summary,
        detail=("\n".join(errors) + "\n" if errors else "") + vig_detail,
        root_cause_candidate=bool(errors),
        severity="HIGH" if errors else "LOW",
    )


def _check_model_calibration(report: AuditReport) -> AuditFinding:
    """C08: 模型校準狀態（ECE 指標審計）"""
    # From report: ECE = 0.1447, cal_method = platt_scaling
    ece = 0.1447
    good_threshold = 0.08
    acceptable_threshold = 0.12

    if ece <= good_threshold:
        status = "PASS"
        severity = "LOW"
        detail = f"ECE={ece:.4f} <= {good_threshold} (良好校準)"
    elif ece <= acceptable_threshold:
        status = "WARN"
        severity = "MEDIUM"
        detail = f"ECE={ece:.4f} 介於 ({good_threshold}, {acceptable_threshold}] 之間（可接受但需改善）"
    else:
        status = "FAIL"
        severity = "HIGH"
        detail = f"ECE={ece:.4f} > {acceptable_threshold} (校準嚴重不足)"

    summary = f"校準誤差 ECE={ece:.4f} (目標 < {good_threshold})"

    return AuditFinding(
        check_id="C08_MODEL_CALIBRATION",
        status=status,
        summary=summary,
        detail=detail,
        root_cause_candidate=(ece > acceptable_threshold),
        severity=severity,
    )


def _check_model_vs_market_probability(report: AuditReport) -> AuditFinding:
    """C09: 模型機率 vs 市場機率分佈比較（基於報告數值）"""
    # From report: market_brier=0.2451, model_brier=0.2796
    # BSS = 1 - 0.2796/0.2451 = -14.07%
    # The market already beats coin flip by 3.1% (coin-flip brier=0.25)
    # The model is worse than the market by 14.1%

    coin_flip_brier = 0.25
    mkt_vs_coinflip_bss = _bss(REPORT_MARKET_BRIER, coin_flip_brier)
    model_vs_coinflip_bss = _bss(REPORT_MODEL_BRIER, coin_flip_brier)

    detail = (
        f"市場 Brier={REPORT_MARKET_BRIER:.4f}, coin-flip BSS={mkt_vs_coinflip_bss:+.1%}\n"
        f"模型 Brier={REPORT_MODEL_BRIER:.4f}, coin-flip BSS={model_vs_coinflip_bss:+.1%}\n"
        f"模型 vs 市場 BSS={REPORT_BSS:+.1%}\n"
        f"結論: 模型雖然略優於拋硬幣但落後市場 14.1%，"
        f"MARL 特徵（ELO+wOBA代理+FIP代理）無法有效捕捉市場隱含資訊。"
    )
    summary = (
        f"模型弱於市場: model_brier={REPORT_MODEL_BRIER:.4f} vs market_brier={REPORT_MARKET_BRIER:.4f}"
    )

    return AuditFinding(
        check_id="C09_MODEL_VS_MARKET",
        status="FAIL",
        summary=summary,
        detail=detail,
        root_cause_candidate=True,
        severity="HIGH",
    )


def _check_walk_forward_windows(report: AuditReport) -> AuditFinding:
    """C10: Walk-Forward 視窗設計審計"""
    # From report: 3 windows, each ~607 test games
    # W1: elo=0.389, market=0.249 → market underweighted
    # W2: elo=0.247, market=0.492 → market higher
    # W3: elo=0.621, market=0.390 → elo dominant

    detail = (
        "Walk-Forward 視窗數: 3 (W1/W2/W3，每窗測試約 607 場)\n"
        "MARL 優化權重:\n"
        "  W1: elo=0.389, market=0.249 → 市場信號被低估\n"
        "  W2: elo=0.247, market=0.492 → 市場信號偏高\n"
        "  W3: elo=0.621, market=0.390 → ELO 主導\n"
        "分析: MARL 在不同視窗的市場權重差異大 (0.249~0.492)，\n"
        "顯示特徵穩定性不足。ELO 代理特徵主導但不及市場賠率精準。"
    )
    summary = "Walk-Forward 3 視窗，MARL 市場權重不穩定 (0.249~0.492)"

    return AuditFinding(
        check_id="C10_WALK_FORWARD_WINDOWS",
        status="WARN",
        summary=summary,
        detail=detail,
        root_cause_candidate=True,
        severity="MEDIUM",
    )


def _check_bss_safety_gate(report: AuditReport) -> AuditFinding:
    """C11: BSS Safety Gate 存在性驗證"""
    gate_file = ROOT / "orchestrator" / "bss_safety_gate.py"
    gate_exists = gate_file.exists()

    if gate_exists:
        # Try importing
        try:
            sys.path.insert(0, str(ROOT))
            from orchestrator.bss_safety_gate import check_bss_safety, evaluate_bss_gate
            # Quick sanity check
            result = check_bss_safety("production_prediction")
            gate_functional = not result.allowed  # Should be blocked (BSS=-14.1%)
        except Exception as e:
            gate_functional = False
            gate_exists = False
    else:
        gate_functional = False

    status = "PASS" if gate_exists and gate_functional else "FAIL"
    summary = f"BSS Safety Gate: exists={gate_exists}, functional={gate_functional}"

    return AuditFinding(
        check_id="C11_BSS_SAFETY_GATE",
        status=status,
        summary=summary,
        detail=(
            f"Gate 位置: {gate_file}\n"
            "驗證: BSS=-14.1% 時，production_prediction 任務應被封鎖。"
        ),
        root_cause_candidate=False,
        severity="CRITICAL" if status == "FAIL" else "LOW",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 主要審計函式
# ══════════════════════════════════════════════════════════════════════════════

def run_audit(section: str | None = None) -> AuditReport:
    """執行完整根因審計並回傳 AuditReport"""
    report = AuditReport()

    checks = [
        ("bss_formula", _check_bss_formula),
        ("raw_data", _check_raw_data_availability),
        ("odds_provenance", _check_odds_provenance),
        ("duplicates", _check_duplicate_records),
        ("market_brier", _check_market_brier_recomputation),
        ("outcome_labels", _check_outcome_label_mapping),
        ("no_vig", _check_no_vig_formula),
        ("calibration", _check_model_calibration),
        ("model_vs_market", _check_model_vs_market_probability),
        ("walk_forward", _check_walk_forward_windows),
        ("safety_gate", _check_bss_safety_gate),
    ]

    for check_name, check_fn in checks:
        if section and check_name != section:
            continue
        try:
            finding = check_fn(report)
            report.findings.append(finding)
        except Exception as e:
            report.findings.append(AuditFinding(
                check_id=check_name.upper(),
                status="ERROR",
                summary=f"審計步驟執行失敗: {e}",
                severity="HIGH",
            ))

    # 彙整根因
    report.root_causes = [
        f.check_id for f in report.findings
        if f.root_cause_candidate and f.status in ("FAIL", "WARN")
    ]

    # 建議
    if "C05_MARKET_BRIER_RECOMPUTE" in report.root_causes:
        report.recommendations.append(
            "METRIC_REPAIR: 確認市場 Brier 計算是否使用重複記錄，統一去重後重新回測。"
        )
    if "C09_MODEL_VS_MARKET" in report.root_causes:
        report.recommendations.append(
            "DATA_REPAIR: 取得真實 Statcast 賠率時間軸，以真實開盤/收盤賠率替代代理值。"
        )
    if "C08_MODEL_CALIBRATION" in report.root_causes:
        report.recommendations.append(
            "METRIC_REPAIR: 調整 Platt Scaling 或使用 Isotonic Regression，目標 ECE < 0.08。"
        )
    if "C10_WALK_FORWARD_WINDOWS" in report.root_causes:
        report.recommendations.append(
            "INVESTIGATE: 增加 Walk-Forward 視窗數至 5+，測試市場權重穩定性。"
        )
    if "C03_ODDS_PROVENANCE" in report.root_causes:
        report.recommendations.append(
            "DATA_REPAIR: 驗證賠率資料來源可信鏈（source_chain_verified=True）。"
        )

    # 判定整體結論
    fail_count = sum(1 for f in report.findings if f.status == "FAIL")
    critical_fails = [f for f in report.findings if f.status == "FAIL" and f.severity == "CRITICAL"]

    if critical_fails:
        report.verdict = "CRITICAL_ROOT_CAUSE_IDENTIFIED"
    elif fail_count > 0:
        report.verdict = "ROOT_CAUSE_IDENTIFIED"
    elif any(f.status == "WARN" for f in report.findings):
        report.verdict = "CONTRIBUTING_FACTORS_IDENTIFIED"
    else:
        report.verdict = "NO_ROOT_CAUSE_FOUND"

    return report


# ══════════════════════════════════════════════════════════════════════════════
# 輸出格式
# ══════════════════════════════════════════════════════════════════════════════

def _render_report_text(r: AuditReport) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"Phase 37: MLB BSS 負值根因審計報告")
    lines.append("=" * 70)
    lines.append(f"資料集    : {r.dataset}")
    lines.append(f"報告 BSS  : {r.report_bss:+.1%} (model_brier={r.report_model_brier}, market_brier={r.report_market_brier})")
    if r.recomputed_market_brier > 0:
        lines.append(f"重算市場  : market_brier={r.recomputed_market_brier}, n={r.recomputed_n_games}, dup={r.recomputed_duplicates}")
    lines.append(f"結論      : {r.verdict}")
    lines.append("")

    for f in r.findings:
        icon = {"PASS": "✓", "FAIL": "✗", "WARN": "△", "INFO": "ℹ", "SKIP": "─", "ERROR": "⚠"}.get(f.status, "?")
        rc = " [ROOT CAUSE]" if f.root_cause_candidate and f.status in ("FAIL", "WARN") else ""
        lines.append(f"  {icon} [{f.check_id}] {f.summary}{rc}")
        if f.detail:
            for dl in f.detail.strip().split("\n"):
                lines.append(f"      {dl}")

    lines.append("")
    lines.append("── 根因清單 ──────────────────────────────────────────────────")
    if r.root_causes:
        for rc in r.root_causes:
            lines.append(f"  • {rc}")
    else:
        lines.append("  (無明確根因)")

    lines.append("")
    lines.append("── 修復建議 ──────────────────────────────────────────────────")
    if r.recommendations:
        for rec in r.recommendations:
            lines.append(f"  → {rec}")
    else:
        lines.append("  (無建議)")

    return "\n".join(lines)


def _to_dict(r: AuditReport) -> dict[str, Any]:
    return {
        "phase": r.phase,
        "dataset": r.dataset,
        "report_bss": r.report_bss,
        "report_model_brier": r.report_model_brier,
        "report_market_brier": r.report_market_brier,
        "recomputed_market_brier": r.recomputed_market_brier,
        "recomputed_n_games": r.recomputed_n_games,
        "recomputed_duplicates": r.recomputed_duplicates,
        "verdict": r.verdict,
        "root_causes": r.root_causes,
        "recommendations": r.recommendations,
        "findings": [
            {
                "check_id": f.check_id,
                "status": f.status,
                "summary": f.summary,
                "detail": f.detail,
                "root_cause_candidate": f.root_cause_candidate,
                "severity": f.severity,
            }
            for f in r.findings
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 37: MLB BSS 負值根因審計"
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出")
    parser.add_argument("--report", action="store_true", help="輸出完整文字報告")
    parser.add_argument(
        "--section",
        help="只執行指定的審計步驟 (e.g. bss_formula, market_brier, safety_gate)",
    )
    args = parser.parse_args()

    audit = run_audit(section=args.section)

    if args.json:
        print(json.dumps(_to_dict(audit), indent=2, ensure_ascii=False))
    elif args.report:
        print(_render_report_text(audit))
    else:
        print(_render_report_text(audit))

    # 退出碼
    if audit.verdict == "CRITICAL_ROOT_CAUSE_IDENTIFIED":
        return 2
    elif audit.verdict in ("ROOT_CAUSE_IDENTIFIED", "CONTRIBUTING_FACTORS_IDENTIFIED"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
