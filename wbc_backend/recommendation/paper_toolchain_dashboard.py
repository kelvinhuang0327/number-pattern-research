"""Static dashboard generator for committed P247 paper toolchain status artifacts.

This module reads the existing P247 status pack and writes a local, self-contained
P248 dashboard. It does not execute earlier workflow/query/diff/gate/status
scripts, contact providers, write DB/data/runtime/log state, or compute betting
performance.
"""
from __future__ import annotations

import csv
import html
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TOOLCHAIN_STATUS_JSON = ROOT / "report" / "p247a_paper_toolchain_status" / "toolchain_status.json"
DEFAULT_TOOLCHAIN_STEPS_CSV = ROOT / "report" / "p247a_paper_toolchain_status" / "toolchain_steps.csv"
DEFAULT_TOOLCHAIN_REPORT_MD = ROOT / "report" / "p247a_paper_toolchain_status" / "toolchain_report.md"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p248a_paper_toolchain_dashboard"
DEFAULT_GENERATED_AT_UTC = None

DASHBOARD_SUMMARY_FILENAME = "dashboard_summary.json"
DASHBOARD_SECTIONS_FILENAME = "dashboard_sections.csv"
DASHBOARD_HTML_FILENAME = "dashboard.html"

SECTION_CSV_FIELDNAMES = [
    "section_id",
    "section_title",
    "source",
    "status",
    "item_count",
    "notes",
]

REQUIRED_STEP_COLUMNS = (
    "step_id",
    "step_name",
    "script_path",
    "script_present",
    "artifact_root_or_file",
    "artifact_present",
    "file_count",
    "total_bytes",
    "status",
    "sha256_or_digest",
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


class PaperToolchainDashboardError(RuntimeError):
    """Raised when the P247 input status pack cannot be read safely."""


@dataclass(frozen=True)
class PaperToolchainDashboardResult:
    summary: dict[str, Any]
    section_rows: tuple[dict[str, str], ...]
    output_paths: dict[str, str]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _stable_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PaperToolchainDashboardError(f"MISSING_INPUT: {label} not found: {_display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperToolchainDashboardError(
            f"CORRUPT_INPUT: {label} invalid JSON: {_display_path(path)}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperToolchainDashboardError(
            f"CORRUPT_INPUT: {label} JSON must be an object: {_display_path(path)}"
        )
    return payload


def _read_steps_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperToolchainDashboardError(f"MISSING_INPUT: toolchain steps CSV not found: {_display_path(path)}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            missing = [column for column in REQUIRED_STEP_COLUMNS if column not in fieldnames]
            if missing:
                raise PaperToolchainDashboardError(
                    "CORRUPT_INPUT: toolchain steps CSV missing required columns: "
                    + ", ".join(missing)
                )
            return [{column: row.get(column, "") for column in REQUIRED_STEP_COLUMNS} for row in reader]
    except csv.Error as exc:
        raise PaperToolchainDashboardError(
            f"CORRUPT_INPUT: toolchain steps CSV invalid: {_display_path(path)}: {exc}"
        ) from exc


def _read_report_markdown(path: Path) -> str:
    if not path.is_file():
        raise PaperToolchainDashboardError(f"MISSING_INPUT: toolchain report Markdown not found: {_display_path(path)}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise PaperToolchainDashboardError(
            f"CORRUPT_INPUT: toolchain report Markdown is empty: {_display_path(path)}"
        )
    return text


def _input_paths(
    *,
    toolchain_status_json: Path,
    toolchain_steps_csv: Path,
    toolchain_report_md: Path,
) -> dict[str, str]:
    return {
        "toolchain_status_json": _display_path(toolchain_status_json),
        "toolchain_steps_csv": _display_path(toolchain_steps_csv),
        "toolchain_report_md": _display_path(toolchain_report_md),
    }


def _input_hashes(input_paths: dict[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, display_path in input_paths.items():
        path = ROOT / display_path
        if not path.is_file():
            path = Path(display_path)
        hashes[key] = _sha256(path)
    return hashes


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list_value(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    return value if isinstance(value, list) else [value]


def _derive_dashboard_status(toolchain_status: str, latest_gate_status: str, failures: list[Any], warnings: list[Any]) -> str:
    if failures or toolchain_status == "FAIL" or latest_gate_status == "FAIL":
        return "FAIL"
    if warnings or toolchain_status == "WARN" or latest_gate_status == "WARN":
        return "WARN"
    if toolchain_status == "PASS" and latest_gate_status == "PASS":
        return "PASS"
    return "WARN"


def _artifact_roots(status_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_hashes = status_payload.get("source_hashes", {})
    if not isinstance(source_hashes, dict):
        return {}
    artifact_roots = source_hashes.get("artifact_roots", {})
    return artifact_roots if isinstance(artifact_roots, dict) else {}


def _scripts(status_payload: dict[str, Any]) -> dict[str, str]:
    source_hashes = status_payload.get("source_hashes", {})
    if not isinstance(source_hashes, dict):
        return {}
    scripts = source_hashes.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _modules(status_payload: dict[str, Any]) -> dict[str, str]:
    source_hashes = status_payload.get("source_hashes", {})
    if not isinstance(source_hashes, dict):
        return {}
    modules = source_hashes.get("modules", {})
    return modules if isinstance(modules, dict) else {}


def _output_files(output_dir: Path) -> dict[str, str]:
    return {
        "dashboard_summary_json": _display_path(output_dir / DASHBOARD_SUMMARY_FILENAME),
        "dashboard_sections_csv": _display_path(output_dir / DASHBOARD_SECTIONS_FILENAME),
        "dashboard_html": _display_path(output_dir / DASHBOARD_HTML_FILENAME),
    }


def _build_summary(
    *,
    generated_at_utc: str,
    status_payload: dict[str, Any],
    step_rows: list[dict[str, str]],
    input_paths: dict[str, str],
    input_hashes: dict[str, str],
    output_files: dict[str, str],
) -> dict[str, Any]:
    warnings = [str(item) for item in _list_value(status_payload, "warnings")]
    failures = [str(item) for item in _list_value(status_payload, "failures")]
    toolchain_status = str(status_payload.get("toolchain_status", "UNKNOWN"))
    latest_gate_status = str(status_payload.get("latest_gate_status", "UNKNOWN"))
    dashboard_status = _derive_dashboard_status(toolchain_status, latest_gate_status, failures, warnings)
    limitation_labels = [str(item) for item in _list_value(status_payload, "limitation_labels")]
    for required_label in REQUIRED_LIMITATION_LABELS:
        if required_label not in limitation_labels:
            limitation_labels.append(required_label)

    no_side_effects = dict(status_payload.get("no_side_effects", {}))
    no_side_effects.update(
        {
            "read_existing_p247_artifacts_only": True,
            "executed_existing_workflows": False,
            "regenerated_p237_to_p247_artifacts": False,
            "contacted_providers": False,
            "fetched_remote_sports_data": False,
            "used_pybaseball": False,
            "wrote_db": False,
            "wrote_data_runtime_logs_or_outputs": False,
            "mutated_p237_to_p247_source_artifacts": False,
            "computed_roi_pnl_ev_kelly": False,
            "created_betting_recommendations": False,
            "created_live_production_or_real_betting_output": False,
        }
    )

    artifact_roots = _artifact_roots(status_payload)
    scripts = _scripts(status_payload)
    return {
        "generated_at_utc": generated_at_utc,
        "dashboard_status": dashboard_status,
        "input_paths": input_paths,
        "input_hashes": input_hashes,
        "toolchain_status": toolchain_status,
        "artifact_roots_present": _as_int(status_payload.get("present_artifact_root_count")),
        "artifact_roots_total": _as_int(status_payload.get("artifact_root_count")),
        "scripts_present": _as_int(status_payload.get("present_script_count")),
        "scripts_total": _as_int(status_payload.get("script_count")),
        "latest_gate_status": latest_gate_status,
        "latest_gate_counts": status_payload.get("latest_gate_counts", {}),
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "section_count": 10,
        "output_files": output_files,
        "limitation_labels": limitation_labels,
        "no_side_effects": no_side_effects,
        "warnings": sorted(warnings),
        "failures": sorted(failures),
        "toolchain_steps": step_rows,
        "artifact_roots": dict(sorted(artifact_roots.items())),
        "scripts": dict(sorted(scripts.items())),
        "modules": dict(sorted(_modules(status_payload).items())),
    }


def _section_rows(summary: dict[str, Any]) -> tuple[dict[str, str], ...]:
    warnings_failures_count = summary["warning_count"] + summary["failure_count"]
    rows = [
        {
            "section_id": "summary",
            "section_title": "Summary",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": summary["dashboard_status"],
            "item_count": 6,
            "notes": f"toolchain={summary['toolchain_status']}",
        },
        {
            "section_id": "latest_gate",
            "section_title": "Latest Gate",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": summary["latest_gate_status"],
            "item_count": 1,
            "notes": "P246 gate status rendered",
        },
        {
            "section_id": "toolchain_steps",
            "section_title": "Toolchain Steps",
            "source": summary["input_paths"]["toolchain_steps_csv"],
            "status": summary["toolchain_status"],
            "item_count": len(summary["toolchain_steps"]),
            "notes": "stable CSV order preserved",
        },
        {
            "section_id": "artifact_roots",
            "section_title": "Artifact Roots",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": summary["dashboard_status"],
            "item_count": len(summary["artifact_roots"]),
            "notes": f"{summary['artifact_roots_present']} / {summary['artifact_roots_total']} present",
        },
        {
            "section_id": "scripts",
            "section_title": "Scripts",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": summary["dashboard_status"],
            "item_count": len(summary["scripts"]),
            "notes": f"{summary['scripts_present']} / {summary['scripts_total']} present",
        },
        {
            "section_id": "hashes",
            "section_title": "Hashes",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": "PASS",
            "item_count": len(summary["input_hashes"]) + len(summary["modules"]),
            "notes": "input and module hashes rendered",
        },
        {
            "section_id": "warnings_failures",
            "section_title": "Warnings / Failures",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": "PASS" if warnings_failures_count == 0 else summary["dashboard_status"],
            "item_count": warnings_failures_count,
            "notes": "none" if warnings_failures_count == 0 else "warnings or failures present",
        },
        {
            "section_id": "safety_boundaries",
            "section_title": "Safety Boundaries",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": "PASS",
            "item_count": len(summary["no_side_effects"]),
            "notes": "result-only boundaries rendered",
        },
        {
            "section_id": "limitations",
            "section_title": "Limitations",
            "source": summary["input_paths"]["toolchain_status_json"],
            "status": "PASS",
            "item_count": len(summary["limitation_labels"]),
            "notes": "required labels rendered",
        },
        {
            "section_id": "not_claims",
            "section_title": "Not Claims",
            "source": summary["input_paths"]["toolchain_report_md"],
            "status": "PASS",
            "item_count": len(NOT_CLAIMS),
            "notes": "forbidden claims excluded",
        },
    ]
    return tuple(rows)


def _write_sections_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SECTION_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in SECTION_CSV_FIELDNAMES})


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
    body_lines = []
    for row in rows:
        body_lines.append("<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body_lines) + "</tbody></table>"


def _list_items(items: Iterable[Any], *, empty: str = "None") -> str:
    values = [str(item) for item in items]
    if not values:
        values = [empty]
    return "<ul>" + "".join(f"<li>{_e(value)}</li>" for value in values) + "</ul>"


def _write_html(path: Path, summary: dict[str, Any], section_rows: tuple[dict[str, str], ...]) -> None:
    artifact_rows = [
        (
            artifact_path,
            details.get("present", ""),
            details.get("file_count", ""),
            details.get("total_bytes", ""),
            details.get("sha256_or_digest", ""),
        )
        for artifact_path, details in summary["artifact_roots"].items()
    ]
    script_rows = [(script_path, digest) for script_path, digest in summary["scripts"].items()]
    input_hash_rows = [(name, summary["input_paths"][name], digest) for name, digest in summary["input_hashes"].items()]
    module_hash_rows = [(module_path, digest) for module_path, digest in summary["modules"].items()]
    step_rows = [
        (
            row["step_id"],
            row["step_name"],
            row["status"],
            row["script_present"],
            row["artifact_present"],
            row["file_count"],
            row["total_bytes"],
            row["sha256_or_digest"],
        )
        for row in summary["toolchain_steps"]
    ]
    boundary_rows = [(key, value) for key, value in sorted(summary["no_side_effects"].items())]
    section_table_rows = [
        (
            row["section_id"],
            row["section_title"],
            row["status"],
            row["item_count"],
            row["notes"],
        )
        for row in section_rows
    ]
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P248-A Paper Toolchain Dashboard</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f7f8fa;
  --panel: #ffffff;
  --ink: #1d252c;
  --muted: #5f6b76;
  --line: #d8dde3;
  --pass: #196b43;
  --warn: #9a5b00;
  --fail: #a3322a;
  --neutral: #46515c;
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
header {{
  padding-top: 28px;
  padding-bottom: 12px;
}}
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
p {{
  margin: 0;
  color: var(--muted);
}}
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
ul {{
  margin: 0;
  padding-left: 20px;
}}
code {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}}
.stack {{
  display: grid;
  gap: 14px;
}}
@media (max-width: 720px) {{
  header, main {{ padding-left: 14px; padding-right: 14px; }}
  h1 {{ font-size: 22px; }}
  section {{ padding: 14px; }}
}}
</style>
</head>
<body>
<header>
<h1>P248-A Paper Toolchain Dashboard</h1>
<p>Generated at UTC: {_e(summary['generated_at_utc'])}</p>
</header>
<main>
<section id="summary">
<h2>Summary <span class="status {_status_class(summary['dashboard_status'])}">{_e(summary['dashboard_status'])}</span></h2>
<div class="metrics">
{_metric("Toolchain status", summary["toolchain_status"])}
{_metric("Latest P246 gate", summary["latest_gate_status"])}
{_metric("Artifact roots", f"{summary['artifact_roots_present']} / {summary['artifact_roots_total']}")}
{_metric("Scripts", f"{summary['scripts_present']} / {summary['scripts_total']}")}
{_metric("Warnings", summary["warning_count"])}
{_metric("Failures", summary["failure_count"])}
</div>
{_table(("Section", "Title", "Status", "Items", "Notes"), section_table_rows)}
</section>
<section id="latest-gate">
<h2>Latest Gate</h2>
<div class="metrics">
{_metric("P246 gate status", summary["latest_gate_status"])}
{_metric("P246 gate counts", json.dumps(summary["latest_gate_counts"], sort_keys=True, separators=(",", ":")))}
</div>
</section>
<section id="toolchain-steps">
<h2>Toolchain Steps</h2>
{_table(("Step", "Name", "Status", "Script", "Artifact", "Files", "Bytes", "Digest"), step_rows)}
</section>
<section id="artifact-roots">
<h2>Artifact Roots</h2>
{_table(("Path", "Present", "Files", "Bytes", "Digest"), artifact_rows)}
</section>
<section id="scripts">
<h2>Scripts</h2>
{_table(("Path", "SHA-256"), script_rows)}
</section>
<section id="hashes">
<h2>Hashes</h2>
<div class="stack">
{_table(("Input", "Path", "SHA-256"), input_hash_rows)}
{_table(("Module", "SHA-256"), module_hash_rows)}
</div>
</section>
<section id="warnings-failures">
<h2>Warnings / Failures</h2>
<div class="stack">
<div><strong>Warnings</strong>{_list_items(summary["warnings"])}</div>
<div><strong>Failures</strong>{_list_items(summary["failures"])}</div>
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


def build_paper_toolchain_dashboard(
    *,
    toolchain_status_json: Path = DEFAULT_TOOLCHAIN_STATUS_JSON,
    toolchain_steps_csv: Path = DEFAULT_TOOLCHAIN_STEPS_CSV,
    toolchain_report_md: Path = DEFAULT_TOOLCHAIN_REPORT_MD,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperToolchainDashboardResult:
    toolchain_status_json = Path(toolchain_status_json)
    toolchain_steps_csv = Path(toolchain_steps_csv)
    toolchain_report_md = Path(toolchain_report_md)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    status_payload = _read_json_object(toolchain_status_json, "toolchain status JSON")
    step_rows = _read_steps_csv(toolchain_steps_csv)
    _read_report_markdown(toolchain_report_md)
    inputs = _input_paths(
        toolchain_status_json=toolchain_status_json,
        toolchain_steps_csv=toolchain_steps_csv,
        toolchain_report_md=toolchain_report_md,
    )
    hashes = _input_hashes(inputs)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = _output_files(output_dir)
    summary = _build_summary(
        generated_at_utc=generated_at_utc,
        status_payload=status_payload,
        step_rows=step_rows,
        input_paths=inputs,
        input_hashes=hashes,
        output_files=outputs,
    )
    section_rows = _section_rows(summary)
    summary["section_count"] = len(section_rows)

    summary_path = output_dir / DASHBOARD_SUMMARY_FILENAME
    sections_path = output_dir / DASHBOARD_SECTIONS_FILENAME
    html_path = output_dir / DASHBOARD_HTML_FILENAME
    _stable_json_write(summary_path, summary)
    _write_sections_csv(sections_path, section_rows)
    _write_html(html_path, summary, section_rows)

    return PaperToolchainDashboardResult(
        summary=summary,
        section_rows=section_rows,
        output_paths=outputs,
    )
