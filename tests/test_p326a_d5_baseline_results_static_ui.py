"""P326A static P325A equal-budget baseline UI acceptance tests.

These tests read static files only. They do not access or create a database.
Every displayed number is independently re-derived here from the copied,
SHA256-verified P325A metrics CSV, so fabricated summary values cannot pass.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
D5_JS = REPO_ROOT / "src" / "apps" / "lottery-d5" / "lottery-d5.js"
BASELINE_ROOT = REPO_ROOT / "public" / "demo-data" / "lottery-d5" / "p325a"
BUILD_SCRIPT = REPO_ROOT / "tools" / "lottery-d5" / "build_p326a_baseline_summary.py"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

CARRIER = "daily539_f4cold_5bet"

# Byte-identical copies; hashes from the verified P325A evidence-root manifest.json.
EXPECTED_HASHES = {
    "equal_budget_baseline_summary.md": "e7af4c900db3929d4417173c8a910c3931e306cbfdcd73b5e23ad04ee75cea38",
    "equal_budget_baseline_metrics.csv": "74bd38c01b6b1e24cf3ead12d64528ce048f4585aae3b3fb712564b8ffbe3932",
    "budget_bias_diagnostics.csv": "e49f1909463fe976f7504bf0cae0d5efe7e469cae33dc4b957cdc152ccd69d50",
    "random_baseline_reference.csv": "2fe10a459c2abb0c8ef9853458095621f9ce0004095b7eae0d380f18de28e01b",
    "baseline_method.md": "8b1d5f1a62592e870b94af0e2e17249edf3fb640e0a27563965dc1b647bdbe92",
    "limitations.md": "4902a3f35028278fa70154621df7d9a6696d00662b2a022e020fc41ef31d9af2",
    "handoff_report.md": "3b428898fa5939e65e0dabc8f206c67f310ac333f8a7cb8296f6850e4888f57a",
}
SOURCE_MANIFEST_SHA256 = "4f70f257eefe5bd165c88e6579e9f97047139d80e884c3621e9163ebd36466d7"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics() -> list[dict[str, str]]:
    with (BASELINE_ROOT / "equal_budget_baseline_metrics.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _summary() -> dict:
    return json.loads((BASELINE_ROOT / "baseline_summary.json").read_text(encoding="utf-8"))


def test_p325a_copies_are_byte_identical_and_provenance_is_documented():
    for name, expected in EXPECTED_HASHES.items():
        assert _sha256(BASELINE_ROOT / name) == expected, name

    provenance = json.loads((BASELINE_ROOT / "source_provenance.json").read_text(encoding="utf-8"))
    assert provenance["source_task_id"] == "P325A_D5_EQUAL_BUDGET_BASELINE_ANALYSIS_READ_ONLY"
    assert provenance["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert provenance["source_repo_head"] == "fce02f0dc271274f7cffc54de527f0262e4f4830"
    assert provenance["copy_mode"] == "byte-for-byte unchanged static files"
    assert provenance["inferential_status"] == "DESCRIPTIVE_ONLY"
    assert provenance["power_lotto_scoring"] == "NOT RUN"

    by_path = {item["path"]: item for item in provenance["artifacts"]}
    for name, expected in EXPECTED_HASHES.items():
        assert by_path[name]["source_sha256"] == expected
        assert by_path[name]["copied_sha256"] == expected


def test_baseline_summary_numbers_match_independent_recompute_from_source_csv():
    rows = _metrics()
    summary = _summary()

    assert len(rows) == 2418
    assert summary["n_metric_rows"] == 2418

    # Mean matched-budget deltas.
    for k, col in (
        ("hit_at_least_1", "descriptive_delta_vs_baseline_hit_at_least_1"),
        ("hit_at_least_2", "descriptive_delta_vs_baseline_hit_at_least_2"),
        ("hit_at_least_3", "descriptive_delta_vs_baseline_hit_at_least_3"),
    ):
        expected = round(sum(float(r[col]) for r in rows) / len(rows), 4)
        assert summary["mean_matched_budget_delta"][k] == expected

    # Positive-delta row counts.
    assert summary["positive_delta_rows"]["hit_at_least_2"] == sum(
        1 for r in rows if float(r["descriptive_delta_vs_baseline_hit_at_least_2"]) > 0
    )

    # Bonferroni screen and non-independent carrier concentration.
    alpha = 0.05 / (len(rows) * 2)
    passing = [
        r for r in rows
        if float(r["binom_p_hit_at_least_2_one_sided"]) < alpha
        or float(r["binom_p_hit_at_least_3_one_sided"]) < alpha
    ]
    carrier = [r for r in passing if CARRIER in r["strategy_ids"].split("|")]
    big = [r for r in passing if r["lottery_type"] == "BIG_LOTTO"]
    screen = summary["inferential_screen"]

    assert screen["n_tests"] == len(rows) * 2 == 4836
    assert screen["rows_passing"] == len(passing) == 41
    assert screen["by_lottery"] == dict(sorted(collections.Counter(r["lottery_type"] for r in passing).items()))
    assert screen["by_window"] == dict(sorted(collections.Counter(r["window"] for r in passing).items()))
    assert screen["by_combination_size"] == dict(
        sorted(collections.Counter(r["combination_size"] for r in passing).items())
    )
    # The corrected count is 34/41 (re-derived from source), NOT 37.
    assert screen["signal_carrier_rows"] == len(carrier) == 34
    assert screen["signal_carrier_of_passing"] == 41
    assert screen["non_carrier_passing"] == len(passing) - len(carrier) == 7
    assert screen["passing_via_k3"] == 0
    assert summary["big_lotto_summary"]["rows_passing_screen"] == len(big) == 0

    # Same-budget cross-size decisive example.
    def same_budget(size: str) -> float:
        vals = [
            float(r["hit_at_least_2_rate"]) for r in rows
            if r["lottery_type"] == "DAILY_539"
            and r["window"] == "recent_50"
            and r["ticket_budget_m"] == "5"
            and r["combination_size"] == size
        ]
        return sum(vals) / len(vals)

    assert summary["same_budget_example"]["single_rate"] == round(same_budget("1"), 3) == 0.7
    assert summary["same_budget_example"]["triple_rate"] == round(same_budget("3"), 3) == 0.498


def test_ui_surfaces_budget_bias_section_with_required_caveats():
    html = INDEX_HTML.read_text(encoding="utf-8")
    module = D5_JS.read_text(encoding="utf-8")
    d5_region = html.split("<!-- ===== P300A D5 Strategy Hit-Rate Matrix MVP", 1)[1].split(
        "<!-- ===== END P300A D5 ===== -->", 1
    )[0]

    for expected in [
        'data-baseline-artifact-root="public/demo-data/lottery-d5/p325a"',
        'class="d5-baseline-panel"',
        "Budget Bias Check",
        "Equal-Budget Baseline",
        "DESCRIPTIVE_ONLY",
        "matched-budget random baseline: computed",
        "raw per-draw equal-budget subsampling: insufficient raw data",
        # Required statement: raw gains are ticket-budget affected.
        "Raw combination hit-rate gains mostly reflect more tickets. At equal ticket budget, "
        "larger combinations do not show a clear advantage.",
        # Required non-claim statement.
        "not a prediction, not a betting recommendation, and it does not recommend any numbers to play",
    ]:
        assert expected in d5_region, expected

    # JS wiring: fetches the derived payload and renders the section.
    for expected in [
        "BASELINE_DATA_FILE",
        "baseline_summary.json",
        "renderBaselineBudgetBias",
        "baselineArtifactRoot",
        "single-strategy signal carrier",
    ]:
        assert expected in module, expected

    # Neutral wording only: f4cold is never called the "best" strategy.
    combined = (d5_region + "\n" + module).lower()
    assert "best strategy" not in combined
    assert "betting pick" not in combined
    assert "recommended numbers" not in combined
    assert "sqlite3" not in module


def test_generator_is_present_and_referenced():
    assert BUILD_SCRIPT.exists()
    provenance = json.loads((BASELINE_ROOT / "source_provenance.json").read_text(encoding="utf-8"))
    derived = {item["path"] for item in provenance["derived_files"]}
    assert "baseline_summary.json" in derived


def test_task_does_not_create_forbidden_db_path():
    assert not DB_PATH.exists()
