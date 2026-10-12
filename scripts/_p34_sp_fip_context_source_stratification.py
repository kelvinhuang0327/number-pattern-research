"""
P34: SP FIP Context Source Stratification
diagnostic_only=True | promotion_freeze=True

Goal: Stratify sp_fip_delta AUC by sp_context_source tier
Tiers: league_average_fallback | historical_proxy | mixed

Sources:
  phase56: data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
           → p0_features: sp_fip_delta, sp_context_source
           → home_win (actual outcome, already in backtest record)
"""
from __future__ import annotations
import json, math, collections
from typing import NamedTuple

# ── Governance ────────────────────────────────────────────────────────────────
DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True
PHASE56 = "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"

# ── Math primitives (pure Python, no sklearn) ─────────────────────────────────
def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)

def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    """Wilcoxon–Mann–Whitney AUC."""
    pos = [s for y, s in zip(y_true, y_score) if y == 1]
    neg = [s for y, s in zip(y_true, y_score) if y == 0]
    if not pos or not neg:
        return float("nan")
    n_concordant = sum(p > n for p in pos for n in neg)
    n_tied = sum(p == n for p in pos for n in neg)
    return (n_concordant + 0.5 * n_tied) / (len(pos) * len(neg))

def brier(y: list[int], p: list[float]) -> float:
    return sum((yi - pi) ** 2 for yi, pi in zip(y, p)) / len(y)

def log_loss(y: list[int], p: list[float]) -> float:
    eps = 1e-9
    return -sum(yi * math.log(pi + eps) + (1 - yi) * math.log(1 - pi + eps)
                for yi, pi in zip(y, p)) / len(y)

def brier_skill(y: list[int], p: list[float]) -> float:
    base_rate = sum(y) / len(y)
    bs_model = brier(y, p)
    bs_naive = brier(y, [base_rate] * len(y))
    return 1 - bs_model / bs_naive if bs_naive > 0 else 0.0

def log_loss_skill(y: list[int], p: list[float]) -> float:
    base_rate = sum(y) / len(y)
    ll_model = log_loss(y, p)
    eps = 1e-9
    ll_naive = -(base_rate * math.log(base_rate + eps) +
                 (1 - base_rate) * math.log(1 - base_rate + eps))
    return 1 - ll_model / ll_naive if ll_naive > 0 else 0.0

def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return float("nan")
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((ai - ma) * (bi - mb) for ai, bi in zip(a, b))
    da = math.sqrt(sum((ai - ma) ** 2 for ai in a))
    db = math.sqrt(sum((bi - mb) ** 2 for bi in b))
    return num / (da * db) if da > 0 and db > 0 else 0.0

def train_logistic_1d(X: list[float], y: list[int],
                      lr: float = 0.05, epochs: int = 600) -> tuple[float, float]:
    """Gradient descent logistic regression (1D feature, returns w, b)."""
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

def standardize_1d(X: list[float]) -> tuple[list[float], float, float]:
    n = len(X)
    mu = sum(X) / n
    var = sum((xi - mu) ** 2 for xi in X) / n
    sd = math.sqrt(var) if var > 0 else 1.0
    return [(xi - mu) / sd for xi in X], mu, sd

# ── Data structures ───────────────────────────────────────────────────────────
class GameRow(NamedTuple):
    game_date: str
    home_team: str
    sp_fip_delta: float
    sp_context_source: str
    home_win: int

# ── Load phase56 ─────────────────────────────────────────────────────────────
def load_phase56() -> list[GameRow]:
    rows = []
    skipped = 0
    for line in open(PHASE56):
        r = json.loads(line)
        p0 = r.get("p0_features", {})
        hw = r.get("home_win")
        fip = p0.get("sp_fip_delta")
        src = p0.get("sp_context_source")
        if hw is None or fip is None or src is None:
            skipped += 1
            continue
        rows.append(GameRow(
            game_date=r["game_date"],
            home_team=r["home_team"],
            sp_fip_delta=float(fip),
            sp_context_source=str(src),
            home_win=int(hw),
        ))
    rows.sort(key=lambda r: r.game_date)
    print(f"[PHASE56] Loaded {len(rows)} rows | Skipped {skipped}")
    return rows

# ── Walk-forward split (70/30 time-ordered) ──────────────────────────────────
def wfv_split(rows: list[GameRow], train_frac: float = 0.70):
    cutoff = int(len(rows) * train_frac)
    return rows[:cutoff], rows[cutoff:]

# ── Tier analysis ─────────────────────────────────────────────────────────────
def analyze_tier(name: str, train: list[GameRow], val: list[GameRow]) -> dict:
    """Run WFV for a single context source tier."""
    result = {
        "tier": name,
        "n_train": len(train),
        "n_val": len(val),
        "classification": "DATA_INSUFFICIENT",
    }

    if len(val) < 30:
        result["note"] = f"Insufficient val samples ({len(val)} < 30)"
        return result

    X_train = [r.sp_fip_delta for r in train]
    y_train = [r.home_win for r in train]
    X_val = [r.sp_fip_delta for r in val]
    y_val = [r.home_win for r in val]

    # Check if feature is constant
    fip_std = math.sqrt(sum((xi - sum(X_train)/len(X_train))**2 for xi in X_train) / len(X_train)) if X_train else 0
    if fip_std < 1e-9:
        # Constant feature — base rate predictions only
        base_rate = sum(y_val) / len(y_val)
        preds = [base_rate] * len(y_val)
        result["auc"] = 0.500
        result["brier_skill"] = 0.000
        result["ll_skill"] = 0.000
        result["coefficient"] = 0.0
        result["intercept"] = 0.0
        result["home_win_rate_val"] = base_rate
        result["note"] = "CONSTANT FEATURE (std=0) — trivially AUC=0.500"
        result["classification"] = "NOISE"
        return result

    # Standardize
    Xs_train, mu, sd = standardize_1d(X_train)
    Xs_val = [(xi - mu) / sd for xi in X_val]

    # Train
    w, b = train_logistic_1d(Xs_train, y_train)
    preds = [sigmoid(w * xi + b) for xi in Xs_val]

    auc = roc_auc(y_val, preds)
    bs = brier_skill(y_val, preds)
    ls = log_loss_skill(y_val, preds)
    pr = pearson(X_train, y_train)
    hw_rate = sum(y_val) / len(y_val)

    result["auc"] = round(auc, 4)
    result["brier_skill"] = round(bs, 4)
    result["ll_skill"] = round(ls, 4)
    result["coefficient_standardized"] = round(w, 4)
    result["coefficient_raw_scale"] = round(w / sd, 4) if sd > 0 else 0.0
    result["intercept"] = round(b, 4)
    result["pearson_r_train"] = round(pr, 4)
    result["home_win_rate_val"] = round(hw_rate, 4)
    result["feature_std_train"] = round(fip_std, 4)

    # Classify
    if auc >= 0.540 and bs > 0:
        result["classification"] = "STABLE_DIAGNOSTIC_SIGNAL"
    elif auc >= 0.510:
        result["classification"] = "WEAK_SIGNAL"
    else:
        result["classification"] = "NOISE"
    return result

# ── Monthly stability ─────────────────────────────────────────────────────────
def monthly_stability(rows: list[GameRow]) -> None:
    """Compute per-month AUC for sp_fip_delta vs home_win."""
    by_month = collections.defaultdict(list)
    for r in rows:
        month = r.game_date[:7]
        by_month[month].append(r)

    print(f"\n{'Month':10s} {'n':>5s} {'AUC':>7s} {'Pearson r':>10s} {'hw%':>7s}")
    print("  " + "-" * 48)
    aucs = []
    for month in sorted(by_month):
        mrs = by_month[month]
        if len(mrs) < 10:
            continue
        X = [r.sp_fip_delta for r in mrs]
        y = [r.home_win for r in mrs]
        fstd = math.sqrt(sum((xi - sum(X)/len(X))**2 for xi in X) / len(X))
        if fstd < 1e-9:
            auc = 0.500
        else:
            auc = roc_auc(y, X)  # raw feature as score (rank-based, sufficient for AUC)
        pr = pearson(X, y)
        hw = sum(y) / len(y)
        aucs.append(auc)
        print(f"  {month:10s} {len(mrs):5d}  {auc:.4f}   {pr:+.4f}   {hw:.1%}")

    if aucs:
        mean_auc = sum(aucs) / len(aucs)
        import math as _m
        std_auc = _m.sqrt(sum((a - mean_auc)**2 for a in aucs) / len(aucs))
        above = sum(1 for a in aucs if a > 0.500)
        print(f"\n  Monthly AUC: mean={mean_auc:.4f}, std={std_auc:.4f}, above-0.5 rate={above}/{len(aucs)} ({above/len(aucs):.0%})")
        verdict = "STABLE" if above / len(aucs) >= 0.70 else "UNSTABLE"
        print(f"  Stability verdict: {verdict}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 72)
    print("P34: SP FIP Context Source Stratification")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print("=" * 72)

    all_rows = load_phase56()

    # Distribution
    src_dist = collections.Counter(r.sp_context_source for r in all_rows)
    print(f"\n[sp_context_source DISTRIBUTION]")
    for k, v in sorted(src_dist.items(), key=lambda x: -x[1]):
        print(f"  {k:40s}: {v:5d} ({v/len(all_rows)*100:.1f}%)")

    # All-sample baseline (matches P33 individual WFV)
    print(f"\n[ALL-SAMPLE BASELINE — {len(all_rows)} rows]")
    train_all, val_all = wfv_split(all_rows)
    print(f"  Train: {len(train_all)} | Val: {len(val_all)}")
    res_all = analyze_tier("ALL_SAMPLE_BASELINE", train_all, val_all)
    print(f"  AUC={res_all.get('auc', 'N/A')} | Brier Skill={res_all.get('brier_skill', 'N/A')} | Classification={res_all['classification']}")

    # Tier-level analysis
    TIERS = sorted(src_dist.keys())
    tier_results = {}
    print(f"\n{'='*72}")
    print("SECTION 1: Tier-Level WFV Results")
    print(f"{'='*72}")
    print(f"\n{'Tier':40s} {'n_train':>8s} {'n_val':>7s} {'AUC':>7s} {'BrierSk':>9s} {'LLSk':>7s} {'PearsonR':>9s} {'Class':>25s}")
    print("  " + "-" * 120)

    for tier in TIERS:
        tier_rows = [r for r in all_rows if r.sp_context_source == tier]
        tr, va = wfv_split(tier_rows)
        res = analyze_tier(tier, tr, va)
        tier_results[tier] = res

        auc_str = f"{res.get('auc', 'N/A'):.4f}" if isinstance(res.get('auc'), float) else "N/A"
        bs_str = f"{res.get('brier_skill', 'N/A'):+.4f}" if isinstance(res.get('brier_skill'), float) else "N/A"
        ls_str = f"{res.get('ll_skill', 'N/A'):+.4f}" if isinstance(res.get('ll_skill'), float) else "N/A"
        pr_str = f"{res.get('pearson_r_train', 'N/A'):+.4f}" if isinstance(res.get('pearson_r_train'), float) else "N/A"
        print(f"  {tier:40s} {res['n_train']:8d} {res['n_val']:7d} {auc_str:>7s} {bs_str:>9s} {ls_str:>7s} {pr_str:>9s} {res['classification']:>25s}")
        if "note" in res:
            print(f"    note: {res['note']}")

    # Detailed tier report
    print(f"\n{'='*72}")
    print("SECTION 2: Tier Detail Report")
    print(f"{'='*72}")
    for tier, res in tier_results.items():
        print(f"\n  --- {tier} ---")
        for k, v in res.items():
            if k != "tier":
                print(f"    {k:35s}: {v}")

    # Monthly stability (run on each tier with enough samples)
    print(f"\n{'='*72}")
    print("SECTION 3: Monthly Stability by Tier")
    print(f"{'='*72}")
    for tier in TIERS:
        tier_rows = [r for r in all_rows if r.sp_context_source == tier]
        fstd_check = math.sqrt(
            sum((r.sp_fip_delta - sum(rr.sp_fip_delta for rr in tier_rows)/len(tier_rows))**2
                for r in tier_rows) / len(tier_rows)
        ) if tier_rows else 0
        print(f"\n  Tier: {tier} (n={len(tier_rows)}, fip_std={fstd_check:.4f})")
        if fstd_check < 1e-9:
            print("  SKIP: constant feature")
            continue
        monthly_stability(tier_rows)

    # Comparison vs P33 baseline
    print(f"\n{'='*72}")
    print("SECTION 4: Comparison vs P33 All-Sample Baseline")
    print(f"{'='*72}")
    p33_baseline_auc = 0.5219  # P33 Section 1, sp_fip_delta individual
    print(f"\n  P33 all-sample baseline AUC: {p33_baseline_auc:.4f}")
    print(f"  P34 all-sample (phase56 own home_win): {res_all.get('auc', 'N/A')}")
    print(f"\n  Tier vs P33 Baseline:")
    print(f"  {'Tier':40s} {'AUC':>7s} {'Δ vs P33':>10s}")
    print("  " + "-" * 60)
    for tier, res in tier_results.items():
        auc = res.get("auc", float("nan"))
        if isinstance(auc, float) and not math.isnan(auc):
            delta = auc - p33_baseline_auc
            note = "▲" if delta > 0.005 else ("▼" if delta < -0.005 else "≈")
            print(f"  {tier:40s} {auc:.4f}   {delta:+.4f} {note}")
        else:
            print(f"  {tier:40s} N/A")

    # Signal classification summary
    print(f"\n{'='*72}")
    print("SECTION 5: Signal Classification Summary")
    print(f"{'='*72}")
    print(f"\n  {'Tier':40s} {'Classification':30s} {'AUC':>7s}")
    print("  " + "-" * 80)
    for tier, res in tier_results.items():
        auc = res.get("auc")
        auc_str = f"{auc:.4f}" if isinstance(auc, float) else "N/A"
        print(f"  {tier:40s} {res['classification']:30s} {auc_str:>7s}")

    # Governance
    print(f"\n{'='*72}")
    print("GOVERNANCE")
    print(f"{'='*72}")
    print(f"  diagnostic_only   = {DIAGNOSTIC_ONLY}")
    print(f"  promotion_freeze  = {PROMOTION_FREEZE}")
    print(f"  Champion strategy = UNMODIFIED")
    print(f"  Kelly/bet logic   = UNMODIFIED")
    print(f"\n{'='*72}")
    print("P34 COMPLETE")
    print(f"{'='*72}")

if __name__ == "__main__":
    main()
