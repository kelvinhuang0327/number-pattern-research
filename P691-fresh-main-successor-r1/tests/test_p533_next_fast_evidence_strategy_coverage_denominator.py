"""Focused static tests for P533_NEXT_FAST evidence strategy coverage."""

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


def test_existing_evidence_payload_provides_strategy_coverage_denominators() -> None:
    payload = json.loads(EVIDENCE_ARTIFACT.read_text(encoding="utf-8"))

    assert payload["lottery_cards"]
    for card in payload["lottery_cards"]:
        assert isinstance(card["replay_strategy_entries"], int)
        assert isinstance(card["strategy_cards_visible"], int)
        assert 0 <= card["replay_strategy_entries"] <= card["strategy_cards_visible"]


def test_monitor_renders_strategy_coverage_as_explicit_count_over_denominator() -> None:
    script = _monitor_script()

    for expected in (
        "// P533_NEXT_FAST: expose per-lottery replay strategy coverage denominators.",
        "card.replay_strategy_entries",
        "card.strategy_cards_visible",
        "replayStrategies.toLocaleString() + '/' + visibleStrategies.toLocaleString() + ' strategies'",
        "(strategyCoverage ? ' · ' + strategyCoverage : '')",
        "detail.textContent",
    ):
        assert expected in script

    assert "detail.innerHTML" not in script
    assert "strategyCoverage /" not in script
    assert "strategyCoverage * 100" not in script


def test_coverage_extends_existing_read_only_monitor_without_new_fetch() -> None:
    script = _monitor_script()
    endpoint_fetch = "fetch(base + '/api/replay/evidence-dashboard')"

    assert script.count(endpoint_fetch) == 1
    assert "card.replay_rows" in script
    assert "payload.lottery_cards" in script
    assert "method:" not in script


def test_coverage_change_stays_no_db_non_mutating_and_non_predictive() -> None:
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
