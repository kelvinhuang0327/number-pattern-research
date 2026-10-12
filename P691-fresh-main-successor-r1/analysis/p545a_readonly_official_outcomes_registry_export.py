"""Export a deterministic official-outcome registry from committed JSON artifacts.

P545A is a research-evidence task.  Its only outcome source is the P268D1
JSONL blob at a pinned Git commit.  P273A supplies the requested draw universe
and P543C supplies an independent BIG_LOTTO outcome cross-check.  The module
has no alternate source, service, or mutable-data path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "p545a_readonly_official_outcomes_registry.v1"
TASK_ID = "P545A_R2_EXPORT_FROM_COMMITTED_NON_DB_OUTCOME_SOURCE"
CLASSIFICATION = "research_only_committed_official_outcome_registry"
PINNED_COMMIT = "fead482e4ffbc501ea07928e338d2416ba3bd126"

P268D1_PATH = "outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"
P273A_PATH = "outputs/research/p273a_distinct_ticket_identity_20260615.json"
P543C_PATH = "outputs/research/p543c_candidate_per_draw_validation_contract_20260710.json"

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "p268d1": {
        "source_id": "p268d1",
        "role": "sole_official_outcome_source",
        "path": P268D1_PATH,
        "sha256": "f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8",
        "byte_size": 7_745_520,
        "format": "jsonl",
    },
    "p273a": {
        "source_id": "p273a",
        "role": "requested_draw_manifest",
        "path": P273A_PATH,
        "sha256": "b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0",
        "byte_size": 26_707_364,
        "format": "json",
    },
    "p543c": {
        "source_id": "p543c",
        "role": "independent_outcome_cross_check",
        "path": P543C_PATH,
        "sha256": "71be8549daddbc0e810e17e3e6afbd49eedc02eee402c017e562a834ef1448a5",
        "byte_size": 515_478,
        "format": "json",
    },
}

LOTTERIES = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")
EXPECTED_SOURCE_COUNTS = {
    "BIG_LOTTO": 2_139,
    "DAILY_539": 5_876,
    "POWER_LOTTO": 1_915,
}
EXPECTED_SOURCE_RANGES = {
    "BIG_LOTTO": ("96000001", "115000057"),
    "DAILY_539": ("96000001", "115000132"),
    "POWER_LOTTO": ("97000001", "115000043"),
}
EXPECTED_REQUEST_COUNTS = {
    "BIG_LOTTO": 752,
    "DAILY_539": 750,
    "POWER_LOTTO": 750,
}
EXPECTED_SOURCE_RELEVANT_RECORDS = 9_930
EXPECTED_REQUESTED_RECORDS = 2_252
EXPECTED_P543C_ROWS = 500
EXPECTED_P543C_CANDIDATES = 10
EXPECTED_P543C_ROWS_PER_CANDIDATE = 50
EXPECTED_P543C_UNIQUE_DRAWS = 52


class P545AError(RuntimeError):
    """Base class for fail-closed P545A errors."""


class InputArtifactError(P545AError):
    """A pinned source is unavailable, malformed, or has unexpected bytes."""


class SourceIntegrityError(P545AError):
    """The committed P268D1 source violates the adapter contract."""


class RequestManifestError(P545AError):
    """The P273A/P543C requested universe or shape drifted."""


class CoverageError(P545AError):
    """The committed outcome source does not cover the requested universe."""


class P543CCrossCheckError(P545AError):
    """P543C primary outcome fields disagree with the registry."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    """Digest the complete canonical payload except its digest field."""
    canonical = dict(payload)
    canonical.pop("canonical_payload_digest", None)
    return _sha256_bytes(_canonical_bytes(canonical))


def record_digest(record: Mapping[str, Any]) -> str:
    """Digest a normalized registry record except its digest field."""
    canonical = dict(record)
    canonical.pop("record_sha256", None)
    return _sha256_bytes(_canonical_bytes(canonical))


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _strict_json_loads(raw: bytes | str, label: str) -> Any:
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonstandard_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InputArtifactError(f"{label} is not strict UTF-8 JSON: {exc}") from exc


def decode_json_object(raw: bytes, label: str) -> Mapping[str, Any]:
    decoded = _strict_json_loads(raw, label)
    if not isinstance(decoded, Mapping):
        raise InputArtifactError(f"{label} must contain a JSON object")
    return decoded


def verify_source_bytes(spec: Mapping[str, Any], raw: bytes) -> dict[str, Any]:
    actual_sha = _sha256_bytes(raw)
    actual_size = len(raw)
    if actual_sha != spec["sha256"]:
        raise InputArtifactError(
            f"{spec['source_id']} SHA-256 changed: expected {spec['sha256']}, observed {actual_sha}"
        )
    if actual_size != spec["byte_size"]:
        raise InputArtifactError(
            f"{spec['source_id']} byte size changed: expected {spec['byte_size']}, observed {actual_size}"
        )
    return {"sha256": actual_sha, "byte_size": actual_size}


class GitBlobSource:
    """Explicit reader for raw local Git object bytes at one pinned commit."""

    def __init__(self, repo_root: Path, commit: str = PINNED_COMMIT):
        if not repo_root.is_absolute():
            raise InputArtifactError("repo_root must be absolute")
        self.repo_root = repo_root
        self.commit = commit

    def read(self, path: str) -> bytes:
        result = subprocess.run(
            ["git", "cat-file", "blob", f"{self.commit}:{path}"],
            cwd=self.repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise InputArtifactError(
                f"unable to read committed blob {self.commit}:{path}: {detail}"
            )
        return result.stdout


def commit_timestamp_utc(repo_root: Path, commit: str) -> str:
    result = subprocess.run(
        ["git", "show", "-s", "--format=%cI", commit],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise InputArtifactError(
            f"unable to read committer timestamp for {commit}: {result.stderr.strip()}"
        )
    try:
        parsed = datetime.fromisoformat(result.stdout.strip())
    except ValueError as exc:
        raise InputArtifactError("pinned commit has an invalid committer timestamp") from exc
    if parsed.tzinfo is None:
        raise InputArtifactError("pinned commit committer timestamp has no timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat(
        timespec="seconds"
    )


def normalize_lottery_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputArtifactError(f"invalid lottery type: {value!r}")
    token = re.sub(r"[\s-]+", "_", value.strip().upper())
    aliases = {
        "BIGLOTTO": "BIG_LOTTO",
        "BIG_LOTTO": "BIG_LOTTO",
        "DAILY539": "DAILY_539",
        "DAILY_539": "DAILY_539",
        "POWERLOTTO": "POWER_LOTTO",
        "POWER_LOTTO": "POWER_LOTTO",
    }
    normalized = aliases.get(token)
    if normalized is None:
        raise InputArtifactError(f"unsupported lottery type: {value!r}")
    return normalized


def normalize_draw_text(value: Any) -> tuple[str, int]:
    if isinstance(value, bool) or value is None:
        raise InputArtifactError(f"invalid target draw: {value!r}")
    text = str(value).strip()
    if not text or not text.isdigit():
        raise InputArtifactError(f"target draw must be decimal text: {value!r}")
    return text, int(text)


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceIntegrityError(f"{label} must be an integer")
    return value


def _integer_sequence(value: Any, label: str) -> list[int]:
    if not isinstance(value, list):
        raise SourceIntegrityError(f"{label} must be an array")
    return [_integer(item, f"{label} item") for item in value]


def normalize_date_component(value: Any) -> str:
    if not isinstance(value, str) or len(value.strip()) < 10:
        raise SourceIntegrityError("draw_date must contain an ISO date")
    candidate = value.strip()[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError as exc:
        raise SourceIntegrityError("draw_date must begin with YYYY-MM-DD") from exc


def validate_outcome_sequences(
    lottery_type: str,
    draw_number_size: Any,
    draw_number_appear: Any,
) -> tuple[list[int], int | None, int | None, list[int]]:
    """Validate P268D1 sequences and return normalized outcome fields."""
    lottery = normalize_lottery_type(lottery_type)
    size = _integer_sequence(draw_number_size, "drawNumberSize")
    appear = _integer_sequence(draw_number_appear, "drawNumberAppear")

    expected_length = 5 if lottery == "DAILY_539" else 7
    if len(size) != expected_length:
        raise SourceIntegrityError(
            f"{lottery} drawNumberSize requires {expected_length} values"
        )
    if len(appear) != expected_length:
        raise SourceIntegrityError(
            f"{lottery} drawNumberAppear is missing an outcome value"
        )

    main_size = size if lottery == "DAILY_539" else size[:6]
    main_appear = appear if lottery == "DAILY_539" else appear[:6]
    if len(main_size) != len(set(main_size)):
        raise SourceIntegrityError(f"{lottery} main numbers must be unique")

    upper = {"DAILY_539": 39, "BIG_LOTTO": 49, "POWER_LOTTO": 38}[lottery]
    if any(number < 1 or number > upper for number in main_size):
        raise SourceIntegrityError(f"{lottery} main number is outside 1..{upper}")
    if sorted(main_appear) != sorted(main_size):
        raise SourceIntegrityError(
            f"{lottery} drawNumberAppear main values disagree with drawNumberSize"
        )

    main = sorted(main_size)
    if lottery == "DAILY_539":
        return main, None, None, appear

    auxiliary = size[6]
    if appear[6] != auxiliary:
        raise SourceIntegrityError(
            f"{lottery} drawNumberAppear auxiliary value disagrees with drawNumberSize"
        )
    if lottery == "BIG_LOTTO":
        if auxiliary < 1 or auxiliary > 49:
            raise SourceIntegrityError("BIG_LOTTO special number is outside 1..49")
        if auxiliary in main:
            raise SourceIntegrityError(
                "BIG_LOTTO special number duplicates a main number"
            )
        return main, auxiliary, None, appear

    if auxiliary < 1 or auxiliary > 8:
        raise SourceIntegrityError("POWER_LOTTO second-zone number is outside 1..8")
    return main, None, auxiliary, appear


def _source_core(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "draw_date": row["draw_date"],
        "main_numbers": row["main_numbers"],
        "special_number": row["special_number"],
        "second_zone_number": row["second_zone_number"],
    }


def parse_p268d1_jsonl(
    raw: bytes,
    *,
    require_expected_shape: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse and fully validate relevant P268D1 records line by line."""
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputArtifactError("P268D1 is not UTF-8 JSONL") from exc

    physical_lines = raw.split(b"\n")
    if physical_lines and physical_lines[-1] == b"":
        physical_lines.pop()
    if not physical_lines:
        raise SourceIntegrityError("P268D1 JSONL is empty")

    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    all_lottery_counts: Counter[str] = Counter()
    observed_key_shapes: Counter[tuple[str, ...]] = Counter()

    for line_number, raw_line in enumerate(physical_lines, start=1):
        if not raw_line.strip():
            raise SourceIntegrityError(f"blank P268D1 line {line_number}")
        try:
            decoded = _strict_json_loads(raw_line, f"P268D1 line {line_number}")
        except InputArtifactError as exc:
            raise SourceIntegrityError(str(exc)) from exc
        if not isinstance(decoded, Mapping):
            raise SourceIntegrityError(f"P268D1 line {line_number} is not an object")
        observed_key_shapes[tuple(sorted(decoded))] += 1
        source_lottery = decoded.get("lottery_type")
        if not isinstance(source_lottery, str) or not source_lottery:
            raise SourceIntegrityError(
                f"P268D1 line {line_number} lacks lottery_type"
            )
        all_lottery_counts[source_lottery] += 1
        if source_lottery not in LOTTERIES:
            continue

        required = {
            "period",
            "draw_date",
            "drawNumberSize",
            "drawNumberAppear",
        }
        missing = sorted(required - set(decoded))
        if missing:
            raise SourceIntegrityError(
                f"P268D1 line {line_number} lacks fields: {', '.join(missing)}"
            )
        try:
            lottery = normalize_lottery_type(source_lottery)
            target_draw, target_draw_numeric = normalize_draw_text(decoded["period"])
            draw_date = normalize_date_component(decoded["draw_date"])
            main, special, second_zone, appear = validate_outcome_sequences(
                lottery,
                decoded["drawNumberSize"],
                decoded["drawNumberAppear"],
            )
        except (InputArtifactError, SourceIntegrityError) as exc:
            raise SourceIntegrityError(
                f"invalid P268D1 line {line_number}: {exc}"
            ) from exc

        normalized = {
            "lottery_type": lottery,
            "target_draw": target_draw,
            "target_draw_numeric": target_draw_numeric,
            "draw_date": draw_date,
            "main_numbers": main,
            "special_number": special,
            "second_zone_number": second_zone,
            "source_line_number": line_number,
            "source_period": decoded["period"],
            "source_draw_date": decoded["draw_date"],
            "source_draw_number_appear": appear,
        }
        key = (lottery, target_draw)
        previous = rows_by_key.get(key)
        if previous is not None:
            if _source_core(previous) == _source_core(normalized):
                raise SourceIntegrityError(
                    f"duplicate identical P268D1 key {lottery}/{target_draw}"
                )
            raise SourceIntegrityError(
                f"conflicting P268D1 key {lottery}/{target_draw}"
            )
        rows_by_key[key] = normalized

    rows = sorted(
        rows_by_key.values(),
        key=lambda row: (
            row["lottery_type"],
            row["target_draw_numeric"],
            row["target_draw"],
        ),
    )
    by_lottery: dict[str, dict[str, Any]] = {}
    for lottery in LOTTERIES:
        selected = [row for row in rows if row["lottery_type"] == lottery]
        by_lottery[lottery] = {
            "record_count": len(selected),
            "unique_key_count": len(
                {(row["lottery_type"], row["target_draw"]) for row in selected}
            ),
            "earliest_draw": selected[0]["target_draw"] if selected else None,
            "latest_draw": selected[-1]["target_draw"] if selected else None,
            "earliest_date": min((row["draw_date"] for row in selected), default=None),
            "latest_date": max((row["draw_date"] for row in selected), default=None),
        }

    summary = {
        "parsed_line_count": len(physical_lines),
        "relevant_record_count": len(rows),
        "ignored_non_target_record_count": len(physical_lines) - len(rows),
        "all_source_lottery_counts": dict(sorted(all_lottery_counts.items())),
        "observed_record_key_shapes": [
            {"keys": list(shape), "record_count": count}
            for shape, count in sorted(observed_key_shapes.items())
        ],
        "by_lottery": by_lottery,
        "duplicate_identical_key_count": 0,
        "conflicting_key_count": 0,
        "malformed_record_count": 0,
        "invalid_date_count": 0,
        "invalid_number_count": 0,
        "invalid_number_range_count": 0,
        "duplicate_number_count": 0,
        "missing_auxiliary_outcome_count": 0,
        "draw_number_appear_checked_count": len(rows),
        "draw_number_appear_mismatch_count": 0,
        "stable_numeric_draw_ordering": True,
        "normalized_record_order": "lottery_type, numeric target_draw, text target_draw",
        "integrity_passed": True,
    }

    if require_expected_shape:
        observed_counts = {
            lottery: by_lottery[lottery]["record_count"] for lottery in LOTTERIES
        }
        observed_ranges = {
            lottery: (
                by_lottery[lottery]["earliest_draw"],
                by_lottery[lottery]["latest_draw"],
            )
            for lottery in LOTTERIES
        }
        if len(rows) != EXPECTED_SOURCE_RELEVANT_RECORDS:
            raise SourceIntegrityError(
                f"relevant P268D1 count changed: {len(rows)}"
            )
        if observed_counts != EXPECTED_SOURCE_COUNTS:
            raise SourceIntegrityError(
                f"P268D1 lottery counts changed: {observed_counts}"
            )
        if observed_ranges != EXPECTED_SOURCE_RANGES:
            raise SourceIntegrityError(
                f"P268D1 draw ranges changed: {observed_ranges}"
            )
    return rows, summary


def _counts_by_lottery(keys: set[tuple[str, str]]) -> dict[str, int]:
    counts = Counter(lottery for lottery, _draw in keys)
    return {lottery: counts.get(lottery, 0) for lottery in LOTTERIES}


def extract_requested_draws(
    p273a: Mapping[str, Any],
    p543c: Mapping[str, Any],
    *,
    require_expected_shape: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cells = p273a.get("cells")
    if not isinstance(cells, list):
        raise RequestManifestError("P273A cells must be a list")
    contract = p543c.get("contract")
    if not isinstance(contract, Mapping) or not isinstance(contract.get("rows"), list):
        raise RequestManifestError("P543C contract.rows must be a list")

    flags: dict[tuple[str, str], dict[str, Any]] = {}
    p273a_keys: set[tuple[str, str]] = set()
    for cell in cells:
        if not isinstance(cell, Mapping):
            raise RequestManifestError("P273A cell must be an object")
        lottery = normalize_lottery_type(cell.get("lottery_type"))
        supported = cell.get("supported_draws")
        if not isinstance(supported, list):
            raise RequestManifestError("P273A supported_draws must be a list")
        for row in supported:
            if not isinstance(row, Mapping):
                raise RequestManifestError("P273A supported draw must be an object")
            row_lottery = normalize_lottery_type(row.get("lottery_type", lottery))
            if row_lottery != lottery:
                raise RequestManifestError(
                    "P273A cell and supported-draw lottery types disagree"
                )
            draw, numeric = normalize_draw_text(row.get("target_draw"))
            key = (lottery, draw)
            p273a_keys.add(key)
            flags.setdefault(
                key,
                {
                    "lottery_type": lottery,
                    "target_draw": draw,
                    "target_draw_numeric": numeric,
                    "requested_by_p273a": False,
                    "requested_by_p543c": False,
                },
            )["requested_by_p273a"] = True

    p543c_rows = contract["rows"]
    p543c_keys: set[tuple[str, str]] = set()
    candidate_counts: Counter[str] = Counter()
    candidate_draw_keys: set[tuple[str, str]] = set()
    for row in p543c_rows:
        if not isinstance(row, Mapping):
            raise RequestManifestError("P543C contract row must be an object")
        lottery = normalize_lottery_type(row.get("lottery"))
        if lottery != "BIG_LOTTO":
            raise RequestManifestError("P543C contains a non-BIG_LOTTO row")
        candidate = row.get("candidate_id")
        if not isinstance(candidate, str) or not candidate:
            raise RequestManifestError("P543C candidate_id must be non-empty text")
        draw, numeric = normalize_draw_text(row.get("draw_id"))
        if (candidate, draw) in candidate_draw_keys:
            raise RequestManifestError(
                f"duplicate P543C candidate/draw identity {candidate}/{draw}"
            )
        candidate_draw_keys.add((candidate, draw))
        candidate_counts[candidate] += 1
        key = (lottery, draw)
        p543c_keys.add(key)
        flags.setdefault(
            key,
            {
                "lottery_type": lottery,
                "target_draw": draw,
                "target_draw_numeric": numeric,
                "requested_by_p273a": False,
                "requested_by_p543c": False,
            },
        )["requested_by_p543c"] = True

    union_keys = set(flags)
    overlap = p273a_keys & p543c_keys
    requested = sorted(
        flags.values(),
        key=lambda row: (
            row["lottery_type"],
            row["target_draw_numeric"],
            row["target_draw"],
        ),
    )
    summary = {
        "p273a": {
            "unique_draw_count": len(p273a_keys),
            "by_lottery": _counts_by_lottery(p273a_keys),
        },
        "p543c": {
            "row_count": len(p543c_rows),
            "candidate_count": len(candidate_counts),
            "rows_per_candidate": dict(sorted(candidate_counts.items())),
            "unique_draw_count": len(p543c_keys),
            "by_lottery": _counts_by_lottery(p543c_keys),
        },
        "union_unique_draw_count": len(union_keys),
        "union_by_lottery": _counts_by_lottery(union_keys),
        "source_overlap_unique_draw_count": len(overlap),
        "all_p543c_draws_overlap_p273a": p543c_keys <= p273a_keys,
    }

    if require_expected_shape:
        if summary["p273a"]["by_lottery"] != EXPECTED_REQUEST_COUNTS:
            raise RequestManifestError(
                f"P273A requested counts changed: {summary['p273a']['by_lottery']}"
            )
        if len(union_keys) != EXPECTED_REQUESTED_RECORDS:
            raise RequestManifestError(
                f"requested union count changed: {len(union_keys)}"
            )
        if summary["union_by_lottery"] != EXPECTED_REQUEST_COUNTS:
            raise RequestManifestError(
                f"requested union lottery counts changed: {summary['union_by_lottery']}"
            )
        expected_shape = (
            len(p543c_rows) == EXPECTED_P543C_ROWS
            and len(candidate_counts) == EXPECTED_P543C_CANDIDATES
            and set(candidate_counts.values()) == {EXPECTED_P543C_ROWS_PER_CANDIDATE}
            and len(p543c_keys) == EXPECTED_P543C_UNIQUE_DRAWS
            and len(overlap) == EXPECTED_P543C_UNIQUE_DRAWS
        )
        if not expected_shape:
            raise RequestManifestError(f"P543C shape changed: {summary['p543c']}")
    return requested, summary


def resolve_requested_outcomes(
    source_rows: Sequence[Mapping[str, Any]],
    requested: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_key = {
        (row["lottery_type"], row["target_draw"]): row for row in source_rows
    }
    records: list[dict[str, Any]] = []
    by_lottery: dict[str, dict[str, int]] = {}
    missing_keys: list[str] = []

    for lottery in LOTTERIES:
        lottery_requests = [row for row in requested if row["lottery_type"] == lottery]
        found = 0
        for request in lottery_requests:
            key = (lottery, request["target_draw"])
            source = source_by_key.get(key)
            if source is None:
                missing_keys.append(f"{lottery}/{request['target_draw']}")
                continue
            record = {
                "lottery_type": lottery,
                "target_draw": request["target_draw"],
                "target_draw_numeric": request["target_draw_numeric"],
                "draw_date": source["draw_date"],
                "main_numbers": source["main_numbers"],
                "special_number": source["special_number"],
                "second_zone_number": source["second_zone_number"],
                "requested_by_p273a": request["requested_by_p273a"],
                "requested_by_p543c": request["requested_by_p543c"],
                "source_artifact_path": P268D1_PATH,
                "source_artifact_sha256": SOURCE_SPECS["p268d1"]["sha256"],
                "source_line_number": source["source_line_number"],
                "source_period": source["source_period"],
                "source_draw_date": source["source_draw_date"],
                "source_draw_number_appear": source["source_draw_number_appear"],
                "record_validation_status": "VALID",
            }
            record["record_sha256"] = record_digest(record)
            records.append(record)
            found += 1
        by_lottery[lottery] = {
            "requested": len(lottery_requests),
            "found_valid": found,
            "missing": len(lottery_requests) - found,
            "conflicting": 0,
            "invalid": 0,
        }

    records.sort(
        key=lambda row: (
            row["lottery_type"],
            row["target_draw_numeric"],
            row["target_draw"],
        )
    )
    total = {
        field: sum(summary[field] for summary in by_lottery.values())
        for field in ("requested", "found_valid", "missing", "conflicting", "invalid")
    }
    coverage = {
        "by_lottery": by_lottery,
        "total": total,
        "exact_one_record_per_requested_key": len(records) == len(requested),
        "complete": not missing_keys and len(records) == len(requested),
    }
    if missing_keys or not coverage["complete"]:
        raise CoverageError(
            "committed source coverage incomplete: " + ", ".join(missing_keys[:20])
        )
    return records, coverage


def cross_check_p543c(
    p543c: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    require_expected_shape: bool = True,
) -> dict[str, Any]:
    contract = p543c.get("contract")
    if not isinstance(contract, Mapping) or not isinstance(contract.get("rows"), list):
        raise P543CCrossCheckError("P543C contract.rows must be a list")
    rows = contract["rows"]
    official = {
        (row["lottery_type"], row["target_draw"]): row for row in records
    }
    signatures_by_draw: dict[str, set[bytes]] = defaultdict(set)
    candidates: Counter[str] = Counter()
    main_mismatches = 0
    special_mismatches = 0

    for row in rows:
        if not isinstance(row, Mapping):
            raise P543CCrossCheckError("P543C row must be an object")
        lottery = normalize_lottery_type(row.get("lottery"))
        if lottery != "BIG_LOTTO":
            raise P543CCrossCheckError("P543C row must be BIG_LOTTO")
        draw, _numeric = normalize_draw_text(row.get("draw_id"))
        candidate = row.get("candidate_id")
        if not isinstance(candidate, str) or not candidate:
            raise P543CCrossCheckError("P543C candidate_id must be non-empty text")
        candidates[candidate] += 1
        try:
            main = _integer_sequence(row.get("actual_numbers"), "P543C actual_numbers")
            special = _integer(row.get("special_actual"), "P543C special_actual")
        except SourceIntegrityError as exc:
            raise P543CCrossCheckError(str(exc)) from exc
        main = sorted(main)
        if len(main) != 6 or len(set(main)) != 6 or any(n < 1 or n > 49 for n in main):
            raise P543CCrossCheckError("P543C actual_numbers are invalid")
        if special < 1 or special > 49 or special in main:
            raise P543CCrossCheckError("P543C special_actual is invalid")
        signatures_by_draw[draw].add(
            _canonical_bytes({"main_numbers": main, "special_number": special})
        )
        official_row = official.get((lottery, draw))
        if official_row is None:
            raise P543CCrossCheckError(
                f"registry row missing for P543C {lottery}/{draw}"
            )
        if main != official_row["main_numbers"]:
            main_mismatches += 1
        if special != official_row["special_number"]:
            special_mismatches += 1

    conflicting_draws = sum(
        1 for signatures in signatures_by_draw.values() if len(signatures) > 1
    )
    result = {
        "compared_row_count": len(rows),
        "candidate_count": len(candidates),
        "rows_per_candidate": dict(sorted(candidates.items())),
        "unique_draw_count": len(signatures_by_draw),
        "main_number_mismatch_count": main_mismatches,
        "special_number_mismatch_count": special_mismatches,
        "internally_conflicting_draw_count": conflicting_draws,
        "passed": (
            main_mismatches == 0
            and special_mismatches == 0
            and conflicting_draws == 0
        ),
    }
    if require_expected_shape:
        if (
            len(rows) != EXPECTED_P543C_ROWS
            or len(candidates) != EXPECTED_P543C_CANDIDATES
            or set(candidates.values()) != {EXPECTED_P543C_ROWS_PER_CANDIDATE}
            or len(signatures_by_draw) != EXPECTED_P543C_UNIQUE_DRAWS
        ):
            raise P543CCrossCheckError(f"P543C shape changed: {result}")
    if not result["passed"]:
        raise P543CCrossCheckError(
            "P543C outcome mismatch: "
            f"main={main_mismatches}, special={special_mismatches}, conflicts={conflicting_draws}"
        )
    return result


def _source_schema_identifiers(
    p273a: Mapping[str, Any], p543c: Mapping[str, Any]
) -> tuple[str, str]:
    meta = p273a.get("meta")
    if not isinstance(meta, Mapping) or not isinstance(meta.get("artifact_version"), str):
        raise InputArtifactError("P273A meta.artifact_version is missing")
    classification = p543c.get("classification")
    if not isinstance(classification, str) or not classification:
        raise InputArtifactError("P543C classification is missing")
    return str(meta["artifact_version"]), f"classification:{classification}"


def build_registry(
    *,
    p268d1_raw: bytes,
    p273a_raw: bytes,
    p543c_raw: bytes,
    pinned_repo_commit: str,
    generated_at_utc: str,
    verify_expected_hashes: bool = True,
    require_expected_shape: bool = True,
) -> dict[str, Any]:
    if verify_expected_hashes:
        for source_id, raw in (
            ("p268d1", p268d1_raw),
            ("p273a", p273a_raw),
            ("p543c", p543c_raw),
        ):
            verify_source_bytes(SOURCE_SPECS[source_id], raw)

    p273a = decode_json_object(p273a_raw, "P273A")
    p543c = decode_json_object(p543c_raw, "P543C")
    p273a_schema, p543c_schema = _source_schema_identifiers(p273a, p543c)
    source_rows, source_summary = parse_p268d1_jsonl(
        p268d1_raw, require_expected_shape=require_expected_shape
    )
    requested, requested_summary = extract_requested_draws(
        p273a, p543c, require_expected_shape=require_expected_shape
    )
    records, coverage = resolve_requested_outcomes(source_rows, requested)
    p543c_check = cross_check_p543c(
        p543c, records, require_expected_shape=require_expected_shape
    )

    schemas = {
        "p268d1": "jsonl:lottery_type-period-draw_date-drawNumberSize-drawNumberAppear",
        "p273a": p273a_schema,
        "p543c": p543c_schema,
    }
    source_artifacts = []
    for source_id in ("p268d1", "p273a", "p543c"):
        spec = SOURCE_SPECS[source_id]
        source_artifacts.append(
            {
                "source_id": source_id,
                "role": spec["role"],
                "path": spec["path"],
                "pinned_commit": pinned_repo_commit,
                "sha256": _sha256_bytes(
                    {
                        "p268d1": p268d1_raw,
                        "p273a": p273a_raw,
                        "p543c": p543c_raw,
                    }[source_id]
                ),
                "byte_size": len(
                    {
                        "p268d1": p268d1_raw,
                        "p273a": p273a_raw,
                        "p543c": p543c_raw,
                    }[source_id]
                ),
                "format": spec["format"],
                "schema_identifier": schemas[source_id],
            }
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "pinned_repo_commit": pinned_repo_commit,
        "generated_at_utc": generated_at_utc,
        "generated_at_policy": (
            "pinned input commit committer timestamp normalized to UTC seconds"
        ),
        "source_artifacts": source_artifacts,
        "source_adapter": {
            "adapter_type": "committed_p268d1_jsonl",
            "database_used": False,
            "network_used": False,
            "fallback_allowed": False,
            "input_path": P268D1_PATH,
            "pinned_commit": pinned_repo_commit,
            "raw_sha256": _sha256_bytes(p268d1_raw),
            "byte_size": len(p268d1_raw),
            "parsed_line_count": source_summary["parsed_line_count"],
            "relevant_record_count": source_summary["relevant_record_count"],
            "duplicate_identical_key_count": source_summary[
                "duplicate_identical_key_count"
            ],
            "conflicting_key_count": source_summary["conflicting_key_count"],
            "malformed_record_count": source_summary["malformed_record_count"],
            "invalid_date_count": source_summary["invalid_date_count"],
            "invalid_number_count": source_summary["invalid_number_count"],
            "invalid_number_range_count": source_summary[
                "invalid_number_range_count"
            ],
            "duplicate_number_count": source_summary["duplicate_number_count"],
            "missing_auxiliary_outcome_count": source_summary[
                "missing_auxiliary_outcome_count"
            ],
            "draw_number_appear_checked_count": source_summary[
                "draw_number_appear_checked_count"
            ],
            "draw_number_appear_mismatch_count": source_summary[
                "draw_number_appear_mismatch_count"
            ],
            "draw_number_size_authority": (
                "target_draw outcomes are normalized exclusively from drawNumberSize"
            ),
        },
        "requested_draw_summary": requested_summary,
        "p268d1_source_summary": source_summary,
        "coverage_summary": coverage,
        "p543c_cross_check": p543c_check,
        "records": records,
        "safety": {
            "database_opened": False,
            "database_written": False,
            "network_used": False,
            "upstream_artifact_modified": False,
            "partial_registry_emitted": False,
            "predictive_claim_made": False,
            "betting_advice": False,
            "production_readiness_claim": False,
        },
        "limitations": [
            "This registry contains deterministic historical outcome evidence only.",
            "It does not evaluate strategies, predictions, returns, ROI, EV, or future draws.",
            "It is for research and entertainment only and is not betting or investment advice.",
            "It does not establish improved winning odds, predictive advantage, betting readiness, or production readiness.",
        ],
    }
    payload["canonical_payload_digest"] = canonical_payload_digest(payload)
    return payload


def markdown_report(payload: Mapping[str, Any], json_bytes: bytes) -> str:
    source = payload["p268d1_source_summary"]
    requested = payload["requested_draw_summary"]
    coverage = payload["coverage_summary"]
    cross_check = payload["p543c_cross_check"]
    json_sha = _sha256_bytes(json_bytes)

    lines = [
        "# P545A — Official Outcomes Registry from Committed P268D1 JSONL",
        "",
        "> Deterministic historical outcome evidence for research only. This is not betting or investment advice and makes no predictive-edge, improved-odds, betting-readiness, or production-readiness claim.",
        "",
        "## Purpose",
        "",
        "Export exactly one validated official outcome for every draw requested by the frozen P273A manifest and P543C contract.",
        "",
        "## Frozen source manifest",
        "",
        f"- Pinned repository commit: `{payload['pinned_repo_commit']}`",
        f"- Deterministic timestamp: `{payload['generated_at_utc']}`",
        f"- Timestamp policy: {payload['generated_at_policy']}",
        "",
        "| source | role | path | SHA-256 | bytes |",
        "|---|---|---|---|---:|",
    ]
    for item in payload["source_artifacts"]:
        lines.append(
            f"| {item['source_id']} | {item['role']} | `{item['path']}` | `{item['sha256']}` | {item['byte_size']} |"
        )
    lines.extend(
        [
            "",
            "P268D1 is the selected authoritative source because it is a frozen, committed full-history artifact with an exact raw-byte hash and an explicit ordered/size outcome contract. No alternate or fallback source is permitted.",
            "",
            "## P268D1 full-source validation",
            "",
            f"- Parsed JSONL lines: {source['parsed_line_count']}",
            f"- Relevant official records: {source['relevant_record_count']}",
            f"- Duplicate identical keys / conflicting keys: {source['duplicate_identical_key_count']} / {source['conflicting_key_count']}",
            f"- Malformed / invalid date / invalid number: {source['malformed_record_count']} / {source['invalid_date_count']} / {source['invalid_number_count']}",
            f"- Invalid range / duplicate number / missing auxiliary: {source['invalid_number_range_count']} / {source['duplicate_number_count']} / {source['missing_auxiliary_outcome_count']}",
            f"- `drawNumberAppear` checked / mismatched: {source['draw_number_appear_checked_count']} / {source['draw_number_appear_mismatch_count']}",
            f"- Stable numeric draw ordering: `{source['stable_numeric_draw_ordering']}`",
            "",
            "| lottery | source records | earliest draw | latest draw | earliest date | latest date |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for lottery in LOTTERIES:
        row = source["by_lottery"][lottery]
        lines.append(
            f"| {lottery} | {row['record_count']} | {row['earliest_draw']} | {row['latest_draw']} | {row['earliest_date']} | {row['latest_date']} |"
        )
    lines.extend(
        [
            "",
            "## Requested manifest and complete coverage",
            "",
            f"- P273A unique draws: {requested['p273a']['unique_draw_count']}",
            f"- P543C rows / candidates / unique draws: {requested['p543c']['row_count']} / {requested['p543c']['candidate_count']} / {requested['p543c']['unique_draw_count']}",
            f"- P543C draws overlapping P273A: {requested['source_overlap_unique_draw_count']}",
            "",
            "| lottery | requested | found valid | missing | conflicting | invalid |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for lottery in LOTTERIES:
        row = coverage["by_lottery"][lottery]
        lines.append(
            f"| {lottery} | {row['requested']} | {row['found_valid']} | {row['missing']} | {row['conflicting']} | {row['invalid']} |"
        )
    total = coverage["total"]
    lines.append(
        f"| **Total** | **{total['requested']}** | **{total['found_valid']}** | **{total['missing']}** | **{total['conflicting']}** | **{total['invalid']}** |"
    )
    lines.extend(
        [
            "",
            "## P543C cross-check",
            "",
            f"- Compared rows / unique draws: {cross_check['compared_row_count']} / {cross_check['unique_draw_count']}",
            f"- Main-number mismatches: {cross_check['main_number_mismatch_count']}",
            f"- Special-number mismatches: {cross_check['special_number_mismatch_count']}",
            f"- Internally conflicting draws: {cross_check['internally_conflicting_draw_count']}",
            f"- Result: `{'PASS' if cross_check['passed'] else 'FAIL'}`",
            "",
            "## Deterministic generation and safety evidence",
            "",
            "- Inputs are raw blobs from the pinned commit and are verified by exact byte size and SHA-256.",
            "- Records are sorted by lottery type, numeric draw, then draw text.",
            "- The timestamp is derived from the pinned commit; wall-clock time, file metadata, random order, external services, and fallback sources are not used.",
            f"- Complete registry emitted: `{coverage['complete']}` ({len(payload['records'])} records)",
            f"- Database opened / written: `{payload['safety']['database_opened']}` / `{payload['safety']['database_written']}`",
            f"- Network used: `{payload['safety']['network_used']}`",
            f"- Upstream artifact modified / partial registry emitted: `{payload['safety']['upstream_artifact_modified']}` / `{payload['safety']['partial_registry_emitted']}`",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["limitations"])
    base_text = "\n".join(lines) + "\n"
    markdown_body_sha = _sha256_bytes(base_text.encode("utf-8"))
    digest_lines = [
        "",
        "## Digest evidence",
        "",
        f"- JSON raw-byte SHA-256: `{json_sha}`",
        f"- Markdown canonical-body SHA-256 (this digest section excluded): `{markdown_body_sha}`",
        f"- Canonical payload digest: `{payload['canonical_payload_digest']}`",
        "",
    ]
    return base_text + "\n".join(digest_lines)


def generate_from_pinned_commit(
    *,
    repo_root: Path,
    pinned_commit: str,
    output_json: Path,
    output_md: Path,
    blob_source: GitBlobSource | None = None,
) -> dict[str, Any]:
    if pinned_commit != PINNED_COMMIT:
        raise InputArtifactError(
            f"pinned commit must remain {PINNED_COMMIT}, observed {pinned_commit}"
        )
    source = blob_source or GitBlobSource(repo_root, pinned_commit)
    raw = {
        source_id: source.read(spec["path"])
        for source_id, spec in SOURCE_SPECS.items()
    }
    payload = build_registry(
        p268d1_raw=raw["p268d1"],
        p273a_raw=raw["p273a"],
        p543c_raw=raw["p543c"],
        pinned_repo_commit=pinned_commit,
        generated_at_utc=commit_timestamp_utc(repo_root, pinned_commit),
    )
    json_bytes = canonical_json_bytes(payload)
    markdown_bytes = markdown_report(payload, json_bytes).encode("utf-8")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_bytes(json_bytes)
    output_md.write_bytes(markdown_bytes)
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--pinned-commit", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    try:
        payload = generate_from_pinned_commit(
            repo_root=Path(args.repo_root).expanduser().resolve(),
            pinned_commit=args.pinned_commit,
            output_json=output_json,
            output_md=output_md,
        )
    except InputArtifactError as exc:
        print(f"P545A_R2_BLOCKED_INPUT_HASH_OR_SIZE_CHANGED: {exc}", file=sys.stderr)
        return 2
    except SourceIntegrityError as exc:
        print(
            f"P545A_R2_BLOCKED_P268D1_FULL_SOURCE_INTEGRITY_FAILED: {exc}",
            file=sys.stderr,
        )
        return 2
    except RequestManifestError as exc:
        print(f"P545A_R2_BLOCKED_REQUEST_MANIFEST_DRIFT: {exc}", file=sys.stderr)
        return 2
    except CoverageError as exc:
        print(
            f"P545A_R2_BLOCKED_COMMITTED_SOURCE_COVERAGE_INCOMPLETE: {exc}",
            file=sys.stderr,
        )
        return 2
    except P543CCrossCheckError as exc:
        print(
            f"P545A_R2_BLOCKED_P543C_P268D1_OUTCOME_MISMATCH: {exc}",
            file=sys.stderr,
        )
        return 2
    print(f"records={len(payload['records'])}")
    print(f"canonical_payload_digest={payload['canonical_payload_digest']}")
    print(f"json_sha256={_sha256_bytes(output_json.read_bytes())}")
    print(f"markdown_sha256={_sha256_bytes(output_md.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
