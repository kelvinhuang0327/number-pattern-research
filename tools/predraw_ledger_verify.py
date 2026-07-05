#!/usr/bin/env python3
"""
P365: predraw ledger verifier / inspection CLI.

Read-only inspection tool for JSONL ledger artifacts produced by the P364
explicit opt-in capture runner (tools/predraw_capture_runner.py), built on
top of the existing P360A `lottery_api.engine.predraw_ledger` reader/chain-
verification APIs. This tool does not redesign the ledger, does not open the
canonical DB, does not generate predictions, and does not accumulate live
ledger rows -- it only reads a ledger path the caller supplies and reports a
safe structural summary.

Safety properties:
  - Read-only: never writes to the ledger path or any DB.
  - Safe output: predicted_numbers and predicted_special are never printed.
    The summary reports counts and identifiers (record kind, generation
    mode, lottery type, target_draw) only.
  - Not a prediction/OOS tool: validating a ledger's structural/chain
    integrity is not a predictive claim, a betting recommendation, or
    evidence of out-of-sample performance. See predraw_ledger.py module
    docstring and docs/p360a_predraw_metadata_preregistration.md.

Usage:
  python3 tools/predraw_ledger_verify.py <ledger_path>

Exit codes:
  0 = ledger file exists and is structurally/chain valid (including an
      empty or absent-but-not-required-to-exist ledger with 0 records)
  1 = ledger file exists but contains malformed records or a broken hash
      chain
  2 = ledger file does not exist at the given path
  3 = ledger path was refused (e.g. resolves to the canonical DB basename)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lottery_api.engine import predraw_ledger as pl  # noqa: E402

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_REFUSED_PATH = 3

DISCLAIMER = (
    "This is a structural/hash-chain validity check only. It is NOT a "
    "prediction, betting recommendation, evidence of strategy edge, or "
    "out-of-sample (OOS) performance proof."
)

_REQUIRED_PREDICTION_FIELDS = (
    "schema_version", "record_id", "record_kind", "lottery_type",
    "generation_mode", "predicted_at", "created_at", "target_draw",
    "strategy_id", "strategy_version", "predicted_numbers", "bet_index",
    "n_bets_total", "run_id", "generation_source",
    "record_hash", "prev_record_hash",
)
_REQUIRED_SETTLEMENT_FIELDS = (
    "schema_version", "record_id", "record_kind", "references_record_id",
    "settled_at", "actual_numbers", "actual_special", "hit_count",
    "special_hit", "record_hash", "prev_record_hash",
)


def _missing_fields(record: Dict[str, Any]) -> List[str]:
    kind = record.get("record_kind")
    if kind == "PREDICTION":
        required = _REQUIRED_PREDICTION_FIELDS
    elif kind == "SETTLEMENT":
        required = _REQUIRED_SETTLEMENT_FIELDS
    else:
        return [f"unknown record_kind={kind!r}"]
    return [f for f in required if f not in record]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P365 predraw ledger verifier/inspection CLI. Reads a JSONL "
            "ledger artifact produced by tools/predraw_capture_runner.py, "
            "validates required fields and the hash chain, and prints a "
            "safe summary (counts and identifiers only -- never predicted "
            "numbers). Read-only: never writes the ledger, the canonical "
            "DB, or any other file. Not a prediction or OOS-proof tool."
        )
    )
    parser.add_argument("ledger_path", help="path to the JSONL ledger file to verify")
    return parser


def verify_ledger(ledger_path: Path) -> Dict[str, Any]:
    """
    Pure read-only verification. Returns a summary dict; never prints.
    Raises pl.LedgerPathError if the path is refused (e.g. canonical DB
    basename) -- callers must catch this before it reaches the user as an
    uncaught traceback.
    """
    chain = pl.verify_chain(ledger_path)
    records = pl.read_all_records(ledger_path) if chain.ok else []

    record_kind_counts: Dict[str, int] = {}
    generation_mode_counts: Dict[str, int] = {}
    per_lottery_draws: Dict[str, Dict[str, Any]] = {}
    malformed: List[Dict[str, Any]] = []

    for idx, rec in enumerate(records):
        kind = rec.get("record_kind", "PREDICTION")
        record_kind_counts[kind] = record_kind_counts.get(kind, 0) + 1

        missing = _missing_fields(rec)
        if missing:
            malformed.append({"index": idx, "record_id": rec.get("record_id"), "missing_fields": missing})
            continue

        if kind == "PREDICTION":
            mode = pl.classify_generation_mode(rec)
            generation_mode_counts[mode] = generation_mode_counts.get(mode, 0) + 1
            lt = rec.get("lottery_type", "UNKNOWN")
            bucket = per_lottery_draws.setdefault(lt, {"record_count": 0, "min_target_draw": None, "max_target_draw": None})
            bucket["record_count"] += 1
            td = rec.get("target_draw")
            if td is not None:
                bucket["min_target_draw"] = td if bucket["min_target_draw"] is None else min(bucket["min_target_draw"], td)
                bucket["max_target_draw"] = td if bucket["max_target_draw"] is None else max(bucket["max_target_draw"], td)

    validation_status = "VALID" if (chain.ok and not malformed) else "INVALID"

    return {
        "ledger_path": str(ledger_path),
        "validation_status": validation_status,
        "chain_ok": chain.ok,
        "chain_total_records": chain.total_records,
        "chain_first_broken_index": chain.first_broken_index,
        "chain_reason": chain.reason,
        "record_count": len(records),
        "record_kind_counts": record_kind_counts,
        "generation_mode_counts": generation_mode_counts,
        "per_lottery_type": per_lottery_draws,
        "malformed_record_count": len(malformed),
        "malformed_records": malformed,
        "disclaimer": DISCLAIMER,
    }


def format_summary(summary: Dict[str, Any]) -> str:
    lines = [
        "[predraw-verify] ledger_path={}".format(summary["ledger_path"]),
        "[predraw-verify] validation_status={}".format(summary["validation_status"]),
        "[predraw-verify] chain_ok={} chain_total_records={}".format(
            summary["chain_ok"], summary["chain_total_records"]),
    ]
    if not summary["chain_ok"]:
        lines.append("[predraw-verify] chain_first_broken_index={} chain_reason={}".format(
            summary["chain_first_broken_index"], summary["chain_reason"]))
    lines.append("[predraw-verify] record_count={} record_kind_counts={}".format(
        summary["record_count"], summary["record_kind_counts"]))
    lines.append("[predraw-verify] generation_mode_counts={}".format(summary["generation_mode_counts"]))
    for lt, bucket in summary["per_lottery_type"].items():
        lines.append(
            "[predraw-verify] lottery_type={} record_count={} target_draw_range=[{}, {}]".format(
                lt, bucket["record_count"], bucket["min_target_draw"], bucket["max_target_draw"]))
    if summary["malformed_record_count"]:
        lines.append("[predraw-verify] malformed_record_count={}".format(summary["malformed_record_count"]))
        for m in summary["malformed_records"][:10]:
            lines.append("[predraw-verify]   index={} record_id={} missing_fields={}".format(
                m["index"], m["record_id"], m["missing_fields"]))
    lines.append("[predraw-verify] disclaimer: {}".format(summary["disclaimer"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ledger_path = Path(args.ledger_path)

    if not ledger_path.exists():
        print(f"[predraw-verify] ERROR: ledger file does not exist: {ledger_path}", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND

    try:
        summary = verify_ledger(ledger_path)
    except pl.LedgerPathError as exc:
        print(f"[predraw-verify] REFUSED ledger path: {exc}", file=sys.stderr)
        return EXIT_REFUSED_PATH

    print(format_summary(summary))
    return EXIT_OK if summary["validation_status"] == "VALID" else EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
