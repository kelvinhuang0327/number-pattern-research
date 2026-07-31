"""
tests/test_p116_powerlotto_oos_monitoring_design.py

Tests for P116: POWER_LOTTO OOS Monitoring Design.
All tests are read-only. No DB writes.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

# ── Artifact paths ──────────────────────────────────────────────────────────
JSON_PATH = Path("outputs/replay/p116_powerlotto_oos_monitoring_design_20260527.json")
MD_PATH = Path("docs/replay/p116_powerlotto_oos_monitoring_design_20260527.md")
SCRIPT_PATH = Path("scripts/p116_powerlotto_oos_monitoring_design.py")

VALID_CLASSIFICATIONS = {
    "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY",
    "P116_POWERLOTTO_OOS_MONITORING_DESIGN_PARTIAL",
    "P116_POWERLOTTO_OOS_MONITORING_DESIGN_INCONCLUSIVE",
    "P116_BLOCKED_BY_PREFLIGHT",
    "P116_BLOCKED_BY_DB_DRIFT",
    "P116_BLOCKED_BY_GUARD_FAILURE",
    "P116_BLOCKED_BY_TEST_FAILURE",
    "P116_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P116_BLOCKED_BY_SCOPE_VIOLATION",
    "P116_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

SQL_WRITE_VERBS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE|VACUUM|PRAGMA\s+writable_schema)\b",
    re.IGNORECASE,
)

DB_PATH = Path("lottery_api/data/lottery_v2.db")


# ── Fixture ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def artifact():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def md_content():
    assert MD_PATH.exists(), f"MD artifact missing: {MD_PATH}"
    return MD_PATH.read_text()


@pytest.fixture(scope="session")
def script_content():
    assert SCRIPT_PATH.exists(), f"Script missing: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text()


@pytest.fixture(scope="session")
def designs(artifact):
    return {d["strategy_id"]: d for d in artifact.get("per_strategy_monitoring_design", [])}


# ── Existence tests ──────────────────────────────────────────────────────────
def test_json_artifact_exists():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"


def test_md_artifact_exists():
    assert MD_PATH.exists(), f"MD artifact missing: {MD_PATH}"


def test_script_exists():
    assert SCRIPT_PATH.exists(), f"Script missing: {SCRIPT_PATH}"


# ── JSON parse ───────────────────────────────────────────────────────────────
def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# ── task_id ──────────────────────────────────────────────────────────────────
def test_task_id(artifact):
    assert artifact.get("task_id") == "P116_POWERLOTTO_OOS_MONITORING_DESIGN"


# ── classification ───────────────────────────────────────────────────────────
def test_classification_valid(artifact):
    assert artifact.get("classification") in VALID_CLASSIFICATIONS


def test_final_classification_valid(artifact):
    assert artifact.get("final_classification") in VALID_CLASSIFICATIONS


def test_classification_ready(artifact):
    assert artifact.get("classification") == "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY"


# ── References ───────────────────────────────────────────────────────────────
def test_p112_reference_exists(artifact):
    ref = artifact.get("p112_reference")
    assert isinstance(ref, dict)
    assert "classification" in ref
    assert "artifact_path" in ref


def test_p113_reference_exists(artifact):
    ref = artifact.get("p113_reference")
    assert isinstance(ref, dict)
    assert "classification" in ref
    assert "artifact_path" in ref


def test_p114_reference_exists(artifact):
    ref = artifact.get("p114_reference")
    assert isinstance(ref, dict)
    assert "classification" in ref
    assert "artifact_path" in ref


def test_p112_classification_in_reference(artifact):
    assert "P112" in artifact["p112_reference"]["classification"]


def test_p113_classification_in_reference(artifact):
    assert "P113" in artifact["p113_reference"]["classification"]


def test_p114_classification_in_reference(artifact):
    assert "P114" in artifact["p114_reference"]["classification"]


# ── Governance flags ─────────────────────────────────────────────────────────
def test_db_writes_false(artifact):
    assert artifact.get("db_writes") is False


def test_replay_rows_before(artifact):
    assert artifact.get("replay_rows_before") == 54462


def test_replay_rows_after(artifact):
    assert artifact.get("replay_rows_after") == 54462


def test_replay_rows_unchanged(artifact):
    assert artifact["replay_rows_before"] == artifact["replay_rows_after"]


def test_no_strategy_promotion(artifact):
    assert artifact.get("no_strategy_promotion") is True


def test_no_lifecycle_mutation(artifact):
    assert artifact.get("no_lifecycle_mutation") is True


def test_no_registry_mutation(artifact):
    assert artifact.get("no_registry_mutation") is True


def test_no_4star_backtest(artifact):
    assert artifact.get("no_4star_backtest") is True


def test_no_special3_p108_rerun(artifact):
    assert artifact.get("no_special3_p108_rerun") is True


def test_no_p115_quarantine_work(artifact):
    assert artifact.get("no_p115_quarantine_work") is True


def test_source_unknown_caveat_preserved(artifact):
    assert artifact.get("source_unknown_caveat_preserved") is True


# ── Monitored lottery type ────────────────────────────────────────────────────
def test_monitored_lottery_type(artifact):
    assert artifact.get("monitored_lottery_type") == "POWER_LOTTO"


# ── Monitoring candidates ─────────────────────────────────────────────────────
def test_monitoring_candidates_exists(artifact):
    assert isinstance(artifact.get("monitoring_candidates"), list)


def test_monitoring_candidates_include_midfreq(artifact):
    assert "midfreq_fourier_mk_3bet" in artifact["monitoring_candidates"]


def test_monitoring_candidates_include_pp3(artifact):
    assert "pp3_freqort_4bet" in artifact["monitoring_candidates"]


# ── Per-strategy monitoring design ───────────────────────────────────────────
def test_per_strategy_monitoring_design_exists(artifact):
    designs = artifact.get("per_strategy_monitoring_design")
    assert isinstance(designs, list)
    assert len(designs) == 2


def test_every_design_has_strategy_id(designs):
    for sid, d in designs.items():
        assert "strategy_id" in d, f"strategy_id missing for {sid}"


def test_every_design_has_oos_status(designs):
    for sid, d in designs.items():
        assert "oos_status" in d, f"oos_status missing for {sid}"


def test_every_design_has_minimum_new_draws(designs):
    for sid, d in designs.items():
        assert "minimum_new_draws" in d, f"minimum_new_draws missing for {sid}"


def test_every_design_has_preferred_new_draws(designs):
    for sid, d in designs.items():
        assert "preferred_new_draws" in d, f"preferred_new_draws missing for {sid}"


def test_every_design_has_promotion_discussion_minimum(designs):
    for sid, d in designs.items():
        assert "promotion_discussion_minimum" in d, f"promotion_discussion_minimum missing for {sid}"


def test_every_design_has_rolling_windows(designs):
    for sid, d in designs.items():
        assert isinstance(d.get("rolling_windows"), list), f"rolling_windows missing for {sid}"
        assert len(d["rolling_windows"]) > 0


def test_every_design_has_metrics(designs):
    for sid, d in designs.items():
        assert isinstance(d.get("metrics"), list), f"metrics missing for {sid}"
        assert len(d["metrics"]) > 0


def test_every_design_has_pass_criteria(designs):
    for sid, d in designs.items():
        assert isinstance(d.get("pass_criteria"), list), f"pass_criteria missing for {sid}"
        assert len(d["pass_criteria"]) > 0


def test_every_design_has_watch_criteria(designs):
    for sid, d in designs.items():
        assert isinstance(d.get("watch_criteria"), list), f"watch_criteria missing for {sid}"
        assert len(d["watch_criteria"]) > 0


def test_every_design_has_fail_criteria(designs):
    for sid, d in designs.items():
        assert isinstance(d.get("fail_criteria"), list), f"fail_criteria missing for {sid}"
        assert len(d["fail_criteria"]) > 0


def test_every_design_promotion_authorized_false(designs):
    for sid, d in designs.items():
        assert d.get("promotion_authorized") is False, f"promotion_authorized not False for {sid}"


def test_future_promotion_proposal_requirements_exists(designs):
    for sid, d in designs.items():
        reqs = d.get("future_promotion_proposal_requirements")
        assert isinstance(reqs, list), f"future_promotion_proposal_requirements missing for {sid}"
        assert len(reqs) > 0


def test_demotion_or_quarantine_triggers_exists(designs):
    for sid, d in designs.items():
        triggers = d.get("demotion_or_quarantine_triggers")
        assert isinstance(triggers, list), f"demotion_or_quarantine_triggers missing for {sid}"
        assert len(triggers) > 0


# ── midfreq_fourier_mk_3bet specifics ────────────────────────────────────────
def test_midfreq_oos_status_design_ready(designs):
    d = designs["midfreq_fourier_mk_3bet"]
    assert d["oos_status"] == "DESIGN_READY"


def test_midfreq_stability_stable_positive(designs):
    d = designs["midfreq_fourier_mk_3bet"]
    assert d["p114_stability_label"] == "STABLE_POSITIVE"


def test_midfreq_p114_decision(designs):
    d = designs["midfreq_fourier_mk_3bet"]
    assert d["p114_decision"] == "READY_FOR_OOS_MONITORING_DESIGN"


def test_midfreq_minimum_new_draws_gte_30(designs):
    d = designs["midfreq_fourier_mk_3bet"]
    assert d["minimum_new_draws"] >= 30


def test_midfreq_promotion_discussion_minimum_gte_80(designs):
    d = designs["midfreq_fourier_mk_3bet"]
    assert d["promotion_discussion_minimum"] >= 80


# ── pp3_freqort_4bet specifics ────────────────────────────────────────────────
def test_pp3_oos_status_controlled_observation(designs):
    d = designs["pp3_freqort_4bet"]
    assert d["oos_status"] == "CONTROLLED_OBSERVATION_READY"


def test_pp3_stability_mostly_positive(designs):
    d = designs["pp3_freqort_4bet"]
    assert d["p114_stability_label"] == "MOSTLY_POSITIVE"


def test_pp3_p114_decision(designs):
    d = designs["pp3_freqort_4bet"]
    assert d["p114_decision"] == "READY_FOR_CONTROLLED_OBSERVATION_PLAN"


def test_pp3_minimum_new_draws_gte_40(designs):
    d = designs["pp3_freqort_4bet"]
    assert d["minimum_new_draws"] >= 40


def test_pp3_promotion_discussion_minimum_gte_100(designs):
    d = designs["pp3_freqort_4bet"]
    assert d["promotion_discussion_minimum"] >= 100


# ── Global monitoring invariants ──────────────────────────────────────────────
def test_global_monitoring_invariants_exists(artifact):
    inv = artifact.get("global_monitoring_invariants")
    assert isinstance(inv, list)
    assert len(inv) > 0


# ── Next task recommendations ─────────────────────────────────────────────────
def test_next_task_recommendations_exists(artifact):
    recs = artifact.get("next_task_recommendations")
    assert isinstance(recs, list)
    assert len(recs) > 0


# ── Limitations ───────────────────────────────────────────────────────────────
def test_limitations_exists(artifact):
    lims = artifact.get("limitations")
    assert isinstance(lims, list)
    assert len(lims) > 0


# ── Live DB invariants ────────────────────────────────────────────────────────
def test_live_db_replay_rows():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert rows == 54462, f"replay_rows={rows}, expected 54462"


# ── Script safety ─────────────────────────────────────────────────────────────
def test_script_has_no_sql_write_verbs(script_content):
    matches = SQL_WRITE_VERBS.findall(script_content)
    assert not matches, f"SQL write verbs found in script: {matches}"


def test_script_has_json_out_arg(script_content):
    assert "--json-out" in script_content


def test_script_uses_mode_ro(script_content):
    assert "mode=ro" in script_content


# ── MD content checks ─────────────────────────────────────────────────────────
def test_md_no_promotion_authorization(md_content):
    # Must not contain statements authorizing promotion in this task
    assert "promotion_authorized: True" not in md_content
    assert "promotion authorized" not in md_content.lower() or "NOT authorized" in md_content or "does NOT authorize" in md_content


def test_md_contains_p108_blocked(md_content):
    assert "P108" in md_content
    assert "BLOCKED" in md_content or "blocked" in md_content


def test_md_contains_4star_unauthorized(md_content):
    content_upper = md_content.upper()
    assert "4_STAR" in content_upper or "4_STAR BACKTEST" in content_upper
    assert "NOT AUTHORIZED" in md_content or "unauthorized" in md_content.lower()


def test_md_contains_p115_separate(md_content):
    assert "P115" in md_content
    assert "separate" in md_content.lower() or "SEPARATE" in md_content


def test_md_contains_final_classification(md_content):
    assert "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY" in md_content


def test_md_contains_project_context_lock(md_content):
    assert "PROJECT_CONTEXT_LOCK" in md_content


# ── No DB files staged ────────────────────────────────────────────────────────
def test_no_db_files_staged():
    """
    Verify that db files are not in HEAD commit staged changes.
    This checks the current index if inside a git repo.
    """
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip().splitlines()
    db_files = [f for f in staged if any(f.endswith(ext) for ext in [".db", ".wal", ".shm"]) or "lottery_history" in f]
    assert not db_files, f"DB/history files staged: {db_files}"
