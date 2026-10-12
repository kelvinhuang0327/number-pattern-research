#!/usr/bin/env python3
"""Build the P217-A pybaseball multi-date sample quality dashboard from P216-A artifacts only."""
from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_MD = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.md"
SOURCE_JSON = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.json"
SOURCE_CSV = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.csv"
OUT_HTML = REPORT_DIR / "p217a_pybaseball_multidate_quality_dashboard.html"
OUT_JSON = REPORT_DIR / "p217a_pybaseball_multidate_quality_dashboard.json"
DISCLAIMER = "Historical pybaseball multi-date quality dashboard only. Not live predictions, not betting advice."
TASK_NAME = "P217-A pybaseball Multi-Date Sample Quality Dashboard"
SUCCESS_BANNER = "P217-A PYBASEBALL MULTIDATE QUALITY DASHBOARD PASS"
FAILURE_BANNER = "P217-A PYBASEBALL MULTIDATE QUALITY DASHBOARD FAIL"
PREVIEW_ROW_LIMIT = 5
DISTRIBUTION_COLUMNS = (
    "pitch_type",
    "events",
    "description",
    "player_name",
    "home_team",
    "away_team",
    "game_date",
)
PROHIBITED_CLAIMS = (
    "No future prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No ROI, EV, Kelly, CLV, or edge claim.",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_cell(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str | None]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {column: _normalize_cell(value) for column, value in row.items()}
            for row in reader
        ]
    return fieldnames, rows


def _fraction(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _build_missingness(columns: list[str], rows: list[dict[str, str | None]]) -> dict[str, dict[str, Any]]:
    row_count = len(rows)
    return {
        column: {
            "missing_count": sum(1 for row in rows if row.get(column) is None),
            "missing_fraction": _fraction(
                sum(1 for row in rows if row.get(column) is None),
                row_count,
            ),
        }
        for column in columns
    }


def _distribution_sort_key(item: tuple[str, int]) -> tuple[int, str]:
    value, count = item
    return (-count, value)


def _build_distributions(rows: list[dict[str, str | None]]) -> dict[str, list[dict[str, Any]]]:
    row_count = len(rows)
    distributions: dict[str, list[dict[str, Any]]] = {}
    for column in DISTRIBUTION_COLUMNS:
        if not rows or column not in rows[0]:
            continue
        counts: dict[str, int] = {}
        for row in rows:
            label = row.get(column) or "(missing)"
            counts[label] = counts.get(label, 0) + 1
        distributions[column] = [
            {
                "value": value,
                "count": count,
                "fraction": _fraction(count, row_count),
            }
            for value, count in sorted(counts.items(), key=_distribution_sort_key)
        ]
    return distributions


def _build_per_date_row_counts(rows: list[dict[str, str | None]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        game_date = row.get("game_date") or "(missing)"
        counts[game_date] = counts.get(game_date, 0) + 1
    return dict(sorted(counts.items()))


def build_payload() -> dict[str, Any]:
    source_md_text = SOURCE_MD.read_text(encoding="utf-8")
    source_json_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    columns, rows = _load_csv_rows(SOURCE_CSV)

    source_artifacts = [
        str(SOURCE_MD.relative_to(ROOT)),
        str(SOURCE_JSON.relative_to(ROOT)),
        str(SOURCE_CSV.relative_to(ROOT)),
    ]
    source_hashes = {
        str(SOURCE_MD.relative_to(ROOT)): _sha256(SOURCE_MD),
        str(SOURCE_JSON.relative_to(ROOT)): _sha256(SOURCE_JSON),
        str(SOURCE_CSV.relative_to(ROOT)): _sha256(SOURCE_CSV),
    }

    limitations = [
        "Dashboard metrics are computed from the fixed P216-A CSV snapshot only, not from a refreshed upstream pull.",
        "This dashboard reflects a small bounded multi-date historical sample and should not be generalized beyond the fixed date range and team filter.",
        "CSV typing is preserved as artifact text for determinism, so numeric-looking fields are summarized as stored snapshot values.",
    ]
    for item in source_json_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)

    return {
        "task": TASK_NAME,
        "status": "PASS_P216A_ARTIFACT_ONLY_MULTIDATE_QUALITY_DASHBOARD",
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": source_artifacts,
        "source_hashes": source_hashes,
        "source_summary": {
            "p216_task": source_json_payload.get("task"),
            "p216_status": source_json_payload.get("status"),
            "p216_disclaimer": source_json_payload.get("disclaimer"),
            "p216_source_request": source_json_payload.get("source_request"),
            "p216_observed_dates": source_json_payload.get("observed_dates"),
            "p216_sample_size_limits": source_json_payload.get("sample_size_limits"),
            "p216_markdown_mentions_disclaimer": source_json_payload.get("disclaimer") in source_md_text,
        },
        "row_count": len(rows),
        "per_date_row_counts": _build_per_date_row_counts(rows),
        "column_count": len(columns),
        "columns": columns,
        "missingness": _build_missingness(columns, rows),
        "distributions": _build_distributions(rows),
        "sample_preview": rows[:PREVIEW_ROW_LIMIT],
        "limitations": limitations,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
    }


def _render_summary_list(payload: dict[str, Any]) -> str:
    items = [
        ("Status", payload["status"]),
        ("Dashboard row count", payload["row_count"]),
        ("Dashboard column count", payload["column_count"]),
        ("Source task", payload["source_summary"]["p216_task"]),
        ("Source status", payload["source_summary"]["p216_status"]),
        ("Observed dates", ", ".join(payload["source_summary"]["p216_observed_dates"] or [])),
    ]
    return "\n".join(
        f"<li><strong>{html.escape(label)}:</strong> {html.escape(str(value))}</li>"
        for label, value in items
    )


def _render_per_date_table(payload: dict[str, Any]) -> str:
    rows = []
    for game_date, count in payload["per_date_row_counts"].items():
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(game_date)}</code></td>"
            f"<td>{count}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_source_table(payload: dict[str, Any]) -> str:
    rows = []
    for artifact in payload["source_artifacts"]:
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(artifact)}</code></td>"
            f"<td><code>{html.escape(payload['source_hashes'][artifact])}</code></td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_missingness_table(payload: dict[str, Any]) -> str:
    rows = []
    for column in payload["columns"]:
        summary = payload["missingness"][column]
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(column)}</code></td>"
            f"<td>{summary['missing_count']}</td>"
            f"<td>{summary['missing_fraction']:.6f}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_distribution_sections(payload: dict[str, Any]) -> str:
    sections = []
    for column, entries in payload["distributions"].items():
        rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(entry['value'])}</td>"
            f"<td>{entry['count']}</td>"
            f"<td>{entry['fraction']:.6f}</td>"
            "</tr>"
            for entry in entries
        )
        sections.append(
            "<section>"
            f"<h3><code>{html.escape(column)}</code></h3>"
            "<table>"
            "<thead><tr><th>Value</th><th>Count</th><th>Fraction</th></tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table>"
            "</section>"
        )
    return "\n".join(sections)


def _render_preview_table(payload: dict[str, Any]) -> str:
    headers = "".join(f"<th><code>{html.escape(column)}</code></th>" for column in payload["columns"])
    rows = []
    for record in payload["sample_preview"]:
        cells = "".join(
            f"<td>{html.escape(record.get(column) or '')}</td>"
            for column in payload["columns"]
        )
        rows.append(f"<tr>{cells}</tr>")
    return (
        "<table>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_html(payload: dict[str, Any]) -> str:
    limitations = "\n".join(f"<li>{html.escape(item)}</li>" for item in payload["limitations"])
    prohibited_claims = "\n".join(
        f"<li>{html.escape(item)}</li>" for item in payload["prohibited_claims"]
    )
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{html.escape(TASK_NAME)}</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light; }\n"
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; color: #182028; background: #f6f8fb; }\n"
        "    main { max-width: 1200px; margin: 0 auto; background: #ffffff; padding: 32px; border: 1px solid #d8dee8; }\n"
        "    h1, h2, h3 { color: #0f3554; }\n"
        "    p.notice { padding: 12px 14px; background: #eef5fb; border-left: 4px solid #2d6ea3; }\n"
        "    table { border-collapse: collapse; width: 100%; margin: 16px 0 24px; font-size: 14px; }\n"
        "    th, td { border: 1px solid #d8dee8; padding: 8px 10px; text-align: left; vertical-align: top; }\n"
        "    th { background: #edf3f8; }\n"
        "    code { font-family: 'SFMono-Regular', Menlo, monospace; font-size: 0.95em; }\n"
        "    section { margin-bottom: 28px; }\n"
        "    ul { padding-left: 20px; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "<main>\n"
        f"<h1>{html.escape(TASK_NAME)}</h1>\n"
        f"<p class=\"notice\">{html.escape(DISCLAIMER)}</p>\n"
        "<section>\n"
        "  <h2>Summary</h2>\n"
        f"  <ul>{_render_summary_list(payload)}</ul>\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Source Artifacts</h2>\n"
        "  <table>\n"
        "    <thead><tr><th>Artifact</th><th>SHA256</th></tr></thead>\n"
        f"    <tbody>{_render_source_table(payload)}</tbody>\n"
        "  </table>\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Per-Date Row Counts</h2>\n"
        "  <table>\n"
        "    <thead><tr><th>game_date</th><th>Row Count</th></tr></thead>\n"
        f"    <tbody>{_render_per_date_table(payload)}</tbody>\n"
        "  </table>\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Columns</h2>\n"
        f"  <p>{html.escape(', '.join(payload['columns']))}</p>\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Missingness</h2>\n"
        "  <table>\n"
        "    <thead><tr><th>Column</th><th>Missing Count</th><th>Missing Fraction</th></tr></thead>\n"
        f"    <tbody>{_render_missingness_table(payload)}</tbody>\n"
        "  </table>\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Selected Distributions</h2>\n"
        f"  {_render_distribution_sections(payload)}\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Sample Preview</h2>\n"
        f"  {_render_preview_table(payload)}\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Limitations</h2>\n"
        f"  <ul>{limitations}</ul>\n"
        "</section>\n"
        "<section>\n"
        "  <h2>Historical-Only Scope</h2>\n"
        f"  <p>{html.escape(payload['historical_only_disclaimer'])}</p>\n"
        "  <ul>"
        f"{prohibited_claims}"
        "  </ul>\n"
        "</section>\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def write_outputs(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_HTML.write_text(render_html(payload), encoding="utf-8")


def main() -> int:
    try:
        payload = build_payload()
        write_outputs(payload)
    except Exception as exc:
        print(f"{FAILURE_BANNER}: {exc}")
        return 1

    print(SUCCESS_BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
