from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_historical_slice_analysis.py"
OUT_HTML = ROOT / "report" / "p210a_historical_slice_analysis.html"
OUT_JSON = ROOT / "report" / "p210a_historical_slice_analysis.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_mlb_historical_slice_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_cli() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_cli_runs_from_repo_root_and_writes_dashboard_files():
    result = _run_cli()

    assert "P210-A HISTORICAL MLB SLICE ANALYSIS" in result.stdout
    assert "dashboard HTML:" in result.stdout
    assert "dashboard JSON:" in result.stdout
    assert "prediction rows read: 3888" in result.stdout
    assert "models analyzed: 4" in result.stdout
    assert "all examples are historical replay/backtest only" in result.stdout
    assert OUT_HTML.exists() and OUT_HTML.stat().st_size > 0
    assert OUT_JSON.exists() and OUT_JSON.stat().st_size > 0


def test_dashboard_outputs_are_deterministic_across_two_runs():
    _run_cli()
    first = (_sha(OUT_HTML), _sha(OUT_JSON))
    _run_cli()
    second = (_sha(OUT_HTML), _sha(OUT_JSON))

    assert first == second


def test_json_contains_required_slice_sections():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    assert payload["title"] == "MLB Historical Slice Analysis Dashboard"
    assert payload["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert payload["disclaimer"] == (
        "Historical replay/backtest only. Not live predictions, not betting advice."
    )
    assert payload["prediction_rows_read"] == 3888
    assert payload["models_analyzed"] == [
        "baseline_fixed_prior",
        "calibrated_elo_recent_form",
        "elo_like_rating",
        "retrained_team_history_smooth",
    ]
    assert set(payload["slices"]) == {
        "month_by_model",
        "confidence_band_by_model",
        "selected_side_by_model",
        "top_team_exposure",
    }
    assert len(payload["slices"]["month_by_model"]) == 12
    assert len(payload["slices"]["confidence_band_by_model"]) == 12
    assert len(payload["slices"]["selected_side_by_model"]) == 8
    assert payload["slices"]["top_team_exposure"]
    assert payload["examples"]["top_correct_high_confidence"]
    assert payload["examples"]["top_incorrect_high_confidence"]
    assert payload["merge_lineage"]["P209-A"] == (
        "48727abef6e3323fdbfe37b89d7e10cf7497f692"
    )


def test_html_contains_required_dashboard_sections_and_disclaimer():
    _run_cli()
    html = OUT_HTML.read_text(encoding="utf-8")

    required = [
        "Historical replay/backtest only. Not live predictions, not betting advice.",
        "MLB Historical Slice Analysis Dashboard",
        "Source Artifacts And Merge Lineage",
        "report/p207a_local_retrain_scorecard.json",
        "report/p208a_visible_scorecard_result_viewer.json",
        "report/p209a_static_scorecard_dashboard.json",
        "Month-By-Month Accuracy And Count Slices",
        "Confidence-Band Correctness Slices",
        "Selected-Side HOME/AWAY Counts And Correctness",
        "Top Teams By Exposure",
        "Top Correct High-Confidence Historical Examples",
        "Top Incorrect High-Confidence Historical Examples",
        "Limitations",
    ]
    for text in required:
        assert text in html


def test_no_forbidden_future_live_or_betting_edge_claims_appear():
    _run_cli()
    text = (OUT_HTML.read_text(encoding="utf-8") + OUT_JSON.read_text(encoding="utf-8")).lower()

    forbidden = [
        "expected value",
        "positive edge",
        "betting edge",
        "payout",
        "kelly",
        "clv",
        "production ready",
        "live-market ready",
        "live market ready",
        "recommendation to bet",
        "future prediction ability",
    ]
    for phrase in forbidden:
        assert phrase not in text
    assert not re.search(r"\broi\b", text)
    assert "historical replay/backtest only" in text


def test_all_sample_examples_are_labeled_historical_replay_backtest_only():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    examples = (
        payload["examples"]["top_correct_high_confidence"]
        + payload["examples"]["top_incorrect_high_confidence"]
    )

    assert examples
    assert {row["label"] for row in examples} == {"historical replay/backtest only"}
    assert {row["learning_guard_status"] for row in examples} == {
        "LOCAL_HISTORICAL_BACKTEST_ONLY"
    }
    assert all(row["confidence_band"] == "HIGH" for row in examples)


def test_html_escaping_helper_escapes_data_derived_strings():
    module = _load_module()

    assert module.escape_html('<script data-x="1">x & y</script>') == (
        "&lt;script data-x=&quot;1&quot;&gt;x &amp; y&lt;/script&gt;"
    )
    html = module._slice_table(
        [
            {
                "model_name": '<b onclick="x">bad</b>',
                "month": "2025-07",
                "count": 1,
                "correct": 1,
                "accuracy": 1.0,
            }
        ],
        "month",
        "Month",
        "empty",
    )

    assert '<b onclick="x">bad</b>' not in html
    assert "&lt;b onclick=&quot;x&quot;&gt;bad&lt;/b&gt;" in html


def test_missing_optional_columns_are_skipped_and_recorded_in_limitations():
    module = _load_module()
    model_rows = [
        {
            "model_name": "model_a",
            "train_rows": "1",
            "test_rows": "2",
            "accuracy": "0.5",
            "log_loss": "0.7",
            "brier_score": "0.25",
            "calibration_error": "0.1",
            "coverage": "1.0",
            "notes": "unit fixture",
        }
    ]
    prediction_rows = [
        {
            "model_name": "model_a",
            "predicted_home_win_probability": "0.6",
            "selected_side": "HOME",
            "confidence_band": "HIGH",
            "actual_home_win": "1",
            "correct": "1",
        }
    ]

    payload = module.build_dashboard_payload(
        {"task": "fixture", "split": {}},
        model_rows,
        prediction_rows,
        {"scope": "fixture"},
        {"scope": "fixture", "title": "fixture"},
    )

    assert payload["slices"]["month_by_model"] == []
    assert payload["slices"]["top_team_exposure"] == []
    assert payload["examples"]["top_correct_high_confidence"] == []
    assert any("Skipped month_by_model slice" in item for item in payload["limitations"])
    assert any("Skipped team_exposure slice" in item for item in payload["limitations"])
    assert any("Skipped historical_examples slice" in item for item in payload["limitations"])
