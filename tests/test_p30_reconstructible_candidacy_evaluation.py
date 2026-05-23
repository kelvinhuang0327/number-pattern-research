"""
P30 — Reconstructible-Candidacy Evaluation Tests (Read-Only)
=============================================================
Verifies the P30 evaluation output is complete and consistent:
- All 51 non-row-backed strategies are classified
- Classification buckets are mutually exclusive and exhaustive
- Production DB is untouched (12460 rows)
- No executable code is invoked (read-only evaluation only)
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
_DB_PATH    = LOTTERY_API / "data" / "lottery_v2.db"
_OUTPUT     = REPO_ROOT / "outputs" / "replay" / "p30_reconstructible_candidacy_evaluation_20260521.json"

sys.path.insert(0, str(LOTTERY_API))
from routes.replay import get_replay_strategy_catalog  # noqa: E402

EXPECTED_PROD_ROWS   = 19960  # Updated post-P31B (2026-05-23): 7500 Wave 1 retired rows applied
EXPECTED_NON_RB      = 51
VALID_CLASSIFICATIONS = {"needs_promotion", "executable_no", "manual_review"}


@pytest.fixture(scope="module")
def output() -> dict:
    assert _OUTPUT.exists(), f"P30 output JSON not found: {_OUTPUT}"
    return json.loads(_OUTPUT.read_text())


@pytest.fixture(scope="module")
def catalog():
    async def _get():
        return await get_replay_strategy_catalog()
    return asyncio.new_event_loop().run_until_complete(_get())


# ── Output JSON structural tests ──────────────────────────────────────────────

def test_output_exists():
    assert _OUTPUT.exists()


def test_output_phase(output):
    assert output["phase"] == "P30_RECONSTRUCTIBLE_CANDIDACY_EVALUATION"


def test_output_production_rows(output):
    assert output["production_rows"] == EXPECTED_PROD_ROWS


def test_output_total_non_row_backed(output):
    assert output["total_non_row_backed"] == EXPECTED_NON_RB


def test_all_strategies_classified(output):
    """Every non-row-backed strategy must have a classification."""
    strategies = output["strategies"]
    assert len(strategies) == EXPECTED_NON_RB, \
        f"Expected {EXPECTED_NON_RB} strategies, got {len(strategies)}"


def test_classification_values_valid(output):
    """All classifications must be from the valid set."""
    for sid, info in output["strategies"].items():
        cls = info["classification"]
        assert cls in VALID_CLASSIFICATIONS, \
            f"{sid}: invalid classification '{cls}'"


def test_classification_counts_sum(output):
    """Sum of classification counts must equal 51."""
    total = sum(output["classification_summary"].values())
    assert total == EXPECTED_NON_RB


def test_needs_promotion_count(output):
    """needs_promotion should be the largest bucket."""
    assert output["classification_summary"]["needs_promotion"] >= 20


def test_executable_no_count(output):
    assert output["classification_summary"]["executable_no"] >= 5


def test_manual_review_count(output):
    assert output["classification_summary"]["manual_review"] >= 5


def test_every_strategy_has_evidence(output):
    """Every entry must have an evidence path or reason."""
    for sid, info in output["strategies"].items():
        assert info.get("evidence"), f"{sid}: missing evidence"


def test_every_strategy_has_lottery_type(output):
    for sid, info in output["strategies"].items():
        assert info.get("lottery_type"), f"{sid}: missing lottery_type"


def test_every_strategy_has_recommended_action(output):
    for sid, info in output["strategies"].items():
        assert info.get("recommended_action"), f"{sid}: missing recommended_action"


def test_next_phase_recommendation_present(output):
    """P30 must recommend a next phase (P31)."""
    nxt = output.get("recommended_next_phase", {})
    assert nxt.get("phase") == "P31"
    assert nxt.get("candidate_count", 0) >= 20
    assert len(nxt.get("candidates", [])) == nxt["candidate_count"]


# ── Catalog cross-check ───────────────────────────────────────────────────────

def test_catalog_non_row_backed_matches_p30(catalog, output):
    """The 51 strategies evaluated must match the catalog's non-queryable list."""
    catalog_non_rb = {s["strategy_id"] for s in catalog["strategies"]
                      if not s.get("is_queryable", False)}
    p30_strategies = set(output["strategies"].keys())
    # P30 should cover all non-row-backed from catalog
    missing = catalog_non_rb - p30_strategies
    extra   = p30_strategies - catalog_non_rb
    assert not missing, f"Strategies in catalog but not in P30: {missing}"
    assert not extra,   f"Strategies in P30 but not in catalog: {extra}"


def test_catalog_total_unchanged(catalog):
    assert catalog["total_strategies"] == 59


def test_catalog_row_backed_count(catalog):
    assert catalog["row_backed_count"] == 8


# ── Production DB invariant ───────────────────────────────────────────────────

def test_production_rows_unchanged():
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_PROD_ROWS, \
        f"Production rows changed: expected {EXPECTED_PROD_ROWS}, got {count}"


# ── Read-only guarantee ───────────────────────────────────────────────────────

def test_no_db_writes_performed(output):
    """P30 is read-only — verify no production_apply flag."""
    assert "production_apply" not in output or output.get("production_apply") is False


def test_no_strategy_execution_artifacts():
    """Ensure no ephemeral strategy-execution files were created."""
    suspicious = list(REPO_ROOT.glob("outputs/replay/p30_*_adapter_*"))
    assert not suspicious, f"Unexpected adapter output files: {suspicious}"
