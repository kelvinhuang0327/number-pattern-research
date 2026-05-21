"""
P18 — Replay UI Timestamp Display Tests.

Verifies that:
- The replay history API returns all timestamp and display fields
- The UI (index.html) renders prediction_cutoff_date and prediction_generated_at
- Legacy fallback text is present in the UI for NULL cutoff date cases
- Metadata backfill label is present for P14D rows (补登 metadata)
- Truth-level badges for P14D/P16 backfill rows are defined in the UI
- No DB writes occur
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT    = Path(__file__).resolve().parents[1]
_LOTTERY_API  = _REPO_ROOT / "lottery_api"
_PROD_DB      = _LOTTERY_API / "data" / "lottery_v2.db"
_INDEX_HTML   = _REPO_ROOT / "index.html"
_P18_OUTPUT   = _REPO_ROOT / "outputs" / "replay" / "p18_replay_ui_timestamp_display_20260520.json"

sys.path.insert(0, str(_LOTTERY_API))
from routes.replay import get_replay_history  # noqa: E402

PROD_ROWS     = 9460  # updated post-P20 apply
STRATEGIES  = ["ts3_regime_3bet", "biglotto_triple_strike", "biglotto_deviation_2bet"]
P14D_APPLY_ID = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
P16_APPLY_ID  = "P16_BIGLOTTO_REMAINING_1500_PROD_20260520"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _history(strategy_id, page=1, page_size=5):
    return _run(get_replay_history(
        lottery_type="BIG_LOTTO",
        strategy_id=strategy_id,
        replay_status=None, lifecycle_status=None,
        fixture_mode=False, date_from=None, date_to=None,
        page=page, page_size=page_size,
    ))


@pytest.fixture(scope="module")
def html() -> str:
    assert _INDEX_HTML.exists()
    return _INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def output() -> dict:
    assert _P18_OUTPUT.exists()
    return json.loads(_P18_OUTPUT.read_text())


@pytest.fixture(scope="module")
def ts3_records() -> list:
    return _history("ts3_regime_3bet")["records"]


@pytest.fixture(scope="module")
def triple_records() -> list:
    return _history("biglotto_triple_strike")["records"]


# ── output JSON tests ─────────────────────────────────────────────────────────

def test_output_exists():
    assert _P18_OUTPUT.exists()


def test_output_phase(output: dict):
    assert output["phase"] == "P18_REPLAY_UI_TIMESTAMP_DISPLAY"


def test_output_production_rows(output: dict):
    # P18 output snapshot captured pre-P19B; value may be lower than current live count
    assert output["production_rows"] >= 4960


def test_output_api_timestamp_fields_present(output: dict):
    assert output["api_timestamp_fields_present"] is True


def test_output_ui_timestamp_display_ready(output: dict):
    assert output["ui_timestamp_display_ready"] is True


def test_output_no_db_write(output: dict):
    assert output["no_db_write"] is True


def test_output_fake_success_zero(output: dict):
    assert output["fake_success_count"] == 0


def test_output_classification(output: dict):
    assert output["final_classification"] == "P18_REPLAY_UI_TIMESTAMP_DISPLAY_READY"


# ── API field tests ───────────────────────────────────────────────────────────

# 1. API response includes prediction_cutoff_date
@pytest.mark.parametrize("strategy_id", STRATEGIES)
def test_api_includes_prediction_cutoff_date(strategy_id):
    r = _history(strategy_id)
    assert r["records"], f"No records for {strategy_id}"
    assert "prediction_cutoff_date" in r["records"][0]


# 2. API response includes prediction_generated_at
@pytest.mark.parametrize("strategy_id", STRATEGIES)
def test_api_includes_prediction_generated_at(strategy_id):
    r = _history(strategy_id)
    assert "prediction_generated_at" in r["records"][0]


# 3. ts3_regime_3bet records have non-NULL cutoff (post-P17B)
def test_ts3_cutoff_date_populated(ts3_records):
    for rec in ts3_records:
        assert rec["prediction_cutoff_date"] is not None, \
            f"draw={rec['target_draw']}: cutoff_date should be populated after P17B"


# 4. ts3_regime_3bet records have non-NULL generated_at (post-P17B)
def test_ts3_generated_at_populated(ts3_records):
    for rec in ts3_records:
        assert rec["prediction_generated_at"] is not None


# 5. P16 records have non-NULL cutoff
def test_p16_cutoff_date_populated(triple_records):
    p16_recs = [r for r in triple_records
                if r.get("controlled_apply_id") == P16_APPLY_ID]
    for rec in p16_recs:
        assert rec["prediction_cutoff_date"] is not None


# 6. truth_level field present in all records
@pytest.mark.parametrize("strategy_id", STRATEGIES)
def test_api_includes_truth_level(strategy_id):
    r = _history(strategy_id)
    for rec in r["records"]:
        assert "truth_level" in rec


# 7. display_status present
@pytest.mark.parametrize("strategy_id", STRATEGIES)
def test_api_includes_display_status(strategy_id):
    r = _history(strategy_id)
    for rec in r["records"]:
        assert rec.get("display_status") == "SHOW_REPLAY_RESULT"


# ── UI (index.html) rendering tests ──────────────────────────────────────────

# 3. UI data model accepts prediction_cutoff_date — renders 預測基準日
def test_ui_renders_cutoff_date_field(html: str):
    assert "prediction_cutoff_date" in html, \
        "index.html must reference prediction_cutoff_date"
    assert "預測基準日" in html, \
        "index.html must render 預測基準日 label"


# 4. UI data model accepts prediction_generated_at — renders 建立時間
def test_ui_renders_generated_at_field(html: str):
    assert "prediction_generated_at" in html, \
        "index.html must reference prediction_generated_at"
    assert "建立時間" in html, \
        "index.html must render 建立時間 label"


# 5. Rows with cutoff date render 預測基準日 label (already verified above)
def test_ui_cutoff_badge_label_in_html(html: str):
    assert "rp-ts-cutoff" in html, "CSS class rp-ts-cutoff must be defined"


# 6. Rows with NULL cutoff render 預測基準日未知（legacy）
def test_ui_legacy_fallback_label_in_html(html: str):
    assert "預測基準日未知（legacy）" in html, \
        "index.html must include legacy fallback text for NULL cutoff"


# 7. Rows with generated_at render 建立時間 label (verified above)
def test_ui_generated_at_badge_label_in_html(html: str):
    assert "rp-ts-genat" in html or "建立時間" in html


# 8. Metadata backfill rows render metadata label
def test_ui_metadata_backfill_label_in_html(html: str):
    assert "補登 metadata" in html, \
        "index.html must include '補登 metadata' label for P14D backfill rows"
    assert "rp-metadata-backfill-label" in html, \
        "CSS class rp-metadata-backfill-label must be defined"


# 9. existing hit_count display still works
def test_ui_hit_count_display_intact(html: str):
    assert "hit_count" in html, "hit_count must still be used in index.html"
    assert "命中" in html


# 10. Truth-level badge for BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED defined
def test_ui_p14d_truth_badge_defined(html: str):
    assert "BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED" in html, \
        "index.html must define truth badge for BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED"
    assert "BIG LOTTO BACKFILL" in html


# 11. Truth-level badge for BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED defined
def test_ui_p16_truth_badge_defined(html: str):
    assert "BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED" in html, \
        "index.html must define truth badge for BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"
    assert "BIG LOTTO BACKFILL (P16)" in html


# DB and production safety ────────────────────────────────────────────────────

def test_production_rows_4960():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS


def test_no_db_writes():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS
