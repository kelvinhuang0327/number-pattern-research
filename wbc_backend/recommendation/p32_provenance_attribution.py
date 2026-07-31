"""
P32 Provenance / Attribution Writer.

Builds and validates provenance records for the Retrosheet 2024 game log source.
Writes provenance JSON with required attribution fields.

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

RETROSHEET_SOURCE_NAME = "Retrosheet"
RETROSHEET_SEASON = 2024
RETROSHEET_LICENSE = "ATTRIBUTION_REQUIRED"
RETROSHEET_SOURCE_URL = "https://www.retrosheet.org/gamelogs/index.html"
RETROSHEET_ATTRIBUTION_TEXT = (
    "The information used here was obtained free of charge from and is "
    "copyrighted by Retrosheet. Interested parties may contact Retrosheet at "
    "www.retrosheet.org."
)

PROVENANCE_FILENAME = "mlb_2024_retrosheet_provenance.json"


# ---------------------------------------------------------------------------
# Provenance record dataclass
# ---------------------------------------------------------------------------


@dataclass
class RetroSheetProvenanceRecord:
    """Provenance record for a Retrosheet game log source file."""

    source_name: str
    season: int
    attribution_required: bool
    license_status: str
    source_url_or_reference: str
    attribution_text: str
    source_path: str
    source_file_exists: bool
    source_file_mtime: Optional[str]   # ISO timestamp or None
    downloaded_at: str                  # ISO timestamp when record was built
    no_odds_included: bool
    no_predictions_included: bool
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError("CONTRACT VIOLATION: production_ready must be False.")
        if not self.paper_only:
            raise ValueError("CONTRACT VIOLATION: paper_only must be True.")
        if not self.attribution_required:
            raise ValueError(
                "CONTRACT VIOLATION: Retrosheet requires attribution. "
                "attribution_required must be True."
            )
        if not self.no_odds_included:
            raise ValueError(
                "CONTRACT VIOLATION: Retrosheet game logs do not include odds. "
                "no_odds_included must be True."
            )
        if not self.no_predictions_included:
            raise ValueError(
                "CONTRACT VIOLATION: no_predictions_included must be True."
            )

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "season": self.season,
            "attribution_required": self.attribution_required,
            "license_status": self.license_status,
            "source_url_or_reference": self.source_url_or_reference,
            "attribution_text": self.attribution_text,
            "source_path": self.source_path,
            "source_file_exists": self.source_file_exists,
            "source_file_mtime": self.source_file_mtime,
            "downloaded_at": self.downloaded_at,
            "no_odds_included": self.no_odds_included,
            "no_predictions_included": self.no_predictions_included,
            "paper_only": self.paper_only,
            "production_ready": self.production_ready,
        }


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def build_retrosheet_provenance_record(source_path: str | Path) -> RetroSheetProvenanceRecord:
    """
    Build a provenance record for a Retrosheet game log file.

    Works whether or not the source file actually exists — records state honestly.
    """
    p = Path(source_path)
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    file_exists = p.exists()
    file_mtime: Optional[str] = None
    if file_exists:
        mtime = os.path.getmtime(p)
        file_mtime = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    return RetroSheetProvenanceRecord(
        source_name=RETROSHEET_SOURCE_NAME,
        season=RETROSHEET_SEASON,
        attribution_required=True,
        license_status=RETROSHEET_LICENSE,
        source_url_or_reference=RETROSHEET_SOURCE_URL,
        attribution_text=RETROSHEET_ATTRIBUTION_TEXT,
        source_path=str(p),
        source_file_exists=file_exists,
        source_file_mtime=file_mtime,
        downloaded_at=now_ts,
        no_odds_included=True,
        no_predictions_included=True,
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
    )


def validate_retrosheet_attribution(record: RetroSheetProvenanceRecord) -> tuple[bool, str]:
    """
    Validate that the provenance record meets attribution requirements.

    Returns:
        (is_valid, reason_if_invalid)
    """
    if record.source_name != RETROSHEET_SOURCE_NAME:
        return False, f"Expected source_name={RETROSHEET_SOURCE_NAME!r}, got {record.source_name!r}"
    if not record.attribution_required:
        return False, "attribution_required must be True for Retrosheet."
    if record.license_status != RETROSHEET_LICENSE:
        return False, f"Expected license_status={RETROSHEET_LICENSE!r}, got {record.license_status!r}"
    if RETROSHEET_SOURCE_URL not in record.source_url_or_reference:
        return False, f"Source URL must reference {RETROSHEET_SOURCE_URL!r}."
    if not record.attribution_text:
        return False, "attribution_text must not be empty."
    if not record.no_odds_included:
        return False, "no_odds_included must be True for Retrosheet game logs."
    if not record.no_predictions_included:
        return False, "no_predictions_included must be True."
    if record.production_ready:
        return False, "production_ready must be False."
    if not record.paper_only:
        return False, "paper_only must be True."
    return True, ""


def write_provenance_record(record: RetroSheetProvenanceRecord, output_dir: Path) -> Path:
    """
    Write provenance record to JSON in output_dir.
    """
    is_valid, reason = validate_retrosheet_attribution(record)
    if not is_valid:
        raise ValueError(f"Provenance validation failed: {reason}")

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / PROVENANCE_FILENAME
    out.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    logger.info("Wrote provenance record: %s", out)
    return out


def summarize_provenance(record: RetroSheetProvenanceRecord) -> str:
    """Return a human-readable provenance summary string."""
    status = "AVAILABLE" if record.source_file_exists else "MISSING"
    return (
        f"Source: {record.source_name} (season={record.season})\n"
        f"  License: {record.license_status}\n"
        f"  Attribution required: {record.attribution_required}\n"
        f"  URL: {record.source_url_or_reference}\n"
        f"  Source file: {record.source_path} [{status}]\n"
        f"  No odds: {record.no_odds_included}\n"
        f"  No predictions: {record.no_predictions_included}\n"
        f"  paper_only: {record.paper_only}\n"
        f"  production_ready: {record.production_ready}\n"
    )
