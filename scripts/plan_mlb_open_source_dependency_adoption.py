#!/usr/bin/env python3
"""Build the P212-A open-source MLB dependency decision gate.

This planner is deterministic and offline. It reads the P211-A adoption report,
does not import candidate MLB libraries, does not modify dependency files, and
does not activate any production data path.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
P211_MD = REPORT_DIR / "p211a_open_source_mlb_data_adoption.md"
P211_JSON = REPORT_DIR / "p211a_open_source_mlb_data_adoption.json"
OUT_MD = REPORT_DIR / "p212a_open_source_mlb_dependency_decision.md"
OUT_JSON = REPORT_DIR / "p212a_open_source_mlb_dependency_decision.json"

DISCLAIMER = "Open-source MLB dependency decision gate only. Not live predictions, not betting advice."
OWNER_AUTHORIZATION_NOTICE = "Dependency addition requires separate Owner authorization."
EXPECTED_P211_HASHES = {
    "report/p211a_open_source_mlb_data_adoption.md": (
        "2f933ded3482ee632a5f64ee494044e3f165d0cbe7ca4abe230c0723c61dfd85"
    ),
    "report/p211a_open_source_mlb_data_adoption.json": (
        "ee4bbd8c579efabe6c74f85f76c30d9d26b80bf02bb83443b7220182b79eba09"
    ),
}
DEPENDENCY_PATTERNS = (
    "requirements*.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "uv.lock",
    "environment*.yml",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_p211_payload() -> dict[str, Any]:
    _validate_p211_report_files()
    return json.loads(P211_JSON.read_text(encoding="utf-8"))


def _validate_p211_report_files() -> None:
    for rel_path, expected_hash in EXPECTED_P211_HASHES.items():
        path = ROOT / rel_path
        if not path.exists():
            raise FileNotFoundError(f"Required P211-A report file is missing: {rel_path}")
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Required P211-A report hash mismatch for {rel_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )


def _detect_dependency_files() -> list[str]:
    files: set[str] = set()
    for pattern in DEPENDENCY_PATTERNS:
        files.update(_repo_relative(path) for path in ROOT.glob(pattern) if path.is_file())
    return sorted(files)


def _candidate_source(candidate: dict[str, Any]) -> str:
    urls = candidate.get("evidence_urls") or []
    if urls:
        return ", ".join(str(url) for url in urls)
    return str(candidate.get("repo", ""))


def _recommendation_status(candidate: dict[str, Any]) -> str:
    package = candidate["package"]
    if package == "pybaseball":
        return "SELECTED_FOR_SEPARATE_OWNER_AUTHORIZATION"
    if package == "MLB-StatsAPI":
        return "REJECTED_FOR_INITIAL_DEPENDENCY_GATE_GPL_LICENSE_REVIEW_REQUIRED"
    if package == "python-mlb-statsapi":
        return "REJECTED_FOR_INITIAL_DEPENDENCY_GATE_SECONDARY_METADATA_CLIENT"
    if package == "baseballr":
        return "REJECTED_FOR_INITIAL_DEPENDENCY_GATE_R_RUNTIME_OUT_OF_SCOPE"
    return "REJECTED_FOR_INITIAL_DEPENDENCY_GATE_NOT_SELECTED"


def _dependency_risk(candidate: dict[str, Any]) -> str:
    package = candidate["package"]
    if package == "pybaseball":
        return (
            "Requires a new Python dependency pin and transitive dependency review; no dependency "
            "file is changed by this gate."
        )
    if package == "MLB-StatsAPI":
        return "GPL-3.0 license creates a higher authorization burden for this repo."
    if package == "python-mlb-statsapi":
        return "Python >=3.10 is compatible, but it is a secondary metadata client for this gate."
    if package == "baseballr":
        return "Requires an R runtime dependency that is outside this Python repo gate."
    return "Not selected by this gate."


def _decision_candidates(p211_payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for candidate in p211_payload["candidate_evaluations"]:
        candidates.append(
            {
                "name": candidate["package"],
                "source_package_reference": _candidate_source(candidate),
                "license": candidate["license"],
                "maintenance_release_signal": candidate["maintenance_release_evidence"],
                "python_runtime_compatibility": candidate["python_compatibility"],
                "data_terms_mlb_notice_risk": candidate["data_source_terms_risk"],
                "dependency_risk": _dependency_risk(candidate),
                "recommendation_status": _recommendation_status(candidate),
                "p211_adoption_decision": candidate["adoption_decision"],
            }
        )
    return candidates


def build_decision_payload() -> dict[str, Any]:
    p211_payload = _load_p211_payload()
    candidates = _decision_candidates(p211_payload)
    selected = next(candidate for candidate in candidates if candidate["name"] == "pybaseball")
    rejected = [candidate for candidate in candidates if candidate["name"] != selected["name"]]

    return {
        "task": "P212-A Open-Source MLB Dependency Decision Gate",
        "scope": "OPEN_SOURCE_MLB_DEPENDENCY_DECISION_GATE_ONLY",
        "disclaimer": DISCLAIMER,
        "decision_status": "PASS_NEEDS_SEPARATE_OWNER_AUTHORIZATION",
        "selected_candidate": selected,
        "rejected_candidates": rejected,
        "license_risks": [
            {
                "candidate": "pybaseball",
                "risk": "MIT license appears compatible for initial authorization review, subject to Owner approval.",
            },
            {
                "candidate": "MLB-StatsAPI",
                "risk": "GPL-3.0 license requires explicit Owner/license authorization before any dependency add.",
            },
            {
                "candidate": "baseballr",
                "risk": "MIT license is not sufficient to offset the out-of-scope R runtime dependency.",
            },
        ],
        "data_terms_risks": [
            {
                "candidate": candidate["name"],
                "risk": candidate["data_terms_mlb_notice_risk"],
            }
            for candidate in candidates
        ],
        "dependency_files_detected": _detect_dependency_files(),
        "proposed_next_authorization": {
            "action": "Request separate Owner authorization to add pybaseball as a pinned optional Python dependency for read-only historical/statcast MLB data work.",
            "required_notice": OWNER_AUTHORIZATION_NOTICE,
            "owner_authorizations_required": [
                "Owner approval to modify dependency files in a separate task.",
                "Owner/legal acceptance of upstream public baseball data terms, rate limits, attribution, caching, and MLB notice boundaries before production use.",
                "CTO review before any production activation, DB write path, live provider call, or model integration.",
            ],
            "not_authorized_by_this_gate": [
                "No dependency addition.",
                "No dependency file mutation.",
                "No live or paid provider connection.",
                "No DB write.",
                "No production activation.",
                "No model logic change.",
            ],
        },
        "prohibited_claims": [
            "future prediction",
            "betting advice",
            "production readiness",
            "edge",
            "ROI",
            "EV",
            "Kelly",
            "CLV",
        ],
        "source_evidence": {
            "p211_md": _repo_relative(P211_MD),
            "p211_json": _repo_relative(P211_JSON),
            "p211_report_hashes": EXPECTED_P211_HASHES,
            "p211_recommended_minimum_path": p211_payload["recommended_minimum_path"],
        },
        "guardrails": [
            DISCLAIMER,
            OWNER_AUTHORIZATION_NOTICE,
            "This decision gate is not formal dependency adoption.",
            "This decision gate does not add, import, or install any candidate MLB package.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# P212-A Open-Source MLB Dependency Decision Gate",
        "",
        payload["disclaimer"],
        "",
        "## Decision",
        "",
        f"- Status: {payload['decision_status']}",
        f"- Selected candidate: {payload['selected_candidate']['name']}",
        f"- Required notice: {payload['proposed_next_authorization']['required_notice']}",
        "- This decision gate is not formal dependency adoption.",
        "- No dependency files are modified by this gate.",
        "",
        "## Candidate Matrix",
        "",
        "| Candidate | Source / Package Reference | License | Maintenance / Release Signal | Python / Runtime Compatibility | Data Terms / MLB Notice Risk | Dependency Risk | Recommendation Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in [payload["selected_candidate"], *payload["rejected_candidates"]]:
        lines.append(
            "| {name} | {source_package_reference} | {license} | {maintenance_release_signal} | "
            "{python_runtime_compatibility} | {data_terms_mlb_notice_risk} | "
            "{dependency_risk} | {recommendation_status} |".format(
                **{key: _md_cell(value) for key, value in candidate.items()}
            )
        )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Proceed only to a separate Owner authorization request for pybaseball as the "
                "initial open-source MLB dependency candidate for read-only historical/statcast "
                "data work."
            ),
            "",
            OWNER_AUTHORIZATION_NOTICE,
            "",
            "Do not add pybaseball, MLB-StatsAPI, python-mlb-statsapi, baseballr, or any other MLB package in this gate.",
            "",
            "## Required Authorizations",
            "",
        ]
    )
    for item in payload["proposed_next_authorization"]["owner_authorizations_required"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Rejected Candidates", ""])
    for candidate in payload["rejected_candidates"]:
        lines.append(f"- {candidate['name']}: {candidate['recommendation_status']}")

    lines.extend(["", "## Dependency Files Detected", ""])
    for path in payload["dependency_files_detected"]:
        lines.append(f"- {path}")

    lines.extend(["", "## Risk Boundaries", ""])
    for item in payload["proposed_next_authorization"]["not_authorized_by_this_gate"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Prohibited Claims", ""])
    for claim in payload["prohibited_claims"]:
        lines.append(f"- {claim}")

    lines.extend(
        [
            "",
            "## Source Evidence",
            "",
            f"- P211-A Markdown: {payload['source_evidence']['p211_md']}",
            f"- P211-A JSON: {payload['source_evidence']['p211_json']}",
            f"- P211-A recommendation: {payload['source_evidence']['p211_recommended_minimum_path']}",
            "",
            payload["disclaimer"],
            "",
        ]
    )
    return "\n".join(lines)


def _md_cell(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value)
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def write_reports() -> dict[str, Any]:
    payload = build_decision_payload()
    REPORT_DIR.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def main() -> int:
    payload = write_reports()
    print("P212-A OPEN-SOURCE MLB DEPENDENCY DECISION GATE PASS")
    print(f"selected_candidate={payload['selected_candidate']['name']}")
    print(OWNER_AUTHORIZATION_NOTICE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
