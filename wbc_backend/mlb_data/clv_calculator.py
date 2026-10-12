"""
CLV (Closing Line Value) Calculator

Computes genuine CLV from real odds timeline data.

CLV = closing_implied_prob - decision_implied_prob

CLV > 0 means the model was betting "ahead of" the market.
CLV is ONLY valid when both decision_ts and closing_ts exist
and are independent snapshots (not the same post-game scrape).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .normalization import parse_ts

logger = logging.getLogger(__name__)

TIMELINE_PATH = Path("data/mlb_context/odds_timeline.jsonl")


def american_to_implied_prob(ml: int | float | None) -> float | None:
    """Convert American moneyline to implied probability."""
    if ml is None:
        return None
    ml = float(ml)
    if ml >= 100:
        return 100.0 / (ml + 100.0)
    elif ml <= -100:
        return abs(ml) / (abs(ml) + 100.0)
    return None


@dataclass(frozen=True)
class CLVResult:
    game_id: str
    clv_value: float | None
    clv_available: bool
    decision_home_ml: int | None
    decision_home_prob: float | None
    closing_home_ml: int | None
    closing_home_prob: float | None
    decision_ts: str | None
    closing_ts: str | None
    timeline_valid: bool
    rejection_reason: str | None = None
    # Dual-source fields
    closing_source: str | None = None          # e.g. "OddsAPI:pinnacle" or "TSL"
    external_closing_home_ml: int | None = None
    external_closing_ts: str | None = None
    used_external_closing: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "clv_value": self.clv_value,
            "clv_available": self.clv_available,
            "decision_home_ml": self.decision_home_ml,
            "decision_home_prob": round(self.decision_home_prob, 6) if self.decision_home_prob is not None else None,
            "closing_home_ml": self.closing_home_ml,
            "closing_home_prob": round(self.closing_home_prob, 6) if self.closing_home_prob is not None else None,
            "decision_ts": self.decision_ts,
            "closing_ts": self.closing_ts,
            "timeline_valid": self.timeline_valid,
            "rejection_reason": self.rejection_reason,
            "closing_source": self.closing_source,
            "external_closing_home_ml": self.external_closing_home_ml,
            "external_closing_ts": self.external_closing_ts,
            "used_external_closing": self.used_external_closing,
        }


def validate_timeline(record: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate that a timeline record has valid, strictly increasing timestamps.

    Accepts either:
      - external_closing (OddsAPI) if present and valid   → preferred
      - TSL closing (closing_home_ml) as fallback

    Returns (is_valid, rejection_reason).
    """
    decision_ts_str = record.get("decision_ts")

    # Select closing source: prefer external if present
    ext_closing_ml  = record.get("external_closing_home_ml")
    ext_closing_ts  = record.get("external_closing_ts")
    tsl_closing_ml  = record.get("closing_home_ml")
    tsl_closing_ts  = record.get("closing_ts")

    if ext_closing_ml is not None and ext_closing_ts:
        closing_ts_str = ext_closing_ts
        closing_ml_val = ext_closing_ml
    else:
        closing_ts_str = tsl_closing_ts
        closing_ml_val = tsl_closing_ml

    if not decision_ts_str or not closing_ts_str:
        return False, "missing_timestamps"

    decision_ts = parse_ts(decision_ts_str)
    closing_ts  = parse_ts(closing_ts_str)

    if decision_ts is None or closing_ts is None:
        return False, "unparseable_timestamps"

    if decision_ts >= closing_ts:
        return False, "decision_ts_not_before_closing_ts"

    # Decision and closing must be DIFFERENT snapshots (not same post-game scrape)
    delta_seconds = (closing_ts - decision_ts).total_seconds()
    if delta_seconds < 60:
        return False, "timestamps_too_close_likely_same_scrape"

    # Both must have valid ML values
    if record.get("decision_home_ml") is None:
        return False, "missing_decision_home_ml"
    if closing_ml_val is None:
        return False, "missing_closing_home_ml"

    return True, None


def compute_clv(record: dict[str, Any]) -> CLVResult:
    """
    Compute CLV for a single game timeline record.

    Closing line preference:
      1. external_closing_home_ml (OddsAPI / Pinnacle) — true market close
      2. closing_home_ml (TSL fallback)

    CLV = closing_home_prob - decision_home_prob
    Positive CLV means we were betting at better odds than closing.
    """
    game_id = str(record.get("game_id", ""))

    # Resolve closing source
    ext_closing_ml = record.get("external_closing_home_ml")
    ext_closing_ts = record.get("external_closing_ts")
    used_external = ext_closing_ml is not None and ext_closing_ts is not None

    if used_external:
        effective_closing_ml = ext_closing_ml
        effective_closing_ts = ext_closing_ts
        closing_src = str(record.get("closing_source") or "OddsAPI")
    else:
        effective_closing_ml = record.get("closing_home_ml")
        effective_closing_ts = record.get("closing_ts")
        closing_src = "TSL"

    # Temporarily patch record for validate_timeline (it reads the fields directly)
    patched = dict(record)
    if not used_external:
        # ensure validate uses TSL path
        patched.pop("external_closing_home_ml", None)
        patched.pop("external_closing_ts", None)

    is_valid, reason = validate_timeline(patched)
    if not is_valid:
        return CLVResult(
            game_id=game_id,
            clv_value=None,
            clv_available=False,
            decision_home_ml=record.get("decision_home_ml"),
            decision_home_prob=None,
            closing_home_ml=effective_closing_ml,
            closing_home_prob=None,
            decision_ts=record.get("decision_ts"),
            closing_ts=effective_closing_ts,
            timeline_valid=False,
            rejection_reason=reason,
            closing_source=closing_src,
            external_closing_home_ml=ext_closing_ml,
            external_closing_ts=ext_closing_ts,
            used_external_closing=used_external,
        )

    decision_ml = record["decision_home_ml"]
    closing_ml  = effective_closing_ml
    decision_prob = american_to_implied_prob(decision_ml)
    closing_prob  = american_to_implied_prob(closing_ml)

    if decision_prob is None or closing_prob is None:
        return CLVResult(
            game_id=game_id,
            clv_value=None,
            clv_available=False,
            decision_home_ml=decision_ml,
            decision_home_prob=decision_prob,
            closing_home_ml=closing_ml,
            closing_home_prob=closing_prob,
            decision_ts=record.get("decision_ts"),
            closing_ts=effective_closing_ts,
            timeline_valid=True,
            rejection_reason="invalid_implied_probability",
            closing_source=closing_src,
            external_closing_home_ml=ext_closing_ml,
            external_closing_ts=ext_closing_ts,
            used_external_closing=used_external,
        )

    clv = closing_prob - decision_prob

    return CLVResult(
        game_id=game_id,
        clv_value=round(clv, 6),
        clv_available=True,
        decision_home_ml=decision_ml,
        decision_home_prob=decision_prob,
        closing_home_ml=closing_ml,
        closing_home_prob=closing_prob,
        decision_ts=record.get("decision_ts"),
        closing_ts=effective_closing_ts,
        timeline_valid=True,
        closing_source=closing_src,
        external_closing_home_ml=ext_closing_ml,
        external_closing_ts=ext_closing_ts,
        used_external_closing=used_external,
    )


def compute_clv_batch(
    timeline_path: Path = TIMELINE_PATH,
) -> dict[str, Any]:
    """
    Compute CLV for all games in the timeline.

    Returns summary with per-game results and aggregate stats.
    """
    if not timeline_path.exists():
        return {
            "status": "no_timeline_data",
            "total_games": 0,
            "clv_available": 0,
            "results": [],
        }

    results: list[dict[str, Any]] = []
    available_count = 0
    positive_count = 0
    clv_values: list[float] = []
    external_count = 0
    tsl_fallback_count = 0

    for line in timeline_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        clv_result = compute_clv(record)
        results.append(clv_result.as_dict())

        if clv_result.clv_available and clv_result.clv_value is not None:
            available_count += 1
            clv_values.append(clv_result.clv_value)
            if clv_result.clv_value > 0:
                positive_count += 1
            if clv_result.used_external_closing:
                external_count += 1
            else:
                tsl_fallback_count += 1

    avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0
    clv_std = 0.0
    if len(clv_values) > 1:
        mean = avg_clv
        clv_std = (sum((v - mean) ** 2 for v in clv_values) / (len(clv_values) - 1)) ** 0.5

    return {
        "status": "computed",
        "total_games": len(results),
        "clv_available": available_count,
        "clv_unavailable": len(results) - available_count,
        "clv_via_external_closing": external_count,
        "clv_via_tsl_fallback": tsl_fallback_count,
        "positive_clv_count": positive_count,
        "negative_clv_count": available_count - positive_count,
        "avg_clv": round(avg_clv, 6),
        "std_clv": round(clv_std, 6),
        "positive_clv_rate": round(positive_count / available_count, 4) if available_count else 0.0,
        "results": results,
    }
