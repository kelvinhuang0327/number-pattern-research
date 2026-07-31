"""
Tests for P262A Replay Strategy Coverage Audit (tools/audit_p262a_replay_strategy_coverage.py).

READ-ONLY audit. These tests:
  - never write to the DB (one test proves row count is unchanged),
  - assert the coverage-matrix schema and overview-membership invariants,
  - assert determinism / re-runnability,
  - gate DB-content-specific identities behind the zen-gates canonical DB marker.

Run:
  .venv/bin/python -m pytest tests/test_p262a_replay_strategy_coverage_audit.py -q
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_PATH = _REPO_ROOT / "tools" / "audit_p262a_replay_strategy_coverage.py"
_DB_PATH = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_p262a", _AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


audit_mod = _load_audit_module()

REQUIRED_MATRIX_KEYS = {
    "strategy_id",
    "strategy_name",
    "lifecycle",
    "lottery_type",
    "appears_in_overview",
    "appears_in_default_bet1_view",
    "has_replay_rows",
    "replay_row_count",
    "distinct_draw_count",
    "max_bet_index",
    "can_open_detail",
    "catalog_visibility_state",
    "missing_reason",
}


# ── No-DB unit tests (pure logic) ────────────────────────────────────────────


def test_derive_bet_count_cases():
    f = audit_mod.derive_bet_count
    assert f("acb_markov_midfreq_3bet") == 3
    assert f("daily539_f4cold_5bet") == 5
    assert f("biglotto_deviation_2bet") == 2
    assert f("pp3_freqort_4bet") == 4
    assert f("biglotto_triple_strike") == 3  # special case
    assert f("acb_1bet") == 1
    assert f("acb_single_539") == 1  # no Nbet suffix -> default 1


def test_derive_bet_count_parity_with_route_ssot():
    """When fastapi is importable, our mirror must match the route SSOT exactly."""
    try:
        from lottery_api.routes.replay import _derive_bet_count as route_fn
    except Exception:
        pytest.skip("fastapi/route module not importable in this env")
    samples = [
        "acb_1bet", "acb_markov_midfreq_3bet", "daily539_f4cold_5bet",
        "biglotto_triple_strike", "pp3_freqort_4bet", "midfreq_fourier_2bet",
        "power_orthogonal_5bet", "ts3_regime_3bet", "acb_single_539",
    ]
    for sid in samples:
        assert audit_mod.derive_bet_count(sid) == route_fn(sid), sid


def test_artifact_token_set_matching():
    """rejected/ filenames reorder tokens vs strategy_ids; token-set match links them."""
    rejected = [
        "ts3_acb_4bet_biglotto",
        "shlc_midfreq_power",
        "p1_deviation_2bet_539",
        "unrelated_xyz",
    ]
    index = audit_mod.build_rejected_index(rejected)
    m = audit_mod.match_rejected_artifact
    assert m("biglotto_ts3_acb_4bet", index) == "ts3_acb_4bet_biglotto"
    assert m("power_shlc_midfreq", index) == "shlc_midfreq_power"
    assert m("p1_deviation_2bet_539", index) == "p1_deviation_2bet_539"
    assert m("totally_unknown_strategy", index) is None


def test_registry_lifecycle_counts_no_db():
    """Registry is code-deterministic regardless of DB state."""
    from lottery_api.models.replay_strategy_registry import (
        list_strategy_lifecycle_metadata,
    )
    reg = list_strategy_lifecycle_metadata()
    counts: dict = {}
    for m in reg:
        counts[m["lifecycle_status"]] = counts.get(m["lifecycle_status"], 0) + 1
    assert len(reg) == 38
    assert counts == {"ONLINE": 8, "REJECTED": 16, "RETIRED": 13, "OBSERVATION": 1}


# ── DB-backed tests (read-only) ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def audit():
    return audit_mod.build_audit()


@pytest.mark.requires_db
def test_build_audit_top_level(audit):
    assert audit["read_only"] is True
    assert audit["no_db_write"] is True
    assert audit["no_replay_backfill"] is True
    assert audit["no_adapter_change"] is True
    for key in ("summary", "issues", "coverage_matrix", "rejected_artifact_strategy_ids"):
        assert key in audit


@pytest.mark.requires_db
def test_db_not_mutated_by_audit():
    """Proves the audit is read-only: row count is identical before and after."""
    def _count():
        con = sqlite3.connect(str(_DB_PATH))
        try:
            return con.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            con.close()

    before = _count()
    audit_mod.build_audit()
    after = _count()
    assert before == after


@pytest.mark.requires_db
def test_audit_is_deterministic():
    """Re-runnable: two consecutive builds produce identical matrices."""
    a = audit_mod.build_audit()["coverage_matrix"]
    b = audit_mod.build_audit()["coverage_matrix"]
    assert a == b


@pytest.mark.requires_db
def test_matrix_schema(audit):
    assert audit["coverage_matrix"], "matrix must be non-empty"
    for row in audit["coverage_matrix"]:
        missing = REQUIRED_MATRIX_KEYS - set(row.keys())
        assert not missing, f"row {row['strategy_id']} missing keys: {missing}"
        assert row["appears_in_overview"] in ("YES", "NO")
        assert row["has_replay_rows"] in ("YES", "NO")
        assert row["can_open_detail"] in ("YES", "NO")


@pytest.mark.requires_db
def test_overview_membership_invariants(audit):
    for row in audit["coverage_matrix"]:
        # default bet1 view implies reachable in overview AND derived bet count == 1
        if row["appears_in_default_bet1_view"] == "YES":
            assert row["appears_in_overview"] == "YES"
            assert row["derived_bet_count"] == 1
        # reachable in overview implies registered AND lottery supported by registry
        if row["appears_in_overview"] == "YES":
            assert row["registered"] is True
            assert row["supported_by_registry_for_lottery_type"] is True


@pytest.mark.requires_db
def test_can_open_detail_iff_has_rows(audit):
    for row in audit["coverage_matrix"]:
        assert (row["can_open_detail"] == "YES") == (row["has_replay_rows"] == "YES")


@pytest.mark.requires_db
def test_summary_internal_consistency(audit):
    s = audit["summary"]
    assert (
        s["strategies_with_replay_rows"] + s["strategies_without_replay_rows"]
        == s["total_known_strategies"]
    )
    assert (
        s["total_known_strategies"]
        == s["total_registered_strategies"]
        + len(s["orphan_strategies_rows_but_unregistered"])
    )
    assert s["total_registered_strategies"] == 38
    # every orphan must be unregistered AND have rows somewhere in the matrix
    orphan_set = set(s["orphan_strategies_rows_but_unregistered"])
    seen = {r["strategy_id"]: r for r in audit["coverage_matrix"]}
    for sid in orphan_set:
        assert seen[sid]["registered"] is False
        assert seen[sid]["has_replay_rows"] == "YES"


@pytest.mark.requires_db
def test_issues_present(audit):
    types = {i["type"] for i in audit["issues"]}
    # the overview-coverage gaps this audit exists to surface
    assert "ORPHAN_REPLAY_ROWS" in types
    assert "HIDDEN_IN_DEFAULT_BET1_VIEW" in types


# ── Canonical zen-gates DB content assertions ────────────────────────────────


@pytest.mark.requires_zen_gates_db
@pytest.mark.requires_bet_index
def test_zen_gates_known_orphans_and_missing(audit):
    s = audit["summary"]
    assert set(s["orphan_strategies_rows_but_unregistered"]) == {
        "midfreq_fourier_mk_3bet",
        "pp3_freqort_4bet",
    }
    assert "h6_gate_mk20_ew85" in s["registered_without_replay_rows"]
    assert s["strategies_with_replay_rows"] == 35
    assert s["total_known_strategies"] == 40


# ── Report writing (isolated to tmp dir; never pollutes outputs/research) ─────


@pytest.mark.requires_db
def test_write_reports_to_tmp(tmp_path):
    audit = audit_mod.build_audit()
    json_path, md_path = audit_mod.write_reports(audit, research_dir=tmp_path)
    assert json_path.exists() and md_path.exists()
    import json as _json
    reparsed = _json.loads(json_path.read_text(encoding="utf-8"))
    assert reparsed["task_id"] == "P262A"
    assert "# P262A" in md_path.read_text(encoding="utf-8")
