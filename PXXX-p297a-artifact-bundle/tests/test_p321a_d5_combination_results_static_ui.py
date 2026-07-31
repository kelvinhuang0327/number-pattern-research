"""P321A static P320A combination-result UI acceptance tests.

These tests read static files only. They do not access or create a database.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
D5_JS = REPO_ROOT / "src" / "apps" / "lottery-d5" / "lottery-d5.js"
ARTIFACT_ROOT = REPO_ROOT / "public" / "demo-data" / "lottery-d5" / "p320a"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_HASHES = {
    "strategy_combination_metrics.csv": "0141b53f135a456fb3c2d02fe15f17aa5728a7ff8f47c88d26777c025e855ec5",
    "top_descriptive_candidates.csv": "e1b074aed742eab0306cdcd002082635899c215e289d2dd1208a61353087cabd",
    "window_summary.csv": "63e72bf7362542e072e4244361a1bc9b70fd5dd01e0067ff64a697c8e785a985",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _csv_rows(name: str) -> list[dict[str, str]]:
    with (ARTIFACT_ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_p320a_static_artifact_hashes_and_provenance_are_preserved():
    provenance = json.loads((ARTIFACT_ROOT / "source_provenance.json").read_text(encoding="utf-8"))
    assert provenance["source_manifest_sha256"] == "503bb58754b63576d69a8640cd3242f53761e068b424b6864f7e167f326f5596"
    assert provenance["copy_mode"] == "byte-for-byte unchanged static files"
    assert provenance["baseline_mode"] == "not_computed"
    assert provenance["inferential_status"] == "DESCRIPTIVE_ONLY"
    assert provenance["power_lotto_scoring"] == "NOT RUN"

    by_path = {item["path"]: item for item in provenance["artifacts"]}
    for name, expected_hash in EXPECTED_HASHES.items():
        assert _sha256(ARTIFACT_ROOT / name) == expected_hash
        assert by_path[name]["source_sha256"] == expected_hash
        assert by_path[name]["copied_sha256"] == expected_hash


def test_combination_metric_scope_and_exact_shortlist_counts():
    metrics = _csv_rows("strategy_combination_metrics.csv")
    candidates = _csv_rows("top_descriptive_candidates.csv")
    summaries = _csv_rows("window_summary.csv")

    assert len(metrics) == 2418
    assert len(candidates) == 60
    assert len(summaries) == 6
    assert {row["lottery_type"] for row in metrics} == {"BIG_LOTTO", "DAILY_539"}
    assert {row["window"] for row in metrics} == {"recent_50", "recent_300", "recent_750"}
    assert {row["combination_size"] for row in metrics} == {"1", "2", "3"}
    assert all(row["classification"] == "DESCRIPTIVE_ONLY" for row in metrics)
    assert all(row["baseline_mode"] == "not_computed" for row in metrics)
    assert all(row["inferential_status"] == "DESCRIPTIVE_ONLY" for row in metrics)
    assert {row["combination_size"] for row in candidates} == {"2", "3"}


def test_combination_panel_is_visible_useful_and_explicitly_non_claiming():
    html = INDEX_HTML.read_text(encoding="utf-8")
    module = D5_JS.read_text(encoding="utf-8")
    d5_region = html.split("<!-- ===== P300A D5 Strategy Hit-Rate Matrix MVP", 1)[1].split(
        "<!-- ===== END P300A D5 ===== -->", 1
    )[0]
    combined = d5_region + "\n" + module

    for expected in [
        "Combination Results",
        "Historical Combination Metrics",
        "BIG_LOTTO + DAILY_539",
        "recent_50",
        "recent_300",
        "recent_750",
        "single",
        "pair",
        "triple",
        "sample_size_draws",
        "sample_size_rows",
        "hit&gt;=1 rate",
        "hit&gt;=2 rate",
        "hit&gt;=3 rate",
        "baseline_mode=not_computed",
        "DESCRIPTIVE_ONLY",
        "POWER_LOTTO: NOT RUN / excluded",
        "Historical descriptive replay result only. No random baseline or statistical inference computed. Not a prediction or betting recommendation.",
        "data-combination-artifact-root=\"public/demo-data/lottery-d5/p320a\"",
    ]:
        assert expected in combined

    assert '<option value="recent_750" selected>' in html
    assert '<option value="3" selected>triple</option>' in html
    assert 'class="d5-panel active d5-combination-panel"' in html
    assert "renderCombinationResults" in module
    assert "top_descriptive_candidates.csv" in module

    lowered = combined.lower()
    assert "best strategy" not in lowered
    assert "betting pick" not in lowered
    assert "recommended numbers" not in lowered
    assert "method: 'post'" not in lowered
    assert 'method: "post"' not in lowered
    assert "sqlite3" not in module


def test_task_does_not_create_forbidden_db_path():
    assert not DB_PATH.exists()
