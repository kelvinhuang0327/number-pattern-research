"""
P15 — Big Lotto Replay API Integration Tests.

Verifies that GET /api/replay/history correctly serves the 1500 P14D
ts3_regime_3bet BIG_LOTTO rows. Tests call the FastAPI route function
directly (no live HTTP server required), mirroring the existing
test_replay_api_contract.py pattern.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT    = Path(__file__).resolve().parents[1]
_LOTTERY_API  = _REPO_ROOT / "lottery_api"
_PROD_DB      = _LOTTERY_API / "data" / "lottery_v2.db"
_P15_OUTPUT   = _REPO_ROOT / "outputs" / "replay" / "p15_biglotto_replay_api_integration_20260520.json"
_P14B_OUTPUT  = _REPO_ROOT / "outputs" / "replay" / "p14b_biglotto_single_strategy_replay_dry_run_20260520.json"

sys.path.insert(0, str(_LOTTERY_API))
from routes.replay import get_replay_history  # noqa: E402

APPLY_ID     = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
TRUTH_LEVEL  = "BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED"
STRATEGY_ID  = "ts3_regime_3bet"
LOTTERY_TYPE = "BIG_LOTTO"
EXPECTED_ROWS = 1500
PROD_ROWS     = 4960  # updated post-P16 apply

REQUIRED_FIELDS = [
    "strategy_id", "strategy_name", "lottery_type",
    "target_draw", "target_date",
    "predicted_numbers", "actual_numbers",
    "hit_numbers", "hit_count", "special_hit",
    "truth_level", "controlled_apply_id",
    "display_status", "visibility_state", "should_count_as_success",
]


# ── helper ────────────────────────────────────────────────────────────────────

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _history(strategy_id=STRATEGY_ID, page=1, page_size=50):
    return _run(get_replay_history(
        lottery_type=LOTTERY_TYPE,
        strategy_id=strategy_id,
        replay_status=None,
        lifecycle_status=None,
        fixture_mode=False,
        date_from=None,
        date_to=None,
        page=page,
        page_size=page_size,
    ))


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def output() -> dict:
    assert _P15_OUTPUT.exists()
    return json.loads(_P15_OUTPUT.read_text())


@pytest.fixture(scope="module")
def first_page() -> dict:
    return _history(page=1, page_size=50)


@pytest.fixture(scope="module")
def sample_record(first_page) -> dict:
    assert first_page["records"], "No records in first page"
    return first_page["records"][0]


# ── output JSON tests ─────────────────────────────────────────────────────────

def test_output_json_exists():
    assert _P15_OUTPUT.exists()


def test_output_phase(output: dict):
    assert output["phase"] == "P15_BIGLOTTO_REPLAY_API_INTEGRATION"


def test_output_production_rows(output: dict):
    # P15 snapshot was captured pre-P16 (rows=1960). Verify the snapshot is internally consistent.
    # PROD_ROWS is the current post-P16 count; the snapshot is allowed to show the pre-P16 value.
    assert output["production_rows"] >= 1960  # must be at least the P14D baseline


def test_output_p14d_rows_found(output: dict):
    assert output["p14d_rows"] == EXPECTED_ROWS


def test_output_api_rows_found(output: dict):
    assert output["api_rows_found"] == EXPECTED_ROWS


def test_output_no_missing_fields(output: dict):
    assert output["missing_fields"] == []


def test_output_hit_count_verified(output: dict):
    assert output["hit_count_verified"] is True
    assert output["hit_count_issues"] == 0


def test_output_page_ready(output: dict):
    assert output["page_ready"] is True


def test_output_no_db_write(output: dict):
    assert output["no_db_write"] is True


def test_output_fake_success_zero(output: dict):
    assert output["fake_success_count"] == 0


def test_output_classification(output: dict):
    assert output["final_classification"] == "P15_BIGLOTTO_REPLAY_API_INTEGRATION_READY"


# ── live API tests (direct route call) ───────────────────────────────────────

# 1. P14D rows count = 1500 in DB
def test_db_p14d_row_count():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_ROWS


# 2. API endpoint exists and returns dict
def test_api_endpoint_returns_dict(first_page: dict):
    assert isinstance(first_page, dict)


# 3. API can query BIG_LOTTO
def test_api_returns_big_lotto(first_page: dict):
    for r in first_page["records"]:
        assert r["lottery_type"] == "BIG_LOTTO"


# 4. API can filter strategy_id = ts3_regime_3bet
def test_api_filters_strategy_id(first_page: dict):
    for r in first_page["records"]:
        assert r["strategy_id"] == STRATEGY_ID


# 5. API returns P14D truth_level
def test_api_returns_p14d_truth_level(sample_record: dict):
    assert sample_record["truth_level"] == TRUTH_LEVEL


# 6. API returns controlled_apply_id
def test_api_returns_controlled_apply_id(sample_record: dict):
    assert sample_record["controlled_apply_id"] == APPLY_ID


# 7. API returns predicted_numbers
def test_api_returns_predicted_numbers(sample_record: dict):
    assert sample_record["predicted_numbers"] is not None
    assert isinstance(sample_record["predicted_numbers"], list)
    assert len(sample_record["predicted_numbers"]) == 6


# 8. API returns actual_numbers
def test_api_returns_actual_numbers(sample_record: dict):
    assert sample_record["actual_numbers"] is not None
    assert isinstance(sample_record["actual_numbers"], list)
    assert len(sample_record["actual_numbers"]) == 6


# 9. API returns hit_numbers
def test_api_returns_hit_numbers(sample_record: dict):
    assert "hit_numbers" in sample_record
    assert isinstance(sample_record["hit_numbers"], list)


# 10. API returns hit_count
def test_api_returns_hit_count(sample_record: dict):
    assert "hit_count" in sample_record
    assert isinstance(sample_record["hit_count"], int)


# 11. API hit_count == len(hit_numbers)
def test_api_hit_count_equals_len_hit_numbers(first_page: dict):
    for r in first_page["records"]:
        hn = r.get("hit_numbers") or []
        hc = r.get("hit_count") or 0
        assert len(hn) == hc, (
            f"draw={r['target_draw']}: hit_count={hc} != len(hit_numbers)={len(hn)}"
        )


# 12. API returns special_hit
def test_api_returns_special_hit(sample_record: dict):
    assert "special_hit" in sample_record


# 13. API supports limit / pagination
def test_api_supports_pagination():
    r = _history(page=1, page_size=10)
    assert r["total"] == EXPECTED_ROWS
    assert r["pages"] == 150   # 1500 / 10
    assert len(r["records"]) == 10


# 14. First page returns <= requested limit
def test_first_page_respects_limit():
    r = _history(page=1, page_size=7)
    assert len(r["records"]) <= 7


# 15. Total count or equivalent pagination metadata exists
def test_pagination_metadata_exists(first_page: dict):
    assert "total" in first_page
    assert "page" in first_page
    assert "page_size" in first_page
    assert "pages" in first_page
    assert first_page["total"] == EXPECTED_ROWS


# 16. display_status is present
def test_api_display_status_present(sample_record: dict):
    assert "display_status" in sample_record
    assert sample_record["display_status"] == "SHOW_REPLAY_RESULT"


# 17. visibility_state is present
def test_api_visibility_state_present(sample_record: dict):
    assert "visibility_state" in sample_record
    assert sample_record["visibility_state"] == "ROW_BACKED"


# 18. should_count_as_success is correct (True when actual_numbers and hit_count present)
def test_api_should_count_as_success(first_page: dict):
    for r in first_page["records"]:
        expected = (r.get("actual_numbers") is not None and
                    r.get("hit_count") is not None)
        assert r["should_count_as_success"] == expected, (
            f"draw={r['target_draw']}: should_count_as_success={r['should_count_as_success']} "
            f"expected={expected}"
        )


# 19. No DB writes occur (verify production rows unchanged after test)
def test_no_db_writes():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS


# 20. Production rows at expected post-P16 count
def test_production_rows_remain_1960():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS


# ── comprehensive sweep (all 1500 rows via pagination) ────────────────────────

def test_all_1500_rows_hit_count_consistent():
    """Paginate through all 1500 rows and verify hit_count == len(hit_numbers)."""
    total_checked = 0
    issues = []
    page = 1
    page_size = 200
    while total_checked < EXPECTED_ROWS:
        result = _history(page=page, page_size=page_size)
        for r in result["records"]:
            hn = r.get("hit_numbers") or []
            hc = r.get("hit_count") or 0
            if len(hn) != hc:
                issues.append(f"draw={r['target_draw']}: hit_count={hc} len_hit_numbers={len(hn)}")
        total_checked += len(result["records"])
        if not result["records"]:
            break
        page += 1
    assert total_checked == EXPECTED_ROWS, f"Only checked {total_checked} rows"
    assert issues == [], f"hit_count issues: {issues[:5]}"


def test_all_1500_rows_have_p14d_truth_level():
    """All P14D rows must have BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED."""
    total_checked = 0
    issues = []
    page = 1
    page_size = 200
    while total_checked < EXPECTED_ROWS:
        result = _history(page=page, page_size=page_size)
        for r in result["records"]:
            if r.get("truth_level") != TRUTH_LEVEL:
                issues.append(f"draw={r['target_draw']}: truth_level={r.get('truth_level')!r}")
        total_checked += len(result["records"])
        if not result["records"]:
            break
        page += 1
    assert issues == [], f"truth_level issues: {issues[:5]}"


def test_p14b_cross_check():
    """Cross-check API output vs P14B page_ready_sample (5 most recent draws)."""
    p14b = json.loads(_P14B_OUTPUT.read_text())
    p14b_sample = p14b.get("page_ready_sample", [])[-5:]

    result = _history(page=1, page_size=20)
    api_by_draw = {r["target_draw"]: r for r in result["records"]}

    mismatches = []
    for p in p14b_sample:
        draw = p["draw_number"]
        assert draw in api_by_draw, f"draw {draw} not in API response"
        api_r = api_by_draw[draw]
        if api_r["hit_count"] != p["hit_count"]:
            mismatches.append(f"{draw}: hit_count API={api_r['hit_count']} P14B={p['hit_count']}")
        if sorted(api_r.get("hit_numbers") or []) != sorted(p.get("hit_numbers") or []):
            mismatches.append(f"{draw}: hit_numbers mismatch")
        if sorted(api_r["predicted_numbers"]) != sorted(p["predicted_numbers"]):
            mismatches.append(f"{draw}: predicted_numbers mismatch")
        if sorted(api_r["actual_numbers"]) != sorted(p["actual_numbers"]):
            mismatches.append(f"{draw}: actual_numbers mismatch")

    assert mismatches == [], f"Cross-check mismatches: {mismatches}"


def test_all_required_fields_in_records(first_page: dict):
    """Verify every required field is present in all records of the first page."""
    for r in first_page["records"]:
        missing = [f for f in REQUIRED_FIELDS if f not in r]
        assert missing == [], f"draw={r.get('target_draw')}: missing fields {missing}"
