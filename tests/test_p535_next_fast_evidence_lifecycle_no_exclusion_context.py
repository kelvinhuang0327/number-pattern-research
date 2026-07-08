"""Focused static tests for P535_NEXT_FAST evidence lifecycle context."""

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


def _monitor_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split(
        "// P524A_FAST: read-only monitoring", 1
    )[1].split("</script>", 1)[0]


def test_existing_evidence_payload_provides_lifecycle_no_exclusion_context() -> None:
    payload = json.loads(EVIDENCE_ARTIFACT.read_text(encoding="utf-8"))
    global_summary = payload["global_summary"]
    default_filter = payload["default_filter_state"]

    assert global_summary["lifecycle_is_label_not_exclusion"] is True
    assert default_filter["exclude_by_lifecycle"] is False
    assert default_filter["historical_rows_visible"] is True
    assert default_filter["artifact_only_visible"] is True


def test_monitor_renders_existing_lifecycle_context_safely() -> None:
    script = _monitor_script()

    for expected in (
        "// P535_NEXT_FAST: expose lifecycle no-exclusion context already present in the payload.",
        "payload.default_filter_state",
        "global.lifecycle_is_label_not_exclusion",
        "defaultFilter.exclude_by_lifecycle",
        "defaultFilter.historical_rows_visible",
        "defaultFilter.artifact_only_visible",
        "lifecycle=label/filter only",
        "no lifecycle exclusion",
        "historical rows visible",
        "artifact-only visible",
        "lifecycleContext.join(' · ')",
        "detail.textContent",
    ):
        assert expected in script

    assert "detail.innerHTML" not in script


def test_lifecycle_context_extends_existing_read_only_monitor_without_new_fetch() -> None:
    script = _monitor_script()
    endpoint_fetch = "fetch(base + '/api/replay/evidence-dashboard')"

    assert script.count(endpoint_fetch) == 1
    assert "sourceContext.join(' · ')" in script
    assert "artifactIdentity.join(' · ')" in script
    assert "strategyCoverage" in script
    assert "method:" not in script


def test_lifecycle_context_change_stays_no_db_non_mutating_and_non_predictive() -> None:
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
