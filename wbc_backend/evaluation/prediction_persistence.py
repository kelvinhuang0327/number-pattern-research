"""
Phase 39: MLB Per-Game Prediction Persistence
=============================================
Persists every per-game model prediction probability during MLB backtest
so that Brier / BSS / ECE / log-loss / calibration experiments can be
recomputed from raw rows without re-running the model.

Hard Rules:
  - Do NOT change model prediction values.
  - Do NOT improve / patch the model.
  - Do NOT call external API / LLM.
  - Do NOT bypass BSS safety gate.
  - Do NOT fabricate model probabilities if not computed.

Schema version: phase39-v1
Output format: JSONL (one JSON object per line)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from wbc_backend.evaluation.metrics import (
    brier_score as _metrics_brier_score,
    brier_skill_score as _metrics_bss,
    log_loss_score as _metrics_log_loss,
    expected_calibration_error as _metrics_ece,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "phase39-v1"
SEASON = 2025

# ─── Default output path ────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PREDICTIONS_PATH = (
    _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
)


# ══════════════════════════════════════════════════════════════════════════════
# § Prediction Row Schema (Task 2)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PredictionRow:
    """
    Canonical per-game prediction row.

    Required fields (validation will fail if missing/invalid):
      - model_home_prob
      - market_home_prob_no_vig
      - home_win
      - game_id or dedupe_key

    All probabilities are in [0.0, 1.0].
    market_home_prob_no_vig + market_away_prob_no_vig must ≈ 1.0.
    """
    schema_version: str = SCHEMA_VERSION
    season: int = SEASON
    # Identity
    game_date: str = ""                        # YYYY-MM-DD
    game_id: str = ""                          # e.g. "MLB2025_0001_2025-04-01_BOS_NYY"
    dedupe_key: str = ""                       # "YYYY-MM-DD|Away|Home"
    home_team: str = ""
    away_team: str = ""
    # Outcome (post-game, required)
    home_win: int = -1                         # 0 or 1
    # Model prediction (required)
    model_home_prob: float = -1.0
    # Market baseline (required)
    market_home_prob_no_vig: float = -1.0
    market_away_prob_no_vig: float = -1.0
    # Raw odds (optional — not in GameRecord, stored as empty string if unavailable)
    home_ml: str = ""
    away_ml: str = ""
    # Model metadata
    model_version: str = ""
    feature_version: str = "marl_elo_woba_fip_rsi_v1"
    split_id: str = ""                         # "window_1", "window_2", …
    train_window_start: str = ""
    train_window_end: str = ""
    test_window_start: str = ""
    test_window_end: str = ""
    # Timing
    prediction_time_utc: str = ""
    odds_snapshot_time_utc: str = ""
    # Provenance
    source_backtest: str = "full_backtest.FullBacktestEngine"
    # Integrity
    audit_hash: str = ""                       # sha256 of deterministic fields


# ══════════════════════════════════════════════════════════════════════════════
# § Core Functions (Task 3)
# ══════════════════════════════════════════════════════════════════════════════

def compute_audit_hash(row: PredictionRow) -> str:
    """
    Compute a deterministic sha256 audit hash over the identity + probability fields.

    Fields hashed (always in this fixed order, to ensure determinism):
      game_id, game_date, home_team, away_team, home_win,
      model_home_prob, market_home_prob_no_vig, market_away_prob_no_vig,
      split_id, schema_version
    """
    parts = "|".join([
        str(row.game_id),
        str(row.game_date),
        str(row.home_team),
        str(row.away_team),
        str(row.home_win),
        f"{row.model_home_prob:.8f}",
        f"{row.market_home_prob_no_vig:.8f}",
        f"{row.market_away_prob_no_vig:.8f}",
        str(row.split_id),
        str(row.schema_version),
    ])
    digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_prediction_row(
    *,
    game_date: str,
    game_id: str,
    home_team: str,
    away_team: str,
    home_win: int,
    model_home_prob: float,
    market_home_prob_no_vig: float,
    market_away_prob_no_vig: float,
    home_ml: str = "",
    away_ml: str = "",
    model_version: str = "",
    split_id: str = "",
    train_window_start: str = "",
    train_window_end: str = "",
    test_window_start: str = "",
    test_window_end: str = "",
    prediction_time_utc: str = "",
    odds_snapshot_time_utc: str = "",
    source_backtest: str = "full_backtest.FullBacktestEngine",
) -> PredictionRow:
    """
    Build a PredictionRow from backtest loop variables.
    Computes dedupe_key and audit_hash automatically.
    """
    dedupe_key = f"{game_date}|{away_team}|{home_team}"
    # market_away = 1 - market_home (already no-vig by construction)
    market_away = round(1.0 - market_home_prob_no_vig, 8)
    if abs(market_home_prob_no_vig + market_away_prob_no_vig - 1.0) < 1e-4:
        # Use supplied value if it's already correct
        market_away = market_away_prob_no_vig

    row = PredictionRow(
        schema_version=SCHEMA_VERSION,
        season=SEASON,
        game_date=game_date,
        game_id=game_id,
        dedupe_key=dedupe_key,
        home_team=home_team,
        away_team=away_team,
        home_win=int(home_win),
        model_home_prob=round(float(model_home_prob), 8),
        market_home_prob_no_vig=round(float(market_home_prob_no_vig), 8),
        market_away_prob_no_vig=round(float(market_away), 8),
        home_ml=str(home_ml),
        away_ml=str(away_ml),
        model_version=str(model_version),
        feature_version="marl_elo_woba_fip_rsi_v1",
        split_id=str(split_id),
        train_window_start=str(train_window_start),
        train_window_end=str(train_window_end),
        test_window_start=str(test_window_start),
        test_window_end=str(test_window_end),
        prediction_time_utc=str(prediction_time_utc),
        odds_snapshot_time_utc=str(odds_snapshot_time_utc),
        source_backtest=str(source_backtest),
        audit_hash="",
    )
    row.audit_hash = compute_audit_hash(row)
    return row


def validate_prediction_row(row: PredictionRow) -> list[str]:
    """
    Validate a PredictionRow. Returns list of error strings (empty = valid).

    Checks:
      - model_home_prob ∈ [0, 1] and set
      - market_home_prob_no_vig ∈ [0, 1] and set
      - market_away_prob_no_vig ∈ [0, 1] and set
      - market_home + market_away ≈ 1.0 (within 1%)
      - home_win ∈ {0, 1}
      - game_id or dedupe_key is non-empty
      - home_team and away_team are non-empty
    """
    errors: list[str] = []

    # Required probability: model
    if row.model_home_prob < 0 or row.model_home_prob > 1.0:
        errors.append(
            f"model_home_prob={row.model_home_prob:.4f} not in [0,1] or not set."
        )

    # Required probability: market home
    if row.market_home_prob_no_vig < 0 or row.market_home_prob_no_vig > 1.0:
        errors.append(
            f"market_home_prob_no_vig={row.market_home_prob_no_vig:.4f} not in [0,1]."
        )

    # Required probability: market away
    if row.market_away_prob_no_vig < 0 or row.market_away_prob_no_vig > 1.0:
        errors.append(
            f"market_away_prob_no_vig={row.market_away_prob_no_vig:.4f} not in [0,1]."
        )

    # Market probs must sum to ~1.0
    if (
        0 <= row.market_home_prob_no_vig <= 1.0
        and 0 <= row.market_away_prob_no_vig <= 1.0
    ):
        total = row.market_home_prob_no_vig + row.market_away_prob_no_vig
        if abs(total - 1.0) > 0.01:
            errors.append(
                f"market_home_prob_no_vig + market_away_prob_no_vig = {total:.6f} ≠ 1.0 "
                f"(tolerance 0.01)."
            )

    # Required: outcome label
    if row.home_win not in (0, 1):
        errors.append(
            f"home_win={row.home_win!r} must be 0 or 1."
        )

    # Required: identity
    if not row.game_id.strip() and not row.dedupe_key.strip():
        errors.append("Both game_id and dedupe_key are empty — need at least one identifier.")

    # Required: team names
    if not row.home_team.strip():
        errors.append("home_team is empty.")
    if not row.away_team.strip():
        errors.append("away_team is empty.")

    return errors


def write_prediction_rows(
    rows: list[PredictionRow],
    path: Path,
    backup: bool = True,
) -> int:
    """
    Write prediction rows to JSONL file.

    Rules:
      - Creates parent directories if needed.
      - If file exists and backup=True, renames existing file to *.bak before writing.
      - Returns number of rows written.
      - Does NOT overwrite original source CSV files.

    Raises:
        ValueError: if rows list is empty.
        RuntimeError: if path is inside a protected source directory.
    """
    _assert_not_source_path(path)

    if not rows:
        raise ValueError("rows list is empty — nothing to write.")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing file
    if backup and path.exists():
        backup_path = path.with_suffix(".jsonl.bak")
        path.rename(backup_path)
        logger.info("[PredictionPersistence] Backed up existing file to %s", backup_path)

    n_written = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            errors = validate_prediction_row(row)
            if errors:
                logger.warning(
                    "[PredictionPersistence] Skipping invalid row %s: %s",
                    row.game_id,
                    errors,
                )
                continue
            f.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
            n_written += 1

    logger.info(
        "[PredictionPersistence] Wrote %d/%d rows to %s",
        n_written,
        len(rows),
        path,
    )
    return n_written


def load_prediction_rows(path: Path) -> list[PredictionRow]:
    """
    Load prediction rows from a JSONL file.
    Returns list of PredictionRow (invalid rows are skipped with a warning).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")

    rows: list[PredictionRow] = []
    n_skipped = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                row = PredictionRow(**{
                    k: v for k, v in data.items()
                    if k in PredictionRow.__dataclass_fields__
                })
                errors = validate_prediction_row(row)
                if errors:
                    logger.warning(
                        "[PredictionPersistence] Line %d invalid: %s", lineno, errors
                    )
                    n_skipped += 1
                    continue
                rows.append(row)
            except Exception as e:
                logger.warning(
                    "[PredictionPersistence] Line %d parse error: %s", lineno, e
                )
                n_skipped += 1

    logger.info(
        "[PredictionPersistence] Loaded %d rows (%d skipped) from %s",
        len(rows),
        n_skipped,
        path,
    )
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# § Duplicate Detection Utility
# ══════════════════════════════════════════════════════════════════════════════

def detect_duplicate_dedupe_keys(rows: list[PredictionRow]) -> list[str]:
    """Return list of dedupe_keys that appear more than once."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.dedupe_key] = counts.get(r.dedupe_key, 0) + 1
    return [k for k, n in counts.items() if n > 1]


# ══════════════════════════════════════════════════════════════════════════════
# § Metrics Recomputation
# ══════════════════════════════════════════════════════════════════════════════

def recompute_metrics_from_rows(
    rows: list[PredictionRow],
) -> dict:
    """
    Recompute all evaluation metrics from persisted prediction rows.

    Uses wbc_backend.evaluation.metrics as SSOT for all computations.

    Returns dict with:
      model_brier, market_brier, bss, ece, log_loss, sample_size,
      home_win_rate, market_home_win_rate
    """
    if not rows:
        return {
            "sample_size": 0,
            "model_brier": None,
            "market_brier": None,
            "bss": None,
            "ece": None,
            "log_loss": None,
            "error": "no rows",
        }

    model_probs = [r.model_home_prob for r in rows]
    market_probs = [r.market_home_prob_no_vig for r in rows]
    actuals = [float(r.home_win) for r in rows]
    n = len(rows)

    model_brier = _metrics_brier_score(model_probs, actuals)
    market_brier = _metrics_brier_score(market_probs, actuals)
    bss = _metrics_bss(model_brier, market_brier)
    ece_result = _metrics_ece(model_probs, actuals)
    log_loss = _metrics_log_loss(model_probs, actuals)

    return {
        "sample_size": n,
        "model_brier": round(model_brier, 6),
        "market_brier": round(market_brier, 6),
        "bss": round(bss, 6) if bss is not None else None,
        "ece": round(ece_result["ece"], 6),
        "log_loss": round(log_loss, 6),
        "home_win_rate": round(sum(actuals) / n, 4),
        "market_home_win_rate": round(sum(market_probs) / n, 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# § Safety Utility
# ══════════════════════════════════════════════════════════════════════════════

_PROTECTED_SOURCE_DIRS = frozenset([
    "mlb_2025/mlb-2025-asplayed.csv",
    "mlb_2025/mlb_odds_2025_real.csv",
])


def _assert_not_source_path(path: Path) -> None:
    """Raise RuntimeError if path points to a protected original source file."""
    path_str = str(path)
    for protected in _PROTECTED_SOURCE_DIRS:
        if protected in path_str:
            raise RuntimeError(
                f"[PredictionPersistence] BLOCKED: Cannot write to source file: {path}\n"
                f"All output must go to data/mlb_2025/derived/."
            )
