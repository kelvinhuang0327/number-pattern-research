"""
Phase 48 — P0 Feature Builder Script
=====================================
Reads  : data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl
Writes : data/mlb_2025/derived/mlb_2025_per_game_predictions_phase48_p0_v1.jsonl

Each output row contains all original prediction fields plus:
  - p0_features   : the full dict from build_mlb_p0_features()
  - feature_version
  - feature_audit_hash

Hard rules:
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED     = False
  - No external API / LLM calls
  - No modification to source JSONL
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Ensure project root on path when run as a script
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from wbc_backend.features.mlb_p0_feature_builder import (
    CANDIDATE_PATCH_CREATED,
    FEATURE_VERSION,
    PRODUCTION_MODIFIED,
    build_mlb_p0_features,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
_DATA_DIR = _ROOT / "data" / "mlb_2025" / "derived"
INPUT_JSONL  = _DATA_DIR / "mlb_2025_per_game_predictions.jsonl"
OUTPUT_JSONL = _DATA_DIR / f"mlb_2025_per_game_predictions_{FEATURE_VERSION}.jsonl"


def run(
    input_path: Path = INPUT_JSONL,
    output_path: Path = OUTPUT_JSONL,
) -> dict:
    """
    Process the input JSONL, attach P0 features to every row, and write output.

    Returns a summary dict (also printed to stdout).
    """
    assert not CANDIDATE_PATCH_CREATED, "safety invariant violated"
    assert not PRODUCTION_MODIFIED,     "safety invariant violated"

    rows_written = 0
    park_known_count = 0
    park_unknown_count = 0
    sp_available_count = 0
    sp_fallback_count = 0
    season_available_count = 0
    season_fallback_count = 0
    forbidden_triggered_count = 0

    logger.info("Reading %s", input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        for raw_line in fin:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            record: dict = json.loads(raw_line)

            # build_mlb_p0_features handles its own leakage guard internally
            p0 = build_mlb_p0_features(record, context=None)

            # Collect stats
            if p0["park_factor_available"]:
                park_known_count += 1
            else:
                park_unknown_count += 1

            if p0["sp_fip_delta_available"]:
                sp_available_count += 1
            else:
                sp_fallback_count += 1

            if p0["season_game_index_available"]:
                season_available_count += 1
            else:
                season_fallback_count += 1

            if p0["audit_notes"]["ignored_forbidden_fields"]:
                forbidden_triggered_count += 1

            # Build output row: original fields + enriched p0 block
            out_row: dict = dict(record)
            out_row["p0_features"]         = p0
            out_row["feature_version"]     = p0["feature_version"]
            out_row["feature_audit_hash"]  = p0["feature_audit_hash"]

            fout.write(json.dumps(out_row, ensure_ascii=False) + "\n")
            rows_written += 1

    total = rows_written
    summary = {
        "input_path":               str(input_path),
        "output_path":              str(output_path),
        "feature_version":          FEATURE_VERSION,
        "rows_written":             total,
        "candidate_patch_created":  CANDIDATE_PATCH_CREATED,
        "production_modified":      PRODUCTION_MODIFIED,
        # Park factor
        "park_known_count":         park_known_count,
        "park_unknown_count":       park_unknown_count,
        "park_availability_rate":   round(park_known_count / max(total, 1), 4),
        # SP FIP delta
        "sp_fip_available_count":   sp_available_count,
        "sp_fip_fallback_count":    sp_fallback_count,
        "sp_fip_availability_rate": round(sp_available_count / max(total, 1), 4),
        # Season index
        "season_idx_available_count": season_available_count,
        "season_idx_fallback_count":  season_fallback_count,
        "season_idx_availability_rate": round(season_available_count / max(total, 1), 4),
        # Leakage guard
        "forbidden_fields_triggered": forbidden_triggered_count,
    }

    logger.info("Wrote %d rows to %s", total, output_path)
    logger.info("Park factor availability : %.1f%%", summary["park_availability_rate"] * 100)
    logger.info("SP FIP availability     : %.1f%%", summary["sp_fip_availability_rate"] * 100)
    logger.info("Season index availability: %.1f%%", summary["season_idx_availability_rate"] * 100)
    logger.info("Forbidden fields triggered: %d rows", forbidden_triggered_count)

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 48 P0 feature builder")
    parser.add_argument("--input",  default=str(INPUT_JSONL),  help="Input JSONL path")
    parser.add_argument("--output", default=str(OUTPUT_JSONL), help="Output JSONL path")
    args = parser.parse_args()

    result = run(Path(args.input), Path(args.output))
    print(json.dumps(result, indent=2))
