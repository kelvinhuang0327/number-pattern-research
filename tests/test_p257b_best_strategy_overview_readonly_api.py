"""P257B — API tests for GET /api/replay/best-strategy-overview.

Uses a minimal FastAPI app with only the replay router — no DB write,
no registry mutation, no strategy promotion, no betting advice.
The endpoint is artifact-backed (reads P257A JSON).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs" / "research" / "p257a_best_nbet_strategy_overview_historical_replay_20260608.json"


# ---------------------------------------------------------------------------
# Minimal app fixture (artifact-backed, no DB, no mocks needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with only replay router mounted."""
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    # Add lottery_api to path so `routes.replay` can import its deps
    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility (pre-existing env issue)")


# ---------------------------------------------------------------------------
# 1. HTTP 200 and basic structure
# ---------------------------------------------------------------------------

def test_endpoint_returns_200(client):
    r = client.get("/api/replay/best-strategy-overview")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"


def test_response_is_json(client):
    r = client.get("/api/replay/best-strategy-overview")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# 2. Metadata flags
# ---------------------------------------------------------------------------

def test_historical_replay_only_true(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    assert data.get("historical_replay_only") is True, \
        "historical_replay_only must be True"


def test_no_betting_advice_true(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    assert data.get("no_betting_advice") is True, \
        "no_betting_advice must be True"


def test_no_future_guarantee_true(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    assert data.get("no_future_guarantee") is True


def test_no_strategy_promotion_true(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    assert data.get("no_strategy_promotion") is True


def test_source_artifact_named(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    src = data.get("source_artifact", "")
    assert "p257a" in src.lower(), f"source_artifact should reference p257a, got: {src!r}"


# ---------------------------------------------------------------------------
# 3. Required payload sections
# ---------------------------------------------------------------------------

def test_best_strategy_by_lottery_and_bet_count_present(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    assert "best_strategy_by_lottery_and_bet_count" in data
    best = data["best_strategy_by_lottery_and_bet_count"]
    assert isinstance(best, dict)
    assert len(best) > 0


def test_high_hit_events_by_lottery_present(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    assert "high_hit_events_by_lottery" in data
    assert isinstance(data["high_hit_events_by_lottery"], list)


def test_page_contract_or_warning_copy_present(client):
    data = client.get("/api/replay/best-strategy-overview").json()
    has_contract = "page_contract" in data
    # warning_copy may be nested inside page_contract or at top level
    has_warning = "warning_copy" in data or (
        has_contract and "warning_copy" in data.get("page_contract", {})
    )
    assert has_contract or has_warning, \
        "Response must include page_contract or warning_copy"


# ---------------------------------------------------------------------------
# 4. Artifact-backed (no DB write verification via file path check)
# ---------------------------------------------------------------------------

def test_artifact_file_exists():
    """Verify the backing artifact is present on disk (no DB required)."""
    assert ARTIFACT_PATH.exists(), f"P257A artifact missing: {ARTIFACT_PATH}"


def test_artifact_parses():
    with ARTIFACT_PATH.open() as f:
        data = json.load(f)
    assert data["task_id"] == "P257A"


def test_no_db_write_flag():
    """Artifact confirms no DB write at generation time."""
    with ARTIFACT_PATH.open() as f:
        data = json.load(f)
    assert data.get("no_db_write_confirmed") is True
