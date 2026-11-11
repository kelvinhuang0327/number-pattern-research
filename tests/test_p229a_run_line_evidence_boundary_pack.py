"""P229-A run line evidence boundary pack 測試（純標準庫；驗證彙整數值與 P226-A/
P227-A/P228-A 既有報告一致、必要免責聲明存在、無未來預測/live/production/已證實
edge 宣稱、JSON 與 MD 關鍵數字一致、P226-A/P227-A/P228-A 檔案未被本任務變動）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_p229a_run_line_evidence_boundary_pack as pack_builder

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"

P226A_JSON = REPORT_DIR / "p226a_run_line_total_scorecard.json"
P227A_JSON = REPORT_DIR / "p227a_total_calibration_scorecard.json"
P228A_JSON = REPORT_DIR / "p228a_run_line_robustness_scorecard.json"

P226A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "run_line_total_scorecard.py"
P227A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "total_calibration_scorecard.py"
P228A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "run_line_robustness_scorecard.py"
P226A_MD = REPORT_DIR / "p226a_run_line_total_scorecard.md"
P227A_MD = REPORT_DIR / "p227a_total_calibration_scorecard.md"
P228A_MD = REPORT_DIR / "p228a_run_line_robustness_scorecard.md"

REQUIRE_REAL_REPORTS = pytest.mark.skipif(
    not (P226A_JSON.exists() and P227A_JSON.exists() and P228A_JSON.exists()),
    reason="P226-A/P227-A/P228-A report JSON artifacts not present locally",
)


# ── Evidence inventory 數值正確性（對照 P226-A/P227-A/P228-A 既有報告）───────
@REQUIRE_REAL_REPORTS
def test_evidence_inventory_matches_p226a_run_line_baseline():
    sources = pack_builder.load_source_reports(REPORT_DIR)
    ev = pack_builder.build_evidence_inventory(sources)
    rl = ev["p226a_run_line_baseline"]
    assert rl["coinflip_brier"] == pytest.approx(0.2500, abs=1e-4)
    assert rl["poisson_accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert rl["poisson_brier"] == pytest.approx(0.2395, abs=1e-3)
    assert rl["test_rows"] == 972


@REQUIRE_REAL_REPORTS
def test_evidence_inventory_matches_p228a_split_robustness():
    sources = pack_builder.load_source_reports(REPORT_DIR)
    ev = pack_builder.build_evidence_inventory(sources)
    split = ev["p228a_split_robustness"]
    assert split["split_grid_total"] == 3
    assert split["split_grid_strict_wins"] == 3
    assert split["split_grid_not_worse_within_tolerance"] == 3
    assert len(split["splits"]) == 3
    assert all(s["beats_coinflip"] for s in split["splits"])


@REQUIRE_REAL_REPORTS
def test_evidence_inventory_matches_p228a_monthly_robustness():
    sources = pack_builder.load_source_reports(REPORT_DIR)
    ev = pack_builder.build_evidence_inventory(sources)
    monthly = ev["p228a_monthly_robustness"]
    assert monthly["monthly_windows_evaluated"] == 5
    assert monthly["monthly_windows_strict_wins"] == 4
    assert monthly["monthly_windows_not_worse_within_tolerance"] == 5
    assert monthly["monthly_windows_skipped"] == 2
    assert monthly["robustness_label"] == "ROBUST_ENOUGH_FOR_FURTHER_HISTORICAL_RESEARCH"


@REQUIRE_REAL_REPORTS
def test_evidence_inventory_matches_p228a_calibration():
    sources = pack_builder.load_source_reports(REPORT_DIR)
    ev = pack_builder.build_evidence_inventory(sources)
    cal = ev["p228a_calibration"]
    assert cal["raw_brier"] == pytest.approx(0.2395, abs=1e-3)
    assert cal["calibrated_brier"] == pytest.approx(0.2375, abs=1e-3)
    assert cal["raw_ece"] == pytest.approx(0.0483, abs=1e-3)
    assert cal["calibrated_ece"] == pytest.approx(0.0180, abs=1e-3)
    assert cal["calibration_beats_raw_brier"] is True
    assert cal["calibration_beats_raw_ece"] is True


@REQUIRE_REAL_REPORTS
def test_evidence_inventory_matches_p227a_total_limitation():
    sources = pack_builder.load_source_reports(REPORT_DIR)
    ev = pack_builder.build_evidence_inventory(sources)
    total_lim = ev["p227a_total_limitation"]
    assert total_lim["best_by_brier"] == "baseline_coinflip_50pct"
    assert total_lim["beats_coinflip_brier"] is False
    assert total_lim["beats_poisson_brier"] is True


# ── 已授權/未授權宣稱 boundary 內容 ───────────────────────────────────────────
@REQUIRE_REAL_REPORTS
def test_boundary_pack_has_required_sections():
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    assert pack["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert pack["not_a_new_model_task"] is True
    assert len(pack["supported_claims"]) >= 1
    assert len(pack["unsupported_claims"]) >= 1
    assert len(pack["missing_evidence_next_gates"]) >= 1
    assert pack["recommended_next_technical_step"]["authorization_status"] == "NOT_AUTHORIZED_YET"


@REQUIRE_REAL_REPORTS
def test_recommended_next_step_is_not_authorized():
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    step = pack["recommended_next_technical_step"]
    assert step["authorization_status"] == "NOT_AUTHORIZED_YET"
    assert "not authorize" in step["note"].lower() or "authorization required" in step["note"].lower() or \
        "authorization is required" in step["note"].lower()


@REQUIRE_REAL_REPORTS
def test_unsupported_claims_cover_required_boundaries():
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    joined = " ".join(pack["unsupported_claims"]).lower()
    for phrase in ("betting edge", "live readiness", "production readiness",
                   "future prediction", "tradable odds edge", "clv"):
        assert phrase in joined, f"missing unsupported-claim coverage for: {phrase}"


# ── 必要免責聲明 / 禁用語言掃描（於 MD 輸出上）────────────────────────────────
@REQUIRE_REAL_REPORTS
def test_markdown_contains_required_disclaimers(tmp_path):
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    md_text = pack_builder.render_markdown(pack).lower()
    for required in ("not a proven edge", "not production", "not real betting",
                     "paper-only", "historical"):
        assert required in md_text


@REQUIRE_REAL_REPORTS
def test_governance_scan_no_banned_words_and_no_future_prediction_language():
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    md_text = pack_builder.render_markdown(pack).lower()
    for banned in ("guaranteed", "sure thing", "real money", "deploy to production",
                   "we predict", "will win", "upcoming game"):
        assert banned not in md_text
    assert "not a proven edge" in md_text
    assert "no future prediction" in md_text


# ── JSON 與 MD 關鍵數字一致 ────────────────────────────────────────────────
@REQUIRE_REAL_REPORTS
def test_json_and_markdown_agree_on_key_figures(tmp_path):
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    written = pack_builder.write_reports(pack, tmp_path)
    names = {p.name for p in written}
    assert names == {
        "p229a_run_line_evidence_boundary_pack.json",
        "p229a_run_line_evidence_boundary_pack.md",
    }
    json_payload = json.loads(
        (tmp_path / "p229a_run_line_evidence_boundary_pack.json").read_text(encoding="utf-8")
    )
    md_text = (tmp_path / "p229a_run_line_evidence_boundary_pack.md").read_text(encoding="utf-8")

    rl = json_payload["evidence_inventory"]["p226a_run_line_baseline"]
    assert f"{rl['poisson_accuracy']:.4f}" in md_text
    assert f"{rl['poisson_brier']:.4f}" in md_text

    cal = json_payload["evidence_inventory"]["p228a_calibration"]
    assert f"{cal['raw_brier']:.4f}" in md_text
    assert f"{cal['calibrated_brier']:.4f}" in md_text

    monthly = json_payload["evidence_inventory"]["p228a_monthly_robustness"]
    assert monthly["robustness_label"] in md_text

    assert json_payload["recommended_next_technical_step"]["candidate"] in md_text


@REQUIRE_REAL_REPORTS
def test_write_reports_deterministic(tmp_path):
    pack = pack_builder.build_boundary_pack(REPORT_DIR)
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    pack_builder.write_reports(pack, out1)
    pack_builder.write_reports(pack, out2)
    for name in ("p229a_run_line_evidence_boundary_pack.json",
                 "p229a_run_line_evidence_boundary_pack.md"):
        assert (out1 / name).read_text(encoding="utf-8") == (out2 / name).read_text(encoding="utf-8")


@REQUIRE_REAL_REPORTS
def test_build_boundary_pack_missing_upstream_report_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        pack_builder.build_boundary_pack(tmp_path)


# ── CLI blocked-state 檢查（缺上游檔案時） ────────────────────────────────────
def test_main_returns_blocked_when_upstream_reports_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(pack_builder, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(pack_builder, "P226A_JSON", tmp_path / "p226a_run_line_total_scorecard.json")
    monkeypatch.setattr(pack_builder, "P227A_JSON", tmp_path / "p227a_total_calibration_scorecard.json")
    monkeypatch.setattr(pack_builder, "P228A_JSON", tmp_path / "p228a_run_line_robustness_scorecard.json")
    assert pack_builder.main() == 2


# ── P226-A / P227-A / P228-A 檔案未被本任務變動（回歸保護）───────────────────
def test_p226a_p227a_p228a_files_unchanged_by_this_test_run():
    """本測試不斷言特定內容，只確認 P226-A/P227-A/P228-A 原始模組與報告仍存在，
    未被本任務刪除或搬移。真正的「未修改」保證來自 Forbidden Files 規範與 PR diff
    審查，本測試僅作程式層面的存在性回歸防護。"""
    assert P226A_MODULE_PATH.exists()
    assert P227A_MODULE_PATH.exists()
    assert P228A_MODULE_PATH.exists()
    assert P226A_MD.exists()
    assert P227A_MD.exists()
    assert P228A_MD.exists()


@REQUIRE_REAL_REPORTS
def test_p226a_p227a_p228a_report_json_unchanged_content():
    p226 = json.loads(P226A_JSON.read_text(encoding="utf-8"))
    rl = {m["model_name"]: m for m in p226["market_comparison"]["run_line"]}
    assert rl["poisson_team_rate_model"]["accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert rl["poisson_team_rate_model"]["brier_score"] == pytest.approx(0.2395, abs=1e-3)

    p227 = json.loads(P227A_JSON.read_text(encoding="utf-8"))
    assert p227["beats_coinflip_brier"] is False

    p228 = json.loads(P228A_JSON.read_text(encoding="utf-8"))
    assert p228["robustness_conclusion"]["label"] == "ROBUST_ENOUGH_FOR_FURTHER_HISTORICAL_RESEARCH"
