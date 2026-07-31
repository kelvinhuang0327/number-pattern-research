#!/usr/bin/env python3
"""
P40 — 2024 Holdout WFV Validation for sp_fip_delta Strong-edge T=0.50
=======================================================================
Governance:
  diagnostic_only          = True
  promotion_freeze         = True
  T_LOCKED                 = 0.50
  live_api_calls           = 0
  no_champion_modification = True

P37 Baseline (2025 season, locked):
  AUC_WFV           = 0.5665
  BrierSk           = +0.0123
  favored_win_rate  = 60.8%
  monthly_stability = 100%
  strong_edge_count = 531

Classification thresholds:
  HOLDOUT_CONFIRMED        : AUC >= 0.54
  HOLDOUT_WEAK_REPLICATION : 0.50 <= AUC < 0.54
  HOLDOUT_FAILED           : AUC < 0.50
  INCONCLUSIVE             : n < 50
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

# ── Governance constants ───────────────────────────────────────────────────────
_DIAGNOSTIC_ONLY          = True
_PROMOTION_FREEZE         = True
_T_LOCKED                 = 0.50
_LIVE_API_CALLS           = 0
_NO_CHAMPION_MODIFICATION = True

assert _DIAGNOSTIC_ONLY,          "STOP: diagnostic_only must be True for P40"
assert _PROMOTION_FREEZE,         "STOP: promotion_freeze must be True for P40"
assert _T_LOCKED == 0.50,         "STOP: T must be 0.50 (P37 locked, no re-optimization)"
assert _LIVE_API_CALLS == 0,      "STOP: live_api_calls must be 0 for P40"
assert _NO_CHAMPION_MODIFICATION, "STOP: no_champion_modification must be True"

# ── P37 Baseline ───────────────────────────────────────────────────────────────
P37_AUC          = 0.5665
P37_BRIER_SKILL  = 0.0123
P37_FAVORED_WR   = 0.608
P37_STABILITY    = 1.00   # 100% months above 0.50
P37_SE_COUNT     = 531
P37_SEASON       = "2025"

# ── Classification thresholds ─────────────────────────────────────────────────
_THR_CONFIRMED = 0.54
_THR_FAILED    = 0.50
_MIN_N_VIABLE  = 50

# ── Paths ──────────────────────────────────────────────────────────────────────
_REPO        = Path(__file__).parent.parent
_FEATURES    = _REPO / "data" / "mlb_2025" / "derived" / "mlb_2024_sp_fip_delta_features.jsonl"
_SUMMARY_OUT = _REPO / "data" / "mlb_2025" / "derived" / "p40_2024_holdout_wfv_summary.json"

# ── Probability model ─────────────────────────────────────────────────────────
# Use sigmoid(sp_fip_delta * k) as soft probability for Brier/log-loss.
# k=0.8 maps T=0.50 → p≈0.60, T=1.0 → p≈0.69 (reasonable spread).
_SIGMOID_K = 0.8


# ── Math helpers ───────────────────────────────────────────────────────────────
def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-_SIGMOID_K * x))


def _auc_mannwhitney(y_true: list[int], y_score: list[float]) -> float:
    """AUROC via Mann-Whitney U statistic (no external dependencies)."""
    n1 = sum(y_true)
    n0 = len(y_true) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    pairs = sorted(zip(y_score, y_true), reverse=True)
    rank_sum = 0
    cum_pos = 0
    for _, label in pairs:
        if label == 0:
            rank_sum += cum_pos
        else:
            cum_pos += 1
    return rank_sum / (n1 * n0)


def _brier(y_prob: list[float], y_true: list[int]) -> float:
    n = len(y_true)
    return sum((p - t) ** 2 for p, t in zip(y_prob, y_true)) / n


def _brier_skill(bs: float, base_rate: float) -> float:
    bs_ref = base_rate * (1.0 - base_rate)
    if bs_ref < 1e-9:
        return float("nan")
    return 1.0 - (bs / bs_ref)


def _log_loss(y_prob: list[float], y_true: list[int], eps: float = 1e-9) -> float:
    n = len(y_true)
    total = 0.0
    for p, t in zip(y_prob, y_true):
        p = max(eps, min(1.0 - eps, p))
        total += t * math.log(p) + (1 - t) * math.log(1.0 - p)
    return -total / n


def _ece(y_prob: list[float], y_true: list[int], n_bins: int = 5) -> float:
    """Expected Calibration Error across equal-width probability bins."""
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, t in zip(y_prob, y_true):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, t))
    ece = 0.0
    n = len(y_true)
    for b in bins:
        if not b:
            continue
        frac     = len(b) / n
        mean_p   = sum(x[0] for x in b) / len(b)
        mean_acc = sum(x[1] for x in b) / len(b)
        ece     += frac * abs(mean_acc - mean_p)
    return ece


# ── Data loading ───────────────────────────────────────────────────────────────
def load_features() -> list[dict]:
    if not _FEATURES.exists():
        print(f"ERROR: Feature file not found: {_FEATURES}", file=sys.stderr)
        sys.exit(1)
    records: list[dict] = []
    with _FEATURES.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    print(f"[P40] Loaded {len(records):,} records from {_FEATURES.name}")
    return records


# ── Filtering ──────────────────────────────────────────────────────────────────
def apply_filters(records: list[dict]) -> dict[str, list[dict]]:
    """Apply P37-compatible quality + PIT-safe + strong-edge filters."""
    quality = [
        r for r in records
        if r.get("sp_context_source") != "league_average_fallback"
        and r.get("pit_safe") is True
        and r.get("actual_home_win") in (0, 1)
        and r.get("sp_fip_delta") is not None
    ]
    strong_edge = [
        r for r in quality
        if abs(r["sp_fip_delta"]) >= _T_LOCKED
    ]
    return {"total": records, "quality": quality, "strong_edge": strong_edge}


# ── Metric computation ─────────────────────────────────────────────────────────
def compute_metrics(records: list[dict]) -> dict:
    if not records:
        return {"n": 0, "error": "no_records"}
    if len(records) < _MIN_N_VIABLE:
        return {"n": len(records), "error": "insufficient_data"}

    y_true  = [r["actual_home_win"] for r in records]
    y_score = [r["sp_fip_delta"]     for r in records]   # continuous score for AUC
    y_prob  = [_sigmoid(s)            for s in y_score]   # soft probability

    n         = len(y_true)
    base_rate = sum(y_true) / n

    auc    = _auc_mannwhitney(y_true, y_score)
    bs     = _brier(y_prob, y_true)
    bsk    = _brier_skill(bs, base_rate)
    ll     = _log_loss(y_prob, y_true)
    ece    = _ece(y_prob, y_true)

    # Favored win rate: directional accuracy (home if delta>0, away if delta<0)
    correct = sum(
        1 for r in records
        if r["predicted_home_win"] == r["actual_home_win"]
    )
    favored_wr = correct / n

    return {
        "n":                 n,
        "base_rate":         round(base_rate, 4),
        "auc":               round(auc, 4),
        "brier_score":       round(bs, 4),
        "brier_skill":       round(bsk, 4),
        "log_loss":          round(ll, 4),
        "ece":               round(ece, 4),
        "favored_win_rate":  round(favored_wr, 4),
        "correct":           correct,
    }


# ── Temporal stability ─────────────────────────────────────────────────────────
def temporal_stability(records: list[dict]) -> dict:
    monthly: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        ym = r["game_date"][:7]   # YYYY-MM
        monthly[ym].append(r)

    monthly_metrics: dict[str, dict] = {}
    for ym in sorted(monthly.keys()):
        recs = monthly[ym]
        m    = compute_metrics(recs)
        monthly_metrics[ym] = {
            "n":          len(recs),
            "auc":        m.get("auc"),
            "favored_wr": m.get("favored_win_rate"),
            "note":       m.get("error"),
        }

    # Early (March-May), Mid (June-August), Late (September+)
    def period(ym: str) -> str:
        mo = int(ym[5:7])
        if mo <= 5:
            return "early"
        elif mo <= 8:
            return "mid"
        return "late"

    period_buckets: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        period_buckets[period(r["game_date"][:7])].append(r)

    period_metrics: dict[str, dict] = {}
    for p in ("early", "mid", "late"):
        recs = period_buckets.get(p, [])
        m    = compute_metrics(recs)
        period_metrics[p] = {
            "n":          len(recs),
            "auc":        m.get("auc"),
            "favored_wr": m.get("favored_win_rate"),
            "note":       m.get("error"),
        }

    monthly_aucs = [
        v["auc"] for v in monthly_metrics.values()
        if v["auc"] is not None and not math.isnan(v["auc"])
    ]
    stable_months = sum(1 for a in monthly_aucs if a >= _THR_FAILED)
    stability_rate = stable_months / len(monthly_aucs) if monthly_aucs else 0.0

    return {
        "monthly":                monthly_metrics,
        "period":                 period_metrics,
        "monthly_auc_min":        round(min(monthly_aucs), 4) if monthly_aucs else None,
        "monthly_auc_max":        round(max(monthly_aucs), 4) if monthly_aucs else None,
        "monthly_auc_mean":       round(sum(monthly_aucs) / len(monthly_aucs), 4) if monthly_aucs else None,
        "months_above_random":    stable_months,
        "total_months_with_data": len(monthly_aucs),
        "monthly_stability_rate": round(stability_rate, 4),
    }


# ── Classification ─────────────────────────────────────────────────────────────
def classify(auc: float, n: int) -> str:
    if n < _MIN_N_VIABLE:
        return "INCONCLUSIVE"
    if math.isnan(auc):
        return "INCONCLUSIVE"
    if auc >= _THR_CONFIRMED:
        return "HOLDOUT_CONFIRMED"
    elif auc >= _THR_FAILED:
        return "HOLDOUT_WEAK_REPLICATION"
    return "HOLDOUT_FAILED"


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 64)
    print("P40 — 2024 MLB Holdout WFV Validation")
    print("=" * 64)
    print(f"  T_LOCKED={_T_LOCKED}  diagnostic_only={_DIAGNOSTIC_ONLY}  "
          f"promotion_freeze={_PROMOTION_FREEZE}")
    print(f"  P37 Baseline (2025): AUC={P37_AUC}  BrierSk={P37_BRIER_SKILL}  "
          f"WR={P37_FAVORED_WR:.1%}")
    print()

    # 1 ── Load
    records  = load_features()

    # 2 ── Filter
    filtered = apply_filters(records)
    total    = filtered["total"]
    quality  = filtered["quality"]
    se       = filtered["strong_edge"]

    print(f"[Section 2] Data inventory")
    print(f"  Total records:         {len(total):,}")
    print(f"  Quality records:       {len(quality):,}  "
          f"({len(quality)/len(total)*100:.1f}%)")
    print(f"  Strong-edge (T≥{_T_LOCKED}): {len(se):,}  "
          f"({len(se)/len(quality)*100:.1f}% of quality)")
    print()

    # 3 ── Overall metrics
    overall = compute_metrics(se)
    print(f"[Section 3] Overall strong-edge metrics (2024 holdout)")
    print(f"  n:              {overall['n']:,}")
    print(f"  Base rate:      {overall['base_rate']:.4f}  (home win rate)")
    print(f"  AUC:            {overall['auc']:.4f}  (P37: {P37_AUC})")
    print(f"  Brier Score:    {overall['brier_score']:.4f}")
    print(f"  Brier Skill:    {overall['brier_skill']:+.4f}  (P37: +{P37_BRIER_SKILL})")
    print(f"  Log-loss:       {overall['log_loss']:.4f}")
    print(f"  ECE:            {overall['ece']:.4f}")
    print(f"  Favored WR:     {overall['favored_win_rate']:.4f}  "
          f"(P37: {P37_FAVORED_WR:.4f})")
    print()

    # 4 ── Temporal stability
    stability = temporal_stability(se)
    print(f"[Section 4] Temporal stability")
    print(f"  Monthly stability rate: {stability['monthly_stability_rate']:.1%}  "
          f"(P37: {P37_STABILITY:.1%})")
    print(f"  Monthly AUC range:  "
          f"[{stability['monthly_auc_min']}, {stability['monthly_auc_max']}]")
    print(f"  Monthly AUC mean:   {stability['monthly_auc_mean']}")
    for p in ("early", "mid", "late"):
        pm = stability["period"][p]
        note = f"  [{pm['note']}]" if pm.get("note") else ""
        print(f"  {p.capitalize():5s} season: n={pm['n']:3d}  "
              f"AUC={pm['auc']}  WR={pm['favored_wr']}{note}")
    print()

    # 5 ── Compare vs P37
    auc_delta = (overall["auc"] or 0) - P37_AUC
    bsk_delta = (overall["brier_skill"] or 0) - P37_BRIER_SKILL
    wr_delta  = (overall["favored_win_rate"] or 0) - P37_FAVORED_WR
    st_delta  = stability["monthly_stability_rate"] - P37_STABILITY

    print(f"[Section 5] Comparison vs P37 2025 baseline")
    print(f"  AUC delta:            {auc_delta:+.4f}")
    print(f"  Brier Skill delta:    {bsk_delta:+.4f}")
    print(f"  Favored WR delta:     {wr_delta:+.4f}")
    print(f"  Stability delta:      {st_delta:+.4f}")
    print()

    # 6 ── Classify
    classification = classify(overall["auc"], overall["n"])
    print(f"[Section 6] Holdout classification")
    print(f"  >>> {classification} <<<")
    print()

    # 7 ── Write summary JSON
    summary = {
        "governance": {
            "phase":                    "P40",
            "diagnostic_only":          _DIAGNOSTIC_ONLY,
            "promotion_freeze":         _PROMOTION_FREEZE,
            "t_locked":                 _T_LOCKED,
            "live_api_calls":           _LIVE_API_CALLS,
            "no_champion_modification": _NO_CHAMPION_MODIFICATION,
        },
        "p37_baseline": {
            "season":            P37_SEASON,
            "auc":               P37_AUC,
            "brier_skill":       P37_BRIER_SKILL,
            "favored_win_rate":  P37_FAVORED_WR,
            "monthly_stability": P37_STABILITY,
            "strong_edge_count": P37_SE_COUNT,
        },
        "data_inventory": {
            "total_records":      len(total),
            "quality_records":    len(quality),
            "quality_rate":       round(len(quality) / max(len(total), 1), 4),
            "strong_edge_count":  len(se),
            "strong_edge_rate":   round(len(se) / max(len(quality), 1), 4),
        },
        "overall_metrics":    overall,
        "temporal_stability": stability,
        "comparison_vs_p37": {
            "auc_delta":       round(auc_delta, 4),
            "brier_skill_delta": round(bsk_delta, 4),
            "favored_wr_delta": round(wr_delta, 4),
            "stability_delta": round(st_delta, 4),
        },
        "classification": {
            "classification":    classification,
            "threshold_confirmed": _THR_CONFIRMED,
            "threshold_failed":  _THR_FAILED,
            "min_viable":        _MIN_N_VIABLE,
        },
    }

    _SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    _SUMMARY_OUT.write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(f"[P40] Summary written: {_SUMMARY_OUT.name}")

    # Exit code
    if classification in ("HOLDOUT_CONFIRMED", "HOLDOUT_WEAK_REPLICATION"):
        print(f"\n✅ P40 PASS — {classification}")
        sys.exit(0)
    elif classification == "HOLDOUT_FAILED":
        print(f"\n❌ P40 DIAGNOSTIC — {classification}")
        sys.exit(2)
    else:
        print(f"\n⚠️  P40 INCONCLUSIVE — {classification}")
        sys.exit(1)


if __name__ == "__main__":
    main()
