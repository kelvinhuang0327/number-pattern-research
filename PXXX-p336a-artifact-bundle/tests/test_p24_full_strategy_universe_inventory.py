"""
tests/test_p24_full_strategy_universe_inventory.py
====================================================
P24: Full Strategy Universe Inventory — test suite

Validates:
  - Output JSON exists and is well-formed
  - Required fields present on every strategy entry
  - ONLINE_ROW_BACKED strategies have row_count > 0
  - ARTIFACT_ONLY strategies have source_artifact, row_count == 0
  - RETIRED / REJECTED_REGISTERED strategies are in registry, reconstructible
  - Production rows unchanged (12460)
  - No DB write occurred
  - P22 / P23 regressions still pass
  - Drift guard consistency
  - Category separation: row-backed vs non-row-backed vs artifact-only
"""
from __future__ import annotations

import json
import pathlib
import sqlite3

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INVENTORY_PATH = REPO_ROOT / "outputs" / "replay" / "p24_full_strategy_universe_inventory_20260521.json"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
REGISTRY_PATH = REPO_ROOT / "lottery_api" / "models" / "replay_strategy_registry.py"
REJECTED_DIR  = REPO_ROOT / "rejected"

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def inv() -> dict:
    assert INVENTORY_PATH.exists(), f"Inventory not found: {INVENTORY_PATH}"
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def strategies(inv) -> list:
    return inv["strategies"]


@pytest.fixture(scope="module")
def by_vis(inv) -> dict:
    return inv["by_replay_visibility_state"]


@pytest.fixture(scope="module")
def db_con():
    con = sqlite3.connect(str(DB_PATH))
    yield con
    con.close()


# ─── Class 1: File existence and top-level structure ──────────────────────────

class TestInventoryFileStructure:
    def test_file_exists(self):
        assert INVENTORY_PATH.exists()

    def test_is_valid_json(self):
        data = json.loads(INVENTORY_PATH.read_text())
        assert isinstance(data, dict)

    def test_phase_is_p24(self, inv):
        assert inv["phase"] == "P24"

    def test_dry_run_only_true(self, inv):
        assert inv["dry_run_only"] is True

    def test_top_level_keys(self, inv):
        required = {
            "generated_at", "phase", "dry_run_only",
            "production_rows_verified", "summary",
            "by_replay_visibility_state", "strategies",
        }
        assert required.issubset(inv.keys())

    def test_strategies_is_list(self, inv):
        assert isinstance(inv["strategies"], list)

    def test_strategies_non_empty(self, strategies):
        assert len(strategies) > 0


# ─── Class 2: Required fields on every strategy entry ─────────────────────────

REQUIRED_FIELDS = {
    "strategy_id", "lottery_type", "lifecycle_state",
    "replay_visibility_state", "row_count", "verified_row_count",
    "truth_level_summary", "reconstructible_candidate", "needs_manual_review",
}

class TestRequiredFields:
    def test_all_strategies_have_required_fields(self, strategies):
        for s in strategies:
            missing = REQUIRED_FIELDS - s.keys()
            assert not missing, f"{s['strategy_id']} missing fields: {missing}"

    def test_strategy_id_non_empty(self, strategies):
        for s in strategies:
            assert s["strategy_id"], "strategy_id must not be empty"

    def test_lifecycle_state_valid(self, strategies):
        valid = {"ONLINE", "OFFLINE", "REJECTED", "OBSERVATION", "RETIRED",
                 "EXPERIMENTAL", "UNKNOWN", "PRODUCTION", "NOT_REGISTERED"}
        for s in strategies:
            assert s["lifecycle_state"] in valid, \
                f"{s['strategy_id']}: unexpected lifecycle_state={s['lifecycle_state']}"

    def test_replay_visibility_state_valid(self, strategies):
        valid = {
            "ONLINE_ROW_BACKED", "ONLINE_NO_ROWS", "OBSERVATION",
            "OFFLINE", "REJECTED_REGISTERED", "RETIRED",
            "ARTIFACT_ONLY", "NO_DATA", "MANUAL_REVIEW",
        }
        for s in strategies:
            assert s["replay_visibility_state"] in valid, \
                f"{s['strategy_id']}: unexpected vis={s['replay_visibility_state']}"

    def test_row_count_non_negative(self, strategies):
        for s in strategies:
            assert s["row_count"] >= 0

    def test_verified_row_count_lte_row_count(self, strategies):
        for s in strategies:
            assert s["verified_row_count"] <= s["row_count"], \
                f"{s['strategy_id']}: verified_row_count > row_count"

    def test_reconstructible_candidate_is_bool(self, strategies):
        for s in strategies:
            assert isinstance(s["reconstructible_candidate"], bool)

    def test_needs_manual_review_is_bool(self, strategies):
        for s in strategies:
            assert isinstance(s["needs_manual_review"], bool)


# ─── Class 3: ONLINE_ROW_BACKED category ──────────────────────────────────────

class TestOnlineRowBacked:
    @pytest.fixture(scope="class")
    def row_backed(self, strategies):
        return [s for s in strategies if s["replay_visibility_state"] == "ONLINE_ROW_BACKED"]

    def test_count_is_8(self, row_backed):
        assert len(row_backed) == 8, f"Expected 8 ONLINE_ROW_BACKED, got {len(row_backed)}"

    def test_all_have_rows(self, row_backed):
        for s in row_backed:
            assert s["row_count"] > 0, f"{s['strategy_id']} has row_count=0"

    def test_all_lifecycle_online(self, row_backed):
        for s in row_backed:
            assert s["lifecycle_state"] == "ONLINE"

    def test_not_reconstructible(self, row_backed):
        for s in row_backed:
            assert s["reconstructible_candidate"] is False

    def test_no_manual_review(self, row_backed):
        for s in row_backed:
            assert s["needs_manual_review"] is False

    def test_known_strategy_ids_present(self, row_backed):
        ids = {s["strategy_id"] for s in row_backed}
        expected = {
            "daily539_f4cold", "daily539_markov_cold",
            "biglotto_deviation_2bet", "biglotto_triple_strike", "ts3_regime_3bet",
            "power_precision_3bet", "power_orthogonal_5bet", "fourier_rhythm_3bet",
        }
        assert ids == expected

    def test_verified_row_count_is_1500_or_more(self, row_backed):
        for s in row_backed:
            assert s["verified_row_count"] >= 1500, \
                f"{s['strategy_id']}: verified_row_count={s['verified_row_count']} < 1500"

    def test_source_path_set(self, row_backed):
        for s in row_backed:
            assert s["source_path"] is not None


# ─── Class 4: ARTIFACT_ONLY category ─────────────────────────────────────────

class TestArtifactOnly:
    @pytest.fixture(scope="class")
    def artifacts(self, strategies):
        return [s for s in strategies if s["replay_visibility_state"] == "ARTIFACT_ONLY"]

    def test_count_is_41(self, artifacts):
        assert len(artifacts) == 41, f"Expected 41 ARTIFACT_ONLY, got {len(artifacts)}"

    def test_all_have_source_artifact(self, artifacts):
        for s in artifacts:
            assert s["source_artifact"] is not None, \
                f"{s['strategy_id']} missing source_artifact"

    def test_all_row_count_zero(self, artifacts):
        for s in artifacts:
            assert s["row_count"] == 0, f"{s['strategy_id']} has unexpected rows"

    def test_not_reconstructible(self, artifacts):
        for s in artifacts:
            assert s["reconstructible_candidate"] is False

    def test_source_artifact_starts_with_rejected(self, artifacts):
        for s in artifacts:
            assert s["source_artifact"].startswith("rejected/"), \
                f"{s['strategy_id']}: source_artifact={s['source_artifact']}"

    def test_artifact_files_exist_on_disk(self, artifacts):
        for s in artifacts:
            path = REPO_ROOT / s["source_artifact"]
            assert path.exists(), f"Artifact file missing: {s['source_artifact']}"


# ─── Class 5: RETIRED / REJECTED_REGISTERED categories ───────────────────────

class TestRegisteredNonOnline:
    @pytest.fixture(scope="class")
    def retired(self, strategies):
        return [s for s in strategies if s["replay_visibility_state"] == "RETIRED"]

    @pytest.fixture(scope="class")
    def rejected_reg(self, strategies):
        return [s for s in strategies if s["replay_visibility_state"] == "REJECTED_REGISTERED"]

    def test_retired_count_is_5(self, retired):
        assert len(retired) == 5, f"Expected 5 RETIRED, got {len(retired)}"

    def test_rejected_registered_count_is_4(self, rejected_reg):
        assert len(rejected_reg) == 4, f"Expected 4 REJECTED_REGISTERED, got {len(rejected_reg)}"

    def test_retired_are_reconstructible(self, retired):
        for s in retired:
            assert s["reconstructible_candidate"] is True

    def test_rejected_registered_are_reconstructible(self, rejected_reg):
        for s in rejected_reg:
            assert s["reconstructible_candidate"] is True

    def test_retired_row_count_zero(self, retired):
        for s in retired:
            assert s["row_count"] == 0, f"{s['strategy_id']} unexpectedly has rows"

    def test_rejected_registered_row_count_zero(self, rejected_reg):
        for s in rejected_reg:
            assert s["row_count"] == 0, f"{s['strategy_id']} unexpectedly has rows"

    def test_retired_ids(self, retired):
        ids = {s["strategy_id"] for s in retired}
        expected = {"acb_1bet", "acb_markov_midfreq", "acb_markov_midfreq_3bet",
                    "midfreq_acb_2bet", "midfreq_fourier_2bet"}
        assert ids == expected

    def test_rejected_registered_ids(self, rejected_reg):
        ids = {s["strategy_id"] for s in rejected_reg}
        expected = {"biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet",
                    "power_shlc_midfreq", "p1_deviation_2bet_539"}
        assert ids == expected


# ─── Class 6: OBSERVATION category ────────────────────────────────────────────

class TestObservation:
    @pytest.fixture(scope="class")
    def obs(self, strategies):
        return [s for s in strategies if s["replay_visibility_state"] == "OBSERVATION"]

    def test_count_is_1(self, obs):
        assert len(obs) == 1

    def test_strategy_id(self, obs):
        assert obs[0]["strategy_id"] == "h6_gate_mk20_ew85"

    def test_reconstructible_true(self, obs):
        assert obs[0]["reconstructible_candidate"] is True

    def test_row_count_zero(self, obs):
        assert obs[0]["row_count"] == 0


# ─── Class 7: Production DB integrity ─────────────────────────────────────────

class TestProductionDBIntegrity:
    def test_production_rows_12460(self, inv):
        assert inv["production_rows_verified"] == 12460

    def test_production_rows_12460_via_db(self, db_con):
        (n,) = db_con.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()
        assert n == 12460

    def test_db_strategy_count_matches_inventory(self, inv, db_con):
        rows = db_con.execute(
            "SELECT COUNT(DISTINCT strategy_id) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert rows == inv["summary"]["db_row_backed_strategies"]

    def test_inventory_row_backed_matches_db(self, strategies, db_con):
        db_ids = {r[0] for r in db_con.execute(
            "SELECT DISTINCT strategy_id FROM strategy_prediction_replays"
        ).fetchall()}
        inv_ids = {s["strategy_id"] for s in strategies
                   if s["replay_visibility_state"] == "ONLINE_ROW_BACKED"}
        assert inv_ids == db_ids


# ─── Class 8: Summary counts consistency ─────────────────────────────────────

class TestSummaryCounts:
    def test_total_equals_registry_plus_artifact(self, inv):
        s = inv["summary"]
        assert s["total_strategies_inventoried"] == s["registry_total"] + s["artifact_only_total"]

    def test_registry_total_is_18(self, inv):
        assert inv["summary"]["registry_total"] == 18

    def test_artifact_only_total_is_41(self, inv):
        assert inv["summary"]["artifact_only_total"] == 41

    def test_total_is_59(self, inv):
        assert inv["summary"]["total_strategies_inventoried"] == 59

    def test_vis_counts_sum_to_total(self, inv):
        total = sum(inv["by_replay_visibility_state"].values())
        assert total == inv["summary"]["total_strategies_inventoried"]

    def test_p0_reference_count(self, inv):
        assert inv["summary"]["p0_universe_reference_count"] == 512

    def test_db_total_rows_12460(self, inv):
        assert inv["summary"]["db_total_rows"] == 12460


# ─── Class 9: Category separation (row-backed vs non-row-backed vs artifact) ──

class TestCategorySeparation:
    def test_row_backed_all_have_rows(self, strategies):
        row_backed = [s for s in strategies if s["replay_visibility_state"] == "ONLINE_ROW_BACKED"]
        non_row = [s for s in strategies if s["replay_visibility_state"] != "ONLINE_ROW_BACKED"]
        # all row-backed have rows
        assert all(s["row_count"] > 0 for s in row_backed)
        # no non-row-backed have rows
        assert all(s["row_count"] == 0 for s in non_row)

    def test_no_duplicate_strategy_ids(self, strategies):
        ids = [s["strategy_id"] for s in strategies]
        assert len(ids) == len(set(ids)), "Duplicate strategy_id found"

    def test_online_row_backed_have_source_path(self, strategies):
        for s in strategies:
            if s["replay_visibility_state"] == "ONLINE_ROW_BACKED":
                assert s["source_path"] is not None

    def test_artifact_only_have_no_source_path(self, strategies):
        for s in strategies:
            if s["replay_visibility_state"] == "ARTIFACT_ONLY":
                assert s["source_path"] is None

    def test_registry_strategies_have_source_path(self, strategies):
        registry_vis = {"ONLINE_ROW_BACKED", "ONLINE_NO_ROWS", "OBSERVATION",
                        "OFFLINE", "REJECTED_REGISTERED", "RETIRED"}
        for s in strategies:
            if s["replay_visibility_state"] in registry_vis:
                assert s["source_path"] is not None, \
                    f"{s['strategy_id']} missing source_path"


# ─── Class 10: P22 regression guard ──────────────────────────────────────────

class TestP22Regression:
    def test_daily539_predicted_special_null(self, db_con):
        """P22 contract: DAILY_539 predicted_special must always be NULL."""
        n = db_con.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type='DAILY_539' AND predicted_special IS NOT NULL"
        ).fetchone()[0]
        assert n == 0, f"P22 violation: {n} DAILY_539 rows have non-null predicted_special"

    def test_daily539_strategies_in_inventory(self, strategies):
        d539 = [s for s in strategies
                if s["lottery_type"] == "DAILY_539"
                and s["replay_visibility_state"] == "ONLINE_ROW_BACKED"]
        assert len(d539) == 2

    def test_daily539_row_backed_ids(self, strategies):
        ids = {s["strategy_id"] for s in strategies
               if s["lottery_type"] == "DAILY_539"
               and s["replay_visibility_state"] == "ONLINE_ROW_BACKED"}
        assert ids == {"daily539_f4cold", "daily539_markov_cold"}


# ─── Class 11: P23 regression guard ──────────────────────────────────────────

class TestP23Regression:
    def test_registry_file_exists(self):
        assert REGISTRY_PATH.exists()

    def test_registry_has_8_online(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
        meta = list_strategy_lifecycle_metadata()
        online = [m for m in meta if m["lifecycle_status"] == "ONLINE"]
        assert len(online) == 8

    def test_p23_ui_presets_in_html(self):
        html = (REPO_ROOT / "index.html").read_text()
        for preset in ["100", "500", "1000", "1500"]:
            assert f'data-preset="{preset}"' in html, \
                f"P23a preset button {preset} missing from index.html"


# ─── Class 12: Drift guard cross-check ────────────────────────────────────────

class TestDriftGuardCrossCheck:
    def test_total_rows_matches_drift_baseline(self, db_con):
        """The drift guard baseline is 12460 rows."""
        (n,) = db_con.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()
        assert n == 12460

    def test_online_strategy_ids_stable(self, db_con):
        db_ids = {r[0] for r in db_con.execute(
            "SELECT DISTINCT strategy_id FROM strategy_prediction_replays"
        ).fetchall()}
        expected = {
            "daily539_f4cold", "daily539_markov_cold",
            "biglotto_deviation_2bet", "biglotto_triple_strike", "ts3_regime_3bet",
            "power_precision_3bet", "power_orthogonal_5bet", "fourier_rhythm_3bet",
        }
        assert db_ids == expected
