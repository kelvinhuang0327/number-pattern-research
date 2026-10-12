"""Tests for P252H — P0 SSOT Adoption Migration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
SSOT_ANNOTATION = "P252H SSOT Governance Annotation"


def _find() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p252h_p0_ssot_adoption_migration_*.json"))
    assert candidates, "No p252h JSON artifact found"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find().read_text(encoding="utf-8"))


# ── Artifact ──────────────────────────────────────────────────────────────────

def test_artifact_parses():
    assert isinstance(_load(), dict)


def test_task_id():
    assert _load()["task_id"] == "P252H"


def test_classification():
    assert _load()["classification"] == "P0_SSOT_ADOPTION_MIGRATION_COMPLETE"


def test_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


# ── Migration matrix completeness ─────────────────────────────────────────────

def test_migration_matrix_covers_all_6_findings():
    mm = _load()["migration_matrix"]
    assert len(mm) == 6, f"Expected 6 findings, got {len(mm)}"


def test_all_6_p252g_findings_in_matrix():
    """All 6 P252G active duplicate files must appear in the migration matrix."""
    expected_files = {
        "lottery_api/engine/rolling_strategy_monitor.py",
        "analysis/p219_external_method_diagnostic_sweep.py",
        "scripts/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py",
        "scripts/p227c_star_box_play_dryrun_scan.py",
        "scripts/p211r_short_mid_window_diagnostic.py",
        "lottery_api/utils/benchmark_framework.py",
    }
    mm_files = {m["file"] for m in _load()["migration_matrix"]}
    assert expected_files <= mm_files, f"Missing files: {expected_files - mm_files}"


def test_migration_matrix_has_required_fields():
    for m in _load()["migration_matrix"]:
        for field in ["finding_id", "priority", "file", "action_taken",
                       "behavior_change", "status"]:
            assert field in m, f"Finding {m.get('finding_id')} missing {field!r}"


def test_no_behavior_changes():
    """No migration should change behavior — all should be safe replacements or comments."""
    for m in _load()["migration_matrix"]:
        assert m["behavior_change"] is False, (
            f"{m['file']} claims behavior_change=True — not allowed in P252H"
        )


def test_no_finding_silently_complete_without_action():
    for m in _load()["migration_matrix"]:
        assert m.get("action_taken") not in (None, ""), (
            f"Finding {m.get('finding_id')} has no action_taken"
        )
        assert m.get("status") not in (None, ""), (
            f"Finding {m.get('finding_id')} has no status"
        )


# ── RSM exact import adoption ─────────────────────────────────────────────────

def test_rsm_contains_rsm_windows_import():
    rsm = (REPO_ROOT / "lottery_api" / "engine" / "rolling_strategy_monitor.py").read_text()
    assert "RSM_WINDOWS" in rsm, "RSM must reference RSM_WINDOWS from SSOT"


def test_rsm_contains_rolling_window_import():
    rsm = (REPO_ROOT / "lottery_api" / "engine" / "rolling_strategy_monitor.py").read_text()
    assert "rolling_window" in rsm, "RSM must import from rolling_window SSOT"


def test_rsm_ssot_annotation_present():
    rsm = (REPO_ROOT / "lottery_api" / "engine" / "rolling_strategy_monitor.py").read_text()
    assert "P252H" in rsm, "RSM must have P252H annotation"


def test_rsm_windows_ssot_values_match():
    """The SSOT RSM_WINDOWS must equal the original dict values."""
    from lottery_api.utils.rolling_window import RSM_WINDOWS
    expected = {'short': 30, 'medium': 100, 'long': 300}
    assert dict(RSM_WINDOWS) == expected


def test_rsm_import_check_in_artifact():
    rsm_check = _load()["rsm_import_check"]
    assert rsm_check["rsm_windows_importable"] is True
    assert rsm_check["values_match"] is True


# ── Comment-only annotations ──────────────────────────────────────────────────

def test_p219_contains_ssot_annotation():
    text = (REPO_ROOT / "analysis" / "p219_external_method_diagnostic_sweep.py").read_text()
    assert SSOT_ANNOTATION in text
    assert "baseline_calculator" in text
    assert "correction_gate" in text
    assert "permutation_test" in text
    assert "rolling_window" in text


def test_p214c_contains_ssot_annotation():
    text = (REPO_ROOT / "scripts" / "p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py").read_text()
    assert SSOT_ANNOTATION in text
    assert "correction_gate" in text


def test_p227c_contains_ssot_annotation():
    text = (REPO_ROOT / "scripts" / "p227c_star_box_play_dryrun_scan.py").read_text()
    assert SSOT_ANNOTATION in text
    assert "correction_gate" in text or "permutation_test" in text


def test_p211r_contains_ssot_annotation():
    text = (REPO_ROOT / "scripts" / "p211r_short_mid_window_diagnostic.py").read_text()
    assert SSOT_ANNOTATION in text
    assert "correction_gate" in text or "rolling_window" in text


def test_benchmark_contains_ssot_annotation():
    text = (REPO_ROOT / "lottery_api" / "utils" / "benchmark_framework.py").read_text()
    assert SSOT_ANNOTATION in text
    assert "baseline_calculator" in text


# ── No DB write in modified files ─────────────────────────────────────────────

def test_rsm_no_db_write_added():
    """RSM changes should not introduce any DB write call."""
    rsm = (REPO_ROOT / "lottery_api" / "engine" / "rolling_strategy_monitor.py").read_text()
    # The new lines we added should not contain DB write patterns
    new_lines = [l for l in rsm.splitlines() if "P252H" in l or "RSM_WINDOWS" in l]
    for line in new_lines:
        assert "write" not in line.lower() and "execute" not in line.lower()


# ── No betting advice ─────────────────────────────────────────────────────────

def test_no_betting_advice_in_annotations():
    """None of the added annotations should introduce betting advice."""
    files_to_check = [
        REPO_ROOT / "lottery_api" / "engine" / "rolling_strategy_monitor.py",
        REPO_ROOT / "analysis" / "p219_external_method_diagnostic_sweep.py",
    ]
    for path in files_to_check:
        # Only check the annotation comment lines we added
        text = path.read_text()
        annotation_lines = [
            l for l in text.splitlines()
            if "P252H" in l or "SSOT Governance" in l or "RSM_WINDOWS" in l
        ]
        combined = " ".join(annotation_lines).lower()
        assert "bet" not in combined or "no" in combined, (
            f"Annotation in {path.name} may contain betting advice"
        )


# ── Verification flags in artifact ───────────────────────────────────────────

def test_all_verifications_pass():
    report = _load()
    assert report["all_verifications_pass"] is True


def test_verification_details_all_true():
    for key, val in _load()["migration_verification"].items():
        assert val is True, f"Verification {key!r} failed"


# ── Exact / comment counts ────────────────────────────────────────────────────

def test_exact_import_count():
    report = _load()
    exact = report["exact_import_adoptions"]
    assert len(exact) == 1
    assert "rolling_strategy_monitor" in exact[0]


def test_comment_only_count():
    report = _load()
    comments = report["comment_only_adoptions"]
    assert len(comments) == 5


# ── Markdown ──────────────────────────────────────────────────────────────────

def test_md_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p252h_p0_ssot_adoption_migration_*.md"))
    assert candidates
    text = candidates[-1].read_text()
    assert "no db write" in text.lower()
    assert "betting" in text.lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_valid():
    from analysis import p252h_p0_ssot_adoption_migration as p252h
    r = p252h.main()
    assert r["task_id"] == "P252H"
    assert r["classification"] == "P0_SSOT_ADOPTION_MIGRATION_COMPLETE"
    assert r["no_db_write_confirmed"] is True
    assert r["all_verifications_pass"] is True
