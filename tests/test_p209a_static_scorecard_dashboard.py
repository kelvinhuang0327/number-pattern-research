from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_scorecard_dashboard.py"
OUT_HTML = ROOT / "report" / "p209a_static_scorecard_dashboard.html"
OUT_JSON = ROOT / "report" / "p209a_static_scorecard_dashboard.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_mlb_scorecard_dashboard", SCRIPT)
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

    assert "P209-A STATIC MLB SCORECARD DASHBOARD" in result.stdout
    assert "dashboard HTML:" in result.stdout
    assert "dashboard JSON:" in result.stdout
    assert "best accuracy model: retrained_team_history_smooth" in result.stdout
    assert "best Brier model: calibrated_elo_recent_form" in result.stdout
    assert "all examples are historical replay/backtest only" in result.stdout
    assert OUT_HTML.exists() and OUT_HTML.stat().st_size > 0
    assert OUT_JSON.exists() and OUT_JSON.stat().st_size > 0


def test_dashboard_outputs_are_deterministic_across_two_runs():
    _run_cli()
    first = (_sha(OUT_HTML), _sha(OUT_JSON))
    _run_cli()
    second = (_sha(OUT_HTML), _sha(OUT_JSON))

    assert first == second


def test_html_contains_required_dashboard_sections():
    _run_cli()
    html = OUT_HTML.read_text(encoding="utf-8")

    required = [
        "MLB Local Retrain Historical Scorecard Dashboard",
        "Historical replay/backtest only",
        "Best Accuracy",
        "Best Brier",
        "Model Leaderboard",
        "Confidence-Band Correctness",
        "Selected-Side Counts",
        "Top Historical Examples Sorted By Confidence",
        "P207-A And P208-A Source Artifacts",
        "report/p207a_local_retrain_scorecard.json",
        "report/p208a_visible_scorecard_result_viewer.json",
    ]
    for text in required:
        assert text in html


def test_json_contains_expected_summary_fields():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    assert payload["title"] == "MLB Local Retrain Historical Scorecard Dashboard"
    assert payload["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert payload["best_accuracy_model"]["model_name"] == "retrained_team_history_smooth"
    assert payload["best_accuracy_model"]["accuracy"] == 0.563786
    assert payload["best_brier_model"]["model_name"] == "calibrated_elo_recent_form"
    assert payload["best_brier_model"]["brier_score"] == 0.246033
    assert payload["confidence_band_summary"]["HIGH"] == {
        "accuracy": 0.71875,
        "correct": 23,
        "n": 32,
    }
    assert payload["selected_side_counts"] == {"AWAY": 205, "HOME": 767}
    assert len(payload["leaderboard"]) == 5
    assert len(payload["top_historical_examples"]) == 14
    assert payload["p208_consistency"] == {
        "best_accuracy_model_matches_p208": True,
        "best_brier_model_matches_p208": True,
    }


def test_no_forbidden_affirmative_future_live_or_edge_claims_appear():
    _run_cli()
    text = (OUT_HTML.read_text(encoding="utf-8") + OUT_JSON.read_text(encoding="utf-8")).lower()

    forbidden = [
        "expected value",
        "positive edge",
        "betting edge",
        "roi",
        "payout",
        "kelly",
        "clv",
        "production ready",
        "live-market ready",
        "live market ready",
        "recommendation to bet",
    ]
    for phrase in forbidden:
        assert phrase not in text
    assert "historical replay/backtest only" in text


def test_all_sample_examples_are_historical_only_and_sorted_by_confidence():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    examples = payload["top_historical_examples"]

    assert examples
    assert {row["label"] for row in examples} == {"historical replay / backtest only"}
    assert {row["learning_guard_status"] for row in examples} == {"LOCAL_HISTORICAL_BACKTEST_ONLY"}
    assert all(row["model_name"] == payload["best_brier_model"]["model_name"] for row in examples)
    probabilities = [row["selected_side_probability"] for row in examples]
    assert probabilities == sorted(probabilities, reverse=True)


def test_html_escaping_helper_escapes_data_derived_strings():
    module = _load_module()

    assert module.escape_html('<script data-x="1">x & y</script>') == (
        "&lt;script data-x=&quot;1&quot;&gt;x &amp; y&lt;/script&gt;"
    )
    html = module._leaderboard_table(
        [
            {
                "model_name": '<b onclick="x">bad</b>',
                "accuracy": 0.5,
                "brier_score": 0.25,
                "log_loss": 0.7,
                "calibration_error": 0.1,
                "coverage": 1.0,
                "reference_only": False,
                "notes": "safe & escaped",
            }
        ]
    )

    assert '<b onclick="x">bad</b>' not in html
    assert "&lt;b onclick=&quot;x&quot;&gt;bad&lt;/b&gt;" in html
    assert "safe &amp; escaped" in html
