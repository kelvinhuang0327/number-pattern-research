"""Focused static tests for P534_NEXT_FAST evidence source context."""

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


def test_existing_evidence_payload_provides_source_context_fields() -> None:
    payload = json.loads(EVIDENCE_ARTIFACT.read_text(encoding="utf-8"))
    global_summary = payload["global_summary"]

    assert global_summary["source_of_truth"] == "P250A inventory artifact published on main"
    assert global_summary["current_registry_is_live_ssot"] is True
    assert global_summary["historical_scoreboard_is_snapshot"] is True


def test_monitor_renders_existing_source_context_safely() -> None:
    script = _monitor_script()

    for expected in (
        "// P534_NEXT_FAST: expose evidence source-of-truth context already present in the payload.",
        "global.source_of_truth",
        "global.current_registry_is_live_ssot",
        "global.historical_scoreboard_is_snapshot",
        "global.source_of_truth.trim()",
        "source='",
    ):
        assert expected in script

    assert "live registry SSOT" in script
    assert "historical snapshot context" in script
    assert "sourceContext.join(' · ')" in script
    assert "detail.textContent" in script
    assert "detail.innerHTML" not in script


def test_source_context_extends_existing_read_only_monitor_without_new_fetch() -> None:
    script = _monitor_script()
    endpoint_fetch = "fetch(base + '/api/replay/evidence-dashboard')"

    assert script.count(endpoint_fetch) == 1
    assert "artifactIdentity.join(' · ')" in script
    assert "strategyCoverage" in script
    assert "payload.lottery_cards" in script
    assert "method:" not in script


def test_source_context_change_stays_no_db_non_mutating_and_non_predictive() -> None:
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
