from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_pybaseball_dependency.py"
REQUIREMENTS = ROOT / "requirements.txt"
OUT_MD = ROOT / "report" / "p213a_pybaseball_dependency_gate.md"
OUT_JSON = ROOT / "report" / "p213a_pybaseball_dependency_gate.json"
DISCLAIMER = "pybaseball dependency gate only. Not live predictions, not betting advice."
PIN = "pybaseball==2.2.7"


def _run_cli() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_requirements_only_adds_expected_pybaseball_pin():
    lines = [
        line.split("#", 1)[0].strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.split("#", 1)[0].strip()
    ]

    mlb_related = [
        line
        for line in lines
        if "baseball" in line.lower() or "mlb-statsapi" in line.lower() or "statsapi" in line.lower()
    ]

    assert PIN in lines
    assert lines.count(PIN) == 1
    assert mlb_related == [PIN]
    assert not any(line.startswith("MLB-StatsAPI") for line in lines)
    assert not any(line.startswith("python-mlb-statsapi") for line in lines)
    assert not any(line.startswith("baseballr") for line in lines)


def test_audit_script_writes_deterministic_reports_with_required_scope_notices():
    first = _run_cli()
    first_json = OUT_JSON.read_text(encoding="utf-8")
    first_md = OUT_MD.read_text(encoding="utf-8")
    second = _run_cli()

    assert "P213-A PYBASEBALL DEPENDENCY GATE PASS" in first.stdout
    assert second.returncode == 0
    assert OUT_JSON.read_text(encoding="utf-8") == first_json
    assert OUT_MD.read_text(encoding="utf-8") == first_md

    payload = json.loads(first_json)
    assert payload["audit_status"] == "PASS"
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["selected_dependency"]["pin"] == PIN
    assert payload["requirements_audit"]["mlb_related_lines"] == [PIN]
    assert payload["requirements_audit"]["forbidden_packages_present"] == []
    assert payload["import_smoke"]["status"] == "SKIPPED_NOT_INSTALLED_IN_CURRENT_PYTHON"
    assert payload["import_smoke"]["installed_version"] is None
    assert payload["import_smoke"]["network_guard"] == "PASS"

    combined = (first_json + "\n" + first_md).lower()
    required_phrases = [
        "pybaseball dependency gate only. not live predictions, not betting advice.",
        "no live or remote data calls were made by this audit",
        "no production activation, db write, model integration, or live data pipeline work was performed",
        "no other mlb package was added",
    ]
    for phrase in required_phrases:
        assert phrase in combined


def test_report_respects_p212a_separate_authorization_requirement():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    markdown = OUT_MD.read_text(encoding="utf-8")

    assert payload["p212a_reference"]["decision_status"] == (
        "PASS_NEEDS_SEPARATE_OWNER_AUTHORIZATION"
    )
    assert payload["p212a_reference"]["selected_candidate"] == "pybaseball"
    assert payload["p212a_reference"]["required_notice"] == (
        "Dependency addition requires separate Owner authorization."
    )
    assert payload["p212a_reference"]["authorization_status_for_p213a"] == (
        "EXPLICIT_OWNER_AUTHORIZATION_RECEIVED_IN_CURRENT_THREAD"
    )
    assert "P212-A required separate Owner authorization before dependency mutation." in markdown
    assert "EXPLICIT_OWNER_AUTHORIZATION_RECEIVED_IN_CURRENT_THREAD" in markdown


def test_reports_do_not_claim_prediction_or_betting_performance():
    _run_cli()
    combined = (OUT_JSON.read_text(encoding="utf-8") + "\n" + OUT_MD.read_text(encoding="utf-8")).lower()
    assert DISCLAIMER.lower() in combined
    forbidden_patterns = [
        r"\bfuture prediction\b",
        r"\bedge\b",
        r"\broi\b",
        r"\bev\b",
        r"\bkelly\b",
        r"\bclv\b",
        r"\bproduction readiness\b",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, combined)
