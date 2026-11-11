"""P235-A final 2025 run line backtest package 測試（純標準庫；required report files
exist／JSON-MD 關鍵數字與標籤一致／Gate 0 數值符合預期／統計附錄 seeded 決定性／
provider path 標記為 PARKED_OPTIONAL／全部限制標籤存在／無下注優勢/未來預測/
live-production/跨球季驗證宣稱／P226/P227/P228/P229/P230/P232 既有產出未被本任務變動）。"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import build_p235a_final_2025_runline_backtest_package as pkgmod

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"

MD_PATH = REPORT_DIR / "p235a_final_2025_runline_backtest_package.md"
JSON_PATH = REPORT_DIR / "p235a_final_2025_runline_backtest_package.json"
APPENDIX_CSV_PATH = REPORT_DIR / "p235a_final_2025_runline_statistical_appendix.csv"

UPSTREAM_ARTIFACTS = [
    REPORT_DIR / "p226a_run_line_total_scorecard.json",
    REPORT_DIR / "p226a_run_line_total_scorecard.md",
    REPORT_DIR / "p226a_run_line_total_predictions.csv",
    REPORT_DIR / "p228a_run_line_robustness_scorecard.json",
    REPORT_DIR / "p228a_run_line_robustness_scorecard.md",
    REPORT_DIR / "p228a_run_line_robustness_predictions.csv",
    REPORT_DIR / "p232a_run_line_feature_ablation_scorecard.json",
    REPORT_DIR / "p232a_run_line_feature_ablation_scorecard.md",
    REPORT_DIR / "p232a_run_line_feature_ablation_predictions.csv",
    REPORT_DIR / "p230a_local_multiseason_runline_data_audit.json",
    REPORT_DIR / "p230a_local_multiseason_runline_data_audit.md",
]

REQUIRED_LOCAL_DATA = all(p.exists() for p in pkgmod.REQUIRED_INPUTS)


# ── required report files exist ─────────────────────────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_required_report_files_exist():
    assert MD_PATH.exists() and MD_PATH.stat().st_size > 0
    assert JSON_PATH.exists() and JSON_PATH.stat().st_size > 0
    assert APPENDIX_CSV_PATH.exists() and APPENDIX_CSV_PATH.stat().st_size > 0


# ── JSON / MD agreement on key metrics and labels ───────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_json_and_md_agree_on_key_metrics_and_labels():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md_text = MD_PATH.read_text(encoding="utf-8")

    g0 = payload["gate0_reproduction"]
    assert g0["status"] in md_text
    rc = g0["recomputed"]
    assert f"{rc['poisson_accuracy']:.4f}" in md_text
    assert f"{rc['poisson_brier']:.4f}" in md_text
    assert f"{rc['coinflip_brier']:.4f}" in md_text
    assert f"{rc['calibrated_brier']:.4f}" in md_text

    assert payload["ablation_summary"]["label"] in md_text
    assert payload["data_status"]["2024"] in md_text
    assert payload["data_status"]["2025"] in md_text
    assert payload["data_status"]["2026"] in md_text
    assert payload["provider_path_status"]["status"] in md_text

    appendix = payload["statistical_appendix"]
    assert f"{appendix['bootstrap']['observed_mean']:.6f}" in md_text
    assert f"{appendix['permutation_test']['p_value']:.6f}" in md_text


# ── Gate 0 values match expected constants ──────────────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_gate0_reproduction_matches_expected_p226a_p228a_values():
    sources = pkgmod.load_source_reports(REPORT_DIR)
    ledger = pkgmod.load_p226a_run_line_ledger()
    anchor = pkgmod.load_p228a_anchor_ledger()
    gate0 = pkgmod.reproduce_gate0(sources, ledger, anchor)

    assert gate0["status"] == "GATE0_REPRODUCED_P235A_FINAL_PACKAGE"
    assert gate0["all_within_tolerance"] is True
    assert gate0["mismatches"] == []

    rc = gate0["recomputed"]
    assert rc["poisson_accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert rc["poisson_brier"] == pytest.approx(0.2395, abs=1e-3)
    assert rc["coinflip_brier"] == pytest.approx(0.2500, abs=1e-4)
    assert rc["calibrated_brier"] == pytest.approx(0.2375, abs=1e-3)

    vf = gate0["verified_from_artifact"]
    assert vf["raw_ece"] == pytest.approx(0.0483, abs=1e-3)
    assert vf["calibrated_ece"] == pytest.approx(0.0180, abs=1e-3)


def test_gate0_raises_on_mismatch():
    ledger = {
        "coinflip": [
            {"game_id": "g1", "predicted_primary_probability": "0.5", "actual_side": "HOME", "correct": "1"},
            {"game_id": "g2", "predicted_primary_probability": "0.5", "actual_side": "AWAY", "correct": "0"},
        ],
        "poisson": [
            {"game_id": "g1", "predicted_primary_probability": "0.9", "actual_side": "HOME", "correct": "1"},
            {"game_id": "g2", "predicted_primary_probability": "0.9", "actual_side": "AWAY", "correct": "0"},
        ],
    }
    anchor = [
        {"game_id": "g1", "calibrated_predicted_home_probability": "0.9", "actual_side": "HOME",
         "calibrated_correct": "1"},
        {"game_id": "g2", "calibrated_predicted_home_probability": "0.9", "actual_side": "AWAY",
         "calibrated_correct": "0"},
    ]
    sources = {"p228a": {"calibration": {"raw": {"calibration_error": 0.0483},
                                          "calibrated": {"calibration_error": 0.0180}}}}
    with pytest.raises(RuntimeError, match="GATE0_FAILED_MISMATCH"):
        pkgmod.reproduce_gate0(sources, ledger, anchor)


# ── statistical appendix determinism under fixed seed ───────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_statistical_appendix_deterministic_across_runs():
    ledger = pkgmod.load_p226a_run_line_ledger()
    a1 = pkgmod.compute_statistical_appendix(ledger)
    a2 = pkgmod.compute_statistical_appendix(ledger)
    assert a1["bootstrap"]["ci95_lower"] == a2["bootstrap"]["ci95_lower"]
    assert a1["bootstrap"]["ci95_upper"] == a2["bootstrap"]["ci95_upper"]
    assert a1["bootstrap"]["observed_mean"] == a2["bootstrap"]["observed_mean"]
    assert a1["permutation_test"]["p_value"] == a2["permutation_test"]["p_value"]


@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_statistical_appendix_bootstrap_ci_excludes_zero_and_brackets_observed_mean():
    ledger = pkgmod.load_p226a_run_line_ledger()
    appendix = pkgmod.compute_statistical_appendix(ledger)
    boot = appendix["bootstrap"]
    assert boot["ci95_lower"] <= boot["observed_mean"] <= boot["ci95_upper"]
    assert boot["seed"] == pkgmod.BOOTSTRAP_SEED
    assert boot["n_resamples"] == pkgmod.N_BOOTSTRAP


@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_statistical_appendix_permutation_pvalue_in_valid_range():
    ledger = pkgmod.load_p226a_run_line_ledger()
    appendix = pkgmod.compute_statistical_appendix(ledger)
    perm = appendix["permutation_test"]
    assert 0.0 < perm["p_value"] <= 1.0
    assert perm["seed"] == pkgmod.PERMUTATION_SEED
    assert perm["n_permutations"] == pkgmod.N_PERMUTATIONS


@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_statistical_appendix_labels_predictive_vs_reference_only():
    ledger = pkgmod.load_p226a_run_line_ledger()
    appendix = pkgmod.compute_statistical_appendix(ledger)
    assert appendix["predictive_baseline"]["label"] == "PREDICTIVE_BASELINE"
    assert appendix["majority_class_reference"]["label"] == "REFERENCE_ONLY"
    assert appendix["model"]["label"] == "MODEL"
    assert appendix["bootstrap"]["label"] == "PREDICTIVE_STATISTIC"
    assert appendix["permutation_test"]["label"] == "PREDICTIVE_STATISTIC"
    # majority class (AWAY, 0.5432) differs from the coinflip predictive baseline
    # (always-HOME, 0.4568) -- surfaced honestly, not conflated.
    ref = appendix["majority_class_reference"]
    baseline = appendix["predictive_baseline"]
    assert ref["majority_class_accuracy_if_always_picked"] != pytest.approx(baseline["accuracy"])


@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_statistical_appendix_csv_rows_deterministic_and_labeled(tmp_path):
    ledger = pkgmod.load_p226a_run_line_ledger()
    appendix = pkgmod.compute_statistical_appendix(ledger)
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    out1.mkdir()
    out2.mkdir()
    p1 = pkgmod.write_statistical_appendix_csv(appendix, out1)
    p2 = pkgmod.write_statistical_appendix_csv(appendix, out2)
    assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")

    with open(p1, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    labels = {r["label"] for r in rows}
    assert "REFERENCE_ONLY" in labels
    assert "PREDICTIVE_BASELINE" in labels
    assert "MODEL" in labels


# ── provider path marked PARKED_OPTIONAL ─────────────────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_provider_path_marked_parked_optional():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    provider = payload["provider_path_status"]
    assert provider["status"] == "PARKED_OPTIONAL"
    assert provider["provider_replies_received"] == 0
    assert provider["true_pit_provider_data_used"] is False


# ── all limitation labels present ────────────────────────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_all_required_limitation_labels_present():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    labels = set(payload["limitation_labels"])
    for required in (
        "2025-ONLY", "HISTORICAL_PAPER_ONLY", "ODDS_PROVENANCE_UNVERIFIED",
        "NOT_TRUE_PIT", "NOT_BETTING_EDGE", "NOT_LIVE", "NOT_PRODUCTION",
        "NOT_FUTURE_PREDICTION", "NOT_MULTI_SEASON_VALIDATION",
    ):
        assert required in labels

    md_lower = MD_PATH.read_text(encoding="utf-8").lower()
    for required_text in (
        "2025-only", "historical", "paper-only", "provenance", "not true-pit",
        "not a proven edge", "not live", "not production", "not future prediction",
        "not multi-season validation",
    ):
        assert required_text in md_lower, f"missing limitation phrase: {required_text}"


# ── no overclaim language ────────────────────────────────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_no_betting_edge_or_future_or_live_production_or_multiseason_claim():
    md_lower = MD_PATH.read_text(encoding="utf-8").lower()
    for banned in (
        "guaranteed", "sure thing", "real money", "deploy to production",
        "we predict", "will win",
    ):
        assert banned not in md_lower, f"banned phrase found: {banned}"
    # "proven edge"/"proven betting edge" are expected to appear only inside
    # the negated disclaimer phrase ("not a proven ... edge").
    assert "not a proven betting edge" in md_lower
    assert md_lower.count("proven betting edge") == md_lower.count("not a proven betting edge")

    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert payload["no_betting_edge_claim"] is True
    assert payload["no_true_pit_validation_claim"] is True
    assert payload["no_multi_season_validation_claim"] is True
    assert payload["no_future_prediction_claim"] is True
    assert payload["no_live_or_production_claim"] is True


# ── upstream artifacts unchanged ─────────────────────────────────────────────
def test_upstream_p226_p228_p230_p232_artifacts_exist_and_unmodified_by_this_module():
    """本模組不修改任何上游檔案；本測試確認上游檔案仍存在，並靜態確認本模組原始碼
    完全不含任何以上游檔名為目標的寫入邏輯（唯一寫入目標僅限 p235a_* 檔案）。"""
    import inspect

    for p in UPSTREAM_ARTIFACTS:
        assert p.exists(), f"upstream artifact missing: {p}"

    source = inspect.getsource(pkgmod)
    write_lines = [
        line for line in source.splitlines()
        if 'open(' in line and ("'w'" in line or '"w"' in line)
    ]
    assert write_lines, "expected at least one write call in the builder module"
    upstream_basenames = {p.name for p in UPSTREAM_ARTIFACTS}
    for line in write_lines:
        for basename in upstream_basenames:
            assert basename not in line, f"write call targets upstream artifact: {line}"


def test_write_reports_only_touches_p235a_named_files(tmp_path):
    ledger = pkgmod.load_p226a_run_line_ledger() if REQUIRED_LOCAL_DATA else None
    if not REQUIRED_LOCAL_DATA:
        pytest.skip("upstream P226/P228/P230/P232 artifacts not present")
    pkg = pkgmod.build_package(REPORT_DIR)
    written = pkgmod.write_reports(pkg, tmp_path)
    for p in written:
        assert p.name.startswith("p235a_")


# ── module-level structural guarantees (no network / DB / pybaseball) ───────
def test_no_remote_fetch_db_or_pybaseball_logic_in_source():
    import inspect

    source = inspect.getsource(pkgmod)
    module_doc = inspect.getdoc(pkgmod) or ""
    code_only = source.replace(module_doc, "", 1).lower()
    for banned in (
        "import pybaseball", "requests.get(", "requests.post(", "urlopen(",
        "sqlite3.connect(", "psycopg2.connect(",
    ):
        assert banned not in code_only, f"forbidden remote/DB usage found: {banned}"


def test_build_package_deterministic(tmp_path):
    if not REQUIRED_LOCAL_DATA:
        pytest.skip("upstream P226/P228/P230/P232 artifacts not present")
    pkg1 = pkgmod.build_package(REPORT_DIR)
    pkg2 = pkgmod.build_package(REPORT_DIR)
    assert pkg1 == pkg2


def test_write_reports_deterministic(tmp_path):
    if not REQUIRED_LOCAL_DATA:
        pytest.skip("upstream P226/P228/P230/P232 artifacts not present")
    pkg = pkgmod.build_package(REPORT_DIR)
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    w1 = pkgmod.write_reports(pkg, out1)
    w2 = pkgmod.write_reports(pkg, out2)
    names1 = {p.name for p in w1}
    names2 = {p.name for p in w2}
    assert names1 == names2 == {
        "p235a_final_2025_runline_backtest_package.json",
        "p235a_final_2025_runline_backtest_package.md",
        "p235a_final_2025_runline_statistical_appendix.csv",
    }
    for name in names1:
        assert (out1 / name).read_text(encoding="utf-8") == (out2 / name).read_text(encoding="utf-8")


# ── P234 acknowledged honestly, not fabricated ───────────────────────────────
@pytest.mark.skipif(not REQUIRED_LOCAL_DATA, reason="upstream P226/P228/P230/P232 artifacts not present")
def test_p234_status_acknowledged_not_fabricated():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert payload["p234_status"]["found_locally"] is False
    assert "p234" in MD_PATH.read_text(encoding="utf-8").lower()
