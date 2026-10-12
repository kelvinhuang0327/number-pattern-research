"""
wbc_backend/recommendation/p20_artifact_manifest.py

P20 Artifact Manifest Generator — computes SHA-256 hashes and validates
all artifacts produced/consumed by the P20 daily paper orchestrator.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from wbc_backend.recommendation.p20_daily_paper_orchestrator_contract import (
    P20ArtifactManifest,
)

# ---------------------------------------------------------------------------
# Artifact type / phase constants
# ---------------------------------------------------------------------------

ARTIFACT_TYPE_CSV = "csv"
ARTIFACT_TYPE_JSON = "json"
ARTIFACT_TYPE_MD = "markdown"

PHASE_P16_6 = "p16_6"
PHASE_P19 = "p19"
PHASE_P17_REPLAY = "p17_replay"
PHASE_P20 = "p20"


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error_code: str = ""
    error_message: str = ""


# ---------------------------------------------------------------------------
# Hash helper
# ---------------------------------------------------------------------------

def hash_file(path: str) -> str:
    """Compute SHA-256 of a file. Returns empty string if file missing."""
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_size(path: str) -> int:
    p = Path(path)
    return p.stat().st_size if p.exists() else 0


# ---------------------------------------------------------------------------
# Artifact spec
# ---------------------------------------------------------------------------

def _make_artifact_entry(
    artifact_path: str,
    artifact_type: str,
    phase: str,
    required: bool,
) -> dict:
    exists = Path(artifact_path).exists()
    return {
        "artifact_path": artifact_path,
        "artifact_type": artifact_type,
        "phase": phase,
        "sha256": hash_file(artifact_path) if exists else "",
        "file_size_bytes": _file_size(artifact_path),
        "required": required,
        "exists": exists,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_artifact_manifest(
    run_date: str,
    p16_6_dir: str,
    p19_dir: str,
    p17_replay_dir: str,
    p20_output_dir: str,
) -> P20ArtifactManifest:
    """Build manifest covering all P16.6 / P19 / P17-replay / P20 artifacts."""
    entries: list[dict] = []

    # P16.6
    entries.append(_make_artifact_entry(
        f"{p16_6_dir}/recommendation_rows.csv", ARTIFACT_TYPE_CSV, PHASE_P16_6, required=True))
    entries.append(_make_artifact_entry(
        f"{p16_6_dir}/recommendation_summary.json", ARTIFACT_TYPE_JSON, PHASE_P16_6, required=True))

    # P19
    entries.append(_make_artifact_entry(
        f"{p19_dir}/enriched_simulation_ledger.csv", ARTIFACT_TYPE_CSV, PHASE_P19, required=True))
    entries.append(_make_artifact_entry(
        f"{p19_dir}/identity_enrichment_summary.json", ARTIFACT_TYPE_JSON, PHASE_P19, required=True))
    entries.append(_make_artifact_entry(
        f"{p19_dir}/p19_gate_result.json", ARTIFACT_TYPE_JSON, PHASE_P19, required=True))

    # P17 replay
    entries.append(_make_artifact_entry(
        f"{p17_replay_dir}/paper_recommendation_ledger.csv", ARTIFACT_TYPE_CSV, PHASE_P17_REPLAY, required=True))
    entries.append(_make_artifact_entry(
        f"{p17_replay_dir}/paper_recommendation_ledger_summary.json", ARTIFACT_TYPE_JSON, PHASE_P17_REPLAY, required=True))
    entries.append(_make_artifact_entry(
        f"{p17_replay_dir}/ledger_gate_result.json", ARTIFACT_TYPE_JSON, PHASE_P17_REPLAY, required=True))

    # P20 outputs (may not exist yet when manifest is first built)
    entries.append(_make_artifact_entry(
        f"{p20_output_dir}/daily_paper_summary.json", ARTIFACT_TYPE_JSON, PHASE_P20, required=True))
    entries.append(_make_artifact_entry(
        f"{p20_output_dir}/daily_paper_summary.md", ARTIFACT_TYPE_MD, PHASE_P20, required=True))
    entries.append(_make_artifact_entry(
        f"{p20_output_dir}/artifact_manifest.json", ARTIFACT_TYPE_JSON, PHASE_P20, required=True))
    entries.append(_make_artifact_entry(
        f"{p20_output_dir}/p20_gate_result.json", ARTIFACT_TYPE_JSON, PHASE_P20, required=True))

    required_present = sum(1 for e in entries if e["required"] and e["exists"])
    required_missing = sum(1 for e in entries if e["required"] and not e["exists"])

    return P20ArtifactManifest(
        run_date=run_date,
        artifacts=tuple(entries),
        total_artifacts=len(entries),
        required_artifacts_present=required_present,
        required_artifacts_missing=required_missing,
        manifest_sha256="",  # filled after serialisation
        paper_only=True,
        production_ready=False,
    )


def validate_manifest(manifest: P20ArtifactManifest) -> ValidationResult:
    """Validate that all required input artifacts exist."""
    missing = [
        e["artifact_path"]
        for e in manifest.artifacts
        if e["required"] and not e["exists"] and e["phase"] != PHASE_P20
    ]
    if missing:
        return ValidationResult(
            valid=False,
            error_code="P20_FAIL_INPUT_MISSING",
            error_message=f"Required artifacts missing: {missing}",
        )
    if manifest.production_ready:
        return ValidationResult(
            valid=False,
            error_code="P20_BLOCKED_CONTRACT_VIOLATION",
            error_message="production_ready must be False",
        )
    if not manifest.paper_only:
        return ValidationResult(
            valid=False,
            error_code="P20_BLOCKED_CONTRACT_VIOLATION",
            error_message="paper_only must be True",
        )
    return ValidationResult(valid=True)


def summarize_manifest(manifest: P20ArtifactManifest) -> dict:
    """Return a JSON-serialisable summary of the manifest."""
    return {
        "run_date": manifest.run_date,
        "total_artifacts": manifest.total_artifacts,
        "required_artifacts_present": manifest.required_artifacts_present,
        "required_artifacts_missing": manifest.required_artifacts_missing,
        "manifest_sha256": manifest.manifest_sha256,
        "paper_only": manifest.paper_only,
        "production_ready": manifest.production_ready,
        "artifacts": list(manifest.artifacts),
    }
