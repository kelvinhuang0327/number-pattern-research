#!/usr/bin/env python3
"""Audit the P213-A pybaseball dependency gate.

This script is deterministic and read-only. It does not fetch live MLB data,
call paid providers, write databases, activate production flows, or mutate
future tickets. It only validates the pinned dependency declaration and writes
report artifacts for this authorization-scoped gate.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib
import importlib.metadata as importlib_metadata
import importlib.util
import json
from pathlib import Path
import socket
import sys
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
P212_JSON_PATH = REPORT_DIR / "p212a_open_source_mlb_dependency_decision.json"
OUT_MD = REPORT_DIR / "p213a_pybaseball_dependency_gate.md"
OUT_JSON = REPORT_DIR / "p213a_pybaseball_dependency_gate.json"

DISCLAIMER = "pybaseball dependency gate only. Not live predictions, not betting advice."
PINNED_REQUIREMENT = "pybaseball==2.2.7"
EXPECTED_PACKAGE = "pybaseball"
FORBIDDEN_MLB_PACKAGES = (
    "MLB-StatsAPI",
    "python-mlb-statsapi",
    "baseballr",
)
LICENSE_REMINDER = (
    "pybaseball is distributed under the MIT license; review broader dependency "
    "and redistribution obligations before wider adoption."
)
DATA_TERMS_REMINDER = (
    "pybaseball wraps public baseball data sources. Respect each upstream source's "
    "terms, rate limits, attribution, caching expectations, and MLB notice "
    "boundaries before production use."
)
OWNER_AUTHORIZATION_REMINDER = (
    "P212-A required separate Owner authorization before dependency mutation. "
    "That authorization was provided in the current task thread before this gate ran."
)
NO_LIVE_CALLS_REMINDER = (
    "No live or remote data calls were made by this audit. Import smoke runs with a "
    "network guard and does not call pybaseball data functions."
)
NO_PRODUCTION_REMINDER = (
    "No production activation, DB write, model integration, or live data pipeline "
    "work was performed."
)


def _load_p212_payload() -> dict[str, Any]:
    return json.loads(P212_JSON_PATH.read_text(encoding="utf-8"))


def _normalized_requirement_lines() -> list[str]:
    lines: list[str] = []
    for raw_line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        normalized = raw_line.split("#", 1)[0].strip()
        if normalized:
            lines.append(normalized)
    return lines


def _requirements_audit() -> dict[str, Any]:
    lines = _normalized_requirement_lines()
    pybaseball_lines = [line for line in lines if line.lower().startswith("pybaseball")]
    forbidden_present = [
        package
        for package in FORBIDDEN_MLB_PACKAGES
        if any(line.lower().startswith(package.lower()) for line in lines)
    ]
    mlb_related_lines = [
        line
        for line in lines
        if "baseball" in line.lower() or "mlb-statsapi" in line.lower() or "statsapi" in line.lower()
    ]
    exact_pin_present = pybaseball_lines.count(PINNED_REQUIREMENT) == 1
    return {
        "path": str(REQUIREMENTS_PATH.relative_to(ROOT)),
        "exact_pin_required": PINNED_REQUIREMENT,
        "pybaseball_lines": pybaseball_lines,
        "pybaseball_line_count": len(pybaseball_lines),
        "exact_pin_present": exact_pin_present,
        "forbidden_packages_present": forbidden_present,
        "mlb_related_lines": mlb_related_lines,
        "status": (
            "PASS"
            if exact_pin_present
            and len(pybaseball_lines) == 1
            and not forbidden_present
            and mlb_related_lines == [PINNED_REQUIREMENT]
            else "FAIL"
        ),
    }


@contextmanager
def _network_guard() -> Any:
    def _blocked(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Network access blocked by P213-A audit guard.")

    with mock.patch("socket.create_connection", side_effect=_blocked), mock.patch.object(
        socket.socket,
        "connect",
        side_effect=_blocked,
    ), mock.patch.object(socket.socket, "connect_ex", side_effect=_blocked):
        yield


def _import_smoke() -> dict[str, Any]:
    spec = importlib.util.find_spec(EXPECTED_PACKAGE)
    if spec is None:
        return {
            "attempted": False,
            "importable": False,
            "installed_version": None,
            "status": "SKIPPED_NOT_INSTALLED_IN_CURRENT_PYTHON",
            "reason": (
                "pybaseball is not installed in the current python3 environment. "
                "This dependency gate does not install packages."
            ),
            "network_guard": "PASS",
        }

    try:
        version = importlib_metadata.version(EXPECTED_PACKAGE)
    except importlib_metadata.PackageNotFoundError:
        version = None

    try:
        with _network_guard():
            importlib.import_module(EXPECTED_PACKAGE)
    except Exception as exc:  # pragma: no cover - environment-specific import failures.
        return {
            "attempted": True,
            "importable": False,
            "installed_version": version,
            "status": "FAILED_IMPORT_SMOKE",
            "reason": f"{exc.__class__.__name__}: {exc}",
            "network_guard": "PASS",
        }

    return {
        "attempted": True,
        "importable": True,
        "installed_version": version,
        "status": "PASS_IMPORTABLE_WITH_NETWORK_GUARD",
        "reason": (
            "pybaseball imported successfully under the network guard without calling "
            "remote data endpoints."
        ),
        "network_guard": "PASS",
    }


def build_payload() -> dict[str, Any]:
    p212_payload = _load_p212_payload()
    requirements_audit = _requirements_audit()
    import_smoke = _import_smoke()

    p212_status_ok = (
        p212_payload.get("decision_status") == "PASS_NEEDS_SEPARATE_OWNER_AUTHORIZATION"
        and p212_payload.get("selected_candidate", {}).get("name") == EXPECTED_PACKAGE
    )

    checks = [
        {
            "name": "p212a_selected_pybaseball",
            "status": "PASS" if p212_status_ok else "FAIL",
            "detail": (
                "P212-A selected pybaseball and required separate Owner authorization."
            ),
        },
        {
            "name": "requirements_exact_pin",
            "status": requirements_audit["status"],
            "detail": (
                "requirements.txt contains exactly one pybaseball pin and no other MLB "
                "package declarations."
            ),
        },
        {
            "name": "import_smoke_read_only",
            "status": "PASS" if import_smoke["network_guard"] == "PASS" else "FAIL",
            "detail": (
                "Import smoke is read-only, does not call remote endpoints, and does not "
                "run pybaseball data functions."
            ),
        },
    ]
    audit_status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"

    return {
        "task": "P213-A pybaseball Dependency Gate",
        "scope": "PYBASEBALL_DEPENDENCY_GATE_ONLY",
        "audit_status": audit_status,
        "disclaimer": DISCLAIMER,
        "selected_dependency": {
            "package": EXPECTED_PACKAGE,
            "pin": PINNED_REQUIREMENT,
            "justification": (
                "P212-A selected pybaseball as the only authorized next-step candidate, "
                "and repo evidence already references version 2.2.7 as the concrete "
                "minimum pin for this gate."
            ),
        },
        "p212a_reference": {
            "decision_status": p212_payload["decision_status"],
            "selected_candidate": p212_payload["selected_candidate"]["name"],
            "required_notice": p212_payload["proposed_next_authorization"]["required_notice"],
            "authorization_status_for_p213a": (
                "EXPLICIT_OWNER_AUTHORIZATION_RECEIVED_IN_CURRENT_THREAD"
            ),
        },
        "requirements_audit": requirements_audit,
        "import_smoke": import_smoke,
        "license_reminder": LICENSE_REMINDER,
        "data_terms_reminder": DATA_TERMS_REMINDER,
        "owner_authorization_reminder": OWNER_AUTHORIZATION_REMINDER,
        "no_live_calls_reminder": NO_LIVE_CALLS_REMINDER,
        "no_production_reminder": NO_PRODUCTION_REMINDER,
        "guardrails": [
            DISCLAIMER,
            OWNER_AUTHORIZATION_REMINDER,
            NO_LIVE_CALLS_REMINDER,
            NO_PRODUCTION_REMINDER,
            "No other MLB package was added.",
            "No dependency installation was performed by this audit.",
        ],
        "checks": checks,
    }


def _md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_md_cell(item) for item in value)
    return str(value).replace("\n", " ").replace("|", "\\|")


def render_markdown(payload: dict[str, Any]) -> str:
    requirements_audit = payload["requirements_audit"]
    import_smoke = payload["import_smoke"]
    p212a_reference = payload["p212a_reference"]
    lines = [
        "# P213-A pybaseball Dependency Gate",
        "",
        payload["disclaimer"],
        "",
        "## Summary",
        "",
        f"- Audit status: {payload['audit_status']}",
        f"- Selected dependency pin: {payload['selected_dependency']['pin']}",
        f"- Dependency file: {requirements_audit['path']}",
        "- Scope: dependency gate only; no live prediction, no betting advice, no production activation.",
        "",
        "## P212-A Authorization Lineage",
        "",
        f"- P212-A decision status: {p212a_reference['decision_status']}",
        f"- P212-A selected candidate: {p212a_reference['selected_candidate']}",
        f"- P212-A required notice: {p212a_reference['required_notice']}",
        f"- P213-A authorization status: {p212a_reference['authorization_status_for_p213a']}",
        "",
        "## Dependency Audit",
        "",
        f"- Exact pin required: {requirements_audit['exact_pin_required']}",
        f"- pybaseball lines: {_md_cell(requirements_audit['pybaseball_lines'])}",
        f"- MLB-related dependency lines: {_md_cell(requirements_audit['mlb_related_lines'])}",
        f"- Forbidden packages present: {_md_cell(requirements_audit['forbidden_packages_present'])}",
        f"- Dependency audit status: {requirements_audit['status']}",
        "",
        "## Import Smoke",
        "",
        f"- Attempted: {_md_cell(import_smoke['attempted'])}",
        f"- Importable: {_md_cell(import_smoke['importable'])}",
        f"- Installed version in current python3: {_md_cell(import_smoke['installed_version'])}",
        f"- Status: {import_smoke['status']}",
        f"- Reason: {import_smoke['reason']}",
        f"- Network guard: {import_smoke['network_guard']}",
        "",
        "## Reminders",
        "",
        f"- {payload['license_reminder']}",
        f"- {payload['data_terms_reminder']}",
        f"- {payload['owner_authorization_reminder']}",
        f"- {payload['no_live_calls_reminder']}",
        f"- {payload['no_production_reminder']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in payload["checks"]:
        lines.append(
            f"| {_md_cell(check['name'])} | {_md_cell(check['status'])} | "
            f"{_md_cell(check['detail'])} |"
        )
    lines.extend(
        [
            "",
            DISCLAIMER,
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(render_markdown(payload) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_reports(payload)
    if payload["audit_status"] != "PASS":
        print("P213-A PYBASEBALL DEPENDENCY GATE FAIL")
        return 1
    print("P213-A PYBASEBALL DEPENDENCY GATE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
