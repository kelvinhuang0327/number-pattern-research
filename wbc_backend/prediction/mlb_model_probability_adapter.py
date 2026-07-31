"""
wbc_backend/prediction/mlb_model_probability_adapter.py

Adapter that loads per-game MLB model probabilities from existing artifacts
and merges them into historical odds rows for simulation.

Security:
  - Writes only under outputs/predictions/PAPER/.
  - Never labels market_proxy as real_model.
  - Refuses market proxy by default.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from wbc_backend.prediction.mlb_model_probability import MlbModelProbability

# ── Root guard ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PAPER_PREDICTIONS_ZONE = "outputs/predictions/PAPER"

# ── MLB team full-name → 3-letter code mapping ────────────────────────────────
# Covers all 30 MLB teams including 2025 Athletics relocation.
MLB_TEAM_CODE_MAP: dict[str, str] = {
    # Full name → code
    "Arizona Diamondbacks": "ARI",
    "Athletics": "ATH",
    "Oakland Athletics": "ATH",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}

# Reverse map for convenience (code → normalized full name)
_CODE_TO_NAME: dict[str, str] = {v: k for k, v in MLB_TEAM_CODE_MAP.items()}


def _normalize_team_to_code(name: str) -> str | None:
    """Map full team name or 3-letter code to canonical 3-letter code."""
    if not name or not name.strip():
        return None
    # Already a code
    upper = name.strip().upper()
    if upper in {v for v in MLB_TEAM_CODE_MAP.values()}:
        return upper
    # Full name lookup (case-insensitive)
    lower = name.strip().lower()
    for full, code in MLB_TEAM_CODE_MAP.items():
        if full.lower() == lower:
            return code
    # Partial suffix match: "Guardians" → CLE
    lower_parts = lower.split()
    if lower_parts:
        for full, code in MLB_TEAM_CODE_MAP.items():
            parts = full.lower().split()
            if parts and parts[-1] == lower_parts[-1]:
                return code
    return None


def _assert_paper_output_path(path: Path) -> None:
    """Raise ValueError if path is not under outputs/predictions/PAPER/."""
    resolved = path.resolve()
    if _PAPER_PREDICTIONS_ZONE not in resolved.as_posix():
        raise ValueError(
            f"Output path must be under {_PAPER_PREDICTIONS_ZONE!r}. "
            f"Got non-PAPER path: {resolved}"
        )


# ── Canonical model outputs artifact ─────────────────────────────────────────

_DEFAULT_MODEL_OUTPUTS_JSONL = (
    _REPO_ROOT / "data" / "derived" / "model_outputs_2026-04-29.jsonl"
)


def _load_model_outputs_jsonl(path: Path) -> list[dict]:
    """Load all valid rows from a model outputs JSONL file."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                rows.append(d)
            except json.JSONDecodeError:
                pass
    return rows


def _extract_home_predictions(
    model_rows: list[dict],
    model_version: str,
) -> list[MlbModelProbability]:
    """
    Extract home-win probabilities from model output rows.

    Each game has one row per selection (home / away). We join home+away rows
    by canonical_match_id to build a (home_prob, away_prob) pair.
    """
    # Group by canonical_match_id
    by_match: dict[str, dict[str, dict]] = {}
    for r in model_rows:
        match_id = r.get("canonical_match_id") or ""
        selection = (r.get("selection") or "").lower()
        if selection not in ("home", "away"):
            continue
        if match_id not in by_match:
            by_match[match_id] = {}
        by_match[match_id][selection] = r

    results: list[MlbModelProbability] = []
    for match_id, selections in by_match.items():
        home_row = selections.get("home")
        away_row = selections.get("away")
        if home_row is None or away_row is None:
            continue

        home_prob_raw = home_row.get("predicted_probability")
        away_prob_raw = away_row.get("predicted_probability")
        if home_prob_raw is None or away_prob_raw is None:
            continue

        try:
            hp = float(home_prob_raw)
            ap = float(away_prob_raw)
        except (TypeError, ValueError):
            continue

        # Renormalize if needed
        total = hp + ap
        if total <= 0:
            continue
        if abs(total - 1.0) > 0.01:
            hp = hp / total
            ap = ap / total

        # Determine probability_source
        raw_source = (home_row.get("probability_source") or "").lower()
        if "calibrat" in raw_source:
            prob_source: str = "calibrated_model"
        elif "real" in raw_source or "trained" in raw_source:
            prob_source = "real_model"
        elif "proxy" in raw_source or "market" in raw_source:
            prob_source = "market_proxy"
        else:
            prob_source = "real_model"  # artifact is from model pipeline

        # Parse date from match_time_utc
        match_time = home_row.get("match_time_utc") or ""
        try:
            game_date = match_time[:10]  # YYYY-MM-DD
        except Exception:
            game_date = ""

        home_code = home_row.get("home_team_code") or ""
        away_code = home_row.get("away_team_code") or ""

        try:
            generated_at = datetime.now(tz=timezone.utc)
            rec = MlbModelProbability(
                game_id=match_id,
                game_date=game_date,
                home_team=home_code,
                away_team=away_code,
                model_prob_home=hp,
                model_prob_away=ap,
                model_version=model_version,
                probability_source=prob_source,  # type: ignore[arg-type]
                generated_at_utc=generated_at,
                source_trace={
                    "source_artifact": "data/derived/model_outputs_2026-04-29.jsonl",
                    "canonical_match_id": match_id,
                    "raw_probability_source": home_row.get("probability_source"),
                    "model_version_raw": home_row.get("model_version"),
                    "prediction_time_utc": home_row.get("prediction_time_utc"),
                },
            )
            results.append(rec)
        except ValueError:
            pass

    return results


# ── Main public API ───────────────────────────────────────────────────────────

def build_model_probabilities_from_existing_artifacts(
    odds_csv_path: str | Path,
    output_jsonl_path: str | Path,
    model_version: str = "v1-mlb-moneyline-trained",
    allow_market_proxy: bool = False,
    model_outputs_jsonl: str | Path | None = None,
) -> list[MlbModelProbability]:
    """
    Build per-game model probabilities by loading existing model output artifacts.

    Parameters
    ----------
    odds_csv_path : path
        Path to the historical odds CSV (used to validate join coverage).
    output_jsonl_path : path
        Where to write the JSONL output. Must be under outputs/predictions/PAPER/.
    model_version : str
        Model version label.
    allow_market_proxy : bool
        If True, rows without real model probabilities fall back to market proxy.
        If False (default), the function raises if no real artifact is available.
    model_outputs_jsonl : path | None
        Path to the model outputs JSONL artifact. Defaults to the canonical
        data/derived/model_outputs_2026-04-29.jsonl.

    Returns
    -------
    list[MlbModelProbability]
    """
    import pandas as pd

    output_jsonl_path = Path(output_jsonl_path)
    _assert_paper_output_path(output_jsonl_path)

    # ── Load model artifact ───────────────────────────────────────────────────
    artifact_path = Path(model_outputs_jsonl) if model_outputs_jsonl else _DEFAULT_MODEL_OUTPUTS_JSONL
    real_probabilities: list[MlbModelProbability] = []

    if artifact_path.exists():
        model_rows = _load_model_outputs_jsonl(artifact_path)
        real_probabilities = _extract_home_predictions(model_rows, model_version)

    if not real_probabilities:
        if not allow_market_proxy:
            raise ValueError(
                "No real model probability artifact found and allow_market_proxy=False. "
                "No real model probabilities are available in "
                f"{artifact_path}. "
                "Pass allow_market_proxy=True to use market-implied probability as proxy."
            )

    # ── Load odds CSV for market proxy fallback ───────────────────────────────
    df_odds = pd.read_csv(odds_csv_path)
    generated_at = datetime.now(tz=timezone.utc)
    all_probabilities = list(real_probabilities)

    if allow_market_proxy:
        # Build a lookup of which games already have real model probs
        covered_match_ids: set[str] = set()
        covered_date_home: set[tuple[str, str]] = set()
        for p in real_probabilities:
            if p.game_id:
                covered_match_ids.add(p.game_id)
            if p.game_date and p.home_team:
                home_code = _normalize_team_to_code(p.home_team) or p.home_team
                covered_date_home.add((p.game_date, home_code))

        # Add market proxy rows for uncovered games
        from wbc_backend.models.mlb_moneyline import american_to_implied_prob

        for _, row in df_odds.iterrows():
            date_str = str(row.get("Date", ""))[:10]
            home_name = str(row.get("Home", ""))
            away_name = str(row.get("Away", ""))
            home_code = _normalize_team_to_code(home_name) or home_name
            away_code = _normalize_team_to_code(away_name) or away_name

            if (date_str, home_code) in covered_date_home:
                continue  # already covered by real model

            home_ml = row.get("Home ML")
            away_ml = row.get("Away ML")
            if home_ml is None or away_ml is None:
                continue

            try:
                hp = american_to_implied_prob(home_ml)
                ap = american_to_implied_prob(away_ml)
                if hp is None or ap is None or (hp + ap) <= 0:
                    continue
                import numpy as np
                if np.isnan(hp) or np.isnan(ap):
                    continue
                # De-vig
                total = hp + ap
                hp = hp / total
                ap = ap / total
                rec = MlbModelProbability(
                    game_id=None,
                    game_date=date_str,
                    home_team=home_code,
                    away_team=away_code,
                    model_prob_home=float(hp),
                    model_prob_away=float(ap),
                    model_version=f"{model_version}:market_proxy",
                    probability_source="market_proxy",
                    generated_at_utc=generated_at,
                    source_trace={
                        "source": "market_implied_odds",
                        "home_ml": home_ml,
                        "away_ml": away_ml,
                        "note": "market proxy — no real model artifact for this date",
                    },
                )
                all_probabilities.append(rec)
                covered_date_home.add((date_str, home_code))
            except Exception:
                continue

    # ── Write JSONL output ────────────────────────────────────────────────────
    output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_jsonl_path, "w", encoding="utf-8") as fout:
        for p in all_probabilities:
            fout.write(p.to_jsonl_line() + "\n")

    return all_probabilities


def merge_model_probabilities_into_rows(
    rows: list[dict],
    probabilities: list[MlbModelProbability],
) -> list[dict]:
    """
    Merge per-game model probabilities into historical odds rows.

    Join strategy:
    1. By game_id (canonical_match_id) if available in both.
    2. Else by normalized date (YYYY-MM-DD) + home_team_code + away_team_code.

    Adds to each row:
    - model_prob_home
    - model_prob_away
    - model_version
    - probability_source
    - probability_source_trace

    Rows without a matching probability are left unchanged (no model_prob_home
    column added, so simulation spine will fall back to market proxy for those).
    """
    # Build lookups
    by_game_id: dict[str, MlbModelProbability] = {}
    by_date_teams: dict[tuple[str, str, str], MlbModelProbability] = {}

    for p in probabilities:
        if p.game_id:
            by_game_id[p.game_id] = p
        if p.game_date and p.home_team and p.away_team:
            home_code = _normalize_team_to_code(p.home_team) or p.home_team.upper()
            away_code = _normalize_team_to_code(p.away_team) or p.away_team.upper()
            key = (p.game_date, home_code, away_code)
            by_date_teams[key] = p

    enriched_rows = []
    for row in rows:
        matched_prob: MlbModelProbability | None = None

        # Try game_id join first
        row_game_id = row.get("game_id") or row.get("canonical_match_id")
        if row_game_id and row_game_id in by_game_id:
            matched_prob = by_game_id[row_game_id]

        # Fallback: date + teams join
        if matched_prob is None:
            raw_date = str(row.get("Date") or row.get("game_date") or "")[:10]
            raw_home = str(row.get("Home") or row.get("home_team") or "")
            raw_away = str(row.get("Away") or row.get("away_team") or "")
            home_code = _normalize_team_to_code(raw_home) or raw_home.upper()
            away_code = _normalize_team_to_code(raw_away) or raw_away.upper()
            key = (raw_date, home_code, away_code)
            matched_prob = by_date_teams.get(key)

        new_row = dict(row)
        if matched_prob is not None:
            new_row["model_prob_home"] = matched_prob.model_prob_home
            new_row["model_prob_away"] = matched_prob.model_prob_away
            new_row["model_version"] = matched_prob.model_version
            new_row["probability_source"] = matched_prob.probability_source
            new_row["probability_source_trace"] = matched_prob.source_trace

        enriched_rows.append(new_row)

    return enriched_rows
