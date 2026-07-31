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
        "Demo review presets",
        "Shortcut filters for reviewing copied static artifact rows only.",
        "Review BIG_LOTTO triple rows",
        "Review DAILY_539 ACB rows",
        "Show POWER_LOTTO exclusion",
        "Reset review filters",
        "Demo URL Launcher",
        "Verified review/demo shortcuts for opening copied static artifact states directly.",
        "Default walkthrough review",
        "BIG_LOTTO triple review",
        "DAILY_539 ACB review",
        "POWER_LOTTO exclusion review",
        "Compare restore review",
        "Demo state review link",
        "Copy review link",
        "Review link mirrors the current demo state.",
        "Clipboard fallback: copy the visible demo state link text if browser copy is unavailable.",
        "No preset applied.",
        "Review-only demo constraints",
        "No future prediction.",
        "Baselines/deltas not computed.",
        "Search strategy_id",
        "All top_k",
        "Strategy detail",
        "Click a matrix or coverage row to review artifact-backed historical metrics.",
        "Selected strategy comparison",
        "Compare selected strategies",
        "Select 2-4 strategies from the matrix, coverage, or detail drawer",
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
        "d5-detail-add-compare",
        "d5-compare-panel",
        "d5-compare-title",
        "d5-compare-count",
        "d5-compare-status",
        "d5-compare-grid",
        "d5-preset-status",
        "d5-copy-review-link",
        "d5-review-link-status",
        "d5-review-link-output",
    ]:
        assert f'id="{element_id}"' in region

    for expected in [
        "REVIEW_PRESETS",
        "applyReviewPreset",
        "wireReviewPresets",
        "activateTab",
        "clearMatrixSecondaryFilters",
        "data-d5-preset",
        "biglotto-triple",
        "daily539-acb",
        "powerlotto-exclusion",
        "Review filters reset.",
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
        "wireComparePanel",
        "renderComparePanel",
        "addCompareStrategy",
        "removeCompareStrategy",
        "wireReviewLink",
        "copyReviewLink",
        "restoreDemoStateFromUrl",
    ]:
        assert expected in module


def test_demo_review_presets_are_static_filter_shortcuts():
    region = _d5_region()
    module = D5_JS.read_text(encoding="utf-8")
    css = D5_CSS.read_text(encoding="utf-8")

    for expected in [
        'data-d5-preset="biglotto-triple"',
        'data-d5-preset="daily539-acb"',
        'data-d5-preset="powerlotto-exclusion"',
        'data-d5-preset="reset"',
        "Review BIG_LOTTO triple rows",
        "Review DAILY_539 ACB rows",
        "Show POWER_LOTTO exclusion",
        "Reset review filters",
    ]:
        assert expected in region

    for expected in [
        "matrixLottery: 'BIG_LOTTO'",
        "matrixSearch: 'triple'",
        "coverageLottery: 'BIG_LOTTO'",
        "coverageSearch: 'triple'",
        "matrixLottery: 'DAILY_539'",
        "matrixSearch: 'acb'",
        "coverageLottery: 'DAILY_539'",
        "coverageSearch: 'acb'",
        "tab: 'powerlotto'",
        "POWER_LOTTO exclusion note is visible.",
        "setControlValue('d5-matrix-window-filter', '')",
        "setControlValue('d5-matrix-topk-filter', '')",
        "renderMatrix();",
        "renderCoverage();",
        "setText('d5-preset-status', preset.status)",
    ]:
        assert expected in module

    preset_region = re.search(
        r'<section class="d5-presets".*?</section>',
        region,
        re.DOTALL,
    ).group(0)
    forbidden_terms = ["best", "recommend", "prediction", "betting pick"]
    assert all(term not in preset_region.lower() for term in forbidden_terms)
    assert "d5-presets" in css
    assert "d5-preset-button" in css


def test_demo_url_launcher_exposes_verified_review_state_fragments():
    region = _d5_region()
    css = D5_CSS.read_text(encoding="utf-8")

    expected_links = {
        "Default walkthrough review": "#d5-review?v=1&amp;tab=matrix",
        "BIG_LOTTO triple review": "#d5-review?v=1&amp;tab=matrix&amp;ml=BIG_LOTTO&amp;ms=triple&amp;cl=BIG_LOTTO&amp;cs=triple",
        "DAILY_539 ACB review": "#d5-review?v=1&amp;tab=matrix&amp;ml=DAILY_539&amp;ms=acb&amp;cl=DAILY_539&amp;cs=acb",
        "POWER_LOTTO exclusion review": "#d5-review?v=1&amp;tab=powerlotto",
        "Compare restore review": "#d5-review?v=1&amp;tab=matrix&amp;cmp=BIG_LOTTO%3A%3Abet2_fourier_expansion_biglotto&amp;cmp=BIG_LOTTO%3A%3Abiglotto_deviation_2bet",
    }

    launcher = re.search(
        r'<div class="d5-demo-launcher".*?</div>\s*</div>',
        region,
        re.DOTALL,
    )
    assert launcher, "D5 demo URL launcher panel is missing"
    panel = launcher.group(0)

    assert "Demo URL Launcher" in panel
    assert "Verified review/demo shortcuts" in panel
    assert "Static fragments" in panel
    assert len(re.findall(r'class="d5-demo-launcher-link"', panel)) == 5
    for label, href in expected_links.items():
        assert f'href="{href}"' in panel
        assert label in panel

    forbidden_terms = ["best strategy", "recommended strategy", "betting pick"]
    assert all(term not in panel.lower() for term in forbidden_terms)
    assert "d5-demo-launcher" in css
    assert "d5-demo-launcher-link" in css


def test_demo_state_review_links_are_hash_backed_and_readonly():
    region = _d5_region()
    module = D5_JS.read_text(encoding="utf-8")
    css = D5_CSS.read_text(encoding="utf-8")
    combined = region + "\n" + module + "\n" + css

    for expected in [
        "Demo state review link",
        "Copy review link",
        "walkthrough shortcut",
        "current tab, filters, and compare selection",
        "Manual demo state link copy fallback",
        "Clipboard API unavailable; copy the visible demo state link text.",
        "Clipboard copy failed; copy the visible demo state link text.",
        "Review link copied.",
        "Demo state restored from review link.",
        "Review link mirrors the current demo state.",
        "hashchange",
    ]:
        assert expected in combined

    for expected in [
        "REVIEW_STATE_HASH_PREFIX = 'd5-review'",
        "REVIEW_STATE_VERSION = '1'",
        "VALID_TABS",
        "currentDemoState",
        "encodeDemoStateHash",
        "parseDemoStateFromHash",
        "applyDemoState",
        "showD5SectionForReviewLink",
        "restoreDemoStateFromUrl",
        "buildDemoStateLink",
        "updateReviewLinkOutput",
        "copyReviewLink",
        "sanitizeCompareKeys",
        "setSelectValue",
        "URLSearchParams",
        "params.set('tab'",
        "['ml', demoState.matrixLottery]",
        "['mw', demoState.matrixWindow]",
        "['mt', demoState.matrixTopK]",
        "['ms', normalizeReviewSearch(demoState.matrixSearch)]",
        "['cl', demoState.coverageLottery]",
        "['cs', normalizeReviewSearch(demoState.coverageSearch)]",
        "params.append('cmp'",
        "button.dataset.section === 'lottery-d5'",
        "section.id === 'lottery-d5-section'",
        "url.hash = encodeDemoStateHash();",
        "navigator.clipboard?.writeText",
    ]:
        assert expected in module

    assert "#${REVIEW_STATE_HASH_PREFIX}?" in module
    assert "d5-share-link" in css
    assert "d5-share-link-output" in css
    assert "method: 'POST'" not in module
    assert 'method: "POST"' not in module
    assert "sqlite3" not in module
    assert "best strategy" not in combined.lower()
    assert "recommended strategy" not in combined.lower()
    assert "betting pick" not in combined.lower()


def test_demo_walkthrough_panel_is_review_only_checklist():
    region = _d5_region()
    css = D5_CSS.read_text(encoding="utf-8")
    walkthrough = re.search(
        r'<details class="d5-walkthrough" open>.*?</details>',
        region,
        re.DOTALL,
    )
    assert walkthrough, "D5 demo walkthrough panel is missing"
    panel = walkthrough.group(0)

    for expected in [
        "Demo walkthrough / reviewer checklist",
        "Open D5 and confirm the no-claims banner is visible.",
        "Click Review BIG_LOTTO triple rows.",
        "Click Review DAILY_539 ACB rows.",
        "Click Show POWER_LOTTO exclusion.",
        "Click Reset review filters.",
        "Open and close one strategy detail.",
        "Select two strategies for compare and verify the snapshot fallback.",
        "Retrospective-only.",
        "No future prediction.",
        "No betting recommendation.",
        "No production readiness.",
    ]:
        assert expected in panel

    assert len(re.findall(r"<li>", panel)) == 7
    assert "d5-walkthrough" in css
    assert "d5-walkthrough-limits" in css

    normalized = panel.lower()
    for allowed_negation in [
        "no future prediction.",
        "no betting recommendation.",
        "no production readiness.",
    ]:
        normalized = normalized.replace(allowed_negation, "")
    for forbidden in [
        "best strategy",
        "recommendation",
        "prediction",
        "betting pick",
        "production optimizer",
        "production-ready",
    ]:
        assert forbidden not in normalized


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


def test_selected_strategy_compare_panel_is_readonly_and_non_ranking():
    region = _d5_region()
    module = D5_JS.read_text(encoding="utf-8")
    css = D5_CSS.read_text(encoding="utf-8")
    combined = region + "\n" + module + "\n" + css

    for expected in [
        "Compare selected strategies",
        "Selected strategies side-by-side",
        "Select at least 2 strategies to compare.",
        "Compare selection is full at 4 strategies.",
        "Selected strategies are shown side-by-side for retrospective review only.",
        "No strategies selected yet.",
        "row count",
        "distinct window segments",
        "distinct top_k values",
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
        "Not computed",
        "Comparison snapshot",
        "Copy comparison snapshot",
        "Manual comparison snapshot copy fallback",
        "Clipboard API unavailable",
        "generated_at",
        "source_label",
        "P299A static artifact-backed D5 demo",
        "selected_strategy_count",
        "No-claims caveats",
    ]:
        assert expected in combined

    for expected in [
        "data-compare-key",
        "data-remove-compare-key",
        "data-detail-key",
        "d5-compare-toggle",
        "d5-compare-remove",
        "d5-compare-card",
        "d5-compare-snapshot",
        "d5-compare-snapshot-output",
        "buildCompareSnapshot",
        "copyCompareSnapshot",
        "COMPARE_LIMIT = 4",
        "activeDetailKey",
    ]:
        assert expected in module + "\n" + css

    for expected in [
        "Retrospective-only.",
        "No future prediction.",
        "No betting recommendation.",
        "No production readiness.",
        "Baselines/deltas not computed.",
        "POWER_LOTTO full scoring excluded.",
    ]:
        assert expected in region

    assert "best strategy" not in combined.lower()
    assert "recommended strategy" not in combined.lower()
    assert "betting pick" not in combined.lower()
    assert "No betting recommendation." in module


def test_detail_key_parsing_preserves_strategy_ids_with_delimiter():
    module = D5_JS.read_text(encoding="utf-8")

    assert "function parseDetailKey(key)" in module
    assert "const delimiterIndex = value.indexOf('::');" in module
    assert "value.slice(0, delimiterIndex)" in module
    assert "value.slice(delimiterIndex + 2)" in module

    for caller in [
        "selectedSummaries",
        "renderComparePanel",
        "isKnownStrategyKey",
        "openDetailFromEvent",
    ]:
        assert caller in module

    assert "parseDetailKey(key)" in module
    assert "parseDetailKey(row.dataset.detailKey)" in module
    assert ".split('::')" not in module


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
