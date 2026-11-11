from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_ui_mock_data_contract import (
    FINAL_MARKER,
    MOCK_DATA_SPEC_MODE,
    validate_strategy_replay_ui_mock_payload,
)


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
MOCK_PAYLOAD_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_ui_mock_api_response.json"


def load_payload() -> dict[str, object]:
    return json.loads(MOCK_PAYLOAD_PATH.read_text(encoding="utf-8"))


def test_valid_mock_payload_passes() -> None:
    payload = load_payload()
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is True
    assert validation["blocker_count"] == 0
    assert payload["mode"] == MOCK_DATA_SPEC_MODE
    assert payload["final_marker"] == FINAL_MARKER


def test_production_ui_true_fails() -> None:
    payload = load_payload()
    payload["production_ui"] = True
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert "production_ui must be false" in validation["blockers"]


def test_missing_mock_warning_fails() -> None:
    payload = load_payload()
    payload["warnings"] = [warning for warning in payload["warnings"] if warning != "Mock-data/spec-only. Not production UI."]
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert any("Mock-data/spec-only. Not production UI." in blocker for blocker in validation["blockers"])


def test_missing_disabled_production_launch_fails() -> None:
    payload = load_payload()
    payload["disabled_actions"] = [action for action in payload["disabled_actions"] if action != "PRODUCTION_LAUNCH"]
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert "disabled_actions must include PRODUCTION_LAUNCH" in validation["blockers"]


def test_source_mode_production_fails() -> None:
    payload = load_payload()
    payload["source_mode"] = "PRODUCTION"
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert "source_mode must be FIXTURE_ONLY or MOCK_ONLY" in validation["blockers"]


def test_runtime_production_enabled_fails() -> None:
    payload = load_payload()
    payload["runtime_production_enablement_allowed"] = True
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert "runtime_production_enablement_allowed must be false" in validation["blockers"]


def test_production_migration_enabled_fails() -> None:
    payload = load_payload()
    payload["production_migration_allowed"] = True
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert "production_migration_allowed must be false" in validation["blockers"]


def test_rows_claiming_production_readiness_fail() -> None:
    payload = load_payload()
    payload["rows"][0]["production_ready"] = True
    validation = validate_strategy_replay_ui_mock_payload(payload)
    assert validation["is_valid"] is False
    assert any("must not claim production readiness" in blocker for blocker in validation["blockers"])


def test_no_production_db_access() -> None:
    payload = load_payload()
    top_level_keys = {str(key).lower() for key in payload.keys()}
    assert "production_db" not in top_level_keys
    assert "db_connection" not in top_level_keys
    assert "database_url" not in top_level_keys
