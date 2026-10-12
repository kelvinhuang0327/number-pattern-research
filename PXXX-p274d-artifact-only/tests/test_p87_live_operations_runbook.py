"""
tests/test_p87_live_operations_runbook.py
P87 Live Operations Runbook — 12 governance assertions
"""
import json
import os
import pytest

RUNBOOK_MD = "docs/replay/p87_live_operations_runbook_20260526.md"
RUNBOOK_JSON = "outputs/replay/p87_live_operations_runbook_20260526.json"


@pytest.fixture(scope="module")
def runbook_json():
    assert os.path.exists(RUNBOOK_JSON), f"JSON artifact missing: {RUNBOOK_JSON}"
    with open(RUNBOOK_JSON, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def runbook_md():
    assert os.path.exists(RUNBOOK_MD), f"Markdown artifact missing: {RUNBOOK_MD}"
    with open(RUNBOOK_MD, encoding="utf-8") as fh:
        return fh.read()


# 1. Markdown artifact exists
def test_markdown_artifact_exists():
    assert os.path.exists(RUNBOOK_MD), f"Markdown artifact not found: {RUNBOOK_MD}"


# 2. JSON artifact exists
def test_json_artifact_exists():
    assert os.path.exists(RUNBOOK_JSON), f"JSON artifact not found: {RUNBOOK_JSON}"


# 3. Classification = P87_LIVE_OPERATIONS_RUNBOOK_READY
def test_classification(runbook_json):
    assert runbook_json["classification"] == "P87_LIVE_OPERATIONS_RUNBOOK_READY", (
        f"Expected P87_LIVE_OPERATIONS_RUNBOOK_READY, got {runbook_json['classification']}"
    )


# 4. Baseline replay_rows = 46962
def test_baseline_replay_rows(runbook_json):
    baseline = runbook_json["production_baseline"]
    assert baseline["replay_rows"] == 46962, (
        f"Expected replay_rows=46962, got {baseline['replay_rows']}"
    )


# 5. Baseline max_draw = 115000041
def test_baseline_max_draw(runbook_json):
    baseline = runbook_json["production_baseline"]
    assert baseline["power_lotto_max_draw"] == 115000041, (
        f"Expected power_lotto_max_draw=115000041, got {baseline['power_lotto_max_draw']}"
    )


# 6. Backend port 8002 documented
def test_port_8002_documented(runbook_json, runbook_md):
    backend = runbook_json["backend"]
    assert backend["port"] == 8002, f"Expected port=8002, got {backend['port']}"
    assert "8002" in runbook_md, "Port 8002 not found in markdown"


# 7. Port 8000 warning documented
def test_port_8000_warning_documented(runbook_json, runbook_md):
    backend = runbook_json["backend"]
    assert "8000" in backend["port_warning"], (
        f"Port 8000 warning missing from JSON backend section"
    )
    assert "8000" in runbook_md, "Port 8000 warning not found in markdown"


# 8. Slash date format documented
def test_slash_date_format_documented(runbook_json, runbook_md):
    backend = runbook_json["backend"]
    assert backend["date_format"] == "YYYY/MM/DD", (
        f"Expected date_format=YYYY/MM/DD, got {backend['date_format']}"
    )
    assert "2026/05/21" in runbook_md, "Slash date example not in markdown"
    assert "YYYY/MM/DD" in runbook_md, "Date format string not in markdown"


# 9. SOURCE_DECISION_REQUIRED documented
def test_source_decision_required_documented(runbook_json, runbook_md):
    decision_tree = runbook_json["decision_tree"]
    assert "SOURCE_DECISION_REQUIRED" in decision_tree, (
        "SOURCE_DECISION_REQUIRED missing from JSON decision_tree"
    )
    assert decision_tree["SOURCE_DECISION_REQUIRED"]["action"] == "STOP", (
        "SOURCE_DECISION_REQUIRED action must be STOP"
    )
    assert "SOURCE_DECISION_REQUIRED" in runbook_md, (
        "SOURCE_DECISION_REQUIRED not found in markdown"
    )


# 10. Forbidden DB writes documented
def test_forbidden_db_writes_documented(runbook_json, runbook_md):
    forbidden = runbook_json["forbidden_actions"]
    db_write_forbidden = any(
        "db_write" in f or "INSERT" in f or "direct_db" in f for f in forbidden
    )
    assert db_write_forbidden, "Direct DB write must be in forbidden_actions"
    assert runbook_json["governance"]["no_db_writes"] is True, (
        "governance.no_db_writes must be True"
    )
    assert "direct DB write" in runbook_md.lower() or "no direct db write" in runbook_md.lower() or (
        "Direct DB write" in runbook_md
    ), "Forbidden DB write not documented in markdown"


# 11. git reset --hard / git clean forbidden documented
def test_reset_hard_git_clean_forbidden(runbook_json, runbook_md):
    forbidden = runbook_json["forbidden_actions"]
    reset_forbidden = any("reset_hard" in f or "reset --hard" in f for f in forbidden)
    clean_forbidden = any("git_clean" in f or "git clean" in f for f in forbidden)
    assert reset_forbidden, "git reset --hard must be in forbidden_actions"
    assert clean_forbidden, "git clean must be in forbidden_actions"
    assert "reset --hard" in runbook_md, "git reset --hard not documented in markdown"
    assert "git clean" in runbook_md, "git clean not documented in markdown"


# 12. Evidence chain includes P84, P85, P86
def test_evidence_chain_includes_p84_p85_p86(runbook_json, runbook_md):
    evidence = runbook_json["evidence_chain"]
    assert "P84" in evidence, "P84 missing from evidence_chain"
    assert "P85" in evidence, "P85 missing from evidence_chain"
    assert "P86" in evidence, "P86 missing from evidence_chain"
    assert "P84" in runbook_md, "P84 not mentioned in markdown"
    assert "P85" in runbook_md, "P85 not mentioned in markdown"
    assert "P86" in runbook_md, "P86 not mentioned in markdown"
