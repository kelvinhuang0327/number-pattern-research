"""P368 Big Lotto no-DB evidence consumer bundle.

Consumes the merged P367 Big Lotto no-DB evidence API and packages its
artifact chain into a portable, deterministic bundle (bundle_manifest.json,
bundle_summary.json, bundle_summary.md) written to an explicit output
directory. It does not open or write a DB, import production registries,
call adapters, create new scoring cohorts, deploy, or make betting or
future-performance claims.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from recovered_strategies.biglotto import no_db_evidence_api as api

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P368_biglotto_evidence_consumer_bundle"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"

BUNDLE_ARTIFACT_BASENAMES = {
    "bundle_manifest": "bundle_manifest.json",
    "bundle_summary": "bundle_summary.json",
    "bundle_summary_md": "bundle_summary.md",
}

DISCLAIMER = (
    "This bundle is a read-only inventory of no-DB evidence artifacts assembled "
    "from the P367 Big Lotto no-DB evidence API. It is not proof of predictive "
    "performance, not an out-of-sample (OOS) claim, and not betting advice."
)


@dataclass(frozen=True)
class BundleOutput:
    manifest: dict[str, object]
    summary: dict[str, object]
    summary_md: str
    validation_rows: tuple[dict[str, str], ...]


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _artifact_entries(manifest_rows: Iterable[Mapping[str, str]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for row in manifest_rows:
        if row["artifact_group"] not in ("source", "output"):
            continue
        entries.append(
            {
                "artifact_group": row["artifact_group"],
                "artifact_role": row["artifact_role"],
                "path": row["path"] or None,
                "source_stage": row["source_stage"],
                "sha256": row["sha256"] or None,
                "row_count": int(row["row_count"]) if row["row_count"] else None,
                "object_count": int(row["object_count"]) if row["object_count"] else None,
            }
        )
    return entries


def _scope_booleans() -> tuple[bool, bool, bool]:
    no_db = not (api.STATEMENTS["db_opened"] or api.STATEMENTS["db_written"])
    no_adapter = not api.STATEMENTS["adapter_calls"]
    no_new_scoring_cohort = not api.STATEMENTS["new_scoring_cohort"]
    return no_db, no_adapter, no_new_scoring_cohort


def _validation_failure_messages(validation_rows: Iterable[Mapping[str, str]]) -> list[str]:
    return [f"{row['check_name']}: {row['details']}" for row in validation_rows if row["status"] == "FAIL"]


def build_bundle(repo_root: Path | None = None) -> BundleOutput:
    no_db, no_adapter, no_new_scoring_cohort = _scope_booleans()

    try:
        api_output = api.run_api(repo_root)
    except Exception as exc:  # the evidence chain must degrade to a reported FAIL, never an unhandled crash
        return _bundle_for_error(f"{type(exc).__name__}: {exc}", no_db, no_adapter, no_new_scoring_cohort)

    validation_rows = api_output.validation_rows
    fail_count = sum(1 for row in validation_rows if row["status"] == "FAIL")
    pass_count = len(validation_rows) - fail_count
    validation_status = "PASS" if fail_count == 0 else "FAIL"
    validation_failures = _validation_failure_messages(validation_rows)

    artifacts = _artifact_entries(api_output.manifest_rows)

    manifest = {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_api_task": api.TASK,
        "validation_status": validation_status,
        "validation_pass_count": pass_count,
        "validation_fail_count": fail_count,
        "validation_failures": validation_failures,
        "no_db": no_db,
        "no_adapter": no_adapter,
        "no_new_scoring_cohort": no_new_scoring_cohort,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }

    summary = {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_api_task": api.TASK,
        "artifact_count": len(artifacts),
        "validation_status": validation_status,
        "validation_pass_count": pass_count,
        "validation_fail_count": fail_count,
        "validation_failures": validation_failures,
        "no_db": no_db,
        "no_adapter": no_adapter,
        "no_new_scoring_cohort": no_new_scoring_cohort,
        "disclaimer": DISCLAIMER,
    }

    summary_md = render_summary_md(summary, artifacts)

    return BundleOutput(manifest=manifest, summary=summary, summary_md=summary_md, validation_rows=validation_rows)


def _bundle_for_error(message: str, no_db: bool, no_adapter: bool, no_new_scoring_cohort: bool) -> BundleOutput:
    manifest = {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_api_task": api.TASK,
        "validation_status": "FAIL",
        "validation_pass_count": 0,
        "validation_fail_count": 1,
        "validation_failures": [message],
        "no_db": no_db,
        "no_adapter": no_adapter,
        "no_new_scoring_cohort": no_new_scoring_cohort,
        "artifact_count": 0,
        "artifacts": [],
    }
    summary = {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_api_task": api.TASK,
        "artifact_count": 0,
        "validation_status": "FAIL",
        "validation_pass_count": 0,
        "validation_fail_count": 1,
        "validation_failures": [message],
        "no_db": no_db,
        "no_adapter": no_adapter,
        "no_new_scoring_cohort": no_new_scoring_cohort,
        "disclaimer": DISCLAIMER,
    }
    summary_md = render_summary_md(summary, [])
    return BundleOutput(manifest=manifest, summary=summary, summary_md=summary_md, validation_rows=())


def render_summary_md(summary: Mapping[str, object], artifacts: Iterable[Mapping[str, object]]) -> str:
    lines = [
        "# P368 Big Lotto no-DB evidence consumer bundle",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Source API task: {summary['source_api_task']}",
        "",
        f"Validation status: {summary['validation_status']} "
        f"({summary['validation_pass_count']} pass / {summary['validation_fail_count']} fail)",
        "",
        f"- no_db: {summary['no_db']}",
        f"- no_adapter: {summary['no_adapter']}",
        f"- no_new_scoring_cohort: {summary['no_new_scoring_cohort']}",
        "",
    ]
    if summary.get("validation_failures"):
        lines.extend(["## Validation failures", ""])
        lines.extend(f"- {message}" for message in summary["validation_failures"])
        lines.append("")
    lines += [
        "## Artifacts",
        "",
        "| artifact_role | source_stage | path | sha256 | row_count | object_count |",
        "|---|---|---|---|---|---|",
    ]
    for artifact in artifacts:
        lines.append(
            "| {role} | {stage} | {path} | {sha256} | {row_count} | {object_count} |".format(
                role=artifact["artifact_role"],
                stage=artifact["source_stage"],
                path=artifact["path"] or "(none)",
                sha256=(artifact["sha256"] or "")[:12],
                row_count=artifact["row_count"] if artifact["row_count"] is not None else "",
                object_count=artifact["object_count"] if artifact["object_count"] is not None else "",
            )
        )
    lines.extend(["", "## Disclaimer", "", str(summary["disclaimer"]), ""])
    return "\n".join(lines) + "\n"


def write_bundle(output: BundleOutput, output_dir: Path) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / basename for key, basename in BUNDLE_ARTIFACT_BASENAMES.items()}
    paths["bundle_manifest"].write_text(_json_text(output.manifest), encoding="utf-8")
    paths["bundle_summary"].write_text(_json_text(output.summary), encoding="utf-8")
    paths["bundle_summary_md"].write_text(output.summary_md, encoding="utf-8")
    return paths


def _assert_deterministic(first: BundleOutput, second: BundleOutput) -> None:
    if (first.manifest, first.summary, first.summary_md) != (second.manifest, second.summary, second.summary_md):
        raise RuntimeError("determinism double-run mismatch: P368 bundle is not reproducible")


def bundle_exit_code(output: BundleOutput) -> int:
    return 0 if output.summary["validation_status"] == "PASS" else 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="explicit directory to write bundle_manifest.json/bundle_summary.json/bundle_summary.md into",
    )
    parser.add_argument("--manifest", action="store_true", help="print bundle manifest JSON instead of writing files")
    parser.add_argument("--summary", action="store_true", help="print bundle summary JSON instead of writing files")
    args = parser.parse_args(argv)

    first = build_bundle()
    second = build_bundle()
    _assert_deterministic(first, second)
    exit_code = bundle_exit_code(first)

    if args.manifest:
        print(_json_text(first.manifest), end="")
        return exit_code
    if args.summary:
        print(_json_text(first.summary), end="")
        return exit_code

    if args.output_dir is None:
        parser.error("--output-dir is required unless --manifest or --summary is given")

    paths = write_bundle(first, args.output_dir)
    print("P368 Big Lotto no-DB evidence consumer bundle: determinism double-run PASS")
    print(f"validation status: {first.summary['validation_status']}")
    print(f"artifact count: {first.summary['artifact_count']}")
    print("No DB was opened or written; no adapters were called; no new scoring cohort was created.")
    for key, path in sorted(paths.items()):
        print(f"{key}: {path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
