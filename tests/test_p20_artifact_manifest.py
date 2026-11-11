"""
tests/test_p20_artifact_manifest.py

Unit tests for p20_artifact_manifest module.
"""
import json
import tempfile
from pathlib import Path

import pytest

from wbc_backend.recommendation.p20_artifact_manifest import (
    build_artifact_manifest,
    hash_file,
    summarize_manifest,
    validate_manifest,
    ValidationResult,
)
from wbc_backend.recommendation.p20_daily_paper_orchestrator_contract import (
    P20ArtifactManifest,
)


# ---------------------------------------------------------------------------
# hash_file
# ---------------------------------------------------------------------------

class TestHashFile:
    def test_returns_empty_for_missing_file(self, tmp_path):
        result = hash_file(str(tmp_path / "nonexistent.csv"))
        assert result == ""

    def test_returns_hex_string_for_existing_file(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("col1,col2\n1,2\n")
        h = hash_file(str(f))
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self, tmp_path):
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        a.write_text("hello")
        b.write_text("hello")
        assert hash_file(str(a)) == hash_file(str(b))

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        a.write_text("hello")
        b.write_text("world")
        assert hash_file(str(a)) != hash_file(str(b))


# ---------------------------------------------------------------------------
# Helpers: create realistic phase dirs
# ---------------------------------------------------------------------------

def _make_p16_6_dir(root: Path) -> Path:
    d = root / "p16_6"
    d.mkdir()
    (d / "recommendation_rows.csv").write_text("game_id,model_p\n1,0.6\n")
    (d / "recommendation_summary.json").write_text(
        json.dumps({"gate": "P16_6_PAPER_RECOMMENDATION_GATE_READY"})
    )
    return d


def _make_p19_dir(root: Path) -> Path:
    d = root / "p19"
    d.mkdir()
    (d / "enriched_simulation_ledger.csv").write_text("game_id,p_model\n1,0.6\n")
    (d / "identity_enrichment_summary.json").write_text(json.dumps({"method": "POSITIONAL"}))
    (d / "p19_gate_result.json").write_text(
        json.dumps({"gate_decision": "P19_IDENTITY_JOIN_REPAIR_READY"})
    )
    return d


def _make_p17_replay_dir(root: Path) -> Path:
    d = root / "p17_replay"
    d.mkdir()
    (d / "paper_recommendation_ledger.csv").write_text("game_id,pnl\n1,1.0\n")
    (d / "paper_recommendation_ledger_summary.json").write_text(
        json.dumps({"p17_gate": "P17_PAPER_LEDGER_READY"})
    )
    (d / "ledger_gate_result.json").write_text(
        json.dumps({"p17_gate": "P17_PAPER_LEDGER_READY"})
    )
    return d


# ---------------------------------------------------------------------------
# build_artifact_manifest
# ---------------------------------------------------------------------------

class TestBuildArtifactManifest:
    def test_all_input_artifacts_present(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest(
            run_date="2026-05-12",
            p16_6_dir=str(p16),
            p19_dir=str(p19),
            p17_replay_dir=str(p17),
            p20_output_dir=str(out),
        )

        assert isinstance(manifest, P20ArtifactManifest)
        assert manifest.run_date == "2026-05-12"
        assert manifest.total_artifacts > 0
        assert manifest.paper_only is True
        assert manifest.production_ready is False

    def test_existing_input_artifacts_have_sha256(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        input_entries = [e for e in manifest.artifacts if e["exists"] and e["phase"] != "p20"]
        for entry in input_entries:
            assert entry["sha256"] != "", f"Missing hash for {entry['artifact_path']}"

    def test_missing_p20_output_artifacts_not_required_to_block(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        # Input artifacts should all be present
        input_entries = [e for e in manifest.artifacts if e["phase"] != "p20"]
        present = [e for e in input_entries if e["exists"]]
        assert len(present) == len(input_entries)

    def test_required_artifacts_missing_counted(self, tmp_path):
        p16 = tmp_path / "p16_6_empty"
        p16.mkdir()
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        assert manifest.required_artifacts_missing > 0


# ---------------------------------------------------------------------------
# validate_manifest
# ---------------------------------------------------------------------------

class TestValidateManifest:
    def test_valid_when_all_inputs_present(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        result = validate_manifest(manifest)
        assert result.valid is True

    def test_invalid_when_input_missing(self, tmp_path):
        p16 = tmp_path / "p16_6_empty"
        p16.mkdir()
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        result = validate_manifest(manifest)
        assert result.valid is False
        assert "P20_FAIL_INPUT_MISSING" in result.error_code

    def test_returns_validation_result_type(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        result = validate_manifest(manifest)
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# summarize_manifest
# ---------------------------------------------------------------------------

class TestSummarizeManifest:
    def test_returns_dict_with_required_keys(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        summary = summarize_manifest(manifest)

        for key in ["run_date", "total_artifacts", "required_artifacts_present",
                    "required_artifacts_missing", "paper_only", "production_ready", "artifacts"]:
            assert key in summary, f"Missing key: {key}"

    def test_json_serialisable(self, tmp_path):
        p16 = _make_p16_6_dir(tmp_path)
        p19 = _make_p19_dir(tmp_path)
        p17 = _make_p17_replay_dir(tmp_path)
        out = tmp_path / "p20_out"

        manifest = build_artifact_manifest("2026-05-12", str(p16), str(p19), str(p17), str(out))
        summary = summarize_manifest(manifest)
        # Should not raise
        serialised = json.dumps(summary)
        assert len(serialised) > 0
