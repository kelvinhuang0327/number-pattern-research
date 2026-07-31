"""Tests for the P537B read-only shortlist robustness review artifact route."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottery_api.routes import replay

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "outputs/research/p537a_shortlist_robustness_review_20260709.json"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(replay.router)
    return TestClient(app)


def test_route_serves_200_and_reuses_committed_artifact():
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    response = _client().get("/api/replay/shortlist-robustness-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_version"] == data["schema_version"]
    assert payload["task_id"] == data["task_id"]
    assert payload["extends_task_id"] == data["extends_task_id"]
    assert payload["upstream_task_id"] == data["upstream_task_id"]
    assert payload["generated_at"] == data["generated_at"]
    assert payload["classification"] == data["classification"]
    assert payload["source_artifact"] == ARTIFACT.name


def test_route_exposes_disclaimer_and_flags():
    response = _client().get("/api/replay/shortlist-robustness-review")
    payload = response.json()

    assert payload["disclaimer"] == (
        "Historical replay review artifact only; not a prediction, "
        "betting edge, future-winning, or production-readiness claim."
    )
    assert payload["historical_replay_only"] is True
    assert payload["no_future_guarantee"] is True
    assert payload["no_betting_advice"] is True
    assert payload["no_strategy_promotion"] is True


def test_counts_match_section_lengths_verbatim():
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    response = _client().get("/api/replay/shortlist-robustness-review")
    payload = response.json()

    section_keys = [
        "stable_candidates_for_owner_review",
        "short_window_spike_caution_list",
        "combination_candidates_for_followup",
        "cross_lottery_candidates_for_followup",
        "insufficient_or_ambiguous_candidates",
    ]
    for key in section_keys:
        assert payload["counts"][key] == len(data[key])
        assert payload[key] == data[key]


def test_provenance_and_limits_passed_through_verbatim():
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    response = _client().get("/api/replay/shortlist-robustness-review")
    payload = response.json()

    assert payload["provenance_and_limits"] == data["provenance_and_limits"]


def test_route_does_not_open_sqlite_or_recompute(monkeypatch):
    """The route must only read the committed JSON artifact — no DB, no recompute."""
    import sqlite3

    def _fail_connect(*args, **kwargs):
        raise AssertionError("route must not open a sqlite3 connection")

    monkeypatch.setattr(sqlite3, "connect", _fail_connect)

    response = _client().get("/api/replay/shortlist-robustness-review")
    assert response.status_code == 200


def test_missing_artifact_returns_clear_error(monkeypatch):
    monkeypatch.setattr(
        replay,
        "_SHORTLIST_ROBUSTNESS_REVIEW_PATH",
        REPO_ROOT / "outputs/research/does-not-exist.json",
    )

    response = _client().get("/api/replay/shortlist-robustness-review")
    assert response.status_code == 500
    assert "not found" in response.json()["detail"]
