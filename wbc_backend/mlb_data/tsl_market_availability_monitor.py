"""
tsl_market_availability_monitor.py
P28B: Standalone TSL pre-game market availability monitor.

Tracks per-match visibility across TSL poll cycles and classifies early-withdrawal
events without modifying any existing TSL crawler or snapshot code.

Root cause addressed: P26K SOURCE_STATE_TRULY_EMPTY
Design reference: data/paper_recommendations/p27a_tsl_market_availability_monitor_design.json
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARLY_THRESHOLD_HOURS: float = 2.0
SOURCE_NAME: str = "TSL_PREGAME_LIST"
DEFAULT_STATE_PATH: Path = Path("data/derived/tsl_market_availability_state.json")

# Classification labels
CLASS_WITHDRAWAL_EARLY: str = "TSL_MARKET_WITHDRAWAL_EARLY"  # > 2h  — HIGH
CLASS_NORMAL_REMOVAL: str = "TSL_MARKET_NORMAL_REMOVAL"      # <= 2h — INFO
CLASS_NEVER_SEEN: str = "TSL_MARKET_NEVER_SEEN"              # never appeared — MEDIUM


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


@dataclass
class MarketAvailabilityRecord:
    """Per-match availability record updated each TSL poll cycle."""

    match_id: str
    league: str
    game_time_utc: str                    # ISO 8601 UTC string
    home_team: str = ""
    away_team: str = ""
    first_seen_timestamp: str | None = None
    last_seen_timestamp: str | None = None
    latest_seen_in_source: bool = False
    disappeared_at: str | None = None    # UTC ISO 8601 of first absence after presence
    hours_before_game: float | None = None
    consecutive_absent_cycles: int = 0
    source_name: str = SOURCE_NAME
    source_response_context: str = ""
    classification: str | None = None    # set once; never reset
    classification_rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MarketAvailabilityRecord":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _to_utc(ts: str) -> datetime:
    """Parse an ISO 8601 string (Z or ±HH:MM offset) and return UTC-aware datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class TslMarketAvailabilityMonitor:
    """
    Tracks per-match TSL pre-game market availability across poll cycles.

    Typical usage (called once per TSL poll):

        monitor = TslMarketAvailabilityMonitor()
        monitor.load()
        new_alerts = monitor.update(
            seen_match_ids={"3469930.1", "3469931.1"},
            match_metadata={
                "3469930.1": {"game_time": "2026-05-20T09:00:00Z", "league": "NPB"},
                ...
            },
            poll_ts="2026-05-20T01:00:00Z",
        )
        monitor.save()
    """

    EARLY_THRESHOLD_HOURS: float = EARLY_THRESHOLD_HOURS
    SOURCE_NAME: str = SOURCE_NAME

    def __init__(self, state_path: Path | str = DEFAULT_STATE_PATH) -> None:
        self._path = Path(state_path)
        self._records: dict[str, MarketAvailabilityRecord] = {}

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """Load state from disk.  Silently starts empty on first run."""
        if not self._path.exists():
            self._records = {}
            return
        with self._path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = json.load(fh)
        self._records = {
            k: MarketAvailabilityRecord.from_dict(v) for k, v in raw.items()
        }

    def save(self) -> None:
        """Atomically write state to disk using a temp-file rename."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v.to_dict() for k, v in self._records.items()}
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._path.parent, prefix=".tmp_tsl_mon_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------ #
    # Core update
    # ------------------------------------------------------------------ #

    def update(
        self,
        seen_match_ids: set[str],
        match_metadata: dict[str, dict],
        poll_ts: str,
        context: str = "",
    ) -> list[dict]:
        """
        Process one TSL poll cycle.

        Parameters
        ----------
        seen_match_ids:
            Match IDs present in this cycle's TSL pre-game list.
        match_metadata:
            Keyed by match_id.  Each value should contain at minimum
            ``game_time`` (ISO 8601) and optionally ``league``,
            ``home_team_name``, ``away_team_name``.
        poll_ts:
            ISO 8601 UTC timestamp for this poll cycle.
        context:
            Free-text logged in ``source_response_context`` when a match
            first disappears (e.g., "cycle_id=X source=TSL_BLOB3RD").

        Returns
        -------
        list[dict]
            Newly classified events produced during this cycle.
        """
        new_events: list[dict] = []
        poll_dt = _to_utc(poll_ts)

        # -- Step 1: update records for matches present in this cycle ------
        for mid in seen_match_ids:
            meta = match_metadata.get(mid, {})
            if mid not in self._records:
                self._records[mid] = MarketAvailabilityRecord(
                    match_id=mid,
                    league=meta.get("league", ""),
                    game_time_utc=meta.get("game_time", ""),
                    home_team=meta.get("home_team_name", ""),
                    away_team=meta.get("away_team_name", ""),
                    source_name=self.SOURCE_NAME,
                )
            rec = self._records[mid]
            if rec.first_seen_timestamp is None:
                rec.first_seen_timestamp = poll_ts
            rec.last_seen_timestamp = poll_ts
            rec.latest_seen_in_source = True
            rec.consecutive_absent_cycles = 0  # reset on reappearance

        # -- Step 2: update records for matches absent from this cycle -----
        # Iterate over a stable snapshot of keys to avoid mutation issues.
        for mid in list(self._records):
            if mid in seen_match_ids:
                continue

            rec = self._records[mid]

            # Only process matches that were previously observed
            if rec.first_seen_timestamp is None:
                continue  # handled by NEVER_SEEN check in step 3

            rec.latest_seen_in_source = False
            rec.consecutive_absent_cycles += 1

            # First absence after being seen → record disappeared_at
            if rec.disappeared_at is None:
                rec.disappeared_at = poll_ts
                rec.source_response_context = context

                if rec.game_time_utc:
                    game_dt = _to_utc(rec.game_time_utc)
                    delta_h = (game_dt - poll_dt).total_seconds() / 3600.0
                    rec.hours_before_game = round(delta_h, 4)
                else:
                    rec.hours_before_game = None

                # Classify once
                if rec.classification is None:
                    event = self._classify(rec)
                    if event is not None:
                        new_events.append(event)

        # -- Step 3: NEVER_SEEN check for pre-registered matches -----------
        for mid in list(self._records):
            rec = self._records[mid]
            if rec.first_seen_timestamp is not None:
                continue  # was seen at least once
            if rec.classification is not None:
                continue  # already classified
            if rec.game_time_utc:
                game_dt = _to_utc(rec.game_time_utc)
                if poll_dt >= game_dt:
                    rec.classification = CLASS_NEVER_SEEN
                    rec.classification_rationale = (
                        f"Match {mid} was never seen in TSL pre-game list "
                        f"before game_time {rec.game_time_utc}"
                    )
                    rec.source_response_context = context
                    new_events.append(rec.to_dict())

        return new_events

    # ------------------------------------------------------------------ #
    # Classification helper
    # ------------------------------------------------------------------ #

    def _classify(self, rec: MarketAvailabilityRecord) -> dict | None:
        """Mutate *rec* with classification and return its dict, or None."""
        hours = rec.hours_before_game
        if hours is None:
            return None

        if hours > self.EARLY_THRESHOLD_HOURS:
            rec.classification = CLASS_WITHDRAWAL_EARLY
            rec.classification_rationale = (
                f"Market disappeared {hours:.2f}h before game_time "
                f"{rec.game_time_utc} — exceeds {self.EARLY_THRESHOLD_HOURS}h "
                "early-withdrawal threshold (HIGH severity)"
            )
        else:
            rec.classification = CLASS_NORMAL_REMOVAL
            rec.classification_rationale = (
                f"Market disappeared {hours:.2f}h before game_time "
                f"{rec.game_time_utc} — within normal {self.EARLY_THRESHOLD_HOURS}h "
                "pre-game window (INFO severity)"
            )
        return rec.to_dict()

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #

    def get_alerts(self) -> list[dict]:
        """Return all records that have been classified (any type)."""
        return [
            r.to_dict()
            for r in self._records.values()
            if r.classification is not None
        ]

    def get_early_withdrawals(self) -> list[dict]:
        """Return only TSL_MARKET_WITHDRAWAL_EARLY records."""
        return [
            r.to_dict()
            for r in self._records.values()
            if r.classification == CLASS_WITHDRAWAL_EARLY
        ]

    def get_state(self) -> dict[str, Any]:
        """Return a shallow copy of the full internal state as plain dicts."""
        return {k: v.to_dict() for k, v in self._records.items()}

    def register_match(
        self,
        match_id: str,
        game_time: str,
        league: str = "",
        home_team: str = "",
        away_team: str = "",
    ) -> None:
        """
        Pre-register a match expected to appear in TSL.

        Enables TSL_MARKET_NEVER_SEEN detection for matches known from an
        external schedule that never surface in the TSL pre-game list.
        """
        if match_id not in self._records:
            self._records[match_id] = MarketAvailabilityRecord(
                match_id=match_id,
                league=league,
                game_time_utc=game_time,
                home_team=home_team,
                away_team=away_team,
                source_name=self.SOURCE_NAME,
            )
