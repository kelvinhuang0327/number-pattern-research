"""End-to-end dry-run checks for the P3 replay pipeline split classifier."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lottery_api.models.replay_pipeline_contract import FORMAL_LIFECYCLE_STATES


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = REPO_ROOT.parent / "LotteryNew" / ".venv" / "bin" / "python3"
SCRIPT = REPO_ROOT / "scripts" / "p3_replay_pipeline_split_classifier.py"
OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json"


def _run_classifier() -> dict:
    subprocess.run(
        [str(PYTHON), str(SCRIPT)],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def payload():
    return _run_classifier()


def test_classifier_generates_expected_totals(payload):
    assert payload["total_strategies"] == 506
    assert payload["by_pipeline"] == {
        "HISTORICAL_RECONSTRUCTION": 97,
        "FUTURE_WAITING": 2,
        "DISPLAY_ONLY": 407,
        "UNSUPPORTED": 0,
    }


def test_classifier_covers_all_formal_lifecycle_states(payload):
    assert set(payload["by_lifecycle_and_pipeline"]) == set(FORMAL_LIFECYCLE_STATES)


def test_historical_reconstruction_split_counts(payload):
    rows = payload["historical_reconstruction_candidates"]
    assert len(rows) == 97
    assert sum(1 for row in rows if row["has_replay_rows"]) == 11
    assert sum(1 for row in rows if not row["has_replay_rows"]) == 86


def test_future_waiting_candidates_are_the_watcher_targets(payload):
    strategy_ids = {row["strategy_id"] for row in payload["future_waiting_candidates"]}
    assert strategy_ids == {"biglotto_triple_strike", "power_precision_3bet"}
    assert all(row["blocks_historical_coverage"] is False for row in payload["future_waiting_candidates"])


def test_display_only_candidates_are_inventory_only(payload):
    rows = payload["display_only_candidates"]
    assert len(rows) == 407
    assert {row["historical_record_source"] for row in rows} == {"none"}


def test_no_placeholder_text_in_payload(payload):
    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            assert value not in {"TBD", "TODO", "null"}

    walk(payload)


def test_dry_run_safety_flags(payload):
    assert payload["safety"] == {
        "db_write": False,
        "draw_import": False,
        "replay_row_generation": False,
        "prediction_update": False,
        "strategy_execution": False,
    }
