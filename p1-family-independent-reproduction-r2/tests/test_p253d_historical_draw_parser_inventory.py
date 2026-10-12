"""Tests for P253D — Historical Draw Parser Inventory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

REQUIRED_JSON_KEYS = [
    "schema_version", "task_id", "classification", "phase0_summary",
    "p253a_dependency_verified", "parser_inventory", "db_positional_inventory",
    "star_lottery_positional_status", "straight_play_storage_caveat",
    "future_parser_ssot_readiness", "recommended_next_task",
    "no_db_write_confirmed", "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed", "no_betting_advice_confirmed",
    "final_decision",
]

PARSER_CLASSIFICATIONS = {
    "ACTIVE_PARSER",
    "OFFICIAL_DRY_RUN_PARSER",
    "HISTORICAL_IMPORT_SCRIPT",
    "CONTROLLED_APPLY_COMPLETE",
    "ARCHIVED_OR_EXPLORATORY_DEFER",
    "UNKNOWN_NEEDS_SCOPE",
}


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p253d_historical_draw_parser_inventory_*.json"))
    assert candidates, "No p253d artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact structure ────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_artifact_task_id():
    assert _load()["task_id"] == "P253D"


def test_artifact_classification():
    assert _load()["classification"] == "HISTORICAL_DRAW_PARSER_INVENTORY_COMPLETE"


def test_artifact_required_keys():
    data = _load()
    for k in REQUIRED_JSON_KEYS:
        assert k in data, f"Missing key: {k!r}"


# ── Compliance flags ──────────────────────────────────────────────────────────

def test_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


# ── P253A dependency ──────────────────────────────────────────────────────────

def test_p253a_dependency_verified():
    dep = _load()["p253a_dependency_verified"]
    assert dep["found"] is True
    assert dep["classification_match"] is True


# ── Parser inventory ──────────────────────────────────────────────────────────

def test_parser_inventory_non_empty():
    inv = _load()["parser_inventory"]
    assert isinstance(inv, list) and len(inv) > 0


def test_parser_inventory_each_has_classification():
    for entry in _load()["parser_inventory"]:
        assert "classification" in entry, f"Missing classification in {entry.get('path')}"
        assert entry["classification"] in PARSER_CLASSIFICATIONS, (
            f"Unknown classification: {entry['classification']!r}"
        )


def test_parser_inventory_each_has_lottery_types():
    for entry in _load()["parser_inventory"]:
        assert "lottery_types" in entry, f"Missing lottery_types in {entry.get('path')}"
        assert isinstance(entry["lottery_types"], list) and len(entry["lottery_types"]) > 0


def test_parser_inventory_each_has_description():
    for entry in _load()["parser_inventory"]:
        assert "description" in entry and isinstance(entry["description"], str)


def test_parser_inventory_has_active_parser():
    clss = [e["classification"] for e in _load()["parser_inventory"]]
    assert "ACTIVE_PARSER" in clss


def test_parser_inventory_has_official_dry_run():
    clss = [e["classification"] for e in _load()["parser_inventory"]]
    assert "OFFICIAL_DRY_RUN_PARSER" in clss


def test_parser_inventory_has_controlled_apply():
    clss = [e["classification"] for e in _load()["parser_inventory"]]
    assert "CONTROLLED_APPLY_COMPLETE" in clss


# ── DB positional inventory ───────────────────────────────────────────────────

def test_db_positional_inventory_non_empty():
    inv = _load()["db_positional_inventory"]
    assert isinstance(inv, dict) and len(inv) > 0


def test_db_positional_inventory_has_3star():
    assert "3_STAR" in _load()["db_positional_inventory"]


def test_db_positional_inventory_has_4star():
    assert "4_STAR" in _load()["db_positional_inventory"]


def test_db_positional_inventory_3star_complete():
    entry = _load()["db_positional_inventory"]["3_STAR"]
    assert entry["positional_coverage_rate"] == 100.0, (
        f"3_STAR coverage should be 100% but got {entry['positional_coverage_rate']}"
    )
    assert entry["draw_rows"] > 0


def test_db_positional_inventory_4star_complete():
    entry = _load()["db_positional_inventory"]["4_STAR"]
    assert entry["positional_coverage_rate"] == 100.0, (
        f"4_STAR coverage should be 100% but got {entry['positional_coverage_rate']}"
    )
    assert entry["draw_rows"] > 0


def test_db_positional_inventory_biglotto_zero():
    entry = _load()["db_positional_inventory"].get("BIG_LOTTO", {})
    assert entry.get("positional_coverage_rate", 0) == 0.0


def test_db_positional_inventory_has_draw_rows():
    for lt, v in _load()["db_positional_inventory"].items():
        assert "draw_rows" in v, f"{lt} missing draw_rows"
        assert v["draw_rows"] >= 0


# ── Star lottery positional status ───────────────────────────────────────────

def test_star_positional_status_has_3star():
    assert "3_STAR" in _load()["star_lottery_positional_status"]


def test_star_positional_status_has_4star():
    assert "4_STAR" in _load()["star_lottery_positional_status"]


def test_3star_positional_complete():
    s = _load()["star_lottery_positional_status"]["3_STAR"]
    assert s["positional_status"] == "COMPLETE"
    assert s["draw_order_preserved"] is True


def test_4star_positional_complete():
    s = _load()["star_lottery_positional_status"]["4_STAR"]
    assert s["positional_status"] == "COMPLETE"
    assert s["draw_order_preserved"] is True


def test_star_positional_status_has_power_caveats():
    status = _load()["star_lottery_positional_status"]
    assert "power_caveats" in status or any(
        "caveat" in k.lower() or "power" in k.lower()
        for k in status.keys()
    )


def test_3star_draw_rows_correct():
    s = _load()["star_lottery_positional_status"]["3_STAR"]
    assert s["draw_rows"] == 5850


def test_4star_draw_rows_correct():
    s = _load()["star_lottery_positional_status"]["4_STAR"]
    assert s["draw_rows"] == 5850


# ── Straight-play caveat ──────────────────────────────────────────────────────

def test_straight_play_storage_caveat_exists():
    caveat = _load()["straight_play_storage_caveat"]
    assert isinstance(caveat, dict) and len(caveat) > 0


def test_straight_play_caveat_mentions_positional():
    caveat = json.dumps(_load()["straight_play_storage_caveat"]).lower()
    assert "numbers_positional" in caveat or "positional" in caveat


def test_straight_play_caveat_not_claiming_edge():
    caveat = json.dumps(_load()["straight_play_storage_caveat"]).lower()
    assert "prediction edge" not in caveat
    assert "betting advice" not in caveat


# ── Future SSOT readiness ─────────────────────────────────────────────────────

def test_future_ssot_readiness_exists():
    assert "future_parser_ssot_readiness" in _load()


def test_future_ssot_readiness_decision_present():
    r = _load()["future_parser_ssot_readiness"]
    assert "decision" in r
    assert r["decision"] in (
        "READY_FOR_NEXT_TASK", "NEEDS_SOURCE_VERIFICATION",
        "BLOCKED_BY_DB_SCHEMA", "DEFER"
    )


def test_future_ssot_readiness_is_ready():
    r = _load()["future_parser_ssot_readiness"]
    assert r["decision"] == "READY_FOR_NEXT_TASK"


# ── Recommended next task ─────────────────────────────────────────────────────

def test_recommended_next_task_exists():
    rec = _load()["recommended_next_task"]
    assert isinstance(rec, dict)
    assert "task_id" in rec or "alternative" in rec


def test_recommended_next_or_hold():
    rec = _load()["recommended_next_task"]
    has_task = "task_id" in rec and rec.get("task_id") not in (None, "")
    has_hold = "hold" in str(rec).lower() or "alternative" in rec
    assert has_task or has_hold, "Must have next task or HOLD"


def test_recommended_no_strategy_promotion():
    rec = json.dumps(_load()["recommended_next_task"]).lower()
    assert "strategy promotion" not in rec
    assert "betting advice" not in rec


# ── Final decision ────────────────────────────────────────────────────────────

def test_final_decision_no_edge_claim():
    fd = _load()["final_decision"].lower()
    assert "deployable prediction edge" in fd or "no deployable prediction edge" in fd or \
           "no edge" in fd or "no betting advice" in fd


def test_final_decision_no_betting_advice_claimed():
    fd = _load()["final_decision"].lower()
    assert "provide betting" not in fd
    assert "recommending bets" not in fd


# ── MD artifact ───────────────────────────────────────────────────────────────

def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p253d_historical_draw_parser_inventory_*.md"))
    assert candidates, "No p253d MD artifact"


def test_md_required_sections():
    candidates = sorted(OUTPUTS_DIR.glob("p253d_historical_draw_parser_inventory_*.md"))
    text = candidates[-1].read_text(encoding="utf-8").lower()
    for phrase in ["no db write", "no betting advice", "ssot", "3_star", "4_star", "positional"]:
        assert phrase in text, f"MD missing phrase: {phrase!r}"


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p253d_historical_draw_parser_inventory as p253d
    r = p253d.main()
    assert r["task_id"] == "P253D"
    assert r["classification"] == "HISTORICAL_DRAW_PARSER_INVENTORY_COMPLETE"
    assert r["no_db_write_confirmed"] is True
    assert r["db_positional_inventory"]["3_STAR"]["positional_coverage_rate"] == 100.0
    assert r["db_positional_inventory"]["4_STAR"]["positional_coverage_rate"] == 100.0
