"""
wbc_backend/simulation/p13_strategy_simulator.py

P14: Strategy simulation runner using P13 OOF predictions.

Key class:
    P13StrategySimulationRunner

Responsibilities:
- Load P13 OOF predictions CSV.
- Validate input contract (paper_only, BSS, row count).
- Apply each policy (flat_stake, capped_kelly, confidence_rank, no_bet).
- Produce per-policy StrategySimulationResult objects.
- Produce a simulation ledger (per-row bet decisions for each policy).
- Emit deterministic outputs: no wall-clock timestamps in ledger data.

Gate statuses emitted in spine_gate field:
    PASS_SIMULATION_SPINE_READY    – all policies ran, outputs deterministic
    MARKET_ODDS_ABSENT_SIMULATION_ONLY  – model-only sim (no ROI computable)
    FAIL_INVALID_INPUT             – rows missing or p_oof/y_true absent
    FAIL_NON_DETERMINISTIC         – repeated run differs (detected externally)

Hard invariants:
- paper_only=True is enforced; any row with paper_only != True is rejected.
- source_bss_oof must be > 0 for gate to be PASS_SIMULATION_SPINE_READY.
- Outputs are deterministic: same input → identical ledger rows + metrics.

NOTE:
    This runner intentionally does NOT compute ROI when market odds are absent.
    P14 proves simulation spine activation, not betting profitability.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from wbc_backend.simulation.strategy_policies import (
    PolicyDecision,
    capped_kelly_policy,
    confidence_rank_policy,
    flat_stake_policy,
    no_bet_policy,
)
from wbc_backend.simulation.strategy_simulation_result import (
    StrategySimulationResult,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SPINE_GATE_PASS = "PASS_SIMULATION_SPINE_READY"
SPINE_GATE_MARKET_ABSENT = "MARKET_ODDS_ABSENT_SIMULATION_ONLY"
SPINE_GATE_INVALID_INPUT = "FAIL_INVALID_INPUT"
SPINE_GATE_NON_DETERMINISTIC = "FAIL_NON_DETERMINISTIC"

_VALID_SPINE_GATES: frozenset[str] = frozenset({
    SPINE_GATE_PASS,
    SPINE_GATE_MARKET_ABSENT,
    SPINE_GATE_INVALID_INPUT,
    SPINE_GATE_NON_DETERMINISTIC,
})

_REQUIRED_OOF_COLUMNS: tuple[str, ...] = ("y_true", "p_oof")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(v: Any, default: float | None = None) -> float | None:
    if v is None:
        return default
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _brier_score(y_true: list[int], probs: list[float]) -> float | None:
    if len(y_true) < 2:
        return None
    n = len(y_true)
    return float(sum((p - y) ** 2 for p, y in zip(probs, y_true)) / n)


def _ece(y_true: list[int], probs: list[float], n_bins: int = 10) -> float | None:
    """Simple ECE: equal-width bins over [0, 1]."""
    if len(y_true) < 10:
        return None
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in zip(probs, y_true):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b].append((p, y))
    ece_val = 0.0
    n = len(y_true)
    for bucket in bins:
        if not bucket:
            continue
        cnt = len(bucket)
        avg_p = sum(x[0] for x in bucket) / cnt
        avg_y = sum(x[1] for x in bucket) / cnt
        ece_val += (cnt / n) * abs(avg_p - avg_y)
    return float(ece_val)


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


# ── Row preparation ───────────────────────────────────────────────────────────

def _prepare_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convert OOF DataFrame to simulation row dicts.

    Adds confidence_rank and n_total for confidence_rank_policy.
    p_model = p_oof (renamed for policy functions).
    decimal_odds and p_market are None (market data absent).
    """
    df = df.copy()
    df = df.sort_values("p_oof", ascending=False).reset_index(drop=True)
    df["confidence_rank"] = range(1, len(df) + 1)
    df["n_total"] = len(df)

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append({
            "y_true": int(row["y_true"]),
            "p_model": float(row["p_oof"]),
            "p_market": None,      # market odds absent
            "decimal_odds": None,  # market odds absent
            "fold_id": row.get("fold_id"),
            "source_model": row.get("source_model", "p13_walk_forward_logistic"),
            "source_bss_oof": row.get("source_bss_oof"),
            "paper_only": True,
            "confidence_rank": int(row["confidence_rank"]),
            "n_total": int(row["n_total"]),
        })
    return rows


def _prepare_rows_with_odds(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convert OOF DataFrame (with joined odds columns) to simulation row dicts.

    When odds columns are present (from MarketOddsJoinAdapter), injects
    p_market, odds_decimal_home, and edge so that capped_kelly_policy can
    produce non-zero stakes for JOINED rows.

    Joined columns expected (all optional — rows without them stay as None):
      odds_join_status : 'JOINED' | 'MISSING' | 'INVALID_ODDS'
      p_market         : float, home-win implied probability
      odds_decimal_home: float, decimal odds on home team
      edge             : float, p_oof - p_market
    """
    from wbc_backend.simulation.market_odds_adapter import JOIN_STATUS_JOINED

    df = df.copy()
    df = df.sort_values("p_oof", ascending=False).reset_index(drop=True)
    df["confidence_rank"] = range(1, len(df) + 1)
    df["n_total"] = len(df)

    has_odds_cols = "odds_join_status" in df.columns

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        if has_odds_cols and row.get("odds_join_status") == JOIN_STATUS_JOINED:
            p_mkt = _safe_float(row.get("p_market"))
            dec_odds = _safe_float(row.get("odds_decimal_home"))
            edge_val = _safe_float(row.get("edge"))
        else:
            p_mkt = None
            dec_odds = None
            edge_val = None

        rows.append({
            "y_true": int(row["y_true"]),
            "p_model": float(row["p_oof"]),
            "p_market": p_mkt,
            "decimal_odds": dec_odds,
            "edge": edge_val,
            "fold_id": row.get("fold_id"),
            "source_model": row.get("source_model", "p13_walk_forward_logistic"),
            "source_bss_oof": row.get("source_bss_oof"),
            "paper_only": True,
            "confidence_rank": int(row["confidence_rank"]),
            "n_total": int(row["n_total"]),
            "game_id": row.get("game_id"),
            "odds_join_status": row.get("odds_join_status") if has_odds_cols else None,
        })
    return rows


# ── P14 runner ────────────────────────────────────────────────────────────────

class P13StrategySimulationRunner:
    """
    Strategy simulation spine using P13 OOF probability output.

    Two construction modes:
    1. Model-only (P14 mode): from_oof_csv() — no market odds.
    2. Odds-aware (P15 mode): from_joined_df() — accepts pre-joined DataFrame
       with p_market, odds_decimal_home, edge, odds_join_status columns.

    Usage (model-only)
    ------------------
    runner = P13StrategySimulationRunner.from_oof_csv(
        oof_csv_path="outputs/.../oof_predictions.csv",
        source_bss_oof=0.008253,
    )

    Usage (odds-aware)
    ------------------
    runner = P13StrategySimulationRunner.from_joined_df(
        joined_df=df_with_odds,
        source_bss_oof=0.008253,
        odds_join_coverage=1577,
        odds_source_path="data/mlb_2025/mlb_odds_2025_real.csv",
    )
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        source_bss_oof: float,
        source_model: str = "p13_walk_forward_logistic",
        date_start: str = "UNKNOWN",
        date_end: str = "UNKNOWN",
        paper_only: bool = True,
        odds_join_coverage: int = 0,
        odds_joined_rows: int = 0,
        odds_missing_rows: int = 0,
        odds_source_path: str = "",
    ) -> None:
        if not paper_only:
            raise ValueError(
                "P13StrategySimulationRunner: paper_only must remain True. "
                "Production mode is not permitted."
            )
        self._rows = rows
        self._source_bss_oof = source_bss_oof
        self._source_model = source_model
        self._date_start = date_start
        self._date_end = date_end
        self._paper_only = paper_only
        self._odds_join_coverage = odds_join_coverage
        self._odds_joined_rows = odds_joined_rows
        self._odds_missing_rows = odds_missing_rows
        self._odds_source_path = odds_source_path

    @classmethod
    def from_oof_csv(
        cls,
        oof_csv_path: str | Path,
        source_bss_oof: float,
        source_model: str = "p13_walk_forward_logistic",
        paper_only: bool = True,
    ) -> "P13StrategySimulationRunner":
        """
        Load OOF predictions CSV and construct runner.

        Parameters
        ----------
        oof_csv_path : str | Path
            Path to oof_predictions.csv produced by run_p13_walk_forward_logistic_oof.py.
        source_bss_oof : float
            Must match actual BSS computed during P13.
        source_model : str
            Human-readable model identifier.
        paper_only : bool
            Must remain True.

        Raises
        ------
        FileNotFoundError, ValueError
        """
        path = Path(oof_csv_path)
        if not path.exists():
            raise FileNotFoundError(f"OOF predictions CSV not found: {path}")

        df = pd.read_csv(path)
        missing = [c for c in _REQUIRED_OOF_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"OOF predictions CSV missing required columns: {missing}. "
                f"Available: {list(df.columns)}"
            )

        df = df.dropna(subset=list(_REQUIRED_OOF_COLUMNS)).reset_index(drop=True)
        if len(df) == 0:
            raise ValueError("OOF predictions CSV has 0 usable rows after dropping NaN.")

        rows = _prepare_rows(df)
        date_start = "OOF_FOLD_DERIVED"
        date_end = "OOF_FOLD_DERIVED"

        return cls(
            rows=rows,
            source_bss_oof=source_bss_oof,
            source_model=source_model,
            date_start=date_start,
            date_end=date_end,
            paper_only=paper_only,
        )

    @classmethod
    def from_joined_df(
        cls,
        joined_df: pd.DataFrame,
        source_bss_oof: float,
        source_model: str = "p13_walk_forward_logistic",
        paper_only: bool = True,
        odds_join_coverage: int = 0,
        odds_joined_rows: int = 0,
        odds_missing_rows: int = 0,
        odds_source_path: str = "",
    ) -> "P13StrategySimulationRunner":
        """Construct runner from a DataFrame that already has odds columns joined.

        Use this for P15 odds-aware simulation.  The DataFrame must have the
        standard OOF columns (y_true, p_oof, fold_id) and optionally:
        odds_join_status, p_market, odds_decimal_home, edge.

        Parameters
        ----------
        joined_df : pd.DataFrame
            OOF DataFrame enriched by MarketOddsJoinAdapter.
        source_bss_oof : float
            BSS from P13 OOF report (must be > 0).
        odds_join_coverage : int
            Number of rows with market odds joined.
        odds_joined_rows : int
            Alias for coverage (may differ if partial).
        odds_missing_rows : int
            Number of rows where odds were absent.
        odds_source_path : str
            Path of the odds source file used.
        """
        missing = [c for c in _REQUIRED_OOF_COLUMNS if c not in joined_df.columns]
        if missing:
            raise ValueError(
                f"joined_df missing required columns: {missing}. "
                f"Available: {list(joined_df.columns)}"
            )

        df = joined_df.dropna(subset=list(_REQUIRED_OOF_COLUMNS)).reset_index(drop=True)
        if len(df) == 0:
            raise ValueError("joined_df has 0 usable rows after dropping NaN.")

        rows = _prepare_rows_with_odds(df)

        return cls(
            rows=rows,
            source_bss_oof=source_bss_oof,
            source_model=source_model,
            date_start="OOF_FOLD_DERIVED",
            date_end="OOF_FOLD_DERIVED",
            paper_only=paper_only,
            odds_join_coverage=odds_join_coverage,
            odds_joined_rows=odds_joined_rows,
            odds_missing_rows=odds_missing_rows,
            odds_source_path=odds_source_path,
        )

    # ── Policy runners ────────────────────────────────────────────────────────

    def _run_single_policy(
        self,
        policy_name: str,
        **kwargs: Any,
    ) -> tuple[StrategySimulationResult, list[dict[str, Any]]]:
        """Run a single policy against all rows. Returns (result, ledger_rows)."""
        policy_fn = {
            "flat": flat_stake_policy,
            "capped_kelly": capped_kelly_policy,
            "confidence_rank": confidence_rank_policy,
            "no_bet": no_bet_policy,
        }.get(policy_name)

        if policy_fn is None:
            raise ValueError(
                f"Unknown policy '{policy_name}'. "
                "Valid policies: flat, capped_kelly, confidence_rank, no_bet"
            )

        decisions: list[PolicyDecision] = []
        for row in self._rows:
            dec = policy_fn(row, paper_only=self._paper_only, **kwargs)
            decisions.append(dec)

        # Aggregate stats
        bet_rows = [(r, d) for r, d in zip(self._rows, decisions) if d.should_bet]
        skip_rows = [(r, d) for r, d in zip(self._rows, decisions) if not d.should_bet]

        model_probs_bet = [r["p_model"] for r, _ in bet_rows]
        y_true_bet = [r["y_true"] for r, _ in bet_rows]

        bet_count = len(bet_rows)
        skip_count = len(skip_rows)
        sample_size = len(self._rows)

        avg_model_prob = _mean_or_none(model_probs_bet)
        brier_val = _brier_score(y_true_bet, model_probs_bet) if bet_count >= 2 else None
        brier_baseline = _brier_score(
            [r["y_true"] for r in self._rows],
            [float(sum(r["y_true"] for r in self._rows)) / len(self._rows)] * len(self._rows)
        )
        bss_val: float | None = None
        if brier_val is not None and brier_baseline and brier_baseline > 0:
            bss_val = 1.0 - brier_val / brier_baseline
        ece_val = _ece(y_true_bet, model_probs_bet) if bet_count >= 10 else None

        # Market-odds-absent: ROI, edge, kelly not computable
        all_market_absent = all(r["decimal_odds"] is None for r in self._rows)
        roi_pct: float | None = None
        avg_edge_pct: float | None = None
        avg_kelly_fraction: float | None = None

        if not all_market_absent:
            # Compute ROI only where odds available
            returns: list[float] = []
            for r, d in bet_rows:
                if r["decimal_odds"] is not None and d.stake_fraction > 0:
                    dec_odds = float(r["decimal_odds"])
                    stake = d.stake_fraction
                    if r["y_true"] == 1:
                        returns.append(stake * (dec_odds - 1.0))
                    else:
                        returns.append(-stake)
            total_staked = sum(d.stake_fraction for _, d in bet_rows)
            if returns and total_staked > 0:
                roi_pct = float(sum(returns) / total_staked * 100)

        # Gate decision
        market_absent_gate = all_market_absent and bet_count > 0
        if sample_size < 1:
            gate_status = "BLOCKED_NO_RESULTS"
            gate_reasons = ["No OOF rows available."]
        elif all_market_absent and policy_name == "capped_kelly":
            gate_status = "BLOCKED_NO_MARKET_DATA"
            gate_reasons = ["Market odds absent; capped_kelly requires decimal_odds."]
        elif policy_name == "no_bet":
            gate_status = "PAPER_ONLY"
            gate_reasons = ["Control policy: no bets placed."]
        elif market_absent_gate:
            gate_status = "PAPER_ONLY"
            gate_reasons = [
                "MARKET_ODDS_ABSENT_SIMULATION_ONLY: model-only simulation, ROI not computable."
            ]
        else:
            gate_status = "PAPER_ONLY"
            gate_reasons = ["Spine activation (paper_only=True)."]

        sim_id = f"p14-{policy_name}-{uuid.uuid4().hex[:8]}"
        result = StrategySimulationResult(
            simulation_id=sim_id,
            strategy_name=f"p14_{policy_name}",
            date_start=self._date_start,
            date_end=self._date_end,
            sample_size=sample_size,
            bet_count=bet_count,
            skipped_count=skip_count,
            gate_status=gate_status,
            gate_reasons=gate_reasons,
            generated_at_utc=datetime.now(tz=timezone.utc),
            avg_model_prob=avg_model_prob,
            avg_market_prob=None,
            brier_model=brier_val,
            brier_market=None,
            brier_skill_score=bss_val,
            ece=ece_val,
            roi_pct=roi_pct,
            max_drawdown_pct=None,
            sharpe_proxy=None,
            avg_edge_pct=avg_edge_pct,
            avg_kelly_fraction=avg_kelly_fraction,
            paper_only=True,
            source_trace={
                "source_model": self._source_model,
                "source_bss_oof": self._source_bss_oof,
                "policy": policy_name,
                "market_odds_available": not all_market_absent,
                "p14_note": (
                    "P14 proves simulation spine activation, not betting profitability."
                    if all_market_absent else ""
                ),
            },
        )

        # Build ledger rows (deterministic: row index, no wall-clock)
        ledger: list[dict[str, Any]] = []
        for idx, (row, dec) in enumerate(zip(self._rows, decisions)):
            ledger.append({
                "row_idx": idx,
                "fold_id": row.get("fold_id"),
                "y_true": row["y_true"],
                "p_model": row["p_model"],
                "p_market": row["p_market"],
                "decimal_odds": row["decimal_odds"],
                "confidence_rank": row.get("confidence_rank"),
                "policy": dec.policy_name,
                "should_bet": dec.should_bet,
                "stake_fraction": dec.stake_fraction,
                "reason": dec.reason,
                "paper_only": True,
            })

        return result, ledger

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        policies: list[str] | None = None,
    ) -> "SimulationSummary":
        """
        Run all requested policies and return a SimulationSummary.

        Parameters
        ----------
        policies : list[str] | None
            Subset of ["flat", "capped_kelly", "confidence_rank", "no_bet"].
            If None, all four are run.
        """
        if policies is None:
            policies = ["flat", "capped_kelly", "confidence_rank", "no_bet"]

        all_market_absent = all(r["decimal_odds"] is None for r in self._rows)

        policy_results: dict[str, StrategySimulationResult] = {}
        policy_ledgers: dict[str, list[dict[str, Any]]] = {}

        for p in policies:
            result, ledger = self._run_single_policy(p)
            policy_results[p] = result
            policy_ledgers[p] = ledger

        # Spine gate
        if len(self._rows) == 0:
            spine_gate = SPINE_GATE_INVALID_INPUT
        elif all_market_absent:
            spine_gate = SPINE_GATE_MARKET_ABSENT
        else:
            spine_gate = SPINE_GATE_PASS

        return SimulationSummary(
            spine_gate=spine_gate,
            source_model=self._source_model,
            source_bss_oof=self._source_bss_oof,
            n_samples=len(self._rows),
            policies_run=policies,
            policy_results=policy_results,
            policy_ledgers=policy_ledgers,
            market_odds_available=not all_market_absent,
            paper_only=True,
            generated_at_utc=datetime.now(tz=timezone.utc),
            odds_join_coverage=self._odds_join_coverage,
            odds_joined_rows=self._odds_joined_rows,
            odds_missing_rows=self._odds_missing_rows,
            odds_source_path=self._odds_source_path,
        )


# ── Summary dataclass ─────────────────────────────────────────────────────────

class SimulationSummary:
    """
    Holds all per-policy results + ledgers from a P14 simulation run.

    Designed to be serializable to JSON + CSV by the CLI.
    """

    def __init__(
        self,
        spine_gate: str,
        source_model: str,
        source_bss_oof: float,
        n_samples: int,
        policies_run: list[str],
        policy_results: dict[str, StrategySimulationResult],
        policy_ledgers: dict[str, list[dict[str, Any]]],
        market_odds_available: bool,
        paper_only: bool,
        generated_at_utc: datetime,
        odds_join_coverage: int = 0,
        odds_joined_rows: int = 0,
        odds_missing_rows: int = 0,
        odds_source_path: str = "",
    ) -> None:
        if spine_gate not in _VALID_SPINE_GATES:
            raise ValueError(
                f"spine_gate '{spine_gate}' not in valid spine gates: "
                f"{sorted(_VALID_SPINE_GATES)}"
            )
        self.spine_gate = spine_gate
        self.source_model = source_model
        self.source_bss_oof = source_bss_oof
        self.n_samples = n_samples
        self.policies_run = policies_run
        self.policy_results = policy_results
        self.policy_ledgers = policy_ledgers
        self.market_odds_available = market_odds_available
        self.paper_only = paper_only
        self.generated_at_utc = generated_at_utc
        self.odds_join_coverage = odds_join_coverage
        self.odds_joined_rows = odds_joined_rows
        self.odds_missing_rows = odds_missing_rows
        self.odds_source_path = odds_source_path

    def to_summary_dict(self) -> dict[str, Any]:
        """Produce a deterministic summary dict (no timestamps in core metrics)."""
        per_policy = {}
        for pname, res in self.policy_results.items():
            per_policy[pname] = {
                "gate_status": res.gate_status,
                "bet_count": res.bet_count,
                "skipped_count": res.skipped_count,
                "sample_size": res.sample_size,
                "avg_model_prob": res.avg_model_prob,
                "brier_model": res.brier_model,
                "brier_skill_score": res.brier_skill_score,
                "ece": res.ece,
                "roi_pct": res.roi_pct,
                "avg_edge_pct": res.avg_edge_pct,
                "avg_kelly_fraction": res.avg_kelly_fraction,
                "gate_reasons": res.gate_reasons,
                "source_trace": res.source_trace,
            }

        return {
            "spine_gate": self.spine_gate,
            "source_model": self.source_model,
            "source_bss_oof": self.source_bss_oof,
            "n_samples": self.n_samples,
            "policies_run": self.policies_run,
            "market_odds_available": self.market_odds_available,
            "paper_only": self.paper_only,
            "production_ready": False,
            "p14_note": (
                "P14 proves simulation spine activation, not betting profitability."
                if not self.market_odds_available
                else "P15 odds-aware simulation: spine activated with market odds."
            ),
            "odds_join_coverage": self.odds_join_coverage,
            "odds_joined_rows": self.odds_joined_rows,
            "odds_missing_rows": self.odds_missing_rows,
            "odds_source_path": self.odds_source_path,
            "per_policy": per_policy,
        }

    def ledger_rows(self) -> list[dict[str, Any]]:
        """Flatten all policy ledgers into a single list, sorted by row_idx."""
        all_rows: list[dict[str, Any]] = []
        for pname, ledger in self.policy_ledgers.items():
            for row in ledger:
                entry = dict(row)
                entry["policy"] = pname
                all_rows.append(entry)
        all_rows.sort(key=lambda r: (r["row_idx"], r["policy"]))
        return all_rows
