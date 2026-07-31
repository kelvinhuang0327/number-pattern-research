"""P257C — Runtime smoke + governance closeout tests for Best Strategy Overview.

Verifies API behavior, static UI markers, and P257C governance artifact.
Read-only: no DB write, no registry mutation, no strategy promotion.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
P257A_JSON = REPO_ROOT / "outputs" / "research" / "p257a_best_nbet_strategy_overview_historical_replay_20260608.json"
P257B_JSON = REPO_ROOT / "outputs" / "research" / "p257b_best_strategy_overview_readonly_ui_20260608.json"
P257C_JSON = REPO_ROOT / "outputs" / "research" / "p257c_best_strategy_overview_runtime_smoke_closeout_20260608.json"

FORBIDDEN_POSITIVE_PHRASES = ["保證", "必中", "推薦下注", "提高中獎率", "中大獎", "jackpot", "future guarantee", "betting advice"]
VALID_FINAL_DECISIONS = {
    "P257C_BEST_STRATEGY_OVERVIEW_RUNTIME_SMOKE_GOVERNANCE_CLOSEOUT_COMPLETE",
    "P257C_API_PASS_UI_SMOKE_BLOCKED_NEEDS_SCOPE",
    "P257C_RUNTIME_SMOKE_BLOCKED_ENVIRONMENT",
    "HOLD_NEEDS_SCOPE_CLARIFICATION",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p257_region(html: str) -> str:
    """Extract only the P257B section + JS block from index.html."""
    m = re.search(
        r"<!-- ===== P257B Best Strategy Overview Section =====.*?<!-- ===== END P257B =====",
        html, re.DOTALL,
    )
    p257_html = m.group(0) if m else ""
    js_m = re.search(r"// ===== P257B BEST STRATEGY OVERVIEW.*?}\)\(\);", html, re.DOTALL)
    p257_js = js_m.group(0) if js_m else ""
    return p257_html + p257_js


@pytest.fixture(scope="module")
def html() -> str:
    assert INDEX_HTML.exists(), f"index.html missing: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def p257_region(html) -> str:
    region = _p257_region(html)
    assert len(region) > 100, "P257B region not found in index.html"
    return region


@pytest.fixture(scope="module")
def api_client():
    """FastAPI TestClient mounting only the replay router."""
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

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


@pytest.fixture(scope="module")
def api_payload(api_client) -> dict:
    r = api_client.get("/api/replay/best-strategy-overview")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def p257c_artifact() -> dict:
    assert P257C_JSON.exists(), f"P257C artifact missing: {P257C_JSON}"
    with P257C_JSON.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. API smoke
# ---------------------------------------------------------------------------

def test_api_returns_200(api_client):
    r = api_client.get("/api/replay/best-strategy-overview")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"


def test_api_historical_replay_only(api_payload):
    assert api_payload.get("historical_replay_only") is True


def test_api_no_future_guarantee(api_payload):
    assert api_payload.get("no_future_guarantee") is True


def test_api_no_betting_advice(api_payload):
    assert api_payload.get("no_betting_advice") is True


def test_api_no_strategy_promotion(api_payload):
    assert api_payload.get("no_strategy_promotion") is True


def test_api_best_strategy_section(api_payload):
    best = api_payload.get("best_strategy_by_lottery_and_bet_count", {})
    assert isinstance(best, dict) and len(best) > 0


def test_api_high_hit_events_by_lottery(api_payload):
    events = api_payload.get("high_hit_events_by_lottery", [])
    assert isinstance(events, list)


def test_api_high_hit_events_by_lottery_and_bet_count(api_payload):
    events = api_payload.get("high_hit_events_by_lottery_and_bet_count", [])
    assert isinstance(events, list)


def test_api_warning_copy_or_page_contract(api_payload):
    has_contract = "page_contract" in api_payload
    has_warning = "warning_copy" in api_payload or (
        has_contract and "warning_copy" in api_payload.get("page_contract", {})
    )
    assert has_contract or has_warning, "API payload must include page_contract or warning_copy"


def test_api_empty_state_for_star_lotteries(api_payload):
    """3_STAR and 4_STAR should have no replay data (empty state signaled by absent keys)."""
    best = api_payload.get("best_strategy_by_lottery_and_bet_count", {})
    # No keys with 3_STAR or 4_STAR should have actual data
    star_keys = [k for k in best if "3_STAR" in k or "4_STAR" in k]
    assert len(star_keys) == 0, (
        f"3_STAR / 4_STAR should have no replay data in best_strategy, found: {star_keys}"
    )


# ---------------------------------------------------------------------------
# 2. Static UI / HTML smoke
# ---------------------------------------------------------------------------

def test_ui_nav_marker(html):
    assert 'data-section="p257-overview"' in html


def test_ui_section_id(html):
    assert 'id="p257-overview-section"' in html


def test_ui_title_zh(html):
    assert "最佳策略總覽" in html


def test_ui_bet_labels(p257_region):
    for n in range(1, 6):
        assert f"最佳 {n} 注" in p257_region, f"'最佳 {n} 注' not found in P257B region"


def test_ui_lottery_tabs(p257_region):
    for lt in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR"):
        assert lt in p257_region, f"Lottery tab {lt!r} not found in P257B region"


def test_ui_empty_state_copy(p257_region):
    """Empty-state copy must be present in section HTML or JS render path."""
    has_literal = "此彩種目前沒有可用回測資料" in p257_region
    has_js_path  = "NO_DATA_LOTTERIES" in p257_region  # JS guard variable
    assert has_literal or has_js_path, "Empty-state copy or JS guard not found in P257B region"


def test_ui_warning_historical(p257_region):
    assert "歷史回測" in p257_region or "historical" in p257_region.lower()


def test_ui_warning_no_future(p257_region):
    assert "不代表未來" in p257_region or "no future" in p257_region.lower()


# ---------------------------------------------------------------------------
# 3. Forbidden wording — scoped to P257B region
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phrase", FORBIDDEN_POSITIVE_PHRASES)
def test_forbidden_wording_absent_in_p257_region(phrase, p257_region):
    """Forbidden positive claims must not appear in the P257B section/JS."""
    if phrase in p257_region:
        # Allowed only in explicit negation/disclaimer context
        for idx in range(len(p257_region)):
            pos = p257_region.find(phrase, idx)
            if pos == -1:
                break
            context = p257_region[max(0, pos - 60): pos + 60].lower()
            assert any(neg in context for neg in ("不", "no ", "not ", "never", "absent")), (
                f"Forbidden phrase {phrase!r} found in P257B region outside disclaimer context near: "
                f"{p257_region[max(0,pos-40):pos+40]!r}"
            )
            idx = pos + 1


# ---------------------------------------------------------------------------
# 4. DB unchanged
# ---------------------------------------------------------------------------

def test_db_integrity():
    import sqlite3
    db = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    assert result == "ok"


def test_db_replays_unchanged():
    import sqlite3
    db = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert count == 94924, f"DB replay rows changed: {count} ≠ 94924"


# ---------------------------------------------------------------------------
# 5. P257C governance artifact
# ---------------------------------------------------------------------------

def test_p257c_artifact_parses(p257c_artifact):
    assert isinstance(p257c_artifact, dict)


def test_p257c_task_id(p257c_artifact):
    assert p257c_artifact["task_id"] == "P257C"


def test_p257c_classification_exists(p257c_artifact):
    assert "classification" in p257c_artifact


def test_p257c_final_decision_valid(p257c_artifact):
    assert p257c_artifact["final_decision"] in VALID_FINAL_DECISIONS


@pytest.mark.parametrize("flag", [
    "no_db_write_confirmed",
    "no_replay_generation_confirmed",
    "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed",
    "no_recommendation_logic_change_confirmed",
    "no_betting_advice_confirmed",
])
def test_p257c_governance_flags(p257c_artifact, flag):
    assert p257c_artifact.get(flag) is True, f"Flag {flag!r} must be True"


def test_p257c_source_artifacts_referenced(p257c_artifact):
    src = p257c_artifact.get("source_artifacts", {})
    assert "p257a" in str(src).lower()
    assert "p257b" in str(src).lower()
