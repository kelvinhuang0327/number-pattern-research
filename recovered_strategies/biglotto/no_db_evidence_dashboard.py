"""P364 no-DB evidence dashboard and query CLI for Big Lotto.

This module reads only the committed P363 evidence-pack artifacts and renders
derived inspection artifacts: a JSON index, sorted CSV tables, a static HTML
dashboard, and a generation manifest. It does not open or write a DB, import
production registries, call adapters, re-score strategies, deploy, or make
future-performance or betting claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P364_biglotto_evidence_dashboard"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"

P363_SOURCE_ARTIFACTS = (
    ("p363_summary", "artifacts/P363_biglotto_evidence_pack_summary.csv"),
    ("p363_adapter_cards", "artifacts/P363_biglotto_evidence_pack_adapter_cards.csv"),
    ("p363_subset_cards", "artifacts/P363_biglotto_evidence_pack_subset_cards.csv"),
    ("p363_consistency_checks", "artifacts/P363_biglotto_evidence_pack_consistency_checks.csv"),
    ("p363_manifest", "artifacts/P363_biglotto_evidence_pack_manifest.csv"),
    ("p363_report", "artifacts/P363_biglotto_evidence_pack_report.md"),
)

ADAPTER_TABLE_COLUMNS = (
    "display_rank",
    "adapter_function",
    "strategy_id",
    "bet_count",
    "p360_windows_present",
    "p360_hit_rate_w30",
    "p360_edge_w30",
    "p360_hit_rate_w150",
    "p360_edge_w150",
    "p360_hit_rate_w750",
    "p360_edge_w750",
    "p360_hit_rate_w1500",
    "p360_edge_w1500",
    "p361_total_hit_count",
    "p361_unique_hit_count",
    "p361_candidate_marginal_share_full_context",
    "p361_redundancy_note",
    "p362_singleton_average_rank_by_coverage_rate",
    "p362_singleton_top_3_window_count",
    "p362_singleton_within_3_hits_window_count",
    "p362_stability_note",
    "caveat",
)

SUBSET_TABLE_COLUMNS = (
    "display_rank",
    "adapter_subset",
    "subset_size",
    "subset_is_full_cohort",
    "p361_rank_within_subset_size",
    "p361_best_subset_for_size",
    "p361_period_count",
    "p361_any_hit_count",
    "p361_coverage_rate",
    "p361_duplicate_hit_events",
    "p361_mean_pairwise_jaccard",
    "p362_windows_evaluated",
    "p362_average_rank_by_coverage_rate",
    "p362_rank_variance_by_coverage_rate",
    "p362_top_1_window_count",
    "p362_top_3_window_count",
    "p362_within_3_hits_window_count",
    "compact_candidate_row_types",
    "compact_candidate_windows",
    "p362_stability_note",
    "caveat",
)

CONSISTENCY_CHECK_COLUMNS = ("check_name", "status", "expected", "actual", "details")

MANIFEST_COLUMNS = (
    "artifact_group",
    "artifact_role",
    "path",
    "row_count",
    "sha256",
    "no_db_open_write",
    "details",
)

ARTIFACT_BASENAMES = {
    "index": "P364_biglotto_evidence_dashboard_index.json",
    "adapter_table": "P364_biglotto_evidence_dashboard_adapter_table.csv",
    "subset_table": "P364_biglotto_evidence_dashboard_subset_table.csv",
    "html": "P364_biglotto_evidence_dashboard.html",
    "manifest": "P364_biglotto_evidence_dashboard_manifest.csv",
}

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No production registry import.",
    "No adapter calls.",
    "No deploy.",
    "No new scoring cohort.",
    "No blended leaderboard.",
    "Shape-only and blocked targets remain excluded.",
)


class EvidenceDashboardError(RuntimeError):
    """P363 evidence artifacts are missing or malformed."""


@dataclass(frozen=True)
class DashboardOutput:
    index: dict[str, object]
    adapter_rows: tuple[dict[str, str], ...]
    subset_rows: tuple[dict[str, str], ...]
    consistency_rows: tuple[dict[str, str], ...]
    manifest_rows: tuple[dict[str, str], ...]
    html_text: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with open(path, newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    paths = tuple(root / relpath for _role, relpath in P363_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise EvidenceDashboardError(f"required P363 evidence pack artifacts missing: {missing}")
    return paths


def _source_inventory(repo_root: Path) -> tuple[dict[str, str], ...]:
    rows = []
    for role, relpath in P363_SOURCE_ARTIFACTS:
        path = repo_root / relpath
        row_count = ""
        if path.suffix == ".csv":
            row_count = str(len(read_csv_rows(path)))
        rows.append(
            {
                "artifact_role": role,
                "path": relpath,
                "file_type": path.suffix.lstrip("."),
                "row_count": row_count,
                "sha256": sha256_file(path),
            }
        )
    return tuple(rows)


def _as_int(value: str) -> int:
    return int(value) if value else 0


def _as_float(value: str) -> float:
    return float(value) if value else 0.0


def _sort_adapter_rows(rows: Iterable[Mapping[str, str]]) -> tuple[dict[str, str], ...]:
    sorted_rows = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            -_as_int(row["p361_total_hit_count"]),
            -_as_int(row["p361_unique_hit_count"]),
            _as_float(row["p362_singleton_average_rank_by_coverage_rate"]),
            row["adapter_function"],
        ),
    )
    return tuple(
        {"display_rank": str(index), **{column: row.get(column, "") for column in ADAPTER_TABLE_COLUMNS[1:]}}
        for index, row in enumerate(sorted_rows, start=1)
    )


def _sort_subset_rows(rows: Iterable[Mapping[str, str]]) -> tuple[dict[str, str], ...]:
    sorted_rows = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            _as_int(row["subset_size"]),
            -_as_int(row["p361_any_hit_count"]),
            _as_float(row["p362_average_rank_by_coverage_rate"]),
            row["adapter_subset"],
        ),
    )
    return tuple(
        {"display_rank": str(index), **{column: row.get(column, "") for column in SUBSET_TABLE_COLUMNS[1:]}}
        for index, row in enumerate(sorted_rows, start=1)
    )


def _consistency_summary(rows: Iterable[Mapping[str, str]]) -> dict[str, object]:
    rows = tuple(rows)
    pass_count = sum(1 for row in rows if row.get("status") == "PASS")
    fail_count = sum(1 for row in rows if row.get("status") == "FAIL")
    warning_count = sum(1 for row in rows if row.get("status") not in {"PASS", "FAIL"})
    return {
        "total": len(rows),
        "pass": pass_count,
        "fail": fail_count,
        "warning": warning_count,
        "failures": [dict(row) for row in rows if row.get("status") == "FAIL"],
        "warnings": [dict(row) for row in rows if row.get("status") not in {"PASS", "FAIL"}],
    }


def _top_compact_candidates(rows: Iterable[Mapping[str, str]], limit: int = 10) -> tuple[dict[str, str], ...]:
    candidates = [
        dict(row)
        for row in rows
        if row.get("compact_candidate_row_types") or row.get("subset_is_full_cohort") == "true"
    ]
    ordered = sorted(
        candidates,
        key=lambda row: (
            _as_int(row["subset_size"]),
            -_as_int(row["p361_any_hit_count"]),
            _as_float(row["p362_average_rank_by_coverage_rate"]),
            row["adapter_subset"],
        ),
    )
    return tuple(ordered[:limit])


def _summary_lookup(rows: Iterable[Mapping[str, str]]) -> dict[str, str]:
    return {f"{row['section']}.{row['key']}": row["value"] for row in rows}


def build_index(
    source_inventory: tuple[dict[str, str], ...],
    summary_rows: tuple[dict[str, str], ...],
    adapter_rows: tuple[dict[str, str], ...],
    subset_rows: tuple[dict[str, str], ...],
    consistency_rows: tuple[dict[str, str], ...],
) -> dict[str, object]:
    summary = _summary_lookup(summary_rows)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "scope": {
            "historical_descriptive_evidence_only": True,
            "future_prediction_guarantee": False,
            "betting_advice": False,
            "db_opened": False,
            "db_written": False,
            "production_registry_imported": False,
            "deployed": False,
            "new_scoring_cohort": False,
            "adapter_calls": False,
            "blended_leaderboard": False,
            "shape_only_and_blocked_targets_excluded": True,
        },
        "source_artifacts": tuple(dict(row) for row in source_inventory),
        "source_sha256": {row["path"]: row["sha256"] for row in source_inventory},
        "summary": summary,
        "adapter_card_count": len(adapter_rows),
        "subset_card_count": len(subset_rows),
        "consistency_check_summary": _consistency_summary(consistency_rows),
        "top_compact_candidates": _top_compact_candidates(subset_rows),
    }


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _json_text(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _table_html(columns: Sequence[str], rows: Iterable[Mapping[str, str]], limit: int | None = None) -> str:
    selected_rows = tuple(rows)[:limit]
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_lines = []
    for row in selected_rows:
        body_lines.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
            + "</tr>"
        )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_lines)}</tbody></table>"


def render_html_dashboard(
    index: Mapping[str, object],
    adapter_rows: tuple[dict[str, str], ...],
    subset_rows: tuple[dict[str, str], ...],
    consistency_rows: tuple[dict[str, str], ...],
    source_inventory: tuple[dict[str, str], ...],
) -> str:
    compact_rows = tuple(index["top_compact_candidates"])  # type: ignore[index]
    disclaimer = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>P364 Big Lotto no-DB Evidence Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1d252c;
      --muted: #5c6770;
      --line: #cbd5df;
      --panel: #f7f9fb;
      --banner: #f3ead2;
      --accent: #006d77;
      --danger: #9d2f2f;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.45;
    }}
    header, main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 32px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      margin: 0;
    }}
    .banner {{
      margin-top: 18px;
      padding: 14px 18px;
      background: var(--banner);
      border: 1px solid #dfc980;
      border-radius: 6px;
    }}
    .banner ul {{
      margin: 8px 0 0;
      padding-left: 22px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 18px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--panel);
      font-weight: 650;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
    }}
    .table-wrap table {{
      border: 0;
    }}
    .table-wrap th:first-child, .table-wrap td:first-child {{
      border-left: 0;
    }}
    .table-wrap th:last-child, .table-wrap td:last-child {{
      border-right: 0;
    }}
    .status-pass {{
      color: var(--accent);
      font-weight: 700;
    }}
    .status-fail {{
      color: var(--danger);
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <header>
    <h1>P364 Big Lotto no-DB Evidence Dashboard</h1>
    <p class="meta">Generated from committed P363 artifacts only. Generated at: {html.escape(str(index["generated_at"]))}</p>
    <div class="banner">
      <strong>Scope / disclaimer banner</strong>
      <ul>{disclaimer}</ul>
    </div>
    <div class="stats">
      <div class="stat"><strong>{len(adapter_rows)}</strong>Adapter cards</div>
      <div class="stat"><strong>{len(subset_rows)}</strong>Subset cards</div>
      <div class="stat"><strong>{len(consistency_rows)}</strong>Consistency checks</div>
      <div class="stat"><strong>{len(source_inventory)}</strong>Source artifacts</div>
    </div>
  </header>
  <main>
    <h2>Adapter Table</h2>
    <div class="table-wrap">{_table_html(ADAPTER_TABLE_COLUMNS, adapter_rows)}</div>

    <h2>Subset Table</h2>
    <div class="table-wrap">{_table_html(SUBSET_TABLE_COLUMNS, subset_rows)}</div>

    <h2>Compact Candidate Section</h2>
    <div class="table-wrap">{_table_html(("display_rank", "adapter_subset", "subset_size", "p361_any_hit_count", "p362_top_3_window_count", "compact_candidate_row_types", "compact_candidate_windows"), compact_rows)}</div>

    <h2>Consistency Check Section</h2>
    <div class="table-wrap">{_table_html(CONSISTENCY_CHECK_COLUMNS, consistency_rows)}</div>

    <h2>Source Artifact Inventory</h2>
    <div class="table-wrap">{_table_html(("artifact_role", "path", "file_type", "row_count", "sha256"), source_inventory)}</div>
  </main>
</body>
</html>
"""


def _artifact_contents(output: DashboardOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "adapter_table": _csv_text(ADAPTER_TABLE_COLUMNS, output.adapter_rows),
        "subset_table": _csv_text(SUBSET_TABLE_COLUMNS, output.subset_rows),
        "html": output.html_text,
        "manifest": _csv_text(MANIFEST_COLUMNS, output.manifest_rows),
    }


def _build_manifest_rows(
    source_inventory: tuple[dict[str, str], ...],
    output_rows: Mapping[str, tuple[Mapping[str, str], ...] | Mapping[str, object] | str],
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for row in source_inventory:
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": row["artifact_role"],
                "path": row["path"],
                "row_count": row["row_count"],
                "sha256": row["sha256"],
                "no_db_open_write": "YES",
                "details": "P363 evidence-pack source artifact.",
            }
        )
    for role, basename in ARTIFACT_BASENAMES.items():
        if role == "manifest":
            row_count = str(len(source_inventory) + len(ARTIFACT_BASENAMES) + 1)
            sha256 = ""
            details = "P364 manifest records deterministic source/output inventory; self SHA omitted."
        else:
            value = output_rows[role]
            if isinstance(value, tuple):
                row_count = str(len(value))
            elif isinstance(value, Mapping):
                row_count = "1"
            else:
                row_count = ""
            text = output_rows[f"{role}_text"]
            sha256 = sha256_bytes(str(text).encode("utf-8"))
            details = "P364 derived output artifact."
        rows.append(
            {
                "artifact_group": "output",
                "artifact_role": role,
                "path": f"artifacts/{basename}",
                "row_count": row_count,
                "sha256": sha256,
                "no_db_open_write": "YES",
                "details": details,
            }
        )
    rows.append(
        {
            "artifact_group": "statement",
            "artifact_role": "no_db_open_write",
            "path": "",
            "row_count": "",
            "sha256": "",
            "no_db_open_write": "YES",
            "details": (
                "P364 reads only merged P363 evidence-pack artifacts; no DB open/write, "
                "no adapter calls, no scoring cohort, no production registry import, no deploy."
            ),
        }
    )
    return tuple(rows)


def run_dashboard(repo_root: Path | None = None) -> DashboardOutput:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    verify_required_artifacts(root)
    summary_rows = read_csv_rows(root / "artifacts/P363_biglotto_evidence_pack_summary.csv")
    p363_adapter_rows = read_csv_rows(root / "artifacts/P363_biglotto_evidence_pack_adapter_cards.csv")
    p363_subset_rows = read_csv_rows(root / "artifacts/P363_biglotto_evidence_pack_subset_cards.csv")
    consistency_rows = read_csv_rows(root / "artifacts/P363_biglotto_evidence_pack_consistency_checks.csv")
    source_inventory = _source_inventory(root)
    adapter_rows = _sort_adapter_rows(p363_adapter_rows)
    subset_rows = _sort_subset_rows(p363_subset_rows)
    index = build_index(source_inventory, summary_rows, adapter_rows, subset_rows, consistency_rows)
    html_text = render_html_dashboard(index, adapter_rows, subset_rows, consistency_rows, source_inventory)
    partial = {
        "index": index,
        "adapter_table": adapter_rows,
        "subset_table": subset_rows,
        "html": html_text,
        "index_text": _json_text(index),
        "adapter_table_text": _csv_text(ADAPTER_TABLE_COLUMNS, adapter_rows),
        "subset_table_text": _csv_text(SUBSET_TABLE_COLUMNS, subset_rows),
        "html_text": html_text,
    }
    manifest_rows = _build_manifest_rows(source_inventory, partial)
    return DashboardOutput(
        index=index,
        adapter_rows=adapter_rows,
        subset_rows=subset_rows,
        consistency_rows=consistency_rows,
        manifest_rows=manifest_rows,
        html_text=html_text,
    )


def _assert_deterministic(first: DashboardOutput, second: DashboardOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P364 dashboard artifacts are not reproducible")


def write_artifacts(output: DashboardOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        with open(path, "w", encoding="utf-8", newline="" if path.suffix == ".csv" else None) as handle:
            handle.write(contents[key])
    return paths


def _print_rows(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    rows = tuple(rows)
    if not rows:
        print("No rows.")
        return
    print(",".join(columns))
    for row in rows:
        print(",".join(str(row.get(column, "")) for column in columns))


def _filtered_subsets(
    rows: Iterable[Mapping[str, str]], subset_size: int | None, limit: int | None
) -> tuple[Mapping[str, str], ...]:
    filtered = tuple(row for row in rows if subset_size is None or int(row["subset_size"]) == subset_size)
    return filtered[:limit] if limit is not None else filtered


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    parser.add_argument("--generate", action="store_true", help="generate all P364 dashboard artifacts")
    parser.add_argument("--json", action="store_true", help="emit the JSON index to stdout")
    parser.add_argument("--top-adapters", type=int, metavar="N", help="print top N adapter cards as CSV")
    parser.add_argument("--top-subsets", type=int, metavar="N", help="print top N subset cards as CSV")
    parser.add_argument("--subset-size", type=int, choices=range(1, 6), help="filter subset card output by subset size")
    parser.add_argument("--checks", action="store_true", help="print consistency check failures/warnings, or all-pass summary")
    args = parser.parse_args(argv)

    first = run_dashboard()
    second = run_dashboard()
    _assert_deterministic(first, second)

    did_query = bool(args.json or args.top_adapters is not None or args.top_subsets is not None or args.checks)
    should_generate = args.generate or not did_query

    if should_generate:
        paths = write_artifacts(first, args.artifacts_dir)
        print("P364 no-DB evidence dashboard: determinism double-run PASS")
        print(f"adapter table rows: {len(first.adapter_rows)}")
        print(f"subset table rows: {len(first.subset_rows)}")
        print(f"consistency checks: {len(first.consistency_rows)}")
        print("No DB was opened or written; no adapters were called.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")

    if args.json:
        print(_json_text(first.index), end="")
    if args.top_adapters is not None:
        _print_rows(ADAPTER_TABLE_COLUMNS, first.adapter_rows[: args.top_adapters])
    if args.top_subsets is not None:
        rows = _filtered_subsets(first.subset_rows, args.subset_size, args.top_subsets)
        _print_rows(SUBSET_TABLE_COLUMNS, rows)
    elif args.subset_size is not None:
        rows = _filtered_subsets(first.subset_rows, args.subset_size, None)
        _print_rows(SUBSET_TABLE_COLUMNS, rows)
    if args.checks:
        summary = first.index["consistency_check_summary"]
        assert isinstance(summary, dict)
        failures = summary["failures"]
        warnings = summary["warnings"]
        if failures or warnings:
            _print_rows(CONSISTENCY_CHECK_COLUMNS, tuple(failures) + tuple(warnings))  # type: ignore[arg-type]
        else:
            print(
                "Consistency checks: "
                f"{summary['pass']} PASS, {summary['fail']} FAIL, {summary['warning']} WARNING"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
