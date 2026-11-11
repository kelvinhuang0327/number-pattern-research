"""P230-A local multi-season run line data audit 測試（純標準庫；驗證 JSON/MD 球季
分類一致、無未來預測/下注優勢宣稱、無遠端擷取邏輯、必列檔案路徑正確、建議下一步標記
為 NOT_AUTHORIZED_YET、P226-A/P227-A/P228-A/P229-A 既有產出未被本任務變動）。"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts import build_p230a_local_multiseason_runline_data_audit as audit_builder

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"

P226A_MD = REPORT_DIR / "p226a_run_line_total_scorecard.md"
P227A_MD = REPORT_DIR / "p227a_total_calibration_scorecard.md"
P228A_MD = REPORT_DIR / "p228a_run_line_robustness_scorecard.md"
P229A_MD = REPORT_DIR / "p229a_run_line_evidence_boundary_pack.md"
P226A_JSON = REPORT_DIR / "p226a_run_line_total_scorecard.json"
P227A_JSON = REPORT_DIR / "p227a_total_calibration_scorecard.json"
P228A_JSON = REPORT_DIR / "p228a_run_line_robustness_scorecard.json"
P229A_JSON = REPORT_DIR / "p229a_run_line_evidence_boundary_pack.json"


# ── 球季分類正確性（比對本機既有檔案事實） ───────────────────────────────────
def test_season_2024_is_label_only_no_odds():
    result = audit_builder.audit_season_2024()
    assert result["season"] == "2024"
    assert result["classification"] == "LABEL_ONLY_NO_ODDS"
    assert result["fields_present"]["final_scores"] is True
    assert result["fields_present"]["run_line_spread"] is False
    assert result["fields_present"]["run_line_prices"] is False


def test_season_2025_is_full_runline_eval_ready():
    result = audit_builder.audit_season_2025()
    assert result["season"] == "2025"
    assert result["classification"] == "FULL_RUNLINE_EVAL_READY"
    assert result["fields_present"]["final_scores"] is True
    assert result["fields_present"]["run_line_spread"] is True
    assert result["fields_present"]["run_line_prices"] is True


def test_season_2026_is_missing_or_unusable():
    result = audit_builder.audit_season_2026()
    assert result["season"] == "2026"
    assert result["classification"] == "MISSING_OR_UNUSABLE"
    assert result["fields_present"]["final_scores"] is False
    assert result["fields_present"]["run_line_spread"] is False


def test_classify_season_covers_all_declared_enum_branches():
    assert audit_builder.classify_season(
        {
            "final_scores": True,
            "home_away_teams": True,
            "game_date": True,
            "run_line_spread": True,
            "run_line_prices": True,
        }
    ) == "FULL_RUNLINE_EVAL_READY"

    assert audit_builder.classify_season(
        {
            "final_scores": True,
            "home_away_teams": True,
            "game_date": True,
            "run_line_spread": False,
            "run_line_prices": False,
        }
    ) == "LABEL_ONLY_NO_ODDS"

    assert audit_builder.classify_season(
        {
            "final_scores": True,
            "home_away_teams": False,
            "game_date": False,
            "run_line_spread": False,
            "run_line_prices": False,
        }
    ) == "SCORES_ONLY"

    assert audit_builder.classify_season(
        {
            "final_scores": False,
            "home_away_teams": False,
            "game_date": False,
            "run_line_spread": False,
            "run_line_prices": False,
        }
    ) == "MISSING_OR_UNUSABLE"

    assert audit_builder.classify_season(
        {
            "final_scores": True,
            "home_away_teams": True,
            "game_date": True,
            "run_line_spread": True,
            "run_line_prices": False,
        }
    ) == "AMBIGUOUS_REQUIRES_REVIEW"


# ── 必列檔案路徑正確性（對照真實本機檔案狀態） ────────────────────────────────
def test_season_2024_files_reference_real_paths_and_row_counts():
    result = audit_builder.audit_season_2024()
    by_path = {f["path"]: f for f in result["files"]}
    assert by_path["data/mlb_2025/mlb-2024-asplayed.csv"]["exists"] is True
    assert by_path["data/mlb_2025/mlb-2024-asplayed.csv"]["row_count"] == 2429
    assert by_path["data/mlb_2025/mlb_odds_2024_real.csv"]["exists"] is False


def test_season_2025_files_reference_real_paths_and_row_counts():
    result = audit_builder.audit_season_2025()
    by_path = {f["path"]: f for f in result["files"]}
    assert by_path["data/mlb_2025/mlb-2025-asplayed.csv"]["row_count"] == 2430
    assert by_path["data/mlb_2025/mlb_odds_2025_real.csv"]["row_count"] == 2430


def test_season_2026_files_reference_real_paths():
    result = audit_builder.audit_season_2026()
    by_path = {f["path"]: f for f in result["files"]}
    assert by_path["data/mlb_2026/schedule/mlb_2026_schedule.jsonl"]["exists"] is True
    assert by_path["data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"]["exists"] is True


def test_excluded_local_data_paths_exist_on_disk():
    audit = audit_builder.build_audit()
    for entry in audit["excluded_local_data"]:
        assert (ROOT / entry["path"]).exists(), f"excluded path missing: {entry['path']}"


# ── 建議下一步標記為 NOT_AUTHORIZED_YET ──────────────────────────────────────
def test_recommended_next_step_is_not_authorized():
    audit = audit_builder.build_audit()
    step = audit["recommended_next_technical_step"]
    assert step["authorization_status"] == "NOT_AUTHORIZED_YET"
    assert step["chosen"] in audit_builder.RECOMMENDATION_CHOICES
    assert "not authorize" in step["note"].lower() or "authorization is required" in step["note"].lower()


def test_recommended_next_step_is_stop_data_gap_given_current_local_evidence():
    audit = audit_builder.build_audit()
    assert audit["recommended_next_technical_step"]["chosen"] == "stop_data_gap"


# ── 無未來預測 / 無下注優勢宣稱 / 無遠端擷取邏輯 ─────────────────────────────
def test_no_future_prediction_or_betting_edge_language_in_markdown():
    audit = audit_builder.build_audit()
    md_text = audit_builder.render_markdown(audit).lower()
    for banned in (
        "we predict",
        "will win",
        "guaranteed",
        "sure thing",
        "real money",
        "deploy to production",
    ):
        assert banned not in md_text, f"banned phrase found: {banned}"
    # "proven edge" is expected to appear only inside the negated disclaimer phrase.
    assert "not a proven edge" in md_text
    assert md_text.count("proven edge") == md_text.count("not a proven edge")
    assert "not a prediction task" in md_text


def test_no_remote_fetch_or_pybaseball_logic_in_source():
    # Strip the module docstring (which legitimately *disclaims* pybaseball/network
    # usage in prose) before scanning for actual usage patterns.
    source = inspect.getsource(audit_builder)
    module_doc = inspect.getdoc(audit_builder) or ""
    code_only = source.replace(module_doc, "", 1).lower()
    for banned in (
        "import pybaseball",
        "requests.get(",
        "requests.post(",
        "urlopen(",
        "sqlite3.connect(",
        "psycopg2.connect(",
    ):
        assert banned not in code_only, f"forbidden remote/DB usage found: {banned}"


# ── JSON 與 MD 球季分類一致 ───────────────────────────────────────────────
def test_json_and_markdown_agree_on_season_classifications(tmp_path):
    audit = audit_builder.build_audit()
    written = audit_builder.write_reports(audit, tmp_path)
    names = {p.name for p in written}
    assert names == {
        "p230a_local_multiseason_runline_data_audit.json",
        "p230a_local_multiseason_runline_data_audit.md",
    }

    json_payload = json.loads(
        (tmp_path / "p230a_local_multiseason_runline_data_audit.json").read_text(encoding="utf-8")
    )
    md_text = (tmp_path / "p230a_local_multiseason_runline_data_audit.md").read_text(encoding="utf-8")

    for season in json_payload["seasons"]:
        assert f"`{season['classification']}`" in md_text
        assert season["season"] in md_text

    step = json_payload["recommended_next_technical_step"]
    assert f"`{step['chosen']}`" in md_text
    assert step["authorization_status"] in md_text


def test_write_reports_deterministic(tmp_path):
    audit = audit_builder.build_audit()
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    audit_builder.write_reports(audit, out1)
    audit_builder.write_reports(audit, out2)
    for name in (
        "p230a_local_multiseason_runline_data_audit.json",
        "p230a_local_multiseason_runline_data_audit.md",
    ):
        assert (out1 / name).read_text(encoding="utf-8") == (out2 / name).read_text(encoding="utf-8")


# ── P226-A/P227-A/P228-A/P229-A 既有產出未被本任務變動 ───────────────────────
def test_p226a_p227a_p228a_p229a_artifacts_unchanged_by_this_test_run():
    """本測試不斷言特定內容，只確認上游四份任務的既有產出仍存在，未被本任務刪除或
    搬移；真正的「未修改」保證來自 Forbidden Files 規範與 PR diff 審查，本測試僅作
    程式層面的存在性回歸防護。"""
    for p in (P226A_MD, P227A_MD, P228A_MD, P229A_MD):
        assert p.exists()


def test_p226a_p227a_p228a_p229a_report_json_present_and_unread_by_audit_module():
    for p in (P226A_JSON, P227A_JSON, P228A_JSON, P229A_JSON):
        assert p.exists()
    source = inspect.getsource(audit_builder)
    for forbidden_ref in (
        "p226a_run_line_total_scorecard.json",
        "p227a_total_calibration_scorecard.json",
        "p228a_run_line_robustness_scorecard.json",
        "p229a_run_line_evidence_boundary_pack.json",
    ):
        assert forbidden_ref not in source
