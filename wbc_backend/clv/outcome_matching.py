"""
P26/P25 — Line-Aware CLV Outcome Matching
paper_only=true / diagnostic_only=true

Replaces P22 index-based outcome comparison with name-based matching.
Skips any pair where the outcome name (which encodes the handicap/total line)
changed between pregame and closing snapshots.

P25 CLV Construction Fix: adds line_comparable / line_shift_detected /
excluded_from_clean_clv / clv_status / audit_reason fields to satisfy
P25 CLV audit contract.

Supported market codes: MNL, HDC, OU, OE, TTO
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    LINE_MOVED = "LINE_MOVED"
    MARKET_SHAPE_MISMATCH = "MARKET_SHAPE_MISMATCH"
    MISSING_OUTCOME = "MISSING_OUTCOME"
    PARSE_FAILED = "PARSE_FAILED"
    UNSUPPORTED_MARKET = "UNSUPPORTED_MARKET"


# P25 CLV status vocabulary (maps from MatchStatus)
_CLV_STATUS_MAP: dict[MatchStatus, str] = {
    MatchStatus.MATCHED: "CLV_COMPARABLE",
    MatchStatus.LINE_MOVED: "LINE_SHIFT_UNCOMPARABLE",
    MatchStatus.MARKET_SHAPE_MISMATCH: "LINE_SHIFT_UNCOMPARABLE",
    MatchStatus.MISSING_OUTCOME: "MISSING_CLOSING_ODDS",
    MatchStatus.PARSE_FAILED: "MISSING_OPENING_ODDS",
    MatchStatus.UNSUPPORTED_MARKET: "UNSUPPORTED_MARKET",
}

# Statuses that indicate a line-shift event specifically
_LINE_SHIFT_STATUSES = {MatchStatus.LINE_MOVED, MatchStatus.MARKET_SHAPE_MISMATCH}


@dataclass
class OutcomeMatchResult:
    market_code: str
    outcome_name: str
    status: MatchStatus
    pregame_odds: float | None = None
    closing_odds: float | None = None
    clv_abs: float | None = None
    clv_pct: float | None = None
    skip_reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid_clv(self) -> bool:
        return self.status == MatchStatus.MATCHED

    # ── P25 CLV audit contract fields ─────────────────────────────────────────

    @property
    def clv_status(self) -> str:
        """P25 CLV status vocabulary."""
        return _CLV_STATUS_MAP.get(self.status, "UNSUPPORTED_MARKET")

    @property
    def line_comparable(self) -> bool:
        """True only when the line is identical between pregame and closing."""
        return self.status == MatchStatus.MATCHED

    @property
    def line_shift_detected(self) -> bool:
        """True when the outcome name changed between pregame and closing (HDC/OU/TTO line moved)."""
        return self.status in _LINE_SHIFT_STATUSES

    @property
    def excluded_from_clean_clv(self) -> bool:
        """True for any row that must not contribute to clean CLV analysis."""
        return self.status != MatchStatus.MATCHED

    @property
    def audit_reason(self) -> str:
        """Human-readable reason for exclusion or inclusion."""
        if self.status == MatchStatus.MATCHED:
            return "CLV_COMPARABLE: same line in pregame and closing — CLV valid"
        return self.skip_reason or self.clv_status

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_code": self.market_code,
            "outcome_name": self.outcome_name,
            "status": self.status.value,
            "pregame_odds": self.pregame_odds,
            "closing_odds": self.closing_odds,
            "clv_abs": self.clv_abs,
            "clv_pct": self.clv_pct,
            "skip_reason": self.skip_reason,
            "meta": self.meta,
            # P25 fields
            "clv_status": self.clv_status,
            "line_comparable": self.line_comparable,
            "line_shift_detected": self.line_shift_detected,
            "excluded_from_clean_clv": self.excluded_from_clean_clv,
            "audit_reason": self.audit_reason,
        }


def _compute_clv(pre: float, clo: float) -> tuple[float, float]:
    clv_abs = round(pre - clo, 6)
    clv_pct = round((pre - clo) / clo * 100.0, 4) if clo != 0 else 0.0
    return clv_abs, clv_pct


def _safe_float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _outcome_map(outcomes: list[dict]) -> dict[str, float]:
    """Build {outcomeName: odds} dict; skip unparseable entries."""
    result: dict[str, float] = {}
    for o in outcomes:
        name = o.get("outcomeName", "")
        odds = _safe_float(o.get("odds"))
        if name and odds is not None:
            result[name] = odds
    return result


def _market_shape_mnl(outcomes: list[dict]) -> str:
    n = len(outcomes)
    if n == 2:
        return "MNL_2WAY"
    if n == 3:
        return "MNL_3WAY"
    return "UNKNOWN"


def _match_mnl(
    pre_outcomes: list[dict],
    clo_outcomes: list[dict],
) -> list[OutcomeMatchResult]:
    """
    MNL: match by team name.
    2-way vs 3-way MUST NOT be compared (different index semantics).
    Within same shape, match by outcomeName (team name).
    """
    results: list[OutcomeMatchResult] = []
    pre_shape = _market_shape_mnl(pre_outcomes)
    clo_shape = _market_shape_mnl(clo_outcomes)

    if pre_shape == "UNKNOWN" or clo_shape == "UNKNOWN":
        return [OutcomeMatchResult(
            market_code="MNL",
            outcome_name="<unknown>",
            status=MatchStatus.PARSE_FAILED,
            skip_reason=f"PARSE_FAILED: cannot determine market shape pre={pre_shape} clo={clo_shape}",
        )]

    if pre_shape != clo_shape:
        # 2-way vs 3-way — different products, must not compare
        for o in pre_outcomes:
            results.append(OutcomeMatchResult(
                market_code="MNL",
                outcome_name=o.get("outcomeName", ""),
                status=MatchStatus.MARKET_SHAPE_MISMATCH,
                skip_reason=f"MARKET_SHAPE_MISMATCH: pre={pre_shape} vs clo={clo_shape}",
                meta={"pre_shape": pre_shape, "clo_shape": clo_shape},
            ))
        return results

    pre_map = _outcome_map(pre_outcomes)
    clo_map = _outcome_map(clo_outcomes)

    for name, pre_odds in pre_map.items():
        if name not in clo_map:
            results.append(OutcomeMatchResult(
                market_code="MNL",
                outcome_name=name,
                status=MatchStatus.MISSING_OUTCOME,
                pregame_odds=pre_odds,
                skip_reason=f"MISSING_OUTCOME: '{name}' found in pregame but not in closing",
            ))
            continue
        clo_odds = clo_map[name]
        clv_abs, clv_pct = _compute_clv(pre_odds, clo_odds)
        results.append(OutcomeMatchResult(
            market_code="MNL",
            outcome_name=name,
            status=MatchStatus.MATCHED,
            pregame_odds=pre_odds,
            closing_odds=clo_odds,
            clv_abs=clv_abs,
            clv_pct=clv_pct,
            meta={"market_shape": pre_shape},
        ))
    return results


def _match_line_encoded_market(
    market_code: str,
    pre_outcomes: list[dict],
    clo_outcomes: list[dict],
) -> list[OutcomeMatchResult]:
    """
    HDC / OU / OE / TTO: outcome name encodes line (or fixed side for OE).
    Match by exact outcomeName.  If pre name ≠ clo name → LINE_MOVED (skip).
    No index fallback.
    """
    results: list[OutcomeMatchResult] = []
    pre_map = _outcome_map(pre_outcomes)
    clo_map = _outcome_map(clo_outcomes)

    if not pre_map:
        return [OutcomeMatchResult(
            market_code=market_code,
            outcome_name="<empty>",
            status=MatchStatus.PARSE_FAILED,
            skip_reason="PARSE_FAILED: pregame outcomes empty or unparseable",
        )]

    for name, pre_odds in pre_map.items():
        if name not in clo_map:
            # The line encoded in this outcome name is not present at closing.
            # This means the line moved; do NOT fall back to index.
            results.append(OutcomeMatchResult(
                market_code=market_code,
                outcome_name=name,
                status=MatchStatus.LINE_MOVED,
                pregame_odds=pre_odds,
                skip_reason=f"LINE_MOVED: pregame outcome '{name}' absent in closing (line likely shifted)",
                meta={"available_in_closing": list(clo_map.keys())},
            ))
            continue
        clo_odds = clo_map[name]
        clv_abs, clv_pct = _compute_clv(pre_odds, clo_odds)
        results.append(OutcomeMatchResult(
            market_code=market_code,
            outcome_name=name,
            status=MatchStatus.MATCHED,
            pregame_odds=pre_odds,
            closing_odds=clo_odds,
            clv_abs=clv_abs,
            clv_pct=clv_pct,
        ))
    return results


SUPPORTED_MARKETS = {"MNL", "HDC", "OU", "OE", "TTO"}


def match_outcomes_for_market(
    market_code: str,
    pre_outcomes: list[dict],
    clo_outcomes: list[dict],
) -> list[OutcomeMatchResult]:
    """
    Entry point for line-aware CLV outcome matching.

    Args:
        market_code: TSL market code (MNL/HDC/OU/OE/TTO or other)
        pre_outcomes: list of outcome dicts from pregame snapshot
        clo_outcomes: list of outcome dicts from closing snapshot

    Returns:
        list of OutcomeMatchResult.  Only results with status=MATCHED
        carry valid CLV values; all others must be skipped.
    """
    if market_code not in SUPPORTED_MARKETS:
        return [OutcomeMatchResult(
            market_code=market_code,
            outcome_name="<all>",
            status=MatchStatus.UNSUPPORTED_MARKET,
            skip_reason=f"UNSUPPORTED_MARKET: {market_code} not in {sorted(SUPPORTED_MARKETS)}",
        )]

    if not pre_outcomes or not clo_outcomes:
        return [OutcomeMatchResult(
            market_code=market_code,
            outcome_name="<all>",
            status=MatchStatus.PARSE_FAILED,
            skip_reason="PARSE_FAILED: pregame or closing outcomes list is empty",
        )]

    if market_code == "MNL":
        return _match_mnl(pre_outcomes, clo_outcomes)

    # HDC, OU, OE, TTO all use line-encoded names
    return _match_line_encoded_market(market_code, pre_outcomes, clo_outcomes)
