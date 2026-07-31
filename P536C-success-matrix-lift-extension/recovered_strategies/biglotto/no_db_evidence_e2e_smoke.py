"""P372 Big Lotto no-DB evidence E2E smoke CLI.

Runs the P367 no-DB evidence API and P368 no-DB evidence consumer bundle
end-to-end against an explicit output directory and reports whether the
chain ran and produced artifacts. It does not open or write a DB, import
adapters, or create a new scoring cohort. This is a smoke test only: it is
not proof of predictive performance, not an out-of-sample (OOS) claim, and
not betting advice.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from recovered_strategies.biglotto import no_db_evidence_api as api
from recovered_strategies.biglotto import no_db_evidence_bundle as bundle

TASK = "P372_biglotto_no_db_evidence_e2e_smoke"

SUMMARY_ARTIFACT_BASENAMES = {
    "summary_json": "e2e_smoke_summary.json",
    "summary_md": "e2e_smoke_summary.md",
}

DISCLAIMER = (
    "This smoke test only checks that the P367/P368 no-DB evidence chain runs and "
    "produces artifacts. It is not proof of predictive performance, not an "
    "out-of-sample (OOS) claim, and not betting advice."
)


@dataclass(frozen=True)
class SmokeOutput:
    summary: dict[str, object]
    summary_md: str


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _scope_booleans() -> tuple[bool, bool, bool]:
    no_db = not (api.STATEMENTS["db_opened"] or api.STATEMENTS["db_written"])
    no_adapter = not api.STATEMENTS["adapter_calls"]
    no_new_scoring_cohort = not api.STATEMENTS["new_scoring_cohort"]
    return no_db, no_adapter, no_new_scoring_cohort


def _base_fields() -> dict[str, object]:
    no_db, no_adapter, no_new_scoring_cohort = _scope_booleans()
    return {
        "task": TASK,
        "no_db": no_db,
        "no_adapter": no_adapter,
        "no_new_scoring_cohort": no_new_scoring_cohort,
        "disclaimer": DISCLAIMER,
    }


def _render_summary_md(summary: Mapping[str, object]) -> str:
    lines = [
        "# P372 Big Lotto no-DB evidence E2E smoke",
        "",
        f"Status: {summary['status']}",
        "",
        f"- artifact_count: {summary['artifact_count']}",
        f"- bundle_manifest_path: {summary['bundle_manifest_path']}",
        f"- bundle_summary_path: {summary['bundle_summary_path']}",
        f"- no_db: {summary['no_db']}",
        f"- no_adapter: {summary['no_adapter']}",
        f"- no_new_scoring_cohort: {summary['no_new_scoring_cohort']}",
        "",
    ]
    if summary.get("error"):
        lines.extend(["## Error", "", str(summary["error"]), ""])
    lines.extend(["## Disclaimer", "", str(summary["disclaimer"]), ""])
    return "\n".join(lines) + "\n"


def _fail(base_fields: Mapping[str, object], error: str, artifact_count: int = 0) -> SmokeOutput:
    summary = {
        **base_fields,
        "status": "FAIL",
        "artifact_count": artifact_count,
        "bundle_manifest_path": None,
        "bundle_summary_path": None,
        "error": error,
    }
    return SmokeOutput(summary=summary, summary_md=_render_summary_md(summary))


def run_smoke(bundle_dir: Path, repo_root: Path | None = None) -> SmokeOutput:
    base_fields = _base_fields()

    try:
        bundle_output = bundle.build_bundle(repo_root)
    except Exception as exc:  # the evidence chain must degrade to a reported FAIL, never an unhandled crash
        return _fail(base_fields, f"{type(exc).__name__}: {exc}")

    if bundle_output.summary["validation_status"] != "PASS":
        failures = "; ".join(bundle_output.summary.get("validation_failures", []))
        return _fail(
            base_fields,
            f"bundle validation FAIL: {failures}",
            artifact_count=int(bundle_output.summary["artifact_count"]),
        )

    paths = bundle.write_bundle(bundle_output, bundle_dir)

    summary = {
        **base_fields,
        "status": "PASS",
        "artifact_count": int(bundle_output.summary["artifact_count"]),
        "bundle_manifest_path": str(paths["bundle_manifest"]),
        "bundle_summary_path": str(paths["bundle_summary"]),
        "error": None,
    }
    return SmokeOutput(summary=summary, summary_md=_render_summary_md(summary))


def write_summary(output: SmokeOutput, output_dir: Path) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / basename for key, basename in SUMMARY_ARTIFACT_BASENAMES.items()}
    paths["summary_json"].write_text(_json_text(output.summary), encoding="utf-8")
    paths["summary_md"].write_text(output.summary_md, encoding="utf-8")
    return paths


def smoke_exit_code(output: SmokeOutput) -> int:
    return 0 if output.summary["status"] == "PASS" else 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="explicit directory to write e2e_smoke_summary.json/.md and bundle/ artifacts into",
    )
    args = parser.parse_args(argv)

    output_dir: Path = args.output_dir
    bundle_dir = output_dir / "bundle"

    output = run_smoke(bundle_dir)
    summary_paths = write_summary(output, output_dir)
    exit_code = smoke_exit_code(output)

    print(f"P372 Big Lotto no-DB evidence E2E smoke: status={output.summary['status']}")
    print(f"artifact_count: {output.summary['artifact_count']}")
    if output.summary["error"]:
        print(f"error: {output.summary['error']}")
    print("No DB was opened or written; no adapters were called; no new scoring cohort was created.")
    for key, path in sorted(summary_paths.items()):
        print(f"{key}: {path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
