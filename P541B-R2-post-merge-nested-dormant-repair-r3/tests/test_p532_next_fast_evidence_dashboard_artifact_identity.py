"""Focused static tests for P532_NEXT_FAST evidence artifact identity."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
EVIDENCE_ARTIFACT = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"
)


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _monitor_script() -> str:
    return _html().split("// P524A_FAST: read-only monitoring", 1)[1].split(
        "</script>", 1
    )[0]


def test_existing_evidence_artifact_provides_identity_fields() -> None:
    payload = json.loads(EVIDENCE_ARTIFACT.read_text(encoding="utf-8"))

    assert payload["task_id"] == "P251B"
    assert payload["schema_version"] == "1.0"


def test_monitor_renders_existing_artifact_identity_fields_safely() -> None:
    script = _monitor_script()

    for expected in (
        "// P532_NEXT_FAST: expose evidence artifact identity",
        "payload.task_id",
        "payload.schema_version",
        "payload.task_id.trim()",
        "payload.schema_version.trim()",
        "artifact=",
        "schema=",
        "artifactIdentity.join(' · ')",
        "detail.textContent",
    ):
        assert expected in script

    assert "detail.innerHTML" not in script


def test_identity_extends_existing_monitor_without_new_fetch() -> None:
    script = _monitor_script()
    endpoint_fetch = "fetch(base + '/api/replay/evidence-dashboard')"

    assert script.count(endpoint_fetch) == 1
    assert "global.current_registry_entries" in script
    assert "global.replay_rows_total" in script
    assert "payload.lottery_cards" in script
    assert "payload.stale_snapshot_warning.message" in script
    assert "method:" not in script


def test_identity_change_stays_no_db_non_mutating_and_non_predictive() -> None:
    script = _monitor_script()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "winning",
        "edge",
        "betting",
    ):
        assert forbidden not in script
