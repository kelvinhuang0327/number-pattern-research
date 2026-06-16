"""
P275B — Unified Prize-Aware Success Matrix (read-only, deterministic build).

PURPOSE
=======
Assemble ONE reproducible unified prize-aware success matrix covering every
confirmed replay-backed lottery, every frozen P267C strategy x lottery cell,
the three primary research windows (SHORT=50 / MID=300 / LONG=750), and each
strategy's intrinsic ticket budget.

This task does NOT run any strategy-combination search and does NOT claim any
future predictive improvement. Every cell is a faithful *re-presentation* of
already-committed, already-validated retrospective evidence into one canonical
matrix schema.

SOURCE-OF-TRUTH (committed artifacts only — the production DB is NEVER opened)
=============================================================================
  1. P273A prize-aware inferential validation
     outputs/research/p273a_prize_aware_inferential_validation_20260615.json
     -> statistical layer: governed exact distinct-ticket random null,
        observed successes, baselines, one-sided exact p-values, Bonferroni
        (m=108) corrected p-values, Wilson + Clopper-Pearson 95% CIs, BH-FDR
        descriptive flags, per-window decisions, stability and group decisions.
  2. P273A primary-window observed counts
     outputs/research/p273a_primary_window_observed_counts_20260615.json
     -> evaluated / eligible / success counts, POWER second-zone exclusions,
        draw ranges, bet-count distributions, governed endpoint definitions.
  3. P273A distinct-ticket identity export
     outputs/research/p273a_distinct_ticket_identity_20260615.json
     -> bet_index values, eligible bet-index counts, distinct ticket counts,
        prediction number counts, ticket-identity availability.
  4. Strategy lifecycle registry (DB-free metadata import)
     lottery_api.models.replay_strategy_registry.get_strategy_lifecycle_metadata
     -> authoritative canonical lifecycle_status + strategy_version
        (ONLINE / RETIRED / REJECTED / OBSERVATION taxonomy).

REUSE (no semantic change, no duplication)
==========================================
  * Wilson / Clopper-Pearson / Bonferroni / BH-FDR helpers are imported from the
    committed P273A inferential-validation module and used verbatim to
    independently RE-DERIVE and CROSS-CHECK the committed statistics. They are
    not re-implemented here.
  * Prize-tier / endpoint semantics are read verbatim from the committed
    artifacts; they are never redefined.

SAFETY
======
  * Read-only. No DB open/query/write. No migration. No registry mutation.
  * No production write, controlled apply, deployment, or activation.
  * POWER rows with a missing predicted second zone are carried as MISSING
    ELIGIBILITY only — never imputed, never counted as losses.
  * Retrospective evidence only. No prediction-success / betting claim.
"""

from __future__ import annotations

import argparse
import builtins
import copy
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Identity / paths                                                            #
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = "p275b_unified_prize_aware_success_matrix_v1"
TASK_ID = "P275B_UNIFIED_PRIZE_AWARE_SUCCESS_MATRIX"

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[1]
ANALYSIS_DIR = _THIS.parent
RESEARCH_DIR = REPO_ROOT / "outputs" / "research"

INF_PATH = RESEARCH_DIR / "p273a_prize_aware_inferential_validation_20260615.json"
OBS_PATH = RESEARCH_DIR / "p273a_primary_window_observed_counts_20260615.json"
IDN_PATH = RESEARCH_DIR / "p273a_distinct_ticket_identity_20260615.json"

OUT_JSON = RESEARCH_DIR / "p275b_unified_prize_aware_success_matrix_20260616.json"
OUT_MD = RESEARCH_DIR / "p275b_unified_prize_aware_success_matrix_20260616.md"

# Committed canonical digests pinned by P273A (integrity gate).
INF_EXPECTED_DIGEST = "5666e67c88e5f3b1233f2d6d5a5f86746c4f7605ae98bda3f2d59ec5aa0b2fb4"
OBS_EXPECTED_DIGEST = "65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f"
IDN_EXPECTED_DIGEST = "ad85e447dfc7db7afd70e9fdde928bb12a2ae367d6c1f23f14b7e3504701ae51"

# Per-artifact digest exclusion sets (empirically pinned to reproduce the
# committed digests exactly).
INF_DIGEST_EXCLUDE = frozenset({"canonical_payload_digest"})
OBS_DIGEST_EXCLUDE = frozenset({
    "canonical_payload_digest", "connection_uri", "generated_at",
    "source_db_path", "transaction_end_at", "transaction_start_at",
})
IDN_DIGEST_EXCLUDE = OBS_DIGEST_EXCLUDE

# This artifact's own digest excludes only the wall-clock + the self hash.
SELF_DIGEST_EXCLUDE = frozenset({"canonical_payload_digest", "generated_at"})

PRIMARY_WINDOWS: Tuple[Tuple[int, str], ...] = ((50, "SHORT"), (300, "MID"), (750, "LONG"))
FAMILY_M = 108  # 36 frozen cells x 3 primary windows; re-verified against P273A.

# Reproducibility cross-check tolerance. Committed P273A statistics are stored
# at 12-digit precision, so an independent re-derivation can differ only by the
# storage rounding (observed CI max diff 5e-13; Bonferroni max diff ~5e-11).
_REPRO_TOL = 1e-9

LIFECYCLE_SENTINEL = "UNREGISTERED_IN_CANONICAL_LIFECYCLE_REGISTRY"
VERSION_SENTINEL = "UNRESOLVED_IN_CANONICAL_LIFECYCLE_REGISTRY"
MONETARY_BUDGET_STATUS = "UNSUPPORTED_NO_AUTHORITATIVE_UNIT_COST_SOURCE"

MAIN_NUMBER_COUNT = {"DAILY_539": 5, "BIG_LOTTO": 6, "POWER_LOTTO": 6}
HAS_SECOND_ZONE = {"DAILY_539": False, "BIG_LOTTO": False, "POWER_LOTTO": True}


class MatrixBuildError(RuntimeError):
    """Raised when an integrity / reproducibility gate fails."""


# --------------------------------------------------------------------------- #
# Hardened DB guard (no production DB may be opened during a build)            #
# --------------------------------------------------------------------------- #

class _DBGuard:
    """Context manager that fails closed if any *.db is opened or sqlite3
    connects while the matrix is being built."""

    def __init__(self) -> None:
        self.hits: List[str] = []
        self._open = builtins.open
        self._connect = sqlite3.connect

    def __enter__(self) -> "_DBGuard":
        guard = self

        def guarded_open(file, *a, **k):  # type: ignore[no-untyped-def]
            try:
                name = os.fspath(file)
            except TypeError:
                name = str(file)
            if isinstance(name, str) and name.endswith(".db"):
                guard.hits.append(f"open:{name}")
                raise MatrixBuildError(f"DB open blocked during build: {name}")
            return guard._open(file, *a, **k)

        def guarded_connect(*a, **k):  # type: ignore[no-untyped-def]
            guard.hits.append(f"sqlite3.connect:{a[:1]}")
            raise MatrixBuildError("sqlite3.connect blocked during build")

        builtins.open = guarded_open  # type: ignore[assignment]
        sqlite3.connect = guarded_connect  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: Any) -> None:
        builtins.open = self._open  # type: ignore[assignment]
        sqlite3.connect = self._connect  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Reuse of committed P273A statistical helpers (imported, never re-implemented)#
# --------------------------------------------------------------------------- #

def load_p273a_module():
    """Import the committed P273A inferential-validation module for verbatim
    reuse of its CI / correction helpers. Verified import-time DB-free."""
    path = ANALYSIS_DIR / "p273a_prize_aware_inferential_validation.py"
    spec = importlib.util.spec_from_file_location("p273a_inferential_validation", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise MatrixBuildError(f"cannot load P273A module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("wilson_interval", "clopper_pearson_interval",
                 "bonferroni_pvalue", "benjamini_hochberg"):
        if not hasattr(module, name):
            raise MatrixBuildError(f"P273A module missing reused helper: {name}")
    if getattr(module, "CORRECTION_FAMILY_M", None) != FAMILY_M:
        raise MatrixBuildError(
            f"P273A CORRECTION_FAMILY_M != {FAMILY_M}; family drift detected")
    return module


# --------------------------------------------------------------------------- #
# Canonical digest (deterministic; excludes named volatile keys recursively)  #
# --------------------------------------------------------------------------- #

def _strip(obj: Any, exclude: frozenset) -> Any:
    if isinstance(obj, dict):
        return {k: _strip(v, exclude) for k, v in obj.items() if k not in exclude}
    if isinstance(obj, list):
        return [_strip(x, exclude) for x in obj]
    return obj


def canonical_digest(obj: Any, exclude: frozenset) -> str:
    payload = _strip(copy.deepcopy(obj), exclude)
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Input loading + integrity verification                                      #
# --------------------------------------------------------------------------- #

def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_verify_inputs() -> Dict[str, Any]:
    """Load the three committed P273A artifacts and verify each embedded
    canonical digest reproduces and matches the pinned committed value."""
    specs = [
        ("inferential_validation", INF_PATH, INF_DIGEST_EXCLUDE, INF_EXPECTED_DIGEST),
        ("observed_counts", OBS_PATH, OBS_DIGEST_EXCLUDE, OBS_EXPECTED_DIGEST),
        ("distinct_ticket_identity", IDN_PATH, IDN_DIGEST_EXCLUDE, IDN_EXPECTED_DIGEST),
    ]
    out: Dict[str, Any] = {"_provenance": {}}
    for key, path, exclude, expected in specs:
        if not path.exists():
            raise MatrixBuildError(f"required input missing: {path}")
        doc = _read_json(path)
        embedded = doc.get("canonical_payload_digest")
        recomputed = canonical_digest(doc, exclude)
        if embedded != recomputed:
            raise MatrixBuildError(
                f"{path.name}: embedded digest {embedded} != recomputed {recomputed}")
        if recomputed != expected:
            raise MatrixBuildError(
                f"{path.name}: digest {recomputed} != pinned committed {expected}")
        out[key] = doc
        out["_provenance"][key] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "raw_sha256": _raw_sha256(path),
            "canonical_payload_digest": recomputed,
            "digest_verified": True,
        }
    return out


def load_lifecycle_registry() -> Dict[str, Any]:
    """Load authoritative canonical lifecycle metadata from the registry module
    via a DB-free import (the registry import is verified side-effect free)."""
    sys.path.insert(0, str(REPO_ROOT))
    import lottery_api.models.replay_strategy_registry as registry  # noqa: WPS433
    records = registry.list_strategy_lifecycle_metadata()
    by_id: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        by_id.setdefault(rec["strategy_id"], []).append(rec)
    src = REPO_ROOT / "lottery_api" / "models" / "replay_strategy_registry.py"
    return {
        "by_id": by_id,
        "source_path": str(src.relative_to(REPO_ROOT)),
        "source_sha256": _raw_sha256(src),
        "record_count": len(records),
    }


def resolve_lifecycle(lottery: str, strategy_id: str,
                      registry: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve (lifecycle_status, strategy_version) for a lottery x strategy
    cell from the canonical registry. A lottery-scoped match is required;
    otherwise an explicit non-fabricated sentinel is returned."""
    candidates = registry["by_id"].get(strategy_id, [])
    scoped = [c for c in candidates if lottery in (c.get("supported_lottery_types") or [])]
    if len(scoped) == 1:
        rec = scoped[0]
        return {
            "lifecycle_status": rec.get("lifecycle_status"),
            "strategy_version": rec.get("strategy_version"),
            "lifecycle_source": "canonical_replay_strategy_registry",
            "resolved": True,
        }
    return {
        "lifecycle_status": LIFECYCLE_SENTINEL,
        "strategy_version": VERSION_SENTINEL,
        "lifecycle_source": "unresolved",
        "resolved": False,
    }


# --------------------------------------------------------------------------- #
# Small structural helpers                                                    #
# --------------------------------------------------------------------------- #

def _index_by_cell(items: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for it in items:
        out[(it["lottery_type"], it["strategy_id"])] = it
    return out


def _window_by_n(windows: List[Dict[str, Any]], n: int) -> Optional[Dict[str, Any]]:
    for w in windows:
        if w.get("window") == n:
            return w
    return None


def _distribution_summary(dist: Dict[str, int]) -> Dict[str, Any]:
    """Summarise a {value: count} distribution deterministically."""
    if not dist:
        return {"distribution": {}, "constant": False, "representative": None,
                "min": None, "max": None, "per_draw_total": 0}
    keys = sorted(int(k) for k in dist)
    constant = len(keys) == 1
    total_draws = sum(dist.values())
    per_draw_total = sum(int(k) * v for k, v in dist.items())
    return {
        "distribution": {str(k): dist[str(k)] for k in keys},
        "constant": constant,
        "representative": keys[0] if constant else None,
        "min": keys[0],
        "max": keys[-1],
        "draws_counted": total_draws,
        "per_draw_total": per_draw_total,
    }


def _bet_index_values_in_window(idn_cell: Dict[str, Any], earliest: Optional[str],
                                latest: Optional[str]) -> List[int]:
    """Union of distinct bet_index values across supported draws inside the
    inclusive [earliest, latest] target-draw range (CAST-int ordering)."""
    if earliest is None or latest is None:
        return []
    lo, hi = int(earliest), int(latest)
    values: set = set()
    for draw in idn_cell.get("supported_draws", []):
        d = int(draw["target_draw"])
        if lo <= d <= hi:
            for group in draw.get("canonical_ticket_groups", []):
                for bi in group.get("bet_index_values", []):
                    values.add(int(bi))
    return sorted(values)


# --------------------------------------------------------------------------- #
# Row construction                                                            #
# --------------------------------------------------------------------------- #

def build_row(lottery: str, strategy_id: str, window_n: int, window_label: str,
              inf_group: Dict[str, Any], obs_cell: Dict[str, Any],
              idn_cell: Dict[str, Any], endpoint_def: Dict[str, Any],
              lifecycle: Dict[str, Any], p273a, *,
              generated_at: str, source_commit: str) -> Dict[str, Any]:
    inf_w = _window_by_n(inf_group["windows"], window_n)
    obs_w = _window_by_n(obs_cell["windows"], window_n)
    idn_w = _window_by_n(idn_cell["windows"], window_n)
    if inf_w is None or obs_w is None or idn_w is None:
        raise MatrixBuildError(
            f"missing window {window_n} for {lottery}/{strategy_id}")

    evaluable = bool(inf_w.get("evaluable"))
    support = int(obs_w["support_draws"])
    successes = int(obs_w["observed_successes"])
    requested = int(obs_w.get("requested_window", window_n))

    # ----- ticket / bet structure (clearly distinguished concepts) ---------- #
    bet_count_dist = _distribution_summary(idn_w.get("eligible_bet_index_count_distribution", {}))
    ticket_count_dist = _distribution_summary(idn_w.get("distinct_ticket_count_distribution", {}))
    bet_index_values = _bet_index_values_in_window(
        idn_cell, obs_w.get("earliest_target_draw"), obs_w.get("latest_target_draw"))

    ticket_budget = ticket_count_dist["representative"]  # per-draw distinct tickets

    # ----- POWER second-zone missingness (never a loss, never imputed) ------ #
    excluded_second_zone_rows = int(obs_w.get("excluded_missing_special_rows", 0))
    missing_draws = {
        "second_zone_excluded_bet_rows": excluded_second_zone_rows,
        "exclusion_by_reason": obs_w.get("exclusion_by_reason", {}),
        "draws_short_of_requested_window": max(0, requested - support),
        "treated_as_loss": False,
        "imputed": False,
    }

    # ----- statistical layer (carried verbatim + independently re-derived) -- #
    if evaluable:
        committed_wilson = inf_w["wilson_ci_95"]
        committed_cp = inf_w["clopper_pearson_ci_95"]
        rederived_wilson = list(p273a.wilson_interval(successes, support))
        rederived_cp = list(p273a.clopper_pearson_interval(successes, support))
        ci_match = (_close(committed_wilson, rederived_wilson)
                    and _close(committed_cp, rederived_cp))
        raw_p = inf_w["raw_p_value_one_sided_upper"]
        committed_bonf = inf_w["bonferroni_p_value"]
        rederived_bonf = p273a.bonferroni_pvalue(raw_p, FAMILY_M)
        # Committed values are stored at 12-digit precision; the only admissible
        # gap is that storage rounding (CI <= 5e-13; Bonferroni <= m * 5e-13).
        bonf_match = abs(committed_bonf - rederived_bonf) <= _REPRO_TOL
        confidence_interval = {
            "method": "two_sided_95",
            "wilson_95": committed_wilson,
            "clopper_pearson_95": committed_cp,
            "independently_rederived": {"wilson_95": rederived_wilson,
                                        "clopper_pearson_95": rederived_cp},
            "rederivation_matches_committed": ci_match,
        }
        success_rate = inf_w["observed_rate"]
        baseline_rate = inf_w["mean_baseline_rate"]
        absolute_lift = inf_w["absolute_excess"]
        relative_lift = inf_w["relative_lift"]
        p_value = raw_p
        corrected_p = committed_bonf
        reproduced = bool(ci_match and bonf_match)
    else:
        confidence_interval = None
        success_rate = None
        baseline_rate = None
        absolute_lift = None
        relative_lift = None
        p_value = None
        corrected_p = None
        reproduced = True  # nothing to re-derive; carried as INSUFFICIENT_SUPPORT

    row = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "lottery_type": lottery,
        "strategy_id": strategy_id,
        "strategy_version": lifecycle["strategy_version"],
        "lifecycle_status": lifecycle["lifecycle_status"],
        "lifecycle_source": lifecycle["lifecycle_source"],
        "evaluation_mode": "RETROSPECTIVE",
        "window_type": window_label,
        "window_draw_count": window_n,
        "evaluation_start_draw": obs_w.get("earliest_target_draw"),
        "evaluation_end_draw": obs_w.get("latest_target_draw"),
        "ticket_budget": ticket_budget,
        "monetary_budget": None,
        "monetary_budget_status": MONETARY_BUDGET_STATUS,
        "bet_indices": {
            "distinct_bet_index_values": bet_index_values,
            "per_draw_eligible_bet_index_count": bet_count_dist,
            "derived_bet_count_per_draw": bet_count_dist["representative"],
        },
        "ticket_count": {
            "per_draw_distinct_ticket_count": ticket_count_dist["representative"],
            "per_draw_distribution": ticket_count_dist["distribution"],
            "window_total_distinct_tickets": ticket_count_dist["per_draw_total"],
        },
        "prediction_number_count": {
            "main_number_count": MAIN_NUMBER_COUNT[lottery],
            "has_second_zone": HAS_SECOND_ZONE[lottery],
            "second_zone_number_count": 1 if HAS_SECOND_ZONE[lottery] else 0,
        },
        "outcome_endpoint": {
            "endpoint_id": endpoint_def["endpoint_id"],
            "condition": endpoint_def["committed_condition_sql"],
            "scored_by": endpoint_def["scored_by"],
        },
        "prize_tier": endpoint_def["min_qualifying_tier"],
        "evaluated_draws": support,
        "eligible_draws": support,
        "missing_draws": missing_draws,
        "success_draws": successes,
        "success_rate": success_rate,
        "confidence_interval": confidence_interval,
        "baseline_type": "GOVERNED_EXACT_DISTINCT_TICKET_RANDOM_NULL",
        "baseline_success_rate": baseline_rate,
        "absolute_lift": absolute_lift,
        "relative_lift": relative_lift,
        "p_value": p_value,
        "corrected_p_value": corrected_p,
        "correction_family": {
            "definition": "all pre-registered (strategy x lottery x primary window) hypotheses",
            "family_m": FAMILY_M,
            "family_alpha": 0.05,
            "per_test_alpha": 0.05 / FAMILY_M,
            "no_post_outcome_family_shrinkage": True,
        },
        "correction_method": "BONFERRONI",
        "bh_fdr_descriptive_reject": inf_w.get("bh_fdr_descriptive_reject"),
        "ticket_identity_available": True,
        "reproducibility_status": "REPRODUCED" if reproduced else "DIVERGENT",
        "evaluable": evaluable,
        "support_status": inf_w.get("support_status"),
        "statistical_status": inf_w.get("statistical_status"),
        "evidence_status": inf_w.get("window_decision"),
        "promotion_eligible_window": window_label != "SHORT",
        "limitations": _row_limitations(lottery, window_label, evaluable,
                                        excluded_second_zone_rows, lifecycle),
    }
    return row


def _close(a: List[float], b: List[float], tol: float = _REPRO_TOL) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def _row_limitations(lottery: str, window_label: str, evaluable: bool,
                     excluded_second_zone_rows: int,
                     lifecycle: Dict[str, Any]) -> List[str]:
    out = [
        "Retrospective evidence only; not confirmatory and not a future-only result.",
        "No claim of improved future prediction success.",
        "Monetary budget unsupported: no authoritative unit-cost source confirmed.",
        "Baseline is the governed exact distinct-ticket random null; no diversified-random baseline exists.",
        "Prize-tier semantics carry source_verification_status=MANUAL_VERIFICATION_REQUIRED (P271B/P271C).",
    ]
    if window_label == "SHORT":
        out.append("50-draw (SHORT) results are integrity guardrail only and cannot independently support promotion.")
    if lottery == "POWER_LOTTO" and excluded_second_zone_rows > 0:
        out.append("POWER second-zone-missing bets excluded as missing eligibility; never imputed, never counted as losses.")
    if not evaluable:
        out.append("Window not evaluable (insufficient support after eligibility filtering); no inference computed.")
    if not lifecycle["resolved"]:
        out.append("Lifecycle/version not resolvable in the canonical registry for this lottery-scoped cell; explicit sentinel used (not fabricated).")
    return out


# --------------------------------------------------------------------------- #
# Matrix assembly                                                             #
# --------------------------------------------------------------------------- #

def build_matrix(inputs: Dict[str, Any], registry: Dict[str, Any], p273a, *,
                 generated_at: str, source_commit: str) -> Dict[str, Any]:
    inf = inputs["inferential_validation"]
    obs = inputs["observed_counts"]
    idn = inputs["distinct_ticket_identity"]

    inf_by_cell = _index_by_cell(inf["inference"]["groups"])
    obs_by_cell = _index_by_cell(obs["cells"])
    idn_by_cell = _index_by_cell(idn["cells"])
    endpoint_defs = obs["endpoint_definitions"]

    # Frozen cell set, deterministically ordered.
    cells = sorted(obs_by_cell.keys())
    if len(cells) != 36:
        raise MatrixBuildError(f"expected 36 frozen cells, found {len(cells)}")

    rows: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    go_candidates = {(g["lottery_type"], g["strategy_id"])
                     for g in inf["summary"]["go_candidate_research_only_groups"]}

    for lottery, strategy_id in cells:
        key = (lottery, strategy_id)
        if key not in inf_by_cell or key not in idn_by_cell:
            raise MatrixBuildError(f"cell {key} missing from a source artifact")
        inf_group = inf_by_cell[key]
        obs_cell = obs_by_cell[key]
        idn_cell = idn_by_cell[key]
        endpoint_def = endpoint_defs[lottery]
        lifecycle = resolve_lifecycle(lottery, strategy_id, registry)

        for window_n, window_label in PRIMARY_WINDOWS:
            rows.append(build_row(
                lottery, strategy_id, window_n, window_label,
                inf_group, obs_cell, idn_cell, endpoint_def, lifecycle, p273a,
                generated_at=generated_at, source_commit=source_commit))

        groups.append({
            "lottery_type": lottery,
            "strategy_id": strategy_id,
            "strategy_version": lifecycle["strategy_version"],
            "lifecycle_status": lifecycle["lifecycle_status"],
            "lifecycle_source": lifecycle["lifecycle_source"],
            "stability_status": inf_group["stability"]["status"],
            "stability_fail_reasons": inf_group["stability"]["criteria"],
            "overall_group_decision": inf_group["overall_group_decision"],
            "is_go_candidate_research_only": key in go_candidates,
        })

    summary = _build_summary(rows, groups, inf)
    return {"rows": rows, "groups": groups, "summary": summary}


def _build_summary(rows: List[Dict[str, Any]], groups: List[Dict[str, Any]],
                   inf: Dict[str, Any]) -> Dict[str, Any]:
    from collections import Counter

    evidence_counts = Counter(r["evidence_status"] for r in rows)
    group_counts = Counter(g["overall_group_decision"] for g in groups)
    stability_counts = Counter(g["stability_status"] for g in groups)
    lifecycle_counts = Counter(g["lifecycle_status"] for g in groups)
    by_lottery = Counter(g["lottery_type"] for g in groups)

    # Cross-check against the committed P273A summary (strong reproducibility).
    committed = inf["summary"]["window_decision_counts"]
    recomputed = dict(evidence_counts)
    matches_committed = recomputed == committed

    correction_surviving = [
        {"lottery_type": r["lottery_type"], "strategy_id": r["strategy_id"],
         "window_type": r["window_type"], "corrected_p_value": r["corrected_p_value"]}
        for r in rows
        if r["evidence_status"] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    ]
    reproduced_rows = sum(1 for r in rows if r["reproducibility_status"] == "REPRODUCED")

    return {
        "total_rows": len(rows),
        "supported_lotteries": sorted(by_lottery),
        "cells_by_lottery": dict(sorted(by_lottery.items())),
        "frozen_cells": len(groups),
        "correction_family_m": FAMILY_M,
        "evaluable_windows": sum(1 for r in rows if r["evaluable"]),
        "evidence_status_counts": dict(sorted(evidence_counts.items())),
        "evidence_status_matches_committed_p273a": matches_committed,
        "group_decision_counts": dict(sorted(group_counts.items())),
        "stability_counts": dict(sorted(stability_counts.items())),
        "lifecycle_status_counts": dict(sorted(lifecycle_counts.items())),
        "correction_surviving_edge_windows": correction_surviving,
        "go_candidate_research_only_groups": [
            {"lottery_type": g["lottery_type"], "strategy_id": g["strategy_id"]}
            for g in groups if g["is_go_candidate_research_only"]
        ],
        "rows_reproduced": reproduced_rows,
        "all_rows_reproduced": reproduced_rows == len(rows),
    }


# --------------------------------------------------------------------------- #
# Artifact assembly                                                           #
# --------------------------------------------------------------------------- #

def _git_head(default: str = "UNKNOWN") -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True)
        return out.stdout.strip() or default
    except Exception:  # pragma: no cover - environment dependent
        return default


def build_artifact(*, generated_at: Optional[str] = None,
                   source_commit: Optional[str] = None) -> Dict[str, Any]:
    generated_at = generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat()
    source_commit = source_commit or _git_head()

    guard = _DBGuard()
    with guard:
        inputs = load_and_verify_inputs()
        registry = load_lifecycle_registry()
        p273a = load_p273a_module()
        matrix = build_matrix(inputs, registry, p273a,
                              generated_at=generated_at, source_commit=source_commit)

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "generated_at": generated_at,
        "source_commit": source_commit,
        "retrospective_research_only": True,
        "prediction_success_claim": False,
        "performs_strategy_combination_search": False,
        "production_db_opened": False,
        "db_guard_hits": guard.hits,
        "scope": {
            "supported_lotteries": ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"],
            "primary_windows": {"SHORT": 50, "MID": 300, "LONG": 750},
            "all_history_windows": "REFERENCE_ONLY_NOT_INCLUDED",
            "frozen_strategy_cells": 36,
            "correction_family_m": FAMILY_M,
        },
        "endpoint_definitions": inputs["observed_counts"]["endpoint_definitions"],
        "baseline_contract": {
            "baseline_type": "GOVERNED_EXACT_DISTINCT_TICKET_RANDOM_NULL",
            "per_lottery_universes": inputs["inferential_validation"]["analytic_random_baselines"],
            "diversified_random_baseline": "ABSENT_NOT_IMPLEMENTED",
            "source": "P273A baseline_contract (exact without-replacement distinct-ticket null)",
        },
        "statistical_contract": {
            "results_are_retrospective": True,
            "confirmatory_correction": "BONFERRONI",
            "bonferroni_family_m": FAMILY_M,
            "bh_fdr": "DESCRIPTIVE_SECONDARY_ONLY",
            "confidence_intervals": ["wilson_95", "clopper_pearson_95"],
            "short_50_cannot_promote": True,
            "missing_observations_excluded_not_failed": True,
            "future_success_claim": False,
        },
        "lifecycle_provenance": {
            "primary_source": "lottery_api.models.replay_strategy_registry.list_strategy_lifecycle_metadata",
            "source_path": registry["source_path"],
            "source_sha256": registry["source_sha256"],
            "db_free_import_verified": True,
            "unresolved_cells_use_sentinel": LIFECYCLE_SENTINEL,
        },
        "input_provenance": inputs["_provenance"],
        "reused_helpers": {
            "module": "analysis/p273a_prize_aware_inferential_validation.py",
            "functions": ["wilson_interval", "clopper_pearson_interval",
                          "bonferroni_pvalue", "benjamini_hochberg"],
            "semantic_change": False,
        },
        "matrix_summary": matrix["summary"],
        "group_decisions": matrix["groups"],
        "matrix_rows": matrix["rows"],
        "limitations": _artifact_limitations(matrix),
        "final_classification": "P275B_UNIFIED_PRIZE_AWARE_SUCCESS_MATRIX_COMPLETE",
    }
    artifact["canonical_payload_digest"] = canonical_digest(artifact, SELF_DIGEST_EXCLUDE)
    return artifact


def _artifact_limitations(matrix: Dict[str, Any]) -> List[str]:
    out = [
        "This matrix unifies already-committed retrospective P273A evidence; it computes no new outcome data.",
        "All results are retrospective; none is confirmatory, future-only, or a prediction-success claim.",
        "No cross-strategy combination search was performed; cells are independent re-presentations.",
        "50-draw (SHORT) windows are integrity guardrails and cannot independently support promotion.",
        "POWER second-zone-missing rows are excluded as missing eligibility; never imputed, never counted as losses.",
        "Lifecycle states are preserved as-is (REJECTED / RETIRED / OBSERVATION / ONLINE); none silently removed.",
        "Monetary budget is unsupported (no authoritative unit-cost source); it remains null.",
        "Prize-tier semantics retain source_verification_status=MANUAL_VERIFICATION_REQUIRED.",
        "No diversified-random baseline exists; only the governed exact distinct-ticket random null is used.",
        "No betting recommendation is made and no future predictive improvement is claimed.",
    ]
    if not matrix["summary"]["evidence_status_matches_committed_p273a"]:
        out.append("WARNING: recomputed evidence-status counts diverge from committed P273A summary.")
    return out


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #

def _fmt(value: Optional[float], digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def render_markdown(artifact: Dict[str, Any]) -> str:
    s = artifact["matrix_summary"]
    lines: List[str] = []
    a = lines.append
    a(f"# P275B — Unified Prize-Aware Success Matrix")
    a("")
    a(f"- **Task:** `{artifact['task_id']}`")
    a(f"- **Schema:** `{artifact['schema_version']}`")
    a(f"- **Source commit:** `{artifact['source_commit']}`")
    a(f"- **Canonical digest:** `{artifact['canonical_payload_digest']}`")
    a(f"- **Retrospective only:** {artifact['retrospective_research_only']} · "
      f"**Prediction-success claim:** {artifact['prediction_success_claim']} · "
      f"**Production DB opened:** {artifact['production_db_opened']}")
    a("")
    a("> Retrospective re-presentation of committed P273A evidence. No betting "
      "recommendation. No future-success claim. No strategy-combination search.")
    a("")

    a("## Capability & Missingness Overview")
    a("")
    a(f"- Supported lotteries: {', '.join(s['supported_lotteries'])}")
    a(f"- Frozen strategy cells: {s['frozen_cells']} · matrix rows: {s['total_rows']} "
      f"(= cells × 3 primary windows)")
    a(f"- Primary windows: SHORT=50 / MID=300 / LONG=750 (1500 & all-history are reference-only, excluded)")
    a(f"- Evaluable windows: {s['evaluable_windows']} / {s['total_rows']}")
    a(f"- Bonferroni confirmatory family m = {s['correction_family_m']}")
    a(f"- Rows reproduced (CI + Bonferroni re-derived vs committed): "
      f"{s['rows_reproduced']}/{s['total_rows']} · "
      f"evidence-status counts match committed P273A: "
      f"{s['evidence_status_matches_committed_p273a']}")
    a("")
    a("### Lifecycle status distribution (states kept visible)")
    a("")
    a("| Lifecycle status | Cells |")
    a("|---|---|")
    for k, v in s["lifecycle_status_counts"].items():
        a(f"| {k} | {v} |")
    a("")
    a("### Evidence-status distribution (window decisions)")
    a("")
    a("| Evidence status | Windows |")
    a("|---|---|")
    for k, v in s["evidence_status_counts"].items():
        a(f"| {k} | {v} |")
    a("")

    a("## Per-Lottery Findings")
    a("")
    for lottery in s["supported_lotteries"]:
        ep = artifact["endpoint_definitions"][lottery]
        rows_l = [r for r in artifact["matrix_rows"] if r["lottery_type"] == lottery]
        cells_l = sorted({r["strategy_id"] for r in rows_l})
        eligible = sum(1 for r in rows_l if r["evaluable"])
        a(f"### {lottery}")
        a("")
        a(f"- Endpoint `{ep['endpoint_id']}`: `{ep['committed_condition_sql']}` "
          f"(min tier: {ep['min_qualifying_tier']})")
        a(f"- Cells: {len(cells_l)} · rows: {len(rows_l)} · evaluable windows: {eligible}/{len(rows_l)}")
        if lottery == "POWER_LOTTO":
            excl = sum(r["missing_draws"]["second_zone_excluded_bet_rows"] for r in rows_l)
            fully = sorted({r["strategy_id"] for r in rows_l
                            if not r["evaluable"] and r["missing_draws"]["second_zone_excluded_bet_rows"] > 0})
            a(f"- Second-zone excluded bet-rows (missing eligibility, never losses): {excl}")
            if fully:
                a(f"- Cells with fully-excluded windows (no eligible second-zone bets): {', '.join(fully)}")
        a("")

    a("## Per-Window Matrix Summary (correction-surviving edges)")
    a("")
    if s["correction_surviving_edge_windows"]:
        a("| Lottery | Strategy | Window | Corrected p (Bonferroni m=108) |")
        a("|---|---|---|---|")
        for e in s["correction_surviving_edge_windows"]:
            a(f"| {e['lottery_type']} | {e['strategy_id']} | {e['window_type']} | "
              f"{_fmt(e['corrected_p_value'], 6)} |")
    else:
        a("_No window survived Bonferroni correction._")
    a("")
    a("### Research-only GO candidate groups (NOT deployment, NOT betting advice)")
    a("")
    if s["go_candidate_research_only_groups"]:
        for g in s["go_candidate_research_only_groups"]:
            a(f"- {g['lottery_type']} / `{g['strategy_id']}`")
    else:
        a("_None._")
    a("")

    a("## Full Matrix (per strategy × window)")
    a("")
    a("| Lottery | Strategy | Life | Win | Budget | Elig | Succ | Rate | Base | "
      "AbsLift | p | corr-p | Evidence |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in artifact["matrix_rows"]:
        a("| {lt} | {sid} | {life} | {win} | {bud} | {elig} | {succ} | {rate} | "
          "{base} | {lift} | {p} | {cp} | {ev} |".format(
              lt=r["lottery_type"], sid=r["strategy_id"],
              life=r["lifecycle_status"], win=r["window_type"],
              bud=r["ticket_budget"], elig=r["eligible_draws"],
              succ=r["success_draws"], rate=_fmt(r["success_rate"]),
              base=_fmt(r["baseline_success_rate"]),
              lift=_fmt(r["absolute_lift"]),
              p=_fmt(r["p_value"], 4), cp=_fmt(r["corrected_p_value"], 4),
              ev=(r["evidence_status"] or "").replace("PRIZE_AWARE_", "")))
    a("")

    a("## Statistical Cautions")
    a("")
    a("- All cells are **retrospective**; none is confirmatory or future-only.")
    a("- Confirmatory correction is **Bonferroni (m=108)**; BH-FDR is descriptive only.")
    a("- **50-draw (SHORT)** windows cannot independently support promotion.")
    a("- Missing observations are **excluded**, never converted to failures.")
    a("- No strategy is claimed to improve future prediction success.")
    a("")
    a("## Limitations")
    a("")
    for lim in artifact["limitations"]:
        a(f"- {lim}")
    a("")
    a(f"_Final classification: `{artifact['final_classification']}`._")
    a("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #

def write_outputs(artifact: Dict[str, Any]) -> None:
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(artifact))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the P275B unified prize-aware success matrix.")
    parser.add_argument("--check", action="store_true",
                        help="Build in-memory and print summary without writing artifacts.")
    parser.add_argument("--generated-at", default=None,
                        help="Pin generated_at (UTC ISO) for deterministic regeneration.")
    args = parser.parse_args(argv)

    artifact = build_artifact(generated_at=args.generated_at)
    if args.check:
        print(json.dumps(artifact["matrix_summary"], ensure_ascii=False, indent=2))
        print("canonical_payload_digest:", artifact["canonical_payload_digest"])
        return 0
    write_outputs(artifact)
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"wrote {OUT_MD.relative_to(REPO_ROOT)}")
    print("canonical_payload_digest:", artifact["canonical_payload_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
