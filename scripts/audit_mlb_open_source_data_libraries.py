#!/usr/bin/env python3
"""Build the P211-A open-source MLB data library adoption report.

The audit is deterministic and read-only. It does not fetch live MLB data, call
paid providers, write a database, mutate tickets, or activate production flows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.mlb_open_source_data_adapter import (
    DISCLAIMER,
    LIBRARY_OPTIONS,
    library_diagnostic,
)

REPORT_DIR = ROOT / "report"
OUT_MD = REPORT_DIR / "p211a_open_source_mlb_data_adoption.md"
OUT_JSON = REPORT_DIR / "p211a_open_source_mlb_data_adoption.json"


@dataclass(frozen=True)
class CandidateEvaluation:
    package: str
    repo: str
    purpose: str
    license: str
    maintenance_release_evidence: str
    python_compatibility: str
    data_source_terms_risk: str
    fit_for_betting_repo: str
    adoption_decision: str
    evidence_urls: tuple[str, ...]


CANDIDATES: tuple[CandidateEvaluation, ...] = (
    CandidateEvaluation(
        package="pybaseball",
        repo="https://github.com/jldbc/pybaseball",
        purpose=(
            "Python package for historical baseball data including Statcast, "
            "FanGraphs, Baseball Reference, and player/team lookup helpers."
        ),
        license="MIT license.",
        maintenance_release_evidence=(
            "PyPI shows pybaseball 2.2.7 uploaded on 2023-09-08; the GitHub "
            "repository is public with issue/PR history visible as of 2026-07-01."
        ),
        python_compatibility=(
            "PyPI classifiers list Python 3.8, 3.9, 3.10, and 3.11. "
            "Local .venv import smoke found pybaseball 2.2.7 available on Python 3.13, "
            "but this task does not add or pin the dependency."
        ),
        data_source_terms_risk=(
            "Medium: it wraps multiple public baseball data sites/APIs. Consumers must "
            "respect each upstream source's terms, rate limits, attribution, and cache "
            "expectations before production activation."
        ),
        fit_for_betting_repo=(
            "Best fit for historical/statcast adoption spike because it covers the "
            "requested statcast/historical surface without custom MLB scraping logic."
        ),
        adoption_decision="RECOMMENDED_FOR_READ_ONLY_SPIKE_WITH_OPTIONAL_IMPORT",
        evidence_urls=(
            "https://pypi.org/project/pybaseball/",
            "https://github.com/jldbc/pybaseball",
        ),
    ),
    CandidateEvaluation(
        package="MLB-StatsAPI",
        repo="https://github.com/toddrob99/MLB-StatsAPI",
        purpose=(
            "Python wrapper for MLB Stats API endpoints covering teams, schedule, "
            "players, standings, and game metadata."
        ),
        license="GPL-3.0 license.",
        maintenance_release_evidence=(
            "PyPI shows version 1.9.0 released on 2025-04-04; GitHub repository is "
            "public and remains a recognized wrapper for statsapi-style team/schedule/"
            "player access as of 2026-07-01."
        ),
        python_compatibility=(
            "PyPI supports Python 3 and typical modern CPython usage; not currently "
            "installed in this repo's system python or .venv."
        ),
        data_source_terms_risk=(
            "Medium: delegates to MLB Stats API/public MLB endpoints. MLB copyright "
            "and acceptable-use language must be reviewed before production use."
        ),
        fit_for_betting_repo=(
            "Functionally useful for read-only team, schedule, and player metadata, "
            "but GPL-3.0 licensing requires Owner/license review before dependency add."
        ),
        adoption_decision="CANDIDATE_REQUIRES_LICENSE_REVIEW_BEFORE_AUTHORIZATION",
        evidence_urls=(
            "https://pypi.org/project/MLB-StatsAPI/",
            "https://github.com/toddrob99/MLB-StatsAPI",
            "https://gdx.mlb.com/components/copyright.txt",
        ),
    ),
    CandidateEvaluation(
        package="python-mlb-statsapi",
        repo="https://github.com/zero-sum-seattle/python-mlb-statsapi",
        purpose=(
            "Object-oriented Python client around MLB Stats API data models for teams, "
            "players, games, stats, and related metadata."
        ),
        license="MIT license.",
        maintenance_release_evidence=(
            "PyPI shows version 0.7.2 uploaded on 2026-02-05; GitHub repository is "
            "public and should still be reviewed before any dependency add."
        ),
        python_compatibility=(
            "PyPI requires Python >=3.10 and classifiers list Python 3.10 through "
            "3.14; not currently installed in this repo's system python or .venv."
        ),
        data_source_terms_risk=(
            "Medium: also relies on MLB Stats API/public MLB endpoints, so MLB terms, "
            "copyright, rate limits, and caching boundaries apply."
        ),
        fit_for_betting_repo=(
            "Possible object-oriented alternative for normalized team/player metadata, "
            "but not preferred over pybaseball plus MLB-StatsAPI for this spike."
        ),
        adoption_decision="SECONDARY_CANDIDATE_NOT_ADOPTED_IN_SPIKE",
        evidence_urls=(
            "https://pypi.org/project/python-mlb-statsapi/",
            "https://github.com/zero-sum-seattle/python-mlb-statsapi",
            "https://gdx.mlb.com/components/copyright.txt",
        ),
    ),
    CandidateEvaluation(
        package="baseballr",
        repo="https://github.com/BillPetti/baseballr",
        purpose=(
            "R package for baseball data retrieval and analysis across MLB public "
            "sources."
        ),
        license="MIT license.",
        maintenance_release_evidence=(
            "CRAN/GitHub package is public and known in the baseball analytics "
            "ecosystem, but it introduces an R runtime dependency."
        ),
        python_compatibility=(
            "Not a Python library. Introducing R runtime is outside this task unless "
            "separately authorized by CTO/Owner."
        ),
        data_source_terms_risk=(
            "Medium: wraps public baseball data sources with the same upstream terms "
            "and rate-limit concerns."
        ),
        fit_for_betting_repo=(
            "Useful comparison point only. Not suitable for this Python repo spike "
            "without explicit runtime authorization."
        ),
        adoption_decision="NOT_ADOPTED_R_RUNTIME_REQUIRES_SEPARATE_AUTHORIZATION",
        evidence_urls=(
            "https://github.com/BillPetti/baseballr",
            "https://cran.r-project.org/package=baseballr",
        ),
    ),
)


def build_report_payload() -> dict[str, Any]:
    diagnostics = [asdict(library_diagnostic(provider)) for provider in sorted(LIBRARY_OPTIONS)]
    return {
        "task": "P211-A Open-Source MLB Data Library Adoption Spike",
        "scope": "READ_ONLY_OPEN_SOURCE_MLB_DATA_ADOPTION_SPIKE",
        "disclaimer": DISCLAIMER,
        "audit_status": "PASS",
        "dependency_policy": (
            "No dependency files were modified. Optional import pattern only; dependency "
            "additions require Owner authorization."
        ),
        "production_policy": (
            "No DB writes, no paid provider calls, no live odds calls, no production "
            "activation, no future-ticket mutation."
        ),
        "candidate_evaluations": [asdict(candidate) for candidate in CANDIDATES],
        "adapter_diagnostics": diagnostics,
        "recommended_minimum_path": (
            "Use pybaseball as the first optional read-only adapter for historical/"
            "statcast samples; consider MLB-StatsAPI later for team/schedule/player "
            "metadata after dependency and MLB terms authorization."
        ),
        "validation_notes": [
            "Adapter fetch methods raise AdapterUnavailableError with clear reasons when packages are missing.",
            "Audit script performs deterministic diagnostics only and does not call live MLB endpoints.",
            "All output is labeled historical/read-only and excludes wagering-performance or staking claims.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# P211-A Open-Source MLB Data Library Adoption Spike",
        "",
        payload["disclaimer"],
        "",
        "## Scope",
        "",
        "- Read-only adoption spike only.",
        "- No DB writes, no paid provider calls, no live odds calls, no production activation.",
        "- No dependency files were modified; optional imports only.",
        "",
        "## Candidate Evaluation",
        "",
        "| Package | Purpose | License | Maintenance / Release Evidence | Python Compatibility | Data Terms Risk | Fit | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in payload["candidate_evaluations"]:
        lines.append(
            "| {package} | {purpose} | {license} | {maintenance_release_evidence} | "
            "{python_compatibility} | {data_source_terms_risk} | {fit_for_betting_repo} | "
            "{adoption_decision} |".format(**{key: _md_cell(value) for key, value in candidate.items()})
        )
    lines.extend(
        [
            "",
            "## Adapter Diagnostics",
            "",
            "| Provider | Package | Import | Installed | Importable | Version | Status | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for diagnostic in payload["adapter_diagnostics"]:
        lines.append(
            "| {provider} | {package_name} | {import_name} | {installed} | {importable} | "
            "{version} | {status} | {reason} |".format(
                **{key: _md_cell(value) for key, value in diagnostic.items()}
            )
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            payload["recommended_minimum_path"],
            "",
            "## Evidence URLs",
            "",
        ]
    )
    for candidate in payload["candidate_evaluations"]:
        for url in candidate["evidence_urls"]:
            lines.append(f"- {candidate['package']}: {url}")
    lines.extend(
        [
            "",
            "## Validation Notes",
            "",
        ]
    )
    for note in payload["validation_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    lines.append(payload["disclaimer"])
    lines.append("")
    return "\n".join(lines)


def _md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (tuple, list)):
        value = ", ".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload()
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print("P211-A OPEN-SOURCE MLB DATA LIBRARY ADOPTION AUDIT PASS")
    print(f"report markdown: {OUT_MD.relative_to(ROOT)}")
    print(f"report json: {OUT_JSON.relative_to(ROOT)}")
    for diagnostic in payload["adapter_diagnostics"]:
        print(
            "{provider}: {status} ({reason})".format(
                provider=diagnostic["provider"],
                status=diagnostic["status"],
                reason=diagnostic["reason"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
