"""Tests for P251D evidence dashboard read-only API route."""

from __future__ import annotations

import asyncio
import ast
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(LOTTERY_API))

from routes import replay  # noqa: E402
from analysis import p251d_evidence_dashboard_readonly_api_route as p251d  # noqa: E402


JSON_PATH = REPO_ROOT / "outputs" / "research" / "p251d_evidence_dashboard_readonly_api_route_20260606.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p251d_evidence_dashboard_readonly_api_route_20260606.md"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_route_returns_dashboard_payload():
    payload = _run(replay.get_replay_evidence_dashboard())

    assert payload["task_id"] == "P251B"
    assert payload["classification"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT"
    assert "global_summary" in payload
    assert "lottery_cards" in payload
    assert "strategy_rows" in payload
    assert "lifecycle_filter_options" in payload
    assert "no_exclusion_rules" in payload
    assert "no_betting_advice_notice" in payload


def test_semantics_preserved():
    payload = _run(replay.get_replay_evidence_dashboard())

    assert len(payload["strategy_rows"]) >= 41
    assert sum(1 for row in payload["strategy_rows"] if row["artifact_only_flag"]) == 3
    statuses = payload["default_filter_state"]["enabled_lifecycle_statuses"]
    assert statuses == [
        "ONLINE",
        "REJECTED",
        "RETIRED",
        "OBSERVATION",
        "ARTIFACT_ONLY",
        "LIFECYCLE_UNRESOLVED",
    ]
    assert payload["default_filter_state"]["exclude_by_lifecycle"] is False

    big_lotto = next(card for card in payload["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")
    assert big_lotto["replay_rows"] == 24_140
    assert big_lotto["draw_rows"] == 22_238
    assert big_lotto["canonical_rows"] == 2_113
    assert payload["global_summary"]["big_lotto_add_on_rows"] == 19_100


def test_no_overclaim_and_notice_present():
    payload = _run(replay.get_replay_evidence_dashboard())

    assert payload["global_summary"]["no_deployable_candidate"] is True
    assert "not betting advice" in payload["no_betting_advice_notice"]["message"].lower()
    assert payload["global_summary"]["lifecycle_is_label_not_exclusion"] is True


def test_missing_artifact_raises_project_style_error(monkeypatch):
    missing = REPO_ROOT / "outputs" / "research" / "__missing_p251b_dashboard.json"
    monkeypatch.setattr(replay, "_EVIDENCE_DASHBOARD_PATH", missing)

    with pytest.raises(HTTPException) as exc_info:
        _run(replay.get_replay_evidence_dashboard())

    assert exc_info.value.status_code == 500
    assert "artifact not found" in str(exc_info.value.detail)


def test_route_source_does_not_import_write_or_controlled_apply_utilities():
    source = (REPO_ROOT / "lottery_api" / "routes" / "replay.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported.extend(f"{base}:{alias.name}" for alias in node.names)

    forbidden_terms = ["controlled_apply", "alembic", "shutil", "subprocess"]
    for name in imported:
        assert not any(term in name for term in forbidden_terms), name


def test_p251d_artifact_builder_and_parse():
    p251d.main()
    assert JSON_PATH.exists()
    assert MD_PATH.exists()

    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD_PATH.read_text(encoding="utf-8")

    assert report["task_id"] == "P251D"
    assert report["classification"] == "EVIDENCE_DASHBOARD_READONLY_API_ROUTE_IMPLEMENTED"
    assert report["implemented_endpoint"]["path"] == "/api/replay/evidence-dashboard"
    assert report["no_db_write_confirmed"] is True
    assert report["no_registry_mutation_confirmed"] is True
    assert report["no_strategy_promotion_confirmed"] is True
    assert report["no_ui_implementation_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
    assert "Implemented Endpoint" in md
    assert "No-Overclaim / No-Betting Notice" in md
