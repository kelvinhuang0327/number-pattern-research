"""P541C_R2 — read-only tests for the BIG_LOTTO legacy method review and
replay-readiness selection replacement artifact.

The module pins and strictly parses a single P541B_R2 artifact. Reviewed
source_path values remain identifiers only; source files are not resolved,
opened, statted, hashed, imported or executed. The module never opens a DB
connection and never writes to `outputs/` except through `main()`.
"""
import ast
import copy
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

pytestmark = pytest.mark.filterwarnings("ignore")


def _module():
    from analysis import p541c_r2_biglotto_legacy_method_review_readiness_selection as mod

    return mod


# ── contract: static-only, no DB, no import/execution of reviewed scripts ──


def test_module_never_imports_sqlite3():
    mod = _module()
    src = inspect.getsource(mod)
    assert "import sqlite3" not in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "sqlite3" for alias in node.names)


def test_module_never_uses_importlib_or_exec_on_targets():
    mod = _module()
    src = inspect.getsource(mod)
    assert "importlib" not in src
    assert "__import__(" not in src
    assert "\nexec(" not in src and " exec(" not in src


def test_module_has_no_per_record_source_io_contract():
    mod = _module()
    classify_src = inspect.getsource(mod.classify_record)
    classify_all_src = inspect.getsource(mod.classify_all)
    for forbidden in ("resolve(", "stat(", "is_file(", "open(", "file_sha256"):
        assert forbidden not in classify_src
        assert forbidden not in classify_all_src
    assert not hasattr(mod, "source_file_identity")


# ── artifact input ──────────────────────────────────────────────────────


def test_p541b_r2_artifact_exists():
    mod = _module()
    assert mod.P541B_R2_JSON.exists()


@pytest.fixture(scope="module")
def verified_input():
    mod = _module()
    return mod.load_verified_input()


@pytest.fixture(scope="module")
def p541b_r2(verified_input):
    return verified_input[0]


@pytest.fixture(scope="module")
def input_provenance(verified_input):
    return verified_input[1]


def test_p541b_r2_has_580_records(p541b_r2):
    assert len(p541b_r2["method_classification_records"]) == 580


def test_input_matches_pinned_identity(input_provenance):
    mod = _module()
    assert input_provenance["byte_size"] == mod.INPUT_IDENTITY["byte_size"]
    assert input_provenance["sha256"] == mod.INPUT_IDENTITY["sha256"]
    assert input_provenance["schema_version"] == "p541b-r2-evidence-v1"
    assert input_provenance["detector_version"] == "p541b-r2-detector-v4"
    assert input_provenance["source_manifest_sha256"] == mod.SOURCE_MANIFEST_SHA256
    assert input_provenance["record_count"] == 580
    assert input_provenance["verification"] == "PASS"


def test_strict_json_rejects_duplicate_keys_and_nonfinite(tmp_path):
    mod = _module()
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"same":1,"same":2}', encoding="utf-8")
    with pytest.raises(mod.P541CR2ValidationError, match="duplicate JSON key"):
        mod.strict_json_load(duplicate)
    for token in ("NaN", "Infinity", "-Infinity"):
        nonfinite = tmp_path / f"nonfinite-{token.replace('-', 'minus')}.json"
        nonfinite.write_text('{"value":' + token + '}', encoding="utf-8")
        with pytest.raises(mod.P541CR2ValidationError, match="non-finite JSON"):
            mod.strict_json_load(nonfinite)


def test_input_hash_mismatch_fails_closed(tmp_path):
    mod = _module()
    path = tmp_path / "input.json"
    path.write_text("{}", encoding="utf-8")
    identity = {"path": "input.json", "byte_size": 2, "sha256": "0" * 64}
    with pytest.raises(mod.P541CR2ValidationError, match="identity mismatch"):
        mod.verify_input_identity(tmp_path, identity)
    with pytest.raises(mod.P541CR2ValidationError, match="unsafe input path"):
        mod.verify_input_identity(tmp_path, {**identity, "path": "../input.json"})


def test_upstream_schema_mismatch_fails_closed(p541b_r2):
    mod = _module()
    wrong_schema = copy.deepcopy(p541b_r2)
    wrong_schema["schema_version"] = "wrong"
    with pytest.raises(mod.P541CR2ValidationError, match="schema_version mismatch"):
        mod.validate_upstream_contract(wrong_schema)

    wrong_manifest = copy.deepcopy(p541b_r2)
    wrong_manifest["provenance"]["source_manifest"]["canonical_sha256"] = "0" * 64
    with pytest.raises(mod.P541CR2ValidationError, match="source manifest sha256 mismatch"):
        mod.validate_upstream_contract(wrong_manifest)

    missing_field = copy.deepcopy(p541b_r2)
    del missing_field["method_classification_records"][0]["safety_classification"]["risk_level"]
    with pytest.raises(mod.P541CR2ValidationError, match="safety_classification contract mismatch"):
        mod.validate_upstream_contract(missing_field)

    bad_risk = copy.deepcopy(p541b_r2)
    bad_risk["method_classification_records"][0]["safety_classification"]["risk_level"] = "extreme"
    with pytest.raises(mod.P541CR2ValidationError, match="unknown risk_level"):
        mod.validate_upstream_contract(bad_risk)

    invariant_break = copy.deepcopy(p541b_r2)
    rec = invariant_break["method_classification_records"][0]
    rec["safety_classification"]["risk_level"] = "low"
    rec["safety_classification"]["low_risk_eligible"] = False
    with pytest.raises(mod.P541CR2ValidationError, match="low_risk_eligible/risk_level invariant"):
        mod.validate_upstream_contract(invariant_break)

    non_boolean_eligibility = copy.deepcopy(p541b_r2)
    rec = non_boolean_eligibility["method_classification_records"][0]
    rec["safety_classification"]["risk_level"] = "medium"
    rec["safety_classification"]["low_risk_eligible"] = "false"
    with pytest.raises(mod.P541CR2ValidationError, match="low_risk_eligible must be boolean"):
        mod.validate_upstream_contract(non_boolean_eligibility)


def test_duplicate_method_id_and_source_path_fail_terminally(p541b_r2):
    mod = _module()
    duplicate_method = copy.deepcopy(p541b_r2)
    duplicate_method["method_classification_records"][1]["method_id"] = (
        duplicate_method["method_classification_records"][0]["method_id"]
    )
    with pytest.raises(mod.P541CR2ValidationError, match="duplicate method_id"):
        mod.validate_upstream_contract(duplicate_method)

    duplicate_source = copy.deepcopy(p541b_r2)
    duplicate_source["method_classification_records"][1]["source_path"] = (
        duplicate_source["method_classification_records"][0]["source_path"]
    )
    with pytest.raises(mod.P541CR2ValidationError, match="duplicate source_path"):
        mod.validate_upstream_contract(duplicate_source)


# ── classify_record: one synthetic record per bucket ────────────────────


def _synthetic_record(
    risk_level,
    low_risk_eligible,
    identity,
    recommended_action="include_in_replay_readiness",
    runnable_status="needs_adapter_wrapper",
    confidence="high",
    source_path="analysis/p541c_r2_biglotto_legacy_method_review_readiness_selection.py",
):
    return {
        "method_id": "synthetic",
        "source_path": source_path,
        "safety_classification": {
            "risk_level": risk_level,
            "low_risk_eligible": low_risk_eligible,
            "disposition": "SYNTHETIC",
            "reasons": [],
        },
        "historical_p541b_classification": {
            "method_family": "synthetic_family",
            "is_actual_prediction_method": identity,
            "recommended_action": recommended_action,
            "runnable_status": runnable_status,
            "confidence": confidence,
            "duplicate_of_existing_strategy": None,
            "why_not_runnable": "",
        },
    }


def test_classify_record_low_risk_confirmed_preserves_adapter_requirement():
    mod = _module()
    rec = _synthetic_record("low", True, True)
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_ADAPTER
    assert d["replay_readiness_priority"] == "high"
    assert d["required_change_before_replay"] == "adapter_wrapper"
    assert d["p541c_decision"] == d["p541c_r2_bucket"]


def test_classify_record_ready_requires_explicit_upstream_ready_status():
    mod = _module()
    rec = _synthetic_record("low", True, True, runnable_status="runnable_with_existing_adapter")
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_READY
    assert d["required_change_before_replay"] == "none"


def test_classify_record_medium_risk_never_becomes_ready():
    mod = _module()
    rec = _synthetic_record(
        "medium", False, True, runnable_status="runnable_with_existing_adapter"
    )
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_CTO_REVIEW
    assert d["required_change_before_replay"] == "safety_review"


def test_classify_record_low_risk_identity_unresolved_needs_cto_review():
    mod = _module()
    rec = _synthetic_record("low", True, "unknown")
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_CTO_REVIEW


def test_classify_record_low_but_not_a_method_is_excluded():
    mod = _module()
    rec = _synthetic_record("low", True, False)
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_EXCLUDED


def test_classify_record_medium_confirmed_preserves_adapter_requirement():
    mod = _module()
    rec = _synthetic_record("medium", False, True)
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_ADAPTER
    assert d["replay_readiness_priority"] == "medium"


def test_classify_record_confirmed_refactor_status_stays_separate():
    mod = _module()
    rec = _synthetic_record(
        "low", True, True, runnable_status="needs_db_safety_refactor"
    )
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_REFACTOR
    assert d["required_change_before_replay"] == "db_safety_refactor"
    assert d["replay_readiness_priority"] == "medium"


def test_classify_record_medium_unresolved_needs_cto_review():
    mod = _module()
    rec = _synthetic_record("medium", False, "unknown")
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_CTO_REVIEW


def test_classify_record_unknown_risk_always_needs_cto_review():
    mod = _module()
    for identity in (True, False, "unknown"):
        rec = _synthetic_record("unknown", False, identity)
        d = mod.classify_record(rec)
        assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_CTO_REVIEW, identity


def test_classify_record_high_risk_always_excluded_regardless_of_identity():
    mod = _module()
    for identity in (True, False, "unknown"):
        rec = _synthetic_record("high", False, identity)
        d = mod.classify_record(rec)
        assert d["p541c_r2_bucket"] == mod.BUCKET_EXCLUDED, identity


def test_classify_record_mark_duplicate_always_excluded_even_if_low_risk():
    mod = _module()
    rec = _synthetic_record("low", True, True, recommended_action="mark_duplicate")
    d = mod.classify_record(rec)
    assert d["p541c_r2_bucket"] == mod.BUCKET_EXCLUDED


# ── classification correctness on the real, pinned artifact ─────────────


def test_classify_all_covers_every_record_exactly_once(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    assert len(decisions) == len(p541b_r2["method_classification_records"])
    ids = [d["method_id"] for d in decisions]
    assert len(ids) == len(set(ids))


def test_every_decision_is_a_known_bucket(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    for d in decisions:
        assert d["p541c_r2_bucket"] in mod.ALL_BUCKETS


def test_bucket_totals_sum_to_580(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    summary = mod.summarize(decisions)
    total = sum(summary[b] for b in mod.ALL_BUCKETS)
    assert total == 580
    assert summary["total_reviewed_from_p541b_r2"] == 580
    assert [summary[b] for b in mod.ALL_BUCKETS] == [0, 12, 0, 458, 110]


def test_source_path_is_identifier_only(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    upstream_paths = [r["source_path"] for r in p541b_r2["method_classification_records"]]
    assert [d["source_path"] for d in decisions] == upstream_paths
    for decision in decisions:
        assert decision["evidence"] == {
            "source_path_contract": "identifier_only_from_pinned_p541b_r2"
        }


def test_nonexistent_source_path_does_not_affect_classification_or_build(
    p541b_r2, input_provenance
):
    mod = _module()
    nonexistent = "does/not/exist/identifier-only.py"
    rec = _synthetic_record("low", True, True, source_path=nonexistent)
    assert mod.classify_record(rec)["source_path"] == nonexistent

    modified = copy.deepcopy(p541b_r2)
    modified["method_classification_records"][0]["source_path"] = nonexistent
    artifact = mod.build_artifact(modified, input_provenance, generated_at="TEST")
    assert artifact["reviewed_method_decisions"][0]["source_path"] == nonexistent


def test_build_performs_no_per_record_source_filesystem_io(
    monkeypatch, p541b_r2, input_provenance
):
    mod = _module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("per-record source filesystem I/O is forbidden")

    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "is_file", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(mod, "file_sha256", forbidden)

    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    assert len(artifact["reviewed_method_decisions"]) == 580


# ── the two safety invariants this replacement exists to enforce ────────


def test_invariant_unknown_risk_never_resolves_to_an_eligible_bucket(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    unknown_risk = [d for d in decisions if d["p541b_r2_status"]["risk_level"] == "unknown"]
    assert len(unknown_risk) > 0
    for d in unknown_risk:
        assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_CTO_REVIEW


def test_invariant_identity_unresolved_records_never_appear_in_shortlist(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    shortlist = mod.build_shortlist(decisions)
    identity_unresolved_ids = {
        d["method_id"]
        for d in decisions
        if d["historical_p541b_status"]["is_actual_prediction_method"] == "unknown"
    }
    shortlist_ids = {d["method_id"] for d in shortlist}
    assert identity_unresolved_ids & shortlist_ids == set()
    for d in shortlist:
        assert d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_ADAPTER
        assert d["historical_p541b_status"]["is_actual_prediction_method"] is True


def test_invariant_low_risk_does_not_erase_upstream_readiness_contract(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    low_confirmed_adapter = [
        d for d in decisions
        if d["p541b_r2_status"]["risk_level"] == "low"
        and d["historical_p541b_status"]["is_actual_prediction_method"] is True
        and d["historical_p541b_status"]["runnable_status"] == "needs_adapter_wrapper"
    ]
    assert len(low_confirmed_adapter) == 12
    assert all(d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_ADAPTER for d in low_confirmed_adapter)
    assert all(d["required_change_before_replay"] == "adapter_wrapper" for d in low_confirmed_adapter)


# ── shortlist ────────────────────────────────────────────────────────────


def test_shortlist_capped_and_deduplicated(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    shortlist = mod.build_shortlist(decisions)
    assert 0 < len(shortlist) <= mod.SHORTLIST_MAX
    ids = [d["method_id"] for d in shortlist]
    assert len(ids) == len(set(ids))


def test_shortlist_is_not_padded_to_historical_size(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    pool = [
        d for d in decisions
        if d["p541c_r2_bucket"] == mod.BUCKET_NEEDS_ADAPTER
        and d["p541b_r2_status"]["risk_level"] == "low"
        and d["replay_readiness_priority"] == "high"
    ]
    shortlist = mod.build_shortlist(decisions)
    assert len(shortlist) == len(pool)
    assert len(shortlist) == 5
    assert len(shortlist) < 20


def test_shortlist_exact_membership_and_contract(p541b_r2):
    mod = _module()
    shortlist = mod.build_shortlist(mod.classify_all(p541b_r2))
    assert [d["method_id"] for d in shortlist] == [
        "tools/advanced_prediction_engine.py",
        "lottery_api/models/social_wisdom_predictor.py",
        "tools/quick_ml_predict.py",
        "tools/big_lotto_exhaustive_audit.py",
        "lottery_api/models/zone_split.py",
    ]
    for decision in shortlist:
        assert decision["p541c_r2_bucket"] == mod.BUCKET_NEEDS_ADAPTER
        assert decision["p541b_r2_status"]["risk_level"] == "low"
        assert decision["historical_p541b_status"]["confidence"] == "high"
        assert decision["historical_p541b_status"]["is_actual_prediction_method"] is True
        assert decision["required_change_before_replay"] != "none"


def test_shortlist_is_deterministic(p541b_r2):
    mod = _module()
    decisions = mod.classify_all(p541b_r2)
    first = [d["method_id"] for d in mod.build_shortlist(decisions)]
    second = [d["method_id"] for d in mod.build_shortlist(decisions)]
    assert first == second


def test_shortlist_never_pads_with_zero_pool():
    mod = _module()
    assert mod.build_shortlist([]) == []


# ── full artifact build ──────────────────────────────────────────────────


def test_build_artifact_has_all_required_sections(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    required_sections = [
        "schema_version", "selector_version",
        "summary", "bucket_definitions", "selection_policy", "reviewed_method_decisions",
        mod.BUCKET_READY, mod.BUCKET_NEEDS_ADAPTER, mod.BUCKET_NEEDS_REFACTOR,
        mod.BUCKET_NEEDS_CTO_REVIEW, "excluded_methods",
        "high_priority_candidate_shortlist", "next_task_recommendation", "contract_reconciliation",
        "input_provenance", "provenance_and_limits", "disclaimer", "supersedes",
    ]
    for section in required_sections:
        assert section in artifact, f"missing section: {section}"


def test_selector_version_is_exact_and_fails_closed(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    assert artifact["selector_version"] == "p541c-r2-selector-v3"

    missing = copy.deepcopy(artifact)
    del missing["selector_version"]
    with pytest.raises(mod.P541CR2ValidationError, match="selector_version mismatch"):
        mod.validate_artifact(missing)

    wrong = copy.deepcopy(artifact)
    wrong["selector_version"] = "p541c-r2-selector-v2"
    with pytest.raises(mod.P541CR2ValidationError, match="selector_version mismatch"):
        mod.validate_artifact(wrong)


def test_build_artifact_disclaimer_text(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    expected = (
        "Historical legacy method review and replay-readiness selection only; "
        "not a prediction, betting edge, future-winning, or production-readiness claim."
    )
    assert artifact["disclaimer"] == expected
    assert artifact["provenance_and_limits"]["disclaimer"] == expected


def test_build_artifact_reviewed_decisions_length_matches_input(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    assert len(artifact["reviewed_method_decisions"]) == 580


def test_build_artifact_is_json_serializable(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    serialized = json.dumps(artifact, ensure_ascii=False)
    reloaded = json.loads(serialized)
    assert reloaded["summary"]["total_reviewed_from_p541b_r2"] == 580


def test_validate_artifact_rejects_noncanonical_projections(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")

    bad_summary = copy.deepcopy(artifact)
    bad_summary["summary"][mod.BUCKET_NEEDS_ADAPTER] += 1
    with pytest.raises(mod.P541CR2ValidationError, match="summary does not match"):
        mod.validate_artifact(bad_summary)

    bad_partition = copy.deepcopy(artifact)
    bad_partition[mod.BUCKET_NEEDS_ADAPTER].append(
        bad_partition[mod.BUCKET_NEEDS_ADAPTER][0]
    )
    with pytest.raises(mod.P541CR2ValidationError, match="bucket partition mismatch"):
        mod.validate_artifact(bad_partition)

    bad_shortlist = copy.deepcopy(artifact)
    bad_shortlist["high_priority_candidate_shortlist"] = []
    with pytest.raises(mod.P541CR2ValidationError, match="canonical selection"):
        mod.validate_artifact(bad_shortlist)


def test_validate_artifact_rejects_safety_bucket_drift(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    unknown = next(
        d for d in artifact["reviewed_method_decisions"]
        if d["p541b_r2_status"]["risk_level"] == "unknown"
    )
    unknown["p541c_r2_bucket"] = mod.BUCKET_READY
    unknown["p541c_decision"] = mod.BUCKET_READY
    with pytest.raises(mod.P541CR2ValidationError, match="unknown risk routed"):
        mod.validate_artifact(artifact)


def test_render_markdown_contains_key_sections(p541b_r2, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b_r2, input_provenance, generated_at="TEST")
    md = mod.render_markdown(artifact)
    assert "# P541C_R2" in md
    assert "## Summary" in md
    assert "## Contract Reconciliation" in md
    assert "## Bucket Definitions" in md
    assert "## Shortlist" in md
    assert "> selector_version: p541c-r2-selector-v3" in md
    assert artifact["next_task_recommendation"] in md
    assert artifact["disclaimer"] in md


def test_committed_json_and_markdown_agree():
    mod = _module()
    committed_json = mod.strict_json_load(
        Path(REPO_ROOT)
        / "outputs/research/p541c_r2_biglotto_legacy_method_review_readiness_selection_20260712.json"
    )
    committed_md = (
        Path(REPO_ROOT)
        / "outputs/research/p541c_r2_biglotto_legacy_method_review_readiness_selection_20260712.md"
    ).read_text(encoding="utf-8")
    assert committed_json["selector_version"] == "p541c-r2-selector-v3"
    assert f"> selector_version: {committed_json['selector_version']}" in committed_md
    for key, value in committed_json["summary"].items():
        assert f"| {key} | {value} |" in committed_md
    for decision in committed_json["high_priority_candidate_shortlist"]:
        assert f"| {decision['method_id']} |" in committed_md


def test_default_build_is_deterministic_and_matches_committed_artifacts(p541b_r2, input_provenance):
    mod = _module()
    first = mod.build_artifact(p541b_r2, input_provenance)
    second = mod.build_artifact(p541b_r2, input_provenance)
    assert first == second
    assert first["generated_at"] == mod.GENERATED_AT
    expected_json = (
        json.dumps(first, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    committed_json = os.path.join(
        REPO_ROOT,
        "outputs/research/p541c_r2_biglotto_legacy_method_review_readiness_selection_20260712.json",
    )
    committed_md = os.path.join(
        REPO_ROOT,
        "outputs/research/p541c_r2_biglotto_legacy_method_review_readiness_selection_20260712.md",
    )
    assert open(committed_json, "rb").read() == expected_json
    assert open(committed_md, "rb").read() == mod.render_markdown(first).encode("utf-8")
