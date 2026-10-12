"""
wbc_backend/prediction/mlb_feature_repair.py

P9: Conservative feature repair for MLB moneyline model probabilities.

Removes the constant ``home_bias=1.0`` artefact from model predictions and
adds ≥ 2 independent non-market baseball features:
  1. Bullpen-usage delta  (last 3 days, home minus away) — pre-game available
  2. Rest-day delta       (home rest days minus away rest days)            "
  3. Recent win-rate delta (rolling last-N games, home minus away)         "

Design constraints:
  - leakage_safe = True: all features use only data available at game start.
  - paper_only   = True: never writes or modifies production artifacts.
  - Do NOT re-train ``mlb_moneyline.py``; apply a conservative logit correction.
  - The resulting column ``model_prob_home`` is labelled
    ``probability_source = "repaired_model_candidate"``.
  - Original probability stored in ``raw_model_prob_home``.

Key API:
    build_repaired_feature_rows(
        rows, *, remove_constant_home_bias, ...
    ) -> tuple[list[dict], dict]
"""
from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from wbc_backend.prediction.mlb_game_key import (
    build_mlb_game_id,
    dedupe_mlb_rows,
    normalize_mlb_team,
    parse_context_game_id,
)

logger = logging.getLogger(__name__)

__all__ = ["build_repaired_feature_rows"]

# ── Constants ─────────────────────────────────────────────────────────────────

_FEATURE_VERSION = "p9_feature_repair_v1"
_PROBABILITY_SOURCE = "repaired_model_candidate"

_DEFAULT_BULLPEN_CONTEXT = "data/mlb_context/bullpen_usage_3d.jsonl"
_DEFAULT_REST_CONTEXT = "data/mlb_context/injury_rest.jsonl"

# Conservative weight magnitude for each correction
_BULLPEN_DELTA_WEIGHT: float = 0.03   # logit units; higher usage home → −edge
_REST_DELTA_WEIGHT: float = 0.02      # logit units; more rest home → +edge
_WIN_RATE_DELTA_WEIGHT: float = 0.05  # logit units; better record home → +edge

_RECENT_WIN_RATE_WINDOW: int = 15     # games

_MIN_PROB: float = 0.01
_MAX_PROB: float = 0.99


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_repaired_feature_rows(
    rows: list[dict],
    *,
    remove_constant_home_bias: bool = True,
    bullpen_context_path: str | None = None,
    rest_context_path: str | None = None,
    home_bias_logit_correction: float | None = None,
    bullpen_delta_weight: float = _BULLPEN_DELTA_WEIGHT,
    rest_delta_weight: float = _REST_DELTA_WEIGHT,
    win_rate_delta_weight: float = _WIN_RATE_DELTA_WEIGHT,
    recent_win_rate_window: int = _RECENT_WIN_RATE_WINDOW,
) -> tuple[list[dict], dict]:
    """
    Enrich each MLB prediction row with repaired features and adjusted probabilities.

    Steps performed (all leakage-safe):
    1. Add ``game_id`` to every row.
    2. Deduplicate rows by game_id.
    3. Load bullpen-usage and rest-day context files (JSONL); join by game_id.
    4. Compute rolling recent-win-rate per team from past results in the rows.
    5. Apply conservative logit correction to ``model_prob_home``:
        a. Remove estimated constant home_bias intercept shift (RC-1 fix).
        b. Apply bullpen-delta, rest-delta, and win-rate-delta adjustments.
    6. Label every row with ``probability_source = "repaired_model_candidate"``,
       preserve original in ``raw_model_prob_home``.

    Parameters
    ----------
    rows : list[dict]
        Input rows from the P5 probability-enriched CSV.  Must contain at
        minimum: ``Date``, ``Home``, ``Away``, ``model_prob_home``,
        ``Away ML``, ``Home ML``.
    remove_constant_home_bias : bool
        If True, subtract the estimated constant home_bias intercept from the
        model logit before applying feature corrections.
    bullpen_context_path : str | None
        Absolute or workspace-relative path to ``bullpen_usage_3d.jsonl``.
        Defaults to ``data/mlb_context/bullpen_usage_3d.jsonl``.
    rest_context_path : str | None
        Path to ``injury_rest.jsonl``.
        Defaults to ``data/mlb_context/injury_rest.jsonl``.
    home_bias_logit_correction : float | None
        Override the auto-estimated bias correction (in logit units).
        When None the correction is estimated as the mean excess logit of the
        model over the market.
    bullpen_delta_weight : float
        Logit weight for normalised bullpen-usage delta (default 0.03).
    rest_delta_weight : float
        Logit weight for normalised rest-day delta (default 0.02).
    win_rate_delta_weight : float
        Logit weight for normalised rolling win-rate delta (default 0.05).
    recent_win_rate_window : int
        Number of past games used to compute rolling team win-rate (default 15).

    Returns
    -------
    tuple[list[dict], dict]
        ``(repaired_rows, metadata)``

        Each repaired row has additional keys:
          - ``game_id``
          - ``raw_model_prob_home`` — original value before adjustment
          - ``model_prob_home`` — adjusted value (replaces original)
          - ``probability_source`` — "repaired_model_candidate"
          - ``repaired_feature_version`` — "p9_feature_repair_v1"
          - ``repaired_home_bias_removed`` — bool
          - ``repaired_feature_trace`` — dict with per-row correction details
          - ``bullpen_usage_last_3d_home`` / ``bullpen_usage_last_3d_away``
          - ``bullpen_delta`` — home − away (positive = home more fatigued)
          - ``rest_days_home`` / ``rest_days_away``
          - ``rest_delta`` — home − away (positive = home better rested)
          - ``recent_win_rate_home`` / ``recent_win_rate_away``
          - ``win_rate_delta`` — home − away

        ``metadata`` keys:
          - ``input_count``, ``output_count``, ``duplicate_count``
          - ``bullpen_join_hit_count``, ``bullpen_join_miss_count``
          - ``rest_join_hit_count``, ``rest_join_miss_count``
          - ``home_bias_logit_correction`` (estimated value used)
          - ``avg_model_prob_before``, ``avg_model_prob_after``
          - ``repaired_feature_version``
          - ``leakage_safe``, ``paper_only``
    """
    if not rows:
        return [], {
            "input_count": 0,
            "output_count": 0,
            "duplicate_count": 0,
            "leakage_safe": True,
            "paper_only": True,
            "repaired_feature_version": _FEATURE_VERSION,
        }

    # ── Step 1 & 2: add game_id + deduplicate ─────────────────────────────
    deduped_rows, dedup_meta = dedupe_mlb_rows(rows)
    duplicate_count = dedup_meta["duplicate_game_id_count"]

    # ── Step 3: load context files ────────────────────────────────────────
    bp_path = _resolve_path(bullpen_context_path or _DEFAULT_BULLPEN_CONTEXT)
    rest_path = _resolve_path(rest_context_path or _DEFAULT_REST_CONTEXT)

    bullpen_lookup = _load_context_lookup(bp_path)
    rest_lookup = _load_context_lookup(rest_path)

    # ── Step 4: compute rolling win rates ─────────────────────────────────
    win_rate_map = _compute_rolling_win_rates(deduped_rows, recent_win_rate_window)

    # ── Step 5: estimate home-bias correction if not overridden ──────────
    if remove_constant_home_bias:
        if home_bias_logit_correction is not None:
            bias_correction = home_bias_logit_correction
        else:
            bias_correction = _estimate_home_bias_logit_correction(deduped_rows)
    else:
        bias_correction = 0.0

    # ── Step 6: enrich each row ───────────────────────────────────────────
    repaired_rows: list[dict] = []
    bullpen_hit = bullpen_miss = rest_hit = rest_miss = 0
    probs_before: list[float] = []
    probs_after: list[float] = []

    for row in deduped_rows:
        gid: str = str(row.get("game_id") or "")

        # --- raw model prob
        raw_prob = _safe_float(
            row.get("model_prob_home") or row.get("model_prob") or row.get("market_prob_home"),
            default=0.5,
        )
        probs_before.append(raw_prob)

        # --- context feature join (game_id → context record)
        bp_rec = bullpen_lookup.get(gid) or {}
        rest_rec = rest_lookup.get(gid) or {}

        bullpen_home_3d = _safe_float(bp_rec.get("bullpen_usage_last_3d_home"), default=None)
        bullpen_away_3d = _safe_float(bp_rec.get("bullpen_usage_last_3d_away"), default=None)
        rest_home = _safe_float(rest_rec.get("rest_days_home"), default=None)
        rest_away = _safe_float(rest_rec.get("rest_days_away"), default=None)

        if bullpen_home_3d is not None and bullpen_away_3d is not None:
            bullpen_hit += 1
        else:
            bullpen_miss += 1
        if rest_home is not None and rest_away is not None:
            rest_hit += 1
        else:
            rest_miss += 1

        # --- deltas (use 0.0 when data missing)
        bullpen_delta = (
            (bullpen_home_3d - bullpen_away_3d)
            if bullpen_home_3d is not None and bullpen_away_3d is not None
            else 0.0
        )
        rest_delta = (
            (rest_home - rest_away)
            if rest_home is not None and rest_away is not None
            else 0.0
        )

        # --- rolling win rates
        win_rate_home = win_rate_map.get((gid, "home"), 0.5)
        win_rate_away = win_rate_map.get((gid, "away"), 0.5)
        win_rate_delta = win_rate_home - win_rate_away

        # --- logit adjustment
        logit_raw = _logit(raw_prob)
        logit_adj = logit_raw

        if remove_constant_home_bias:
            logit_adj -= bias_correction   # remove systematic intercept lift

        # Bullpen: more home usage → worse home outlook → subtract edge
        # Normalise to ~[-1, +1] by dividing by 3 innings (typical half-inning range)
        bullpen_norm = bullpen_delta / 3.0
        logit_adj -= bullpen_delta_weight * bullpen_norm

        # Rest: more home rest → better home outlook → add edge
        # Normalise by 7 days
        rest_norm = rest_delta / 7.0
        logit_adj += rest_delta_weight * rest_norm

        # Win rate: better home record → add edge
        logit_adj += win_rate_delta_weight * win_rate_delta

        repaired_prob = _sigmoid(logit_adj)
        repaired_prob = max(_MIN_PROB, min(_MAX_PROB, repaired_prob))
        probs_after.append(repaired_prob)

        feature_trace: dict[str, Any] = {
            "raw_logit": round(logit_raw, 6),
            "bias_correction": round(bias_correction, 6),
            "bullpen_norm": round(bullpen_norm, 6),
            "rest_norm": round(rest_norm, 6),
            "win_rate_delta": round(win_rate_delta, 6),
            "adjusted_logit": round(logit_adj, 6),
        }

        repaired_row = dict(row)
        repaired_row["raw_model_prob_home"] = raw_prob
        repaired_row["model_prob_home"] = repaired_prob
        repaired_row["probability_source"] = _PROBABILITY_SOURCE
        repaired_row["repaired_feature_version"] = _FEATURE_VERSION
        repaired_row["repaired_home_bias_removed"] = remove_constant_home_bias
        repaired_row["repaired_feature_trace"] = json.dumps(feature_trace)
        repaired_row["bullpen_usage_last_3d_home"] = bullpen_home_3d
        repaired_row["bullpen_usage_last_3d_away"] = bullpen_away_3d
        repaired_row["bullpen_delta"] = round(bullpen_delta, 4)
        repaired_row["rest_days_home"] = rest_home
        repaired_row["rest_days_away"] = rest_away
        repaired_row["rest_delta"] = round(rest_delta, 4)
        repaired_row["recent_win_rate_home"] = round(win_rate_home, 4)
        repaired_row["recent_win_rate_away"] = round(win_rate_away, 4)
        repaired_row["win_rate_delta"] = round(win_rate_delta, 4)

        repaired_rows.append(repaired_row)

    avg_before = sum(probs_before) / len(probs_before) if probs_before else float("nan")
    avg_after = sum(probs_after) / len(probs_after) if probs_after else float("nan")

    metadata: dict[str, Any] = {
        "input_count": len(rows),
        "output_count": len(repaired_rows),
        "duplicate_count": duplicate_count,
        "bullpen_join_hit_count": bullpen_hit,
        "bullpen_join_miss_count": bullpen_miss,
        "rest_join_hit_count": rest_hit,
        "rest_join_miss_count": rest_miss,
        "home_bias_logit_correction": round(bias_correction, 6),
        "avg_model_prob_before": round(avg_before, 4),
        "avg_model_prob_after": round(avg_after, 4),
        "repaired_feature_version": _FEATURE_VERSION,
        "leakage_safe": True,
        "paper_only": True,
    }
    return repaired_rows, metadata


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Context file loading
# ─────────────────────────────────────────────────────────────────────────────

def _load_context_lookup(path: Path) -> dict[str, dict]:
    """
    Load a context JSONL file and build a dict keyed by canonical game_id.

    Tries two key strategies:
      1. Parse the ``game_id`` field in each record using
         ``parse_context_game_id()``, then build
         ``YYYY-MM-DD_HOME_AWAY`` key.
      2. Fall back to positional index (0-based), so callers can do
         ``lookup.get(str(i))`` for the i-th row.

    Returns
    -------
    dict[str, dict]
        ``{canonical_game_id: record}``
        Also includes ``{"__pos__<i>": record}`` positional fallback entries.
    """
    lookup: dict[str, dict] = {}
    if not path.exists():
        logger.warning("Context file not found: %s", path)
        return lookup

    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Positional fallback
            lookup[f"__pos__{i}"] = rec

            raw_gid = str(rec.get("game_id") or "").strip()
            if not raw_gid:
                continue

            parsed = parse_context_game_id(raw_gid)
            if parsed:
                date_iso, home_code, away_code = parsed
                canonical = f"{date_iso}_{home_code}_{away_code}"
                lookup[canonical] = rec
            else:
                # If it's already in canonical format, store as-is
                lookup[raw_gid] = rec

    return lookup


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Rolling win-rate computation (leakage-safe)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_rolling_win_rates(
    rows: list[dict],
    window: int,
) -> dict[tuple[str, str], float]:
    """
    Compute rolling pre-game win rates for each team per game (leakage-safe).

    Uses only results from games strictly BEFORE the target game date.

    Parameters
    ----------
    rows : list[dict]
        Prediction rows sorted arbitrarily (sorted internally by Date).
    window : int
        Number of most recent completed games to include.

    Returns
    -------
    dict[(game_id, side), float]
        ``{(game_id, "home"): win_rate, (game_id, "away"): win_rate}``
        Both default to 0.5 if insufficient history.
    """
    # Collect all games with known outcomes
    completed: list[dict] = []
    for row in rows:
        date_raw = str(row.get("Date") or row.get("date") or "").strip()
        home_score = _safe_float(row.get("Home Score") or row.get("home_score"), None)
        away_score = _safe_float(row.get("Away Score") or row.get("away_score"), None)
        if date_raw and home_score is not None and away_score is not None:
            completed.append({
                "date": date_raw,
                "home_code": normalize_mlb_team(
                    str(row.get("Home") or row.get("home_team") or "")
                ),
                "away_code": normalize_mlb_team(
                    str(row.get("Away") or row.get("away_team") or "")
                ),
                "home_win": 1 if home_score > away_score else 0,
                "game_id": str(row.get("game_id") or ""),
            })

    # Sort by date (ISO strings sort correctly)
    completed.sort(key=lambda r: r["date"])

    # Build rolling history: team → deque of results (1=win, 0=loss)
    # Process in chronological order; for each target game use history so far
    from collections import deque

    team_history: dict[str, deque] = {}

    # Pre-build a lookup of game_id → index in completed for fast retrieval
    # and also map each target game_id to its rolling win rates

    # Process chronologically, recording rates BEFORE updating
    win_rate_map: dict[tuple[str, str], float] = {}

    # We need to process one game at a time, recording the rate BEFORE the game
    for rec in completed:
        gid = rec["game_id"]
        hc = rec["home_code"]
        ac = rec["away_code"]

        # Record pre-game win rates
        h_hist = team_history.get(hc, deque(maxlen=window))
        a_hist = team_history.get(ac, deque(maxlen=window))

        win_rate_map[(gid, "home")] = (sum(h_hist) / len(h_hist)) if h_hist else 0.5
        win_rate_map[(gid, "away")] = (sum(a_hist) / len(a_hist)) if a_hist else 0.5

        # Update history with this game's result
        if hc not in team_history:
            team_history[hc] = deque(maxlen=window)
        if ac not in team_history:
            team_history[ac] = deque(maxlen=window)
        team_history[hc].append(rec["home_win"])
        team_history[ac].append(1 - rec["home_win"])

    # For any row NOT in completed (no score yet), use the latest history
    for row in rows:
        gid = str(row.get("game_id") or "")
        if not gid:
            continue
        if (gid, "home") not in win_rate_map:
            hc = normalize_mlb_team(str(row.get("Home") or row.get("home_team") or ""))
            ac = normalize_mlb_team(str(row.get("Away") or row.get("away_team") or ""))
            h_hist = team_history.get(hc, deque())
            a_hist = team_history.get(ac, deque())
            win_rate_map[(gid, "home")] = (sum(h_hist) / len(h_hist)) if h_hist else 0.5
            win_rate_map[(gid, "away")] = (sum(a_hist) / len(a_hist)) if a_hist else 0.5

    return win_rate_map


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Home-bias estimation
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_home_bias_logit_correction(rows: list[dict]) -> float:
    """
    Estimate the systematic home-bias as mean excess logit(model) − logit(market).

    The constant ``home_bias=1.0`` feature adds a fixed term ``w_bias`` to every
    prediction logit.  We approximate this as the mean over-confidence of the
    model vs the market.

    Returns
    -------
    float
        Estimated logit correction (positive → model is systematically high).
        Clamped to [−2.0, +2.0] for safety.
    """
    excess: list[float] = []
    for row in rows:
        mp = _safe_float(row.get("model_prob_home") or row.get("model_prob"), None)
        if mp is None:
            continue
        # Derive market prob from American ML
        home_ml = _safe_float(row.get("Home ML") or row.get("home_ml"), None)
        away_ml = _safe_float(row.get("Away ML") or row.get("away_ml"), None)
        if home_ml is None or away_ml is None:
            continue
        mkt_prob = _ml_to_no_vig_prob(home_ml, away_ml)
        if mkt_prob is None:
            continue
        excess.append(_logit(mp) - _logit(mkt_prob))

    if not excess:
        return 0.0

    raw = sum(excess) / len(excess)
    return max(-2.0, min(2.0, raw))


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Math helpers
# ─────────────────────────────────────────────────────────────────────────────

def _logit(p: float) -> float:
    p = max(1e-7, min(1 - 1e-7, float(p)))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def _safe_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        f = float(str(value).replace("+", "").strip())
        return f if math.isfinite(f) else default
    except (ValueError, TypeError):
        return default


def _ml_to_no_vig_prob(home_ml: float, away_ml: float) -> float | None:
    """Convert American ML pair to home no-vig implied probability."""
    try:
        def ml2imp(ml: float) -> float:
            if ml > 0:
                return 100.0 / (ml + 100.0)
            return abs(ml) / (abs(ml) + 100.0)

        h = ml2imp(home_ml)
        a = ml2imp(away_ml)
        total = h + a
        if total <= 0:
            return None
        return h / total
    except Exception:
        return None


def _resolve_path(path_str: str) -> Path:
    """Resolve path: absolute or relative to workspace root."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    # Relative: try current working directory
    cwd_path = Path.cwd() / p
    if cwd_path.exists():
        return cwd_path
    # Try relative to this file's location (package root is 3 levels up)
    pkg_root = Path(__file__).parent.parent.parent
    return pkg_root / p
