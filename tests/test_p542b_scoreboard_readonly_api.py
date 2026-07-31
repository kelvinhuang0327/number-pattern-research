"""Focused, artifact-only tests for the P542B scoreboard endpoint."""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottery_api.routes import p542b_scoreboard as scoreboard

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(scoreboard.router)
    return TestClient(app)


def test_scoreboard_endpoint_returns_committed_artifact_metadata() -> None:
    original = scoreboard._ARTIFACT_PATH.read_bytes()

    response = _client().get("/api/research/p542a/scoreboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["task"] == "P542A"
    assert payload["descriptive_only"] is True
    assert payload["source_artifact"] == (
        "outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json"
    )
    assert payload["artifact_sha256"] == hashlib.sha256(original).hexdigest()
    assert payload["artifact_bytes"] == len(original)
    assert payload["data"]["task_id"] == "P542A"
    assert scoreboard._ARTIFACT_PATH.read_bytes() == original


def test_missing_artifact_returns_safe_non_500_error(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(scoreboard, "_ARTIFACT_PATH", tmp_path / "missing.json")

    response = _client().get("/api/research/p542a/scoreboard")

    assert response.status_code == 404
    assert response.json()["detail"] == "P542A scoreboard artifact is not available."


def test_invalid_artifact_returns_safe_non_500_error(
    monkeypatch, tmp_path: Path
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(scoreboard, "_ARTIFACT_PATH", invalid)

    response = _client().get("/api/research/p542a/scoreboard")

    assert response.status_code == 422
    assert response.json()["detail"] == "P542A scoreboard artifact is not valid JSON."


def test_p542b_code_has_no_data_store_dependency() -> None:
    route_source = Path(scoreboard.__file__).read_text(encoding="utf-8").lower()
    test_source = Path(__file__).read_text(encoding="utf-8").lower()
    forbidden = ("sql" + "ite3", "database" + "manager", "con" + "nect(")
    for token in forbidden:
        assert token not in route_source
        assert token not in test_source


def test_main_app_registers_the_p542b_router() -> None:
    app_source = (REPO_ROOT / "lottery_api" / "app.py").read_text(encoding="utf-8")
    assert "p542b_scoreboard.router" in app_source
    assert '"/api/research/p542a/scoreboard"' in Path(scoreboard.__file__).read_text(
        encoding="utf-8"
    )
