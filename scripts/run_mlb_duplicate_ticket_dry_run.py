from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.duplicate_ticket_policy import analyze_duplicate_tickets


DEFAULT_INPUT_GLOB = "outputs/recommendations/PAPER/**/*.jsonl"
DEFAULT_JSON_REPORT = Path("report/p206a_duplicate_ticket_dry_run.json")
DEFAULT_MD_REPORT = Path("report/p206a_duplicate_ticket_dry_run.md")
DEFAULT_CSV_REPORT = Path("report/p206a_duplicate_ticket_dry_run.csv")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            row["_p206a_input_path"] = str(path)
            row["_p206a_input_line"] = line_number
            rows.append(row)
    return rows


def discover_input_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        candidate = Path(pattern)
        if candidate.is_absolute():
            if candidate.is_file():
                paths.append(candidate)
            continue

        matched = [path for path in Path().glob(pattern) if path.is_file()]
        if matched:
            paths.extend(matched)
        elif candidate.is_file():
            paths.append(candidate)
    return sorted(set(paths))


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(_read_jsonl(path))
    return rows


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "row_index",
        "group_key",
        "status",
        "keep_reason",
        "suppress_reason",
        "ungroupable_reason",
        "game_identity",
        "selected_side",
        "market",
        "strategy_attribution",
        "provenance_contract_version",
        "learning_guard_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for decision in payload["decisions"]:
            writer.writerow({field: decision.get(field, "") for field in fields})


def _pct(value: float) -> str:
    return f"{value:.2%}"


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ungroupable = payload["ungroupable_counts"]
    lines = [
        "# P206A Duplicate-Ticket Reduction Dry Run",
        "",
        "This is a local historical/replay dry run only. It is not a future prediction, betting recommendation, EV/ROI/payout/Kelly claim, activation claim, live-market claim, production change, DB mutation, real publication, or future-ticket mutation.",
        "",
        "## Summary",
        "",
        f"- Dry-run input rows: {payload['total_input_rows']}",
        f"- Duplicate/overlap groups: {payload['total_groups']}",
        f"- Kept rows: {payload['kept_rows']}",
        f"- Suppressed rows: {payload['suppressed_rows']}",
        f"- Suppression rate: {_pct(payload['suppression_rate'])}",
        f"- Missing stable identity rows: {ungroupable['ungroupable_missing_identity']}",
        f"- Missing selected side rows: {ungroupable['ungroupable_missing_selected_side']}",
        f"- Missing market/bet type rows: {ungroupable['ungroupable_missing_market']}",
        "",
        "## Observed Duplicate Patterns",
        "",
    ]
    duplicate_groups = [group for group in payload["group_details"] if group["row_count"] > 1]
    if duplicate_groups:
        for group in duplicate_groups:
            lines.append(
                f"- `{group['group_key']}`: {group['row_count']} rows, "
                f"{group['suppressed_rows']} suppressed, "
                f"{group['strategy_attribution_count']} strategy attribution set(s)."
            )
    else:
        lines.append("- No groupable duplicate or overlapping recommendation tickets were observed.")

    lines.extend(
        [
            "",
            "## Policy Inventory",
            "",
            "- Grouping uses stable game identity, selected side, and market/bet type only.",
            "- Exact duplicate suppression additionally requires materially equivalent strategy attribution.",
            "- Stable identity is ID-based; team names, dates, and text labels are not fuzzy-matched.",
            "- Missing stable identity, selected side, or market/bet type is fail-closed and kept as ungroupable.",
            "- P205A/P205B learning boundaries are preserved; this dry run only reports provenance contract version and learning guard status.",
            "",
            "## Row Decisions",
            "",
            "| row | status | group_key | keep_reason | suppress_reason | learning_guard_status | provenance_contract_version |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for decision in payload["decisions"]:
        lines.append(
            f"| {decision['row_index']} | {decision['status']} | `{decision['group_key']}` | "
            f"{decision['keep_reason']} | {decision['suppress_reason']} | "
            f"{decision['learning_guard_status']} | {decision['provenance_contract_version']} |"
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_dry_run(
    input_patterns: list[str],
    json_report: Path = DEFAULT_JSON_REPORT,
    md_report: Path = DEFAULT_MD_REPORT,
    csv_report: Path = DEFAULT_CSV_REPORT,
) -> dict[str, Any]:
    input_paths = discover_input_paths(input_patterns)
    rows = load_rows(input_paths)
    payload = analyze_duplicate_tickets(rows)
    payload["input_sources"] = [str(path) for path in input_paths]
    write_json_report(json_report, payload)
    write_csv_report(csv_report, payload)
    write_markdown_report(md_report, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P206A local duplicate-ticket dry run.")
    parser.add_argument("--input", action="append", dest="inputs", default=None)
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_REPORT))
    parser.add_argument("--output-csv", default=str(DEFAULT_CSV_REPORT))
    args = parser.parse_args()

    payload = run_dry_run(
        args.inputs or [DEFAULT_INPUT_GLOB],
        json_report=Path(args.output_json),
        md_report=Path(args.output_md),
        csv_report=Path(args.output_csv),
    )
    print(
        "P206A duplicate-ticket dry run complete: "
        f"input_rows={payload['total_input_rows']} "
        f"groups={payload['total_groups']} "
        f"kept={payload['kept_rows']} "
        f"suppressed={payload['suppressed_rows']} "
        f"suppression_rate={payload['suppression_rate']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
