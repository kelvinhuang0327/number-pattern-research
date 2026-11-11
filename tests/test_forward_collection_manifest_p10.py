"""
Tests for P10-D: Forward-Only Activation Manifest
scripts/run_forward_collection_manifest_p10.py

Guards:
- No network call
- No TSL crawler modification
- Includes pregame + closing windows (critical)
- paper_only enforced
- Duplicate snapshot policy deterministic
- Failure taxonomy complete
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_forward_collection_manifest_p10 import (
    CLOSING_WINDOWS,
    EXPECTED_TAXONOMY_KEYS,
    FAILURE_REASON_TAXONOMY,
    MIN_PAIR_COVERAGE_PCT,
    MIN_PAIRS_FOR_CLV,
    MIN_TIMESTAMP_COVERAGE_PCT,
    PREGAME_WINDOWS,
    PaperOnlyViolationError,
    build_forward_collection_manifest,
    build_snapshot_filename,
    run_forward_collection_manifest,
)

# ── Fixed test datetime for determinism ───────────────────────────────────────
_DT = datetime(2026, 3, 15, 20, 30, 0, tzinfo=timezone.utc)
_DT2 = datetime(2026, 3, 15, 20, 31, 0, tzinfo=timezone.utc)  # different minute


class TestManifestDeterministic:
    def test_manifest_same_inputs_same_output(self):
        m1 = build_forward_collection_manifest(run_date=_DT)
        m2 = build_forward_collection_manifest(run_date=_DT)
        assert m1 == m2

    def test_manifest_different_run_date_different_output(self):
        m1 = build_forward_collection_manifest(run_date=_DT)
        m2 = build_forward_collection_manifest(run_date=_DT2)
        assert m1["run_date"] != m2["run_date"]

    def test_manifest_is_dict(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert isinstance(m, dict)

    def test_manifest_task_p10d(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["task"] == "P10-D"


class TestNoNetworkCall:
    def test_network_call_false_in_manifest(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["network_call"] is False

    def test_no_requests_import_in_script(self):
        script = (Path(__file__).parent.parent / "scripts" / "run_forward_collection_manifest_p10.py").read_text()
        assert "import requests" not in script
        assert "from requests" not in script

    def test_no_socket_import_in_script(self):
        script = (Path(__file__).parent.parent / "scripts" / "run_forward_collection_manifest_p10.py").read_text()
        assert "import socket" not in script

    def test_no_urllib_import_in_script(self):
        script = (Path(__file__).parent.parent / "scripts" / "run_forward_collection_manifest_p10.py").read_text()
        assert "import urllib" not in script
        assert "from urllib" not in script


class TestNoCrawlerModification:
    def test_crawler_modified_false_in_manifest(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["crawler_modified"] is False

    def test_production_write_false(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["production_write"] is False

    def test_no_tsl_crawler_import_in_script(self):
        script = (Path(__file__).parent.parent / "scripts" / "run_forward_collection_manifest_p10.py").read_text()
        assert "import tsl_crawler" not in script
        assert "from tsl_crawler" not in script

    def test_script_does_not_call_crawl(self):
        script = (Path(__file__).parent.parent / "scripts" / "run_forward_collection_manifest_p10.py").read_text()
        assert "crawl(" not in script
        assert ".crawl(" not in script


class TestPregameAndClosingWindows:
    def test_manifest_has_pregame_windows(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert len(m["pregame_windows"]) >= 2

    def test_manifest_includes_pregame_d2(self):
        m = build_forward_collection_manifest(run_date=_DT)
        labels = [w["label"] for w in m["pregame_windows"]]
        assert "pregame_d2" in labels

    def test_pregame_d2_is_critical(self):
        m = build_forward_collection_manifest(run_date=_DT)
        for w in m["pregame_windows"]:
            if w["label"] == "pregame_d2":
                assert w["priority"] == "CRITICAL"
                assert w["critical"] is True
                break

    def test_manifest_includes_decision_window(self):
        m = build_forward_collection_manifest(run_date=_DT)
        labels = [w["label"] for w in m["pregame_windows"]]
        assert "decision" in labels

    def test_decision_window_is_critical(self):
        m = build_forward_collection_manifest(run_date=_DT)
        for w in m["pregame_windows"]:
            if w["label"] == "decision":
                assert w["priority"] == "CRITICAL"
                break

    def test_manifest_has_closing_windows(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert len(m["closing_windows"]) >= 1

    def test_closing_final_present(self):
        m = build_forward_collection_manifest(run_date=_DT)
        labels = [w["label"] for w in m["closing_windows"]]
        assert "closing_final" in labels

    def test_closing_final_is_critical(self):
        m = build_forward_collection_manifest(run_date=_DT)
        for w in m["closing_windows"]:
            if w["label"] == "closing_final":
                assert w["priority"] == "CRITICAL"
                assert w["critical"] is True
                break


class TestPaperOnly:
    def test_paper_only_true_in_manifest(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["paper_only"] is True

    def test_paper_only_false_raises(self):
        with pytest.raises(PaperOnlyViolationError):
            build_forward_collection_manifest(paper_only=False, run_date=_DT)

    def test_output_path_plan_paper_only_flag(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["output_path_plan"]["paper_only_path"] is True

    def test_run_forward_collection_manifest_paper_only_true(self):
        result = run_forward_collection_manifest()
        assert result["paper_only"] is True


class TestDuplicateSnapshotPolicy:
    def test_build_snapshot_filename_deterministic(self):
        name1 = build_snapshot_filename("G001", "ML", "closing_final", _DT)
        name2 = build_snapshot_filename("G001", "ML", "closing_final", _DT)
        assert name1 == name2

    def test_build_snapshot_filename_differs_by_market(self):
        ml = build_snapshot_filename("G001", "ML", "closing_final", _DT)
        rl = build_snapshot_filename("G001", "RL", "closing_final", _DT)
        assert ml != rl

    def test_build_snapshot_filename_differs_by_window(self):
        c = build_snapshot_filename("G001", "ML", "closing_final", _DT)
        p = build_snapshot_filename("G001", "ML", "pregame_d2", _DT)
        assert c != p

    def test_build_snapshot_filename_differs_by_match(self):
        a = build_snapshot_filename("G001", "ML", "closing_final", _DT)
        b = build_snapshot_filename("G002", "ML", "closing_final", _DT)
        assert a != b

    def test_build_snapshot_filename_same_minute_bucket(self):
        dt_same_min = datetime(2026, 3, 15, 20, 30, 45, tzinfo=timezone.utc)
        name1 = build_snapshot_filename("G001", "ML", "closing_final", _DT)
        name2 = build_snapshot_filename("G001", "ML", "closing_final", dt_same_min)
        assert name1 == name2  # same minute → same filename → duplicate detected

    def test_duplicate_policy_in_manifest(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert "duplicate_snapshot_policy" in m

    def test_duplicate_policy_deterministic_flag(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["duplicate_snapshot_policy"]["deterministic"] is True

    def test_duplicate_policy_rule_skip(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["duplicate_snapshot_policy"]["rule"] == "SKIP_IF_EXISTS"

    def test_replay_safe_append_mode(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert m["replay_safe_append_policy"]["mode"] == "APPEND_ONLY"
        assert m["replay_safe_append_policy"]["overwrite"] is False


class TestFailureTaxonomy:
    def test_taxonomy_has_crawler_fetch_failed(self):
        assert "CRAWLER_FETCH_FAILED" in FAILURE_REASON_TAXONOMY

    def test_taxonomy_has_paper_only_violation(self):
        assert "PAPER_ONLY_VIOLATION" in FAILURE_REASON_TAXONOMY

    def test_taxonomy_has_post_game_proxy(self):
        assert "POST_GAME_PROXY_MISCLASSIFY" in FAILURE_REASON_TAXONOMY

    def test_taxonomy_has_duplicate_snapshot(self):
        assert "DUPLICATE_SNAPSHOT" in FAILURE_REASON_TAXONOMY

    def test_taxonomy_has_api_timeout(self):
        assert "API_TIMEOUT" in FAILURE_REASON_TAXONOMY

    def test_taxonomy_has_closing_window_outside_range(self):
        assert "CLOSING_WINDOW_OUTSIDE_RANGE" in FAILURE_REASON_TAXONOMY

    def test_taxonomy_complete_8_entries(self):
        assert len(FAILURE_REASON_TAXONOMY) == 8

    def test_taxonomy_in_manifest(self):
        m = build_forward_collection_manifest(run_date=_DT)
        assert "failure_reason_taxonomy" in m
        assert len(m["failure_reason_taxonomy"]) == 8


class TestCLVThresholds:
    def test_min_pairs_matches_p8_p9(self):
        assert MIN_PAIRS_FOR_CLV == 200

    def test_min_coverage_matches_p8_p9(self):
        assert MIN_PAIR_COVERAGE_PCT == 90.0

    def test_min_timestamp_matches_p8_p9(self):
        assert MIN_TIMESTAMP_COVERAGE_PCT == 95.0

    def test_thresholds_in_manifest(self):
        m = build_forward_collection_manifest(run_date=_DT)
        thresholds = m["clv_gate_thresholds"]
        assert thresholds["min_pairs"] == 200
        assert thresholds["min_pair_coverage_pct"] == 90.0


class TestOutputFile:
    def test_output_written_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            path = tf.name
        result = run_forward_collection_manifest(output_path=path)
        data = json.loads(Path(path).read_text())
        assert data["paper_only"] is True
        assert data["task"] == "P10-D"

    def test_output_json_valid(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            path = tf.name
        run_forward_collection_manifest(output_path=path)
        data = json.loads(Path(path).read_text())
        assert isinstance(data, dict)
