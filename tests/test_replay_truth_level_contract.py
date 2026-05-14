"""
test_replay_truth_level_contract.py
====================================
Post-V3 truth-level API contract tests.

Validates that /api/replay/history exposes correct truth_level, controlled_apply_id,
source, and provenance_hash for V1/V2/legacy rows, and that V1 controlled rows appear
on page 1 (not masked by legacy rows).

READ-ONLY. No DB writes. No replay generation.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(LOTTERY_API))

from routes.replay import get_replay_history

DB_PATH = LOTTERY_API / "data" / "lottery_v2.db"

V1_APPLY_ID = "20260514033100-13acaf34996e"
V2_APPLY_ID = "20260514134953-cf683424"

V1_STRATEGIES = [
    ("BIG_LOTTO", "biglotto_deviation_2bet"),
    ("BIG_LOTTO", "biglotto_triple_strike"),
    ("DAILY_539", "daily539_f4cold"),
    ("DAILY_539", "daily539_markov_cold"),
    ("POWER_LOTTO", "power_orthogonal_5bet"),
    ("POWER_LOTTO", "power_precision_3bet"),
]

V2_STRATEGIES = [
    ("BIG_LOTTO", "biglotto_ts3_acb_4bet"),
    ("BIG_LOTTO", "biglotto_ts3_markov_freq_5bet"),
    ("DAILY_539", "p1_deviation_2bet_539"),
    ("POWER_LOTTO", "power_shlc_midfreq"),
]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _history(lottery_type: str, strategy_id: str, page: int = 1, page_size: int = 50):
    return _run(get_replay_history(
        lottery_type=lottery_type,
        strategy_id=strategy_id,
        replay_status=None,
        lifecycle_status=None,
        fixture_mode=False,
        date_from=None,
        date_to=None,
        page=page,
        page_size=page_size,
    ))


@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestV1TruthLevelContract:
    """V1 controlled rows must appear on page 1, all with REGENERATED_RETROSPECTIVE."""

    @pytest.mark.parametrize("lottery_type,strategy_id", V1_STRATEGIES)
    def test_v1_page1_all_regenerated_retrospective(self, lottery_type, strategy_id):
        data = _history(lottery_type, strategy_id, page=1)
        records = data["records"]
        assert len(records) > 0, f"{strategy_id}: page 1 must not be empty"
        bad = [r for r in records if r.get("truth_level") != "REGENERATED_RETROSPECTIVE"]
        assert not bad, (
            f"{strategy_id}: {len(bad)}/{len(records)} page-1 records have "
            f"wrong truth_level: {[r.get('truth_level') for r in bad[:3]]}"
        )

    @pytest.mark.parametrize("lottery_type,strategy_id", V1_STRATEGIES)
    def test_v1_page1_has_controlled_apply_id(self, lottery_type, strategy_id):
        data = _history(lottery_type, strategy_id, page=1)
        records = data["records"]
        assert len(records) > 0
        bad = [r for r in records if r.get("controlled_apply_id") != V1_APPLY_ID]
        assert not bad, (
            f"{strategy_id}: page-1 records missing expected controlled_apply_id"
        )

    @pytest.mark.parametrize("lottery_type,strategy_id", V1_STRATEGIES)
    def test_v1_page1_has_source_and_provenance(self, lottery_type, strategy_id):
        data = _history(lottery_type, strategy_id, page=1)
        records = data["records"]
        assert len(records) > 0
        first = records[0]
        assert first.get("source") is not None, f"{strategy_id}: source must not be null for V1"
        assert first.get("provenance_hash") is not None, (
            f"{strategy_id}: provenance_hash must not be null for V1"
        )

    @pytest.mark.parametrize("lottery_type,strategy_id", V1_STRATEGIES)
    def test_v1_records_ordered_by_draw_numeric_desc(self, lottery_type, strategy_id):
        """V1 rows on page 1 must be ordered by numeric draw value DESC (no text-sort bug)."""
        data = _history(lottery_type, strategy_id, page=1)
        draws = [int(r["target_draw"]) for r in data["records"] if r.get("target_draw")]
        assert draws == sorted(draws, reverse=True), (
            f"{strategy_id}: draws not in numeric DESC order — text-sort bug present"
        )


@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestV2TruthLevelContract:
    """V2 rows must all have ARTIFACT_RECONSTRUCTED_RETROSPECTIVE."""

    @pytest.mark.parametrize("lottery_type,strategy_id", V2_STRATEGIES)
    def test_v2_all_artifact_reconstructed(self, lottery_type, strategy_id):
        data = _history(lottery_type, strategy_id, page=1)
        records = data["records"]
        assert len(records) > 0, f"{strategy_id}: must have records"
        bad = [r for r in records if r.get("truth_level") != "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"]
        assert not bad, (
            f"{strategy_id}: {len(bad)} records have wrong truth_level"
        )

    @pytest.mark.parametrize("lottery_type,strategy_id", V2_STRATEGIES)
    def test_v2_has_controlled_apply_id(self, lottery_type, strategy_id):
        data = _history(lottery_type, strategy_id, page=1)
        bad = [r for r in data["records"] if r.get("controlled_apply_id") != V2_APPLY_ID]
        assert not bad, f"{strategy_id}: page-1 records missing V2 controlled_apply_id"


@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestTruthLevelFieldsAlwaysPresent:
    """truth_level and controlled_apply_id keys must always be present in response records."""

    def test_truth_level_key_always_in_records(self):
        data = _history("BIG_LOTTO", "biglotto_deviation_2bet", page=1)
        for rec in data["records"]:
            assert "truth_level" in rec, f"truth_level key missing from record id={rec.get('id')}"

    def test_controlled_apply_id_key_always_in_records(self):
        data = _history("BIG_LOTTO", "biglotto_deviation_2bet", page=1)
        for rec in data["records"]:
            assert "controlled_apply_id" in rec, (
                f"controlled_apply_id key missing from record id={rec.get('id')}"
            )

    def test_source_key_always_in_records(self):
        data = _history("BIG_LOTTO", "biglotto_deviation_2bet", page=1)
        for rec in data["records"]:
            assert "source" in rec, f"source key missing from record id={rec.get('id')}"

    def test_provenance_hash_key_always_in_records(self):
        data = _history("BIG_LOTTO", "biglotto_deviation_2bet", page=1)
        for rec in data["records"]:
            assert "provenance_hash" in rec, (
                f"provenance_hash key missing from record id={rec.get('id')}"
            )

    def test_legacy_rows_have_null_truth_level(self):
        """Legacy rows (last page) must have null truth_level — they are protected, not reclassified."""
        data = _history("BIG_LOTTO", "biglotto_deviation_2bet", page=1)
        total_pages = data["pages"]
        if total_pages > 1:
            last_page = _history("BIG_LOTTO", "biglotto_deviation_2bet", page=total_pages)
            legacy = [r for r in last_page["records"] if r.get("truth_level") is None]
            assert len(legacy) > 0, "Last page should contain legacy (null truth_level) rows"
