"""
P37: sp_fip_delta Strong-Edge Threshold Optimization
diagnostic_only=True | promotion_freeze=True

Convention:
  sp_fip_delta = away_SP_FIP - home_SP_FIP
    >= +T  →  home SP advantage (strong edge)
    <= -T  →  away SP advantage (strong edge)
    |x| <T  →  neutral zone (no edge declared)

For each threshold T in GRID:
  1. Coverage stats: n_covered, coverage%
  2. Favored-team win rate: hw_home_edge, hw_away_edge, spread, lift
  3. AUC of sp_fip_delta on covered subset (raw score, no model)
  4. WFV 70/30 on covered subset: AUC, Brier Skill, ECE, log-loss
  5. Monthly stability on covered subset
  6. Season-phase breakdown

Data: same as P36 — phase56 quality-filtered 1,409 rows
"""
from __future__ import annotations
import json, math, collections
from typing import NamedTuple

# ── Governance ──────────────────────────────────────────────────────────────────
DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True

PHASE56 = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
EXCLUDED_TIER = "league_average_fallback"

THRESHOLDS = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]

MIN_SAMPLE_WFV     = 150   # min covered records for a reliable WFV
MIN_SAMPLE_MONTHLY = 15    # min per month for monthly AUC


# ── Math primitives ─────────────────────────────────────────────────────────────
def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)

def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    pos = [s for y, s in zip(y_true, y_score) if y == 1]
    neg = [s for y, s in zip(y_true, y_score) if y == 0]
    if not pos or not neg:
        return float("nan")
    conc = sum(p > n for p in pos for n in neg)
    tied = sum(p == n for p in pos for n in neg)
    return (conc + 0.5 * tied) / (len(pos) * len(neg))

def brier(y: list[int], p: list[float]) -> float:
    return sum((yi - pi) ** 2 for yi, pi in zip(y, p)) / len(y)

def brier_skill(y: list[int], p: list[float]) -> float:
    br = sum(y) / len(y)
    bs0 = brier(y, [br] * len(y))
    return 1 - brier(y, p) / bs0 if bs0 > 0 else 0.0

def log_loss_val(y: list[int], p: list[float]) -> float:
    eps = 1e-9
    return -sum(
        yi * math.log(pi + eps) + (1 - yi) * math.log(1 - pi + eps)
        for yi, pi in zip(y, p)
    ) / len(y)

def ece_val(y: list[int], p: list[float], n_bins: int = 8) -> float:
    bins: list[list] = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((pi, yi))
    total = len(y)
    return sum(
        abs(sum(x[0] for x in b) / len(b) - sum(x[1] for x in b) / len(b))
        * len(b) / total
        for b in bins if b
    )

def standardize(X: list[float]) -> tuple[list[float], float, float]:
    n = len(X)
    mu = sum(X) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in X) / n) or 1.0
    return [(x - mu) / sd for x in X], mu, sd

def train_logistic(
    X: list[float], y: list[int], lr: float = 0.05, epochs: int = 800
) -> tuple[float, float]:
    w, b = 0.0, 0.0
    n = len(X)
    for _ in range(epochs):
        gw = gb = 0.0
        for xi, yi in zip(X, y):
            p = sigmoid(w * xi + b)
            err = p - yi
            gw += err * xi
            gb += err
        w -= lr * gw / n
        b -= lr * gb / n
    return w, b

def stddev(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mu = sum(xs) / n
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / n)


# ── Record ──────────────────────────────────────────────────────────────────────
class Rec(NamedTuple):
    game_date: str
    home_team: str
    sp_fip_delta: float
    sp_context_source: str
    season_game_index: float
    home_win: int


# ── Data loading ─────────────────────────────────────────────────────────────────
def load_records() -> list[Rec]:
    raw = [json.loads(l) for l in open(PHASE56)]
    seen: set = set()
    recs: list[Rec] = []
    skip_fallback = 0
    for r in raw:
        key = (r["game_date"], r["home_team"])
        if key in seen:
            continue
        seen.add(key)
        p0 = r.get("p0_features", {})
        if p0.get("sp_context_source") == EXCLUDED_TIER:
            skip_fallback += 1
            continue
        hw = r.get("home_win")
        if hw is None:
            continue
        recs.append(Rec(
            game_date=r["game_date"],
            home_team=r["home_team"],
            sp_fip_delta=float(p0.get("sp_fip_delta", 0)),
            sp_context_source=p0.get("sp_context_source", ""),
            season_game_index=float(p0.get("season_game_index", 0.5)),
            home_win=int(float(hw)),
        ))
    print(f"[LOAD] total_raw={len(raw)} | after_dedup={len(seen)} | excluded_fallback={skip_fallback} | kept={len(recs)}")
    return recs


# ── WFV on covered subset ────────────────────────────────────────────────────────
def wfv_covered(covered: list[Rec]) -> dict:
    if len(covered) < MIN_SAMPLE_WFV:
        return {"skip": True, "n": len(covered)}
    sorted_c = sorted(covered, key=lambda r: r.game_date)
    cut = int(len(sorted_c) * 0.70)
    train, val = sorted_c[:cut], sorted_c[cut:]
    X_tr = [r.sp_fip_delta for r in train]
    y_tr = [r.home_win for r in train]
    X_va = [r.sp_fip_delta for r in val]
    y_va = [r.home_win for r in val]
    Xs_tr, mu, sd = standardize(X_tr)
    Xs_va = [(x - mu) / sd for x in X_va]
    w, b = train_logistic(Xs_tr, y_tr)
    preds = [sigmoid(w * xi + b) for xi in Xs_va]
    return {
        "skip": False,
        "n_train": len(train),
        "n_val": len(val),
        "auc": roc_auc(y_va, preds),
        "bs": brier_skill(y_va, preds),
        "ece": ece_val(y_va, preds),
        "ll": log_loss_val(y_va, preds),
        "hw_val": sum(y_va) / len(y_va),
        "w": w, "b": b,
        "train_start": sorted_c[0].game_date,
        "train_end": sorted_c[cut - 1].game_date,
        "val_start": sorted_c[cut].game_date,
        "val_end": sorted_c[-1].game_date,
    }


# ── Monthly stability per threshold ──────────────────────────────────────────────
def monthly_by_threshold(records: list[Rec]) -> dict[float, dict]:
    """Returns {threshold: {month: auc or 'SPARSE'}}"""
    result: dict = {}
    for T in THRESHOLDS:
        covered = [r for r in records if abs(r.sp_fip_delta) >= T]
        by_month: dict[str, list[Rec]] = collections.defaultdict(list)
        for r in covered:
            by_month[r.game_date[:7]].append(r)
        month_aucs = {}
        for month, recs in sorted(by_month.items()):
            if len(recs) < MIN_SAMPLE_MONTHLY:
                month_aucs[month] = f"SPARSE(n={len(recs)})"
            else:
                X = [r.sp_fip_delta for r in recs]
                y = [r.home_win for r in recs]
                month_aucs[month] = roc_auc(y, X)
        result[T] = month_aucs
    return result


# ── Season phase per threshold ───────────────────────────────────────────────────
def season_phase_by_threshold(records: list[Rec]) -> dict:
    phases = {
        "Early (0.00-0.33)": lambda r: r.season_game_index < 0.33,
        "Mid   (0.33-0.67)": lambda r: 0.33 <= r.season_game_index < 0.67,
        "Late  (0.67-1.00)": lambda r: r.season_game_index >= 0.67,
    }
    result = {}
    for T in THRESHOLDS:
        covered = [r for r in records if abs(r.sp_fip_delta) >= T]
        result[T] = {}
        for label, filt in phases.items():
            phase_recs = [r for r in covered if filt(r)]
            if len(phase_recs) < 20:
                result[T][label] = float("nan")
            else:
                X = [r.sp_fip_delta for r in phase_recs]
                y = [r.home_win for r in phase_recs]
                result[T][label] = roc_auc(y, X)
    return result


# ── Main ─────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 80)
    print("P37: sp_fip_delta Strong-Edge Threshold Optimization")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print(f"Grid: {THRESHOLDS}")
    print("=" * 80)

    records = load_records()
    total_n = len(records)
    overall_hw = sum(r.home_win for r in records) / total_n

    print(f"\n[DATA] n={total_n} | overall HW%={overall_hw:.4f}")

    # ─ SECTION 1: Threshold Grid ──────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 1: Threshold Grid — Coverage & Favored-Team Win Rates")
    print(f"{'='*80}")
    print(f"\n  {'T':>5}  {'n_cov':>6}  {'cov%':>5}  {'n_home':>7}  {'n_away':>7}  "
          f"{'HW%(H)':>7}  {'HW%(A)':>7}  {'favored':>8}  {'spread':>7}  {'lift':>6}  "
          f"{'AUC_cov':>8}")
    print("  " + "-" * 86)

    grid_metrics: dict[float, dict] = {}
    for T in THRESHOLDS:
        home_edge = [r for r in records if r.sp_fip_delta >= T]
        away_edge = [r for r in records if r.sp_fip_delta <= -T]
        covered = home_edge + away_edge

        n_cov = len(covered)
        cov_pct = 100 * n_cov / total_n
        hw_home = sum(r.home_win for r in home_edge) / max(1, len(home_edge))
        hw_away = sum(r.home_win for r in away_edge) / max(1, len(away_edge))
        favored = (hw_home + (1 - hw_away)) / 2   # win rate betting favored team
        spread = hw_home - hw_away
        lift = favored - overall_hw

        # AUC: raw sp_fip_delta as score on covered games
        X_cov = [r.sp_fip_delta for r in covered]
        y_cov = [r.home_win for r in covered]
        auc_cov = roc_auc(y_cov, X_cov) if n_cov >= 20 else float("nan")

        grid_metrics[T] = {
            "n_cov": n_cov, "cov_pct": cov_pct,
            "n_home": len(home_edge), "n_away": len(away_edge),
            "hw_home": hw_home, "hw_away": hw_away,
            "favored": favored, "spread": spread, "lift": lift,
            "auc_cov": auc_cov,
        }
        print(
            f"  {T:>5.2f}  {n_cov:>6}  {cov_pct:>5.1f}%"
            f"  {len(home_edge):>7}  {len(away_edge):>7}"
            f"  {hw_home:>7.3f}  {hw_away:>7.3f}"
            f"  {favored:>8.3f}  {spread:>7.3f}  {lift:>+6.3f}"
            f"  {auc_cov:>8.4f}"
        )

    # ─ SECTION 2: WFV on Covered Subset ──────────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 2: WFV (70/30) on Covered Subset — sp_fip_delta as logistic feature")
    print(f"{'='*80}")
    print(f"\n  {'T':>5}  {'n_tr':>6}  {'n_val':>6}  {'AUC':>7}  {'BrierSk':>9}  "
          f"{'ECE':>7}  {'LL':>7}  {'HW%(val)':>8}  note")
    print("  " + "-" * 80)

    wfv_results: dict[float, dict] = {}
    for T in THRESHOLDS:
        home_edge = [r for r in records if r.sp_fip_delta >= T]
        away_edge = [r for r in records if r.sp_fip_delta <= -T]
        covered = home_edge + away_edge
        res = wfv_covered(covered)
        wfv_results[T] = res

        if res.get("skip"):
            print(f"  {T:>5.2f}  [SKIPPED — n={res['n']} < {MIN_SAMPLE_WFV}]")
        else:
            note = "P36" if abs(T - 0.50) < 0.001 else ""
            print(
                f"  {T:>5.2f}  {res['n_train']:>6}  {res['n_val']:>6}"
                f"  {res['auc']:>7.4f}  {res['bs']:>+9.5f}"
                f"  {res['ece']:>7.4f}  {res['ll']:>7.4f}"
                f"  {res['hw_val']:>8.3f}  {note}"
            )

    # ─ SECTION 3: Monthly Stability ──────────────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 3: Monthly Stability by Threshold (AUC on covered games)")
    print(f"{'='*80}")
    monthly_data = monthly_by_threshold(records)

    all_months = sorted({m for T in THRESHOLDS for m in monthly_data[T]})
    header = f"  {'T':>5}  " + "  ".join(f"{m:>15}" for m in all_months)
    print(f"\n{header}")
    print("  " + "-" * (7 + 17 * len(all_months)))
    for T in THRESHOLDS:
        row = f"  {T:>5.2f}  "
        stable_count = 0
        valid_aucs = []
        for m in all_months:
            val = monthly_data[T].get(m, "—")
            if isinstance(val, float):
                row += f"  {val:>15.4f}"
                if val > 0.5:
                    stable_count += 1
                valid_aucs.append(val)
            else:
                row += f"  {str(val):>15}"
        mu = sum(valid_aucs) / len(valid_aucs) if valid_aucs else float("nan")
        sd = stddev(valid_aucs)
        pct_above = stable_count / len(valid_aucs) * 100 if valid_aucs else 0
        row += f"   mean={mu:.4f} std={sd:.4f} {pct_above:.0f}%>0.5"
        print(row)

    # ─ SECTION 4: Season Phase ───────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 4: Season Phase AUC by Threshold (raw score on covered games)")
    print(f"{'='*80}")
    phase_data = season_phase_by_threshold(records)
    phase_labels = ["Early (0.00-0.33)", "Mid   (0.33-0.67)", "Late  (0.67-1.00)"]

    print(f"\n  {'T':>5}  {'Early':>7}  {'Mid':>7}  {'Late':>7}  {'Range':>7}")
    print("  " + "-" * 44)
    for T in THRESHOLDS:
        pd = phase_data[T]
        e = pd.get("Early (0.00-0.33)", float("nan"))
        m = pd.get("Mid   (0.33-0.67)", float("nan"))
        la = pd.get("Late  (0.67-1.00)", float("nan"))
        vals = [v for v in [e, m, la] if not math.isnan(v)]
        rng = max(vals) - min(vals) if len(vals) >= 2 else float("nan")
        def fmt(v):
            return f"{v:.4f}" if not math.isnan(v) else "  nan "
        print(f"  {T:>5.2f}  {fmt(e):>7}  {fmt(m):>7}  {fmt(la):>7}  {fmt(rng):>7}")

    # ─ SECTION 5: Best Threshold Selection ───────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 5: Best Threshold Selection")
    print(f"{'='*80}")

    # Rank by: Brier Skill first (WFV), AUC second (WFV), coverage third
    candidates = []
    for T in THRESHOLDS:
        wfv = wfv_results[T]
        m_data = monthly_data[T]
        if wfv.get("skip"):
            continue
        valid_monthly = [v for v in m_data.values() if isinstance(v, float)]
        pct_stable = sum(1 for v in valid_monthly if v > 0.5) / len(valid_monthly) if valid_monthly else 0.0
        gm = grid_metrics[T]
        candidates.append({
            "T": T,
            "bs": wfv["bs"],
            "auc_wfv": wfv["auc"],
            "ece": wfv["ece"],
            "cov_pct": gm["cov_pct"],
            "n_cov": gm["n_cov"],
            "auc_cov": gm["auc_cov"],
            "favored": gm["favored"],
            "lift": gm["lift"],
            "spread": gm["spread"],
            "pct_stable": pct_stable,
        })

    # Sort: Brier Skill ↓ first, AUC_WFV ↓ second, coverage ↑ third
    ranked = sorted(candidates, key=lambda c: (-c["bs"], -c["auc_wfv"], c["T"]))

    print(f"\n  Ranked by (Brier Skill ↓, AUC_WFV ↓, threshold ↑):")
    print(f"  {'Rank':>4}  {'T':>5}  {'BrierSk':>9}  {'AUC_WFV':>8}  {'ECE':>7}  "
          f"{'cov%':>6}  {'favored':>8}  {'lift':>6}  {'stable%':>8}")
    print("  " + "-" * 78)
    for rank, c in enumerate(ranked, 1):
        marker = " ← BEST" if rank == 1 else (" ← P36" if abs(c["T"] - 0.50) < 0.001 else "")
        print(
            f"  {rank:>4}  {c['T']:>5.2f}  {c['bs']:>+9.5f}  {c['auc_wfv']:>8.4f}"
            f"  {c['ece']:>7.4f}  {c['cov_pct']:>5.1f}%  {c['favored']:>8.3f}"
            f"  {c['lift']:>+6.3f}  {c['pct_stable']:>7.0%}{marker}"
        )

    best = ranked[0] if ranked else None
    p36_entry = next((c for c in ranked if abs(c["T"] - 0.50) < 0.001), None)

    # ─ SECTION 6: Comparison vs P36 ──────────────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 6: Comparison vs P36 (T=0.50 baseline)")
    print(f"{'='*80}")

    if best and p36_entry:
        print(f"\n  P36 baseline (T=0.50):")
        print(f"    AUC_WFV  = {p36_entry['auc_wfv']:.4f}")
        print(f"    BrierSk  = {p36_entry['bs']:+.5f}")
        print(f"    ECE      = {p36_entry['ece']:.4f}")
        print(f"    Coverage = {p36_entry['cov_pct']:.1f}%  ({p36_entry['n_cov']} games)")
        print(f"    Favored  = {p36_entry['favored']:.3f}")
        print(f"    Lift     = {p36_entry['lift']:+.3f}")
        print(f"\n  Best threshold (T={best['T']:.2f}):")
        print(f"    AUC_WFV  = {best['auc_wfv']:.4f}  (Δ={best['auc_wfv']-p36_entry['auc_wfv']:+.4f})")
        print(f"    BrierSk  = {best['bs']:+.5f}  (Δ={best['bs']-p36_entry['bs']:+.5f})")
        print(f"    ECE      = {best['ece']:.4f}  (Δ={best['ece']-p36_entry['ece']:+.4f})")
        print(f"    Coverage = {best['cov_pct']:.1f}%  ({best['n_cov']} games, Δ={best['n_cov']-p36_entry['n_cov']:+d})")
        print(f"    Favored  = {best['favored']:.3f}  (Δ={best['favored']-p36_entry['favored']:+.3f})")
        print(f"    Lift     = {best['lift']:+.3f}  (Δ={best['lift']-p36_entry['lift']:+.3f})")

        delta_bs = best["bs"] - p36_entry["bs"]
        delta_auc = best["auc_wfv"] - p36_entry["auc_wfv"]
        if delta_bs > 0.002 and best["cov_pct"] >= p36_entry["cov_pct"] * 0.50:
            outcome = "IMPROVED — new threshold recommended"
        elif delta_bs > 0.001:
            outcome = "MARGINAL IMPROVEMENT — verify on holdout"
        elif abs(delta_bs) <= 0.001 and abs(delta_auc) <= 0.003:
            outcome = "EQUIVALENT — P36 threshold (0.50) is robust"
        else:
            outcome = "P36 REMAINS BEST — threshold=0.50 validated"
        print(f"\n  Outcome: {outcome}")

    # ─ SECTION 7: Signal Classification ──────────────────────────────────────
    print(f"\n{'='*80}")
    print("SECTION 7: Signal Classification")
    print(f"{'='*80}")

    if best:
        auc_b = best["auc_wfv"]
        bs_b  = best["bs"]
        st_b  = best["pct_stable"]
        cov_b = best["cov_pct"]

        if auc_b >= 0.550 and bs_b > 0.005 and st_b >= 0.80 and cov_b >= 20:
            cls = "THRESHOLD_OPTIMIZED_DIAGNOSTIC"
            rec = "Eligible for OOS holdout test on 2024 MLB data."
        elif auc_b >= 0.530 and bs_b > 0.002 and st_b >= 0.70:
            cls = "STABLE_DIAGNOSTIC_SIGNAL"
            rec = "Strong-edge filter confirmed. Proceed to P38 holdout validation."
        elif auc_b >= 0.515 and st_b >= 0.50:
            cls = "WEAK_SIGNAL"
            rec = "Marginal. Collect more current-season FIP data before escalating."
        else:
            cls = "NOISE"
            rec = "Signal not reproducible under threshold optimization."

        cls += " | PROMOTION_BLOCKED_BY_GOVERNANCE"

        print(f"\n  Best T        = {best['T']:.2f}")
        print(f"  AUC_WFV       = {auc_b:.4f}")
        print(f"  Brier Skill   = {bs_b:+.5f}")
        print(f"  Monthly stable= {st_b:.0%}")
        print(f"  Coverage      = {cov_b:.1f}%")
        print(f"\n  Classification: {cls}")
        print(f"  Recommendation: {rec}")

    # ─ Governance Footer ──────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("GOVERNANCE")
    print(f"{'='*80}")
    print(f"  diagnostic_only   = {DIAGNOSTIC_ONLY}")
    print(f"  promotion_freeze  = {PROMOTION_FREEZE}")
    print(f"  Champion strategy = UNMODIFIED")
    print(f"  Kelly/bet logic   = UNMODIFIED")
    print(f"\n{'='*80}")
    print("P37 COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
