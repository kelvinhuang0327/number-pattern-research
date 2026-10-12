"""P541C — read-only tests for the BIG_LOTTO legacy method review and
replay-readiness selection artifact.

The module pins and strictly parses the P541B/P541A artifacts, then hashes
repository-contained Python sources without importing or executing them.
It never opens a DB connection and never writes to `outputs/` except through
`main()`.
"""
import ast
import copy
import inspect
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

pytestmark = pytest.mark.filterwarnings("ignore")


def _module():
    from analysis import p541c_biglotto_legacy_method_review_readiness_selection as mod

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


def test_module_only_touches_disk_via_isfile_and_open():
    mod = _module()
    src = inspect.getsource(mod)
    assert "is_file()" in src


# ── artifact inputs ─────────────────────────────────────────────────────


def test_p541b_and_p541a_artifacts_exist():
    mod = _module()
    assert mod.P541B_JSON.exists()
    assert mod.P541B_MD.exists()
    assert mod.P541A_JSON.exists()
    assert mod.P541A_MD.exists()


@pytest.fixture(scope="module")
def verified_inputs():
    mod = _module()
    return mod.load_verified_inputs()


@pytest.fixture(scope="module")
def p541b(verified_inputs):
    return verified_inputs[0]


@pytest.fixture(scope="module")
def p541a(verified_inputs):
    return verified_inputs[1]


@pytest.fixture(scope="module")
def input_provenance(verified_inputs):
    return verified_inputs[2]


def test_p541b_has_580_records(p541b):
    assert len(p541b["method_classification_records"]) == 580


def test_all_four_consumed_artifacts_match_pinned_identity(input_provenance):
    mod = _module()
    assert set(input_provenance) == set(mod.INPUT_ARTIFACTS)
    assert {item["verification"] for item in input_provenance.values()} == {"PASS"}
    assert {
        name: (item["byte_size"], item["sha256"])
        for name, item in input_provenance.items()
    } == {
        name: (item["byte_size"], item["sha256"])
        for name, item in mod.INPUT_ARTIFACTS.items()
    }


def test_strict_json_rejects_duplicate_keys_and_nonfinite(tmp_path):
    mod = _module()
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"same":1,"same":2}', encoding="utf-8")
    with pytest.raises(mod.P541CValidationError, match="duplicate JSON key"):
        mod.strict_json_load(duplicate)
    for token in ("NaN", "Infinity", "-Infinity"):
        nonfinite = tmp_path / f"nonfinite-{token.replace('-', 'minus')}.json"
        nonfinite.write_text('{"value":' + token + '}', encoding="utf-8")
        with pytest.raises(mod.P541CValidationError, match="non-finite JSON"):
            mod.strict_json_load(nonfinite)


def test_input_hash_mismatch_fails_closed(tmp_path):
    mod = _module()
    path = tmp_path / "input.json"
    path.write_text("{}", encoding="utf-8")
    identity = {"path": "input.json", "byte_size": 2, "sha256": "0" * 64}
    with pytest.raises(mod.P541CValidationError, match="identity mismatch"):
        mod.verify_file_identity(tmp_path, identity)
    with pytest.raises(mod.P541CValidationError, match="unsafe input path"):
        mod.verify_file_identity(tmp_path, {**identity, "path": "../input.json"})


def test_build_rejects_forged_input_provenance(p541b, p541a, input_provenance):
    mod = _module()
    forged = copy.deepcopy(input_provenance)
    forged["p541b_json"]["sha256"] = "0" * 64
    with pytest.raises(mod.P541CValidationError, match="input provenance identity contract mismatch"):
        mod.build_artifact(p541b, p541a, forged)


def test_unknown_upstream_action_and_missing_evidence_flag_fail_closed(p541b, p541a):
    mod = _module()
    unknown = copy.deepcopy(p541b)
    unknown["method_classification_records"][0]["recommended_action"] = "silently_promote"
    with pytest.raises(mod.P541CValidationError, match="unknown recommended_action"):
        mod.validate_upstream_contracts(unknown, p541a)

    missing_flag = copy.deepcopy(p541b)
    record = missing_flag["method_classification_records"][0]
    record["evidence"] = [line for line in record["evidence"] if not line.startswith("uses_db_anywhere=")]
    with pytest.raises(mod.P541CValidationError, match="evidence flag contract mismatch"):
        mod.validate_upstream_contracts(missing_flag, p541a)

    duplicate_flag = copy.deepcopy(p541b)
    duplicate_flag["method_classification_records"][0]["evidence"].append("uses_db_anywhere=False")
    with pytest.raises(mod.P541CValidationError, match="duplicate evidence flag"):
        mod.validate_upstream_contracts(duplicate_flag, p541a)

    numeric_identity = copy.deepcopy(p541b)
    numeric_identity["method_classification_records"][0]["is_actual_prediction_method"] = 1
    with pytest.raises(mod.P541CValidationError, match="unknown method identity"):
        mod.validate_upstream_contracts(numeric_identity, p541a)


def test_source_path_escape_missing_and_symlink_fail_closed(tmp_path):
    mod = _module()
    with pytest.raises(mod.P541CValidationError, match="unsafe source_path"):
        mod.source_file_identity("../escape.py", tmp_path)
    with pytest.raises(mod.P541CValidationError, match="source_path missing"):
        mod.source_file_identity("missing.py", tmp_path)
    target = tmp_path / "target.py"
    target.write_text("pass\n", encoding="utf-8")
    link = tmp_path / "link.py"
    link.symlink_to(target)
    with pytest.raises(mod.P541CValidationError, match="symlink source_path rejected"):
        mod.source_file_identity("link.py", tmp_path)


# ── evidence parsing ────────────────────────────────────────────────────


def test_parse_evidence_flags_extracts_booleans():
    mod = _module()
    flags = mod.parse_evidence_flags([
        "docstring[:120]='hello'",
        "module_level_db_call=False",
        "uses_db_anywhere=True",
        "writes_files_anywhere=False",
    ])
    assert flags == {
        "module_level_db_call": False,
        "uses_db_anywhere": True,
        "writes_files_anywhere": False,
    }


def test_compute_risk_level():
    mod = _module()
    assert mod.compute_risk_level({"uses_db_anywhere": True}) == "high"
    assert mod.compute_risk_level({"writes_files_anywhere": True}) == "medium"
    assert mod.compute_risk_level({"hardcoded_abs_path": True}) == "medium"
    assert mod.compute_risk_level({}) == "low"
    assert mod.compute_risk_level({"uses_db_anywhere": True, "writes_files_anywhere": True}) == "high"


# ── classification correctness ──────────────────────────────────────────


def test_classify_all_covers_every_record_exactly_once(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    assert len(decisions) == len(p541b["method_classification_records"])
    ids = [d["method_id"] for d in decisions]
    assert len(ids) == len(set(ids))


def test_every_decision_is_a_known_bucket(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    for d in decisions:
        assert d["p541c_decision"] in mod.ALL_DECISIONS


def test_include_in_replay_readiness_records_become_needs_adapter(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    included = [
        r for r in p541b["method_classification_records"]
        if r["recommended_action"] == "include_in_replay_readiness"
    ]
    assert len(included) == 142
    for rec in included:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_ADAPTER
        assert d["required_change_before_replay"] == "adapter_wrapper"


def test_mark_duplicate_records_are_excluded_with_deprecate(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    dups = [
        r for r in p541b["method_classification_records"]
        if r["recommended_action"] == "mark_duplicate"
    ]
    assert len(dups) == 9
    for rec in dups:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_EXCLUDE
        assert d["required_change_before_replay"] == "deprecate"
        assert d["replay_readiness_priority"] == "exclude"


def test_unsafe_side_effect_records_always_excluded_regardless_of_identity(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    unsafe = [
        r for r in p541b["method_classification_records"]
        if r["runnable_status"] in (
            "unsafe_side_effects", "imports_db_or_runs_work_at_module_load",
        )
    ]
    assert len(unsafe) > 0
    for rec in unsafe:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_EXCLUDE
        assert d["risk_level"] == "high"


def test_needs_cto_review_records_stay_needs_cto_review_when_no_new_evidence(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    cto = [
        r for r in p541b["method_classification_records"]
        if r["recommended_action"] == "needs_cto_review"
    ]
    assert len(cto) == 167
    for rec in cto:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_CTO


def test_hardcoded_paths_with_confirmed_identity_become_needs_adapter(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    matches = [
        r for r in p541b["method_classification_records"]
        if r["recommended_action"] == "exclude_from_replay"
        and r["runnable_status"] == "hardcoded_paths_or_dates"
        and r["is_actual_prediction_method"] is True
    ]
    assert len(matches) == 31
    for rec in matches:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_ADAPTER
        assert d["required_change_before_replay"] == "parameterization"


def test_refactor_needed_with_confirmed_identity_becomes_needs_refactor(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    matches = [
        r for r in p541b["method_classification_records"]
        if r["recommended_action"] == "exclude_from_replay"
        and r["runnable_status"] in ("needs_refactor_to_pure_function", "needs_db_safety_refactor")
        and r["is_actual_prediction_method"] is True
    ]
    assert len(matches) == 35
    for rec in matches:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_REFACTOR
        assert d["required_change_before_replay"] in ("pure_function_refactor", "db_safety_refactor")


def test_unresolved_identity_with_fixable_blocker_deferred_to_cto(p541b):
    mod = _module()
    decisions = {d["method_id"]: d for d in mod.classify_all(p541b)}
    matches = [
        r for r in p541b["method_classification_records"]
        if r["recommended_action"] == "exclude_from_replay"
        and r["runnable_status"] in (
            "hardcoded_paths_or_dates", "needs_refactor_to_pure_function", "needs_db_safety_refactor",
        )
        and r["is_actual_prediction_method"] != True
    ]
    assert len(matches) == 123
    for rec in matches:
        d = decisions[rec["method_id"]]
        assert d["p541c_decision"] == mod.DECISION_CTO


def test_bucket_totals_sum_to_580(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    summary = mod.summarize(decisions)
    total = (
        summary["ready_for_replay_readiness_now"]
        + summary["needs_adapter_before_readiness"]
        + summary["needs_refactor_before_readiness"]
        + summary["needs_cto_review"]
        + summary["exclude_from_replay"]
    )
    assert total == 580
    assert summary["total_reviewed_from_p541b"] == 580


def test_all_reviewed_source_paths_exist_on_disk(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    missing = [d for d in decisions if not d["evidence"]["source_path_exists"]]
    assert missing == []


# ── shortlist ────────────────────────────────────────────────────────────


def test_shortlist_capped_at_20_and_deduplicated(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    shortlist = mod.build_shortlist(decisions)
    assert 0 < len(shortlist) <= 20
    ids = [d["method_id"] for d in shortlist]
    assert len(ids) == len(set(ids))


def test_shortlist_members_are_low_risk_high_priority_adapter_candidates(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    shortlist = mod.build_shortlist(decisions)
    for d in shortlist:
        assert d["p541c_decision"] == mod.DECISION_ADAPTER
        assert d["replay_readiness_priority"] == "high"
        assert d["risk_level"] == "low"
        assert d["evidence"]["static_flags"].get("uses_db_anywhere") is not True
        assert d["evidence"]["static_flags"].get("writes_files_anywhere") is not True


def test_shortlist_is_deterministic(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    first = [d["method_id"] for d in mod.build_shortlist(decisions)]
    second = [d["method_id"] for d in mod.build_shortlist(decisions)]
    assert first == second


# ── next task recommendation ────────────────────────────────────────────


def test_next_task_recommendation_is_one_of_allowed_values(p541b):
    mod = _module()
    decisions = mod.classify_all(p541b)
    shortlist = mod.build_shortlist(decisions)
    next_task = mod.determine_next_task(decisions, shortlist)
    assert next_task in mod.NEXT_TASK_OPTIONS


# ── full artifact build ──────────────────────────────────────────────────


def test_build_artifact_has_all_required_sections(p541b, p541a, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b, p541a, input_provenance, generated_at="TEST")
    required_sections = [
        "summary", "p541b_context", "selection_policy", "reviewed_method_decisions",
        "ready_for_replay_readiness_now", "needs_adapter_before_readiness",
        "needs_refactor_before_readiness", "needs_cto_review", "excluded_methods",
        "high_priority_candidate_shortlist", "next_task_recommendation",
        "input_provenance", "provenance_and_limits", "disclaimer",
    ]
    for section in required_sections:
        assert section in artifact, f"missing section: {section}"


def test_build_artifact_disclaimer_text(p541b, p541a, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b, p541a, input_provenance, generated_at="TEST")
    expected = (
        "Historical legacy method review and replay-readiness selection only; "
        "not a prediction, betting edge, future-winning, or production-readiness claim."
    )
    assert artifact["disclaimer"] == expected
    assert artifact["provenance_and_limits"]["disclaimer"] == expected


def test_build_artifact_reviewed_method_decisions_length_matches_p541b(p541b, p541a, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b, p541a, input_provenance, generated_at="TEST")
    assert len(artifact["reviewed_method_decisions"]) == 580


def test_build_artifact_is_json_serializable(p541b, p541a, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b, p541a, input_provenance, generated_at="TEST")
    serialized = json.dumps(artifact, ensure_ascii=False)
    reloaded = json.loads(serialized)
    assert reloaded["summary"]["total_reviewed_from_p541b"] == 580


def test_render_markdown_contains_key_sections(p541b, p541a, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b, p541a, input_provenance, generated_at="TEST")
    md = mod.render_markdown(artifact)
    assert "# P541C" in md
    assert "## Summary" in md
    assert "## Verified Input Provenance" in md
    assert "## High-Priority Candidate Shortlist" in md
    assert artifact["next_task_recommendation"] in md
    assert artifact["disclaimer"] in md


def test_source_manifest_and_per_record_provenance_are_complete(p541b, p541a, input_provenance):
    mod = _module()
    artifact = mod.build_artifact(p541b, p541a, input_provenance)
    manifest = artifact["input_provenance"]["source_manifest"]
    assert manifest == {
        "record_count": 580,
        "total_bytes": mod.SOURCE_MANIFEST_TOTAL_BYTES,
        "sha256": mod.SOURCE_MANIFEST_SHA256,
        "canonicalization": "UTF-8 compact sorted-key JSON ordered by source_path",
        "entry_fields": ["source_path", "byte_size", "sha256"],
        "entries_embedded_at": "reviewed_method_decisions[*].evidence.source_file_identity",
        "verification": "PASS",
    }
    identities = [
        decision["evidence"]["source_file_identity"]
        for decision in artifact["reviewed_method_decisions"]
    ]
    assert len(identities) == len({item["source_path"] for item in identities}) == 580
    assert all(len(item["sha256"]) == 64 and item["byte_size"] > 0 for item in identities)


def test_default_build_is_deterministic_and_matches_committed_artifacts(p541b, p541a, input_provenance):
    mod = _module()
    first = mod.build_artifact(p541b, p541a, input_provenance)
    second = mod.build_artifact(p541b, p541a, input_provenance)
    assert first == second
    assert first["generated_at"] == mod.GENERATED_AT
    expected_json = (
        json.dumps(first, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    committed_json = os.path.join(
        REPO_ROOT,
        "outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_20260710.json",
    )
    committed_md = os.path.join(
        REPO_ROOT,
        "outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_20260710.md",
    )
    assert open(committed_json, "rb").read() == expected_json
    assert open(committed_md, "rb").read() == mod.render_markdown(first).encode("utf-8")
