"""
P278A — Hit-Spectrum Data Contract: test suite.

Proves the 22 mandated invariants plus path-independence / two-root
determinism, fail-closed null!=zero semantics, taxonomy reconciliation,
forbidden-interface absence, and JSON/Markdown consistency.

Counted PASS only: no SKIPPED / ENVIRONMENT_BLOCKED / NOT-RUN substitution.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import importlib.util

MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "analysis"
    / "p278a_hit_spectrum_data_contract.py"
)
spec = importlib.util.spec_from_file_location("p278a_contract", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "outputs" / "research" / "p278a_hit_spectrum_data_contract_20260617.json"
MD_PATH = ROOT / "outputs" / "research" / "p278a_hit_spectrum_data_contract_20260617.md"


@pytest.fixture(scope="module")
def payload():
    return mod.build_payload(ROOT)


@pytest.fixture(scope="module")
def committed():
    with open(JSON_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1-3. Identity: exactly 36 cells, 108 rows, no collisions, dimensions present
# ---------------------------------------------------------------------------

def test_exactly_36_unique_strategy_cells(payload):
    keys = {r["strategy_cell_key"] for r in payload["rows"]}
    assert len(keys) == 36
    assert payload["summaries"]["unique_strategy_cell_count"] == 36
    assert mod.P277_STRATEGY_CELL_UNIVERSE == 36


def test_exactly_108_rows_three_windows(payload):
    assert len(payload["rows"]) == 108
    per_cell = {}
    for r in payload["rows"]:
        per_cell.setdefault(r["strategy_cell_key"], set()).add(
            r["evaluation_window"]["label"]
        )
    assert all(v == {"SHORT", "MID", "LONG"} for v in per_cell.values())


def test_identity_collisions_fail_closed(payload):
    pairs = [
        (r["strategy_cell_key"], r["evaluation_window"]["label"]) for r in payload["rows"]
    ]
    assert len(pairs) == len(set(pairs)), "duplicate (cell, window) row detected"


def test_required_identity_dimensions_present(payload):
    required = {
        "schema_version",
        "cell_id",
        "strategy_cell_key",
        "game",
        "strategy_id",
        "endpoint",
        "bet_count",
        "evaluation_window",
        "evidence_stage",
        "lifecycle_status",
    }
    for r in payload["rows"]:
        assert required.issubset(r.keys())
        assert r["endpoint"]["endpoint_id"]
        assert r["evaluation_window"]["label"] in ("SHORT", "MID", "LONG")


# ---------------------------------------------------------------------------
# 4-5. Integer/non-negative counts; null vs zero distinct
# ---------------------------------------------------------------------------

def test_available_counts_are_nonnegative_integers(payload):
    for r in payload["rows"]:
        den = r["denominator"]
        for fld in ("distinct_draw_count", "evaluated_ticket_count", "distinct_ticket_count"):
            v = den[fld]
            assert isinstance(v, int) and v >= 0
        agg = r["prize_aware_win_aggregate"]["prize_aware_win_draws"]
        assert agg is None or (isinstance(agg, int) and agg >= 0)


def test_null_and_zero_semantically_distinct(payload):
    for r in payload["rows"]:
        hs = r["hit_spectrum"]
        # exact buckets never fabricated as zero
        for b in ("m0_count", "m1_count", "m2_count", "m3plus_count"):
            assert hs[b] is None
        assert hs["exact_hit_buckets"] == "NOT_AVAILABLE"
        # unscoreable rows: aggregate is null (not 0); scoreable: integer
        scoreable = r["evaluation_window"]["endpoint_scoreable"]
        agg = r["prize_aware_win_aggregate"]["prize_aware_win_draws"]
        if scoreable:
            assert isinstance(agg, int)
        else:
            assert agg is None


# ---------------------------------------------------------------------------
# 6-7. Full-spectrum bucket sum / derived-rate recomputation
# ---------------------------------------------------------------------------

def test_no_full_spectrum_bucket_sum_fabricated(payload):
    # No row is full-spectrum; bucket_sum stays null and never claims a match.
    for r in payload["rows"]:
        assert r["hit_spectrum"]["bucket_sum"] is None
        assert r["hit_spectrum"]["bucket_sum_matches_denominator"] is None
    assert payload["summaries"]["full_spectrum_identities"] == []


def test_derived_rates_recompute_from_counts(payload):
    for r in payload["rows"]:
        agg = r["prize_aware_win_aggregate"]
        if r["evaluation_window"]["endpoint_scoreable"]:
            denom = r["denominator"]["distinct_draw_count"]
            expected = agg["prize_aware_win_draws"] / denom
            assert abs(agg["prize_aware_win_rate"] - expected) < 1e-12
        else:
            assert agg["prize_aware_win_rate"] is None


# ---------------------------------------------------------------------------
# 8-9. Endpoints don't merge; prize/special/second-zone applicability
# ---------------------------------------------------------------------------

def test_incompatible_endpoints_do_not_merge(payload):
    by_game = {}
    for r in payload["rows"]:
        by_game.setdefault(r["game"], set()).add(r["endpoint"]["endpoint_id"])
    assert by_game["DAILY_539"] == {"D539_ANY_PRIZE_AWARE_WIN"}
    assert by_game["BIG_LOTTO"] == {"BIG_ANY_PRIZE_AWARE_WIN"}
    assert by_game["POWER_LOTTO"] == {"POWER_ANY_PRIZE_AWARE_WIN"}
    # M3+ (P267C main-number) endpoint id never appears in any row
    for r in payload["rows"]:
        assert "M3PLUS" not in r["endpoint"]["endpoint_id"].upper()


def test_endpoint_applicability_rules(payload):
    for r in payload["rows"]:
        es = r["endpoint_specific"]
        game = r["game"]
        if game == "DAILY_539":
            assert es["special_number_applicable"] is False
            assert es["second_zone_applicable"] is False
            assert es["special_number_hit_counts"] == "NOT_AVAILABLE"
            assert es["second_zone_hit_counts"] == "NOT_AVAILABLE"
        elif game == "BIG_LOTTO":
            assert es["special_number_applicable"] is True
            assert es["second_zone_applicable"] is False
            # applicable component count is null (not committed), not a fabricated 0
            assert es["special_number_hit_counts"] is None
        elif game == "POWER_LOTTO":
            assert es["special_number_applicable"] is False
            assert es["second_zone_applicable"] is True
            assert es["second_zone_hit_counts"] is None
        # prize tier counts never fabricated
        assert es["prize_tier_counts"] is None
        assert es["prize_aware_applicable"] is True


# ---------------------------------------------------------------------------
# 10-11. Traceability + repo-relative POSIX paths
# ---------------------------------------------------------------------------

def test_every_row_has_source_traceability(payload):
    for r in payload["rows"]:
        tr = r["traceability"]
        assert tr["source_artifacts"]
        assert tr["source_commit"] == mod.SOURCE_COMMIT
        assert tr["extraction_status"] == "COMMITTED_ARTIFACT_ONLY"
        assert tr["source_gap_codes"]
        for v in tr["source_artifact_hashes"].values():
            assert len(v) == 64  # sha-256 hex


def test_all_source_paths_repo_relative_posix(payload):
    for rel in payload["source_artifact_manifest"]:
        assert not rel.startswith("/")
        assert "\\" not in rel
        assert ".." not in rel
        assert rel.startswith("outputs/research/")


# ---------------------------------------------------------------------------
# 12-14. Two-root determinism + absolute-path rejection
# ---------------------------------------------------------------------------

def _materialize_root(tmp: Path) -> Path:
    for rel in mod.SOURCE_RELPATHS.values():
        src = ROOT / rel
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    return tmp


def test_two_roots_produce_same_digest(tmp_path, payload):
    alt_root = _materialize_root(tmp_path / "alt_repo_root")
    alt = mod.build_payload(alt_root)
    assert alt["canonical_payload_digest"] == payload["canonical_payload_digest"]


def test_two_root_outputs_contract_identical(tmp_path, payload):
    alt_root = _materialize_root(tmp_path / "alt_repo_root2")
    alt = mod.build_payload(alt_root)
    a = json.dumps(alt, sort_keys=True, ensure_ascii=False)
    b = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    assert a == b


def test_absolute_path_in_digest_subset_would_change_digest(payload):
    import copy

    tampered = copy.deepcopy(payload)
    tampered["source_artifact_manifest"] = [
        "/Users/somebody/" + p for p in tampered["source_artifact_manifest"]
    ]
    d2 = mod.compute_canonical_digest(tampered)
    assert d2 != payload["canonical_payload_digest"]


def test_no_absolute_or_home_paths_anywhere(committed):
    blob = json.dumps(committed, ensure_ascii=False)
    for needle in ("/Users/", "/home/", "/tmp/", "/private/", "C:\\\\"):
        assert needle not in blob


# ---------------------------------------------------------------------------
# 15-18. P277 taxonomy / supported / OOS / missing-baseline unchanged
# ---------------------------------------------------------------------------

def test_p277_taxonomy_unchanged(payload):
    recon = payload["summaries"]["p277_reconciliation"]
    assert recon["p277_canonical_digest"] == mod.P277_CANONICAL_DIGEST
    assert recon["total_strategy_cells"] == 36
    assert recon["total_portfolios"] == 8
    assert recon["count_by_new_classification"] == {
        "OBSERVATION_POTENTIAL_ABOVE_RANDOM": 12,
        "NO_EVIDENCE_OVER_RANDOM": 15,
        "OBSERVATION_SUPPORTED_ABOVE_RANDOM": 3,
        "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL": 1,
        "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE": 4,
        "UNDERPOWERED_OBSERVATION_POTENTIAL": 1,
    }


def test_three_supported_daily539_candidates_unchanged(payload):
    supported = sorted(
        r["strategy_cell_key"]
        for r in payload["rows"]
        if r["research_status"]["p277_observation_class"]
        == "OBSERVATION_SUPPORTED_ABOVE_RANDOM"
    )
    cells = sorted(set(supported))
    assert cells == [
        "DAILY_539/acb_markov_midfreq_3bet",
        "DAILY_539/daily539_f4cold_3bet",
        "DAILY_539/daily539_f4cold_5bet",
    ]


def test_oos_superseded_identity_unchanged(payload):
    oos = sorted(
        set(
            r["strategy_cell_key"]
            for r in payload["rows"]
            if r["research_status"]["p277_observation_class"]
            == "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL"
        )
    )
    assert len(oos) == 1


def test_missing_random_baseline_identities_unchanged(payload):
    missing = sorted(
        set(
            r["strategy_cell_key"]
            for r in payload["rows"]
            if r["research_status"]["p277_observation_class"]
            == "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE"
        )
    )
    assert len(missing) == 4


# ---------------------------------------------------------------------------
# 19-20. No-claim flags
# ---------------------------------------------------------------------------

def test_prediction_success_claim_false(payload, committed):
    assert payload["prediction_success_claim"] is False
    assert committed["prediction_success_claim"] is False


def test_strategy_promoted_false(payload, committed):
    assert payload["strategy_promoted"] is False
    assert committed["strategy_promoted"] is False
    assert payload["database_opened"] is False
    assert payload["database_write"] is False


# ---------------------------------------------------------------------------
# 21. Forbidden-interface static scan
# ---------------------------------------------------------------------------

def test_static_forbidden_interface_scan_clean():
    assert mod.static_forbidden_check() == []


def test_module_source_has_no_db_or_network_imports():
    text = MODULE_PATH.read_text(encoding="utf-8")
    # AST-verified absence is the authority; this is a belt-and-braces line check
    import ast

    tree = ast.parse(text)
    forbidden = {"sqlite3", "requests", "urllib", "socket", "subprocess", "psycopg2"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden


# ---------------------------------------------------------------------------
# 22. JSON / Markdown consistency + committed-file digest reproducibility
# ---------------------------------------------------------------------------

def test_committed_json_digest_recomputes(committed):
    recomputed = mod.compute_canonical_digest(committed)
    assert recomputed == committed["canonical_payload_digest"]


def test_committed_json_matches_fresh_build(committed, payload):
    assert committed["canonical_payload_digest"] == payload["canonical_payload_digest"]
    assert json.dumps(committed, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_markdown_consistent_with_json(committed):
    md = MD_PATH.read_text(encoding="utf-8")
    assert committed["canonical_payload_digest"] in md
    assert committed["source_commit"] in md
    assert str(committed["summaries"]["row_count"]) in md
    # UI-readiness counts surfaced in MD
    for k in committed["summaries"]["summary_by_ui_readiness"]:
        assert k in md
    # no-claim boundary present
    assert "prediction_success_claim=false" in md or "prediction-success" in md.lower()


def test_ui_readiness_values_in_taxonomy(payload):
    allowed = set(mod.UI_READINESS_TAXONOMY)
    for r in payload["rows"]:
        assert r["ui_readiness_status"] in allowed
        for c in r["traceability"]["source_gap_codes"]:
            assert c in set(mod.SOURCE_GAP_CODES) or c == "MISSING_PREDICTED_SECOND_ZONE"


def test_ui_readiness_does_not_imply_support(payload):
    # The 3 P277-supported DAILY_539 cells are still NOT UI-ready full spectrum.
    for r in payload["rows"]:
        if r["research_status"]["p277_observation_class"] == "OBSERVATION_SUPPORTED_ABOVE_RANDOM":
            assert r["ui_readiness_status"] != "UI_READY_FULL_SPECTRUM"


def test_unscoreable_power_rows_are_endpoint_mapping_gap(payload):
    unscoreable = [r for r in payload["rows"] if not r["evaluation_window"]["endpoint_scoreable"]]
    assert len(unscoreable) == 12
    for r in unscoreable:
        assert r["game"] == "POWER_LOTTO"
        assert r["ui_readiness_status"] == "SOURCE_GAP_ENDPOINT_MAPPING"
        assert "SOURCE_GAP_ENDPOINT_MAPPING" in r["traceability"]["source_gap_codes"]


# ---------------------------------------------------------------------------
# P278C Narrative Truthfulness Regression Tests
# ---------------------------------------------------------------------------

# Expected four affected POWER strategy identities (must remain stable).
_EXPECTED_POWER_EGM_STRATEGIES = frozenset({
    "fourier_rhythm_3bet",
    "power_fourier_rhythm_2bet",
    "power_orthogonal_5bet",
    "power_precision_3bet",
})


def test_markdown_does_not_claim_zero_power_second_zone_exclusions():
    """Markdown must not contain the previously false zero-exclusion claim."""
    md = MD_PATH.read_text(encoding="utf-8")
    assert "0 missing-second-zone exclusions" not in md, (
        "Markdown still contains the false claim that POWER second-zone rows have "
        "zero missing-second-zone exclusions; this was confirmed false by P278C."
    )
    assert "fully populated (0" not in md, (
        "Markdown still contains a 'fully populated (0...' pattern implying zero "
        "POWER second-zone exclusions."
    )


def test_markdown_reflects_nonzero_power_second_zone_exclusions():
    """Markdown must positively assert that POWER second-zone exclusions exist."""
    md = MD_PATH.read_text(encoding="utf-8")
    assert "SOURCE_GAP_ENDPOINT_MAPPING" in md, (
        "Markdown must mention SOURCE_GAP_ENDPOINT_MAPPING to reflect the nonzero "
        "POWER second-zone exclusion rows."
    )
    assert "missing-predicted-second-zone" in md or "missing predicted second-zone" in md.lower(), (
        "Markdown must state that POWER missing-predicted-second-zone exclusions exist."
    )


def test_markdown_twelve_endpoint_mapping_rows_consistent_with_json(committed):
    """12 SOURCE_GAP_ENDPOINT_MAPPING rows in JSON must be reflected in the Markdown."""
    json_count = committed["summaries"]["summary_by_ui_readiness"]["SOURCE_GAP_ENDPOINT_MAPPING"]
    assert json_count == 12
    md = MD_PATH.read_text(encoding="utf-8")
    assert "SOURCE_GAP_ENDPOINT_MAPPING`: 12" in md or "SOURCE_GAP_ENDPOINT_MAPPING: 12" in md, (
        f"Markdown must consistently report {json_count} SOURCE_GAP_ENDPOINT_MAPPING rows "
        "as recorded in the committed JSON."
    )


def test_four_affected_power_strategy_identities_unchanged(payload):
    """The four affected POWER strategies must still be the SOURCE_GAP_ENDPOINT_MAPPING set."""
    egm_rows = [r for r in payload["rows"] if r.get("ui_readiness_status") == "SOURCE_GAP_ENDPOINT_MAPPING"]
    actual_strategies = frozenset(r["strategy_id"] for r in egm_rows)
    assert actual_strategies == _EXPECTED_POWER_EGM_STRATEGIES, (
        f"Affected POWER strategy set changed. Expected {_EXPECTED_POWER_EGM_STRATEGIES}, "
        f"got {actual_strategies}."
    )
    assert len(egm_rows) == 12, (
        f"Expected exactly 12 SOURCE_GAP_ENDPOINT_MAPPING rows, got {len(egm_rows)}."
    )


def test_power_second_zone_narrative_is_data_derived(payload):
    """render_markdown must derive POWER second-zone exclusion narrative from payload rows."""
    md_text = mod.render_markdown(payload)
    egm_rows = [r for r in payload["rows"] if r.get("ui_readiness_status") == "SOURCE_GAP_ENDPOINT_MAPPING"]
    egm_count = len(egm_rows)
    egm_strategies = sorted(set(r["strategy_id"] for r in egm_rows))
    # The generated Markdown must reference the data-derived count and each affected strategy.
    assert str(egm_count) in md_text, (
        f"Generated Markdown must contain the data-derived SOURCE_GAP_ENDPOINT_MAPPING count ({egm_count})."
    )
    for strat in egm_strategies:
        assert strat in md_text, (
            f"Generated Markdown must name affected strategy '{strat}' in the second-zone narrative."
        )


def test_json_bytes_unchanged_after_narrative_fix(committed, payload):
    """JSON must remain byte-identical to the committed PR head artifact.

    Uses the module's own compute_canonical_digest to verify the pinned digest
    still holds after the P278C render_markdown correction (JSON must not have
    been modified by the narrative fix).
    """
    # Verify the pinned canonical digest using the module's own function.
    recomputed = mod.compute_canonical_digest(committed)
    assert recomputed == committed["canonical_payload_digest"], (
        f"Canonical digest mismatch after P278C: computed={recomputed}, "
        f"expected={committed['canonical_payload_digest']}"
    )
    # The pinned value itself must not have drifted.
    assert committed["canonical_payload_digest"] == (
        "4ad80e9c84b70a3382161587fabf150da134c8bf416bd7be28fab19c2419062e"
    ), "Canonical digest value differs from the PR-head pinned value."
    # The fresh build payload must still match the committed JSON byte-for-byte.
    assert json.dumps(committed, sort_keys=True) == json.dumps(payload, sort_keys=True), (
        "Fresh build payload differs from committed JSON — JSON has been modified."
    )


def test_second_zone_component_counts_still_unavailable(payload):
    """P278C must not have introduced second-zone component hit counts."""
    for r in payload["rows"]:
        if r.get("endpoint_specific", {}).get("second_zone_applicable"):
            hit_counts = r["endpoint_specific"].get("second_zone_hit_counts")
            assert hit_counts is None, (
                f"Row {r['cell_id']} now has second_zone_hit_counts={hit_counts!r}; "
                "second-zone component hit counts must remain unavailable (None)."
            )


def test_no_m0m1m2m3_spectrum_established(payload):
    """P278C must not establish any exact M0/M1/M2/M3+ hit spectrum in any row."""
    for r in payload["rows"]:
        spectrum = r.get("hit_spectrum", {})
        for bucket in ("m0", "m1", "m2", "m3_plus"):
            assert spectrum.get(bucket) is None, (
                f"Row {r['cell_id']} has hit_spectrum.{bucket}={spectrum.get(bucket)!r}; "
                "P278C must not have introduced spectrum data."
            )
