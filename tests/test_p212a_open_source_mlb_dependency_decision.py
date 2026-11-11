from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan_mlb_open_source_dependency_adoption.py"
OUT_MD = ROOT / "report" / "p212a_open_source_mlb_dependency_decision.md"
OUT_JSON = ROOT / "report" / "p212a_open_source_mlb_dependency_decision.json"
DISCLAIMER = "Open-source MLB dependency decision gate only. Not live predictions, not betting advice."
OWNER_NOTICE = "Dependency addition requires separate Owner authorization."


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


def test_planner_writes_deterministic_decision_reports():
    first = _run_cli()
    first_json = OUT_JSON.read_text(encoding="utf-8")
    first_md = OUT_MD.read_text(encoding="utf-8")
    second = _run_cli()

    assert "P212-A OPEN-SOURCE MLB DEPENDENCY DECISION GATE PASS" in first.stdout
    assert second.returncode == 0
    assert OUT_JSON.read_text(encoding="utf-8") == first_json
    assert OUT_MD.read_text(encoding="utf-8") == first_md


def test_decision_payload_is_machine_readable_and_authorization_bound():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    assert payload["disclaimer"] == DISCLAIMER
    assert payload["decision_status"] == "PASS_NEEDS_SEPARATE_OWNER_AUTHORIZATION"
    assert payload["selected_candidate"]["name"] == "pybaseball"
    assert payload["selected_candidate"]["recommendation_status"] == (
        "SELECTED_FOR_SEPARATE_OWNER_AUTHORIZATION"
    )
    assert {candidate["name"] for candidate in payload["rejected_candidates"]} == {
        "MLB-StatsAPI",
        "python-mlb-statsapi",
        "baseballr",
    }
    assert payload["dependency_files_detected"] == ["requirements.txt"]
    assert payload["proposed_next_authorization"]["required_notice"] == OWNER_NOTICE
    assert OWNER_NOTICE in OUT_MD.read_text(encoding="utf-8")
    assert DISCLAIMER in OUT_MD.read_text(encoding="utf-8")


def test_each_candidate_contains_required_decision_fields():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    required = {
        "name",
        "source_package_reference",
        "license",
        "maintenance_release_signal",
        "python_runtime_compatibility",
        "data_terms_mlb_notice_risk",
        "dependency_risk",
        "recommendation_status",
    }

    candidates = [payload["selected_candidate"], *payload["rejected_candidates"]]
    assert len(candidates) == 4
    for candidate in candidates:
        assert required <= set(candidate)
        for key in required:
            assert candidate[key]


def test_gate_does_not_claim_formal_adoption_or_activation():
    _run_cli()
    combined = (
        OUT_JSON.read_text(encoding="utf-8") + "\n" + OUT_MD.read_text(encoding="utf-8")
    ).lower()

    assert "not formal dependency adoption" in combined
    assert "no dependency addition" in combined
    assert "no production activation" in combined
    assert "not live predictions, not betting advice" in combined
