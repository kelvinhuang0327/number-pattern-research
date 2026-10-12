"""Tests for P251E evidence dashboard API runtime smoke and governance closure."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(LOTTERY_API))

import app as app_module  # noqa: E402
from routes import replay  # noqa: E402
from analysis import p251e_evidence_dashboard_api_runtime_smoke_governance_closure as p251e  # noqa: E402


JSON_PATH = REPO_ROOT / "outputs" / "research" / "p251e_evidence_dashboard_api_runtime_smoke_governance_closure_20260606.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p251e_evidence_dashboard_api_runtime_smoke_governance_closure_20260606.md"
P251B_PATH = REPO_ROOT / "outputs" / "research" / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"


def test_runtime_route_returns_p251b_payload_via_app_client():
    expected = json.loads(P251B_PATH.read_text(encoding="utf-8"))
    with TestClient(app_module.app) as client:
        response = client.get("/api/replay/evidence-dashboard")

    assert response.status_code == 200
    assert response.json() == expected


def test_response_semantics_preserved():
    payload = replay._load_evidence_dashboard_payload()

    assert len(payload["strategy_rows"]) >= 41
    assert sum(1 for row in payload["strategy_rows"] if row["artifact_only_flag"]) == 3
    assert payload["default_filter_state"]["enabled_lifecycle_statuses"] == p251e.REQUIRED_STATUSES
    assert payload["default_filter_state"]["exclude_by_lifecycle"] is False

    big_lotto = next(card for card in payload["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")
    assert big_lotto["replay_rows"] == 24_140
    assert big_lotto["draw_rows"] == 22_238
    assert big_lotto["canonical_rows"] == 2_113
    assert payload["global_summary"]["big_lotto_add_on_rows"] == 19_100
    assert payload["global_summary"]["no_deployable_candidate"] is True
    assert "not betting advice" in payload["no_betting_advice_notice"]["message"].lower()


def test_route_is_artifact_backed_and_db_free_by_source_scan():
    scan = p251e._scan_route_for_no_db_query()

    assert scan["route_returns_loader_only"] is True
    assert scan["loader_reads_json_only"] is True
    assert scan["loader_uses_db_terms"] is False


def test_governance_files_record_p251d_and_p251e():
    updates = p251e._governance_updates()

    assert updates["arc_closed"] is True
    assert all(updates["required_terms_present"].values())


def test_p251e_artifact_builder_and_parse():
    p251e.main()
    assert JSON_PATH.exists()
    assert MD_PATH.exists()

    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD_PATH.read_text(encoding="utf-8")

    assert report["task_id"] == "P251E"
    assert report["classification"] == "EVIDENCE_DASHBOARD_API_RUNTIME_SMOKE_GOVERNANCE_CLOSURE"
    assert report["runtime_route_smoke"]["status"] == "PASS"
    assert report["runtime_route_smoke"]["status_code"] == 200
    assert report["runtime_route_smoke"]["response_equals_p251b_artifact"] is True
    assert report["response_contract_validation"]["strategy_rows_len_ok"] is True
    assert report["response_contract_validation"]["artifact_only_visible_count_ok"] is True
    assert report["response_contract_validation"]["default_lifecycle_statuses_ok"] is True
    assert report["response_contract_validation"]["big_lotto_semantics_ok"] is True
    assert report["no_db_write_confirmed"] is True
    assert report["no_registry_mutation_confirmed"] is True
    assert report["no_strategy_promotion_confirmed"] is True
    assert report["no_ui_implementation_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
    assert "Runtime route smoke result" in md
    assert "P251A-D arc closure summary" in md
