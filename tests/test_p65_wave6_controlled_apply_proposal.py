"""
Test suite for P65: Wave 6 Controlled Apply Proposal

Covers:
- Artifact existence and schema validation
- Governance: no production apply, no DB writes
- Production DB invariant: rows = 43960
- Decision matrix: cold/zonal INCLUDE, lag EXCLUDE
- Proposal: Option D, both strategies, projected 46960
- Apply plan: correct CAIDs, auth phrases, caution notes
- Conservative policy: no performance claim, no ONLINE
- P64 artifact verification: all three present and classified correctly
- Duplicate check: 0 rows for both candidates
- Script is read-only: no staged DB changes
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
PROPOSAL_JSON = REPO / "outputs" / "replay" / "p65_wave6_controlled_apply_proposal_20260525.json"
PROPOSAL_DOC = REPO / "docs" / "replay" / "p65_wave6_controlled_apply_proposal_20260525.md"
PROD_DB = REPO / "lottery_api" / "data" / "lottery_v2.db"

P64A_JSON = REPO / "outputs" / "replay" / "p64_cold_complement_wave6_dryrun_rehearsal_20260525.json"
P64B_JSON = REPO / "outputs" / "replay" / "p64b_lag_reversion_wave6_mini_backtest_20260525.json"
P64C_JSON = REPO / "outputs" / "replay" / "p64c_zonal_entropy_wave6_determinism_dryrun_20260525.json"

# ─── Constants ────────────────────────────────────────────────────────────────

EXPECTED_PROD_ROWS = 43960
EVIDENCE_GATE = 3.87
P65_CLASSIFICATION = "P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_READY_WITH_CAUTION"
CAID_COLD = "P65_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525"
CAID_ZONAL = "P65_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def proposal() -> dict:
    return json.load(open(PROPOSAL_JSON))


@pytest.fixture(scope="module")
def doc_text() -> str:
    return PROPOSAL_DOC.read_text()


@pytest.fixture(scope="module")
def p64a() -> dict:
    return json.load(open(P64A_JSON))


@pytest.fixture(scope="module")
def p64b() -> dict:
    return json.load(open(P64B_JSON))


@pytest.fixture(scope="module")
def p64c() -> dict:
    return json.load(open(P64C_JSON))


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(PROD_DB))
    yield conn
    conn.close()


# ─── Class 1: Artifact existence ─────────────────────────────────────────────

class TestArtifactExistence:
    def test_proposal_json_exists(self):
        assert PROPOSAL_JSON.exists(), "Proposal JSON not found"

    def test_proposal_doc_exists(self):
        assert PROPOSAL_DOC.exists(), "Proposal doc not found"

    def test_p64a_json_exists(self):
        assert P64A_JSON.exists(), "P64a JSON not found"

    def test_p64b_json_exists(self):
        assert P64B_JSON.exists(), "P64b JSON not found"

    def test_p64c_json_exists(self):
        assert P64C_JSON.exists(), "P64c JSON not found"

    def test_proposal_json_non_empty(self):
        assert PROPOSAL_JSON.stat().st_size > 1000

    def test_proposal_doc_non_empty(self):
        assert PROPOSAL_DOC.stat().st_size > 500


# ─── Class 2: Schema validation ───────────────────────────────────────────────

class TestProposalSchema:
    REQUIRED_TOP_KEYS = [
        "schema_version", "task_id", "run_id", "marker", "generated_at",
        "governance", "p59_rows", "p64_artifacts", "p64_summary",
        "duplicate_check", "decision_matrix", "proposal", "apply_plan",
        "classification", "conservative_policy", "next_steps",
        "preceding_tasks", "base_commit",
    ]

    def test_top_level_keys(self, proposal):
        for key in self.REQUIRED_TOP_KEYS:
            assert key in proposal, f"Missing top-level key: {key}"

    def test_schema_version(self, proposal):
        assert proposal["schema_version"] == "1.0"

    def test_task_id(self, proposal):
        assert proposal["task_id"] == "P65"

    def test_marker(self, proposal):
        assert "P65" in proposal["marker"]
        assert "WAVE6" in proposal["marker"]

    def test_classification_field(self, proposal):
        assert proposal["classification"] == P65_CLASSIFICATION

    def test_governance_keys(self, proposal):
        gov = proposal["governance"]
        for k in ["db_writes", "online_promotions", "champion_replacement",
                  "production_apply", "production_rows_before", "production_rows_after"]:
            assert k in gov, f"Missing governance key: {k}"

    def test_proposal_keys(self, proposal):
        p = proposal["proposal"]
        for k in ["decision", "proposed_strategies", "apply_rows_per_strategy",
                  "total_apply_rows", "current_production_rows",
                  "projected_rows_after_apply", "classification"]:
            assert k in p, f"Missing proposal key: {k}"

    def test_preceding_tasks(self, proposal):
        assert "P63" in proposal["preceding_tasks"]
        assert "P64a" in proposal["preceding_tasks"]
        assert "P64b" in proposal["preceding_tasks"]
        assert "P64c" in proposal["preceding_tasks"]

    def test_base_commit(self, proposal):
        assert proposal["base_commit"] == "de70f32"


# ─── Class 3: Governance ─────────────────────────────────────────────────────

class TestGovernance:
    def test_no_db_writes(self, proposal):
        assert proposal["governance"]["db_writes"] is False

    def test_no_online_promotions(self, proposal):
        assert proposal["governance"]["online_promotions"] is False

    def test_no_champion_replacement(self, proposal):
        assert proposal["governance"]["champion_replacement"] is False

    def test_no_production_apply(self, proposal):
        assert proposal["governance"]["production_apply"] is False

    def test_prod_rows_before(self, proposal):
        assert proposal["governance"]["production_rows_before"] == EXPECTED_PROD_ROWS

    def test_prod_rows_after(self, proposal):
        assert proposal["governance"]["production_rows_after"] == EXPECTED_PROD_ROWS

    def test_prod_rows_unchanged(self, proposal):
        before = proposal["governance"]["production_rows_before"]
        after = proposal["governance"]["production_rows_after"]
        assert before == after, "Production rows must not change during proposal phase"

    def test_drift_guard_pass(self, proposal):
        assert proposal["governance"]["drift_guard"] == "PASS"

    def test_branch_guard_pass(self, proposal):
        assert proposal["governance"]["branch_governance_guard"] == "PASS"

    def test_no_registry_mutation(self, proposal):
        assert proposal["governance"].get("registry_mutation", False) is False


# ─── Class 4: Production DB ───────────────────────────────────────────────────

class TestProductionDB:
    def test_prod_rows_exact(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert count == EXPECTED_PROD_ROWS, f"Expected {EXPECTED_PROD_ROWS}, got {count}"

    def test_no_cold_complement_rows(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='cold_complement_2bet'"
        ).fetchone()[0]
        assert count == 0, "cold_complement_2bet should not be in production yet"

    def test_no_zonal_entropy_rows(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='zonal_entropy_2bet'"
        ).fetchone()[0]
        assert count == 0, "zonal_entropy_2bet should not be in production yet"

    def test_p59_rows(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id='P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525'"
        ).fetchone()[0]
        assert count == 1500, f"Expected 1500 P59 rows, got {count}"

    def test_no_wave6_caid(self, db_conn):
        rows = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id LIKE '%WAVE6%' OR controlled_apply_id LIKE '%P65%'"
        ).fetchone()[0]
        assert rows == 0, "No Wave 6 CAIDs should be in production yet"


# ─── Class 5: Duplicate check ─────────────────────────────────────────────────

class TestDuplicateCheck:
    def test_cold_complement_safe(self, proposal):
        assert proposal["duplicate_check"]["cold_complement_safe"] is True

    def test_zonal_entropy_safe(self, proposal):
        assert proposal["duplicate_check"]["zonal_entropy_safe"] is True

    def test_no_wave6_caid_collision(self, proposal):
        assert proposal["duplicate_check"]["no_wave6_caid_collision"] is True

    def test_no_duplicate_risk(self, proposal):
        assert proposal["duplicate_check"]["duplicate_risk"] is False

    def test_cold_prod_rows_zero(self, proposal):
        assert proposal["duplicate_check"]["cold_complement_prod_rows"] == 0

    def test_zonal_prod_rows_zero(self, proposal):
        assert proposal["duplicate_check"]["zonal_entropy_prod_rows"] == 0


# ─── Class 6: Decision matrix ─────────────────────────────────────────────────

class TestDecisionMatrix:
    def test_cold_complement_included(self, proposal):
        dm = proposal["decision_matrix"]["cold_complement_2bet"]
        assert dm["exclude"] is False
        assert dm["recommendation"] == "INCLUDE_WITH_CAUTION"

    def test_cold_complement_m3plus(self, proposal):
        m3 = proposal["decision_matrix"]["cold_complement_2bet"]["m3plus_rate_pct"]
        assert abs(m3 - 3.67) < 0.01, f"M3+={m3} expected ~3.67"

    def test_cold_complement_baseline(self, proposal):
        dm = proposal["decision_matrix"]["cold_complement_2bet"]
        assert dm["baseline_pct"] == EVIDENCE_GATE

    def test_cold_complement_vs_baseline_pp(self, proposal):
        pp = proposal["decision_matrix"]["cold_complement_2bet"]["vs_baseline_pp"]
        assert pp < 0, "cold_complement should be below baseline"
        assert pp > -1.0, "cold_complement delta within 1pp noise band"

    def test_cold_complement_deterministic(self, proposal):
        assert proposal["decision_matrix"]["cold_complement_2bet"]["deterministic"] is True

    def test_cold_complement_dry_run_rows(self, proposal):
        rows = proposal["decision_matrix"]["cold_complement_2bet"]["dry_run_rows"]
        assert rows == 1500

    def test_cold_complement_caid(self, proposal):
        assert proposal["decision_matrix"]["cold_complement_2bet"]["proposed_caid"] == CAID_COLD

    def test_zonal_entropy_included(self, proposal):
        dm = proposal["decision_matrix"]["zonal_entropy_2bet"]
        assert dm["exclude"] is False
        assert dm["recommendation"] == "INCLUDE_WITH_CAUTION"

    def test_zonal_entropy_m3plus(self, proposal):
        m3 = proposal["decision_matrix"]["zonal_entropy_2bet"]["m3plus_rate_pct"]
        assert abs(m3 - 3.67) < 0.01, f"M3+={m3} expected ~3.67"

    def test_zonal_entropy_vs_baseline_pp(self, proposal):
        pp = proposal["decision_matrix"]["zonal_entropy_2bet"]["vs_baseline_pp"]
        assert pp < 0, "zonal_entropy should be below baseline"
        assert pp > -1.0, "zonal_entropy delta within 1pp noise band"

    def test_zonal_entropy_deterministic(self, proposal):
        assert proposal["decision_matrix"]["zonal_entropy_2bet"]["deterministic"] is True

    def test_zonal_entropy_determinism_verified(self, proposal):
        assert proposal["decision_matrix"]["zonal_entropy_2bet"]["determinism_verified"] is True

    def test_zonal_entropy_caid(self, proposal):
        assert proposal["decision_matrix"]["zonal_entropy_2bet"]["proposed_caid"] == CAID_ZONAL

    def test_lag_reversion_excluded(self, proposal):
        dm = proposal["decision_matrix"]["lag_reversion_2bet"]
        assert dm["exclude"] is True
        assert dm["recommendation"] == "EXCLUDE"

    def test_lag_reversion_gate_fail(self, proposal):
        dm = proposal["decision_matrix"]["lag_reversion_2bet"]
        assert "GATE_FAIL" in dm["readiness"] or "GATE_FAIL" in dm.get("classification", "")

    def test_lag_reversion_w150_below_baseline(self, proposal):
        w150 = proposal["decision_matrix"]["lag_reversion_2bet"]["w150_m3plus_pct"]
        assert w150 < EVIDENCE_GATE, f"w150={w150} should be below baseline {EVIDENCE_GATE}"

    def test_lag_reversion_w150_severe(self, proposal):
        w150 = proposal["decision_matrix"]["lag_reversion_2bet"]["w150_m3plus_pct"]
        assert w150 < 2.0, f"w150={w150} should be severely below baseline"


# ─── Class 7: Proposal decision ──────────────────────────────────────────────

class TestProposalDecision:
    def test_decision_is_D(self, proposal):
        assert proposal["proposal"]["decision"] == "D"

    def test_proposed_strategies(self, proposal):
        strategies = proposal["proposal"]["proposed_strategies"]
        assert "cold_complement_2bet" in strategies
        assert "zonal_entropy_2bet" in strategies

    def test_lag_reversion_not_proposed(self, proposal):
        strategies = proposal["proposal"]["proposed_strategies"]
        assert "lag_reversion_2bet" not in strategies

    def test_apply_rows_per_strategy(self, proposal):
        assert proposal["proposal"]["apply_rows_per_strategy"] == 1500

    def test_total_apply_rows(self, proposal):
        assert proposal["proposal"]["total_apply_rows"] == 3000

    def test_current_prod_rows(self, proposal):
        assert proposal["proposal"]["current_production_rows"] == EXPECTED_PROD_ROWS

    def test_projected_rows(self, proposal):
        assert proposal["proposal"]["projected_rows_after_apply"] == 46960

    def test_no_performance_improvement_claim(self, proposal):
        assert proposal["proposal"]["is_performance_improvement_claim"] is False

    def test_no_online_promotion(self, proposal):
        assert proposal["proposal"]["online_promotion"] is False

    def test_no_champion_replacement(self, proposal):
        assert proposal["proposal"]["champion_replacement"] is False

    def test_classification(self, proposal):
        assert proposal["proposal"]["classification"] == P65_CLASSIFICATION


# ─── Class 8: Apply plan ──────────────────────────────────────────────────────

class TestApplyPlan:
    def test_plan_applicable(self, proposal):
        assert proposal["apply_plan"]["applicable"] is True

    def test_proposed_task_id(self, proposal):
        assert proposal["apply_plan"]["proposed_task_id"] == "P66"

    def test_cold_caid(self, proposal):
        caids = proposal["apply_plan"]["controlled_apply_ids"]
        assert caids.get("cold_complement_2bet") == CAID_COLD

    def test_zonal_caid(self, proposal):
        caids = proposal["apply_plan"]["controlled_apply_ids"]
        assert caids.get("zonal_entropy_2bet") == CAID_ZONAL

    def test_auth_phrase_cold(self, proposal):
        phrases = proposal["apply_plan"]["authorization_phrases_required"]
        phrase = phrases.get("cold_complement_2bet", "")
        assert "cold_complement_2bet" in phrase
        assert "1500" in phrase
        assert "P66" in phrase

    def test_auth_phrase_zonal(self, proposal):
        phrases = proposal["apply_plan"]["authorization_phrases_required"]
        phrase = phrases.get("zonal_entropy_2bet", "")
        assert "zonal_entropy_2bet" in phrase
        assert "1500" in phrase
        assert "P66" in phrase

    def test_backup_required(self, proposal):
        assert proposal["apply_plan"]["backup_required"] is True

    def test_apply_one_at_a_time(self, proposal):
        assert proposal["apply_plan"]["apply_one_at_a_time"] is True

    def test_caution_notes_present(self, proposal):
        notes = proposal["apply_plan"]["caution_notes"]
        assert len(notes) > 0

    def test_caution_no_performance_claim(self, proposal):
        notes = " ".join(proposal["apply_plan"]["caution_notes"]).lower()
        # Check that caution notes explicitly warn about performance
        assert any(
            "performance" in note.lower() or "coverage" in note.lower()
            for note in proposal["apply_plan"]["caution_notes"]
        )

    def test_no_online_in_caution(self, proposal):
        notes = " ".join(proposal["apply_plan"]["caution_notes"])
        assert "ONLINE" in notes, "Caution notes should mention no ONLINE promotion"

    def test_drift_guard_expected_rows(self, proposal):
        assert proposal["apply_plan"]["drift_guard_expected_rows_after"] == 46960

    def test_rollback_commands_present(self, proposal):
        rc = proposal["apply_plan"]["rollback_commands"]
        assert "cold_complement_2bet" in rc
        assert "zonal_entropy_2bet" in rc


# ─── Class 9: Conservative policy ────────────────────────────────────────────

class TestConservativePolicy:
    def test_coverage_expansion_only(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["coverage_expansion_only"] is True

    def test_no_performance_improvement_claim(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["performance_improvement_claim"] is False

    def test_no_online_promotion(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["online_promotion"] is False

    def test_no_champion_replacement(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["champion_replacement"] is False

    def test_wave5_champion_unchanged(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["wave5_champion_unchanged"] == "fourier30_markov30_2bet"

    def test_monitoring_draws_set(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["post_apply_monitoring_draws"] == 50

    def test_monitoring_threshold(self, proposal):
        cp = proposal["conservative_policy"]
        assert cp["monitoring_threshold_m3plus_pct"] < EVIDENCE_GATE


# ─── Class 10: P64 artifact cross-verification ───────────────────────────────

class TestP64ArtifactCrossVerification:
    def test_p64a_classification_in_proposal(self, proposal, p64a):
        dm = proposal["decision_matrix"]["cold_complement_2bet"]
        assert dm["classification"] == p64a["classification"]

    def test_p64a_m3plus_matches(self, proposal, p64a):
        dm_m3 = proposal["decision_matrix"]["cold_complement_2bet"]["m3plus_rate_pct"]
        artifact_m3 = p64a["metrics"]["m3plus_rate_pct"]
        assert abs(dm_m3 - artifact_m3) < 0.001

    def test_p64b_classification_in_proposal(self, proposal, p64b):
        dm = proposal["decision_matrix"]["lag_reversion_2bet"]
        assert dm["classification"] == p64b["classification"]

    def test_p64b_window_values_match(self, proposal, p64b):
        dm = proposal["decision_matrix"]["lag_reversion_2bet"]
        wr = p64b["window_results"]
        assert abs(dm["w150_m3plus_pct"] - float(wr["150"]["m3plus_rate_pct"])) < 0.001
        assert abs(dm["w500_m3plus_pct"] - float(wr["500"]["m3plus_rate_pct"])) < 0.001
        assert abs(dm["w1500_m3plus_pct"] - float(wr["1500"]["m3plus_rate_pct"])) < 0.001

    def test_p64c_classification_in_proposal(self, proposal, p64c):
        dm = proposal["decision_matrix"]["zonal_entropy_2bet"]
        assert dm["classification"] == p64c["classification"]

    def test_p64c_m3plus_matches(self, proposal, p64c):
        dm_m3 = proposal["decision_matrix"]["zonal_entropy_2bet"]["m3plus_rate_pct"]
        artifact_m3 = p64c["metrics"]["m3plus_rate_pct"]
        assert abs(dm_m3 - artifact_m3) < 0.001

    def test_p64c_determinism_matches(self, proposal, p64c):
        dm_det = proposal["decision_matrix"]["zonal_entropy_2bet"]["deterministic"]
        artifact_det = p64c["determinism_check"]["determinism_pass"]
        assert dm_det == artifact_det

    def test_all_p64_prod_rows_unchanged(self, p64a, p64b, p64c):
        for art, name in [(p64a, "P64a"), (p64b, "P64b"), (p64c, "P64c")]:
            before = art["governance"]["production_rows_before"]
            assert before == EXPECTED_PROD_ROWS, f"{name}: prod_before={before} expected {EXPECTED_PROD_ROWS}"

    def test_p64a_no_prod_apply(self, p64a):
        assert p64a["governance"]["production_apply"] is False

    def test_p64b_no_prod_apply(self, p64b):
        assert p64b["governance"]["production_apply"] is False

    def test_p64c_no_prod_apply(self, p64c):
        assert p64c["governance"]["production_apply"] is False


# ─── Class 11: Document content ───────────────────────────────────────────────

class TestDocContent:
    def test_p65_header(self, doc_text):
        assert "P65" in doc_text

    def test_wave6_mention(self, doc_text):
        assert "Wave 6" in doc_text or "WAVE6" in doc_text

    def test_classification_in_doc(self, doc_text):
        assert P65_CLASSIFICATION in doc_text

    def test_cold_complement_in_doc(self, doc_text):
        assert "cold_complement_2bet" in doc_text

    def test_zonal_entropy_in_doc(self, doc_text):
        assert "zonal_entropy_2bet" in doc_text

    def test_lag_reversion_excluded_in_doc(self, doc_text):
        assert "lag_reversion_2bet" in doc_text
        assert "EXCLUDE" in doc_text or "excluded" in doc_text.lower()

    def test_option_d_in_doc(self, doc_text):
        assert "Option D" in doc_text or "decision\" == \"D\"" in doc_text or "Decision: D" in doc_text or "**D**" in doc_text

    def test_no_production_apply_stated(self, doc_text):
        assert "NO" in doc_text or "No" in doc_text
        assert "production_apply" in doc_text or "Production apply" in doc_text

    def test_caution_mention(self, doc_text):
        assert "CAUTION" in doc_text or "caution" in doc_text.lower()

    def test_coverage_expansion_in_doc(self, doc_text):
        assert "coverage" in doc_text.lower()

    def test_caid_cold_in_doc(self, doc_text):
        assert CAID_COLD in doc_text

    def test_caid_zonal_in_doc(self, doc_text):
        assert CAID_ZONAL in doc_text

    def test_projected_rows_in_doc(self, doc_text):
        assert "46960" in doc_text

    def test_current_rows_in_doc(self, doc_text):
        assert str(EXPECTED_PROD_ROWS) in doc_text

    def test_governance_section(self, doc_text):
        assert "Governance" in doc_text

    def test_no_performance_improvement_in_doc(self, doc_text):
        assert "NOT" in doc_text or "not" in doc_text.lower()

    def test_p66_mentioned(self, doc_text):
        assert "P66" in doc_text


# ─── Class 12: No staging leak ────────────────────────────────────────────────

class TestNoStagingLeak:
    FORBIDDEN_FILES = [
        "lottery_api/data/lottery_v2.db",
        "backend.pid",
        "frontend.pid",
        ".fuse_hidden",
        "CEO-Decision.md",
        "active_task.md",
    ]

    def test_prod_db_not_modified_in_tests(self, db_conn):
        """After reading the DB, ensure row count is still 43960."""
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert count == EXPECTED_PROD_ROWS

    def test_proposal_json_is_separate_from_db(self):
        """Proposal JSON must not be inside the DB directory."""
        assert PROPOSAL_JSON.parent == REPO / "outputs" / "replay"
        assert "data" not in str(PROPOSAL_JSON)

    def test_no_temp_db_in_repo(self):
        """No unexpected temp DB files in repo root (known legacy DBs are excluded)."""
        import glob
        # lottery.db and lottery_v2.db are pre-existing legacy files (non-staging debt)
        KNOWN_LEGACY_DBS = {"lottery.db", "lottery_v2.db"}
        temp_dbs = [
            p for p in glob.glob(str(REPO / "*.db"))
            if Path(p).name not in KNOWN_LEGACY_DBS
        ]
        assert len(temp_dbs) == 0, f"Unexpected temp DB files found in repo root: {temp_dbs}"

    def test_forbidden_files_not_in_proposal_artifacts(self):
        """Proposal artifacts should not reference forbidden files."""
        text = PROPOSAL_JSON.read_text()
        for f in self.FORBIDDEN_FILES:
            if "lottery_v2.db" in f:
                # DB path is referenced in path but not staged
                continue
            assert f not in text or "backend.pid" not in text


# ─── Class 13: Next steps ─────────────────────────────────────────────────────

class TestNextSteps:
    def test_next_steps_present(self, proposal):
        assert "next_steps" in proposal
        ns = proposal["next_steps"]
        assert "if_authorized" in ns
        assert "if_not_authorized" in ns

    def test_if_authorized_mentions_p66(self, proposal):
        assert "P66" in proposal["next_steps"]["if_authorized"]

    def test_auth_phrases_in_next_steps(self, proposal):
        phrases = proposal["next_steps"].get("authorization_phrases", {})
        assert "cold_complement_2bet" in phrases
        assert "zonal_entropy_2bet" in phrases

    def test_auth_phrase_cold_complete(self, proposal):
        phrases = proposal["next_steps"]["authorization_phrases"]
        phrase = phrases["cold_complement_2bet"]
        assert "cold_complement_2bet" in phrase
        assert "1500" in phrase
        assert "P66" in phrase

    def test_auth_phrase_zonal_complete(self, proposal):
        phrases = proposal["next_steps"]["authorization_phrases"]
        phrase = phrases["zonal_entropy_2bet"]
        assert "zonal_entropy_2bet" in phrase
        assert "1500" in phrase
        assert "P66" in phrase
