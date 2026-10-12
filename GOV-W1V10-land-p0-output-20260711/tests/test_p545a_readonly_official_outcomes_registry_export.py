"""Focused tests for the committed-P268D1 P545A registry exporter.

Pure parser tests use only in-memory JSON/JSONL.  Integration tests read raw
blobs from the pinned local Git commit and reproduce the committed P545A
artifacts in temporary directories.  No mutable data source or service is used.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest

from analysis import p545a_readonly_official_outcomes_registry_export as exporter


REPO_ROOT = Path(exporter.__file__).resolve().parents[1]
OUTPUT_STEM = "p545a_readonly_official_outcomes_registry_20260710"
COMMITTED_JSON = REPO_ROOT / "outputs" / "research" / f"{OUTPUT_STEM}.json"
COMMITTED_MARKDOWN = REPO_ROOT / "outputs" / "research" / f"{OUTPUT_STEM}.md"


def _line(
    lottery: str,
    period: int | str,
    size: list[int],
    appear: list[int] | None = None,
    draw_date: str = "2026-01-02T00:00:00",
) -> dict[str, object]:
    return {
        "lottery_type": lottery,
        "month": "2026-01",
        "period": period,
        "draw_date": draw_date,
        "drawNumberAppear": list(size if appear is None else appear),
        "drawNumberSize": list(size),
        "validation": {"fixture": True},
    }


def _jsonl(*rows: dict[str, object]) -> bytes:
    return b"".join(
        json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n" for row in rows
    )


@pytest.fixture(scope="module")
def frozen_raw() -> dict[str, bytes]:
    source = exporter.GitBlobSource(REPO_ROOT, exporter.PINNED_COMMIT)
    return {
        source_id: source.read(spec["path"])
        for source_id, spec in exporter.SOURCE_SPECS.items()
    }


@pytest.fixture(scope="module")
def frozen_documents(frozen_raw: dict[str, bytes]) -> dict[str, object]:
    return {
        "p273a": exporter.decode_json_object(frozen_raw["p273a"], "P273A"),
        "p543c": exporter.decode_json_object(frozen_raw["p543c"], "P543C"),
    }


@pytest.fixture(scope="module")
def payload(frozen_raw: dict[str, bytes]) -> dict[str, object]:
    return exporter.build_registry(
        p268d1_raw=frozen_raw["p268d1"],
        p273a_raw=frozen_raw["p273a"],
        p543c_raw=frozen_raw["p543c"],
        pinned_repo_commit=exporter.PINNED_COMMIT,
        generated_at_utc=exporter.commit_timestamp_utc(
            REPO_ROOT, exporter.PINNED_COMMIT
        ),
    )


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    first = tmp_path_factory.mktemp("p545a-first")
    second = tmp_path_factory.mktemp("p545a-second")
    first_json = first / "registry.json"
    first_md = first / "registry.md"
    second_json = second / "registry.json"
    second_md = second / "registry.md"
    first_payload = exporter.generate_from_pinned_commit(
        repo_root=REPO_ROOT,
        pinned_commit=exporter.PINNED_COMMIT,
        output_json=first_json,
        output_md=first_md,
    )
    second_payload = exporter.generate_from_pinned_commit(
        repo_root=REPO_ROOT,
        pinned_commit=exporter.PINNED_COMMIT,
        output_json=second_json,
        output_md=second_md,
    )
    return {
        "first_payload": first_payload,
        "second_payload": second_payload,
        "first_json": first_json.read_bytes(),
        "second_json": second_json.read_bytes(),
        "first_markdown": first_md.read_bytes(),
        "second_markdown": second_md.read_bytes(),
    }


def test_all_frozen_raw_hashes_and_sizes(frozen_raw: dict[str, bytes]) -> None:
    for source_id, raw in frozen_raw.items():
        observed = exporter.verify_source_bytes(exporter.SOURCE_SPECS[source_id], raw)
        assert observed == {
            "sha256": exporter.SOURCE_SPECS[source_id]["sha256"],
            "byte_size": exporter.SOURCE_SPECS[source_id]["byte_size"],
        }


def test_jsonl_line_parsing_uses_source_line_number() -> None:
    rows, summary = exporter.parse_p268d1_jsonl(
        _jsonl(_line("DAILY_539", 10, [1, 2, 3, 4, 5])),
        require_expected_shape=False,
    )
    assert len(rows) == summary["relevant_record_count"] == 1
    assert rows[0]["source_line_number"] == 1
    assert rows[0]["target_draw"] == "10"


@pytest.mark.parametrize("raw", (b"\n", b"{not-json}\n", b"[]\n"))
def test_blank_malformed_or_nonobject_jsonl_rejected(raw: bytes) -> None:
    with pytest.raises(exporter.SourceIntegrityError):
        exporter.parse_p268d1_jsonl(raw, require_expected_shape=False)


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("biglotto", "BIG_LOTTO"),
        ("Big Lotto", "BIG_LOTTO"),
        ("daily539", "DAILY_539"),
        ("power-lotto", "POWER_LOTTO"),
    ),
)
def test_lottery_identifier_normalization(source: str, expected: str) -> None:
    assert exporter.normalize_lottery_type(source) == expected


def test_numeric_draw_ordering_is_not_lexical() -> None:
    rows, _summary = exporter.parse_p268d1_jsonl(
        _jsonl(
            _line("DAILY_539", "10", [1, 2, 3, 4, 5]),
            _line("DAILY_539", "2", [6, 7, 8, 9, 10]),
        ),
        require_expected_shape=False,
    )
    assert [row["target_draw"] for row in rows] == ["2", "10"]


def test_daily_539_validation() -> None:
    main, special, second_zone, appear = exporter.validate_outcome_sequences(
        "DAILY_539", [1, 2, 3, 4, 39], [39, 1, 4, 2, 3]
    )
    assert main == [1, 2, 3, 4, 39]
    assert special is second_zone is None
    assert appear == [39, 1, 4, 2, 3]


def test_big_lotto_validation() -> None:
    main, special, second_zone, _appear = exporter.validate_outcome_sequences(
        "BIG_LOTTO", [1, 2, 3, 4, 5, 49, 6], [49, 5, 4, 3, 2, 1, 6]
    )
    assert main == [1, 2, 3, 4, 5, 49]
    assert special == 6
    assert second_zone is None


def test_power_lotto_validation() -> None:
    main, special, second_zone, _appear = exporter.validate_outcome_sequences(
        "POWER_LOTTO", [1, 2, 3, 4, 5, 38, 8], [38, 5, 4, 3, 2, 1, 8]
    )
    assert main == [1, 2, 3, 4, 5, 38]
    assert special is None
    assert second_zone == 8


def test_big_lotto_special_must_not_duplicate_main() -> None:
    with pytest.raises(exporter.SourceIntegrityError, match="duplicates"):
        exporter.validate_outcome_sequences(
            "BIG_LOTTO", [1, 2, 3, 4, 5, 6, 6], [6, 5, 4, 3, 2, 1, 6]
        )


def test_power_lotto_second_zone_range() -> None:
    with pytest.raises(exporter.SourceIntegrityError, match="outside 1..8"):
        exporter.validate_outcome_sequences(
            "POWER_LOTTO", [1, 2, 3, 4, 5, 6, 9], [6, 5, 4, 3, 2, 1, 9]
        )


def test_duplicate_source_key_rejected() -> None:
    row = _line("DAILY_539", 10, [1, 2, 3, 4, 5])
    with pytest.raises(exporter.SourceIntegrityError, match="duplicate identical"):
        exporter.parse_p268d1_jsonl(
            _jsonl(row, copy.deepcopy(row)), require_expected_shape=False
        )


def test_conflicting_source_key_rejected() -> None:
    first = _line("DAILY_539", 10, [1, 2, 3, 4, 5])
    second = _line("DAILY_539", 10, [1, 2, 3, 4, 6])
    with pytest.raises(exporter.SourceIntegrityError, match="conflicting"):
        exporter.parse_p268d1_jsonl(
            _jsonl(first, second), require_expected_shape=False
        )


def test_full_source_counts_and_ranges(frozen_raw: dict[str, bytes]) -> None:
    rows, summary = exporter.parse_p268d1_jsonl(frozen_raw["p268d1"])
    assert len(rows) == summary["relevant_record_count"] == 9_930
    assert {
        lottery: summary["by_lottery"][lottery]["record_count"]
        for lottery in exporter.LOTTERIES
    } == {"BIG_LOTTO": 2_139, "DAILY_539": 5_876, "POWER_LOTTO": 1_915}
    assert {
        lottery: (
            summary["by_lottery"][lottery]["earliest_draw"],
            summary["by_lottery"][lottery]["latest_draw"],
        )
        for lottery in exporter.LOTTERIES
    } == exporter.EXPECTED_SOURCE_RANGES
    assert summary["draw_number_appear_checked_count"] == 9_930
    assert summary["draw_number_appear_mismatch_count"] == 0


def test_requested_manifest_counts_and_total(
    frozen_documents: dict[str, object],
) -> None:
    requested, summary = exporter.extract_requested_draws(
        frozen_documents["p273a"], frozen_documents["p543c"]
    )
    assert len(requested) == summary["union_unique_draw_count"] == 2_252
    assert summary["union_by_lottery"] == {
        "BIG_LOTTO": 752,
        "DAILY_539": 750,
        "POWER_LOTTO": 750,
    }


def test_p543c_shape_is_500_rows_10_candidates_50_each_52_draws(
    frozen_documents: dict[str, object],
) -> None:
    _requested, summary = exporter.extract_requested_draws(
        frozen_documents["p273a"], frozen_documents["p543c"]
    )
    shape = summary["p543c"]
    assert shape["row_count"] == 500
    assert shape["candidate_count"] == 10
    assert set(shape["rows_per_candidate"].values()) == {50}
    assert shape["unique_draw_count"] == 52
    assert summary["source_overlap_unique_draw_count"] == 52
    assert summary["all_p543c_draws_overlap_p273a"] is True


def test_complete_requested_coverage_and_one_record_per_key(
    payload: dict[str, object],
) -> None:
    coverage = payload["coverage_summary"]
    assert coverage["total"] == {
        "requested": 2_252,
        "found_valid": 2_252,
        "missing": 0,
        "conflicting": 0,
        "invalid": 0,
    }
    assert coverage["complete"] is True
    assert coverage["exact_one_record_per_requested_key"] is True
    records = payload["records"]
    keys = {(row["lottery_type"], row["target_draw"]) for row in records}
    assert len(records) == len(keys) == 2_252


def test_p543c_500_row_main_and_special_cross_check(payload: dict[str, object]) -> None:
    check = payload["p543c_cross_check"]
    assert check["compared_row_count"] == 500
    assert check["unique_draw_count"] == 52
    assert check["main_number_mismatch_count"] == 0
    assert check["special_number_mismatch_count"] == 0
    assert check["internally_conflicting_draw_count"] == 0
    assert check["passed"] is True


def test_p543c_mismatch_fails_closed(
    frozen_documents: dict[str, object], payload: dict[str, object]
) -> None:
    broken = copy.deepcopy(frozen_documents["p543c"])
    broken["contract"]["rows"][0]["actual_numbers"][0] = 49
    with pytest.raises(exporter.P543CCrossCheckError):
        exporter.cross_check_p543c(broken, payload["records"])


def test_stable_normalized_record_order(payload: dict[str, object]) -> None:
    records = payload["records"]
    keys = [
        (row["lottery_type"], row["target_draw_numeric"], row["target_draw"])
        for row in records
    ]
    assert keys == sorted(keys)


def test_record_sha256_reproduction(payload: dict[str, object]) -> None:
    records = payload["records"]
    assert all(row["record_sha256"] == exporter.record_digest(row) for row in records)


def test_canonical_payload_digest_reproduction(payload: dict[str, object]) -> None:
    assert payload["canonical_payload_digest"] == exporter.canonical_payload_digest(
        payload
    )


def test_deterministic_timestamp_policy_and_value(payload: dict[str, object]) -> None:
    assert payload["generated_at_utc"] == "2026-07-10T11:18:28+00:00"
    assert "pinned input commit committer timestamp" in payload["generated_at_policy"]


def test_deterministic_two_run_json_and_markdown_bytes(
    two_runs: dict[str, object],
) -> None:
    assert two_runs["first_json"] == two_runs["second_json"]
    assert two_runs["first_markdown"] == two_runs["second_markdown"]
    assert two_runs["first_payload"] == two_runs["second_payload"]


def test_reproduced_outputs_equal_committed_files(two_runs: dict[str, object]) -> None:
    assert two_runs["first_json"] == COMMITTED_JSON.read_bytes()
    assert two_runs["first_markdown"] == COMMITTED_MARKDOWN.read_bytes()


def test_markdown_embeds_json_markdown_body_and_payload_digests(
    two_runs: dict[str, object],
) -> None:
    markdown = two_runs["first_markdown"].decode("utf-8")
    json_sha = hashlib.sha256(two_runs["first_json"]).hexdigest()
    base, marker, _digest_section = markdown.partition("\n## Digest evidence\n")
    assert marker
    markdown_body_sha = hashlib.sha256(base.encode("utf-8")).hexdigest()
    assert json_sha in markdown
    assert markdown_body_sha in markdown
    assert two_runs["first_payload"]["canonical_payload_digest"] in markdown


def test_no_database_import_filename_or_use() -> None:
    source = Path(exporter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "sqlite3" not in imported
    assert "sqlalchemy" not in imported
    assert "lottery_v2.db" not in source
    assert not any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.lower().endswith((".sqlite", ".sqlite3"))
        for node in ast.walk(tree)
    )


def test_no_network_library_http_call_or_fallback_source(
    payload: dict[str, object],
) -> None:
    source = Path(exporter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported.isdisjoint({"requests", "httpx", "urllib", "socket", "aiohttp"})
    assert "http://" not in source and "https://" not in source
    adapter = payload["source_adapter"]
    assert adapter["adapter_type"] == "committed_p268d1_jsonl"
    assert adapter["database_used"] is False
    assert adapter["network_used"] is False
    assert adapter["fallback_allowed"] is False


def test_safety_and_no_claim_contract(payload: dict[str, object]) -> None:
    assert payload["safety"] == {
        "database_opened": False,
        "database_written": False,
        "network_used": False,
        "upstream_artifact_modified": False,
        "partial_registry_emitted": False,
        "predictive_claim_made": False,
        "betting_advice": False,
        "production_readiness_claim": False,
    }
    limitations = " ".join(payload["limitations"]).lower()
    assert "does not establish improved winning odds" in limitations
    assert "not betting or investment advice" in limitations
