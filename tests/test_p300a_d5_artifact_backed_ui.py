"""P300A D5 artifact-backed read-only UI smoke tests.

No DB access, no migrations, no strategy promotion, no predictions.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
D5_JS = REPO_ROOT / "src" / "apps" / "lottery-d5" / "lottery-d5.js"
D5_CSS = REPO_ROOT / "src" / "apps" / "lottery-d5" / "lottery-d5.css"
ARTIFACT_ROOT = REPO_ROOT / "public" / "demo-data" / "lottery-d5" / "p299a"

EXPECTED_HASHES = {
    "manifest.json": "691403d589e7d9ddb507fcaff6ef0e2787875ceb314bcd0f223e59b1a718cb67",
    "d5_hit_rate_matrix.csv": "046b7284ccc858f3f3368b4f05f31b6eee2853f27932a209e6e62d641367b66a",
    "strategy_coverage_summary.csv": "46a29f0b75f707ac4d862b60fc5b1e77acd999c305f831563fdfb045fa13f41b",
    "optimizer_input_contract.json": "7cabf347a60df0972c090b0a69b5ddfbd38979cb243c409053176aa3192d8b0b",
    "powerlotto_exclusion_note.md": "19e17e7be5dd2505dbce77a7ac5170763f0e70da0f422b94707cd96407b48385",
}

REQUIRED_MATRIX_COLUMNS = {
    "lottery",
    "strategy_id",
    "window_segment",
    "top_k",
    "sample_size_draws",
    "sample_size_rows",
    "m1_rate",
    "m2_rate",
    "m3_rate",
    "m3plus_hit_rate",
    "baseline_mode",
    "baseline_value",
    "delta",
    "delta_pp",
    "inferential_status",
    "readiness_status",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(name: str) -> list[dict[str, str]]:
    with (ARTIFACT_ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _d5_region() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- ===== P300A D5 Strategy Hit-Rate Matrix MVP.*?<!-- ===== END P300A D5 ===== -->",
        html,
        re.DOTALL,
    )
    assert match, "P300A D5 section is missing from index.html"
    return match.group(0)


def test_static_artifact_hashes_match_verified_p299a_inputs():
    for filename, expected in EXPECTED_HASHES.items():
        artifact = ARTIFACT_ROOT / filename
        assert artifact.exists(), f"Missing copied P299A artifact: {artifact}"
        assert _sha256(artifact) == expected


def test_index_integration_markers_exist():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-section="lottery-d5"' in html
    assert 'id="lottery-d5-section"' in html
    assert 'src/apps/lottery-d5/lottery-d5.css' in html
    assert 'src/apps/lottery-d5/lottery-d5.js' in html


def test_required_visible_summary_and_sections_exist():
    region = _d5_region()
    for text in [
        "D5 Strategy Hit-Rate Matrix MVP",
        "Matrix rows",
        "BIG_LOTTO rows",
        "DAILY_539 rows",
        "Strategies total",
        "Baseline status",
        "not computed",
        "POWER_LOTTO",
        "excluded / blocked",
        "Matrix table",
        "Strategy coverage",
        "Optimizer input contract",
        "POWER_LOTTO exclusion",
        "Limitations / non-claims",
        "Review-only demo constraints",
        "No future prediction.",
        "Baselines/deltas not computed.",
        "Search strategy_id",
        "All top_k",
        "Strategy detail",
        "Click a matrix or coverage row to review artifact-backed historical metrics.",
        "Showing 130 of 130 rows",
        "Showing 29 of 29 rows",
    ]:
        assert text in region


def test_review_filters_and_counts_are_wired():
    region = _d5_region()
    module = D5_JS.read_text(encoding="utf-8")

    for element_id in [
        "d5-matrix-lottery-filter",
        "d5-matrix-window-filter",
        "d5-matrix-topk-filter",
        "d5-matrix-strategy-search",
        "d5-matrix-row-count",
        "d5-coverage-lottery-filter",
        "d5-coverage-strategy-search",
        "d5-coverage-row-count",
        "d5-strategy-detail-drawer",
        "d5-detail-title",
        "d5-detail-body",
        "d5-detail-close",
    ]:
        assert f'id="{element_id}"' in region

    for expected in [
        "populateTopKFilter",
        "strategyMatches",
        "rowCountLabel",
        "d5-matrix-strategy-search",
        "d5-coverage-strategy-search",
        "No matrix rows match the current filters.",
        "No coverage rows match the current filters.",
        "d5-clickable-row",
        "data-detail-source=\"matrix\"",
        "data-detail-source=\"coverage\"",
        "wireDetailDrawer",
        "renderStrategyDetail",
    ]:
        assert expected in module


def test_strategy_detail_drawer_is_readonly_and_artifact_backed():
    region = _d5_region()
    module = D5_JS.read_text(encoding="utf-8")
    css = D5_CSS.read_text(encoding="utf-8")

    for expected in [
        "Selected strategy summary",
        "Total rows available",
        "Distinct window segments",
        "Distinct top_k values",
        "sample_size_draws summary",
        "sample_size_rows summary",
        "m1_rate summary",
        "m2_rate summary",
        "m3_rate summary",
        "m3plus_hit_rate summary",
        "baseline_mode status",
        "baseline_value status",
        "delta status",
        "delta_pp status",
        "inferential_status",
        "readiness_status",
        "eligibility_status",
        "exclusion_reason",
        "Historical windows/top_k rows",
        "Not computed",
        "No matrix rows are available for this strategy in the copied artifact.",
    ]:
        assert expected in module

    for expected in [
        "Retrospective-only.",
        "No future prediction.",
        "No betting recommendation.",
        "No production readiness.",
        "Baselines/deltas not computed.",
        "POWER_LOTTO full scoring excluded.",
    ]:
        assert expected in region

    for expected in [
        "role=\"button\"",
        "tabindex=\"0\"",
        "aria-label=\"Open strategy detail",
        "d5-detail-drawer",
        "d5-detail-caveats",
        "d5-detail-table",
    ]:
        assert expected in module + "\n" + css


def test_matrix_artifact_counts_columns_and_null_baselines():
    rows = _read_csv("d5_hit_rate_matrix.csv")
    assert len(rows) == 130
    assert sum(1 for row in rows if row["lottery"] == "BIG_LOTTO") == 55
    assert sum(1 for row in rows if row["lottery"] == "DAILY_539") == 75
    assert {row["lottery"] for row in rows} == {"BIG_LOTTO", "DAILY_539"}
    assert REQUIRED_MATRIX_COLUMNS.issubset(rows[0].keys())
    assert all(row["baseline_mode"] == "not_computed" for row in rows)
    assert all(row["baseline_value"] == "NULL" for row in rows)
    assert all(row["delta"] == "NULL" for row in rows)
    assert all(row["delta_pp"] == "NULL" for row in rows)


def test_coverage_artifact_counts():
    rows = _read_csv("strategy_coverage_summary.csv")
    assert len(rows) == 29
    assert sum(1 for row in rows if row["lottery"] == "BIG_LOTTO") == 13
    assert sum(1 for row in rows if row["lottery"] == "DAILY_539") == 16
    assert sum(1 for row in rows if row["readiness"] == "NOT_READY") == 3


def test_optimizer_contract_gates_are_visible_and_readonly():
    contract = json.loads((ARTIFACT_ROOT / "optimizer_input_contract.json").read_text(encoding="utf-8"))
    gates = "\n".join(contract["readiness_gates"])
    assert "NULL or NOT_READY as edge" in gates
    assert "sample_size_draws" in gates
    assert "window_segment" in gates
    assert "baseline_mode" in gates
    assert "POWER_LOTTO full prize-aware" in gates

    module = D5_JS.read_text(encoding="utf-8")
    assert "readiness_gates" in module
    assert "fetch(" in module
    for forbidden in ["sqlite3", "DatabaseManager", "method: 'POST'", 'method: "POST"', "method: 'PUT'", 'method: "PUT"', "method: 'DELETE'", 'method: "DELETE"']:
        assert forbidden not in module


def test_powerlotto_exclusion_and_non_claims():
    note = (ARTIFACT_ROOT / "powerlotto_exclusion_note.md").read_text(encoding="utf-8")
    region = _d5_region()
    module_text = D5_JS.read_text(encoding="utf-8") + "\n" + D5_CSS.read_text(encoding="utf-8")

    assert "no POWER_LOTTO canonical DB view/source contract" in note
    assert "predicted_special IS NULL" in note
    assert "9000" in note
    assert "is not full POWER_LOTTO readiness" in region
    assert "No future prediction ability claimed." in region
    assert "No betting recommendation." in region
    assert "not a production optimizer" in region
    assert "best strategy" not in (region + module_text).lower()
