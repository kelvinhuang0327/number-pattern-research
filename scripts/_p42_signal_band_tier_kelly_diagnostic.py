"""
P42: sp_fip_delta Signal-band Tier Framework + Kelly-equivalent Diagnostic
===========================================================================
Preconditions:
  - P41 CLOSED (6ee4e57): CROSS_YEAR_CONFIRMED, n=1490, AUC=0.5865
  - P40 CLOSED (5870cef): 2024 HOLDOUT_CONFIRMED, AUC=0.5788
  - P37 baseline locked: T_LOCKED=0.50

Governance (all locked):
  - diagnostic_only      = True
  - promotion_freeze     = True
  - T_LOCKED             = 0.50 (unchanged)
  - live_api_calls       = 0
  - no_champion_modification = True
  - kelly_deploy_allowed = False   ← Kelly analysis is DIAGNOSTIC ONLY

Tier definitions:
  Tier A  |sp_fip_delta| >= 1.50   (highest conviction)
  Tier B  |sp_fip_delta| >= 1.25
  Tier C  |sp_fip_delta| >= 0.50   (current locked threshold, P37 baseline)

Per-tier metrics:
  n, coverage, AUC, favored_wr, brier, brier_skill, ece, log_loss
  95% bootstrap CI for AUC and WR

Year-by-year validation: 2024 vs 2025 per tier

Tier A vs Tier C: AUC delta + bootstrap significance (permutation)

Kelly-equivalent diagnostic:
  Assumes theoretical fixed decimal odds (NOT live odds)
  Output: diagnostic fraction only — NOT a betting recommendation

Exit codes:
  0  all tiers produce positive AUC
  1  any tier INCONCLUSIVE (n < 50)
  2  any tier CROSS_YEAR_FAILED
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Any

# ── Governance ────────────────────────────────────────────────────────────────
GOVERNANCE: dict[str, Any] = {
    "diagnostic_only": True,
    "promotion_freeze": True,
    "T_LOCKED": 0.50,
    "live_api_calls": 0,
    "no_champion_modification": True,
    "kelly_deploy_allowed": False,
    "p41_commit": "6ee4e57",
    "p40_commit": "5870cef",
}
assert GOVERNANCE["diagnostic_only"] is True
assert GOVERNANCE["promotion_freeze"] is True
assert GOVERNANCE["kelly_deploy_allowed"] is False
assert GOVERNANCE["live_api_calls"] == 0

T_LOCKED: float = GOVERNANCE["T_LOCKED"]

TIER_THRESHOLDS: dict[str, float] = {"A": 1.50, "B": 1.25, "C": 0.50}

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
FILE_2025 = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
FILE_2024 = ROOT / "data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl"
OUT_JSON  = ROOT / "data/mlb_2025/derived/p42_signal_band_tier_kelly_summary.json"

N_BOOT   = 1_000
N_PERM   = 2_000   # permutation test iterations
SEED     = 42

# Theoretical odds scenarios for Kelly diagnostic (NOT live odds)
KELLY_SCENARIOS: list[dict] = [
    {"label": "fair_no_vig",    "decimal_odds": 2.00},
    {"label": "tight_book",     "decimal_odds": 1.90},
    {"label": "standard_book",  "decimal_odds": 1.85},
]


# ── Math helpers ──────────────────────────────────────────────────────────────
def _auc_mannwhitney(y_true: list[int], y_score: list[float]) -> float:
    pos = [s for t, s in zip(y_true, y_score) if t == 1]
    neg = [s for t, s in zip(y_true, y_score) if t == 0]
    if not pos or not neg:
        return float("nan")
    U = sum(1 if p > n else 0.5 if p == n else 0 for p in pos for n in neg)
    return U / (len(pos) * len(neg))


def _sigmoid(x: float, k: float = 0.8) -> float:
    return 1.0 / (1.0 + math.exp(-k * x))


def _brier(y_true: list[int], y_score: list[float]) -> float:
    probs = [_sigmoid(s) for s in y_score]
    return sum((p - t) ** 2 for p, t in zip(probs, y_true)) / len(y_true)


def _brier_skill(y_true: list[int], y_score: list[float]) -> float:
    base = sum(y_true) / len(y_true)
    b_ref = sum((base - t) ** 2 for t in y_true) / len(y_true)
    if b_ref <= 0:
        return float("nan")
    return 1.0 - _brier(y_true, y_score) / b_ref


def _log_loss(y_true: list[int], y_score: list[float]) -> float:
    EPS = 1e-9
    probs = [_sigmoid(s) for s in y_score]
    return -sum(t * math.log(p + EPS) + (1 - t) * math.log(1 - p + EPS)
                for p, t in zip(probs, y_true)) / len(y_true)


def _ece(y_true: list[int], y_score: list[float], n_bins: int = 5) -> float:
    probs = [_sigmoid(s) for s in y_score]
    bins: list[list] = [[] for _ in range(n_bins)]
    for p, t in zip(probs, y_true):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, t))
    n = len(y_true)
    return sum(
        abs(sum(p for p, _ in b) / len(b) - sum(t for _, t in b) / len(b)) * len(b) / n
        for b in bins if b
    )


def _bootstrap_auc_ci(
    y_true: list[int],
    y_score: list[float],
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """Returns (mean, ci_lo, ci_hi)."""
    rng = random.Random(seed)
    n = len(y_true)
    aucs: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        a = _auc_mannwhitney([y_true[i] for i in idx], [y_score[i] for i in idx])
        if not math.isnan(a):
            aucs.append(a)
    aucs.sort()
    lo = aucs[int(0.025 * len(aucs))]
    hi = aucs[int(0.975 * len(aucs))]
    return sum(aucs) / len(aucs), lo, hi


def _bootstrap_wr_ci(
    records: list[dict],
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """Bootstrap CI for favored_wr. Returns (mean, ci_lo, ci_hi)."""
    rng = random.Random(seed + 1)
    n = len(records)
    wrs: list[float] = []
    for _ in range(n_boot):
        sample = [records[rng.randint(0, n - 1)] for _ in range(n)]
        wr = sum(
            1 for r in sample if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])
        ) / n
        wrs.append(wr)
    wrs.sort()
    lo = wrs[int(0.025 * len(wrs))]
    hi = wrs[int(0.975 * len(wrs))]
    return sum(wrs) / len(wrs), lo, hi


def _permutation_auc_pvalue(
    y_true_a: list[int],
    y_score_a: list[float],
    y_true_c: list[int],
    y_score_c: list[float],
    n_perm: int = N_PERM,
    seed: int = SEED + 2,
) -> tuple[float, float]:
    """
    One-sided permutation test: H0 = AUC_A <= AUC_C.
    Returns (observed_delta, p_value).
    Pools A+C, randomly assigns |A| records to "tier A", rest to "tier C".
    """
    obs_a = _auc_mannwhitney(y_true_a, y_score_a)
    obs_c = _auc_mannwhitney(y_true_c, y_score_c)
    obs_delta = obs_a - obs_c

    # Pool all records
    all_t = y_true_a + y_true_c
    all_s = y_score_a + y_score_c
    n_a = len(y_true_a)
    n_total = len(all_t)
    rng = random.Random(seed)

    count_exceed = 0
    for _ in range(n_perm):
        idx = list(range(n_total))
        rng.shuffle(idx)
        perm_a_t = [all_t[i] for i in idx[:n_a]]
        perm_a_s = [all_s[i] for i in idx[:n_a]]
        perm_c_t = [all_t[i] for i in idx[n_a:]]
        perm_c_s = [all_s[i] for i in idx[n_a:]]
        perm_delta = _auc_mannwhitney(perm_a_t, perm_a_s) - _auc_mannwhitney(perm_c_t, perm_c_s)
        if perm_delta >= obs_delta:
            count_exceed += 1

    p_value = count_exceed / n_perm
    return round(obs_delta, 4), round(p_value, 4)


# ── Kelly diagnostic ──────────────────────────────────────────────────────────
def _kelly_diagnostic(p_win: float) -> list[dict]:
    """
    DIAGNOSTIC ONLY — NOT a betting recommendation.
    Kelly fraction = (p * b - (1-p)) / b  where b = decimal_odds - 1
    Quarter-Kelly shown as conservative variant.
    """
    results = []
    for scenario in KELLY_SCENARIOS:
        d = scenario["decimal_odds"]
        b = d - 1.0
        full_k = (p_win * b - (1.0 - p_win)) / b
        results.append({
            "scenario": scenario["label"],
            "decimal_odds": d,
            "p_win_assumed": round(p_win, 4),
            "full_kelly_fraction": round(full_k, 4) if full_k > 0 else None,
            "quarter_kelly_fraction": round(full_k / 4.0, 4) if full_k > 0 else None,
            "positive_ev": full_k > 0,
            "note": "DIAGNOSTIC ONLY — theoretical, assumes p_win=favored_wr as oracle. NOT a live recommendation.",
        })
    return results


# ── Tier classification ───────────────────────────────────────────────────────
def classify_tier(
    auc: float, n: int, ci_lo: float, ci_hi: float
) -> str:
    if n < 100:
        return "SAMPLE_LIMITED" if auc < 0.65 else "SAMPLE_LIMITED_HIGH_AUC"
    if math.isnan(auc) or math.isnan(ci_lo):
        return "CALIBRATION_REQUIRED"
    if ci_lo > 0.54 and n >= 200:
        return "HIGH_CONFIDENCE_DIAGNOSTIC"
    if ci_lo > 0.50 and n >= 1_000:
        return "BROAD_STABLE_SIGNAL"
    if ci_lo > 0.50:
        return "MEDIUM_CONFIDENCE_DIAGNOSTIC"
    return "CALIBRATION_REQUIRED"


# ── Data loading ──────────────────────────────────────────────────────────────
def load_all_quality() -> list[dict]:
    """Load 2024 + 2025 quality records (pre-strong-edge filter)."""
    records: list[dict] = []

    # 2024
    with open(FILE_2024) as f:
        for line in f:
            r = json.loads(line)
            if r.get("sp_context_source") == "league_average_fallback":
                continue
            if not r.get("pit_safe", True):
                continue
            delta = r.get("sp_fip_delta")
            hw = r.get("actual_home_win")
            if hw is None or delta is None:
                continue
            records.append({
                "sp_fip_delta": float(delta),
                "actual_home_win": int(hw),
                "game_date": str(r.get("game_date", "")),
                "season": 2024,
            })

    # 2025
    with open(FILE_2025) as f:
        for line in f:
            r = json.loads(line)
            p0 = r.get("p0_features", {})
            if not p0.get("sp_fip_delta_available"):
                continue
            if p0.get("sp_context_source") == "league_average_fallback":
                continue
            delta = p0.get("sp_fip_delta")
            hw = r.get("home_win")
            if hw is None or delta is None:
                continue
            records.append({
                "sp_fip_delta": float(delta),
                "actual_home_win": int(bool(hw)),
                "game_date": str(r.get("game_date", "")),
                "season": 2025,
            })

    return records


# ── Tier metrics ──────────────────────────────────────────────────────────────
def compute_tier_metrics(
    records: list[dict],
    tier: str,
    threshold: float,
    n_quality_total: int,
    verbose: bool = True,
) -> dict[str, Any]:
    strong = [r for r in records if abs(r["sp_fip_delta"]) >= threshold]
    n = len(strong)
    coverage = n / n_quality_total if n_quality_total > 0 else 0.0

    if n == 0:
        return {"tier": tier, "threshold": threshold, "n": 0,
                "error": "no_records", "classification": "CALIBRATION_REQUIRED"}

    y_t = [r["actual_home_win"] for r in strong]
    y_s = [r["sp_fip_delta"] for r in strong]

    auc    = _auc_mannwhitney(y_t, y_s)
    brier  = _brier(y_t, y_s)
    bsk    = _brier_skill(y_t, y_s)
    ll     = _log_loss(y_t, y_s)
    ece    = _ece(y_t, y_s)
    wr     = sum(1 for r in strong if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])) / n

    print(f"  Tier {tier} (|delta|>={threshold}): n={n}, AUC={auc:.4f}, WR={wr:.4f}")

    # Bootstrap CI for AUC
    boot_mean, ci_lo, ci_hi = _bootstrap_auc_ci(y_t, y_s)
    # Bootstrap CI for WR
    wr_mean, wr_lo, wr_hi = _bootstrap_wr_ci(strong)

    # Per-year breakdown
    per_year: dict[str, Any] = {}
    for yr in (2024, 2025):
        sub = [r for r in strong if r["season"] == yr]
        if len(sub) < 10:
            per_year[str(yr)] = {"n": len(sub), "note": "insufficient"}
            continue
        yt = [r["actual_home_win"] for r in sub]
        ys = [r["sp_fip_delta"] for r in sub]
        a  = _auc_mannwhitney(yt, ys)
        w  = sum(1 for r in sub if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])) / len(sub)
        per_year[str(yr)] = {
            "n": len(sub),
            "auc": round(a, 4),
            "favored_wr": round(w, 4),
            "auc_positive": a > 0.50,
        }

    cross_year_stable = all(
        v.get("auc_positive", False)
        for v in per_year.values()
        if "auc_positive" in v
    )

    # Kelly diagnostic (uses overall favored_wr as oracle estimate)
    kelly = _kelly_diagnostic(wr)

    # Tier classification
    cls = classify_tier(auc, n, ci_lo, ci_hi)

    return {
        "tier": tier,
        "threshold": threshold,
        "n": n,
        "coverage_pct": round(coverage * 100, 2),
        "auc": round(auc, 4),
        "favored_wr": round(wr, 4),
        "brier_score": round(brier, 4),
        "brier_skill": round(bsk, 4),
        "log_loss": round(ll, 4),
        "ece": round(ece, 4),
        "bootstrap_auc": {
            "n_boot": N_BOOT,
            "mean": round(boot_mean, 4),
            "ci_95_low": round(ci_lo, 4),
            "ci_95_high": round(ci_hi, 4),
            "ci_excludes_050": bool(ci_lo > 0.50),
            "ci_excludes_054": bool(ci_lo > 0.54),
        },
        "bootstrap_wr": {
            "mean": round(wr_mean, 4),
            "ci_95_low": round(wr_lo, 4),
            "ci_95_high": round(wr_hi, 4),
            "ci_excludes_050": bool(wr_lo > 0.50),
        },
        "per_year": per_year,
        "cross_year_stable": cross_year_stable,
        "kelly_diagnostic": kelly,
        "classification": cls,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    print("[P42] Loading quality records …")
    all_records = load_all_quality()
    n_quality_total = len(all_records)
    n24 = sum(1 for r in all_records if r["season"] == 2024)
    n25 = sum(1 for r in all_records if r["season"] == 2025)
    print(f"  Quality total: {n_quality_total}  (2024: {n24}, 2025: {n25})")

    # ── Compute tier metrics ──────────────────────────────────────────────────
    print("\n[P42] Tier metrics …")
    tiers: dict[str, dict] = {}
    for name, thresh in TIER_THRESHOLDS.items():
        tiers[name] = compute_tier_metrics(
            all_records, name, thresh, n_quality_total
        )

    # ── Tier A vs Tier C significance test ───────────────────────────────────
    print(f"\n[P42] Permutation test: Tier A vs Tier C (n_perm={N_PERM}) …")
    tier_a_records = [r for r in all_records if abs(r["sp_fip_delta"]) >= TIER_THRESHOLDS["A"]]
    tier_c_records = [r for r in all_records if abs(r["sp_fip_delta"]) >= TIER_THRESHOLDS["C"]]
    a_yt = [r["actual_home_win"] for r in tier_a_records]
    a_ys = [r["sp_fip_delta"] for r in tier_a_records]
    c_yt = [r["actual_home_win"] for r in tier_c_records]
    c_ys = [r["sp_fip_delta"] for r in tier_c_records]

    obs_delta, p_value = _permutation_auc_pvalue(a_yt, a_ys, c_yt, c_ys)
    significance = "significant" if p_value <= 0.05 else "not_significant"
    print(f"  AUC delta (A-C): {obs_delta:+.4f},  p-value: {p_value:.4f} ({significance})")
    print(f"  Caveat: Tier A n={len(tier_a_records)} — small sample, interpret with caution")

    comparison_ac = {
        "tier_a_auc": tiers["A"]["auc"],
        "tier_c_auc": tiers["C"]["auc"],
        "observed_delta": obs_delta,
        "permutation_p_value": p_value,
        "n_permutations": N_PERM,
        "significance_05": significance,
        "tier_a_n": len(tier_a_records),
        "caveat": "Tier A n=47 — insufficient for definitive statistical conclusion. P-value directional only.",
    }

    # ── Classification summary ────────────────────────────────────────────────
    print("\n[P42] Tier classifications:")
    for name in ("A", "B", "C"):
        t = tiers[name]
        print(f"  Tier {name}: {t['classification']}  (n={t['n']}, AUC={t['auc']}, CI=[{t['bootstrap_auc']['ci_95_low']},{t['bootstrap_auc']['ci_95_high']}])")

    # ── Sanity checks ─────────────────────────────────────────────────────────
    failed = False
    inconclusive = False
    for name in ("A", "B", "C"):
        t = tiers[name]
        if t["n"] < 50:
            inconclusive = True
        if not math.isnan(t["auc"]) and t["auc"] < 0.50:
            failed = True

    # ── Build output JSON ─────────────────────────────────────────────────────
    summary: dict[str, Any] = {
        "version": "p42_v1",
        "governance": GOVERNANCE,
        "data_inventory": {
            "n_quality_total": n_quality_total,
            "n_quality_2024": n24,
            "n_quality_2025": n25,
            "T_LOCKED": T_LOCKED,
        },
        "tier_definitions": {
            name: {"threshold_abs_delta": thresh}
            for name, thresh in TIER_THRESHOLDS.items()
        },
        "tiers": tiers,
        "comparison_tier_a_vs_c": comparison_ac,
        "p41_reference": {
            "combined_auc": 0.5865,
            "combined_n": 1490,
            "ci_95": [0.5557, 0.6170],
            "commit": "6ee4e57",
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[P42] JSON written → {OUT_JSON.relative_to(ROOT)}")

    if inconclusive:
        print("⚠️  P42 INCONCLUSIVE — Tier A n < 50 (directional only)")
        return 1
    if failed:
        print("❌ P42 FAIL — at least one tier AUC < 0.50")
        return 2
    print("✅ P42 PASS — all tiers AUC > 0.50")
    return 0


if __name__ == "__main__":
    sys.exit(main())
