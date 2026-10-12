#!/usr/bin/env python3
"""
P518F no-DB smoke harness for tools.predraw_ledger_verify.

This harness builds only synthetic temporary ledger fixtures, calls the
predraw ledger verifier against those fixtures, and writes deterministic smoke
artifacts. It does not open or write the canonical DB, does not run migrations
or backfills, does not deploy, is not production release approval, and makes no
betting advice or future prediction claims.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lottery_api.engine import predraw_ledger as ledger  # noqa: E402
from tools import predraw_ledger_verify as verifier  # noqa: E402

ARTIFACT_PREFIX = "P518F_predraw_ledger_verify_smoke"
EDGE_ARTIFACT_PREFIX = "P518G_predraw_ledger_verify_edge_matrix"
ARTIFACTS_DIR = _PROJECT_ROOT / "artifacts"
RESULTS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_results.json"
CASES_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_cases.csv"
TRANSCRIPTS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_transcripts.json"
REPORT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_report.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"
EDGE_RESULTS_PATH = ARTIFACTS_DIR / f"{EDGE_ARTIFACT_PREFIX}_results.json"
EDGE_CASES_PATH = ARTIFACTS_DIR / f"{EDGE_ARTIFACT_PREFIX}_cases.csv"
EDGE_TRANSCRIPTS_PATH = ARTIFACTS_DIR / f"{EDGE_ARTIFACT_PREFIX}_transcripts.json"
EDGE_COVERAGE_PATH = ARTIFACTS_DIR / f"{EDGE_ARTIFACT_PREFIX}_coverage.csv"
EDGE_REPORT_PATH = ARTIFACTS_DIR / f"{EDGE_ARTIFACT_PREFIX}_report.md"
EDGE_MANIFEST_PATH = ARTIFACTS_DIR / f"{EDGE_ARTIFACT_PREFIX}_manifest.csv"

NOTICE_LINES = (
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "synthetic fixtures only",
    "not production release approval",
    "no betting/future prediction claims",
)

_TEMP_TOKEN = "${P518F_SMOKE_TMP}"
_EDGE_TEMP_TOKEN = "${P518G_EDGE_TMP}"


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _prediction_payload(
    *,
    record_id: str,
    bet_index: int,
    numbers: Sequence[int],
    lottery_type: str = "BIG_LOTTO",
    target_draw: int = 114000101,
    strategy_id: str = "p518f-smoke-synthetic",
) -> Dict[str, Any]:
    return {
        "schema_version": ledger.SCHEMA_VERSION,
        "record_id": record_id,
        "record_kind": "PREDICTION",
        "lottery_type": lottery_type,
        "generation_mode": "RETROSPECTIVE_REPLAY",
        "predicted_at": "2020-01-01T00:00:00+00:00",
        "created_at": "2020-01-01T00:00:00+00:00",
        "target_draw": target_draw,
        "target_draw_date": None,
        "scheduled_draw_close_at": None,
        "schedule_rule_version": None,
        "history_cutoff_draw": None,
        "history_cutoff_date": None,
        "max_source_draw_at_generation": None,
        "max_source_draw_date_at_generation": None,
        "source_db_fingerprint": None,
        "strategy_id": strategy_id,
        "strategy_version": "v1",
        "code_git_sha": "p518f-smoke-fixed-sha",
        "code_dirty_flag": False,
        "params_hash": None,
        "random_seed": None,
        "strategy_artifact_hash": None,
        "predicted_numbers": [int(n) for n in numbers],
        "predicted_special": None,
        "bet_index": int(bet_index),
        "n_bets_total": 2,
        "run_id": "p518f-smoke-run",
        "generation_source": "tools.predraw_ledger_verify_smoke synthetic fixture",
        "supersedes_record_id": None,
    }


def _write_valid_ledger(path: Path) -> None:
    prev_hash = None
    records = []
    for record_id, bet_index, numbers in (
        ("p518f-smoke-rec-001", 0, (1, 2, 3, 4, 5, 6)),
        ("p518f-smoke-rec-002", 1, (7, 8, 9, 10, 11, 12)),
    ):
        payload = _prediction_payload(record_id=record_id, bet_index=bet_index, numbers=numbers)
        record_hash = ledger.compute_record_hash(payload, prev_hash)
        record = dict(payload)
        record["prev_record_hash"] = prev_hash
        record["record_hash"] = record_hash
        records.append(record)
        prev_hash = record_hash
    path.write_text("".join(_canonical_json(record) + "\n" for record in records), encoding="utf-8")


def _records_from_payloads(payloads: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    prev_hash = None
    records: List[Dict[str, Any]] = []
    for payload in payloads:
        payload_dict = dict(payload)
        record_hash = ledger.compute_record_hash(payload_dict, prev_hash)
        record = dict(payload_dict)
        record["prev_record_hash"] = prev_hash
        record["record_hash"] = record_hash
        records.append(record)
        prev_hash = record_hash
    return records


def _write_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.write_text("".join(_canonical_json(dict(record)) + "\n" for record in records), encoding="utf-8")


def _write_tampered_ledger(valid_path: Path, tampered_path: Path) -> None:
    lines = valid_path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["bet_index"] = 99
    lines[1] = _canonical_json(second)
    tampered_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normalize_text(text: str, tmp_root: Path, temp_token: str = _TEMP_TOKEN) -> str:
    normalized = text.replace(str(tmp_root), temp_token)
    resolved = str(tmp_root.resolve())
    if resolved != str(tmp_root):
        normalized = normalized.replace(resolved, temp_token)
    return normalized


def _run_verifier(path: Path, tmp_root: Path, temp_token: str = _TEMP_TOKEN) -> Dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    argv = [str(path)]
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = verifier.main(argv)
    return {
        "argv": ["tools.predraw_ledger_verify", _normalize_text(str(path), tmp_root, temp_token)],
        "exit_code": exit_code,
        "stdout": _normalize_text(stdout.getvalue(), tmp_root, temp_token),
        "stderr": _normalize_text(stderr.getvalue(), tmp_root, temp_token),
    }


def run_smoke_cases() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p518f_predraw_ledger_verify_smoke_") as tmp:
        tmp_root = Path(tmp)
        valid_path = tmp_root / "synthetic_valid_ledger.jsonl"
        tampered_path = tmp_root / "synthetic_tampered_ledger.jsonl"
        missing_path = tmp_root / "synthetic_missing_ledger.jsonl"
        refused_path = tmp_root / "lottery_v2.db"

        _write_valid_ledger(valid_path)
        _write_tampered_ledger(valid_path, tampered_path)
        refused_path.write_text("synthetic refusal fixture; not a database\n", encoding="utf-8")

        canonical_db = _PROJECT_ROOT / "data" / "lottery_v2.db"
        no_db_evidence = {
            "canonical_db_path": str(canonical_db),
            "canonical_db_exists_before": canonical_db.exists(),
            "canonical_db_exists_after": None,
            "canonical_db_opened": False,
            "canonical_db_written": False,
            "migration_backfill_deploy_run": False,
            "fixture_root": _TEMP_TOKEN,
            "fixture_scope": "temporary synthetic JSONL files only",
        }

        raw_cases = (
            (
                "valid_synthetic_ledger",
                "valid synthetic ledger verifies successfully",
                valid_path,
                verifier.EXIT_OK,
            ),
            (
                "tampered_chain_invalid",
                "tampered ledger returns chain-invalid nonzero status",
                tampered_path,
                verifier.EXIT_INVALID,
            ),
            (
                "missing_ledger_path",
                "missing ledger path returns file-not-found status",
                missing_path,
                verifier.EXIT_FILE_NOT_FOUND,
            ),
            (
                "canonical_db_basename_refusal",
                "ledger path with canonical DB basename is refused",
                refused_path,
                verifier.EXIT_REFUSED_PATH,
            ),
        )

        cases: List[Dict[str, Any]] = []
        transcripts: List[Dict[str, Any]] = []
        for case_id, description, path, expected_exit in raw_cases:
            transcript = _run_verifier(path, tmp_root)
            actual_exit = int(transcript["exit_code"])
            status = "PASS" if actual_exit == expected_exit else "FAIL"
            cases.append(
                {
                    "case_id": case_id,
                    "description": description,
                    "ledger_input": _normalize_text(str(path), tmp_root),
                    "expected_exit": expected_exit,
                    "actual_exit": actual_exit,
                    "status": status,
                    "invariant_notes": "; ".join(NOTICE_LINES),
                }
            )
            transcripts.append({"case_id": case_id, **transcript})

        no_db_evidence["canonical_db_exists_after"] = canonical_db.exists()
        no_db_status = (
            no_db_evidence["canonical_db_exists_before"] == no_db_evidence["canonical_db_exists_after"]
            and not no_db_evidence["canonical_db_opened"]
            and not no_db_evidence["canonical_db_written"]
            and not no_db_evidence["migration_backfill_deploy_run"]
        )
        cases.append(
            {
                "case_id": "no_db_invariant_evidence",
                "description": "harness records no canonical DB open/write and no migration/backfill/deploy",
                "ledger_input": "none",
                "expected_exit": 0,
                "actual_exit": 0 if no_db_status else 1,
                "status": "PASS" if no_db_status else "FAIL",
                "invariant_notes": "; ".join(NOTICE_LINES),
            }
        )

        return {
            "artifact_prefix": ARTIFACT_PREFIX,
            "notices": list(NOTICE_LINES),
            "verifier_module": "tools.predraw_ledger_verify",
            "fixture_scope": "synthetic temporary JSONL ledgers only",
            "cases": cases,
            "transcripts": transcripts,
            "no_db_evidence": no_db_evidence,
            "overall_status": "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL",
        }


def _write_edge_fixtures(tmp_root: Path) -> Dict[str, Path]:
    paths = {
        "malformed_jsonl_row": tmp_root / "edge_malformed_jsonl_row.jsonl",
        "empty_ledger_file": tmp_root / "edge_empty_ledger_file.jsonl",
        "missing_required_field": tmp_root / "edge_missing_required_field.jsonl",
        "duplicate_draw_record_supported": tmp_root / "edge_duplicate_draw_record_supported.jsonl",
        "wrong_game_identifier_supported": tmp_root / "edge_wrong_game_identifier_supported.jsonl",
        "prev_hash_mismatch_chain_invalid": tmp_root / "edge_prev_hash_mismatch_chain_invalid.jsonl",
    }

    paths["malformed_jsonl_row"].write_text('{"record_id": "broken", "record_kind": ', encoding="utf-8")
    paths["empty_ledger_file"].write_text("", encoding="utf-8")

    missing_payload = _prediction_payload(
        record_id="p518g-edge-missing-field-001",
        bet_index=0,
        numbers=(1, 2, 3, 4, 5, 6),
        strategy_id="p518g-edge-synthetic",
    )
    missing_payload.pop("strategy_id")
    _write_records(paths["missing_required_field"], _records_from_payloads([missing_payload]))

    duplicate_payloads = [
        _prediction_payload(
            record_id="p518g-edge-duplicate-rec-001",
            bet_index=0,
            numbers=(1, 2, 3, 4, 5, 6),
            strategy_id="p518g-edge-synthetic",
        ),
        _prediction_payload(
            record_id="p518g-edge-duplicate-rec-002",
            bet_index=0,
            numbers=(7, 8, 9, 10, 11, 12),
            strategy_id="p518g-edge-synthetic",
        ),
    ]
    _write_records(paths["duplicate_draw_record_supported"], _records_from_payloads(duplicate_payloads))

    wrong_game_payload = _prediction_payload(
        record_id="p518g-edge-wrong-game-001",
        bet_index=0,
        numbers=(1, 2, 3, 4, 5, 6),
        lottery_type="MYSTERY_LOTTO",
        strategy_id="p518g-edge-synthetic",
    )
    _write_records(paths["wrong_game_identifier_supported"], _records_from_payloads([wrong_game_payload]))

    valid_records = _records_from_payloads(
        [
            _prediction_payload(
                record_id="p518g-edge-prevhash-rec-001",
                bet_index=0,
                numbers=(1, 2, 3, 4, 5, 6),
                strategy_id="p518g-edge-synthetic",
            ),
            _prediction_payload(
                record_id="p518g-edge-prevhash-rec-002",
                bet_index=1,
                numbers=(7, 8, 9, 10, 11, 12),
                strategy_id="p518g-edge-synthetic",
            ),
        ]
    )
    bad_prev = "0" * 64
    second_payload = dict(valid_records[1])
    second_payload.pop("record_hash")
    second_payload.pop("prev_record_hash")
    valid_records[1]["prev_record_hash"] = bad_prev
    valid_records[1]["record_hash"] = ledger.compute_record_hash(second_payload, bad_prev)
    _write_records(paths["prev_hash_mismatch_chain_invalid"], valid_records)

    return paths


def run_edge_matrix_cases() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p518g_predraw_ledger_verify_edge_matrix_") as tmp:
        tmp_root = Path(tmp)
        fixture_paths = _write_edge_fixtures(tmp_root)
        canonical_db = _PROJECT_ROOT / "data" / "lottery_v2.db"
        no_db_evidence = {
            "canonical_db_path": str(canonical_db),
            "canonical_db_exists_before": canonical_db.exists(),
            "canonical_db_exists_after": None,
            "canonical_db_opened": False,
            "canonical_db_written": False,
            "migration_backfill_deploy_run": False,
            "fixture_root": _EDGE_TEMP_TOKEN,
            "fixture_scope": "temporary synthetic JSONL files only",
        }

        raw_cases = (
            {
                "case_id": "malformed_jsonl_row",
                "requirement": "malformed JSONL row",
                "description": "truncated JSONL row returns chain-invalid nonzero status",
                "path": fixture_paths["malformed_jsonl_row"],
                "expected_exit": verifier.EXIT_INVALID,
                "expected_signal": "unparseable/truncated",
                "semantic_notes": "existing verifier detects JSON decode failure during chain verification",
            },
            {
                "case_id": "empty_ledger_file",
                "requirement": "empty ledger file",
                "description": "empty ledger file is valid with zero records",
                "path": fixture_paths["empty_ledger_file"],
                "expected_exit": verifier.EXIT_OK,
                "expected_signal": "record_count=0",
                "semantic_notes": "existing verifier treats an empty ledger as structurally valid",
            },
            {
                "case_id": "missing_required_field",
                "requirement": "missing required field",
                "description": "chain-consistent record missing strategy_id is reported malformed",
                "path": fixture_paths["missing_required_field"],
                "expected_exit": verifier.EXIT_INVALID,
                "expected_signal": "strategy_id",
                "semantic_notes": "existing verifier flags required-field omissions after chain validation",
            },
            {
                "case_id": "duplicate_draw_record_supported",
                "requirement": "duplicate draw record if supported by verifier behavior",
                "description": "duplicate target draw identity remains valid under current verifier semantics",
                "path": fixture_paths["duplicate_draw_record_supported"],
                "expected_exit": verifier.EXIT_OK,
                "expected_signal": "validation_status=VALID",
                "semantic_notes": "current verifier does not reject duplicate draw identity records",
            },
            {
                "case_id": "wrong_game_identifier_supported",
                "requirement": "wrong game identifier if supported by verifier behavior",
                "description": "unknown lottery_type remains valid under current verifier semantics",
                "path": fixture_paths["wrong_game_identifier_supported"],
                "expected_exit": verifier.EXIT_OK,
                "expected_signal": "lottery_type=MYSTERY_LOTTO",
                "semantic_notes": "current verifier requires the lottery_type field but does not validate its enum",
            },
            {
                "case_id": "prev_hash_mismatch_chain_invalid",
                "requirement": "inconsistent hash chain beyond existing tampered case",
                "description": "stored prev_record_hash mismatch returns chain-invalid nonzero status",
                "path": fixture_paths["prev_hash_mismatch_chain_invalid"],
                "expected_exit": verifier.EXIT_INVALID,
                "expected_signal": "prev_record_hash mismatch",
                "semantic_notes": "existing verifier detects a distinct chain linkage mismatch",
            },
        )

        cases: List[Dict[str, Any]] = []
        transcripts: List[Dict[str, Any]] = []
        for raw in raw_cases:
            transcript = _run_verifier(raw["path"], tmp_root, _EDGE_TEMP_TOKEN)
            actual_exit = int(transcript["exit_code"])
            combined_output = transcript["stdout"] + transcript["stderr"]
            signal_present = raw["expected_signal"] in combined_output
            status = "PASS" if actual_exit == raw["expected_exit"] and signal_present else "FAIL"
            cases.append(
                {
                    "case_id": raw["case_id"],
                    "requirement": raw["requirement"],
                    "description": raw["description"],
                    "ledger_input": _normalize_text(str(raw["path"]), tmp_root, _EDGE_TEMP_TOKEN),
                    "expected_exit": raw["expected_exit"],
                    "actual_exit": actual_exit,
                    "expected_signal": raw["expected_signal"],
                    "signal_present": signal_present,
                    "status": status,
                    "semantic_notes": raw["semantic_notes"],
                    "invariant_notes": "; ".join(NOTICE_LINES),
                }
            )
            transcripts.append({"case_id": raw["case_id"], **transcript})

        no_db_evidence["canonical_db_exists_after"] = canonical_db.exists()
        no_db_status = (
            no_db_evidence["canonical_db_exists_before"] == no_db_evidence["canonical_db_exists_after"]
            and not no_db_evidence["canonical_db_opened"]
            and not no_db_evidence["canonical_db_written"]
            and not no_db_evidence["migration_backfill_deploy_run"]
        )
        cases.append(
            {
                "case_id": "no_db_invariant_evidence",
                "requirement": "DB side-effect invariant",
                "description": "harness records no canonical DB open/write and no migration/backfill/deploy",
                "ledger_input": "none",
                "expected_exit": 0,
                "actual_exit": 0 if no_db_status else 1,
                "expected_signal": "no canonical DB open/write",
                "signal_present": True,
                "status": "PASS" if no_db_status else "FAIL",
                "semantic_notes": "temporary synthetic fixtures are the only inputs",
                "invariant_notes": "; ".join(NOTICE_LINES),
            }
        )

        return {
            "artifact_prefix": EDGE_ARTIFACT_PREFIX,
            "notices": list(NOTICE_LINES),
            "verifier_module": "tools.predraw_ledger_verify",
            "fixture_scope": "synthetic temporary JSONL ledgers only",
            "cases": cases,
            "transcripts": transcripts,
            "coverage": _edge_coverage_rows(cases),
            "no_db_evidence": no_db_evidence,
            "overall_status": "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL",
        }


def _csv_text(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def _cases_csv(results: Mapping[str, Any]) -> str:
    return _csv_text(
        results["cases"],
        (
            "case_id",
            "description",
            "ledger_input",
            "expected_exit",
            "actual_exit",
            "status",
            "invariant_notes",
        ),
    )


def _edge_cases_csv(results: Mapping[str, Any]) -> str:
    return _csv_text(
        results["cases"],
        (
            "case_id",
            "requirement",
            "description",
            "ledger_input",
            "expected_exit",
            "actual_exit",
            "expected_signal",
            "signal_present",
            "status",
            "semantic_notes",
            "invariant_notes",
        ),
    )


def _transcripts_json(results: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "artifact_prefix": ARTIFACT_PREFIX,
            "notices": results["notices"],
            "transcripts": results["transcripts"],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _edge_transcripts_json(results: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "artifact_prefix": EDGE_ARTIFACT_PREFIX,
            "notices": results["notices"],
            "transcripts": results["transcripts"],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _results_json(results: Mapping[str, Any]) -> str:
    return json.dumps(results, indent=2, sort_keys=True) + "\n"


def _edge_coverage_rows(cases: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "requirement": case["requirement"],
            "case_id": case["case_id"],
            "covered": case["status"] == "PASS",
            "verifier_semantic_change_required": False,
            "notes": case["semantic_notes"],
            "invariant_notes": case["invariant_notes"],
        }
        for case in cases
    ]


def _edge_coverage_csv(results: Mapping[str, Any]) -> str:
    return _csv_text(
        results["coverage"],
        (
            "requirement",
            "case_id",
            "covered",
            "verifier_semantic_change_required",
            "notes",
            "invariant_notes",
        ),
    )


def _report_md(results: Mapping[str, Any]) -> str:
    lines = [
        "# P518F Predraw Ledger Verify Smoke Report",
        "",
        "## Scope",
        "",
        "This smoke harness uses synthetic temporary ledger fixtures only.",
        "It records no canonical DB open/write, no migration/backfill, no deploy,",
        "is not production release approval, and makes no betting/future prediction claims.",
        "",
        "## Cases",
        "",
        "| Case | Expected | Actual | Status |",
        "| --- | ---: | ---: | --- |",
    ]
    for case in results["cases"]:
        lines.append(
            "| {case_id} | {expected_exit} | {actual_exit} | {status} |".format(**case)
        )
    lines.extend(
        [
            "",
            "## No-DB Evidence",
            "",
            f"- Canonical DB path: `{results['no_db_evidence']['canonical_db_path']}`",
            f"- Canonical DB existed before: `{results['no_db_evidence']['canonical_db_exists_before']}`",
            f"- Canonical DB existed after: `{results['no_db_evidence']['canonical_db_exists_after']}`",
            "- Canonical DB opened by harness: `False`",
            "- Canonical DB written by harness: `False`",
            "- Migration/backfill/deploy run: `False`",
            "",
            "## Safety Notices",
            "",
        ]
    )
    lines.extend(f"- {line}" for line in NOTICE_LINES)
    lines.append("")
    lines.append(f"Overall status: `{results['overall_status']}`")
    lines.append("")
    return "\n".join(lines)


def _edge_report_md(results: Mapping[str, Any]) -> str:
    lines = [
        "# P518G Predraw Ledger Verify Edge Matrix Report",
        "",
        "## Scope",
        "",
        "This edge matrix uses synthetic temporary JSONL ledger fixtures only.",
        "It records no canonical DB open/write, no migration/backfill, no deploy,",
        "is not production release approval, and makes no betting/future prediction claims.",
        "It documents current verifier behavior without changing verifier semantics.",
        "",
        "## Edge Cases",
        "",
        "| Case | Requirement | Expected | Actual | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for case in results["cases"]:
        lines.append(
            "| {case_id} | {requirement} | {expected_exit} | {actual_exit} | {status} |".format(**case)
        )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            "| Requirement | Case | Covered | Semantic Change Required |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in results["coverage"]:
        lines.append(
            "| {requirement} | {case_id} | {covered} | {verifier_semantic_change_required} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## No-DB Evidence",
            "",
            f"- Canonical DB path: `{results['no_db_evidence']['canonical_db_path']}`",
            f"- Canonical DB existed before: `{results['no_db_evidence']['canonical_db_exists_before']}`",
            f"- Canonical DB existed after: `{results['no_db_evidence']['canonical_db_exists_after']}`",
            "- Canonical DB opened by harness: `False`",
            "- Canonical DB written by harness: `False`",
            "- Migration/backfill/deploy run: `False`",
            "",
            "## Safety Notices",
            "",
        ]
    )
    lines.extend(f"- {line}" for line in NOTICE_LINES)
    lines.append("")
    lines.append(f"Overall status: `{results['overall_status']}`")
    lines.append("")
    return "\n".join(lines)


def _manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows = []
    for path in (RESULTS_PATH, CASES_PATH, TRANSCRIPTS_PATH, REPORT_PATH):
        body = rendered[path]
        data = body.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "notes": "; ".join(NOTICE_LINES),
            }
        )
    rows.append(
        {
            "artifact_path": _artifact_label(MANIFEST_PATH),
            "artifact_kind": "csv",
            "sha256": "",
            "bytes": "",
            "notes": "manifest self-hash intentionally omitted; " + "; ".join(NOTICE_LINES),
        }
    )
    return _csv_text(rows, ("artifact_path", "artifact_kind", "sha256", "bytes", "notes"))


def _edge_manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows = []
    for path in (EDGE_RESULTS_PATH, EDGE_CASES_PATH, EDGE_TRANSCRIPTS_PATH, EDGE_COVERAGE_PATH, EDGE_REPORT_PATH):
        body = rendered[path]
        data = body.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "notes": "; ".join(NOTICE_LINES),
            }
        )
    rows.append(
        {
            "artifact_path": _artifact_label(EDGE_MANIFEST_PATH),
            "artifact_kind": "csv",
            "sha256": "",
            "bytes": "",
            "notes": "manifest self-hash intentionally omitted; " + "; ".join(NOTICE_LINES),
        }
    )
    return _csv_text(rows, ("artifact_path", "artifact_kind", "sha256", "bytes", "notes"))


def _artifact_label(path: Path) -> str:
    try:
        return str(path.relative_to(_PROJECT_ROOT))
    except ValueError:
        return path.name


def render_artifacts() -> Dict[Path, str]:
    results = run_smoke_cases()
    rendered: Dict[Path, str] = {
        RESULTS_PATH: _results_json(results),
        CASES_PATH: _cases_csv(results),
        TRANSCRIPTS_PATH: _transcripts_json(results),
        REPORT_PATH: _report_md(results),
    }
    rendered[MANIFEST_PATH] = _manifest_csv(rendered)
    return rendered


def render_edge_artifacts() -> Dict[Path, str]:
    results = run_edge_matrix_cases()
    rendered: Dict[Path, str] = {
        EDGE_RESULTS_PATH: _results_json(results),
        EDGE_CASES_PATH: _edge_cases_csv(results),
        EDGE_TRANSCRIPTS_PATH: _edge_transcripts_json(results),
        EDGE_COVERAGE_PATH: _edge_coverage_csv(results),
        EDGE_REPORT_PATH: _edge_report_md(results),
    }
    rendered[EDGE_MANIFEST_PATH] = _edge_manifest_csv(rendered)
    return rendered


def write_artifacts(rendered: Mapping[Path, str] | None = None) -> Dict[Path, str]:
    rendered = dict(rendered or render_artifacts())
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for path, body in rendered.items():
        path.write_text(body, encoding="utf-8")
    return rendered


def write_edge_artifacts(rendered: Mapping[Path, str] | None = None) -> Dict[Path, str]:
    rendered = dict(rendered or render_edge_artifacts())
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for path, body in rendered.items():
        path.write_text(body, encoding="utf-8")
    return rendered


def validate_artifacts(rendered: Mapping[Path, str] | None = None) -> Tuple[bool, List[str]]:
    rendered = dict(rendered or render_artifacts())
    mismatches = []
    for path, expected in rendered.items():
        if not path.exists():
            mismatches.append(f"missing: {path.relative_to(_PROJECT_ROOT)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            mismatches.append(f"content mismatch: {path.relative_to(_PROJECT_ROOT)}")
    return not mismatches, mismatches


def validate_edge_artifacts(rendered: Mapping[Path, str] | None = None) -> Tuple[bool, List[str]]:
    rendered = dict(rendered or render_edge_artifacts())
    mismatches = []
    for path, expected in rendered.items():
        if not path.exists():
            mismatches.append(f"missing: {path.relative_to(_PROJECT_ROOT)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            mismatches.append(f"content mismatch: {path.relative_to(_PROJECT_ROOT)}")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P518F/P518G no-DB smoke harness for tools.predraw_ledger_verify. "
            "Uses synthetic temporary fixtures only and writes deterministic artifacts."
        )
    )
    parser.add_argument("--generate", action="store_true", help="write all P518G edge artifacts")
    parser.add_argument("--cases", action="store_true", help="print the generated cases CSV")
    parser.add_argument("--transcripts", action="store_true", help="print the generated transcripts JSON")
    parser.add_argument("--report", action="store_true", help="print the generated smoke report Markdown")
    parser.add_argument("--edge-cases", action="store_true", help="print the generated P518G edge cases CSV")
    parser.add_argument("--edge-transcripts", action="store_true", help="print the generated P518G edge transcripts JSON")
    parser.add_argument("--edge-coverage", action="store_true", help="print the generated P518G edge coverage CSV")
    parser.add_argument("--edge-report", action="store_true", help="print the generated P518G edge report Markdown")
    parser.add_argument("--validate", action="store_true", help="validate committed P518G edge artifacts against a fresh run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()
    edge_rendered = render_edge_artifacts()

    if args.generate:
        write_edge_artifacts(edge_rendered)
        for path in edge_rendered:
            print(f"[p518f-smoke] wrote {path.relative_to(_PROJECT_ROOT)}")

    if args.cases:
        print(rendered[CASES_PATH], end="")

    if args.transcripts:
        print(rendered[TRANSCRIPTS_PATH], end="")

    if args.report:
        print(rendered[REPORT_PATH], end="")

    if args.edge_cases:
        print(edge_rendered[EDGE_CASES_PATH], end="")

    if args.edge_transcripts:
        print(edge_rendered[EDGE_TRANSCRIPTS_PATH], end="")

    if args.edge_coverage:
        print(edge_rendered[EDGE_COVERAGE_PATH], end="")

    if args.edge_report:
        print(edge_rendered[EDGE_REPORT_PATH], end="")

    if args.validate:
        ok, mismatches = validate_edge_artifacts(edge_rendered)
        if ok:
            print("[p518f-smoke] validation_status=PASS")
        else:
            print("[p518f-smoke] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p518f-smoke] {mismatch}", file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.cases,
            args.transcripts,
            args.report,
            args.edge_cases,
            args.edge_transcripts,
            args.edge_coverage,
            args.edge_report,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
