"""
wbc_backend/recommendation/p16_p18_policy_loader.py

P16.6 — P18 Selected Policy Loader and Validator.

Loads the selected_strategy_policy.json produced by P18 and validates
all invariants required for P16.6 gate re-run.

Invariants:
  - gate_decision == P18_STRATEGY_POLICY_RISK_REPAIRED
  - edge_threshold present and finite
  - max_stake_cap present and finite
  - kelly_fraction present and finite
  - odds_decimal_max present and finite
  - max_drawdown_pct <= 25.0 (fraction: <= 0.25 interpreted from pct field)
  - sharpe_ratio >= 0.0
  - n_bets >= 50
  - production_ready == False (if present)
  - paper_only == True (if present)

PAPER_ONLY: This loader is used exclusively for PAPER gate re-run.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass


# ── Gate constants ─────────────────────────────────────────────────────────────

P18_GATE_REPAIRED = "P18_STRATEGY_POLICY_RISK_REPAIRED"
VALIDATION_ERROR_CODE = "P16_6_BLOCKED_INVALID_P18_POLICY"

MAX_DRAWDOWN_LIMIT_PCT = 25.0   # max_drawdown_pct must be <= 25.0
SHARPE_FLOOR = 0.0
N_BETS_FLOOR = 50


# ── Data contract ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class P18SelectedPolicy:
    selected_policy_id: str
    edge_threshold: float
    max_stake_cap: float
    kelly_fraction: float
    odds_decimal_max: float
    n_bets: int
    max_drawdown_pct: float
    sharpe_ratio: float
    gate_decision: str
    paper_only: bool
    production_ready: bool
    # optional fields (may be 0.0 if not present in JSON)
    roi_mean: float
    roi_ci_low_95: float
    roi_ci_high_95: float
    hit_rate: float


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error_code: str | None
    error_message: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_float(v: object, field: str) -> float:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"P18 policy field '{field}' must be numeric, got {v!r}")
    if not math.isfinite(f):
        raise ValueError(f"P18 policy field '{field}' must be finite, got {f}")
    return f


def _safe_int(v: object, field: str) -> int:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"P18 policy field '{field}' must be integer, got {v!r}")


# ── Loader ─────────────────────────────────────────────────────────────────────

def load_p18_selected_policy(path: str) -> P18SelectedPolicy:
    """
    Load P18 selected_strategy_policy.json and return a typed P18SelectedPolicy.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If required fields are missing or malformed.
    """
    with open(path) as f:
        data: dict = json.load(f)

    required = [
        "selected_policy_id",
        "edge_threshold",
        "max_stake_cap",
        "kelly_fraction",
        "odds_decimal_max",
        "n_bets",
        "max_drawdown_pct",
        "sharpe_ratio",
        "gate_decision",
    ]
    for field in required:
        if field not in data:
            raise ValueError(
                f"P18 policy JSON missing required field '{field}' in {path}"
            )

    return P18SelectedPolicy(
        selected_policy_id=str(data["selected_policy_id"]),
        edge_threshold=_safe_float(data["edge_threshold"], "edge_threshold"),
        max_stake_cap=_safe_float(data["max_stake_cap"], "max_stake_cap"),
        kelly_fraction=_safe_float(data["kelly_fraction"], "kelly_fraction"),
        odds_decimal_max=_safe_float(data["odds_decimal_max"], "odds_decimal_max"),
        n_bets=_safe_int(data["n_bets"], "n_bets"),
        max_drawdown_pct=_safe_float(data["max_drawdown_pct"], "max_drawdown_pct"),
        sharpe_ratio=_safe_float(data["sharpe_ratio"], "sharpe_ratio"),
        gate_decision=str(data["gate_decision"]),
        paper_only=bool(data.get("paper_only", True)),
        production_ready=bool(data.get("production_ready", False)),
        roi_mean=_safe_float(data.get("roi_mean", 0.0), "roi_mean"),
        roi_ci_low_95=_safe_float(data.get("roi_ci_low_95", 0.0), "roi_ci_low_95"),
        roi_ci_high_95=_safe_float(data.get("roi_ci_high_95", 0.0), "roi_ci_high_95"),
        hit_rate=_safe_float(data.get("hit_rate", 0.0), "hit_rate"),
    )


# ── Validator ──────────────────────────────────────────────────────────────────

def validate_p18_selected_policy(policy: P18SelectedPolicy) -> ValidationResult:
    """
    Validate P18SelectedPolicy against all P16.6 invariants.

    Returns ValidationResult with valid=True if all checks pass,
    or valid=False with error_code=P16_6_BLOCKED_INVALID_P18_POLICY otherwise.
    """
    def fail(msg: str) -> ValidationResult:
        return ValidationResult(
            valid=False,
            error_code=VALIDATION_ERROR_CODE,
            error_message=msg,
        )

    # gate_decision must be P18_STRATEGY_POLICY_RISK_REPAIRED
    if policy.gate_decision != P18_GATE_REPAIRED:
        return fail(
            f"gate_decision must be '{P18_GATE_REPAIRED}', "
            f"got '{policy.gate_decision}'"
        )

    # edge_threshold must be finite and positive
    if not math.isfinite(policy.edge_threshold) or policy.edge_threshold < 0.0:
        return fail(f"edge_threshold must be >= 0, got {policy.edge_threshold}")

    # max_stake_cap must be finite and positive
    if not math.isfinite(policy.max_stake_cap) or policy.max_stake_cap <= 0.0:
        return fail(f"max_stake_cap must be > 0, got {policy.max_stake_cap}")

    # kelly_fraction must be finite and positive
    if not math.isfinite(policy.kelly_fraction) or policy.kelly_fraction <= 0.0:
        return fail(f"kelly_fraction must be > 0, got {policy.kelly_fraction}")

    # odds_decimal_max must be finite and > 1.0
    if not math.isfinite(policy.odds_decimal_max) or policy.odds_decimal_max <= 1.0:
        return fail(f"odds_decimal_max must be > 1.0, got {policy.odds_decimal_max}")

    # max_drawdown_pct <= 25.0
    if policy.max_drawdown_pct > MAX_DRAWDOWN_LIMIT_PCT:
        return fail(
            f"max_drawdown_pct={policy.max_drawdown_pct:.4f} exceeds "
            f"limit={MAX_DRAWDOWN_LIMIT_PCT}"
        )

    # sharpe_ratio >= 0.0
    if policy.sharpe_ratio < SHARPE_FLOOR:
        return fail(
            f"sharpe_ratio={policy.sharpe_ratio:.4f} below floor={SHARPE_FLOOR}"
        )

    # n_bets >= 50
    if policy.n_bets < N_BETS_FLOOR:
        return fail(f"n_bets={policy.n_bets} < floor={N_BETS_FLOOR}")

    # production_ready must be False
    if policy.production_ready:
        return fail("production_ready must be False for PAPER_ONLY gate")

    # paper_only must be True
    if not policy.paper_only:
        return fail("paper_only must be True for PAPER_ONLY gate")

    return ValidationResult(valid=True, error_code=None, error_message=None)
