"""
test_p128_wave2_adapter_phase1.py
===================================
Tests for P128 Wave 2 Phase 1 multi-bet adapter implementation.

Verifies:
  - JSON artifact exists and has correct fields
  - DB row count = 72422 (post RSR-6 cleanup: 40 orphan rows deleted)
  - bet_index schema is present
  - P127 classification is valid
  - phase_scope fields (no DB write, no controlled_apply, replay_rows=0)
  - adapter_contract.function_name == 'get_all_bets'
  - All 6 adapters have deterministic ordering + bet_count == 2
  - blocked_or_excluded includes 4_STAR / P108 / P117 / P118 / rejected
  - Markdown contains required sections
  - No DB files staged in git index
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

WORKTREE_ROOT = Path(__file__).parent.parent.resolve()
DB_PATH = WORKTREE_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_ARTIFACT = WORKTREE_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase1_20260528.json"
MD_ARTIFACT = WORKTREE_ROOT / "docs" / "replay" / "p128_wave2_adapter_phase1_20260528.md"
ADAPTER_MODULE = WORKTREE_ROOT / "lottery_api" / "models" / "p128_wave2_phase1_adapters.py"

EXPECTED_DB_ROWS = 82922          # Post P133 apply (pp3_freqort_4bet +4500 rows)
EXPECTED_DB_ROWS_AT_P128_TIME = 72462  # Historical: DB state when P128 artifact was generated
EXPECTED_CLASSIFICATION = "P128_WAVE2_ADAPTER_PHASE1_READY"
EXPECTED_TASK_ID = "P128"
EXPECTED_P127_CLASSIFICATION = "P127_ADAPTER_BUILD_SPECS_READY"

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def artifact() -> dict:
    assert JSON_ARTIFACT.exists(), f"JSON artifact not found: {JSON_ARTIFACT}"
    return json.loads(JSON_ARTIFACT.read_text())


@pytest.fixture(scope="session")
def md_text() -> str:
    assert MD_ARTIFACT.exists(), f"Markdown artifact not found: {MD_ARTIFACT}"
    return MD_ARTIFACT.read_text()


@pytest.fixture(scope="session")
def adapter_module():
    if str(WORKTREE_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKTREE_ROOT))
    import importlib
    import lottery_api.models.p128_wave2_phase1_adapters as mod
    importlib.reload(mod)
    return mod


# ─── Section 1: JSON artifact exists and top-level fields ─────────────────────

class TestJsonArtifactExists:
    def test_json_file_exists(self):
        assert JSON_ARTIFACT.exists(), f"Missing: {JSON_ARTIFACT}"

    def test_task_id(self, artifact):
        assert artifact["task_id"] == EXPECTED_TASK_ID

    def test_classification(self, artifact):
        assert artifact["classification"] == EXPECTED_CLASSIFICATION

    def test_generated_at_present(self, artifact):
        assert "generated_at" in artifact
        assert artifact["generated_at"]

    def test_summary_present(self, artifact):
        assert "summary" in artifact
        assert len(artifact["summary"]) > 10


# ─── Section 2: DB row count unchanged ────────────────────────────────────────

class TestDbRowCount:
    def test_db_rows_unchanged(self):
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        conn.close()
        assert count == EXPECTED_DB_ROWS, (
            f"DB row count changed! Expected {EXPECTED_DB_ROWS}, got {count}"
        )

    def test_artifact_db_row_count(self, artifact):
        # Artifact was generated pre-RSR-6 cleanup; check historical value
        db = artifact["db_snapshot"]
        assert db["row_count"] == EXPECTED_DB_ROWS_AT_P128_TIME
        assert db["expected"] == EXPECTED_DB_ROWS_AT_P128_TIME


# ─── Section 3: bet_index schema ──────────────────────────────────────────────

class TestBetIndexSchema:
    def test_bet_index_column_exists(self):
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
        conn.close()
        names = [c[1] for c in cols]
        assert "bet_index" in names, "bet_index column missing from strategy_prediction_replays"

    def test_artifact_bet_index_schema(self, artifact):
        schema = artifact["bet_index_schema"]
        assert schema["column_name"] == "bet_index"
        assert schema["status"] == "PASS"


# ─── Section 4: P127 classification valid ─────────────────────────────────────

class TestP127Classification:
    def test_p127_classification_in_artifact(self, artifact):
        p127 = artifact["p127_source_summary"]
        assert p127["classification"] == EXPECTED_P127_CLASSIFICATION

    def test_p127_phase1_strategy_count(self, artifact):
        phase1 = artifact["p127_source_summary"]["phase1_strategies"]
        assert len(phase1) == 6, f"Expected 6 Phase 1 strategies, got {len(phase1)}"

    def test_p127_priorities(self, artifact):
        phase1 = artifact["p127_source_summary"]["phase1_strategies"]
        priorities = [s["priority"] for s in phase1]
        assert sorted(priorities) == [1, 2, 3, 4, 5, 6]


# ─── Section 5: phase_scope fields ────────────────────────────────────────────

class TestPhaseScope:
    def test_db_write_false(self, artifact):
        scope = artifact["phase_scope"]
        assert scope["db_write_in_p128"] is False

    def test_controlled_apply_false(self, artifact):
        scope = artifact["phase_scope"]
        assert scope["controlled_apply_executed"] is False

    def test_replay_rows_inserted_zero(self, artifact):
        scope = artifact["phase_scope"]
        assert scope["replay_rows_inserted"] == 0

    def test_production_db_rows_after(self, artifact):
        # Artifact was generated pre-RSR-6 cleanup; check historical value
        scope = artifact["phase_scope"]
        assert scope["production_db_rows_after"] == EXPECTED_DB_ROWS_AT_P128_TIME


# ─── Section 6: adapter_contract.function_name ────────────────────────────────

class TestAdapterContract:
    def test_function_name(self, artifact):
        contract = artifact["adapter_contract"]
        assert contract["function_name"] == "get_all_bets"

    def test_signature_present(self, artifact):
        contract = artifact["adapter_contract"]
        assert "get_all_bets" in contract["signature"]

    def test_no_db_write(self, artifact):
        contract = artifact["adapter_contract"]
        assert contract["no_db_write"] is True

    def test_determinism_guaranteed(self, artifact):
        contract = artifact["adapter_contract"]
        # contract has key "determinism" with value containing "guaranteed"
        assert "determinism" in contract
        assert "guaranteed" in contract["determinism"].lower()


# ─── Section 7: Implemented adapters (all 6, bet_count=2, deterministic) ──────

class TestImplementedAdapters:
    def test_implemented_count_equals_six(self, artifact):
        assert len(artifact["implemented_adapters"]) == 6

    def test_all_adapters_pass(self, artifact):
        for a in artifact["implemented_adapters"]:
            assert a["status"] == "PASS", f"Adapter failed: {a['strategy_id']} / {a['lottery_type']}"

    def test_all_bet_count_two(self, artifact):
        for a in artifact["implemented_adapters"]:
            assert a["bet_count"] == 2, f"{a['strategy_id']}: expected 2 bets"

    def test_all_deterministic(self, artifact):
        for a in artifact["implemented_adapters"]:
            assert a["deterministic"] is True, f"{a['strategy_id']}: not deterministic"

    def test_expected_strategy_ids_present(self, artifact):
        expected = {
            ("midfreq_acb_2bet",        "DAILY_539"),
            ("midfreq_fourier_2bet",    "DAILY_539"),
            ("zonal_entropy_2bet",      "POWER_LOTTO"),
            ("cold_complement_2bet",    "POWER_LOTTO"),
            ("midfreq_fourier_2bet",    "POWER_LOTTO"),
            ("fourier30_markov30_2bet", "POWER_LOTTO"),
        }
        actual = {(a["strategy_id"], a["lottery_type"]) for a in artifact["implemented_adapters"]}
        assert actual == expected

    def test_bet_index_1_daily539_pick5(self, artifact):
        for a in artifact["implemented_adapters"]:
            if a["lottery_type"] == "DAILY_539":
                assert len(a["bet_index_1"]) == 5, f"{a['strategy_id']} bet-1 should have 5 picks"
                assert len(a["bet_index_2"]) == 5, f"{a['strategy_id']} bet-2 should have 5 picks"

    def test_bet_index_1_powerlotto_pick6(self, artifact):
        for a in artifact["implemented_adapters"]:
            if a["lottery_type"] == "POWER_LOTTO":
                assert len(a["bet_index_1"]) == 6, f"{a['strategy_id']} bet-1 should have 6 picks"
                assert len(a["bet_index_2"]) == 6, f"{a['strategy_id']} bet-2 should have 6 picks"

    def test_bet_index_1_daily539_range(self, artifact):
        for a in artifact["implemented_adapters"]:
            if a["lottery_type"] == "DAILY_539":
                for num in a["bet_index_1"] + a["bet_index_2"]:
                    assert 1 <= num <= 39, f"{a['strategy_id']}: number {num} out of DAILY_539 range"

    def test_bet_index_1_powerlotto_range(self, artifact):
        for a in artifact["implemented_adapters"]:
            if a["lottery_type"] == "POWER_LOTTO":
                for num in a["bet_index_1"] + a["bet_index_2"]:
                    assert 1 <= num <= 38, f"{a['strategy_id']}: number {num} out of POWER_LOTTO range"

    def test_bet_index_1_sorted(self, artifact):
        for a in artifact["implemented_adapters"]:
            assert a["bet_index_1"] == sorted(a["bet_index_1"]), (
                f"{a['strategy_id']} bet-1 not sorted: {a['bet_index_1']}"
            )
            assert a["bet_index_2"] == sorted(a["bet_index_2"]), (
                f"{a['strategy_id']} bet-2 not sorted: {a['bet_index_2']}"
            )

    def test_bet_index_1_unique(self, artifact):
        for a in artifact["implemented_adapters"]:
            assert len(set(a["bet_index_1"])) == len(a["bet_index_1"]), (
                f"{a['strategy_id']} bet-1 has duplicates: {a['bet_index_1']}"
            )
            assert len(set(a["bet_index_2"])) == len(a["bet_index_2"]), (
                f"{a['strategy_id']} bet-2 has duplicates: {a['bet_index_2']}"
            )


# ─── Section 8: blocked_or_excluded includes required exclusions ───────────────

class TestBlockedOrExcluded:
    def test_4star_excluded(self, artifact):
        blocked = artifact["blocked_or_excluded"]
        assert "4_STAR" in blocked

    def test_p108_excluded(self, artifact):
        blocked = artifact["blocked_or_excluded"]
        assert "P108" in blocked

    def test_p117_excluded(self, artifact):
        blocked = artifact["blocked_or_excluded"]
        assert "P117" in blocked

    def test_p118_excluded(self, artifact):
        blocked = artifact["blocked_or_excluded"]
        assert "P118" in blocked

    def test_rejected_excluded(self, artifact):
        blocked = artifact["blocked_or_excluded"]
        assert "rejected_strategies" in blocked

    def test_priority_7_12_deferred(self, artifact):
        blocked = artifact["blocked_or_excluded"]
        assert "priority_7_to_12" in blocked


# ─── Section 9: Markdown contains required content ────────────────────────────

class TestMarkdownContent:
    def test_md_file_exists(self):
        assert MD_ARTIFACT.exists(), f"Missing: {MD_ARTIFACT}"

    def test_contains_get_all_bets(self, md_text):
        assert "get_all_bets" in md_text

    def test_contains_phase_1_matrix(self, md_text):
        assert "Phase 1" in md_text or "phase 1" in md_text.lower()

    def test_contains_classification(self, md_text):
        assert EXPECTED_CLASSIFICATION in md_text

    def test_contains_db_rows(self, md_text):
        # Artifact was generated pre-RSR-6 cleanup; check historical value appears
        assert str(EXPECTED_DB_ROWS_AT_P128_TIME) in md_text

    def test_contains_rsr6_note(self, md_text):
        assert "RSR-6" in md_text

    def test_contains_adapter_contract(self, md_text):
        assert "adapter_contract" in md_text or "Adapter Contract" in md_text or "Contract" in md_text

    def test_contains_all_strategy_ids(self, md_text):
        strategies = [
            "midfreq_acb_2bet",
            "midfreq_fourier_2bet",
            "zonal_entropy_2bet",
            "cold_complement_2bet",
            "fourier30_markov30_2bet",
        ]
        for sid in strategies:
            assert sid in md_text, f"Markdown missing strategy_id: {sid}"


# ─── Section 10: No DB files staged ──────────────────────────────────────────

class TestNoDbStaged:
    def test_db_not_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=WORKTREE_ROOT,
        )
        staged = result.stdout.strip()
        staged_files = [f for f in staged.split("\n") if f]
        db_files = [f for f in staged_files if f.endswith(".db")]
        assert len(db_files) == 0, (
            f"DB files staged in git index — this must not happen: {db_files}"
        )


# ─── Section 11: Adapter module smoke tests ────────────────────────────────────

class TestAdapterModuleDirect:
    """Direct adapter module tests (separate from artifact — verify code directly)."""

    def test_adapter_module_exists(self):
        assert ADAPTER_MODULE.exists(), f"Missing: {ADAPTER_MODULE}"

    def test_adapter_module_imports(self, adapter_module):
        assert hasattr(adapter_module, "get_all_bets")
        assert hasattr(adapter_module, "PHASE1_STRATEGIES")
        assert hasattr(adapter_module, "PROVENANCE_SHA256")

    def test_dispatch_has_six_keys(self, adapter_module):
        assert len(adapter_module._DISPATCH) == 6

    def test_provenance_sha256_present(self, adapter_module):
        sha = adapter_module.PROVENANCE_SHA256
        assert len(sha) == 64  # SHA256 hex string

    def _make_history(self, lottery_type: str, n: int = 150) -> list[dict]:
        import itertools
        draws = []
        if lottery_type == "DAILY_539":
            pool, pick = 39, 5
        else:
            pool, pick = 38, 6
        combs = list(itertools.combinations(range(1, pool + 1), pick))
        for i in range(n):
            nums = list(combs[i % len(combs)])
            draw = {"numbers": nums}
            if lottery_type == "POWER_LOTTO":
                draw["special"] = (i % 8) + 1
            draws.append(draw)
        return draws

    @pytest.mark.parametrize("strategy_id,lottery_type", [
        ("midfreq_acb_2bet",        "DAILY_539"),
        ("midfreq_fourier_2bet",    "DAILY_539"),
        ("zonal_entropy_2bet",      "POWER_LOTTO"),
        ("cold_complement_2bet",    "POWER_LOTTO"),
        ("midfreq_fourier_2bet",    "POWER_LOTTO"),
        ("fourier30_markov30_2bet", "POWER_LOTTO"),
    ])
    def test_adapter_returns_two_bets(self, adapter_module, strategy_id, lottery_type):
        history = self._make_history(lottery_type)
        ctx = {"history": history, "lottery_type": lottery_type}
        bets = adapter_module.get_all_bets(strategy_id, ctx)
        assert len(bets) == 2

    @pytest.mark.parametrize("strategy_id,lottery_type,pick", [
        ("midfreq_acb_2bet",        "DAILY_539",    5),
        ("midfreq_fourier_2bet",    "DAILY_539",    5),
        ("zonal_entropy_2bet",      "POWER_LOTTO",  6),
        ("cold_complement_2bet",    "POWER_LOTTO",  6),
        ("midfreq_fourier_2bet",    "POWER_LOTTO",  6),
        ("fourier30_markov30_2bet", "POWER_LOTTO",  6),
    ])
    def test_adapter_correct_pick_count(self, adapter_module, strategy_id, lottery_type, pick):
        history = self._make_history(lottery_type)
        ctx = {"history": history, "lottery_type": lottery_type}
        bets = adapter_module.get_all_bets(strategy_id, ctx)
        for i, bet in enumerate(bets):
            assert len(bet) == pick, f"{strategy_id} bet-{i+1}: expected {pick} picks, got {len(bet)}"

    @pytest.mark.parametrize("strategy_id,lottery_type", [
        ("midfreq_acb_2bet",        "DAILY_539"),
        ("midfreq_fourier_2bet",    "DAILY_539"),
        ("zonal_entropy_2bet",      "POWER_LOTTO"),
        ("cold_complement_2bet",    "POWER_LOTTO"),
        ("midfreq_fourier_2bet",    "POWER_LOTTO"),
        ("fourier30_markov30_2bet", "POWER_LOTTO"),
    ])
    def test_adapter_deterministic(self, adapter_module, strategy_id, lottery_type):
        """Same draw_context -> same output (determinism guarantee)."""
        history = self._make_history(lottery_type)
        ctx = {"history": history, "lottery_type": lottery_type}
        bets1 = adapter_module.get_all_bets(strategy_id, ctx)
        bets2 = adapter_module.get_all_bets(strategy_id, ctx)
        assert bets1 == bets2, f"{strategy_id}: non-deterministic output!"

    @pytest.mark.parametrize("strategy_id,lottery_type,pool", [
        ("midfreq_acb_2bet",        "DAILY_539",    39),
        ("midfreq_fourier_2bet",    "DAILY_539",    39),
        ("zonal_entropy_2bet",      "POWER_LOTTO",  38),
        ("cold_complement_2bet",    "POWER_LOTTO",  38),
        ("midfreq_fourier_2bet",    "POWER_LOTTO",  38),
        ("fourier30_markov30_2bet", "POWER_LOTTO",  38),
    ])
    def test_adapter_numbers_in_range(self, adapter_module, strategy_id, lottery_type, pool):
        history = self._make_history(lottery_type)
        ctx = {"history": history, "lottery_type": lottery_type}
        bets = adapter_module.get_all_bets(strategy_id, ctx)
        for i, bet in enumerate(bets):
            for num in bet:
                assert 1 <= num <= pool, (
                    f"{strategy_id} bet-{i+1}: {num} out of range [1..{pool}]"
                )

    @pytest.mark.parametrize("strategy_id,lottery_type", [
        ("midfreq_acb_2bet",        "DAILY_539"),
        ("midfreq_fourier_2bet",    "DAILY_539"),
        ("zonal_entropy_2bet",      "POWER_LOTTO"),
        ("cold_complement_2bet",    "POWER_LOTTO"),
        ("midfreq_fourier_2bet",    "POWER_LOTTO"),
        ("fourier30_markov30_2bet", "POWER_LOTTO"),
    ])
    def test_adapter_numbers_sorted(self, adapter_module, strategy_id, lottery_type):
        history = self._make_history(lottery_type)
        ctx = {"history": history, "lottery_type": lottery_type}
        bets = adapter_module.get_all_bets(strategy_id, ctx)
        for i, bet in enumerate(bets):
            assert bet == sorted(bet), f"{strategy_id} bet-{i+1}: not sorted: {bet}"

    @pytest.mark.parametrize("strategy_id,lottery_type", [
        ("midfreq_acb_2bet",        "DAILY_539"),
        ("midfreq_fourier_2bet",    "DAILY_539"),
        ("zonal_entropy_2bet",      "POWER_LOTTO"),
        ("cold_complement_2bet",    "POWER_LOTTO"),
        ("midfreq_fourier_2bet",    "POWER_LOTTO"),
        ("fourier30_markov30_2bet", "POWER_LOTTO"),
    ])
    def test_adapter_numbers_unique(self, adapter_module, strategy_id, lottery_type):
        history = self._make_history(lottery_type)
        ctx = {"history": history, "lottery_type": lottery_type}
        bets = adapter_module.get_all_bets(strategy_id, ctx)
        for i, bet in enumerate(bets):
            assert len(set(bet)) == len(bet), f"{strategy_id} bet-{i+1}: duplicates: {bet}"

    def test_invalid_strategy_raises(self, adapter_module):
        """Unknown strategy_id must raise ValueError."""
        ctx = {"history": [], "lottery_type": "DAILY_539"}
        with pytest.raises(ValueError):
            adapter_module.get_all_bets("nonexistent_strategy", ctx)

    def test_wrong_lottery_type_raises(self, adapter_module):
        """Valid strategy_id with wrong lottery_type must raise ValueError."""
        ctx = {"history": [], "lottery_type": "BIG_LOTTO"}
        with pytest.raises(ValueError):
            adapter_module.get_all_bets("midfreq_acb_2bet", ctx)
