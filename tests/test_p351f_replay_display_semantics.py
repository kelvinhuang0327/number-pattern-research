"""P351F replay display semantics.

Display-only regression coverage:
- REJECTED detail is capped to the latest 300 periods and remains paginated.
- V2 artifact reconstructed rows expose row-level retrospective display labels.
- RETIRED zero-row strategies remain tombstones.
- OBSERVATION zero-row strategies remain visible with NO_DATA semantics.
- Replay UI/API copy avoids forbidden betting-promotion language.

READ-ONLY. No DB writes, no backfill, no registry mutation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

V2_STRATEGIES = [
    ("BIG_LOTTO", "biglotto_ts3_acb_4bet", 4),
    ("BIG_LOTTO", "biglotto_ts3_markov_freq_5bet", 5),
    ("DAILY_539", "p1_deviation_2bet_539", 2),
    ("POWER_LOTTO", "power_shlc_midfreq", 1),
]

FORBIDDEN_DISPLAY_TERMS = (
    "recommended " + "bet",
    "best " + "strategy",
    "increase " + "win rate",
    "推薦" + "投注",
    "最佳" + "策略",
    "提高" + "中獎率",
)


def _html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    if not DB_PATH.exists():
        pytest.skip(f"Replay DB not found: {DB_PATH}")
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from routes import replay as replay_mod

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility")


@pytest.fixture(scope="module")
def rejected_sample(client):
    for lottery_type, strategy_id, bet_index in V2_STRATEGIES:
        resp = client.get(
            "/api/replay/history-detail-grouped"
            f"?lottery_type={lottery_type}&strategy_id={strategy_id}"
            f"&bet_index={bet_index}&page_size=300"
        )
        if resp.status_code == 200 and resp.json().get("total_count", 0) > 0:
            return {
                "lottery_type": lottery_type,
                "strategy_id": strategy_id,
                "bet_index": bet_index,
            }
    pytest.skip("No V2 REJECTED artifact reconstructed replay rows found")


def _grouped_url(sample: dict, **kw) -> str:
    url = (
        "/api/replay/history-detail-grouped"
        f"?lottery_type={sample['lottery_type']}"
        f"&strategy_id={sample['strategy_id']}"
        f"&bet_index={sample['bet_index']}"
    )
    for key, value in kw.items():
        url += f"&{key}={value}"
    return url


def test_rejected_grouped_detail_latest_300_display_depth(client, rejected_sample):
    data = client.get(_grouped_url(rejected_sample, page_size=1500)).json()
    assert data["lifecycle_status"] == "REJECTED"
    assert data["display_depth_policy"] == "LATEST_300_PERIODS_FOR_REJECTED"
    assert data["display_depth_limit"] == 300
    assert data["total_count"] <= 300
    draws = [int(row["target_draw"]) for row in data["rows"]]
    assert draws == sorted(draws, reverse=True)


def test_rejected_artifact_rows_have_row_level_retrospective_badges(client, rejected_sample):
    data = client.get(_grouped_url(rejected_sample, page_size=50)).json()
    assert data["rows"], "fixture should expose rows"
    for row in data["rows"]:
        assert row["truth_level"] == "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
        assert row["display_trust_label"] == "RETROSPECTIVE"
        assert row["display_trust_detail"] == "Artifact Reconstructed"
        assert row["display_trust_is_live"] is False
        for bet in row["bets"]:
            assert bet["truth_level"] == "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
            assert bet["display_trust_label"] == "RETROSPECTIVE"
            assert bet["display_trust_detail"] == "Artifact Reconstructed"
            assert bet["display_trust_is_live"] is False


def test_retired_zero_row_strategies_are_tombstone_only(client):
    data = client.get(
        "/api/replay/history-overview?coverage_mode=true&bet_index=0"
        "&replay_status_category=no_production_replay"
    ).json()
    retired = [
        row for row in data["rows"]
        if row["lifecycle_status"] == "RETIRED" and not row["has_replay_rows"]
    ]
    assert retired, "expected at least one current zero-row RETIRED strategy"
    assert {row["can_open_detail"] for row in retired} == {False}
    assert {row["missing_reason"] for row in retired} == {"retired_no_rows"}


def test_observation_no_rows_remains_visible_as_no_data(client):
    data = client.get("/api/replay/history-overview?coverage_mode=true&bet_index=0").json()
    observation = [row for row in data["rows"] if row["lifecycle_status"] == "OBSERVATION"]
    assert observation, "OBSERVATION strategy must remain visible"
    no_row_observation = [row for row in observation if not row["has_replay_rows"]]
    assert no_row_observation, "current OBSERVATION fixture should have no replay rows"
    assert {row["can_open_detail"] for row in no_row_observation} == {False}
    assert {row["missing_reason"] for row in no_row_observation} == {"observation_no_data"}


def test_index_renders_p351f_badge_and_placeholder_hooks():
    html = _html()
    assert "function trustBadge(" in html
    assert "Artifact Reconstructed" in html
    assert "p351f-trust-badge--artifact" in html
    assert "NO_DATA" in html
    assert "TOMBSTONE" in html
    assert "REJECTED 僅顯示最新 300 期" in html


def test_replay_display_surfaces_avoid_forbidden_language():
    combined = _html() + "\n" + (REPO_ROOT / "lottery_api" / "routes" / "replay.py").read_text(encoding="utf-8")
    lowered = combined.lower()
    for term in FORBIDDEN_DISPLAY_TERMS:
        assert term.lower() not in lowered
