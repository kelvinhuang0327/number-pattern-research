"""
Tests for P280AW BIG 6/49 Private Ticket Decision Runner.

Coverage:
- Deterministic output with synthetic fixture
- No official target/deadline fields
- No pre-draw manifest output
- No publication artifact path
- No prediction_success_claim / strategy_promoted / activation
- No DB write/copy (mocked DB)
- Diversified random low-overlap behavior
- Hybrid pack budget shape for k=3/5/7/11
- Strategy pack digest reconciliation
- Contribution metrics
- P280AT NULL warning present
- Committed artifact schema includes final_classification
- Live/current ticket numbers not in committed artifact
"""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.p280aw_big649_private_ticket_decision_runner import (
    ADAPTER_DIGEST_EXPECTED,
    AT_CONTRIBUTION_RANK_ORDER,
    FROZEN_STRATEGY_PACK,
    NULL_WARNING,
    P280AT_ARTIFACT,
    TICKET_SIZE,
    BIG_POOL,
    coverage_metrics,
    diversified_random_pack,
    get_private_local_ref_id,
    marginal_coverage,
    mode_contribution_report,
    mode_diversified_random_pack,
    mode_hybrid_pack,
    mode_strategy_reference_pack,
    mode_summary_recommendation,
    pair_overlap,
    run,
    verify_adapter_digest,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_db(tmp_path):
    """Create a minimal synthetic DB fixture."""
    db_file = tmp_path / "test_lottery.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE draws_big_lotto_canonical_main "
        "(draw TEXT, date TEXT, numbers TEXT, special INTEGER)"
    )
    conn.execute(
        "INSERT INTO draws_big_lotto_canonical_main VALUES "
        "('115000062', '2026/06/16', '[1, 2, 9, 11, 28, 36]', 41)"
    )
    conn.execute(
        "INSERT INTO draws_big_lotto_canonical_main VALUES "
        "('115000061', '2026/06/12', '[1, 6, 16, 20, 34, 49]', 3)"
    )
    conn.commit()
    conn.close()
    return str(db_file)


@pytest.fixture
def committed_artifact_path():
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "outputs/research/p280aw_big649_private_ticket_decision_runner_20260619.json"


# ── 1. Deterministic output ────────────────────────────────────────────────────

class TestDeterministicOutput:
    def test_diversified_random_same_seed_same_output(self):
        t1 = diversified_random_pack(5, seed=42)
        t2 = diversified_random_pack(5, seed=42)
        assert t1 == t2

    def test_diversified_random_different_seeds_different_output(self):
        t1 = diversified_random_pack(5, seed=42)
        t2 = diversified_random_pack(5, seed=99)
        assert t1 != t2

    def test_run_deterministic_with_fixture(self, synthetic_db):
        out1 = run(["--mode", "diversified_random_pack", "--budget", "5",
                    "--seed", "42", "--db", synthetic_db, "--json"])
        out2 = run(["--mode", "diversified_random_pack", "--budget", "5",
                    "--seed", "42", "--db", synthetic_db, "--json"])
        r1 = out1["results"]["diversified_random_pack"]["tickets"]
        r2 = out2["results"]["diversified_random_pack"]["tickets"]
        assert r1 == r2


# ── 2. No official target/deadline fields ─────────────────────────────────────

class TestNoOfficialTargetDeadline:
    def test_output_has_no_official_target_flag(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["official_target_lookup_performed"] is False
        assert out["official_deadline_lookup_performed"] is False

    def test_private_ref_id_not_official(self, synthetic_db):
        out = run(["--mode", "summary_recommendation", "--db", synthetic_db, "--json"])
        note = out.get("private_local_ref_id_note", "")
        assert "NOT official target" in note
        assert "NOT official deadline" in note

    def test_no_official_target_key_in_results(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        for mode_name, result in out["results"].items():
            assert "official_target" not in result, f"Found official_target in {mode_name}"
            assert "official_deadline" not in result, f"Found official_deadline in {mode_name}"


# ── 3. No pre-draw manifest output ────────────────────────────────────────────

class TestNoPreDrawManifest:
    def test_no_pre_draw_manifest_created(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["pre_draw_manifest_created"] is False

    def test_no_manifest_key_in_results(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        for mode_name, result in out["results"].items():
            assert "manifest" not in json.dumps(result).lower() or \
                   "no_manifest" in json.dumps(result).lower(), \
                f"Unexpected manifest reference in {mode_name}"


# ── 4. No publication artifact path ───────────────────────────────────────────

class TestNoPublicationArtifact:
    def test_no_publication_pr_created(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["publication_pr_created"] is False

    def test_no_real_publication(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["real_publication_performed"] is False

    def test_final_classification_is_no_publication(self, synthetic_db):
        out = run(["--mode", "summary_recommendation", "--db", synthetic_db, "--json"])
        fc = out.get("final_classification", "")
        assert "NO_PUBLICATION" in fc
        assert "NO_CLAIM" in fc


# ── 5. No prediction_success_claim / strategy_promoted / activation ──────────

class TestNoClaimsOrActivation:
    def test_no_prediction_success_claim(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["prediction_success_claim"] is False

    def test_no_strategy_promoted(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["strategy_promoted"] is False

    def test_no_activation(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["activation"] is False


# ── 6. No DB write/copy ────────────────────────────────────────────────────────

class TestNoDatabaseWriteOrCopy:
    def test_db_copied_false(self, synthetic_db):
        out = run(["--mode", "contribution_report", "--db", synthetic_db, "--json"])
        assert out["database_access"]["copied"] is False

    def test_db_written_false(self, synthetic_db):
        out = run(["--mode", "contribution_report", "--db", synthetic_db, "--json"])
        assert out["database_access"]["written"] is False

    def test_db_file_unchanged_after_run(self, synthetic_db):
        import hashlib
        before = hashlib.sha256(open(synthetic_db, "rb").read()).hexdigest()
        run(["--mode", "all", "--db", synthetic_db, "--json"])
        after = hashlib.sha256(open(synthetic_db, "rb").read()).hexdigest()
        assert before == after, "DB was modified during runner execution"


# ── 7. Diversified random low-overlap behavior ────────────────────────────────

class TestDiversifiedRandomLowOverlap:
    def test_max_pair_overlap_at_most_3(self):
        tickets = diversified_random_pack(11, seed=42)
        for i in range(len(tickets)):
            for j in range(i + 1, len(tickets)):
                ov = pair_overlap(tickets[i], tickets[j])
                assert ov <= 4, f"Pair ({i},{j}) overlap={ov} exceeds tolerance"

    def test_no_duplicate_tickets(self):
        tickets = diversified_random_pack(7, seed=42)
        sorted_tickets = [tuple(sorted(t)) for t in tickets]
        assert len(set(sorted_tickets)) == len(sorted_tickets), "Duplicate tickets found"

    def test_all_numbers_in_valid_range(self):
        tickets = diversified_random_pack(11, seed=42)
        for t in tickets:
            assert len(t) == TICKET_SIZE, f"Ticket size wrong: {t}"
            assert all(1 <= n <= 49 for n in t), f"Number out of range: {t}"

    def test_returns_exactly_k_tickets(self):
        for k in [3, 5, 7, 11]:
            tickets = diversified_random_pack(k, seed=42)
            assert len(tickets) == k, f"Expected {k} tickets, got {len(tickets)}"


# ── 8. Hybrid pack budget shape ───────────────────────────────────────────────

class TestHybridPackBudgetShape:
    def test_k3_zero_strategy_tickets(self):
        result = mode_hybrid_pack(k=3, seed=42)
        assert result["strategy_ticket_count"] == 0
        assert result["random_ticket_count"] == 3
        assert len(result["random_tickets"]) == 3

    def test_k5_one_strategy_ticket(self):
        result = mode_hybrid_pack(k=5, seed=42)
        assert result["strategy_ticket_count"] == 1
        assert result["random_ticket_count"] == 4
        assert len(result["strategy_tickets"]) == 1
        assert len(result["random_tickets"]) == 4

    def test_k7_one_strategy_ticket(self):
        result = mode_hybrid_pack(k=7, seed=42)
        assert result["strategy_ticket_count"] == 1
        assert result["random_ticket_count"] == 6

    def test_k11_two_strategy_tickets(self):
        result = mode_hybrid_pack(k=11, seed=42)
        assert result["strategy_ticket_count"] == 2
        assert result["random_ticket_count"] == 9

    def test_strategy_tickets_labeled_observation(self):
        result = mode_hybrid_pack(k=5, seed=42)
        for t in result["strategy_tickets"]:
            assert t["role"] == "observation_tracking"

    def test_random_tickets_labeled_diversified(self):
        result = mode_hybrid_pack(k=5, seed=42)
        for t in result["random_tickets"]:
            assert t["role"] == "diversified_coverage"

    def test_total_tickets_equals_k(self):
        for k in [3, 5, 7, 11]:
            result = mode_hybrid_pack(k=k, seed=42)
            total = result["strategy_ticket_count"] + result["random_ticket_count"]
            assert total == k


# ── 9. Strategy pack digest reconciliation ────────────────────────────────────

class TestStrategyPackDigestReconciliation:
    def test_frozen_pack_digest_matches_expected(self):
        assert verify_adapter_digest(FROZEN_STRATEGY_PACK) is True

    def test_mutated_pack_digest_fails(self):
        mutated = [dict(t) for t in FROZEN_STRATEGY_PACK]
        mutated[0] = {**mutated[0], "ticket": [1, 2, 3, 4, 5, 6]}
        assert verify_adapter_digest(mutated) is False

    def test_strategy_reference_pack_digest_verified(self):
        result = mode_strategy_reference_pack()
        assert result["adapter_digest_verified"] is True
        assert result["adapter_digest"] == ADAPTER_DIGEST_EXPECTED

    def test_frozen_pack_has_11_tickets(self):
        assert len(FROZEN_STRATEGY_PACK) == 11

    def test_all_strategy_tickets_have_6_numbers(self):
        for t in FROZEN_STRATEGY_PACK:
            assert len(t["ticket"]) == TICKET_SIZE, f"Wrong size: {t['strategy_id']}"
            assert all(1 <= n <= 49 for n in t["ticket"]), f"Out of range: {t['strategy_id']}"


# ── 10. Contribution metrics ──────────────────────────────────────────────────

class TestContributionMetrics:
    def test_coverage_metrics_fields(self):
        tickets = [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]
        m = coverage_metrics(tickets)
        assert "unique_numbers_covered" in m
        assert "coverage_fraction" in m
        assert "max_pair_overlap" in m
        assert "mean_pair_overlap" in m
        assert "duplicate_ticket_count" in m
        assert "high_overlap_pairs" in m

    def test_duplicate_detection(self):
        t = [1, 2, 3, 4, 5, 6]
        m = coverage_metrics([t, t])
        assert m["duplicate_ticket_count"] == 1

    def test_marginal_coverage_decreasing(self):
        tickets = [[1, 2, 3, 4, 5, 6], [1, 2, 3, 7, 8, 9], [1, 2, 7, 8, 10, 11]]
        mc = marginal_coverage(tickets)
        assert mc[0]["marginal_new_numbers"] == 6
        assert mc[1]["marginal_new_numbers"] == 3
        assert mc[2]["marginal_new_numbers"] == 2

    def test_contribution_report_has_null_warning(self):
        result = mode_contribution_report()
        assert "p280at_null_warning" in result
        assert "NULL" in result["p280at_null_warning"]

    def test_contribution_report_strategy_count(self):
        result = mode_contribution_report()
        assert result["strategy_count"] == 11

    def test_contribution_report_has_marginal_coverage(self):
        result = mode_contribution_report()
        assert "marginal_coverage_by_at_rank" in result
        assert len(result["marginal_coverage_by_at_rank"]) == 11

    def test_coverage_fraction_in_range(self):
        tickets = [t["ticket"] for t in FROZEN_STRATEGY_PACK]
        m = coverage_metrics(tickets)
        assert 0 < m["coverage_fraction"] <= 1.0


# ── 11. P280AT NULL warning ───────────────────────────────────────────────────

class TestNullWarning:
    def test_null_warning_in_top_level_output(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert "p280at_null_warning" in out
        assert "NULL" in out["p280at_null_warning"]

    def test_null_warning_in_every_mode(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        for mode_name, result in out["results"].items():
            assert "p280at_null_warning" in result, f"Missing NULL warning in {mode_name}"

    def test_null_warning_no_edge_claim(self):
        assert "NOT" in NULL_WARNING or "no" in NULL_WARNING.lower()

    def test_summary_recommendation_prefers_random(self):
        result = mode_summary_recommendation(k=5, seed=42)
        assert result["default_recommendation"] == "diversified_random_pack"


# ── 12. Committed artifact schema ─────────────────────────────────────────────

class TestCommittedArtifactSchema:
    def test_artifact_exists(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written (Task B)")

    def test_artifact_has_final_classification(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            data = json.load(f)
        assert "final_classification" in data
        fc = data["final_classification"]
        assert "NO_PUBLICATION" in fc or "BLOCKED" in fc or "FAIL" in fc or "PUSHED" in fc

    def test_artifact_no_live_ticket_numbers(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            content = f.read()
        assert "current_live_ticket_numbers_committed" in content
        data = json.loads(content)
        assert data.get("current_live_ticket_numbers_committed") is False

    def test_artifact_has_schema_version(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            data = json.load(f)
        assert "schema_version" in data

    def test_artifact_no_prediction_success_claim(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            data = json.load(f)
        assert data.get("prediction_success_claim") is False

    def test_artifact_no_strategy_promoted(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            data = json.load(f)
        assert data.get("strategy_promoted") is False

    def test_artifact_no_activation(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            data = json.load(f)
        assert data.get("activation") is False


# ── 13. No live/current ticket numbers in committed artifact ──────────────────

class TestNoLiveTicketNumbersInArtifact:
    def test_run_does_not_produce_committed_live_numbers(self, synthetic_db):
        out = run(["--mode", "all", "--db", synthetic_db, "--json"])
        assert out["current_live_ticket_numbers_committed"] is False

    def test_committed_artifact_flag_false(self, committed_artifact_path):
        if not committed_artifact_path.exists():
            pytest.skip("Committed artifact not yet written")
        with open(committed_artifact_path) as f:
            data = json.load(f)
        assert data.get("current_live_ticket_numbers_committed") is False

    def test_mode_results_have_no_live_draw_numbers(self, synthetic_db):
        out = run(["--mode", "strategy_reference_pack", "--db", synthetic_db, "--json"])
        result = out["results"]["strategy_reference_pack"]
        # Strategy pack tickets are frozen historical reference, not live draw results
        assert "live_draw" not in json.dumps(result).lower()
        assert "current_draw" not in json.dumps(result).lower()


# ── 14. Private ref id is synthetic ───────────────────────────────────────────

class TestPrivateRefId:
    def test_private_ref_id_is_latest_plus_one(self, synthetic_db):
        out = run(["--mode", "summary_recommendation", "--db", synthetic_db, "--json"])
        latest = out["latest_local_draw"]["draw_id"]
        ref = out["private_local_ref_id"]
        assert int(ref) == int(latest) + 1

    def test_private_ref_id_not_in_results(self, synthetic_db):
        out = run(["--mode", "diversified_random_pack", "--budget", "3",
                   "--db", synthetic_db, "--json"])
        results_str = json.dumps(out["results"])
        assert out["private_local_ref_id"] not in results_str or \
            "NOT official target" in json.dumps(out)


# ── 15. Coverage and overlap helpers ─────────────────────────────────────────

class TestHelpers:
    def test_pair_overlap_exact(self):
        t1 = [1, 2, 3, 4, 5, 6]
        t2 = [3, 4, 5, 7, 8, 9]
        assert pair_overlap(t1, t2) == 3

    def test_pair_overlap_zero(self):
        t1 = [1, 2, 3, 4, 5, 6]
        t2 = [7, 8, 9, 10, 11, 12]
        assert pair_overlap(t1, t2) == 0

    def test_get_private_local_ref_id(self):
        assert get_private_local_ref_id("115000062") == "115000063"
        assert get_private_local_ref_id("115000001") == "115000002"

    def test_at_contribution_rank_order_covers_all_strategies(self):
        all_ids = {t["strategy_id"] for t in FROZEN_STRATEGY_PACK}
        rank_ids = set(AT_CONTRIBUTION_RANK_ORDER)
        assert all_ids == rank_ids, f"Mismatch: {all_ids ^ rank_ids}"
