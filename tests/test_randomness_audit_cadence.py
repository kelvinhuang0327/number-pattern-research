"""Cadence contract for the real existing-logic randomness audit.

The gate is anchored only to a real executable audit and to an independent
canonical DB population.  Human or timestamp-only re-attestation is legacy
metadata and resets neither the 14-day nor the 50-new-draw trigger.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import randomness_audit as audit


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_results.json"
SUMMARY_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
WIKI_PATH = REPO_ROOT / "wiki" / "system" / "randomness_final_verdict.md"


def _draws(count: int) -> list[dict]:
    return [
        {
            "draw": f"115{index:06d}",
            "date": f"2026-01-{((index - 1) % 28) + 1:02d}",
            "numbers": [1, 8, 15, 22, 29, 36],
            "special": 7,
        }
        for index in range(count, 0, -1)
    ]


def _population(draws: list[dict]) -> audit.PopulationLoad:
    stream_hash = audit._sha256_bytes(audit._row_stream_bytes(draws))
    provenance = {
        "selected_row_count": len(draws),
        "selected_row_stream_sha256": stream_hash,
        "newest_selected_row": {
            "draw": draws[0]["draw"],
            "date": draws[0]["date"],
        },
    }
    return audit.PopulationLoad(draws=draws, raw_count=len(draws), provenance=provenance)


def _document(audit_time: datetime, baseline: audit.PopulationLoad) -> dict:
    return {
        "re_attestation_timestamp": "2099-01-01T00:00:00Z",
        "current_executable_audit": {
            "cadence_anchor": {
                "real_executable_audit_timestamp_utc": audit._format_utc(audit_time),
                "canonical_draw_count": len(baseline.draws),
                "selected_row_stream_sha256": baseline.provenance[
                    "selected_row_stream_sha256"
                ],
                "newest_selected_row": baseline.provenance["newest_selected_row"],
            },
            "cadence_policy": {
                "max_calendar_days": audit.CADENCE_MAX_CALENDAR_DAYS,
                "max_new_canonical_draws": audit.CADENCE_MAX_NEW_DRAWS,
                "trigger": "whichever_occurs_first",
                "timestamp_only_re_attestation_is_gating": False,
            },
            "input_provenance": baseline.provenance,
        },
    }


@pytest.fixture
def baseline() -> audit.PopulationLoad:
    return _population(_draws(100))


def test_policy_constants_are_owner_approved_values():
    assert audit.CADENCE_MAX_CALENDAR_DAYS == 14
    assert audit.CADENCE_MAX_NEW_DRAWS == 50


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-07-18T08:00:00Z", datetime(2026, 7, 18, 8, tzinfo=timezone.utc)),
        ("2026-07-18T16:00:00+08:00", datetime(2026, 7, 18, 8, tzinfo=timezone.utc)),
    ],
)
def test_parse_utc_timestamp_normalizes_offsets(raw: str, expected: datetime):
    assert audit._parse_utc_timestamp(raw, field_name="test") == expected


@pytest.mark.parametrize("raw", ["", "not-a-date", "2026-07-18T08:00:00"])
def test_parse_utc_timestamp_fails_closed_on_malformed_or_naive(raw: str):
    with pytest.raises(audit.AuditProvenanceError):
        audit._parse_utc_timestamp(raw, field_name="test")


def test_calendar_trigger_not_due_one_second_before_14_days(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        baseline,
        audit_time + timedelta(days=14) - timedelta(seconds=1),
    )
    assert result["status"] == "CURRENT"
    assert result["calendar_due"] is False


def test_calendar_trigger_due_exactly_at_14_days(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        baseline,
        audit_time + timedelta(days=14),
    )
    assert result["status"] == "DUE"
    assert result["trigger"] == "CALENDAR"
    assert result["calendar_due"] is True


def test_draw_trigger_not_due_at_49_new_canonical_draws(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    current = _population(_draws(149))
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        current,
        audit_time + timedelta(days=1),
    )
    assert result["status"] == "CURRENT"
    assert result["new_canonical_draws"] == 49
    assert result["draw_due"] is False


def test_draw_trigger_due_at_50_new_canonical_draws(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    current = _population(_draws(150))
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        current,
        audit_time + timedelta(days=1),
    )
    assert result["status"] == "DUE"
    assert result["trigger"] == "DRAW_COUNT"
    assert result["new_canonical_draws"] == 50


def test_whichever_trigger_occurs_first_is_enough(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    by_draw = audit.evaluate_cadence(
        _document(audit_time, baseline),
        _population(_draws(150)),
        audit_time + timedelta(days=2),
    )
    by_time = audit.evaluate_cadence(
        _document(audit_time, baseline),
        baseline,
        audit_time + timedelta(days=14),
    )
    assert by_draw["due"] is True and by_draw["trigger"] == "DRAW_COUNT"
    assert by_time["due"] is True and by_time["trigger"] == "CALENDAR"


def test_both_triggers_are_reported_when_both_due(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        _population(_draws(150)),
        audit_time + timedelta(days=14),
    )
    assert result["trigger"] == "CALENDAR_AND_DRAW_COUNT"


def test_timestamp_only_reattestation_resets_neither_trigger(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    first = audit.evaluate_cadence(
        document,
        _population(_draws(150)),
        audit_time + timedelta(days=14),
    )
    changed = deepcopy(document)
    changed["re_attestation_timestamp"] = "2200-12-31T23:59:59Z"
    second = audit.evaluate_cadence(
        changed,
        _population(_draws(150)),
        audit_time + timedelta(days=14),
    )
    assert first == second
    assert second["due"] is True


def test_generated_output_cannot_supply_current_draw_count(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    document["current_draw_count"] = 999999
    result = audit.evaluate_cadence(
        document,
        _population(_draws(149)),
        audit_time + timedelta(days=1),
    )
    assert result["new_canonical_draws"] == 49
    assert result["current_draw_source"] == "independent_read_only_canonical_DB_query"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document.pop("current_executable_audit"),
        lambda document: document["current_executable_audit"].pop("cadence_anchor"),
        lambda document: document["current_executable_audit"].pop("input_provenance"),
        lambda document: document["current_executable_audit"]["cadence_anchor"].update(
            {"canonical_draw_count": "100"}
        ),
        lambda document: document["current_executable_audit"]["cadence_anchor"].update(
            {"selected_row_stream_sha256": "bad"}
        ),
        lambda document: document["current_executable_audit"]["cadence_policy"].update(
            {"timestamp_only_re_attestation_is_gating": True}
        ),
    ],
)
def test_missing_or_malformed_provenance_fails_closed(baseline, mutation):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    mutation(document)
    with pytest.raises(audit.AuditProvenanceError):
        audit.evaluate_cadence(document, baseline, audit_time + timedelta(days=1))


def test_changed_historical_row_stream_fails_closed(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    changed_draws = deepcopy(baseline.draws)
    changed_draws[-1]["numbers"] = [2, 9, 16, 23, 30, 37]
    changed = _population(changed_draws)
    with pytest.raises(audit.AuditProvenanceError, match="does not preserve"):
        audit.evaluate_cadence(
            _document(audit_time, baseline),
            changed,
            audit_time + timedelta(days=1),
        )


def test_smaller_current_population_fails_closed(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    with pytest.raises(audit.AuditProvenanceError, match="smaller"):
        audit.evaluate_cadence(
            _document(audit_time, baseline),
            _population(_draws(99)),
            audit_time + timedelta(days=1),
        )


def test_implausibly_future_real_audit_timestamp_fails_closed(baseline):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(now + timedelta(hours=25), baseline)
    with pytest.raises(audit.AuditProvenanceError, match="future"):
        audit.evaluate_cadence(document, baseline, now)


def test_committed_artifact_anchors_to_real_executable_audit():
    document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    current = document["current_executable_audit"]
    anchor = current["cadence_anchor"]
    provenance = current["input_provenance"]
    assert anchor["real_executable_audit_timestamp_utc"] == current["executed_at_utc"]
    assert anchor["canonical_draw_count"] == provenance["selected_row_count"]
    assert anchor["selected_row_stream_sha256"] == provenance["selected_row_stream_sha256"]
    assert current["cadence_policy"] == {
        "max_calendar_days": 14,
        "max_new_canonical_draws": 50,
        "trigger": "whichever_occurs_first",
        "timestamp_only_re_attestation_is_gating": False,
    }


def test_committed_real_audit_calendar_gate_is_current():
    document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    timestamp = document["current_executable_audit"]["cadence_anchor"][
        "real_executable_audit_timestamp_utc"
    ]
    audit_time = audit._parse_utc_timestamp(
        timestamp,
        field_name="real_executable_audit_timestamp_utc",
    )
    age = datetime.now(timezone.utc) - audit_time
    assert age < timedelta(days=14), (
        f"real executable randomness audit is due by calendar cadence: age={age}"
    )


def test_summary_timestamp_matches_committed_cadence_anchor():
    document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    expected = document["current_executable_audit"]["executed_at_utc"]
    assert f"**Current executable audit timestamp (UTC):** {expected}" in summary


def test_wiki_policy_routes_to_real_execution_and_both_triggers():
    wiki = WIKI_PATH.read_text(encoding="utf-8")
    lowered = wiki.lower()
    assert "14 calendar days" in lowered
    assert "50 new canonical" in lowered
    assert "whichever occurs first" in lowered
    assert "timestamp-only re-attestation" in lowered
    assert "scripts/randomness_audit.py" in wiki
    assert "P246K" in wiki
