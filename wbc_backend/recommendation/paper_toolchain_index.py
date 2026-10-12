"""Deterministic local launch/index page for committed paper toolchain artifacts.

This module reads existing P246/P247/P248 status artifacts and writes the P249
index outputs. It does not run earlier workflows, mutate earlier reports, contact
providers, fetch sports data, write DB/data/runtime/log state, or compute betting
performance.
"""
from __future__ import annotations

import csv
import html
import json
import posixpath
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Sequence

from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DASHBOARD_SUMMARY_JSON = (
    ROOT / "report" / "p248a_paper_toolchain_dashboard" / "dashboard_summary.json"
)
DEFAULT_DASHBOARD_SECTIONS_CSV = (
    ROOT / "report" / "p248a_paper_toolchain_dashboard" / "dashboard_sections.csv"
)
DEFAULT_DASHBOARD_HTML = ROOT / "report" / "p248a_paper_toolchain_dashboard" / "dashboard.html"
DEFAULT_TOOLCHAIN_STATUS_JSON = (
    ROOT / "report" / "p247a_paper_toolchain_status" / "toolchain_status.json"
)
DEFAULT_GATE_SUMMARY_JSON = (
    ROOT / "report" / "p246a_paper_artifact_diff_gate" / "gate_summary.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p249a_paper_toolchain_index"
DEFAULT_GENERATED_AT_UTC = None

INDEX_SUMMARY_FILENAME = "index_summary.json"
INDEX_LINKS_FILENAME = "index_links.csv"
INDEX_HTML_FILENAME = "index.html"

LINK_CSV_FIELDNAMES = [
    "link_id",
    "title",
    "category",
    "relative_path",
    "target_exists",
    "target_type",
    "sha256",
    "notes",
]

DASHBOARD_SECTION_COLUMNS = (
    "section_id",
    "section_title",
    "source",
    "status",
    "item_count",
    "notes",
)

REQUIRED_LIMITATION_LABELS = (
    "2025-only",
    "historical paper-only",
    "odds provenance unverified",
    "not true-PIT",
    "not betting edge",
    "not future prediction",
    "not live",
    "not production",
    "not real betting",
    "not multi-season validation",
)

NOT_CLAIMS = (
    "No ROI, paper P/L, EV, Kelly, bankroll, or compounding is computed.",
    "No best_strategy, best_threshold, recommended_bet, or strategy ranking is output.",
    "No betting edge, future prediction, true-PIT validation, or multi-season validation is claimed.",
    "No live, production, or real betting output is created.",
)


class PaperToolchainIndexError(RuntimeError):
    """Raised when the index cannot be generated from committed local artifacts."""


@dataclass(frozen=True)
class LinkSpec:
    link_id: str
    title: str
    category: str
    target_path: str
    notes: str = ""
    optional: bool = False


@dataclass(frozen=True)
class PaperToolchainIndexResult:
    summary: dict[str, Any]
    link_rows: tuple[dict[str, str], ...]
    output_paths: dict[str, str]


DEFAULT_LINK_SPECS: tuple[LinkSpec, ...] = (
    LinkSpec(
        "p248_dashboard_html",
        "P248 dashboard HTML",
        "launch",
        "report/p248a_paper_toolchain_dashboard/dashboard.html",
        "primary local dashboard launch link",
    ),
    LinkSpec(
        "p248_dashboard_summary",
        "P248 dashboard summary JSON",
        "dashboard",
        "report/p248a_paper_toolchain_dashboard/dashboard_summary.json",
    ),
    LinkSpec(
        "p248_dashboard_sections",
        "P248 dashboard sections CSV",
        "dashboard",
        "report/p248a_paper_toolchain_dashboard/dashboard_sections.csv",
    ),
    LinkSpec(
        "p247_toolchain_status",
        "P247 toolchain status JSON",
        "toolchain_status",
        "report/p247a_paper_toolchain_status/toolchain_status.json",
    ),
    LinkSpec(
        "p247_toolchain_steps",
        "P247 toolchain steps CSV",
        "toolchain_status",
        "report/p247a_paper_toolchain_status/toolchain_steps.csv",
    ),
    LinkSpec(
        "p247_toolchain_report",
        "P247 toolchain report Markdown",
        "toolchain_status",
        "report/p247a_paper_toolchain_status/toolchain_report.md",
    ),
    LinkSpec(
        "p246_gate_summary",
        "P246 gate summary JSON",
        "latest_gate",
        "report/p246a_paper_artifact_diff_gate/gate_summary.json",
    ),
    LinkSpec(
        "p246_gate_checks",
        "P246 gate checks CSV",
        "latest_gate",
        "report/p246a_paper_artifact_diff_gate/gate_checks.csv",
    ),
    LinkSpec(
        "p246_gate_report",
        "P246 gate report Markdown",
        "latest_gate",
        "report/p246a_paper_artifact_diff_gate/gate_report.md",
    ),
    LinkSpec(
        "p245_diff_summary",
        "P245 diff summary JSON",
        "catalog_query_diff",
        "report/p245a_paper_artifact_catalog_diff/diff_summary.json",
    ),
    LinkSpec(
        "p245_diff_entries",
        "P245 diff entries CSV",
        "catalog_query_diff",
        "report/p245a_paper_artifact_catalog_diff/diff_entries.csv",
    ),
    LinkSpec(
        "p245_diff_report",
        "P245 diff report Markdown",
        "catalog_query_diff",
        "report/p245a_paper_artifact_catalog_diff/diff_report.md",
    ),
    LinkSpec(
        "p244_query_summary",
        "P244 query summary JSON",
        "catalog_query_diff",
        "report/p244a_paper_artifact_catalog_query/query_summary.json",
    ),
    LinkSpec(
        "p244_query_results",
        "P244 query results CSV",
        "catalog_query_diff",
        "report/p244a_paper_artifact_catalog_query/query_results.csv",
    ),
    LinkSpec(
        "p244_query_report",
        "P244 query report Markdown",
        "catalog_query_diff",
        "report/p244a_paper_artifact_catalog_query/query_report.md",
    ),
    LinkSpec(
        "p243_catalog_json",
        "P243 artifact catalog JSON",
        "catalog_query_diff",
        "report/p243a_paper_artifact_catalog/artifact_catalog.json",
    ),
    LinkSpec(
        "p243_catalog_csv",
        "P243 artifact catalog CSV",
        "catalog_query_diff",
        "report/p243a_paper_artifact_catalog/artifact_catalog.csv",
    ),
    LinkSpec(
        "p243_catalog_md",
        "P243 artifact catalog Markdown",
        "catalog_query_diff",
        "report/p243a_paper_artifact_catalog/artifact_catalog.md",
    ),
    LinkSpec(
        "p239_script",
        "P239 workflow script",
        "scripts",
        "scripts/run_mlb_paper_strategy_workflow.py",
    ),
    LinkSpec(
        "p240_script",
        "P240 workflow inspector script",
        "scripts",
        "scripts/inspect_mlb_paper_strategy_workflow.py",
    ),
    LinkSpec(
        "p241_script",
        "P241 review pack script",
        "scripts",
        "scripts/build_mlb_paper_strategy_workflow_review_pack.py",
    ),
    LinkSpec(
        "p242_script",
        "P242 workflow bundle script",
        "scripts",
        "scripts/run_mlb_paper_strategy_workflow_bundle.py",
    ),
    LinkSpec(
        "p243_script",
        "P243 catalog script",
        "scripts",
        "scripts/build_mlb_paper_artifact_catalog.py",
    ),
    LinkSpec(
        "p244_script",
        "P244 query script",
        "scripts",
        "scripts/query_mlb_paper_artifact_catalog.py",
    ),
    LinkSpec(
        "p245_script",
        "P245 diff script",
        "scripts",
        "scripts/diff_mlb_paper_artifact_catalogs.py",
    ),
    LinkSpec(
        "p246_script",
        "P246 gate script",
        "scripts",
        "scripts/check_mlb_paper_artifact_diff.py",
    ),
    LinkSpec(
        "p247_script",
        "P247 toolchain status script",
        "scripts",
        "scripts/build_mlb_paper_toolchain_status.py",
    ),
    LinkSpec(
        "p248_script",
        "P248 dashboard script",
        "scripts",
        "scripts/build_mlb_paper_toolchain_dashboard.py",
    ),
    LinkSpec(
        "p239_workflow_summary",
        "P239 workflow summary JSON",
        "reports",
        "report/p239a_paper_strategy_workflow/workflow_summary.json",
    ),
    LinkSpec(
        "p240_inspection_summary",
        "P240 inspection summary JSON",
        "reports",
        "report/p240a_paper_strategy_workflow_inspector/inspection_summary.json",
    ),
    LinkSpec(
        "p241_review_report",
        "P241 review report Markdown",
        "reports",
        "report/p241a_paper_strategy_workflow_review_pack/review_report.md",
    ),
    LinkSpec(
        "p242_bundle_summary",
        "P242 bundle summary JSON",
        "reports",
        "report/p242a_paper_strategy_workflow_bundle/bundle_summary.json",
    ),
)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _stable_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PaperToolchainIndexError(f"MISSING_INPUT: {label} not found: {_display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperToolchainIndexError(
            f"CORRUPT_INPUT: {label} invalid JSON: {_display_path(path)}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperToolchainIndexError(
            f"CORRUPT_INPUT: {label} JSON must be an object: {_display_path(path)}"
        )
    return payload


def _read_dashboard_sections(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperToolchainIndexError(f"MISSING_INPUT: dashboard sections CSV not found: {_display_path(path)}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            missing = [column for column in DASHBOARD_SECTION_COLUMNS if column not in fieldnames]
            if missing:
                raise PaperToolchainIndexError(
                    "CORRUPT_INPUT: dashboard sections CSV missing required columns: "
                    + ", ".join(missing)
                )
            return [{column: row.get(column, "") for column in DASHBOARD_SECTION_COLUMNS} for row in reader]
    except csv.Error as exc:
        raise PaperToolchainIndexError(
            f"CORRUPT_INPUT: dashboard sections CSV invalid: {_display_path(path)}: {exc}"
        ) from exc


def _read_existing_text(path: Path, label: str) -> str:
    if not path.is_file():
        raise PaperToolchainIndexError(f"MISSING_INPUT: {label} not found: {_display_path(path)}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise PaperToolchainIndexError(f"CORRUPT_INPUT: {label} is empty: {_display_path(path)}")
    return text


def _input_paths(
    *,
    dashboard_summary_json: Path,
    dashboard_sections_csv: Path,
    dashboard_html: Path,
    toolchain_status_json: Path,
    gate_summary_json: Path,
) -> dict[str, str]:
    return {
        "dashboard_summary_json": _display_path(dashboard_summary_json),
        "dashboard_sections_csv": _display_path(dashboard_sections_csv),
        "dashboard_html": _display_path(dashboard_html),
        "toolchain_status_json": _display_path(toolchain_status_json),
        "gate_summary_json": _display_path(gate_summary_json),
    }


def _input_hashes(input_paths: dict[str, str]) -> dict[str, str]:
    return {key: _sha256(_repo_path(display_path)) for key, display_path in input_paths.items()}


def _output_files(output_dir: Path) -> dict[str, str]:
    return {
        "index_summary_json": _display_path(output_dir / INDEX_SUMMARY_FILENAME),
        "index_links_csv": _display_path(output_dir / INDEX_LINKS_FILENAME),
        "index_html": _display_path(output_dir / INDEX_HTML_FILENAME),
    }


def _as_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_labels(*payloads: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for payload in payloads:
        for label in _as_list(payload, "limitation_labels"):
            text = str(label)
            if text not in labels:
                labels.append(text)
    for required_label in REQUIRED_LIMITATION_LABELS:
        if required_label not in labels:
            labels.append(required_label)
    return labels


def _rel_href(output_dir: Path, target: Path) -> str:
    rel = posixpath.relpath(target.resolve().as_posix(), output_dir.resolve().as_posix())
    return rel if rel.startswith(".") else f"./{rel}"


def _target_type(path: Path) -> str:
    if path.is_file():
        return "file"
    if path.is_dir():
        return "directory"
    return "missing"


def _link_rows(output_dir: Path, link_specs: Sequence[LinkSpec]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for spec in link_specs:
        target = _repo_path(spec.target_path)
        exists = target.exists()
        rows.append(
            {
                "link_id": spec.link_id,
                "title": spec.title,
                "category": spec.category,
                "relative_path": _rel_href(output_dir, target),
                "target_exists": str(exists),
                "target_type": _target_type(target),
                "sha256": _sha256(target) if target.is_file() else "",
                "notes": spec.notes + (" optional" if spec.optional else ""),
            }
        )
    return tuple(rows)


def _derive_index_status(
    *,
    dashboard_status: str,
    toolchain_status: str,
    latest_gate_status: str,
    warnings: Sequence[str],
    failures: Sequence[str],
) -> str:
    statuses = (dashboard_status, toolchain_status, latest_gate_status)
    if failures or any(status == "FAIL" for status in statuses):
        return "FAIL"
    if warnings or any(status != "PASS" for status in statuses):
        return "WARN"
    return "PASS"


def _build_summary(
    *,
    generated_at_utc: str,
    input_paths: dict[str, str],
    input_hashes: dict[str, str],
    output_files: dict[str, str],
    dashboard_summary: dict[str, Any],
    dashboard_sections: list[dict[str, str]],
    toolchain_status: dict[str, Any],
    gate_summary: dict[str, Any],
    link_rows: tuple[dict[str, str], ...],
    link_specs: Sequence[LinkSpec],
) -> dict[str, Any]:
    warnings = sorted(
        str(item)
        for item in (
            _as_list(dashboard_summary, "warnings")
            + _as_list(toolchain_status, "warnings")
            + _as_list(gate_summary, "warnings")
        )
    )
    failures = sorted(
        str(item)
        for item in (
            _as_list(dashboard_summary, "failures")
            + _as_list(toolchain_status, "failures")
            + _as_list(gate_summary, "failures")
        )
    )
    optional_ids = {spec.link_id for spec in link_specs if spec.optional}
    missing_rows = [
        row
        for row in link_rows
        if row["target_exists"] != "True" and row["link_id"] not in optional_ids
    ]
    failures.extend(f"MISSING_LINK: {row['link_id']} -> {row['relative_path']}" for row in missing_rows)

    dashboard_status = str(dashboard_summary.get("dashboard_status", "UNKNOWN"))
    toolchain_state = str(toolchain_status.get("toolchain_status", "UNKNOWN"))
    latest_gate_status = str(gate_summary.get("gate_status", "UNKNOWN"))
    index_status = _derive_index_status(
        dashboard_status=dashboard_status,
        toolchain_status=toolchain_state,
        latest_gate_status=latest_gate_status,
        warnings=warnings,
        failures=failures,
    )
    no_side_effects = {
        "read_existing_p246_p247_p248_artifacts_only": True,
        "wrote_only_p249_index_outputs": True,
        "executed_existing_workflows": False,
        "regenerated_p237_to_p248_artifacts": False,
        "contacted_providers": False,
        "fetched_remote_sports_data": False,
        "used_pybaseball": False,
        "wrote_db": False,
        "wrote_data_runtime_logs_or_outputs": False,
        "mutated_p237_to_p248_source_artifacts": False,
        "computed_roi_pnl_ev_kelly": False,
        "created_betting_recommendations": False,
        "created_live_production_or_real_betting_output": False,
    }
    return {
        "generated_at_utc": generated_at_utc,
        "index_status": index_status,
        "input_paths": input_paths,
        "input_hashes": input_hashes,
        "dashboard_status": dashboard_status,
        "toolchain_status": toolchain_state,
        "latest_gate_status": latest_gate_status,
        "link_count": len(link_rows),
        "local_link_count": sum(1 for row in link_rows if row["target_exists"] == "True"),
        "missing_link_count": len(missing_rows),
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "output_files": output_files,
        "limitation_labels": _normalize_labels(dashboard_summary, toolchain_status, gate_summary),
        "no_side_effects": no_side_effects,
        "warnings": warnings,
        "failures": failures,
        "dashboard_section_count": len(dashboard_sections),
        "latest_gate_counts": gate_summary.get("check_counts", {}),
        "latest_gate_observed_counts": gate_summary.get("observed_counts", {}),
        "toolchain_step_count": _as_int(toolchain_status.get("step_count")),
        "artifact_roots_present": _as_int(toolchain_status.get("present_artifact_root_count")),
        "artifact_roots_total": _as_int(toolchain_status.get("artifact_root_count")),
        "scripts_present": _as_int(toolchain_status.get("present_script_count")),
        "scripts_total": _as_int(toolchain_status.get("script_count")),
    }


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _write_links_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LINK_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in LINK_CSV_FIELDNAMES})


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status_class(status: Any) -> str:
    value = str(status).lower()
    if value == "pass":
        return "pass"
    if value == "warn":
        return "warn"
    if value == "fail":
        return "fail"
    return "neutral"


def _metric(label: str, value: Any) -> str:
    return f'<div class="metric"><dt>{_e(label)}</dt><dd>{_e(value)}</dd></div>'


def _table(headers: tuple[str, ...], rows: Iterable[Iterable[Any]]) -> str:
    head = "".join(f"<th>{_e(header)}</th>" for header in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _links_table(rows: Iterable[dict[str, str]]) -> str:
    body = []
    for row in rows:
        href = row["relative_path"]
        body.append(
            "<tr>"
            f"<td>{_e(row['link_id'])}</td>"
            f'<td><a href="{_e(href)}">{_e(row["title"])}</a></td>'
            f"<td>{_e(row['category'])}</td>"
            f"<td>{_e(row['target_exists'])}</td>"
            f"<td>{_e(row['target_type'])}</td>"
            f"<td>{_e(row['notes'])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>ID</th><th>Title</th><th>Category</th>"
        "<th>Exists</th><th>Type</th><th>Notes</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _list_items(items: Iterable[Any], *, empty: str = "None") -> str:
    values = [str(item) for item in items]
    if not values:
        values = [empty]
    return "<ul>" + "".join(f"<li>{_e(value)}</li>" for value in values) + "</ul>"


def _filter_links(rows: tuple[dict[str, str], ...], *categories: str) -> list[dict[str, str]]:
    wanted = set(categories)
    return [row for row in rows if row["category"] in wanted]


def _write_html(path: Path, summary: dict[str, Any], link_rows: tuple[dict[str, str], ...]) -> None:
    boundary_rows = [(key, value) for key, value in sorted(summary["no_side_effects"].items())]
    input_rows = [(key, path, summary["input_hashes"][key]) for key, path in summary["input_paths"].items()]
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P249-A Paper Toolchain Index</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f6f7f8;
  --panel: #ffffff;
  --ink: #20262d;
  --muted: #5c6873;
  --line: #d7dde2;
  --pass: #196b43;
  --warn: #9a5b00;
  --fail: #a3322a;
  --neutral: #46515c;
  --link: #245b8f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.45;
}}
header, main {{
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}}
header {{ padding-bottom: 12px; }}
h1 {{
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 650;
  letter-spacing: 0;
}}
h2 {{
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 650;
  letter-spacing: 0;
}}
p {{ margin: 0; color: var(--muted); }}
a {{ color: var(--link); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
section {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin: 0 0 16px;
  padding: 18px;
  overflow: hidden;
}}
.status {{
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 10px;
  border-radius: 999px;
  color: #fff;
  font-weight: 650;
}}
.pass {{ background: var(--pass); }}
.warn {{ background: var(--warn); }}
.fail {{ background: var(--fail); }}
.neutral {{ background: var(--neutral); }}
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-top: 14px;
}}
.metric {{
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px;
  min-width: 0;
}}
.metric dt {{
  margin: 0 0 4px;
  color: var(--muted);
  font-size: 12px;
}}
.metric dd {{
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  overflow-wrap: anywhere;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}}
th, td {{
  border-bottom: 1px solid var(--line);
  padding: 8px 7px;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}}
th {{
  color: var(--muted);
  font-size: 12px;
  font-weight: 650;
}}
ul {{ margin: 0; padding-left: 20px; }}
.stack {{ display: grid; gap: 14px; }}
@media (max-width: 720px) {{
  header, main {{ padding-left: 14px; padding-right: 14px; }}
  h1 {{ font-size: 22px; }}
  section {{ padding: 14px; }}
}}
</style>
</head>
<body>
<header>
<h1>P249-A Paper Toolchain Index</h1>
<p>Generated at UTC: {_e(summary['generated_at_utc'])}</p>
</header>
<main>
<section id="summary">
<h2>Summary <span class="status {_status_class(summary['index_status'])}">{_e(summary['index_status'])}</span></h2>
<div class="metrics">
{_metric("Dashboard status", summary["dashboard_status"])}
{_metric("Toolchain status", summary["toolchain_status"])}
{_metric("Latest P246 gate", summary["latest_gate_status"])}
{_metric("Local links", f"{summary['local_link_count']} / {summary['link_count']}")}
{_metric("Warnings", summary["warning_count"])}
{_metric("Failures", summary["failure_count"])}
</div>
{_table(("Input", "Path", "SHA-256"), input_rows)}
</section>
<section id="launch-links">
<h2>Launch Links</h2>
{_links_table(_filter_links(link_rows, "launch"))}
</section>
<section id="dashboard">
<h2>Dashboard</h2>
<div class="metrics">
{_metric("P248 dashboard status", summary["dashboard_status"])}
{_metric("P248 sections", summary["dashboard_section_count"])}
</div>
{_links_table(_filter_links(link_rows, "dashboard"))}
</section>
<section id="latest-gate">
<h2>Latest Gate</h2>
<div class="metrics">
{_metric("P246 gate status", summary["latest_gate_status"])}
{_metric("P246 checks", json.dumps(summary["latest_gate_counts"], sort_keys=True, separators=(",", ":")))}
</div>
{_links_table(_filter_links(link_rows, "latest_gate"))}
</section>
<section id="toolchain-status">
<h2>Toolchain Status</h2>
<div class="metrics">
{_metric("P247 status", summary["toolchain_status"])}
{_metric("Steps", summary["toolchain_step_count"])}
{_metric("Artifact roots", f"{summary['artifact_roots_present']} / {summary['artifact_roots_total']}")}
{_metric("Scripts", f"{summary['scripts_present']} / {summary['scripts_total']}")}
</div>
{_links_table(_filter_links(link_rows, "toolchain_status"))}
</section>
<section id="catalog-query-diff">
<h2>Catalog / Query / Diff</h2>
{_links_table(_filter_links(link_rows, "catalog_query_diff"))}
</section>
<section id="scripts">
<h2>Scripts</h2>
<div class="stack">
{_links_table(_filter_links(link_rows, "scripts"))}
{_links_table(_filter_links(link_rows, "reports"))}
</div>
</section>
<section id="safety-boundaries">
<h2>Safety Boundaries</h2>
{_table(("Boundary", "Value"), boundary_rows)}
</section>
<section id="limitations">
<h2>Limitations</h2>
{_list_items(summary["limitation_labels"])}
</section>
<section id="not-claims">
<h2>Not Claims</h2>
{_list_items(NOT_CLAIMS)}
</section>
</main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def build_paper_toolchain_index(
    *,
    dashboard_summary_json: Path = DEFAULT_DASHBOARD_SUMMARY_JSON,
    dashboard_sections_csv: Path = DEFAULT_DASHBOARD_SECTIONS_CSV,
    dashboard_html: Path = DEFAULT_DASHBOARD_HTML,
    toolchain_status_json: Path = DEFAULT_TOOLCHAIN_STATUS_JSON,
    gate_summary_json: Path = DEFAULT_GATE_SUMMARY_JSON,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
    link_specs: Sequence[LinkSpec] = DEFAULT_LINK_SPECS,
) -> PaperToolchainIndexResult:
    dashboard_summary_json = Path(dashboard_summary_json)
    dashboard_sections_csv = Path(dashboard_sections_csv)
    dashboard_html = Path(dashboard_html)
    toolchain_status_json = Path(toolchain_status_json)
    gate_summary_json = Path(gate_summary_json)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    dashboard_summary = _read_json_object(dashboard_summary_json, "dashboard summary JSON")
    dashboard_sections = _read_dashboard_sections(dashboard_sections_csv)
    _read_existing_text(dashboard_html, "dashboard HTML")
    toolchain_status = _read_json_object(toolchain_status_json, "toolchain status JSON")
    gate_summary = _read_json_object(gate_summary_json, "gate summary JSON")

    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = _input_paths(
        dashboard_summary_json=dashboard_summary_json,
        dashboard_sections_csv=dashboard_sections_csv,
        dashboard_html=dashboard_html,
        toolchain_status_json=toolchain_status_json,
        gate_summary_json=gate_summary_json,
    )
    hashes = _input_hashes(inputs)
    outputs = _output_files(output_dir)
    link_rows = _link_rows(output_dir, link_specs)
    summary = _build_summary(
        generated_at_utc=generated_at_utc,
        input_paths=inputs,
        input_hashes=hashes,
        output_files=outputs,
        dashboard_summary=dashboard_summary,
        dashboard_sections=dashboard_sections,
        toolchain_status=toolchain_status,
        gate_summary=gate_summary,
        link_rows=link_rows,
        link_specs=link_specs,
    )

    summary_path = output_dir / INDEX_SUMMARY_FILENAME
    links_path = output_dir / INDEX_LINKS_FILENAME
    html_path = output_dir / INDEX_HTML_FILENAME
    _stable_json_write(summary_path, summary)
    _write_links_csv(links_path, link_rows)
    _write_html(html_path, summary, link_rows)

    return PaperToolchainIndexResult(
        summary=summary,
        link_rows=link_rows,
        output_paths=outputs,
    )
