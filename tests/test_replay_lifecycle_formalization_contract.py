from __future__ import annotations

import json
from pathlib import Path

from lottery_api.models.replay_lifecycle_contract import (
    FORMAL_LIFECYCLE_STATES,
    PRODUCTION_APPLY_FORBIDDEN_STATES,
    can_production_apply,
    canonicalize_formal_lifecycle_status,
)
from scripts import generate_p1_lifecycle_formalization_fixture as fixture_gen


def test_formal_lifecycle_enum_has_seven_states():
    assert FORMAL_LIFECYCLE_STATES == (
        "PRODUCTION",
        "WATCHING",
        "PROVISIONAL",
        "REJECTED",
        "OFFLINE",
        "EXPERIMENTAL",
        "UNKNOWN",
    )
    assert len(FORMAL_LIFECYCLE_STATES) == 7


def test_formal_lifecycle_enum_is_strictly_normalized():
    for state in FORMAL_LIFECYCLE_STATES:
        assert canonicalize_formal_lifecycle_status(state) == state
    assert canonicalize_formal_lifecycle_status("not-a-state") == "UNKNOWN"
    assert canonicalize_formal_lifecycle_status(None) == "UNKNOWN"


def test_production_apply_permissions():
    assert can_production_apply("PRODUCTION") is True
    assert can_production_apply("ONLINE") is True
    assert can_production_apply("ACTIVE") is True
    for state in PRODUCTION_APPLY_FORBIDDEN_STATES:
        assert can_production_apply(state) is False


def test_fixture_builder_contains_all_formal_states():
    fixture = fixture_gen.build_fixture()
    assert fixture["fixture_name"] == "p1_lifecycle_formalization_fixture"
    assert fixture["fixture_version"] == "p1_20260517"
    assert fixture["synthetic_only"] is True
    assert fixture["fixture_only"] is True
    assert fixture["production_db_write"] is False
    assert fixture["backfill"] is False
    assert fixture["promotion_action"] is False
    assert fixture["strategy_count"] == 7
    assert fixture["lifecycle_counts"] == {
        "PRODUCTION": 1,
        "WATCHING": 1,
        "PROVISIONAL": 1,
        "REJECTED": 1,
        "OFFLINE": 1,
        "EXPERIMENTAL": 1,
        "UNKNOWN": 1,
    }

    records = fixture["records"]
    assert len(records) == 7
    assert {row["lifecycle_status"] for row in records} == set(FORMAL_LIFECYCLE_STATES)
    for row in records:
        assert row["fixture_source"] == "p1_lifecycle_formalization_fixture"
        assert row["governance_marker"] == "P1_LIFECYCLE_FORMALIZATION_FIXTURE_ROW"
        assert row["synthetic_only"] is True
        assert row["fixture_only"] is True
        assert row["prediction_payload"]["numbers"]
        assert row["actual_result_payload"]["numbers"]


def test_fixture_generator_writes_valid_json(tmp_path: Path):
    output = tmp_path / "outputs" / "replay" / "p1_fixture.json"
    rc = fixture_gen.main(["--output", str(output)])
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["markers"][0] == "P1_LIFECYCLE_FORMALIZATION_FIXTURE_READY"
    assert len(payload["records"]) == 7


def test_fixture_generator_source_is_read_only():
    source = Path(fixture_gen.__file__).read_text(encoding="utf-8")
    assert "import sqlite3" not in source
    assert "from sqlite3" not in source
