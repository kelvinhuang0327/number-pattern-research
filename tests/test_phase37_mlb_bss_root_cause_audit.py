"""
Phase 37: MLB BSS 負值根因審計 — 單元測試
===========================================
14 個測試覆蓋審計腳本、Safety Gate 和工具函式。

規則 (硬性):
  - 不呼叫外部 API / LLM
  - 不修改任何模型或生產資料
  - 僅 read-only 操作
"""
from __future__ import annotations

import csv
import json
import math
import sys
import tempfile
from pathlib import Path

import pytest

# 確保專案根目錄在 path 中
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ══════════════════════════════════════════════════════════════════════════════
# T01: BSS 公式驗證
# ══════════════════════════════════════════════════════════════════════════════

class TestBssFormula:
    """C01: BSS = 1 - model_brier / market_brier 公式正確性"""

    def test_01_bss_negative_when_model_worse(self):
        """模型 Brier > 市場 Brier → BSS < 0"""
        model_brier = 0.2796
        market_brier = 0.2451
        bss = 1.0 - model_brier / market_brier
        assert bss < 0, f"Expected BSS < 0, got {bss:.4f}"

    def test_02_bss_known_value_matches_report(self):
        """已知值: 1 - 0.2796/0.2451 ≈ -0.141"""
        model_brier = 0.2796
        market_brier = 0.2451
        bss = 1.0 - model_brier / market_brier
        assert abs(bss - (-0.141)) < 0.001, f"BSS={bss:.4f}, expected ~-0.141"

    def test_03_bss_positive_when_model_better(self):
        """模型 Brier < 市場 Brier → BSS > 0"""
        model_brier = 0.22
        market_brier = 0.25
        bss = 1.0 - model_brier / market_brier
        assert bss > 0, f"Expected BSS > 0, got {bss:.4f}"

    def test_04_bss_zero_when_equal(self):
        """模型 Brier == 市場 Brier → BSS = 0"""
        brier = 0.25
        bss = 1.0 - brier / brier
        assert abs(bss) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# T02: No-vig 公式測試
# ══════════════════════════════════════════════════════════════════════════════

class TestNoVigFormula:
    """C07: 美式賠率去 vig 計算"""

    def _american_to_prob(self, ml_str: str) -> float:
        try:
            ml = float(str(ml_str).replace("+", "").strip())
            return abs(ml) / (abs(ml) + 100) if ml < 0 else 100 / (ml + 100)
        except Exception:
            return 0.5

    def _remove_vig(self, p_h: float, p_a: float) -> tuple[float, float]:
        total = p_h + p_a
        if total <= 0:
            return 0.5, 0.5
        return p_h / total, p_a / total

    def test_05_symmetric_line_gives_fifty_fifty(self):
        """-110/-110 → 50/50 機率"""
        rh = self._american_to_prob("-110")
        ra = self._american_to_prob("-110")
        ph, pa = self._remove_vig(rh, ra)
        assert abs(ph - 0.5) < 0.001
        assert abs(pa - 0.5) < 0.001

    def test_06_sum_to_one_after_vig_removal(self):
        """去 vig 後機率和為 1"""
        rh = self._american_to_prob("-150")
        ra = self._american_to_prob("+130")
        ph, pa = self._remove_vig(rh, ra)
        assert abs(ph + pa - 1.0) < 1e-9

    def test_07_favorite_has_higher_prob_after_vig(self):
        """強隊賠率 → 去 vig 後機率仍較高"""
        rh = self._american_to_prob("-200")
        ra = self._american_to_prob("+170")
        ph, pa = self._remove_vig(rh, ra)
        assert ph > pa, f"ph={ph:.4f} should > pa={pa:.4f}"

    def test_08_invalid_ml_returns_half(self):
        """無效賠率 → 回傳 0.5"""
        result = self._american_to_prob("N/A")
        assert abs(result - 0.5) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# T03: BSS Safety Gate 測試
# ══════════════════════════════════════════════════════════════════════════════

class TestBssSafetyGate:
    """C11: BSS Safety Gate 正確封鎖生產任務"""

    def _get_gate(self):
        from orchestrator.bss_safety_gate import evaluate_bss_gate, check_bss_safety
        return evaluate_bss_gate, check_bss_safety

    def test_09_blocks_production_when_bss_negative(self):
        """BSS < 0 時，production_prediction 應被封鎖"""
        evaluate_bss_gate, _ = self._get_gate()
        result = evaluate_bss_gate(
            bss=-0.141, model_brier=0.2796, baseline_brier=0.2451,
            task_kind="production_prediction"
        )
        assert not result.allowed
        assert result.bss_negative

    def test_10_allows_investigate_when_bss_negative(self):
        """BSS < 0 時，investigate 任務應被允許"""
        evaluate_bss_gate, _ = self._get_gate()
        result = evaluate_bss_gate(
            bss=-0.141, model_brier=0.2796, baseline_brier=0.2451,
            task_kind="investigate_bss_root_cause"
        )
        assert result.allowed
        assert result.bss_negative

    def test_11_allows_all_when_bss_positive(self):
        """BSS >= 0 時，所有任務均允許"""
        evaluate_bss_gate, _ = self._get_gate()
        for task in ["production_prediction", "live_bet", "kelly_bet"]:
            result = evaluate_bss_gate(
                bss=0.05, model_brier=0.22, baseline_brier=0.25,
                task_kind=task
            )
            assert result.allowed, f"task={task} should be allowed when BSS > 0"

    def test_12_blocks_kelly_bet_when_bss_negative(self):
        """BSS < 0 時，kelly_bet 應被封鎖"""
        evaluate_bss_gate, _ = self._get_gate()
        result = evaluate_bss_gate(
            bss=-0.05, model_brier=0.26, baseline_brier=0.25,
            task_kind="kelly_bet_execution"
        )
        assert not result.allowed

    def test_13_allows_metric_repair_when_bss_negative(self):
        """BSS < 0 時，metric_repair 任務應被允許"""
        evaluate_bss_gate, _ = self._get_gate()
        result = evaluate_bss_gate(
            bss=-0.141, model_brier=0.2796, baseline_brier=0.2451,
            task_kind="metric_repair_calibration"
        )
        assert result.allowed

    def test_14_check_bss_safety_convenience_function(self):
        """check_bss_safety 便利函式使用報告預設值"""
        _, check_bss_safety = self._get_gate()
        # production task should be blocked (BSS=-14.1%)
        result = check_bss_safety("production_prediction")
        assert not result.allowed
        assert result.bss < 0


# ══════════════════════════════════════════════════════════════════════════════
# T04: 審計腳本整合測試
# ══════════════════════════════════════════════════════════════════════════════

class TestAuditScript:
    """審計腳本整合測試"""

    def _get_audit(self):
        from scripts.run_phase37_mlb_bss_root_cause_audit import run_audit, _bss, _brier
        return run_audit, _bss, _brier

    def test_15_audit_returns_report_with_findings(self):
        """run_audit() 返回含 findings 的 AuditReport"""
        run_audit, _, _ = self._get_audit()
        report = run_audit()
        assert len(report.findings) > 0
        check_ids = [f.check_id for f in report.findings]
        assert "C01_BSS_FORMULA" in check_ids
        assert "C09_MODEL_VS_MARKET" in check_ids

    def test_16_audit_identifies_root_causes(self):
        """run_audit() 識別出根因"""
        run_audit, _, _ = self._get_audit()
        report = run_audit()
        assert len(report.root_causes) > 0, "Should identify at least one root cause"

    def test_17_audit_verdict_is_root_cause_identified(self):
        """verdict 應為 ROOT_CAUSE_IDENTIFIED"""
        run_audit, _, _ = self._get_audit()
        report = run_audit()
        assert report.verdict in (
            "ROOT_CAUSE_IDENTIFIED",
            "CRITICAL_ROOT_CAUSE_IDENTIFIED",
            "CONTRIBUTING_FACTORS_IDENTIFIED",
        ), f"Unexpected verdict: {report.verdict}"

    def test_18_c01_bss_formula_passes(self):
        """C01 BSS 公式驗證應 PASS"""
        run_audit, _, _ = self._get_audit()
        report = run_audit(section="bss_formula")
        assert any(f.check_id == "C01_BSS_FORMULA" and f.status == "PASS" for f in report.findings)

    def test_19_c09_model_vs_market_is_root_cause(self):
        """C09 模型 vs 市場應為根因"""
        run_audit, _, _ = self._get_audit()
        report = run_audit(section="model_vs_market")
        finding = next((f for f in report.findings if f.check_id == "C09_MODEL_VS_MARKET"), None)
        assert finding is not None
        assert finding.root_cause_candidate is True

    def test_20_no_external_api_calls(self):
        """審計腳本不可呼叫外部 API（確認無 requests/urllib 匯入）"""
        audit_file = ROOT / "scripts" / "run_phase37_mlb_bss_root_cause_audit.py"
        content = audit_file.read_text()
        forbidden = ["import requests", "urllib.request", "http.client", "openai", "anthropic"]
        for token in forbidden:
            assert token not in content, f"Found forbidden import: {token}"

    def test_21_safety_gate_file_exists(self):
        """orchestrator/bss_safety_gate.py 必須存在"""
        gate_file = ROOT / "orchestrator" / "bss_safety_gate.py"
        assert gate_file.exists(), f"Safety gate file not found: {gate_file}"


# ══════════════════════════════════════════════════════════════════════════════
# T05: 市場 Brier 重算測試（合成資料）
# ══════════════════════════════════════════════════════════════════════════════

class TestMarketBrierRecomputation:
    """C05: 市場 Brier 重算（使用合成資料）"""

    def _make_odds_csv(self, tmp_path: Path, rows: list[dict]) -> Path:
        p = tmp_path / "odds.csv"
        fieldnames = ["Date", "Away", "Home", "Away ML", "Home ML", "Status", "is_verified_real"]
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return p

    def _make_outcomes_csv(self, tmp_path: Path, rows: list[dict]) -> Path:
        p = tmp_path / "outcomes.csv"
        fieldnames = ["Date", "Away", "Home", "home_win", "Away Score", "Home Score"]
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return p

    def test_22_market_brier_of_perfect_predictor_is_zero(self):
        """完美預測器的 Brier = 0"""
        from scripts.run_phase37_mlb_bss_root_cause_audit import _brier
        probs = [1.0, 1.0, 0.0, 0.0]
        outcomes = [1.0, 1.0, 0.0, 0.0]
        assert abs(_brier(probs, outcomes)) < 1e-9

    def test_23_market_brier_of_coin_flip_is_quarter(self):
        """拋硬幣預測器的 Brier = 0.25"""
        from scripts.run_phase37_mlb_bss_root_cause_audit import _brier
        n = 1000
        probs = [0.5] * n
        outcomes = [1.0] * (n // 2) + [0.0] * (n // 2)
        assert abs(_brier(probs, outcomes) - 0.25) < 1e-9

    def test_24_bss_interpretation(self):
        """BSS < 0 代表模型劣於市場基準（模型在錯誤方向過度自信）"""
        from scripts.run_phase37_mlb_bss_root_cause_audit import _bss, _brier
        n = 1000
        # 50/50 outcomes
        outcomes = [1.0] * 500 + [0.0] * 500
        # Market: calibrated (mkt_brier ~ 0.2025)
        market_probs = [0.55] * 500 + [0.45] * 500
        # Model: always predicts home win (p=0.70), wrong for ALL away wins
        # model_brier = (500*(0.70-1)^2 + 500*(0.70-0)^2)/1000 = 0.29
        model_probs = [0.70] * n
        mkt_brier = _brier(market_probs, outcomes)
        model_brier = _brier(model_probs, outcomes)
        bss = _bss(model_brier, mkt_brier)
        assert bss < 0, (
            f"Expected BSS < 0 for model always predicting home win, "
            f"got {bss:.4f} (model_brier={model_brier:.4f}, mkt_brier={mkt_brier:.4f})"
        )
