"""P367 Big Lotto no-DB evidence API facade.

This module exposes a stable local API and CLI over the merged P363/P364/P365/P366
Big Lotto no-DB evidence stack. It reads committed evidence artifacts only. It
does not open or write a DB, import production registries, call adapters, create
new scoring cohorts, deploy, or make betting or future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P367_biglotto_evidence_api"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"

EXPECTED_ADAPTER_COUNT = 5
EXPECTED_SUBSET_COUNT = 31
EXPECTED_PAIRWISE_COUNT = 10
EXPECTED_COMPACT_SHORTLIST_COUNT = 8

SOURCE_ARTIFACTS = (
    ("P363", "p363_summary", "csv", "artifacts/P363_biglotto_evidence_pack_summary.csv"),
    ("P363", "p363_adapter_cards", "csv", "artifacts/P363_biglotto_evidence_pack_adapter_cards.csv"),
    ("P363", "p363_subset_cards", "csv", "artifacts/P363_biglotto_evidence_pack_subset_cards.csv"),
    ("P363", "p363_consistency_checks", "csv", "artifacts/P363_biglotto_evidence_pack_consistency_checks.csv"),
    ("P363", "p363_manifest", "csv", "artifacts/P363_biglotto_evidence_pack_manifest.csv"),
    ("P363", "p363_report", "markdown", "artifacts/P363_biglotto_evidence_pack_report.md"),
    ("P364", "p364_index", "json", "artifacts/P364_biglotto_evidence_dashboard_index.json"),
    ("P364", "p364_adapter_table", "csv", "artifacts/P364_biglotto_evidence_dashboard_adapter_table.csv"),
    ("P364", "p364_subset_table", "csv", "artifacts/P364_biglotto_evidence_dashboard_subset_table.csv"),
    ("P364", "p364_html", "html", "artifacts/P364_biglotto_evidence_dashboard.html"),
    ("P364", "p364_manifest", "csv", "artifacts/P364_biglotto_evidence_dashboard_manifest.csv"),
    ("P365", "p365_adapter_detail_cards", "json", "artifacts/P365_biglotto_evidence_explorer_adapter_detail_cards.json"),
    ("P365", "p365_subset_detail_cards", "json", "artifacts/P365_biglotto_evidence_explorer_subset_detail_cards.json"),
    ("P365", "p365_pairwise_comparison", "csv", "artifacts/P365_biglotto_evidence_explorer_pairwise_comparison.csv"),
    ("P365", "p365_compact_shortlist", "csv", "artifacts/P365_biglotto_evidence_explorer_compact_shortlist.csv"),
    ("P365", "p365_query_snapshots", "json", "artifacts/P365_biglotto_evidence_explorer_query_snapshots.json"),
    ("P365", "p365_html", "html", "artifacts/P365_biglotto_evidence_explorer.html"),
    ("P365", "p365_manifest", "csv", "artifacts/P365_biglotto_evidence_explorer_manifest.csv"),
    ("P366", "p366_manifest", "json", "artifacts/P366_biglotto_evidence_release_bundle_manifest.json"),
    ("P366", "p366_inventory", "csv", "artifacts/P366_biglotto_evidence_release_bundle_inventory.csv"),
    ("P366", "p366_smoke_results", "csv", "artifacts/P366_biglotto_evidence_release_bundle_smoke_results.csv"),
    ("P366", "p366_cli_examples", "json", "artifacts/P366_biglotto_evidence_release_bundle_cli_examples.json"),
    ("P366", "p366_landing", "html", "artifacts/P366_biglotto_evidence_release_bundle_landing.html"),
    ("P366", "p366_readme", "markdown", "artifacts/P366_biglotto_evidence_release_bundle_readme.md"),
    ("P363", "p363_entry_source", "python", "recovered_strategies/biglotto/no_db_evidence_pack.py"),
    ("P364", "p364_entry_source", "python", "recovered_strategies/biglotto/no_db_evidence_dashboard.py"),
    ("P365", "p365_entry_source", "python", "recovered_strategies/biglotto/no_db_evidence_explorer.py"),
    ("P366", "p366_entry_source", "python", "recovered_strategies/biglotto/no_db_evidence_release_bundle.py"),
)

P367_ARTIFACT_BASENAMES = {
    "contract": "P367_biglotto_evidence_api_contract.json",
    "examples": "P367_biglotto_evidence_api_examples.json",
    "validation": "P367_biglotto_evidence_api_validation.csv",
    "manifest": "P367_biglotto_evidence_api_manifest.csv",
    "readme": "P367_biglotto_evidence_api_readme.md",
}

VALIDATION_COLUMNS = ("check_name", "status", "expected", "actual", "details")

MANIFEST_COLUMNS = (
    "artifact_group",
    "artifact_role",
    "path",
    "source_stage",
    "sha256",
    "row_count",
    "object_count",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "details",
)

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

FORBIDDEN_CLAIM_PHRASES = (
    "bet this",
    "guaranteed profit",
    "guaranteed win",
    "will win",
    "future lock",
    "recommended wager",
    "sure thing",
)


class EvidenceApiError(RuntimeError):
    """P367 evidence API source artifacts are missing or malformed."""


@dataclass(frozen=True)
class EvidenceApiOutput:
    contract: dict[str, object]
    examples: dict[str, object]
    validation_rows: tuple[dict[str, str], ...]
    manifest_rows: tuple[dict[str, str], ...]
    readme_md: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with open(path, newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def _artifact_path(relpath: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return root / relpath


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


def _count_for_source(path: Path) -> tuple[str, str]:
    if path.suffix == ".csv":
        return str(len(_read_csv_rows(path))), ""
    if path.suffix == ".json":
        payload = _read_json(path)
        if isinstance(payload, list):
            return "", str(len(payload))
        return "", "1"
    return "", ""


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for _stage, _role, _kind, relpath in SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise EvidenceApiError(f"required P363/P364/P365/P366 evidence artifacts missing: {missing}")
    return paths


def source_artifact_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_artifacts(repo_root)
    rows: list[dict[str, str]] = []
    for stage, role, expected_kind, relpath in SOURCE_ARTIFACTS:
        path = _artifact_path(relpath, repo_root)
        row_count, object_count = _count_for_source(path)
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": role,
                "path": relpath,
                "source_stage": stage,
                "sha256": sha256_file(path),
                "row_count": row_count,
                "object_count": object_count,
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": f"{expected_kind} source evidence read by P367 facade.",
            }
        )
    return tuple(rows)


def load_release_manifest(repo_root: Path | None = None) -> dict[str, object]:
    payload = _read_json(_artifact_path("artifacts/P366_biglotto_evidence_release_bundle_manifest.json", repo_root))
    if not isinstance(payload, dict):
        raise EvidenceApiError("P366 release manifest must be a JSON object")
    return dict(payload)


def load_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P366_biglotto_evidence_release_bundle_inventory.csv", repo_root))


def _adapter_cards(repo_root: Path | None = None) -> tuple[dict[str, object], ...]:
    payload = _read_json(_artifact_path("artifacts/P365_biglotto_evidence_explorer_adapter_detail_cards.json", repo_root))
    if not isinstance(payload, list):
        raise EvidenceApiError("P365 adapter detail cards must be a JSON list")
    return tuple(dict(card) for card in payload if isinstance(card, dict))


def _subset_cards(repo_root: Path | None = None) -> tuple[dict[str, object], ...]:
    payload = _read_json(_artifact_path("artifacts/P365_biglotto_evidence_explorer_subset_detail_cards.json", repo_root))
    if not isinstance(payload, list):
        raise EvidenceApiError("P365 subset detail cards must be a JSON list")
    return tuple(dict(card) for card in payload if isinstance(card, dict))


def _pairwise_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P365_biglotto_evidence_explorer_pairwise_comparison.csv", repo_root))


def list_adapters(repo_root: Path | None = None) -> tuple[str, ...]:
    return tuple(str(card["adapter_function"]) for card in _adapter_cards(repo_root))


def get_adapter(adapter_function: str, repo_root: Path | None = None) -> dict[str, object]:
    for card in _adapter_cards(repo_root):
        if card.get("adapter_function") == adapter_function:
            return dict(card)
    raise EvidenceApiError(f"adapter not found: {adapter_function}")


def list_subsets(
    subset_size: int | str | None = None, repo_root: Path | None = None
) -> tuple[dict[str, object], ...]:
    return tuple(
        dict(card)
        for card in _subset_cards(repo_root)
        if subset_size is None or str(card.get("subset_size")) == str(subset_size)
    )


def get_subset(adapter_subset: str, repo_root: Path | None = None) -> dict[str, object]:
    for card in _subset_cards(repo_root):
        if card.get("adapter_subset") == adapter_subset:
            return dict(card)
    raise EvidenceApiError(f"subset not found: {adapter_subset}")


def compare_adapters(adapter_a: str, adapter_b: str, repo_root: Path | None = None) -> dict[str, str]:
    expected = tuple(sorted((adapter_a, adapter_b)))
    for row in _pairwise_rows(repo_root):
        if (row["adapter_a"], row["adapter_b"]) == expected:
            return dict(row)
    raise EvidenceApiError(f"pairwise comparison not found: {adapter_a} | {adapter_b}")


def get_compact_shortlist(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P365_biglotto_evidence_explorer_compact_shortlist.csv", repo_root))


def build_contract(repo_root: Path | None = None) -> dict[str, object]:
    source_rows = source_artifact_rows(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "supported_functions": [
            {
                "name": "load_release_manifest",
                "input_arguments": [],
                "output_schema_name": "P366ReleaseManifest",
            },
            {"name": "load_inventory", "input_arguments": [], "output_schema_name": "ReleaseInventoryRows"},
            {"name": "list_adapters", "input_arguments": [], "output_schema_name": "AdapterFunctionList"},
            {
                "name": "get_adapter",
                "input_arguments": ["adapter_function"],
                "output_schema_name": "AdapterDetailCard",
            },
            {
                "name": "list_subsets",
                "input_arguments": ["subset_size"],
                "output_schema_name": "SubsetDetailCardList",
            },
            {
                "name": "get_subset",
                "input_arguments": ["adapter_subset"],
                "output_schema_name": "SubsetDetailCard",
            },
            {
                "name": "compare_adapters",
                "input_arguments": ["adapter_a", "adapter_b"],
                "output_schema_name": "PairwiseComparisonRow",
            },
            {
                "name": "get_compact_shortlist",
                "input_arguments": [],
                "output_schema_name": "CompactShortlistRows",
            },
            {
                "name": "validate_evidence_stack",
                "input_arguments": [],
                "output_schema_name": "ValidationRows",
            },
        ],
        "schemas": {
            "P366ReleaseManifest": "JSON object from artifacts/P366_biglotto_evidence_release_bundle_manifest.json",
            "ReleaseInventoryRows": "CSV rows from artifacts/P366_biglotto_evidence_release_bundle_inventory.csv",
            "AdapterFunctionList": "Ordered adapter_function strings from P365 adapter detail cards.",
            "AdapterDetailCard": "One JSON object from P365 adapter detail cards.",
            "SubsetDetailCardList": "Filtered JSON objects from P365 subset detail cards.",
            "SubsetDetailCard": "One JSON object from P365 subset detail cards.",
            "PairwiseComparisonRow": "One CSV row from P365 pairwise comparison evidence.",
            "CompactShortlistRows": "CSV rows from P365 compact shortlist evidence.",
            "ValidationRows": "P367 validation CSV rows.",
        },
        "artifact_sources": tuple(
            {
                "stage": row["source_stage"],
                "role": row["artifact_role"],
                "path": row["path"],
                "sha256": row["sha256"],
            }
            for row in source_rows
        ),
        "statements": STATEMENTS,
        "no_db_open_write_statement": "No DB was opened or written.",
        "no_adapter_calls_statement": "No adapters were called or executed.",
        "no_new_scoring_statement": (
            "No new scoring cohort, blended leaderboard, shape-only scoring, or blocked target scoring was created."
        ),
    }


def build_examples(repo_root: Path | None = None) -> dict[str, object]:
    adapters = list_adapters(repo_root)
    subsets_size_2 = list_subsets(2, repo_root)
    if not adapters:
        raise EvidenceApiError("adapter evidence is empty")
    if not subsets_size_2:
        raise EvidenceApiError("subset-size-2 evidence is empty")
    first_pair = str(subsets_size_2[0]["adapter_subset"]).split(";")
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "statements": STATEMENTS,
        "examples": {
            "list_adapters": adapters,
            "one_adapter_detail": get_adapter(adapters[0], repo_root),
            "list_subset_size_2": subsets_size_2,
            "one_subset_detail": get_subset(str(subsets_size_2[0]["adapter_subset"]), repo_root),
            "one_pairwise_comparison": compare_adapters(first_pair[1], first_pair[0], repo_root),
            "compact_shortlist": get_compact_shortlist(repo_root),
            "validation_summary": {
                "expected_adapter_count": EXPECTED_ADAPTER_COUNT,
                "expected_subset_count": EXPECTED_SUBSET_COUNT,
                "no_db_open_write": True,
                "no_adapter_calls": True,
                "no_new_scoring": True,
            },
        },
    }


def _generated_artifact_texts_without_manifest(repo_root: Path | None = None) -> dict[str, str]:
    contract = build_contract(repo_root)
    examples = build_examples(repo_root)
    readme = render_readme()
    return {
        "contract": _json_text(contract),
        "examples": _json_text(examples),
        "readme": readme,
    }


def validate_evidence_stack(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    source_rows = source_artifact_rows(repo_root)
    for row in source_rows:
        path = _artifact_path(row["path"], repo_root)
        rows.append(
            _check(
                f"required_artifact_exists:{row['path']}",
                path.is_file(),
                "exists",
                path.is_file(),
                f"{row['source_stage']} source evidence file is present.",
            )
        )
        if path.suffix == ".json":
            try:
                payload = _read_json(path)
                rows.append(
                    _check(
                        f"json_artifact_parses:{row['path']}",
                        True,
                        "parseable json",
                        type(payload).__name__,
                        "JSON parsed with json.load.",
                    )
                )
            except json.JSONDecodeError as exc:
                rows.append(
                    _check(
                        f"json_artifact_parses:{row['path']}",
                        False,
                        "parseable json",
                        type(exc).__name__,
                        str(exc),
                    )
                )
        elif path.suffix == ".csv":
            try:
                parsed_rows = _read_csv_rows(path)
                rows.append(
                    _check(
                        f"csv_artifact_parses:{row['path']}",
                        True,
                        "parseable csv",
                        len(parsed_rows),
                        "CSV parsed with csv.DictReader.",
                    )
                )
            except csv.Error as exc:
                rows.append(
                    _check(
                        f"csv_artifact_parses:{row['path']}",
                        False,
                        "parseable csv",
                        type(exc).__name__,
                        str(exc),
                    )
                )
        elif path.suffix in {".html", ".md"}:
            rows.append(
                _check(
                    f"html_markdown_artifact_exists:{row['path']}",
                    path.is_file(),
                    "exists",
                    path.is_file(),
                    "HTML/Markdown evidence artifact exists for local inspection.",
                )
            )
    rows.append(
        _check(
            "source_sha256_values_available",
            all(len(row["sha256"]) == 64 for row in source_rows),
            f"{len(source_rows)} sha256 values",
            sum(1 for row in source_rows if len(row["sha256"]) == 64),
            "Every source artifact row has a SHA256 digest.",
        )
    )
    adapters = list_adapters(repo_root)
    subsets = list_subsets(repo_root=repo_root)
    pairwise = _pairwise_rows(repo_root)
    shortlist = get_compact_shortlist(repo_root)
    rows.extend(
        (
            _check(
                "adapter_count_matches_expected_evidence",
                len(adapters) == EXPECTED_ADAPTER_COUNT,
                EXPECTED_ADAPTER_COUNT,
                len(adapters),
                "P365 adapter detail evidence exposes the expected adapter count.",
            ),
            _check(
                "subset_count_matches_expected_evidence",
                len(subsets) == EXPECTED_SUBSET_COUNT,
                EXPECTED_SUBSET_COUNT,
                len(subsets),
                "P365 subset detail evidence exposes the expected subset count.",
            ),
            _check(
                "pairwise_count_matches_expected_evidence",
                len(pairwise) == EXPECTED_PAIRWISE_COUNT,
                EXPECTED_PAIRWISE_COUNT,
                len(pairwise),
                "P365 pairwise evidence exposes the expected size-2 comparison count.",
            ),
            _check(
                "compact_shortlist_count_matches_expected_evidence",
                len(shortlist) == EXPECTED_COMPACT_SHORTLIST_COUNT,
                EXPECTED_COMPACT_SHORTLIST_COUNT,
                len(shortlist),
                "P365 compact shortlist evidence exposes the expected row count.",
            ),
        )
    )
    generated_text = "\n".join(_generated_artifact_texts_without_manifest(repo_root).values()).lower()
    found = [phrase for phrase in FORBIDDEN_CLAIM_PHRASES if phrase in generated_text]
    rows.append(
        _check(
            "generated_p367_forbidden_claim_phrases_absent",
            not found,
            "absent",
            ";".join(found) if found else "absent",
            "P367 generated contract/examples/readme contain no promotional or guarantee claim phrases.",
        )
    )
    return tuple(rows)


def render_readme() -> str:
    disclaimer = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    return f"""# P367 Big Lotto no-DB evidence API

Generated at: {GENERATED_AT}

This local API facade reads merged P363/P364/P365/P366 Big Lotto no-DB evidence artifacts and exposes stable Python functions plus a flag-based CLI for future Workers.

## Python API

```python
from recovered_strategies.biglotto import no_db_evidence_api as api

adapters = api.list_adapters()
adapter = api.get_adapter(adapters[0])
subsets = api.list_subsets(subset_size=2)
comparison = api.compare_adapters("adapt_biglotto_p0_2bet", "adapt_predict_biglotto_echo_2bet")
validation_rows = api.validate_evidence_stack()
```

## CLI

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_api --help
python3 -m recovered_strategies.biglotto.no_db_evidence_api --list-adapters
python3 -m recovered_strategies.biglotto.no_db_evidence_api --get-adapter adapt_predict_biglotto_echo_mixed_3bet
python3 -m recovered_strategies.biglotto.no_db_evidence_api --list-subsets --subset-size 2
python3 -m recovered_strategies.biglotto.no_db_evidence_api --get-subset adapt_biglotto_p0_2bet\\;adapt_predict_biglotto_echo_2bet
python3 -m recovered_strategies.biglotto.no_db_evidence_api --compare-adapters adapt_biglotto_p0_2bet adapt_predict_biglotto_echo_2bet
python3 -m recovered_strategies.biglotto.no_db_evidence_api --compact-shortlist
python3 -m recovered_strategies.biglotto.no_db_evidence_api --validate
python3 -m recovered_strategies.biglotto.no_db_evidence_api --emit-contract
```

With no action flag, the CLI writes the P367 artifacts into `artifacts/`.

## Scope

{disclaimer}

The facade builds only on merged P363/P364/P365/P366 evidence. It does not create a new scoring cohort, blended leaderboard, shape-only scoring, or blocked target scoring. It does not import production registries, deploy, call adapters, open a DB, or write a DB.
"""


def _output_artifact_rows(output_texts: Mapping[str, str]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for role, basename in P367_ARTIFACT_BASENAMES.items():
        text = output_texts.get(role, "")
        path = Path(basename)
        row_count = ""
        object_count = ""
        if role in {"validation", "manifest"} and text:
            row_count = str(len(tuple(csv.DictReader(text.splitlines()))))
        elif role in {"contract", "examples"} and text:
            object_count = "1"
        rows.append(
            {
                "artifact_group": "output",
                "artifact_role": role,
                "path": f"artifacts/{basename}",
                "source_stage": "P367",
                "sha256": sha256_bytes(text.encode("utf-8")) if text else "",
                "row_count": row_count,
                "object_count": object_count,
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P367 generated API facade artifact.",
            }
        )
    return tuple(rows)


def build_manifest_rows(
    validation_rows: tuple[dict[str, str], ...], output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None
) -> tuple[dict[str, str], ...]:
    output_texts = dict(output_texts_without_manifest)
    output_texts["manifest"] = ""
    rows = list(source_artifact_rows(repo_root))
    rows.extend(_output_artifact_rows(output_texts))
    rows.extend(
        (
            {
                "artifact_group": "statement",
                "artifact_role": "validation_summary",
                "path": "",
                "source_stage": "P367",
                "sha256": "",
                "row_count": str(len(validation_rows)),
                "object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": (
                    f"validation_pass={sum(1 for row in validation_rows if row['status'] == 'PASS')}; "
                    f"validation_fail={sum(1 for row in validation_rows if row['status'] == 'FAIL')}"
                ),
            },
            {
                "artifact_group": "statement",
                "artifact_role": "scope",
                "path": "",
                "source_stage": "P367",
                "sha256": "",
                "row_count": "",
                "object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": (
                    "Historical descriptive evidence only; no future prediction guarantee; no betting advice; "
                    "no DB open/write; no production registry import; no deploy; no adapter calls; "
                    "no new scoring cohort; no blended leaderboard; shape-only and blocked targets remain excluded."
                ),
            },
        )
    )
    return tuple(rows)


def _artifact_contents(output: EvidenceApiOutput) -> dict[str, str]:
    return {
        "contract": _json_text(output.contract),
        "examples": _json_text(output.examples),
        "validation": _csv_text(VALIDATION_COLUMNS, output.validation_rows),
        "manifest": _csv_text(MANIFEST_COLUMNS, output.manifest_rows),
        "readme": output.readme_md,
    }


def run_api(repo_root: Path | None = None) -> EvidenceApiOutput:
    contract = build_contract(repo_root)
    examples = build_examples(repo_root)
    readme = render_readme()
    validation_rows = validate_evidence_stack(repo_root)
    output_texts_without_manifest = {
        "contract": _json_text(contract),
        "examples": _json_text(examples),
        "validation": _csv_text(VALIDATION_COLUMNS, validation_rows),
        "readme": readme,
    }
    manifest_rows = build_manifest_rows(validation_rows, output_texts_without_manifest, repo_root)
    return EvidenceApiOutput(
        contract=contract,
        examples=examples,
        validation_rows=validation_rows,
        manifest_rows=manifest_rows,
        readme_md=readme,
    )


def _assert_deterministic(first: EvidenceApiOutput, second: EvidenceApiOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P367 API artifacts are not reproducible")


def write_artifacts(output: EvidenceApiOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P367_ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        with open(path, "w", encoding="utf-8", newline="" if path.suffix == ".csv" else None) as handle:
            handle.write(contents[key])
    return paths


def _print_json(payload: object) -> None:
    print(_json_text(payload), end="")


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    parser.add_argument("--list-adapters", action="store_true", help="emit adapter_function list as JSON")
    parser.add_argument("--get-adapter", metavar="ADAPTER_FUNCTION", help="emit one adapter detail card as JSON")
    parser.add_argument("--list-subsets", action="store_true", help="emit subset detail cards as JSON")
    parser.add_argument("--subset-size", type=int, choices=range(1, 6), help="filter --list-subsets by subset size")
    parser.add_argument("--get-subset", metavar="ADAPTER_SUBSET", help="emit one subset detail card as JSON")
    parser.add_argument(
        "--compare-adapters",
        nargs=2,
        metavar=("ADAPTER_A", "ADAPTER_B"),
        help="emit one pairwise comparison row as JSON",
    )
    parser.add_argument("--compact-shortlist", action="store_true", help="emit compact shortlist rows as CSV")
    parser.add_argument("--validate", action="store_true", help="emit validation rows as CSV")
    parser.add_argument("--emit-contract", action="store_true", help="emit API contract JSON")
    args = parser.parse_args(argv)

    first = run_api()
    second = run_api()
    _assert_deterministic(first, second)

    if args.list_adapters:
        _print_json(list_adapters())
    elif args.get_adapter:
        _print_json(get_adapter(args.get_adapter))
    elif args.list_subsets or args.subset_size is not None:
        _print_json(list_subsets(args.subset_size))
    elif args.get_subset:
        _print_json(get_subset(args.get_subset))
    elif args.compare_adapters:
        _print_json(compare_adapters(args.compare_adapters[0], args.compare_adapters[1]))
    elif args.compact_shortlist:
        _print_csv(
            (
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
            ),
            get_compact_shortlist(),
        )
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, first.validation_rows)
    elif args.emit_contract:
        _print_json(first.contract)
    else:
        paths = write_artifacts(first, args.artifacts_dir)
        print("P367 Big Lotto no-DB evidence API: determinism double-run PASS")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring cohort was created.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
