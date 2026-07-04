"""P365 no-DB evidence explorer for Big Lotto parity adapters.

This module reads only committed P363/P364 evidence artifacts and renders
detail cards, pairwise comparison rows, query snapshots, and a static HTML
explorer. It does not open or write a DB, import production registries, call
adapters, re-score strategies, deploy, or make future-performance or betting
claims.
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
TASK = "P365_biglotto_evidence_explorer"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"

P365_SOURCE_ARTIFACTS = (
    ("p363_summary", "artifacts/P363_biglotto_evidence_pack_summary.csv"),
    ("p363_adapter_cards", "artifacts/P363_biglotto_evidence_pack_adapter_cards.csv"),
    ("p363_subset_cards", "artifacts/P363_biglotto_evidence_pack_subset_cards.csv"),
    ("p363_consistency_checks", "artifacts/P363_biglotto_evidence_pack_consistency_checks.csv"),
    ("p363_manifest", "artifacts/P363_biglotto_evidence_pack_manifest.csv"),
    ("p363_report", "artifacts/P363_biglotto_evidence_pack_report.md"),
    ("p364_index", "artifacts/P364_biglotto_evidence_dashboard_index.json"),
    ("p364_adapter_table", "artifacts/P364_biglotto_evidence_dashboard_adapter_table.csv"),
    ("p364_subset_table", "artifacts/P364_biglotto_evidence_dashboard_subset_table.csv"),
    ("p364_html", "artifacts/P364_biglotto_evidence_dashboard.html"),
    ("p364_manifest", "artifacts/P364_biglotto_evidence_dashboard_manifest.csv"),
)

PAIRWISE_COLUMNS = (
    "display_rank",
    "adapter_a",
    "adapter_b",
    "adapter_pair",
    "p363_pair_subset",
    "subset_size",
    "p361_period_count",
    "p361_pair_any_hit_count",
    "p361_pair_coverage_rate",
    "p361_pair_duplicate_hit_events",
    "p361_pair_mean_pairwise_jaccard",
    "p362_windows_evaluated",
    "p362_average_rank_by_coverage_rate",
    "p362_top_3_window_count",
    "p362_within_3_hits_window_count",
    "redundancy_scope",
    "caveat",
)

SHORTLIST_COLUMNS = (
    "display_rank",
    "adapter_subset",
    "subset_size",
    "p361_any_hit_count",
    "p361_coverage_rate",
    "p362_average_rank_by_coverage_rate",
    "p362_top_3_window_count",
    "compact_candidate_row_types",
    "compact_candidate_windows",
    "why_compact_historically",
    "what_it_does_not_prove",
    "caveat",
)

MANIFEST_COLUMNS = (
    "artifact_group",
    "artifact_role",
    "path",
    "object_count",
    "row_count",
    "sha256",
    "no_db_open_write",
    "no_adapter_calls",
    "details",
)

ARTIFACT_BASENAMES = {
    "adapter_detail_cards": "P365_biglotto_evidence_explorer_adapter_detail_cards.json",
    "subset_detail_cards": "P365_biglotto_evidence_explorer_subset_detail_cards.json",
    "pairwise_comparison": "P365_biglotto_evidence_explorer_pairwise_comparison.csv",
    "compact_shortlist": "P365_biglotto_evidence_explorer_compact_shortlist.csv",
    "query_snapshots": "P365_biglotto_evidence_explorer_query_snapshots.json",
    "html": "P365_biglotto_evidence_explorer.html",
    "manifest": "P365_biglotto_evidence_explorer_manifest.csv",
}

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No production registry import.",
    "No deploy.",
    "No new scoring cohort.",
    "No adapter calls.",
    "No blended leaderboard.",
    "Shape-only and blocked targets remain excluded.",
)

CAVEATS = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No production registry import.",
    "No deploy.",
    "No new scoring cohort.",
    "No adapter calls.",
    "No blended leaderboard.",
    "Shape-only and blocked targets remain excluded.",
)


class EvidenceExplorerError(RuntimeError):
    """P363/P364 source evidence is missing or malformed."""


@dataclass(frozen=True)
class ExplorerOutput:
    adapter_detail_cards: tuple[dict[str, object], ...]
    subset_detail_cards: tuple[dict[str, object], ...]
    pairwise_rows: tuple[dict[str, str], ...]
    compact_shortlist_rows: tuple[dict[str, str], ...]
    query_snapshots: dict[str, object]
    html_text: str
    manifest_rows: tuple[dict[str, str], ...]
    source_inventory: tuple[dict[str, str], ...]


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


def read_json(path: Path) -> dict[str, object]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise EvidenceExplorerError(f"expected JSON object at {path}")
    return payload


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    paths = tuple(root / relpath for _role, relpath in P365_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise EvidenceExplorerError(f"required P363/P364 evidence artifacts missing: {missing}")
    return paths


def _line_count(path: Path) -> int:
    with open(path, encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _source_inventory(repo_root: Path) -> tuple[dict[str, str], ...]:
    rows = []
    for role, relpath in P365_SOURCE_ARTIFACTS:
        path = repo_root / relpath
        row_count = ""
        object_count = ""
        if path.suffix == ".csv":
            row_count = str(len(read_csv_rows(path)))
        elif path.suffix == ".json":
            object_count = "1"
        rows.append(
            {
                "artifact_role": role,
                "path": relpath,
                "file_type": path.suffix.lstrip("."),
                "object_count": object_count,
                "row_count": row_count,
                "line_count": str(_line_count(path)),
                "sha256": sha256_file(path),
            }
        )
    return tuple(rows)


def _scope() -> dict[str, object]:
    return {
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
    }


def _window_summary(row: Mapping[str, str]) -> dict[str, dict[str, str]]:
    windows = {}
    for window in ("30", "150", "750", "1500"):
        windows[window] = {
            "hit_rate": row.get(f"p360_hit_rate_w{window}", ""),
            "edge": row.get(f"p360_edge_w{window}", ""),
        }
    return windows


def _adapter_detail_card(row: Mapping[str, str]) -> dict[str, object]:
    return {
        "adapter_function": row["adapter_function"],
        "strategy_id": row["strategy_id"],
        "bet_count": row["bet_count"],
        "scope": _scope(),
        "p360_performance_summary": {
            "windows_present": row["p360_windows_present"],
            "windows": _window_summary(row),
        },
        "p361_contribution_redundancy": {
            "total_hit_count": row["p361_total_hit_count"],
            "unique_hit_count": row["p361_unique_hit_count"],
            "candidate_marginal_share_full_context": row[
                "p361_candidate_marginal_share_full_context"
            ],
            "redundancy_note": row["p361_redundancy_note"],
        },
        "p362_stability": {
            "singleton_average_rank_by_coverage_rate": row[
                "p362_singleton_average_rank_by_coverage_rate"
            ],
            "singleton_top_3_window_count": row["p362_singleton_top_3_window_count"],
            "singleton_within_3_hits_window_count": row[
                "p362_singleton_within_3_hits_window_count"
            ],
            "stability_note": row["p362_stability_note"],
        },
        "caveats": CAVEATS,
        "source_caveat": row["caveat"],
    }


def build_adapter_detail_cards(
    adapter_rows: Iterable[Mapping[str, str]],
) -> tuple[dict[str, object], ...]:
    return tuple(_adapter_detail_card(row) for row in adapter_rows)


def _subset_detail_card(row: Mapping[str, str]) -> dict[str, object]:
    return {
        "adapter_subset": row["adapter_subset"],
        "subset_size": row["subset_size"],
        "scope": _scope(),
        "p361_coverage_utility": {
            "subset_is_full_cohort": row["subset_is_full_cohort"],
            "rank_within_subset_size": row["p361_rank_within_subset_size"],
            "best_subset_for_size": row["p361_best_subset_for_size"],
            "period_count": row["p361_period_count"],
            "any_hit_count": row["p361_any_hit_count"],
            "coverage_rate": row["p361_coverage_rate"],
            "duplicate_hit_events": row["p361_duplicate_hit_events"],
            "mean_pairwise_jaccard": row["p361_mean_pairwise_jaccard"],
        },
        "p362_stability": {
            "windows_evaluated": row["p362_windows_evaluated"],
            "average_rank_by_coverage_rate": row["p362_average_rank_by_coverage_rate"],
            "rank_variance_by_coverage_rate": row["p362_rank_variance_by_coverage_rate"],
            "top_1_window_count": row["p362_top_1_window_count"],
            "top_3_window_count": row["p362_top_3_window_count"],
            "within_3_hits_window_count": row["p362_within_3_hits_window_count"],
            "stability_note": row["p362_stability_note"],
        },
        "compact_candidate_flags": {
            "row_types": [value for value in row["compact_candidate_row_types"].split(";") if value],
            "windows": [value for value in row["compact_candidate_windows"].split(";") if value],
        },
        "caveats": CAVEATS,
        "source_caveat": row["caveat"],
    }


def build_subset_detail_cards(
    subset_rows: Iterable[Mapping[str, str]],
) -> tuple[dict[str, object], ...]:
    return tuple(_subset_detail_card(row) for row in subset_rows)


def build_pairwise_rows(subset_rows: Iterable[Mapping[str, str]]) -> tuple[dict[str, str], ...]:
    rows = []
    for subset_row in subset_rows:
        if subset_row["subset_size"] != "2":
            continue
        adapters = subset_row["adapter_subset"].split(";")
        if len(adapters) != 2:
            raise EvidenceExplorerError(f"malformed pairwise subset: {subset_row['adapter_subset']}")
        adapter_a, adapter_b = sorted(adapters)
        rows.append(
            {
                "adapter_a": adapter_a,
                "adapter_b": adapter_b,
                "adapter_pair": f"{adapter_a} | {adapter_b}",
                "p363_pair_subset": subset_row["adapter_subset"],
                "subset_size": subset_row["subset_size"],
                "p361_period_count": subset_row["p361_period_count"],
                "p361_pair_any_hit_count": subset_row["p361_any_hit_count"],
                "p361_pair_coverage_rate": subset_row["p361_coverage_rate"],
                "p361_pair_duplicate_hit_events": subset_row["p361_duplicate_hit_events"],
                "p361_pair_mean_pairwise_jaccard": subset_row["p361_mean_pairwise_jaccard"],
                "p362_windows_evaluated": subset_row["p362_windows_evaluated"],
                "p362_average_rank_by_coverage_rate": subset_row[
                    "p362_average_rank_by_coverage_rate"
                ],
                "p362_top_3_window_count": subset_row["p362_top_3_window_count"],
                "p362_within_3_hits_window_count": subset_row[
                    "p362_within_3_hits_window_count"
                ],
                "redundancy_scope": (
                    "Pairwise overlap fields are inherited from P363/P364 subset-size-2 evidence."
                ),
                "caveat": "Historical descriptive comparison only; no new scoring or recommendation.",
            }
        )
    ordered = sorted(rows, key=lambda row: (row["adapter_a"], row["adapter_b"]))
    return tuple({"display_rank": str(index), **row} for index, row in enumerate(ordered, start=1))


def build_compact_shortlist(
    subset_rows: Iterable[Mapping[str, str]], limit: int = 10
) -> tuple[dict[str, str], ...]:
    candidates = [
        dict(row)
        for row in subset_rows
        if row.get("compact_candidate_row_types") or row.get("subset_is_full_cohort") == "true"
    ]
    ordered = sorted(
        candidates,
        key=lambda row: (
            int(row["subset_size"]),
            -int(row["p361_any_hit_count"]),
            float(row["p362_average_rank_by_coverage_rate"]),
            row["adapter_subset"],
        ),
    )[:limit]
    rows = []
    for index, row in enumerate(ordered, start=1):
        compact_flags = row["compact_candidate_row_types"] or "full_cohort_reference"
        compact_windows = row["compact_candidate_windows"] or "full_cohort_reference"
        rows.append(
            {
                "display_rank": str(index),
                "adapter_subset": row["adapter_subset"],
                "subset_size": row["subset_size"],
                "p361_any_hit_count": row["p361_any_hit_count"],
                "p361_coverage_rate": row["p361_coverage_rate"],
                "p362_average_rank_by_coverage_rate": row[
                    "p362_average_rank_by_coverage_rate"
                ],
                "p362_top_3_window_count": row["p362_top_3_window_count"],
                "compact_candidate_row_types": compact_flags,
                "compact_candidate_windows": compact_windows,
                "why_compact_historically": (
                    "Flagged by P363/P364 compact evidence as small subset coverage "
                    "or full-cohort reference across historical windows."
                ),
                "what_it_does_not_prove": (
                    "Does not prove future performance, expected profit, or betting suitability."
                ),
                "caveat": "No recommendation language; descriptive-only historical shortlist.",
            }
        )
    return tuple(rows)


def _card_by_key(cards: Iterable[Mapping[str, object]], key: str, value: str) -> dict[str, object] | None:
    for card in cards:
        if card.get(key) == value:
            return dict(card)
    return None


def _pairwise_by_adapters(
    rows: Iterable[Mapping[str, str]], adapter_a: str, adapter_b: str
) -> dict[str, str] | None:
    expected = tuple(sorted((adapter_a, adapter_b)))
    for row in rows:
        if (row["adapter_a"], row["adapter_b"]) == expected:
            return dict(row)
    return None


def build_query_snapshots(
    source_inventory: tuple[dict[str, str], ...],
    adapter_cards: tuple[dict[str, object], ...],
    subset_cards: tuple[dict[str, object], ...],
    pairwise_rows: tuple[dict[str, str], ...],
    compact_shortlist_rows: tuple[dict[str, str], ...],
) -> dict[str, object]:
    adapters = tuple(str(card["adapter_function"]) for card in adapter_cards)
    subsets_by_size: dict[str, list[str]] = {}
    for card in subset_cards:
        subsets_by_size.setdefault(str(card["subset_size"]), []).append(str(card["adapter_subset"]))
    first_pair = pairwise_rows[0] if pairwise_rows else {}
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "scope": _scope(),
        "source_artifacts": tuple(dict(row) for row in source_inventory),
        "source_sha256": {row["path"]: row["sha256"] for row in source_inventory},
        "query_examples": {
            "list_adapters": adapters,
            "show_adapter": adapter_cards[0] if adapter_cards else {},
            "list_subsets_by_size": {
                size: tuple(values) for size, values in sorted(subsets_by_size.items())
            },
            "show_subset": subset_cards[0] if subset_cards else {},
            "compare_two_adapters": first_pair,
            "compact_shortlist": compact_shortlist_rows,
        },
        "counts": {
            "adapter_detail_cards": len(adapter_cards),
            "subset_detail_cards": len(subset_cards),
            "pairwise_comparison_rows": len(pairwise_rows),
            "compact_shortlist_rows": len(compact_shortlist_rows),
            "source_artifacts": len(source_inventory),
        },
    }


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _table_html(columns: Sequence[str], rows: Iterable[Mapping[str, str]], limit: int | None = None) -> str:
    selected_rows = tuple(rows)[:limit]
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in selected_rows:
        body.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
            + "</tr>"
        )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _card_summary_html(cards: Iterable[Mapping[str, object]], key: str, limit: int | None = None) -> str:
    rows = []
    for card in tuple(cards)[:limit]:
        caveats = card.get("caveats", ())
        if not isinstance(caveats, (list, tuple)):
            caveats = ()
        rows.append(
            "<article>"
            f"<h3>{html.escape(str(card.get(key, '')))}</h3>"
            f"<pre>{html.escape(_json_text(card))}</pre>"
            f"<p>{html.escape('; '.join(str(value) for value in caveats[:3]))}</p>"
            "</article>"
        )
    return "".join(rows)


def render_html_explorer(
    adapter_cards: tuple[dict[str, object], ...],
    subset_cards: tuple[dict[str, object], ...],
    pairwise_rows: tuple[dict[str, str], ...],
    compact_shortlist_rows: tuple[dict[str, str], ...],
    query_snapshots: Mapping[str, object],
    source_inventory: tuple[dict[str, str], ...],
) -> str:
    disclaimer = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    source_rows = tuple(
        {
            "artifact_role": row["artifact_role"],
            "path": row["path"],
            "file_type": row["file_type"],
            "row_count": row["row_count"],
            "object_count": row["object_count"],
            "sha256": row["sha256"],
        }
        for row in source_inventory
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>P365 Big Lotto no-DB Evidence Explorer</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #20262d;
      --muted: #59636f;
      --line: #cad3dc;
      --panel: #f6f8fa;
      --banner: #fff4cf;
      --accent: #006a6a;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.45;
    }}
    header, main {{
      max-width: 1220px;
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
    h3 {{
      margin: 0 0 8px;
      font-size: 15px;
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
      border: 1px solid #d8bd67;
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
      color: var(--accent);
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
    article {{
      border: 1px solid var(--line);
      border-radius: 6px;
      margin: 10px 0;
      padding: 12px;
      background: #ffffff;
    }}
    pre {{
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>P365 Big Lotto no-DB Evidence Explorer</h1>
    <p class="meta">Generated from committed P363/P364 evidence artifacts only. Generated at: {GENERATED_AT}</p>
    <div class="banner">
      <strong>Scope / disclaimer banner</strong>
      <ul>{disclaimer}</ul>
    </div>
    <div class="stats">
      <div class="stat"><strong>{len(adapter_cards)}</strong>Adapter detail cards</div>
      <div class="stat"><strong>{len(subset_cards)}</strong>Subset detail cards</div>
      <div class="stat"><strong>{len(pairwise_rows)}</strong>Pairwise comparison rows</div>
      <div class="stat"><strong>{len(compact_shortlist_rows)}</strong>Compact shortlist rows</div>
    </div>
  </header>
  <main>
    <h2>Adapter Detail Section</h2>
    {_card_summary_html(adapter_cards, "adapter_function")}

    <h2>Subset Detail Section</h2>
    {_card_summary_html(subset_cards, "adapter_subset", limit=12)}

    <h2>Compact Shortlist Section</h2>
    <div class="table-wrap">{_table_html(SHORTLIST_COLUMNS, compact_shortlist_rows)}</div>

    <h2>Pairwise Comparison Section</h2>
    <div class="table-wrap">{_table_html(PAIRWISE_COLUMNS, pairwise_rows)}</div>

    <h2>Query Snapshot Section</h2>
    <pre>{html.escape(_json_text(query_snapshots))}</pre>

    <h2>Source Artifact Inventory</h2>
    <div class="table-wrap">{_table_html(("artifact_role", "path", "file_type", "row_count", "object_count", "sha256"), source_rows)}</div>
  </main>
</body>
</html>
"""


def _artifact_contents(output: ExplorerOutput) -> dict[str, str]:
    return {
        "adapter_detail_cards": _json_text(output.adapter_detail_cards),
        "subset_detail_cards": _json_text(output.subset_detail_cards),
        "pairwise_comparison": _csv_text(PAIRWISE_COLUMNS, output.pairwise_rows),
        "compact_shortlist": _csv_text(SHORTLIST_COLUMNS, output.compact_shortlist_rows),
        "query_snapshots": _json_text(output.query_snapshots),
        "html": output.html_text,
        "manifest": _csv_text(MANIFEST_COLUMNS, output.manifest_rows),
    }


def _build_manifest_rows(
    source_inventory: tuple[dict[str, str], ...],
    output_counts: Mapping[str, tuple[str, str]],
    output_texts: Mapping[str, str],
) -> tuple[dict[str, str], ...]:
    rows = []
    for row in source_inventory:
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": row["artifact_role"],
                "path": row["path"],
                "object_count": row["object_count"],
                "row_count": row["row_count"],
                "sha256": row["sha256"],
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "details": "P363/P364 committed evidence source artifact.",
            }
        )
    for role, basename in ARTIFACT_BASENAMES.items():
        if role == "manifest":
            object_count, row_count = "", str(len(source_inventory) + len(ARTIFACT_BASENAMES) + 2)
            sha256 = ""
            details = "P365 manifest records source/output inventory; self SHA omitted."
        else:
            object_count, row_count = output_counts[role]
            sha256 = sha256_bytes(output_texts[role].encode("utf-8"))
            details = "P365 derived output artifact from P363/P364 evidence."
        rows.append(
            {
                "artifact_group": "output",
                "artifact_role": role,
                "path": f"artifacts/{basename}",
                "object_count": object_count,
                "row_count": row_count,
                "sha256": sha256,
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "details": details,
            }
        )
    rows.append(
        {
            "artifact_group": "statement",
            "artifact_role": "no_db_open_write",
            "path": "",
            "object_count": "",
            "row_count": "",
            "sha256": "",
            "no_db_open_write": "YES",
            "no_adapter_calls": "YES",
            "details": (
                "P365 reads only merged P363/P364 evidence artifacts; no DB open/write, "
                "no adapter calls, no scoring cohort, no production registry import, no deploy."
            ),
        }
    )
    rows.append(
        {
            "artifact_group": "statement",
            "artifact_role": "scope_disclaimer",
            "path": "",
            "object_count": "",
            "row_count": "",
            "sha256": "",
            "no_db_open_write": "YES",
            "no_adapter_calls": "YES",
            "details": (
                "Historical descriptive evidence only; no betting advice; no future prediction "
                "guarantee; no blended leaderboard; shape-only and blocked targets remain excluded."
            ),
        }
    )
    return tuple(rows)


def run_explorer(repo_root: Path | None = None) -> ExplorerOutput:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    verify_required_artifacts(root)
    source_inventory = _source_inventory(root)
    p364_index = read_json(root / "artifacts/P364_biglotto_evidence_dashboard_index.json")
    if p364_index.get("task") != "P364_biglotto_evidence_dashboard":
        raise EvidenceExplorerError("P364 index task marker is missing or unexpected")
    adapter_rows = read_csv_rows(root / "artifacts/P364_biglotto_evidence_dashboard_adapter_table.csv")
    subset_rows = read_csv_rows(root / "artifacts/P364_biglotto_evidence_dashboard_subset_table.csv")
    adapter_cards = build_adapter_detail_cards(adapter_rows)
    subset_cards = build_subset_detail_cards(subset_rows)
    pairwise_rows = build_pairwise_rows(subset_rows)
    compact_shortlist_rows = build_compact_shortlist(subset_rows)
    query_snapshots = build_query_snapshots(
        source_inventory, adapter_cards, subset_cards, pairwise_rows, compact_shortlist_rows
    )
    html_text = render_html_explorer(
        adapter_cards,
        subset_cards,
        pairwise_rows,
        compact_shortlist_rows,
        query_snapshots,
        source_inventory,
    )
    output_texts = {
        "adapter_detail_cards": _json_text(adapter_cards),
        "subset_detail_cards": _json_text(subset_cards),
        "pairwise_comparison": _csv_text(PAIRWISE_COLUMNS, pairwise_rows),
        "compact_shortlist": _csv_text(SHORTLIST_COLUMNS, compact_shortlist_rows),
        "query_snapshots": _json_text(query_snapshots),
        "html": html_text,
    }
    output_counts = {
        "adapter_detail_cards": (str(len(adapter_cards)), ""),
        "subset_detail_cards": (str(len(subset_cards)), ""),
        "pairwise_comparison": ("", str(len(pairwise_rows))),
        "compact_shortlist": ("", str(len(compact_shortlist_rows))),
        "query_snapshots": ("1", ""),
        "html": ("", ""),
    }
    manifest_rows = _build_manifest_rows(source_inventory, output_counts, output_texts)
    return ExplorerOutput(
        adapter_detail_cards=adapter_cards,
        subset_detail_cards=subset_cards,
        pairwise_rows=pairwise_rows,
        compact_shortlist_rows=compact_shortlist_rows,
        query_snapshots=query_snapshots,
        html_text=html_text,
        manifest_rows=manifest_rows,
        source_inventory=source_inventory,
    )


def _assert_deterministic(first: ExplorerOutput, second: ExplorerOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P365 explorer artifacts are not reproducible")


def write_artifacts(output: ExplorerOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        with open(path, "w", encoding="utf-8", newline="" if path.suffix == ".csv" else None) as handle:
            handle.write(contents[key])
    return paths


def _print_json(payload: object) -> None:
    print(_json_text(payload), end="")


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def _filter_subsets(
    cards: Iterable[Mapping[str, object]], subset_size: int | None = None
) -> tuple[dict[str, object], ...]:
    return tuple(
        dict(card)
        for card in cards
        if subset_size is None or str(card.get("subset_size")) == str(subset_size)
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("generate", help="generate all P365 explorer artifacts")
    subparsers.add_parser("list-adapters", help="list adapter functions")
    show_adapter = subparsers.add_parser("show-adapter", help="show one adapter detail card as JSON")
    show_adapter.add_argument("adapter_function")
    list_subsets = subparsers.add_parser("list-subsets", help="list subset detail cards as JSON")
    list_subsets.add_argument("--subset-size", type=int, choices=range(1, 6), default=None)
    show_subset = subparsers.add_parser("show-subset", help="show one subset detail card as JSON")
    show_subset.add_argument("adapter_subset")
    compare = subparsers.add_parser("compare", help="compare two adapters if pairwise evidence exists")
    compare.add_argument("adapter_a")
    compare.add_argument("adapter_b")
    subparsers.add_parser("shortlist", help="show compact shortlist as CSV")
    subparsers.add_parser("snapshots", help="emit query snapshots JSON")

    args = parser.parse_args(argv)
    first = run_explorer()
    second = run_explorer()
    _assert_deterministic(first, second)

    command = args.command or "generate"
    if command == "generate":
        paths = write_artifacts(first, args.artifacts_dir)
        print("P365 no-DB evidence explorer: determinism double-run PASS")
        print(f"adapter detail cards: {len(first.adapter_detail_cards)}")
        print(f"subset detail cards: {len(first.subset_detail_cards)}")
        print(f"pairwise comparison rows: {len(first.pairwise_rows)}")
        print(f"compact shortlist rows: {len(first.compact_shortlist_rows)}")
        print("No DB was opened or written; no adapters were called.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    elif command == "list-adapters":
        for card in first.adapter_detail_cards:
            print(card["adapter_function"])
    elif command == "show-adapter":
        card = _card_by_key(first.adapter_detail_cards, "adapter_function", args.adapter_function)
        if card is None:
            raise SystemExit(f"adapter not found: {args.adapter_function}")
        _print_json(card)
    elif command == "list-subsets":
        _print_json(_filter_subsets(first.subset_detail_cards, args.subset_size))
    elif command == "show-subset":
        card = _card_by_key(first.subset_detail_cards, "adapter_subset", args.adapter_subset)
        if card is None:
            raise SystemExit(f"subset not found: {args.adapter_subset}")
        _print_json(card)
    elif command == "compare":
        row = _pairwise_by_adapters(first.pairwise_rows, args.adapter_a, args.adapter_b)
        if row is None:
            raise SystemExit(f"pairwise evidence not found: {args.adapter_a} | {args.adapter_b}")
        _print_csv(PAIRWISE_COLUMNS, (row,))
    elif command == "shortlist":
        _print_csv(SHORTLIST_COLUMNS, first.compact_shortlist_rows)
    elif command == "snapshots":
        _print_json(first.query_snapshots)
    else:
        raise SystemExit(f"unknown command: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
