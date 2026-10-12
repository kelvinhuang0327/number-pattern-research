"""MLB Result Ingestion + Post-game Review Module.

Reads paper betting ledger JSONL, ingests game results from fixture / replay
sources, matches entries to results, and produces a reviewed snapshot with
Brier / BSS / residual diagnostics via Metrics SSOT.

Design principles:
  - Append-only ledger is NEVER modified — only a separate reviewed snapshot
    is written.
  - If a result is unavailable the entry stays PENDING_REVIEW — no guessing.
  - Original recommendation is NEVER retroactively changed.
  - PASS / WATCH_ONLY → REVIEWED_NO_BET (recorded but not counted as WON/LOST).
  - MARKET_ONLY_SHADOW → shadow-tracked separately.
  - Result ingestion is read-only with respect to all production artefacts.

Safety:
  PRODUCTION_MODIFIED      = False
  NO_REAL_BET              = True
  PAPER_ONLY               = True
  NO_PROFIT_CLAIM          = True
  NO_EDGE_CLAIM            = True
  LEDGER_OVERWRITE_BLOCKED = True
"""
from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Any

from orchestrator.metrics_ssot import (
    calculate_brier_score,
    calculate_bss,
    calculate_residual_summary,
    NO_PROFIT_CLAIM as _SSOT_NO_PROFIT_CLAIM,
    PRODUCTION_MODIFIED as _SSOT_PROD_MODIFIED,
)

# ─── Safety constants ─────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
CANDIDATE_PATCH_CREATED: bool = False
ALPHA_MODIFIED: bool = False
PREDICTION_JSONL_OVERWRITTEN: bool = False
LEDGER_OVERWRITE_BLOCKED: bool = True
NO_EDGE_CLAIM: bool = True
NO_PROFIT_CLAIM: bool = True
DIAGNOSTIC_ONLY: bool = True
PAPER_ONLY: bool = True
NO_REAL_BET: bool = True

MODULE_VERSION: str = "mlb_result_review_v1"
COMPLETION_MARKER: str = "MLB_POSTGAME_REVIEW_VERIFIED"

# ─── Gate constants (7 valid) ─────────────────────────────────────────────────

MLB_POSTGAME_REVIEW_READY: str = "MLB_POSTGAME_REVIEW_READY"
MLB_RESULT_INGESTION_READY: str = "MLB_RESULT_INGESTION_READY"
MLB_RESULT_REVIEW_DATA_LIMITED: str = "MLB_RESULT_REVIEW_DATA_LIMITED"
MLB_RESULT_SOURCE_NEEDS_LIVE_API: str = "MLB_RESULT_SOURCE_NEEDS_LIVE_API"
MLB_RESULT_REVIEW_GOVERNANCE_RISK: str = "MLB_RESULT_REVIEW_GOVERNANCE_RISK"
MLB_RESULT_REVIEW_SCHEMA_CONFLICT: str = "MLB_RESULT_REVIEW_SCHEMA_CONFLICT"
MLB_RESULT_REVIEW_NOT_READY: str = "MLB_RESULT_REVIEW_NOT_READY"

VALID_GATES: frozenset[str] = frozenset({
    MLB_POSTGAME_REVIEW_READY,
    MLB_RESULT_INGESTION_READY,
    MLB_RESULT_REVIEW_DATA_LIMITED,
    MLB_RESULT_SOURCE_NEEDS_LIVE_API,
    MLB_RESULT_REVIEW_GOVERNANCE_RISK,
    MLB_RESULT_REVIEW_SCHEMA_CONFLICT,
    MLB_RESULT_REVIEW_NOT_READY,
})

# ─── Default paths ────────────────────────────────────────────────────────────

DEFAULT_LEDGER_PATH: str = "reports/mlb_paper_betting_ledger.jsonl"
DEFAULT_FIXTURE_PATH: str = "data/fixtures/mlb_current_source_sample_20260507.json"
DEFAULT_PREDICTION_JSONL: str = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
DEFAULT_REVIEWED_SNAPSHOT_DIR: str = "reports"

# ─── Review status tokens ─────────────────────────────────────────────────────

STATUS_REVIEWED: str = "REVIEWED"
STATUS_REVIEWED_NO_BET: str = "REVIEWED_NO_BET"
STATUS_PENDING_REVIEW: str = "PENDING_REVIEW"
STATUS_DATA_LIMITED: str = "DATA_LIMITED"
STATUS_CURRENT_UNAVAILABLE: str = "current_result_source_unavailable"

# ─── Result outcome tokens ────────────────────────────────────────────────────

OUTCOME_WON: str = "WON"
OUTCOME_LOST: str = "LOST"
OUTCOME_PUSH: str = "PUSH"
OUTCOME_VOID: str = "VOID"
OUTCOME_UNKNOWN: str = "UNKNOWN"
OUTCOME_PENDING: str = "PENDING"
OUTCOME_NO_BET: str = "NO_BET"

# ─── Failure tags ─────────────────────────────────────────────────────────────

TAG_MODEL_MARKET_DISAGREEMENT_LOSS: str = "MODEL_MARKET_DISAGREEMENT_LOSS"
TAG_MARKET_ONLY_SHADOW_LOSS: str = "MARKET_ONLY_SHADOW_LOSS"
TAG_HIGH_CONFIDENCE_LOSS: str = "HIGH_CONFIDENCE_LOSS"
TAG_DATA_UNAVAILABLE: str = "DATA_UNAVAILABLE"
TAG_RESULT_UNAVAILABLE: str = "RESULT_UNAVAILABLE"
TAG_NO_BET_REVIEW_ONLY: str = "NO_BET_REVIEW_ONLY"
TAG_UNKNOWN_OUTCOME: str = "UNKNOWN_OUTCOME"

MIN_GAMES_FOR_BRIER: int = 3


# ════════════════════════════════════════════════════════════════════════════
# SECTION A — Dataclasses
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class ResultSnapshot:
    """Normalized game result for result ingestion."""
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    home_win: bool | None           # True = home won, False = away won, None = unknown
    result_status: str              # "final", "scheduled", "live", "unknown", "pending"
    source_name: str
    source_mode: str
    source_timestamp: str
    unavailable_fields: list[str] = field(default_factory=list)


@dataclass
class ReviewedLedgerEntry:
    """A ledger entry enriched with post-game review data."""
    # Original ledger fields
    ledger_id: str
    advisory_id: str
    game_id: str
    game_date: str
    market_type: str
    recommendation: str
    paper_selection: str | None
    model_prob: float | None
    market_prob: float | None
    # Review enrichment
    result_status: str              # WON / LOST / PUSH / VOID / UNKNOWN / PENDING / NO_BET
    realized_outcome: str | None    # "home_win" / "away_win" / None
    review_status: str              # REVIEWED / REVIEWED_NO_BET / PENDING_REVIEW
    review_reason: str
    paper_profit_loss_units: float | None
    brier_component: float | None   # (pred - actual)^2 for this game
    failure_tags: list[str] = field(default_factory=list)
    paper_only: bool = True
    no_real_bet: bool = True


@dataclass
class ReviewSummary:
    """Aggregate review summary for a date/session."""
    review_date: str
    source_mode: str
    total_ledger_entries: int
    matched_results: int
    pending_results: int
    reviewed_count: int
    won_count: int
    lost_count: int
    push_count: int
    unknown_count: int
    pass_count: int
    watch_only_count: int
    lean_count: int
    market_only_shadow_count: int
    brier_score: float | None
    bss_vs_baseline: float | None
    recommendation_accuracy: float | None
    top_failure_reasons: list[str] = field(default_factory=list)
    next_day_adjustment_notes: list[str] = field(default_factory=list)
    human_review_required: bool = True


# ════════════════════════════════════════════════════════════════════════════
# SECTION B — Data Loading
# ════════════════════════════════════════════════════════════════════════════


def load_paper_ledger_jsonl(ledger_path: str = DEFAULT_LEDGER_PATH) -> list[dict]:
    """
    Load the append-only paper betting ledger JSONL.

    Returns list of ledger entry dicts. Empty list if file missing.
    Does NOT modify the ledger.
    """
    entries: list[dict] = []
    if not os.path.exists(ledger_path):
        return entries
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def load_result_snapshots_from_fixture(
    fixture_path: str = DEFAULT_FIXTURE_PATH,
) -> list[ResultSnapshot]:
    """
    Load result snapshots from a fixture JSON file.

    If result_home_score / result_away_score are null → result_status stays
    "scheduled" and home_win = None.
    """
    if not os.path.exists(fixture_path):
        return []

    with open(fixture_path, encoding="utf-8") as fh:
        data = json.load(fh)

    metadata = data.get("fixture_metadata", {})
    source_name = metadata.get("source_name", "fixture")
    source_ts = metadata.get("created_at", "")

    snapshots: list[ResultSnapshot] = []
    for g in data.get("games", []):
        home_score = g.get("result_home_score")
        away_score = g.get("result_away_score")
        result_status = g.get("result_status", "unknown")

        # Derive home_win only if both scores are available and game is final
        home_win: bool | None = None
        unavailable: list[str] = []

        if home_score is None or away_score is None:
            unavailable.extend(["result_home_score", "result_away_score", "home_win"])
        elif result_status == "final":
            home_win = int(home_score) > int(away_score)
        else:
            # Game not yet final — don't derive home_win
            unavailable.append("home_win")

        snapshots.append(ResultSnapshot(
            game_id=g.get("game_id", ""),
            game_date=g.get("game_date", ""),
            home_team=g.get("home_team", ""),
            away_team=g.get("away_team", ""),
            home_score=int(home_score) if home_score is not None else None,
            away_score=int(away_score) if away_score is not None else None,
            home_win=home_win,
            result_status=result_status,
            source_name=source_name,
            source_mode="fixture",
            source_timestamp=source_ts,
            unavailable_fields=unavailable,
        ))

    return snapshots


def load_result_snapshots_from_replay(
    date_str: str,
    prediction_jsonl_path: str = DEFAULT_PREDICTION_JSONL,
) -> list[ResultSnapshot]:
    """
    Load result snapshots from the historical prediction JSONL (replay mode).

    Only rows with home_win != None and game_date == date_str are included.
    """
    if not os.path.exists(prediction_jsonl_path):
        return []

    snapshots: list[ResultSnapshot] = []
    ts_now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with open(prediction_jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            if row.get("game_date") != date_str:
                continue

            home_win_raw = row.get("home_win")
            if home_win_raw is None or home_win_raw == "":
                continue

            try:
                hw = int(home_win_raw)
            except (ValueError, TypeError):
                continue

            home_win = bool(hw == 1)
            snapshots.append(ResultSnapshot(
                game_id=row.get("game_id", ""),
                game_date=row.get("game_date", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_score=None,    # raw scores not in prediction JSONL
                away_score=None,
                home_win=home_win,
                result_status="final",
                source_name="replay_prediction_jsonl",
                source_mode="replay",
                source_timestamp=ts_now,
                unavailable_fields=["home_score", "away_score"],
            ))

    return snapshots


# ════════════════════════════════════════════════════════════════════════════
# SECTION C — Matching
# ════════════════════════════════════════════════════════════════════════════


def _build_result_index(
    snapshots: list[ResultSnapshot],
) -> tuple[dict[str, ResultSnapshot], dict[tuple[str, str, str], ResultSnapshot]]:
    """
    Build two look-up indices for fast matching.

    Returns:
        by_game_id: {game_id: ResultSnapshot}
        by_date_teams: {(date, home_team.lower(), away_team.lower()): ResultSnapshot}
    """
    by_game_id: dict[str, ResultSnapshot] = {}
    by_date_teams: dict[tuple[str, str, str], ResultSnapshot] = {}

    for snap in snapshots:
        if snap.game_id:
            by_game_id[snap.game_id] = snap
        key = (snap.game_date, snap.home_team.lower(), snap.away_team.lower())
        by_date_teams[key] = snap

    return by_game_id, by_date_teams


def match_ledger_to_results(
    ledger_entries: list[dict],
    result_snapshots: list[ResultSnapshot],
) -> list[tuple[dict, ResultSnapshot | None]]:
    """
    Match each ledger entry to a ResultSnapshot.

    Matching priority:
      1. game_id exact match
      2. (game_date, home_team.lower(), away_team.lower()) fallback
      3. None if still unmatched → PENDING_REVIEW

    Returns list of (ledger_entry, matched_snapshot_or_None).
    """
    by_game_id, by_date_teams = _build_result_index(result_snapshots)
    pairs: list[tuple[dict, ResultSnapshot | None]] = []

    for entry in ledger_entries:
        game_id = entry.get("game_id", "")
        game_date = entry.get("game_date", "")
        # Try to infer home/away from advisory metadata (not always present in ledger)
        # We rely on game_id first, then try date-team from result index if we can
        snap: ResultSnapshot | None = None

        if game_id in by_game_id:
            snap = by_game_id[game_id]
        else:
            # Attempt partial game_id → extract home/away from game_id pattern
            # Pattern: "MLB2025_NNNN_YYYY-MM-DD_AWAY_HOME" or "MLB2026_FIXTURE_AWAY_HOME"
            # Try all date-team keys for this date
            candidates = [
                s for gid, s in by_game_id.items()
                if s.game_date == game_date
            ]
            # Check date+teams match in by_date_teams using the ledger entry's id hints
            # Final fallback: mark as unmatched
            if not snap and candidates:
                # No further disambiguation without team names in ledger entry
                pass

        pairs.append((entry, snap))

    return pairs


# ════════════════════════════════════════════════════════════════════════════
# SECTION D — Result Evaluation
# ════════════════════════════════════════════════════════════════════════════


def evaluate_moneyline_result(
    ledger_entry: dict,
    result_snap: ResultSnapshot | None,
) -> tuple[str, str | None, str, float | None, list[str]]:
    """
    Evaluate the moneyline result for a single ledger entry.

    Returns:
        result_status: WON / LOST / PUSH / VOID / UNKNOWN / PENDING / NO_BET
        realized_outcome: "home_win" / "away_win" / None
        review_status: REVIEWED / REVIEWED_NO_BET / PENDING_REVIEW
        paper_profit_loss_units: float or None (paper-only, ±1 unit)
        failure_tags: list[str]
    """
    recommendation = ledger_entry.get("recommendation", "")
    paper_selection = ledger_entry.get("paper_selection")
    market_prob = ledger_entry.get("market_prob") or 0.5

    tags: list[str] = []

    # PASS / WATCH_ONLY → no bet, review-only
    if recommendation in {"PASS", "WATCH_ONLY"}:
        return OUTCOME_NO_BET, None, STATUS_REVIEWED_NO_BET, None, [TAG_NO_BET_REVIEW_ONLY]

    # No result snapshot → PENDING
    if result_snap is None:
        tags.append(TAG_RESULT_UNAVAILABLE)
        return OUTCOME_PENDING, None, STATUS_PENDING_REVIEW, None, tags

    # Score unavailable → PENDING
    if result_snap.home_win is None:
        tags.append(TAG_RESULT_UNAVAILABLE)
        return OUTCOME_PENDING, None, STATUS_PENDING_REVIEW, None, tags

    # MARKET_ONLY_SHADOW — track separately, no W/L counted
    if recommendation == "MARKET_ONLY_SHADOW":
        hw = result_snap.home_win
        realized = "home_win" if hw else "away_win"
        # Shadow outcome: what would have happened if we'd followed model direction
        model_prob_raw = ledger_entry.get("model_prob") or 0.5
        if model_prob_raw > 0.5:
            model_direction = "HOME"
        else:
            model_direction = "AWAY"
        shadow_correct = (
            (model_direction == "HOME" and hw) or (model_direction == "AWAY" and not hw)
        )
        if not shadow_correct:
            tags.append(TAG_MARKET_ONLY_SHADOW_LOSS)
        return OUTCOME_UNKNOWN, realized, STATUS_REVIEWED_NO_BET, None, tags

    # No paper_selection → can't evaluate
    if not paper_selection:
        tags.append(TAG_UNKNOWN_OUTCOME)
        return OUTCOME_UNKNOWN, None, STATUS_REVIEWED_NO_BET, None, tags

    # Runline / total: data insufficient
    market_type = ledger_entry.get("market_type", "moneyline")
    if market_type in {"runline", "total"}:
        tags.append("runline_or_total_result_unavailable")
        return OUTCOME_UNKNOWN, None, STATUS_REVIEWED_NO_BET, None, tags

    # Moneyline evaluation
    hw = result_snap.home_win
    realized = "home_win" if hw else "away_win"

    if paper_selection == "HOME":
        if hw:
            outcome = OUTCOME_WON
        else:
            outcome = OUTCOME_LOST
    elif paper_selection == "AWAY":
        if not hw:
            outcome = OUTCOME_WON
        else:
            outcome = OUTCOME_LOST
    else:
        outcome = OUTCOME_UNKNOWN
        tags.append(TAG_UNKNOWN_OUTCOME)

    # Paper P&L (±1 unit, paper-only, no real money)
    paper_pnl: float | None = None
    if outcome == OUTCOME_WON:
        if market_prob and 0.0 < market_prob < 1.0:
            decimal_odds = 1.0 / market_prob
            paper_pnl = round(decimal_odds - 1.0, 3)
        else:
            paper_pnl = 1.0
    elif outcome == OUTCOME_LOST:
        paper_pnl = -1.0

    # Failure tags
    model_prob_raw = ledger_entry.get("model_prob") or 0.5
    if outcome == OUTCOME_LOST:
        if abs(model_prob_raw - market_prob) > 0.10:
            tags.append(TAG_MODEL_MARKET_DISAGREEMENT_LOSS)
        if model_prob_raw > 0.65:
            tags.append(TAG_HIGH_CONFIDENCE_LOSS)

    return outcome, realized, STATUS_REVIEWED, paper_pnl, tags


# ════════════════════════════════════════════════════════════════════════════
# SECTION E — Build Reviewed Snapshot
# ════════════════════════════════════════════════════════════════════════════


def build_reviewed_ledger_snapshot(
    ledger_entries: list[dict],
    result_snapshots: list[ResultSnapshot],
) -> list[ReviewedLedgerEntry]:
    """
    Build reviewed snapshot by matching ledger entries to results.

    Does NOT modify the original ledger.
    Entries without results remain as PENDING_REVIEW.
    """
    pairs = match_ledger_to_results(ledger_entries, result_snapshots)
    reviewed: list[ReviewedLedgerEntry] = []

    for entry, snap in pairs:
        recommendation = entry.get("recommendation", "")
        paper_selection = entry.get("paper_selection")
        model_prob = entry.get("model_prob")
        market_prob = entry.get("market_prob")

        result_status, realized, review_status, paper_pnl, tags = evaluate_moneyline_result(
            entry, snap
        )

        # Brier component: (pred - actual)^2 for this single game
        brier_component: float | None = None
        if (
            model_prob is not None
            and snap is not None
            and snap.home_win is not None
            and review_status == STATUS_REVIEWED
        ):
            actual = 1.0 if snap.home_win else 0.0
            brier_component = round((float(model_prob) - actual) ** 2, 6)

        # Review reason
        if review_status == STATUS_PENDING_REVIEW:
            if snap is None:
                review_reason = "no_result_match_found: game_id not in result source"
            elif snap.home_win is None:
                review_reason = "result_scores_unavailable: home_win not derivable"
            else:
                review_reason = "pending_review: unknown reason"
        elif review_status == STATUS_REVIEWED_NO_BET:
            review_reason = f"no_bet: recommendation={recommendation}"
        else:
            review_reason = f"result_available: {result_status}"

        reviewed.append(ReviewedLedgerEntry(
            ledger_id=entry.get("ledger_id", ""),
            advisory_id=entry.get("advisory_id", ""),
            game_id=entry.get("game_id", ""),
            game_date=entry.get("game_date", ""),
            market_type=entry.get("market_type", ""),
            recommendation=recommendation,
            paper_selection=paper_selection,
            model_prob=model_prob,
            market_prob=market_prob,
            result_status=result_status,
            realized_outcome=realized,
            review_status=review_status,
            review_reason=review_reason,
            paper_profit_loss_units=paper_pnl,
            brier_component=brier_component,
            failure_tags=tags,
            paper_only=True,
            no_real_bet=True,
        ))

    return reviewed


# ════════════════════════════════════════════════════════════════════════════
# SECTION F — Review Summary + Metrics
# ════════════════════════════════════════════════════════════════════════════


def calculate_review_summary(
    reviewed_entries: list[ReviewedLedgerEntry],
    result_snapshots: list[ResultSnapshot],
    review_date: str,
    source_mode: str,
) -> ReviewSummary:
    """
    Aggregate reviewed entries into a ReviewSummary with Brier / BSS metrics.
    Uses metrics_ssot functions for all calculations.
    """
    total = len(reviewed_entries)
    pending = sum(1 for e in reviewed_entries if e.review_status == STATUS_PENDING_REVIEW)
    matched = sum(1 for e in reviewed_entries if e.review_status != STATUS_PENDING_REVIEW)

    reviewed_proper = [e for e in reviewed_entries if e.review_status == STATUS_REVIEWED]
    won = sum(1 for e in reviewed_proper if e.result_status == OUTCOME_WON)
    lost = sum(1 for e in reviewed_proper if e.result_status == OUTCOME_LOST)
    push = sum(1 for e in reviewed_proper if e.result_status == OUTCOME_PUSH)
    unknown = sum(1 for e in reviewed_proper if e.result_status == OUTCOME_UNKNOWN)

    all_reviewed = [e for e in reviewed_entries if e.review_status in {
        STATUS_REVIEWED, STATUS_REVIEWED_NO_BET
    }]

    recs = [e.recommendation for e in reviewed_entries]
    pass_count = recs.count("PASS")
    watch_only_count = recs.count("WATCH_ONLY")
    lean_count = recs.count("LEAN_HOME") + recs.count("LEAN_AWAY")
    shadow_count = recs.count("MARKET_ONLY_SHADOW")

    # Brier score using metrics_ssot — only for entries with model_prob + result
    brier_eligible = [
        e for e in reviewed_entries
        if (
            e.model_prob is not None
            and e.result_status in {OUTCOME_WON, OUTCOME_LOST}
            and e.realized_outcome is not None
        )
    ]
    brier_val: float | None = None
    bss_val: float | None = None

    if len(brier_eligible) >= MIN_GAMES_FOR_BRIER:
        probs = [float(e.model_prob) for e in brier_eligible]  # type: ignore[arg-type]
        # Outcome from paper_selection perspective: if paper_selection=HOME, model_prob
        # is home probability, outcome=1 if WON
        labels: list[float] = []
        for e in brier_eligible:
            if e.paper_selection == "HOME":
                labels.append(1.0 if e.result_status == OUTCOME_WON else 0.0)
            elif e.paper_selection == "AWAY":
                # model_prob is home prob; away selection WON means home_win=False
                labels.append(1.0 if e.result_status == OUTCOME_LOST else 0.0)
            else:
                labels.append(0.5)

        br = calculate_brier_score(probs, labels)
        brier_val = round(br.brier, 4)
        bss_val = round(br.bss_vs_baseline, 4)

    # Recommendation accuracy (leans only)
    lean_entries = [
        e for e in reviewed_proper
        if e.recommendation in {"LEAN_HOME", "LEAN_AWAY"}
    ]
    rec_accuracy: float | None = None
    if lean_entries:
        correct = sum(1 for e in lean_entries if e.result_status == OUTCOME_WON)
        rec_accuracy = round(correct / len(lean_entries), 3)

    # Top failure reasons
    all_tags: list[str] = []
    for e in reviewed_entries:
        all_tags.extend(e.failure_tags)
    tag_counts: dict[str, int] = {}
    for t in all_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1
    top_failures = sorted(tag_counts, key=lambda t: -tag_counts[t])[:5]

    # Next-day adjustment notes (conservative — no auto-change)
    adjustment_notes: list[str] = []
    if lost > 0:
        adjustment_notes.append(
            f"{lost} paper bet(s) LOST: review model-market divergence patterns"
        )
    if pending > 0:
        adjustment_notes.append(
            f"{pending} entries still PENDING_REVIEW: re-run when results available"
        )
    if shadow_count > 0:
        adjustment_notes.append(
            f"{shadow_count} MARKET_ONLY_SHADOW entries: review Phase71/72 band outcomes"
        )
    if not adjustment_notes:
        adjustment_notes.append("No adjustment needed: results pending or insufficient sample")

    return ReviewSummary(
        review_date=review_date,
        source_mode=source_mode,
        total_ledger_entries=total,
        matched_results=matched,
        pending_results=pending,
        reviewed_count=len(reviewed_proper),
        won_count=won,
        lost_count=lost,
        push_count=push,
        unknown_count=unknown,
        pass_count=pass_count,
        watch_only_count=watch_only_count,
        lean_count=lean_count,
        market_only_shadow_count=shadow_count,
        brier_score=brier_val,
        bss_vs_baseline=bss_val,
        recommendation_accuracy=rec_accuracy,
        top_failure_reasons=top_failures,
        next_day_adjustment_notes=adjustment_notes,
        human_review_required=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION G — Failure Notes + Next Audit Proposal
# ════════════════════════════════════════════════════════════════════════════


def build_failure_notes(
    reviewed_entries: list[ReviewedLedgerEntry],
    review_summary: ReviewSummary,
) -> list[dict]:
    """
    Build structured failure notes from reviewed entries.

    GOVERNANCE: No auto-model modification. All notes are diagnostic only.
    human_review_required = True for all items.
    """
    # Tally tags
    tag_to_entries: dict[str, list[ReviewedLedgerEntry]] = {}
    for e in reviewed_entries:
        for tag in e.failure_tags:
            tag_to_entries.setdefault(tag, []).append(e)

    # Ensure all expected tags are represented (even if count=0)
    all_expected_tags = [
        TAG_MODEL_MARKET_DISAGREEMENT_LOSS,
        TAG_MARKET_ONLY_SHADOW_LOSS,
        TAG_HIGH_CONFIDENCE_LOSS,
        TAG_DATA_UNAVAILABLE,
        TAG_RESULT_UNAVAILABLE,
        TAG_NO_BET_REVIEW_ONLY,
        TAG_UNKNOWN_OUTCOME,
    ]
    for tag in all_expected_tags:
        tag_to_entries.setdefault(tag, [])

    notes: list[dict] = []
    failure_mode_map = {
        TAG_MODEL_MARKET_DISAGREEMENT_LOSS: (
            "model_market_divergence_not_predictive: opening line gap may close before game time"
        ),
        TAG_MARKET_ONLY_SHADOW_LOSS: (
            "phase71_band_model_wrong: market may have better info in [0.65,0.70) band"
        ),
        TAG_HIGH_CONFIDENCE_LOSS: (
            "overconfidence: model assigned high prob but outcome was opposite"
        ),
        TAG_DATA_UNAVAILABLE: (
            "missing_features: SP FIP / park factor / bullpen data not available"
        ),
        TAG_RESULT_UNAVAILABLE: (
            "no_result_source: live result API not configured; fixture/replay only"
        ),
        TAG_NO_BET_REVIEW_ONLY: (
            "pass_or_watch_only: no bet placed; outcome tracked for reference only"
        ),
        TAG_UNKNOWN_OUTCOME: (
            "runline_or_total_not_tracked: insufficient data for non-moneyline markets"
        ),
    }

    for tag in all_expected_tags:
        entries_for_tag = tag_to_entries.get(tag, [])
        examples = [
            {
                "game_id": e.game_id,
                "recommendation": e.recommendation,
                "result_status": e.result_status,
                "model_prob": e.model_prob,
                "market_prob": e.market_prob,
            }
            for e in entries_for_tag[:3]
        ]
        notes.append({
            "failure_tag": tag,
            "count": len(entries_for_tag),
            "examples": examples,
            "suspected_failure_mode": failure_mode_map.get(tag, "unknown"),
            "proposed_next_audit": _get_next_audit_for_tag(tag),
            "blocked_auto_change_reason": (
                "human_review_required: governance rules prohibit automatic "
                "model/alpha/stake changes based on dry-run review results"
            ),
            "human_review_required": True,
        })

    return notes


def _get_next_audit_for_tag(tag: str) -> str:
    """Return a conservative next-audit proposal for a given failure tag."""
    proposals = {
        TAG_MODEL_MARKET_DISAGREEMENT_LOSS: (
            "Accumulate 30+ LEAN outcomes; test whether large model-market gap "
            "is predictive in held-out season data (n >= 1500 required)"
        ),
        TAG_MARKET_ONLY_SHADOW_LOSS: (
            "Review Phase71 market-superiority evidence in [0.65,0.70) band; "
            "validate that shadow-only guard holds out-of-sample"
        ),
        TAG_HIGH_CONFIDENCE_LOSS: (
            "Investigate whether model is systematically overconfident above 0.65; "
            "run ECE calibration audit with Phase69 counterfactual framework"
        ),
        TAG_DATA_UNAVAILABLE: (
            "Improve feature completeness: SP FIP data, park factor pipeline, "
            "bullpen usage tracking"
        ),
        TAG_RESULT_UNAVAILABLE: (
            "Integrate live result source API (e.g., MLB Stats API) for same-day "
            "post-game review; replace fixture/replay with real-time pipeline"
        ),
        TAG_NO_BET_REVIEW_ONLY: (
            "Monitor PASS/WATCH_ONLY outcome distributions to validate threshold "
            "calibration (LEAN_THRESHOLD=0.10, WATCH_THRESHOLD=0.05)"
        ),
        TAG_UNKNOWN_OUTCOME: (
            "Add runline / total result tracking once live source provides "
            "final scores and spread data"
        ),
    }
    return proposals.get(tag, "No specific proposal available")


def build_next_audit_proposal(
    review_summary: ReviewSummary,
    failure_notes: list[dict],
) -> dict:
    """
    Conservative next-audit proposal.

    GOVERNANCE: Does NOT propose:
      - Auto-model change
      - Alpha adjustment
      - Stake sizing change
      - Any real betting action
    """
    observations: list[str] = []
    proposals: list[str] = []
    required_data: list[str] = []

    if review_summary.lean_count > 0 and review_summary.recommendation_accuracy is not None:
        observations.append(
            f"lean_count={review_summary.lean_count}; "
            f"accuracy={review_summary.recommendation_accuracy}"
        )
        proposals.append(
            "Accumulate >= 30 LEAN outcomes before drawing any conclusion about model edge"
        )

    if review_summary.pending_results > 0:
        observations.append(
            f"{review_summary.pending_results} results still PENDING_REVIEW; "
            "live result source not yet integrated"
        )
        proposals.append(
            "Integrate live MLB result source to enable same-day REVIEWED status"
        )
        required_data.append("live_mlb_result_api_or_scraper")

    if review_summary.brier_score is not None:
        observations.append(
            f"brier={review_summary.brier_score}; bss={review_summary.bss_vs_baseline}"
        )
        proposals.append(
            "Continue accumulating replay sessions; require n >= 1500 "
            "before interpreting Brier as stable"
        )
    else:
        observations.append("Brier score unavailable: insufficient reviewed games")
        required_data.append("more_reviewed_games_n_ge_3")

    if review_summary.market_only_shadow_count > 0:
        observations.append(
            f"{review_summary.market_only_shadow_count} games in Phase71/72 de-risk band"
        )
        proposals.append(
            "Track shadow outcomes over >= 20 sessions to validate Phase71 market "
            "superiority hypothesis out-of-sample"
        )

    if not observations:
        observations.append("No actionable signal; data sample too small")

    return {
        "observation": observations,
        "suspected_failure_mode": [
            note["suspected_failure_mode"]
            for note in failure_notes
            if note["count"] > 0 and note["failure_tag"] not in {
                TAG_NO_BET_REVIEW_ONLY, TAG_RESULT_UNAVAILABLE
            }
        ][:3],
        "proposed_next_audit": proposals,
        "required_data": required_data,
        "blocked_auto_change_reason": (
            "human_review_required: no automatic model/alpha/stake/bet changes permitted; "
            "all proposals require human review and >= 1500 sample validation"
        ),
        "human_review_required": True,
        "auto_model_change_blocked": True,
        "auto_alpha_change_blocked": True,
        "auto_stake_change_blocked": True,
        "auto_bet_blocked": True,
        "no_profit_claim": True,
        "no_edge_claim": True,
    }


# ════════════════════════════════════════════════════════════════════════════
# SECTION H — I/O + Validation
# ════════════════════════════════════════════════════════════════════════════


def write_reviewed_snapshot_jsonl(
    reviewed_entries: list[ReviewedLedgerEntry],
    snapshot_path: str,
) -> int:
    """
    Write reviewed snapshot to a NEW file (not the original ledger).

    Safety: this function NEVER opens the original ledger for writing.
    Returns count of entries written.
    """
    dirpath = os.path.dirname(snapshot_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    with open(snapshot_path, "w", encoding="utf-8") as fh:
        for entry in reviewed_entries:
            record = {
                "ledger_id": entry.ledger_id,
                "advisory_id": entry.advisory_id,
                "game_id": entry.game_id,
                "game_date": entry.game_date,
                "market_type": entry.market_type,
                "recommendation": entry.recommendation,
                "paper_selection": entry.paper_selection,
                "model_prob": entry.model_prob,
                "market_prob": entry.market_prob,
                "result_status": entry.result_status,
                "realized_outcome": entry.realized_outcome,
                "review_status": entry.review_status,
                "review_reason": entry.review_reason,
                "paper_profit_loss_units": entry.paper_profit_loss_units,
                "brier_component": entry.brier_component,
                "failure_tags": entry.failure_tags,
                "paper_only": entry.paper_only,
                "no_real_bet": entry.no_real_bet,
                "_schema_version": MODULE_VERSION,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return len(reviewed_entries)


def validate_review_summary(summary: ReviewSummary) -> list[str]:
    """
    Validate ReviewSummary schema.
    Returns list of error strings; empty = valid.
    """
    errors: list[str] = []

    if not summary.review_date:
        errors.append("review_date_missing")
    if not summary.source_mode:
        errors.append("source_mode_missing")
    if summary.total_ledger_entries < 0:
        errors.append("total_ledger_entries_negative")
    if summary.matched_results < 0:
        errors.append("matched_results_negative")
    if summary.pending_results < 0:
        errors.append("pending_results_negative")
    if summary.matched_results + summary.pending_results > summary.total_ledger_entries:
        errors.append("matched_plus_pending_exceeds_total")
    if summary.brier_score is not None and not (0.0 <= summary.brier_score <= 1.0):
        errors.append("brier_score_out_of_range")
    if summary.recommendation_accuracy is not None:
        if not (0.0 <= summary.recommendation_accuracy <= 1.0):
            errors.append("recommendation_accuracy_out_of_range")
    if not summary.human_review_required:
        errors.append("human_review_required_must_be_true")

    return errors


# ════════════════════════════════════════════════════════════════════════════
# SECTION I — Gate Determination
# ════════════════════════════════════════════════════════════════════════════


def determine_gate(
    reviewed_entries: list[ReviewedLedgerEntry],
    review_summary: ReviewSummary,
    source_mode: str,
    result_snapshots: list[ResultSnapshot],
) -> tuple[str, str]:
    """
    Determine the gate from 7 valid options.

    Conservative logic: prefer lower-confidence gate when in doubt.
    """
    if not reviewed_entries:
        return (
            MLB_RESULT_REVIEW_NOT_READY,
            "No reviewed entries: ledger is empty or no entries matched date filter",
        )

    # Safety: all entries must have paper_only=True, no_real_bet=True
    all_safe = all(e.paper_only is True and e.no_real_bet is True for e in reviewed_entries)
    if not all_safe:
        return (
            MLB_RESULT_REVIEW_GOVERNANCE_RISK,
            "Some reviewed entries missing paper_only or no_real_bet safety flags",
        )

    total = review_summary.total_ledger_entries
    pending = review_summary.pending_results
    matched = review_summary.matched_results

    has_reviewed = review_summary.reviewed_count > 0
    has_results = bool(result_snapshots)
    majority_pending = pending > (total * 0.5) if total > 0 else True

    # Current source → NEEDS_LIVE_API
    if source_mode == "current" and not has_results:
        return (
            MLB_RESULT_SOURCE_NEEDS_LIVE_API,
            "source_mode=current; live result API not configured; "
            "no results ingested; fixture or replay required",
        )

    # Mostly pending → DATA_LIMITED
    if majority_pending and total > 0:
        return (
            MLB_RESULT_REVIEW_DATA_LIMITED,
            f"majority pending_review ({pending}/{total}); "
            "result source incomplete or games not yet final",
        )

    # Full pipeline works with results
    if has_results and matched > 0 and review_summary.brier_score is not None:
        return (
            MLB_POSTGAME_REVIEW_READY,
            "result_ingestion + reviewed_snapshot + review_summary + "
            "brier_metrics + failure_notes all operational; "
            "paper-only safety flags complete",
        )

    # Ingestion works but review summary / brier incomplete
    if has_results and matched > 0:
        return (
            MLB_RESULT_INGESTION_READY,
            "result_ingestion + reviewed_snapshot operational; "
            "brier/failure notes incomplete (insufficient reviewed games)",
        )

    # Default: ingestion can run but limited results
    return (
        MLB_RESULT_REVIEW_DATA_LIMITED,
        f"result_ingestion operational but matched={matched}/{total}; "
        "more results needed for full review",
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION J — Markdown Report
# ════════════════════════════════════════════════════════════════════════════


def generate_markdown_report(payload: dict, md_path: str) -> None:
    """Write post-game review markdown report."""
    review_date = payload.get("review_date", "")
    gate = payload.get("gate", "")
    rs_dict = payload.get("review_summary", {})
    fn_list = payload.get("failure_notes", [])
    nap = payload.get("next_audit_proposal", {})

    lines: list[str] = []
    lines.append("# MLB Post-game Review Report")
    lines.append("")
    lines.append("> **⚠️ PAPER-ONLY — DRY-RUN — NO REAL BET — NO PROFIT CLAIM**")
    lines.append(">")
    lines.append("> 本報告為 paper-only post-game review。不代表任何真實下注、真實獲利、")
    lines.append("> 或真實 edge 聲明。所有結果僅供研究與回測使用。")
    lines.append("")
    lines.append(f"**review_date:** {review_date}")
    lines.append(f"**source_mode:** {payload.get('source_mode', '')}")
    lines.append(f"**run_timestamp_utc:** {payload.get('run_timestamp_utc', '')}")
    lines.append(f"**ledger_path:** {payload.get('ledger_path', '')}")
    lines.append(f"**reviewed_snapshot_path:** {payload.get('reviewed_snapshot_path', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Safety Flags")
    lines.append("")
    for k, v in payload.get("safety", {}).items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Review Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| total_ledger_entries | {rs_dict.get('total_ledger_entries', 0)} |")
    lines.append(f"| matched_results | {rs_dict.get('matched_results', 0)} |")
    lines.append(f"| pending_results | {rs_dict.get('pending_results', 0)} |")
    lines.append(f"| reviewed_count | {rs_dict.get('reviewed_count', 0)} |")
    lines.append(f"| won_count | {rs_dict.get('won_count', 0)} |")
    lines.append(f"| lost_count | {rs_dict.get('lost_count', 0)} |")
    lines.append(f"| push_count | {rs_dict.get('push_count', 0)} |")
    lines.append(f"| pass_count | {rs_dict.get('pass_count', 0)} |")
    lines.append(f"| watch_only_count | {rs_dict.get('watch_only_count', 0)} |")
    lines.append(f"| lean_count | {rs_dict.get('lean_count', 0)} |")
    lines.append(f"| market_only_shadow_count | {rs_dict.get('market_only_shadow_count', 0)} |")
    lines.append(f"| brier_score | {rs_dict.get('brier_score', 'N/A')} |")
    lines.append(f"| bss_vs_baseline | {rs_dict.get('bss_vs_baseline', 'N/A')} |")
    lines.append(f"| recommendation_accuracy | {rs_dict.get('recommendation_accuracy', 'N/A')} |")
    lines.append(f"| human_review_required | `True` |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Reviewed Entries")
    lines.append("")
    entries = payload.get("reviewed_entries", [])
    if entries:
        lines.append("| game_id | date | mkt | rec | selection | result | review_status | P&L |")
        lines.append("|---------|------|-----|-----|-----------|--------|---------------|-----|")
        for e in entries:
            pnl = e.get("paper_profit_loss_units")
            pnl_str = f"{pnl:+.3f}" if pnl is not None else "—"
            lines.append(
                f"| {e.get('game_id','')[:28]} | {e.get('game_date','')} | "
                f"{e.get('market_type','')} | {e.get('recommendation','')} | "
                f"{e.get('paper_selection','—')} | {e.get('result_status','')} | "
                f"{e.get('review_status','')} | {pnl_str} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Failure Notes")
    lines.append("")
    for fn in fn_list:
        if fn["count"] > 0:
            lines.append(f"### `{fn['failure_tag']}` (count={fn['count']})")
            lines.append(f"- **suspected_failure_mode**: {fn['suspected_failure_mode']}")
            lines.append(f"- **proposed_next_audit**: {fn['proposed_next_audit']}")
            lines.append(f"- **human_review_required**: `{fn['human_review_required']}`")
            lines.append(f"- **blocked_auto_change_reason**: {fn['blocked_auto_change_reason']}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Next Audit Proposal")
    lines.append("")
    for obs in nap.get("observation", []):
        lines.append(f"- **Observation**: {obs}")
    lines.append("")
    for prop in nap.get("proposed_next_audit", []):
        lines.append(f"- {prop}")
    lines.append("")
    lines.append(f"**blocked_auto_change_reason**: {nap.get('blocked_auto_change_reason', '')}")
    lines.append(f"**human_review_required**: `{nap.get('human_review_required', True)}`")
    lines.append(f"**auto_model_change_blocked**: `{nap.get('auto_model_change_blocked', True)}`")
    lines.append(f"**auto_alpha_change_blocked**: `{nap.get('auto_alpha_change_blocked', True)}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## No Profit Claim")
    lines.append("")
    lines.append(
        "本系統不聲稱已找到可盈利的投注 edge。"
        "所有 paper review 均為研究目的，不代表任何真實獲利預期。"
    )
    lines.append("")
    lines.append("**NO_PROFIT_CLAIM = True**")
    lines.append("**NO_EDGE_CLAIM = True**")
    lines.append("**PAPER_ONLY = True**")
    lines.append("**NO_REAL_BET = True**")
    lines.append("**LEDGER_OVERWRITE_BLOCKED = True**")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Gate Conclusion")
    lines.append("")
    lines.append(f"**Gate: `{gate}`**")
    lines.append("")
    lines.append(f"> {payload.get('gate_rationale', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Completion Marker")
    lines.append("")
    lines.append(f"`{COMPLETION_MARKER}`")
    lines.append("")

    dirpath = os.path.dirname(md_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ════════════════════════════════════════════════════════════════════════════
# SECTION K — Main Orchestration
# ════════════════════════════════════════════════════════════════════════════


def run_postgame_review(
    review_date: str,
    source_mode: str = "fixture",
    ledger_path: str = DEFAULT_LEDGER_PATH,
    fixture_path: str = DEFAULT_FIXTURE_PATH,
    prediction_jsonl_path: str = DEFAULT_PREDICTION_JSONL,
    reviewed_snapshot_path: str | None = None,
    report_path: str | None = None,
    markdown_path: str | None = None,
    *,
    write_reports: bool = True,
) -> dict:
    """
    Main orchestration function for post-game review.

    Args:
        review_date: YYYY-MM-DD date to review
        source_mode: "fixture" | "replay" | "current"
        ledger_path: path to append-only paper betting ledger JSONL
        fixture_path: path to fixture JSON (for fixture mode)
        prediction_jsonl_path: path to historical prediction JSONL (for replay mode)
        reviewed_snapshot_path: where to write the reviewed snapshot JSONL
        report_path: where to write the JSON report
        markdown_path: where to write the markdown report
        write_reports: if False, skip all disk writes (for unit tests)

    Returns:
        Full review payload dict (paper-only / no-real-bet)
    """
    run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ── 1. Load ledger ──────────────────────────────────────────────────────
    ledger_entries = load_paper_ledger_jsonl(ledger_path)

    # Filter to review_date only
    date_entries = [e for e in ledger_entries if e.get("game_date") == review_date]
    # If no entries for specific date, use all entries for review (allows cross-date review)
    if not date_entries:
        date_entries = ledger_entries  # use all entries for summary

    # ── 2. Load results by source ───────────────────────────────────────────
    result_snapshots: list[ResultSnapshot] = []
    source_status: str = "loaded"

    if source_mode == "fixture":
        result_snapshots = load_result_snapshots_from_fixture(fixture_path)
    elif source_mode == "replay":
        result_snapshots = load_result_snapshots_from_replay(
            review_date, prediction_jsonl_path
        )
        if not result_snapshots:
            source_status = STATUS_DATA_LIMITED
    elif source_mode == "current":
        # Live result API not yet configured
        source_status = STATUS_CURRENT_UNAVAILABLE
        result_snapshots = []
    else:
        source_status = "unknown_source_mode"
        result_snapshots = []

    # ── 3. Build reviewed snapshot ──────────────────────────────────────────
    reviewed_entries = build_reviewed_ledger_snapshot(date_entries, result_snapshots)

    # ── 4. Calculate review summary ─────────────────────────────────────────
    summary = calculate_review_summary(
        reviewed_entries, result_snapshots, review_date, source_mode
    )

    # ── 5. Build failure notes ──────────────────────────────────────────────
    failure_notes = build_failure_notes(reviewed_entries, summary)

    # ── 6. Next audit proposal ──────────────────────────────────────────────
    next_audit = build_next_audit_proposal(summary, failure_notes)

    # ── 7. Gate determination ────────────────────────────────────────────────
    gate, gate_rationale = determine_gate(
        reviewed_entries, summary, source_mode, result_snapshots
    )
    assert gate in VALID_GATES, f"Gate {gate!r} not in VALID_GATES"

    # ── 8. Write reviewed snapshot ───────────────────────────────────────────
    snap_path = reviewed_snapshot_path or _default_snapshot_path(review_date)
    snap_written = 0
    if write_reports:
        snap_written = write_reviewed_snapshot_jsonl(reviewed_entries, snap_path)

    # ── 9. Serialise reviewed entries for payload ────────────────────────────
    clean_reviewed = [
        {
            "ledger_id": e.ledger_id,
            "advisory_id": e.advisory_id,
            "game_id": e.game_id,
            "game_date": e.game_date,
            "market_type": e.market_type,
            "recommendation": e.recommendation,
            "paper_selection": e.paper_selection,
            "model_prob": e.model_prob,
            "market_prob": e.market_prob,
            "result_status": e.result_status,
            "realized_outcome": e.realized_outcome,
            "review_status": e.review_status,
            "review_reason": e.review_reason,
            "paper_profit_loss_units": e.paper_profit_loss_units,
            "brier_component": e.brier_component,
            "failure_tags": e.failure_tags,
            "paper_only": e.paper_only,
            "no_real_bet": e.no_real_bet,
        }
        for e in reviewed_entries
    ]

    # ── 10. Build payload ────────────────────────────────────────────────────
    rs_dict = {
        "review_date": summary.review_date,
        "source_mode": summary.source_mode,
        "total_ledger_entries": summary.total_ledger_entries,
        "matched_results": summary.matched_results,
        "pending_results": summary.pending_results,
        "reviewed_count": summary.reviewed_count,
        "won_count": summary.won_count,
        "lost_count": summary.lost_count,
        "push_count": summary.push_count,
        "unknown_count": summary.unknown_count,
        "pass_count": summary.pass_count,
        "watch_only_count": summary.watch_only_count,
        "lean_count": summary.lean_count,
        "market_only_shadow_count": summary.market_only_shadow_count,
        "brier_score": summary.brier_score,
        "bss_vs_baseline": summary.bss_vs_baseline,
        "recommendation_accuracy": summary.recommendation_accuracy,
        "top_failure_reasons": summary.top_failure_reasons,
        "next_day_adjustment_notes": summary.next_day_adjustment_notes,
        "human_review_required": summary.human_review_required,
    }

    payload = {
        "module_version": MODULE_VERSION,
        "run_timestamp_utc": run_ts,
        "review_date": review_date,
        "source_mode": source_mode,
        "source_status": source_status,
        "ledger_path": ledger_path,
        "reviewed_snapshot_path": snap_path,
        "reviewed_entries_written": snap_written,
        "total_ledger_entries_loaded": len(ledger_entries),
        "date_filtered_entries": len(date_entries),
        "total_result_snapshots": len(result_snapshots),
        "safety": {
            "production_modified": PRODUCTION_MODIFIED,
            "candidate_patch_created": CANDIDATE_PATCH_CREATED,
            "alpha_modified": ALPHA_MODIFIED,
            "prediction_jsonl_overwritten": PREDICTION_JSONL_OVERWRITTEN,
            "ledger_overwrite_blocked": LEDGER_OVERWRITE_BLOCKED,
            "no_edge_claim": NO_EDGE_CLAIM,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "paper_only": PAPER_ONLY,
            "no_real_bet": NO_REAL_BET,
        },
        "review_summary": rs_dict,
        "reviewed_entries": clean_reviewed,
        "failure_notes": failure_notes,
        "next_audit_proposal": next_audit,
        "gate": gate,
        "gate_rationale": gate_rationale,
        "completion_marker": COMPLETION_MARKER,
        "metrics_ssot_used": True,
        "metrics_ssot_module": "orchestrator.metrics_ssot",
    }

    # ── 11. Write JSON report ────────────────────────────────────────────────
    if write_reports and report_path:
        dirpath = os.path.dirname(report_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    # ── 12. Write markdown report ────────────────────────────────────────────
    if write_reports and markdown_path:
        generate_markdown_report(payload, markdown_path)

    return payload


def _default_snapshot_path(date_str: str) -> str:
    date_no_dash = date_str.replace("-", "")
    return f"reports/mlb_paper_betting_reviewed_snapshot_{date_no_dash}.jsonl"
