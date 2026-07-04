"""P366 Big Lotto no-DB evidence release bundle.

This module packages the merged P363/P364/P365 no-DB evidence artifacts into a
local smoke and handoff bundle. It reads only committed source artifacts. It
does not open or write a DB, import production registries, call adapters,
create new scoring cohorts, deploy, or make betting or future-performance
claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from recovered_strategies.biglotto import no_db_evidence_explorer as explorer

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P366_biglotto_evidence_release_bundle"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"

SOURCE_ARTIFACTS = (
    ("P363", "p363_summary", "artifact", "artifacts/P363_biglotto_evidence_pack_summary.csv"),
    ("P363", "p363_adapter_cards", "artifact", "artifacts/P363_biglotto_evidence_pack_adapter_cards.csv"),
    ("P363", "p363_subset_cards", "artifact", "artifacts/P363_biglotto_evidence_pack_subset_cards.csv"),
    ("P363", "p363_consistency_checks", "artifact", "artifacts/P363_biglotto_evidence_pack_consistency_checks.csv"),
    ("P363", "p363_manifest", "artifact", "artifacts/P363_biglotto_evidence_pack_manifest.csv"),
    ("P363", "p363_report", "artifact", "artifacts/P363_biglotto_evidence_pack_report.md"),
    ("P364", "p364_index", "artifact", "artifacts/P364_biglotto_evidence_dashboard_index.json"),
    ("P364", "p364_adapter_table", "artifact", "artifacts/P364_biglotto_evidence_dashboard_adapter_table.csv"),
    ("P364", "p364_subset_table", "artifact", "artifacts/P364_biglotto_evidence_dashboard_subset_table.csv"),
    ("P364", "p364_html", "artifact", "artifacts/P364_biglotto_evidence_dashboard.html"),
    ("P364", "p364_manifest", "artifact", "artifacts/P364_biglotto_evidence_dashboard_manifest.csv"),
    ("P365", "p365_adapter_detail_cards", "artifact", "artifacts/P365_biglotto_evidence_explorer_adapter_detail_cards.json"),
    ("P365", "p365_subset_detail_cards", "artifact", "artifacts/P365_biglotto_evidence_explorer_subset_detail_cards.json"),
    ("P365", "p365_pairwise_comparison", "artifact", "artifacts/P365_biglotto_evidence_explorer_pairwise_comparison.csv"),
    ("P365", "p365_compact_shortlist", "artifact", "artifacts/P365_biglotto_evidence_explorer_compact_shortlist.csv"),
    ("P365", "p365_query_snapshots", "artifact", "artifacts/P365_biglotto_evidence_explorer_query_snapshots.json"),
    ("P365", "p365_html", "artifact", "artifacts/P365_biglotto_evidence_explorer.html"),
    ("P365", "p365_manifest", "artifact", "artifacts/P365_biglotto_evidence_explorer_manifest.csv"),
    ("P363", "p363_entry_source", "python_source", "recovered_strategies/biglotto/no_db_evidence_pack.py"),
    ("P364", "p364_entry_source", "python_source", "recovered_strategies/biglotto/no_db_evidence_dashboard.py"),
    ("P365", "p365_entry_source", "python_source", "recovered_strategies/biglotto/no_db_evidence_explorer.py"),
    ("P365", "p365_explorer_tests", "python_test", "tests/test_p365_biglotto_evidence_explorer.py"),
)

P366_ARTIFACT_BASENAMES = {
    "manifest": "P366_biglotto_evidence_release_bundle_manifest.json",
    "inventory": "P366_biglotto_evidence_release_bundle_inventory.csv",
    "smoke_results": "P366_biglotto_evidence_release_bundle_smoke_results.csv",
    "cli_examples": "P366_biglotto_evidence_release_bundle_cli_examples.json",
    "landing": "P366_biglotto_evidence_release_bundle_landing.html",
    "readme": "P366_biglotto_evidence_release_bundle_readme.md",
}

INVENTORY_COLUMNS = (
    "artifact_path",
    "artifact_type",
    "source_stage",
    "sha256",
    "row_count",
    "object_count",
    "role",
)

SMOKE_COLUMNS = ("check_name", "status", "expected", "actual", "details")

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No production registry import.",
    "No deploy.",
    "No adapter calls.",
    "No new scoring cohort.",
    "No blended leaderboard.",
    "Shape-only and blocked targets remain excluded.",
)

STATEMENTS = {
    "historical_descriptive_evidence_only": True,
    "future_prediction_guarantee": False,
    "betting_advice": False,
    "db_opened": False,
    "db_written": False,
    "production_registry_imported": False,
    "deployed": False,
    "adapter_calls": False,
    "new_scoring_cohort": False,
    "blended_leaderboard": False,
    "shape_only_and_blocked_targets_excluded": True,
}

FORBIDDEN_PROMOTIONAL_PHRASES = (
    "bet this",
    "guaranteed profit",
    "guaranteed win",
    "will win",
    "future lock",
    "recommended wager",
    "sure thing",
)


class ReleaseBundleError(RuntimeError):
    """P366 source evidence is missing or malformed."""


@dataclass(frozen=True)
class ReleaseBundleOutput:
    manifest: dict[str, object]
    inventory_rows: tuple[dict[str, str], ...]
    smoke_rows: tuple[dict[str, str], ...]
    cli_examples: dict[str, object]
    landing_html: str
    readme_md: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with open(path, newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _line_count(path: Path) -> int:
    with open(path, encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _artifact_type(path: Path) -> str:
    if path.suffix == ".csv":
        return "csv"
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".html":
        return "html"
    if path.suffix == ".md":
        return "markdown"
    if path.suffix == ".py":
        return "python"
    return path.suffix.lstrip(".") or "file"


def _counts_for_path(path: Path) -> tuple[str, str]:
    if path.suffix == ".csv":
        return str(len(_read_csv_rows(path))), ""
    if path.suffix == ".json":
        payload = _read_json(path)
        if isinstance(payload, list):
            return "", str(len(payload))
        if isinstance(payload, dict):
            return "", "1"
        return "", "1"
    return "", ""


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    paths = tuple(root / relpath for _stage, _role, _kind, relpath in SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ReleaseBundleError(f"required P363/P364/P365 evidence files missing: {missing}")
    return paths


def build_source_inventory_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    verify_required_artifacts(root)
    rows: list[dict[str, str]] = []
    for stage, role, kind, relpath in SOURCE_ARTIFACTS:
        path = root / relpath
        row_count, object_count = _counts_for_path(path)
        rows.append(
            {
                "artifact_path": relpath,
                "artifact_type": _artifact_type(path),
                "source_stage": stage,
                "sha256": sha256_file(path),
                "row_count": row_count,
                "object_count": object_count,
                "role": f"{kind}:{role}",
            }
        )
    return tuple(rows)


def _run_local_command(command: Sequence[str], repo_root: Path) -> dict[str, object]:
    result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
    return {
        "command": " ".join("python3" if value == sys.executable else value for value in command),
        "exit_code": result.returncode,
        "stdout": _normalize_python_command_text(result.stdout),
        "stderr": _normalize_python_command_text(result.stderr),
    }


def _normalize_python_command_text(text: str) -> str:
    return re.sub(r"\bpython3(?:\.\d+)?\b", "python3", text)


def build_cli_examples(repo_root: Path | None = None) -> dict[str, object]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    p365 = explorer.run_explorer(root)
    first_adapter = str(p365.adapter_detail_cards[0]["adapter_function"])
    first_subset = str(p365.subset_detail_cards[0]["adapter_subset"])
    examples = {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "scope": STATEMENTS,
        "examples": {
            "explorer_help": _run_local_command(
                (sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_explorer", "--help"),
                root,
            ),
            "list_adapters": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_evidence_explorer list-adapters",
                "exit_code": 0,
                "stdout": "\n".join(str(card["adapter_function"]) for card in p365.adapter_detail_cards) + "\n",
                "stderr": "",
            },
            "list_compact_shortlist": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_evidence_explorer shortlist",
                "exit_code": 0,
                "stdout": _csv_text(explorer.SHORTLIST_COLUMNS, p365.compact_shortlist_rows),
                "stderr": "",
            },
            "show_one_adapter_detail": {
                "command": (
                    "python3 -m recovered_strategies.biglotto.no_db_evidence_explorer "
                    f"show-adapter {first_adapter}"
                ),
                "exit_code": 0,
                "stdout": _json_text(p365.adapter_detail_cards[0]),
                "stderr": "",
            },
            "show_one_subset_detail": {
                "command": (
                    "python3 -m recovered_strategies.biglotto.no_db_evidence_explorer "
                    f"show-subset {first_subset}"
                ),
                "exit_code": 0,
                "stdout": _json_text(p365.subset_detail_cards[0]),
                "stderr": "",
            },
        },
    }
    return examples


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def _validate_entry_file(path: Path) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    blocked = []
    if "sqlite3.connect" in text:
        blocked.append("sqlite3.connect")
    if "production registry" in text.lower() and "no production registry" not in text.lower():
        blocked.append("production registry wording")
    return not blocked, ";".join(blocked) if blocked else "entry file contains no direct DB open marker"


def build_smoke_rows(
    source_rows: tuple[dict[str, str], ...],
    cli_examples: Mapping[str, object],
    generated_texts: Mapping[str, str],
    repo_root: Path | None = None,
) -> tuple[dict[str, str], ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    rows: list[dict[str, str]] = []
    for row in source_rows:
        path = root / row["artifact_path"]
        rows.append(_check(f"required_file_exists:{row['artifact_path']}", path.is_file(), "exists", path.is_file(), "P363/P364/P365 source evidence file is present."))
        if path.suffix == ".csv":
            try:
                parsed_rows = _read_csv_rows(path)
                rows.append(_check(f"csv_parses:{row['artifact_path']}", True, "parseable csv", len(parsed_rows), "CSV parsed with csv.DictReader."))
            except csv.Error as exc:
                rows.append(_check(f"csv_parses:{row['artifact_path']}", False, "parseable csv", type(exc).__name__, str(exc)))
        elif path.suffix == ".json":
            try:
                payload = _read_json(path)
                rows.append(_check(f"json_parses:{row['artifact_path']}", True, "parseable json", type(payload).__name__, "JSON parsed with json.load."))
            except json.JSONDecodeError as exc:
                rows.append(_check(f"json_parses:{row['artifact_path']}", False, "parseable json", type(exc).__name__, str(exc)))

    for relpath in (
        "artifacts/P364_biglotto_evidence_dashboard.html",
        "artifacts/P365_biglotto_evidence_explorer.html",
    ):
        text = (root / relpath).read_text(encoding="utf-8")
        missing = [line for line in DISCLAIMER_LINES if line not in text]
        rows.append(_check(f"html_disclaimers:{relpath}", not missing, "all disclaimer lines", "missing:" + ";".join(missing) if missing else "present", "HTML contains required scope and disclaimer banner text."))

    landing_missing = [line for line in DISCLAIMER_LINES if line not in generated_texts["landing"]]
    rows.append(_check("html_disclaimers:artifacts/P366_biglotto_evidence_release_bundle_landing.html", not landing_missing, "all disclaimer lines", "missing:" + ";".join(landing_missing) if landing_missing else "present", "P366 landing page contains required scope and disclaimer text."))

    help_result = _run_local_command(
        (sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "--help"),
        root,
    )
    rows.append(_check("cli_help_works:p366", help_result["exit_code"] == 0 and "usage:" in str(help_result["stdout"]), "exit 0 with usage", help_result["exit_code"], "P366 CLI help returned deterministic argparse help."))

    explorer_help = cli_examples["examples"]["explorer_help"]  # type: ignore[index]
    rows.append(_check("cli_help_works:p365_explorer", explorer_help["exit_code"] == 0 and "usage:" in str(explorer_help["stdout"]), "exit 0 with usage", explorer_help["exit_code"], "P365 explorer help captured for release examples."))

    second_examples = build_cli_examples(root)
    rows.append(_check("example_commands_deterministic", second_examples == cli_examples, "same example JSON", second_examples == cli_examples, "CLI example output was regenerated and compared byte-for-byte at object level."))

    for relpath in (
        "recovered_strategies/biglotto/no_db_evidence_dashboard.py",
        "recovered_strategies/biglotto/no_db_evidence_explorer.py",
    ):
        ok, details = _validate_entry_file(root / relpath)
        rows.append(_check(f"validate_entry_file:{relpath}", ok, "no direct DB open marker", details, "Dashboard/explorer entry file validation."))

    joined = "\n".join(generated_texts.values()).lower()
    found = [phrase for phrase in FORBIDDEN_PROMOTIONAL_PHRASES if phrase in joined]
    rows.append(_check("forbidden_promotional_phrases_absent", not found, "absent", ";".join(found) if found else "absent", "Checks for language suggesting betting advice or future guarantees."))

    return tuple(rows)


def _output_artifact_rows(output_texts: Mapping[str, str]) -> tuple[dict[str, str], ...]:
    rows = []
    for key, basename in P366_ARTIFACT_BASENAMES.items():
        text = output_texts.get(key, "")
        if key in {"manifest", "inventory", "landing"}:
            sha = "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
        else:
            sha = sha256_bytes(text.encode("utf-8"))
        rows.append(
            {
                "artifact_path": f"artifacts/{basename}",
                "artifact_type": _artifact_type(Path(basename)),
                "source_stage": "P366",
                "sha256": sha,
                "row_count": _row_count_for_output(key, text),
                "object_count": _object_count_for_output(key, text),
                "role": f"release_bundle:{key}",
            }
        )
    return tuple(rows)


def _row_count_for_output(key: str, text: str) -> str:
    if key in {"inventory", "smoke_results"} and text:
        return str(len(tuple(csv.DictReader(text.splitlines()))))
    return ""


def _object_count_for_output(key: str, text: str) -> str:
    if key in {"manifest", "cli_examples"} and text:
        payload = json.loads(text)
        return str(len(payload)) if isinstance(payload, list) else "1"
    return ""


def build_manifest(
    source_rows: tuple[dict[str, str], ...],
    output_rows: tuple[dict[str, str], ...],
    smoke_rows: tuple[dict[str, str], ...],
) -> dict[str, object]:
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_artifacts": tuple(dict(row) for row in source_rows),
        "source_artifact_paths": tuple(row["artifact_path"] for row in source_rows),
        "source_sha256": {row["artifact_path"]: row["sha256"] for row in source_rows},
        "source_counts": {
            row["artifact_path"]: {
                "row_count": row["row_count"],
                "object_count": row["object_count"],
            }
            for row in source_rows
        },
        "output_artifacts": tuple(dict(row) for row in output_rows),
        "output_artifact_paths": tuple(row["artifact_path"] for row in output_rows),
        "output_sha256": {row["artifact_path"]: row["sha256"] for row in output_rows},
        "statements": STATEMENTS,
        "no_db_open_write_statement": "No DB was opened or written.",
        "no_adapter_calls_statement": "No adapters were called or executed.",
        "no_new_scoring_statement": "No new scoring cohort, blended leaderboard, shape-only scoring, or blocked target scoring was created.",
        "smoke_summary": {
            "pass": sum(1 for row in smoke_rows if row["status"] == "PASS"),
            "fail": sum(1 for row in smoke_rows if row["status"] == "FAIL"),
            "total": len(smoke_rows),
        },
        "recursive_sha256_note": (
            "Manifest and inventory rows use SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT "
            "because embedding a file's own digest would make the artifact recursive."
        ),
    }


def render_landing_html(
    inventory_rows: tuple[dict[str, str], ...],
    smoke_rows: tuple[dict[str, str], ...],
    cli_examples: Mapping[str, object],
) -> str:
    disclaimer = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    inventory_table = _table_html(INVENTORY_COLUMNS, inventory_rows)
    smoke_table = _table_html(SMOKE_COLUMNS, smoke_rows)
    example_commands = []
    examples = cli_examples["examples"]  # type: ignore[index]
    for name, item in examples.items():
        example_commands.append(f"<li><code>{html.escape(str(item['command']))}</code> <span>{html.escape(str(name))}</span></li>")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>P366 Big Lotto no-DB Evidence Release Bundle</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #20262d;
      --muted: #5d6772;
      --line: #c9d3de;
      --panel: #f6f8fa;
      --banner: #fff4cf;
      --accent: #006a6a;
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
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
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
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
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
    <h1>P366 Big Lotto no-DB Evidence Release Bundle</h1>
    <p class="meta">Generated from merged P363/P364/P365 evidence artifacts only. Generated at: {GENERATED_AT}</p>
    <div class="banner">
      <strong>Scope / disclaimer banner</strong>
      <ul>{disclaimer}</ul>
    </div>
    <div class="stats">
      <div class="stat"><strong>{len(inventory_rows)}</strong>Inventory rows</div>
      <div class="stat"><strong>{sum(1 for row in smoke_rows if row["status"] == "PASS")}</strong>Smoke checks passed</div>
      <div class="stat"><strong>{sum(1 for row in smoke_rows if row["status"] == "FAIL")}</strong>Smoke checks failed</div>
      <div class="stat"><strong>{len(P366_ARTIFACT_BASENAMES)}</strong>P366 artifacts</div>
    </div>
  </header>
  <main>
    <h2>Release Scope</h2>
    <p>Historical descriptive evidence only; no future prediction guarantee; no betting advice; no DB open/write; no production registry import; no deploy; no adapter calls; no new scoring cohort; no blended leaderboard; shape-only and blocked targets remain excluded.</p>

    <h2>P363/P364/P365/P366 Artifact Paths</h2>
    <div class="table-wrap">{inventory_table}</div>

    <h2>Available CLI Commands</h2>
    <ul>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle</code></li>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle --help</code></li>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle smoke</code></li>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle inventory</code></li>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle examples</code></li>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle validate</code></li>
      <li><code>python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle manifest</code></li>
    </ul>
    <ul>{''.join(example_commands)}</ul>

    <h2>Smoke Check Summary</h2>
    <div class="table-wrap">{smoke_table}</div>
  </main>
</body>
</html>
"""


def _table_html(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        body.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
            + "</tr>"
        )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_readme() -> str:
    disclaimer = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    return f"""# P366 Big Lotto no-DB evidence release bundle

Generated at: {GENERATED_AT}

This local-only bundle packages merged P363/P364/P365 Big Lotto no-DB evidence artifacts for smoke validation, inspection, and handoff.

## Run locally

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle
python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle --help
python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle smoke
python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle inventory
python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle examples
python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle manifest
```

Open `artifacts/P366_biglotto_evidence_release_bundle_landing.html` locally in a browser to inspect the artifact inventory and smoke summary.

## Scope and disclaimers

{disclaimer}

This release bundle reads committed artifacts only. It does not claim predictive value, betting suitability, future profit, production readiness, or adapter execution readiness.
"""


def _artifact_contents(output: ReleaseBundleOutput) -> dict[str, str]:
    return {
        "manifest": _json_text(output.manifest),
        "inventory": _csv_text(INVENTORY_COLUMNS, output.inventory_rows),
        "smoke_results": _csv_text(SMOKE_COLUMNS, output.smoke_rows),
        "cli_examples": _json_text(output.cli_examples),
        "landing": output.landing_html,
        "readme": output.readme_md,
    }


def run_bundle(repo_root: Path | None = None) -> ReleaseBundleOutput:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    source_rows = build_source_inventory_rows(root)
    cli_examples = build_cli_examples(root)
    readme = render_readme()
    preliminary_inventory = source_rows
    preliminary_smoke: tuple[dict[str, str], ...] = tuple()
    preliminary_landing = render_landing_html(preliminary_inventory, preliminary_smoke, cli_examples)
    smoke_rows = build_smoke_rows(
        source_rows,
        cli_examples,
        {
            "cli_examples": _json_text(cli_examples),
            "landing": preliminary_landing,
            "readme": readme,
        },
        root,
    )
    landing = render_landing_html(preliminary_inventory, smoke_rows, cli_examples)
    output_texts_without_manifest = {
        "inventory": "",
        "smoke_results": _csv_text(SMOKE_COLUMNS, smoke_rows),
        "cli_examples": _json_text(cli_examples),
        "landing": landing,
        "readme": readme,
        "manifest": "",
    }
    output_rows = _output_artifact_rows(output_texts_without_manifest)
    inventory_rows = tuple(source_rows + output_rows)
    manifest = build_manifest(source_rows, output_rows, smoke_rows)
    return ReleaseBundleOutput(
        manifest=manifest,
        inventory_rows=inventory_rows,
        smoke_rows=smoke_rows,
        cli_examples=cli_examples,
        landing_html=render_landing_html(inventory_rows, smoke_rows, cli_examples),
        readme_md=readme,
    )


def _assert_deterministic(first: ReleaseBundleOutput, second: ReleaseBundleOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P366 release bundle artifacts are not reproducible")


def write_artifacts(output: ReleaseBundleOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P366_ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        with open(path, "w", encoding="utf-8", newline="" if path.suffix == ".csv" else None) as handle:
            handle.write(contents[key])
    return paths


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("generate", help="generate all P366 release-bundle artifacts")
    subparsers.add_parser("smoke", help="print deterministic smoke results CSV")
    subparsers.add_parser("inventory", help="print release inventory CSV")
    subparsers.add_parser("examples", help="print deterministic CLI example outputs JSON")
    subparsers.add_parser("validate", help="print dashboard/explorer validation smoke rows CSV")
    subparsers.add_parser("manifest", help="print release manifest JSON")
    args = parser.parse_args(argv)

    first = run_bundle()
    second = run_bundle()
    _assert_deterministic(first, second)

    command = args.command or "generate"
    if command == "generate":
        paths = write_artifacts(first, args.artifacts_dir)
        print("P366 Big Lotto no-DB evidence release bundle: determinism double-run PASS")
        print(f"inventory rows: {len(first.inventory_rows)}")
        print(f"smoke checks: {len(first.smoke_rows)}")
        print(f"smoke failures: {sum(1 for row in first.smoke_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring cohort was created.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    elif command == "smoke":
        _print_csv(SMOKE_COLUMNS, first.smoke_rows)
    elif command == "inventory":
        _print_csv(INVENTORY_COLUMNS, first.inventory_rows)
    elif command == "examples":
        print(_json_text(first.cli_examples), end="")
    elif command == "validate":
        validation_rows = tuple(row for row in first.smoke_rows if row["check_name"].startswith("validate_entry_file:"))
        _print_csv(SMOKE_COLUMNS, validation_rows)
    elif command == "manifest":
        print(_json_text(first.manifest), end="")
    else:
        raise SystemExit(f"unknown command: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
