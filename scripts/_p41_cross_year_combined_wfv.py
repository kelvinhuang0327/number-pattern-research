"""
P41: sp_fip_delta Cross-Year Aggregated WFV — 2024 + 2025 Combined OOS
=======================================================================
Preconditions:
  - P39 CLOSED (6221234): mlb_2024_sp_fip_delta_features.jsonl built
  - P40 CLOSED (5870cef): HOLDOUT_CONFIRMED AUC=0.5788 (2024 OOS)
  - P37 baseline locked: AUC=0.5665, T_LOCKED=0.50 (2025 in-sample reference)

Governance (all locked, no re-optimization):
  - diagnostic_only = True
  - promotion_freeze = True
  - T_LOCKED = 0.50
  - live_api_calls = 0
  - no_champion_modification = True

Tasks:
  1. Load 2025 data (phase56, quality filter)
  2. Load 2024 data (P39 JSONL, quality + pit_safe filter)
  3. Apply T_LOCKED=0.50 strong-edge filter
  4. Combined AUC + 95% bootstrap CI (n_boot=1000)
  5. 5-band analysis by |sp_fip_delta|
  6. Cross-year seasonal breakdown (2024 vs 2025 separately)
  7. Classify, write JSON, exit

Exit codes:
  0 = CROSS_YEAR_CONFIRMED or CROSS_YEAR_WEAK (AUC >= 0.50)
  1 = INCONCLUSIVE (n < 50)
  2 = CROSS_YEAR_FAILED (AUC < 0.50)
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Any

# ── Governance ────────────────────────────────────────────────────────────────
GOVERNANCE = {
    "diagnostic_only": True,
    "promotion_freeze": True,
    "T_LOCKED": 0.50,
    "live_api_calls": 0,
    "no_champion_modification": True,
    "p39_commit": "6221234",
    "p40_commit": "5870cef",
}
assert GOVERNANCE["diagnostic_only"] is True, "ABORT: diagnostic_only must be True"
assert GOVERNANCE["promotion_freeze"] is True, "ABORT: promotion_freeze must be True"
assert GOVERNANCE["live_api_calls"] == 0, "ABORT: live_api_calls must be 0"
T_LOCKED: float = GOVERNANCE["T_LOCKED"]

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
FILE_2025 = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
FILE_2024 = ROOT / "data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl"
OUT_JSON  = ROOT / "data/mlb_2025/derived/p41_cross_year_combined_summary.json"

N_BOOT = 1_000
BAND_EDGES = [0.50, 0.75, 1.00, 1.25, 1.50, float("inf")]
BAND_LABELS = ["0.50–0.75", "0.75–1.00", "1.00–1.25", "1.25–1.50", "1.50+"]

# ── Math helpers ──────────────────────────────────────────────────────────────
def _auc_mannwhitney(y_true: list[int], y_score: list[float]) -> float:
    """AUROC via Mann-Whitney U (no sklearn)."""
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
    base = sum(t for t in y_true) / len(y_true)
    b_ref = sum((base - t) ** 2 for t in y_true) / len(y_true)
    return 1.0 - _brier(y_true, y_score) / b_ref if b_ref > 0 else float("nan")


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
    return sum(abs(sum(p for p, _ in b) / len(b) - sum(t for _, t in b) / len(b)) * len(b) / n
               for b in bins if b)


def _bootstrap_auc_ci(
    y_true: list[int], y_score: list[float], n_boot: int = N_BOOT, seed: int = 42
) -> tuple[float, float, float]:
    """Returns (mean_boot_auc, ci_low_95, ci_high_95)."""
    rng = random.Random(seed)
    n = len(y_true)
    aucs: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        bt_y = [y_true[i] for i in idx]
        bt_s = [y_score[i] for i in idx]
        a = _auc_mannwhitney(bt_y, bt_s)
        if not math.isnan(a):
            aucs.append(a)
    aucs.sort()
    lo = aucs[int(0.025 * len(aucs))]
    hi = aucs[int(0.975 * len(aucs))]
    return sum(aucs) / len(aucs), lo, hi


# ── Data loading ──────────────────────────────────────────────────────────────
def load_2025() -> list[dict]:
    records: list[dict] = []
    with open(FILE_2025) as f:
        for line in f:
            r = json.loads(line)
            p0 = r.get("p0_features", {})
            if not p0.get("sp_fip_delta_available"):
                continue
            src = p0.get("sp_context_source", "")
            if src == "league_average_fallback":
                continue
            delta = p0.get("sp_fip_delta")
            hw = r.get("home_win")
            gd = r.get("game_date", "")
            if hw is None or delta is None:
                continue
            records.append({
                "sp_fip_delta": float(delta),
                "actual_home_win": int(bool(hw)),
                "game_date": str(gd),
                "sp_context_source": src,
                "season": 2025,
            })
    return records


def load_2024() -> list[dict]:
    records: list[dict] = []
    with open(FILE_2024) as f:
        for line in f:
            r = json.loads(line)
            src = r.get("sp_context_source", "")
            if src == "league_average_fallback":
                continue
            if not r.get("pit_safe", True):
                continue
            delta = r.get("sp_fip_delta")
            hw = r.get("actual_home_win")
            gd = r.get("game_date", "")
            if hw is None or delta is None:
                continue
            records.append({
                "sp_fip_delta": float(delta),
                "actual_home_win": int(hw),
                "game_date": str(gd),
                "sp_context_source": r.get("sp_context_source", ""),
                "season": 2024,
            })
    return records


# ── Band analysis ─────────────────────────────────────────────────────────────
def band_analysis(strong: list[dict]) -> list[dict]:
    results = []
    for label, lo, hi in zip(BAND_LABELS, BAND_EDGES, BAND_EDGES[1:]):
        band = [r for r in strong if lo <= abs(r["sp_fip_delta"]) < hi]
        if len(band) < 10:
            results.append({"band": label, "n": len(band), "auc": None, "favored_wr": None,
                             "note": "insufficient_data"})
            continue
        y_t = [r["actual_home_win"] for r in band]
        y_s = [r["sp_fip_delta"] for r in band]
        auc = _auc_mannwhitney(y_t, y_s)
        wr = sum(1 for r in band if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])) / len(band)
        results.append({
            "band": label,
            "n": len(band),
            "auc": round(auc, 4),
            "favored_wr": round(wr, 4),
        })
    return results


# ── Seasonal breakdown ────────────────────────────────────────────────────────
def seasonal_breakdown(strong: list[dict], season: int) -> list[dict]:
    if season == 2025:
        phases = [
            ("Early (Apr–May)", lambda m: m in (4, 5)),
            ("Mid  (Jun–Aug)",  lambda m: m in (6, 7, 8)),
            ("Late (Sep+)",     lambda m: m >= 9),
        ]
    else:  # 2024 starts in March
        phases = [
            ("Early (Mar–May)", lambda m: m in (3, 4, 5)),
            ("Mid  (Jun–Aug)",  lambda m: m in (6, 7, 8)),
            ("Late (Sep+)",     lambda m: m >= 9),
        ]
    results = []
    yr = [r for r in strong if r["season"] == season]
    for label, filt in phases:
        sub = [r for r in yr if filt(int(r["game_date"][5:7]))]
        if len(sub) < 10:
            results.append({"period": label, "n": len(sub), "auc": None,
                             "favored_wr": None, "note": "insufficient_data"})
            continue
        y_t = [r["actual_home_win"] for r in sub]
        y_s = [r["sp_fip_delta"] for r in sub]
        auc = _auc_mannwhitney(y_t, y_s)
        wr = sum(1 for r in sub if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])) / len(sub)
        results.append({
            "period": label, "n": len(sub),
            "auc": round(auc, 4), "favored_wr": round(wr, 4),
        })
    return results


# ── Monthly stability (combined) ──────────────────────────────────────────────
def monthly_auc(strong: list[dict]) -> dict[str, Any]:
    months: dict[str, list] = {}
    for r in strong:
        mo = r["game_date"][:7]  # YYYY-MM
        months.setdefault(mo, []).append(r)
    results = {}
    stable_count = 0
    for mo in sorted(months):
        sub = months[mo]
        if len(sub) < 5:
            results[mo] = {"n": len(sub), "auc": None, "note": "too_few"}
            continue
        y_t = [r["actual_home_win"] for r in sub]
        y_s = [r["sp_fip_delta"] for r in sub]
        a = _auc_mannwhitney(y_t, y_s)
        results[mo] = {"n": len(sub), "auc": round(a, 4)}
        if a >= 0.50:
            stable_count += 1
    eligible = [mo for mo, v in results.items() if v.get("auc") is not None]
    stability_rate = stable_count / len(eligible) if eligible else 0.0
    return {"monthly_auc": results, "stability_rate": round(stability_rate, 4),
            "stable_months": stable_count, "eligible_months": len(eligible)}


# ── Classification ────────────────────────────────────────────────────────────
def classify(auc: float, n: int) -> str:
    if n < 50:
        return "INCONCLUSIVE"
    if auc >= 0.54:
        return "CROSS_YEAR_CONFIRMED"
    if auc >= 0.50:
        return "CROSS_YEAR_WEAK"
    return "CROSS_YEAR_FAILED"


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    print("[P41] Loading 2025 quality records …")
    rec25 = load_2025()
    print("[P41] Loading 2024 quality records …")
    rec24 = load_2024()

    strong25 = [r for r in rec25 if abs(r["sp_fip_delta"]) >= T_LOCKED]
    strong24 = [r for r in rec24 if abs(r["sp_fip_delta"]) >= T_LOCKED]
    combined = strong24 + strong25

    print(f"  2025: quality={len(rec25)}, strong={len(strong25)}")
    print(f"  2024: quality={len(rec24)}, strong={len(strong24)}")
    print(f"  Combined strong-edge n={len(combined)}")

    y_true = [r["actual_home_win"] for r in combined]
    y_score = [r["sp_fip_delta"] for r in combined]

    # ── Section 4: Combined metrics ───────────────────────────────────────────
    print("[P41] Computing combined metrics …")
    auc = _auc_mannwhitney(y_true, y_score)
    brier = _brier(y_true, y_score)
    brier_sk = _brier_skill(y_true, y_score)
    ll = _log_loss(y_true, y_score)
    ece = _ece(y_true, y_score)
    favored_wr = sum(1 for r in combined if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])) / len(combined)

    # ── Bootstrap CI ─────────────────────────────────────────────────────────
    print(f"[P41] Bootstrap CI (n_boot={N_BOOT}) …")
    boot_mean, ci_lo, ci_hi = _bootstrap_auc_ci(y_true, y_score)

    print(f"  AUC={auc:.4f}  95% CI=[{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  BrierSk={brier_sk:.4f}  FavoredWR={favored_wr:.4f}")

    # ── Per-year metrics ──────────────────────────────────────────────────────
    def _year_metrics(strong: list[dict]) -> dict:
        yt = [r["actual_home_win"] for r in strong]
        ys = [r["sp_fip_delta"] for r in strong]
        a = _auc_mannwhitney(yt, ys)
        wr = sum(1 for r in strong if (r["sp_fip_delta"] > 0) == bool(r["actual_home_win"])) / len(strong)
        return {"n": len(strong), "auc": round(a, 4), "favored_wr": round(wr, 4)}

    per_year = {
        "2024": _year_metrics(strong24),
        "2025": _year_metrics(strong25),
    }

    # ── Section 5: 5-band analysis ────────────────────────────────────────────
    print("[P41] Band analysis …")
    bands = band_analysis(combined)
    for b in bands:
        print(f"  {b['band']:12s}  n={b['n']:4d}  AUC={b.get('auc','N/A')}  WR={b.get('favored_wr','N/A')}")

    # ── Section 6: Seasonal breakdown ────────────────────────────────────────
    print("[P41] Seasonal breakdown …")
    season24 = seasonal_breakdown(combined, 2024)
    season25 = seasonal_breakdown(combined, 2025)
    for row in season24:
        print(f"  2024 {row['period']:20s}  n={row['n']:4d}  AUC={row.get('auc','N/A')}  WR={row.get('favored_wr','N/A')}")
    for row in season25:
        print(f"  2025 {row['period']:20s}  n={row['n']:4d}  AUC={row.get('auc','N/A')}  WR={row.get('favored_wr','N/A')}")

    # ── Monthly stability ─────────────────────────────────────────────────────
    print("[P41] Monthly stability …")
    monthly = monthly_auc(combined)
    print(f"  Stability rate: {monthly['stability_rate']:.1%} ({monthly['stable_months']}/{monthly['eligible_months']} months)")

    # ── P37 reference ─────────────────────────────────────────────────────────
    P37_REF = {
        "source": "P37 in-sample 2025 baseline (locked)",
        "auc": 0.5665,
        "brier_skill": 0.0123,
        "favored_wr": 0.6080,
        "monthly_stability": 1.0,
        "strong_edge_count": 531,
        "T_LOCKED": 0.50,
    }

    # ── Section 7: Classify ───────────────────────────────────────────────────
    classification = classify(auc, len(combined))
    print(f"  Classification: {classification}")

    # ── Write JSON ────────────────────────────────────────────────────────────
    summary: dict[str, Any] = {
        "version": "p41_v1",
        "governance": GOVERNANCE,
        "data_inventory": {
            "file_2025": str(FILE_2025.name),
            "file_2024": str(FILE_2024.name),
            "n_2025_quality": len(rec25),
            "n_2024_quality": len(rec24),
            "n_2025_strong_edge": len(strong25),
            "n_2024_strong_edge": len(strong24),
            "n_combined_strong_edge": len(combined),
            "T_LOCKED": T_LOCKED,
        },
        "per_year_metrics": per_year,
        "combined_metrics": {
            "n": len(combined),
            "auc": round(auc, 4),
            "brier_score": round(brier, 4),
            "brier_skill": round(brier_sk, 4),
            "log_loss": round(ll, 4),
            "ece": round(ece, 4),
            "favored_wr": round(favored_wr, 4),
        },
        "bootstrap_ci": {
            "n_boot": N_BOOT,
            "seed": 42,
            "auc_mean": round(boot_mean, 4),
            "ci_95_low": round(ci_lo, 4),
            "ci_95_high": round(ci_hi, 4),
            "ci_excludes_0_50": bool(ci_lo > 0.50),
        },
        "band_analysis": bands,
        "seasonal_breakdown": {
            "2024": season24,
            "2025": season25,
        },
        "monthly_stability": monthly,
        "p37_reference": P37_REF,
        "comparison_vs_p37": {
            "combined_vs_p37_auc_delta": round(auc - P37_REF["auc"], 4),
            "combined_vs_p37_wr_delta": round(favored_wr - P37_REF["favored_wr"], 4),
            "per_year_2024_auc": per_year["2024"]["auc"],
            "per_year_2025_auc": per_year["2025"]["auc"],
            "cross_year_auc_range": [
                min(per_year["2024"]["auc"], per_year["2025"]["auc"]),
                max(per_year["2024"]["auc"], per_year["2025"]["auc"]),
            ],
        },
        "classification": {
            "classification": classification,
            "combined_auc": round(auc, 4),
            "combined_n": len(combined),
            "threshold_used": 0.54,
            "ci_95_low": round(ci_lo, 4),
            "ci_95_high": round(ci_hi, 4),
            "ci_excludes_0_50": bool(ci_lo > 0.50),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[P41] JSON written → {OUT_JSON.relative_to(ROOT)}")

    # ── Final verdict ──────────────────────────────────────────────────────────
    if classification == "CROSS_YEAR_CONFIRMED":
        print(f"✅ P41 PASS — {classification}")
        return 0
    elif classification == "CROSS_YEAR_WEAK":
        print(f"⚠️  P41 PASS (WEAK) — {classification}")
        return 0
    elif classification == "INCONCLUSIVE":
        print(f"⚠️  P41 INCONCLUSIVE — n={len(combined)} < 50")
        return 1
    else:
        print(f"❌ P41 FAIL — {classification}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
