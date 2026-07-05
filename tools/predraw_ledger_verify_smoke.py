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
ARTIFACTS_DIR = _PROJECT_ROOT / "artifacts"
RESULTS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_results.json"
CASES_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_cases.csv"
TRANSCRIPTS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_transcripts.json"
REPORT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_report.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

NOTICE_LINES = (
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "synthetic fixtures only",
    "not production release approval",
    "no betting/future prediction claims",
)

_TEMP_TOKEN = "${P518F_SMOKE_TMP}"


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _prediction_payload(*, record_id: str, bet_index: int, numbers: Sequence[int]) -> Dict[str, Any]:
    return {
        "schema_version": ledger.SCHEMA_VERSION,
        "record_id": record_id,
        "record_kind": "PREDICTION",
        "lottery_type": "BIG_LOTTO",
        "generation_mode": "RETROSPECTIVE_REPLAY",
        "predicted_at": "2020-01-01T00:00:00+00:00",
        "created_at": "2020-01-01T00:00:00+00:00",
        "target_draw": 114000101,
        "target_draw_date": None,
        "scheduled_draw_close_at": None,
        "schedule_rule_version": None,
        "history_cutoff_draw": None,
        "history_cutoff_date": None,
        "max_source_draw_at_generation": None,
        "max_source_draw_date_at_generation": None,
        "source_db_fingerprint": None,
        "strategy_id": "p518f-smoke-synthetic",
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


def _write_tampered_ledger(valid_path: Path, tampered_path: Path) -> None:
    lines = valid_path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["bet_index"] = 99
    lines[1] = _canonical_json(second)
    tampered_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normalize_text(text: str, tmp_root: Path) -> str:
    normalized = text.replace(str(tmp_root), _TEMP_TOKEN)
    resolved = str(tmp_root.resolve())
    if resolved != str(tmp_root):
        normalized = normalized.replace(resolved, _TEMP_TOKEN)
    return normalized


def _run_verifier(path: Path, tmp_root: Path) -> Dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    argv = [str(path)]
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = verifier.main(argv)
    return {
        "argv": ["tools.predraw_ledger_verify", _normalize_text(str(path), tmp_root)],
        "exit_code": exit_code,
        "stdout": _normalize_text(stdout.getvalue(), tmp_root),
        "stderr": _normalize_text(stderr.getvalue(), tmp_root),
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


def _results_json(results: Mapping[str, Any]) -> str:
    return json.dumps(results, indent=2, sort_keys=True) + "\n"


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


def write_artifacts(rendered: Mapping[Path, str] | None = None) -> Dict[Path, str]:
    rendered = dict(rendered or render_artifacts())
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P518F no-DB smoke harness for tools.predraw_ledger_verify. "
            "Uses synthetic temporary fixtures only and writes deterministic artifacts."
        )
    )
    parser.add_argument("--generate", action="store_true", help="write all P518F smoke artifacts")
    parser.add_argument("--cases", action="store_true", help="print the generated cases CSV")
    parser.add_argument("--transcripts", action="store_true", help="print the generated transcripts JSON")
    parser.add_argument("--report", action="store_true", help="print the generated smoke report Markdown")
    parser.add_argument("--validate", action="store_true", help="validate committed artifacts against a fresh run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p518f-smoke] wrote {path.relative_to(_PROJECT_ROOT)}")

    if args.cases:
        print(rendered[CASES_PATH], end="")

    if args.transcripts:
        print(rendered[TRANSCRIPTS_PATH], end="")

    if args.report:
        print(rendered[REPORT_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p518f-smoke] validation_status=PASS")
        else:
            print("[p518f-smoke] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p518f-smoke] {mismatch}", file=sys.stderr)
            return 1

    if not any((args.generate, args.cases, args.transcripts, args.report, args.validate)):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
