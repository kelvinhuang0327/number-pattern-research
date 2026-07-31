"""P263A — read-only tests for the D3 strategy-status coverage audit.

These tests are READ-ONLY: they call `build_audit()` (a pure function that only
SELECTs from the replay DB and reads artifacts) and assert the reconciled numbers.
They never write the DB, the registry, the D3 UI/API, or any artifact file.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

pytestmark = pytest.mark.filterwarnings("ignore")


def _audit():
    from tools.audit_p263a_d3_strategy_status_coverage import build_audit, DB_PATH
    if not DB_PATH.exists():
        pytest.skip(f"replay DB not present at {DB_PATH}")
    return build_audit()


# ── Universe reconciliation (P262B baseline) ────────────────────────────────

def test_universe_is_41_cells_40_strategies():
    a = _audit()
    assert a["universe"]["total_cells"] == 41
    assert a["universe"]["total_strategy_ids"] == 40


def test_registered_without_rows_is_five():
    a = _audit()
    assert len(a["universe"]["registered_without_rows"]) == 5
    assert set(a["universe"]["registered_without_rows"]) == {
        "BIG_LOTTO:biglotto_ts3_acb_4bet",
        "BIG_LOTTO:biglotto_ts3_markov_freq_5bet",
        "DAILY_539:p1_deviation_2bet_539",
        "POWER_LOTTO:h6_gate_mk20_ew85",
        "POWER_LOTTO:power_shlc_midfreq",
    }


def test_two_orphans_and_one_mismatch():
    a = _audit()
    assert a["universe"]["unregistered_orphans"] == [
        "POWER_LOTTO:midfreq_fourier_mk_3bet",
        "POWER_LOTTO:pp3_freqort_4bet",
    ]
    assert a["universe"]["registry_lottery_mismatch"] == [
        "POWER_LOTTO:midfreq_fourier_2bet",
    ]


# ── D3 coverage ─────────────────────────────────────────────────────────────

def test_d3_artifact_backed_no_db_query():
    a = _audit()
    assert a["d3"]["data_source"] == "artifact_only"
    assert a["d3"]["row_count"] == 14


def test_d3_covers_only_8_of_41_cells():
    a = _audit()
    assert a["d3"]["coverage_count"] == 8
    covered = sum(1 for r in a["coverage_matrix"] if r["appears_in_D3"])
    assert covered == 8


def test_d3_has_6_phantom_rows():
    a = _audit()
    assert len(a["d3"]["phantom_rows"]) == 6
    assert set(a["d3"]["phantom_rows"]) == {
        "BIG_LOTTO:regime_2bet",
        "BIG_LOTTO:p1_deviation_4bet",
        "BIG_LOTTO:p1_dev_sum5bet",
        "BIG_LOTTO:p1_neighbor_cold_2bet",
        "DAILY_539:f4cold_5bet",
        "POWER_LOTTO:orthogonal_5bet",
    }


def test_d3_missing_33_cells():
    a = _audit()
    assert len(a["d3"]["missing_cells"]) == 41 - 8


# ── Missing fields ──────────────────────────────────────────────────────────

def test_d3_missing_status_and_reject_fields():
    a = _audit()
    miss = set(a["d3"]["missing_fields"])
    for f in ("registry_status", "distinct_draw_count", "can_open_detail",
              "missing_reason", "status_reason", "status_updated_at",
              "status_source", "reject_reason", "reject_updated_at",
              "reject_source_artifact"):
        assert f in miss, f


def test_d3_missing_all_success_rate_fields():
    a = _audit()
    miss = set(a["d3"]["missing_fields"])
    for w in (30, 100, 500, 1500):
        assert f"success_rate_{w}" in miss


# ── Success-rate contract is undefined (must NOT be self-defined) ────────────

def test_success_rate_data_exists_but_contract_undefined():
    a = _audit()
    assert a["success_rate"]["raw_data_exists_in_replay_db"] is True
    assert a["success_rate"]["exposed_by_d3"] is False
    assert a["success_rate"]["exposed_by_any_api"] is False
    assert a["success_rate"]["contract_defined"] is False
    assert len(a["success_rate"]["contract_open_questions"]) >= 5


# ── Data-quality findings ───────────────────────────────────────────────────

def test_lifecycle_disagrees_on_every_mapped_cell():
    a = _audit()
    # all 8 mapped cells have a D3 lifecycle that differs from the registry
    assert len(a["d3"]["lifecycle_disagreements"]) == 8


def test_d3_replay_row_count_is_swapped_aggregate():
    a = _audit()
    by_lt = {f["lottery_type"]: f for f in a["d3"]["replay_row_count_findings"]}
    # DAILY_539 and POWER_LOTTO totals are transposed in the D3 artifact
    assert by_lt["DAILY_539"]["d3_replay_row_count"] == 36104
    assert by_lt["DAILY_539"]["db_lottery_total"] == 34680
    assert by_lt["POWER_LOTTO"]["d3_replay_row_count"] == 34680
    assert by_lt["POWER_LOTTO"]["db_lottery_total"] == 36104
    assert by_lt["DAILY_539"]["matches_db_total"] is False
    assert by_lt["POWER_LOTTO"]["matches_db_total"] is False
    assert all(not f["is_per_strategy"] for f in a["d3"]["replay_row_count_findings"])


def test_registry_lacks_status_reason_provenance():
    a = _audit()
    sr = a["status_reject_reason"]
    assert sr["registry_has_reason_field"] is False
    assert sr["registry_has_updated_at_field"] is False
    assert sr["registry_has_source_field"] is False
    assert sr["rejected_artifacts_used_by_d3"] is False
