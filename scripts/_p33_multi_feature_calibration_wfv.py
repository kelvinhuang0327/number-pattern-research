"""
P33: MLB Bullpen Multi-Feature WFV + Calibration
diagnostic_only=True | promotion_freeze=True

Three-way join:
  phase56 derived  (sp_fip_delta, park_run_factor)  — keyed by game_date + home_team
  bullpen_usage_3d.jsonl (bullpen_usage_diff)         — keyed by game_id → date + home_display
  mlb-2025-asplayed.csv  (home_win outcome)           — keyed by date + home_team

Tasks:
  1. Multi-feature logistic regression (3-feature vs individual)
  2. Pearson correlation / multicollinearity check
  3. Calibration audit: ECE + reliability diagram (10 bins, text-based)
  4. Platt scaling diagnostic (in-sample upper bound, clearly labelled)
  5. Signal stability: bullpen_usage_diff AUC by calendar month
"""

from __future__ import annotations
import csv, json, math, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIAGNOSTIC_ONLY   = True
PROMOTION_FREEZE  = True
assert DIAGNOSTIC_ONLY,  "GOVERNANCE: diagnostic_only must be True"
assert PROMOTION_FREEZE, "GOVERNANCE: promotion_freeze must be True"

PHASE56_PATH = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
BP_PATH      = ROOT / "data/mlb_context/bullpen_usage_3d.jsonl"
PLAYED_PATH  = ROOT / "data/mlb_2025/mlb-2025-asplayed.csv"

# ── Team normalization (reused from P32) ──────────────────────────────────────
TEAM_OVERRIDES = {
    "ST_LOUIS_CARDINALS": "St. Louis Cardinals",
    "ST_LOUIS_BROWNS":    "St. Louis Browns",
}

def canon_to_display(raw: str) -> str:
    if raw in TEAM_OVERRIDES:
        return TEAM_OVERRIDES[raw]
    return " ".join(w.capitalize() for w in raw.split("_"))


_GID_RE = re.compile(r"MLB-(\d{4})_(\d{2})_(\d{2})-.*-AT-(.+)$")

def parse_gid(gid: str) -> tuple[str | None, str | None]:
    """Returns (iso_date, home_display) or (None, None)."""
    m = _GID_RE.match(gid)
    if not m:
        return None, None
    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return date, canon_to_display(m.group(4))


# ── Data loading ──────────────────────────────────────────────────────────────
def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_asplayed(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── Math helpers ──────────────────────────────────────────────────────────────
def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, x))))


def standardize(X: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    """Standardize each column (feature) across rows. Returns (Xs, means, stds)."""
    n, d = len(X), len(X[0])
    means = [sum(X[i][j] for i in range(n)) / n for j in range(d)]
    stds  = [
        math.sqrt(sum((X[i][j] - means[j]) ** 2 for i in range(n)) / n) or 1.0
        for j in range(d)
    ]
    Xs = [[(X[i][j] - means[j]) / stds[j] for j in range(d)] for i in range(n)]
    return Xs, means, stds


def train_logistic_nd(
    X: list[list[float]], y: list[int],
    lr: float = 0.05, epochs: int = 800,
) -> tuple[list[float], float, list[float], list[float]]:
    """Multi-feature logistic regression. Returns (w_raw, b_raw, means, stds)."""
    if not X:
        return [], 0.0, [], []
    Xs, means, stds = standardize(X)
    d   = len(X[0])
    n   = len(X)
    w   = [0.0] * d
    b   = 0.0
    for _ in range(epochs):
        dw = [0.0] * d
        db = 0.0
        for xi, yi in zip(Xs, y):
            p  = sigmoid(sum(w[j] * xi[j] for j in range(d)) + b)
            e  = p - yi
            for j in range(d):
                dw[j] += e * xi[j]
            db += e
        w = [w[j] - lr * dw[j] / n for j in range(d)]
        b = b - lr * db / n
    # Convert back to raw-scale weights
    w_raw = [w[j] / stds[j] for j in range(d)]
    b_raw = b - sum(w[j] * means[j] / stds[j] for j in range(d))
    return w_raw, b_raw, means, stds


def train_logistic_1d(X: list[float], y: list[int], lr: float = 0.05, epochs: int = 600) -> tuple[float, float]:
    n = len(X)
    if not n:
        return 0.0, 0.0
    mu  = sum(X) / n
    std = math.sqrt(sum((v - mu) ** 2 for v in X) / n) or 1.0
    Xs  = [(v - mu) / std for v in X]
    w, b = 0.0, 0.0
    for _ in range(epochs):
        dw = db = 0.0
        for xi, yi in zip(Xs, y):
            p = sigmoid(w * xi + b)
            e = p - yi
            dw += e * xi
            db += e
        w -= lr * dw / n
        b -= lr * db / n
    return w / std, b - w * mu / std


def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    pos = [s for s, y in zip(y_score, y_true) if y == 1]
    neg = [s for s, y in zip(y_score, y_true) if y == 0]
    if not pos or not neg:
        return float("nan")
    concordant = sum(1 for p in pos for n in neg if p > n)
    tied       = sum(0.5 for p in pos for n in neg if p == n)
    return (concordant + tied) / (len(pos) * len(neg))


def brier(y: list[int], p: list[float]) -> float:
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(y)


def log_loss(y: list[int], p: list[float]) -> float:
    def clip(v: float) -> float:
        return max(1e-7, min(1 - 1e-7, v))
    return -sum(
        yi * math.log(clip(pi)) + (1 - yi) * math.log(1 - clip(pi))
        for pi, yi in zip(p, y)
    ) / len(y)


def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return float("nan")
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((ai - ma) * (bi - mb) for ai, bi in zip(a, b))
    da  = math.sqrt(sum((ai - ma) ** 2 for ai in a))
    db  = math.sqrt(sum((bi - mb) ** 2 for bi in b))
    if da == 0 or db == 0:
        return float("nan")
    return num / (da * db)


def ece(y: list[int], p: list[float], n_bins: int = 10) -> float:
    """Expected Calibration Error."""
    bins: list[list] = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((yi, pi))
    total = len(y)
    err = 0.0
    for b_items in bins:
        if not b_items:
            continue
        avg_conf = sum(pi for _, pi in b_items) / len(b_items)
        avg_acc  = sum(yi for yi, _ in b_items) / len(b_items)
        err += (len(b_items) / total) * abs(avg_acc - avg_conf)
    return err


def reliability_diagram_text(y: list[int], p: list[float], n_bins: int = 10) -> str:
    """Text-based reliability diagram."""
    bins: list[list] = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((yi, pi))
    lines = ["Reliability Diagram (n=10 bins, ideal: accuracy ≈ confidence)"]
    lines.append(f"  {'Bin':>4}  {'Conf':>6}  {'Acc':>6}  {'n':>5}  {'Bar'}")
    lines.append("  " + "-" * 55)
    for i, b_items in enumerate(bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        if not b_items:
            lines.append(f"  [{lo:.1f}-{hi:.1f}]  {'--':>6}  {'--':>6}  {0:>5}")
            continue
        avg_conf = sum(pi for _, pi in b_items) / len(b_items)
        avg_acc  = sum(yi for yi, _ in b_items) / len(b_items)
        bar_len  = int(avg_acc * 30)
        ideal_len= int(avg_conf * 30)
        bar = "█" * bar_len + ("·" * max(0, ideal_len - bar_len) if ideal_len > bar_len else "")
        overconf_mark = " ▲OVERCONF" if avg_conf - avg_acc > 0.05 else ""
        underconf_mark = " ▼UNDERCONF" if avg_acc - avg_conf > 0.05 else ""
        lines.append(
            f"  [{lo:.1f}-{hi:.1f}]  {avg_conf:6.3f}  {avg_acc:6.3f}  {len(b_items):>5}  |{bar}{overconf_mark}{underconf_mark}"
        )
    return "\n".join(lines)


def platt_scale(y_val: list[int], scores_val: list[float]) -> tuple[float, float]:
    """Fit a 1-D logistic (Platt scaling) on raw scores → calibrated probs.
    In-sample on val set — upper-bound diagnostic only."""
    return train_logistic_1d(scores_val, y_val)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 72)
    print("P33: MLB Bullpen Multi-Feature WFV + Calibration")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print("=" * 72)

    # ── Load sources
    phase56_rows = load_jsonl(PHASE56_PATH)
    bp_rows      = load_jsonl(BP_PATH)
    asplayed     = load_asplayed(PLAYED_PATH)

    print(f"\n[PRE-FLIGHT]")
    print(f"  phase56 rows : {len(phase56_rows)}")
    print(f"  BP rows      : {len(bp_rows)}")
    print(f"  Asplayed rows: {len(asplayed)}")

    # ── Build phase56 lookup {(game_date, home_team) → {sp_fip_delta, park_run_factor}}
    p56_lookup: dict[tuple, dict] = {}
    p56_skip = 0
    for r in phase56_rows:
        gd  = r.get("game_date", "")
        ht  = r.get("home_team", "")
        if not gd or not ht:
            p56_skip += 1
            continue
        key = (gd, ht)
        p0  = r.get("p0_features", {})
        if key not in p56_lookup:
            p56_lookup[key] = {
                "sp_fip_delta":   p0.get("sp_fip_delta"),
                "park_run_factor": p0.get("park_run_factor"),
            }
    print(f"\n[PHASE56 LOOKUP] {len(p56_lookup)} keys built (skipped: {p56_skip})")

    # ── Build BP lookup {(date, home_display) → bullpen_usage_diff}
    bp_lookup: dict[tuple, float | None] = {}
    for r in bp_rows:
        date, home = parse_gid(r["game_id"])
        if not date:
            continue
        key = (date, home)
        bph = r.get("bullpen_usage_last_3d_home")
        bpa = r.get("bullpen_usage_last_3d_away")
        if key not in bp_lookup:
            bp_lookup[key] = (bph - bpa) if (bph is not None and bpa is not None) else None
    print(f"[BP LOOKUP]     {len(bp_lookup)} keys built")

    # ── Three-way join on asplayed
    joined: list[dict] = []
    for row in asplayed:
        date = row.get("date", "")
        home = row.get("home_team", "")
        if row.get("status") != "Final" or not date or not home:
            continue
        try:
            hw = int(float(row["home_win"]))
        except (ValueError, TypeError, KeyError):
            continue

        p56 = p56_lookup.get((date, home), {})
        bp_diff = bp_lookup.get((date, home))

        joined.append({
            "date":             date,
            "home_team":        home,
            "home_win":         hw,
            "sp_fip_delta":     p56.get("sp_fip_delta"),
            "park_run_factor":  p56.get("park_run_factor"),
            "bullpen_usage_diff": bp_diff,
        })

    joined.sort(key=lambda r: r["date"])
    split_idx  = int(len(joined) * 0.70)
    split_date = joined[split_idx]["date"] if joined else "?"

    print(f"\n[JOIN]")
    print(f"  Total joined : {len(joined)}")
    for feat in ["sp_fip_delta", "park_run_factor", "bullpen_usage_diff"]:
        n = sum(1 for r in joined if r.get(feat) is not None)
        print(f"  {feat}: {n}/{len(joined)} ({100*n//max(len(joined),1)}%)")

    print(f"\n[WALK-FORWARD SPLIT]")
    print(f"  Train (70%) : {split_idx} rows | {joined[0]['date']} → {joined[split_idx-1]['date']}")
    print(f"  Val   (30%) : {len(joined)-split_idx} rows | {split_date} → {joined[-1]['date']}")

    train = joined[:split_idx]
    val   = joined[split_idx:]

    # ── Helper: extract 1D feature
    def extract_1d(rows: list[dict], feat: str) -> tuple[list[float], list[int]]:
        X, y = [], []
        for r in rows:
            v = r.get(feat)
            if v is not None:
                X.append(float(v))
                y.append(r["home_win"])
        return X, y

    # ── Helper: extract multi-feature (rows where ALL feats non-null)
    def extract_nd(rows: list[dict], feats: list[str]) -> tuple[list[list[float]], list[int]]:
        X, y = [], []
        for r in rows:
            vals = [r.get(f) for f in feats]
            if all(v is not None for v in vals):
                X.append([float(v) for v in vals])
                y.append(r["home_win"])
        return X, y

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 1: Individual feature AUC (trained on train, evaluated on val)
    # ─────────────────────────────────────────────────────────────────────────
    FEATURES_1D = ["sp_fip_delta", "park_run_factor", "bullpen_usage_diff"]
    P31B_INDIVIDUAL = {
        "sp_fip_delta":   {"auc": 0.511, "brier_skill": -0.0046, "class": "WEAK_SIGNAL"},
        "park_run_factor": {"auc": 0.513, "brier_skill": +0.0013, "class": "WEAK_SIGNAL"},
        "bullpen_usage_diff": {"auc": 0.529, "brier_skill": -0.0004, "class": "WEAK_SIGNAL"},  # P32
    }

    print(f"\n{'='*72}")
    print("SECTION 1: Individual Feature WFV (train → val)")
    print(f"{'='*72}")
    individual_results: dict[str, dict] = {}
    for feat in FEATURES_1D:
        X_tr, y_tr = extract_1d(train, feat)
        X_vl, y_vl = extract_1d(val, feat)
        if len(X_tr) < 20 or len(X_vl) < 10:
            print(f"{feat}: UNAVAILABLE (n_train={len(X_tr)}, n_val={len(X_vl)})")
            continue
        w, b       = train_logistic_1d(X_tr, y_tr)
        y_prob_vl  = [sigmoid(w * x + b) for x in X_vl]
        auc_v      = roc_auc(y_vl, y_prob_vl)
        br_v       = brier(y_vl, y_prob_vl)
        base       = sum(y_vl) / len(y_vl)
        br_base    = brier(y_vl, [base] * len(y_vl))
        br_skill   = 1 - br_v / br_base
        individual_results[feat] = {
            "auc": round(auc_v, 4), "brier_skill": round(br_skill, 4),
            "w": round(w, 6), "b": round(b, 6),
            "n_train": len(X_tr), "n_val": len(X_vl), "base": round(base, 4),
            "y_prob": y_prob_vl, "y_true": y_vl,
        }
        print(f"  {feat:<28} AUC={auc_v:.4f} | Brier Skill={br_skill:+.4f} | n_val={len(X_vl)}")

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 2: Pearson correlations (multicollinearity)
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("SECTION 2: Pearson Correlations (Multicollinearity Check)")
    print(f"{'='*72}")

    # Build complete rows (all 3 features + outcome)
    X_all, y_all = extract_nd(joined, FEATURES_1D)
    if X_all:
        fip_col  = [r[0] for r in X_all]
        park_col = [r[1] for r in X_all]
        bp_col   = [r[2] for r in X_all]

        print(f"  n_complete_rows (all 3 features): {len(X_all)}")
        print(f"\n  Feature vs Feature Pearson r:")
        pairs = [
            ("sp_fip_delta", "park_run_factor", fip_col, park_col),
            ("sp_fip_delta", "bullpen_usage_diff", fip_col, bp_col),
            ("park_run_factor", "bullpen_usage_diff", park_col, bp_col),
        ]
        max_r = 0.0
        for n1, n2, c1, c2 in pairs:
            r = pearson(c1, c2)
            flag = " ← HIGH COLLINEARITY" if abs(r) > 0.5 else ""
            print(f"    {n1:<28} vs {n2:<28} r={r:+.4f}{flag}")
            max_r = max(max_r, abs(r))

        print(f"\n  Feature vs home_win Pearson r:")
        for feat, col in [("sp_fip_delta", fip_col), ("park_run_factor", park_col), ("bullpen_usage_diff", bp_col)]:
            r = pearson(col, [float(yi) for yi in y_all])
            print(f"    {feat:<28} r={r:+.4f}")

        if max_r < 0.4:
            print(f"\n  VERDICT: No collinearity concern (max inter-feature |r|={max_r:.3f} < 0.4)")
        elif max_r < 0.6:
            print(f"\n  VERDICT: Mild collinearity (max |r|={max_r:.3f}); monitor")
        else:
            print(f"\n  VERDICT: HIGH COLLINEARITY DETECTED (max |r|={max_r:.3f}); multi-feature model unreliable")

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 3: Multi-feature model (3D LR)
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("SECTION 3: Multi-Feature Logistic Regression (3 features combined)")
    print(f"{'='*72}")

    X_tr_3, y_tr_3 = extract_nd(train, FEATURES_1D)
    X_vl_3, y_vl_3 = extract_nd(val, FEATURES_1D)
    print(f"  n_train (complete): {len(X_tr_3)} | n_val (complete): {len(X_vl_3)}")

    multi_probs: list[float] = []
    multi_auc = multi_bs = 0.0
    if len(X_tr_3) >= 20 and len(X_vl_3) >= 10:
        w3, b3, _, _ = train_logistic_nd(X_tr_3, y_tr_3)
        multi_probs = [sigmoid(sum(w3[j] * x[j] for j in range(len(w3))) + b3) for x in X_vl_3]
        multi_auc   = roc_auc(y_vl_3, multi_probs)
        br_v        = brier(y_vl_3, multi_probs)
        ll_v        = log_loss(y_vl_3, multi_probs)
        base        = sum(y_vl_3) / len(y_vl_3)
        br_base     = brier(y_vl_3, [base] * len(y_vl_3))
        ll_base     = log_loss(y_vl_3, [base] * len(y_vl_3))
        multi_bs    = round(1 - br_v / br_base, 4)
        ll_skill    = round(1 - ll_v / ll_base, 4)

        print(f"\n  Multi-feature result:")
        print(f"    AUC        = {multi_auc:.4f}")
        print(f"    Brier Skill= {multi_bs:+.4f}")
        print(f"    LL Skill   = {ll_skill:+.4f}")
        print(f"    Coefficients: {dict(zip(FEATURES_1D, [round(w,6) for w in w3]))}")
        print(f"    Intercept: {b3:.6f}")

        print(f"\n  Individual vs Multi-Feature comparison:")
        print(f"  {'Feature / Model':<35} {'AUC':>7}  {'Brier Skill':>12}")
        print(f"  {'-'*57}")
        for feat in FEATURES_1D:
            ir = individual_results.get(feat, {})
            print(f"  {feat:<35} {str(ir.get('auc','-')):>7}  {str(ir.get('brier_skill','-')):>12}")
        print(f"  {'multi_feature (all 3 combined)':<35} {multi_auc:.4f}  {multi_bs:>12}")

        # Classify multi-feature
        if multi_auc > 0.55 and multi_bs > 0.01:
            cls = "PROMISING_DIAGNOSTIC"
        elif multi_auc > 0.53 and multi_bs > 0.005:
            cls = "PROMISING_DIAGNOSTIC"
        elif multi_auc > 0.51 or multi_bs > 0.002:
            cls = "WEAK_SIGNAL"
        else:
            cls = "NOISE"
        print(f"\n  Multi-feature Classification: {cls}")

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 4: Calibration Audit
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("SECTION 4: Calibration Audit (multi-feature model on val set)")
    print(f"{'='*72}")

    if multi_probs and y_vl_3:
        base_probs = [sum(y_vl_3) / len(y_vl_3)] * len(y_vl_3)

        ece_base  = ece(y_vl_3, base_probs)
        ece_model = ece(y_vl_3, multi_probs)
        print(f"\n  ECE (naive base rate model): {ece_base:.4f}")
        print(f"  ECE (multi-feature model)  : {ece_model:.4f}")

        print(f"\n  {reliability_diagram_text(y_vl_3, multi_probs)}")

        # Platt scaling (in-sample — diagnostic upper bound)
        w_platt, b_platt = platt_scale(y_vl_3, multi_probs)
        platt_probs = [sigmoid(w_platt * s + b_platt) for s in multi_probs]
        ece_platt   = ece(y_vl_3, platt_probs)
        auc_platt   = roc_auc(y_vl_3, platt_probs)
        br_platt    = brier(y_vl_3, platt_probs)
        base_br     = brier(y_vl_3, base_probs)
        bs_platt    = round(1 - br_platt / base_br, 4)

        print(f"\n  ⚠ In-sample Platt scaling (diagnostic upper bound, NOT deployment-ready):")
        print(f"    Platt w={w_platt:.4f}, b={b_platt:.4f}")
        print(f"    ECE after Platt : {ece_platt:.4f} (vs {ece_model:.4f} before)")
        print(f"    AUC after Platt : {auc_platt:.4f} (AUC preserved by monotone transform)")
        print(f"    Brier Skill after Platt: {bs_platt:+.4f}")
        print(f"    ECE improvement : {ece_model - ece_platt:+.4f}")

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 5: Signal Stability — bullpen_usage_diff by calendar month
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("SECTION 5: Signal Stability — bullpen_usage_diff by Month")
    print(f"{'='*72}")

    month_data: dict[str, tuple[list[float], list[int]]] = defaultdict(lambda: ([], []))
    for r in joined:
        v = r.get("bullpen_usage_diff")
        if v is None:
            continue
        month = r["date"][:7]  # YYYY-MM
        month_data[month][0].append(float(v))
        month_data[month][1].append(r["home_win"])

    print(f"\n  {'Month':<9}  {'n':>5}  {'AUC':>7}  {'Pearson r':>10}  {'home_win%':>10}")
    print(f"  {'-'*48}")
    for month in sorted(month_data):
        X_m, y_m = month_data[month]
        if len(X_m) < 10:
            print(f"  {month:<9}  {len(X_m):>5}  {'--':>7}  {'--':>10}  {100*sum(y_m)//max(len(y_m),1):>9}%")
            continue
        auc_m = roc_auc(y_m, X_m)  # use raw feature value as score for within-month AUC
        pr    = pearson(X_m, [float(yi) for yi in y_m])
        hw_pct = sum(y_m) / len(y_m)
        print(f"  {month:<9}  {len(X_m):>5}  {auc_m:.4f}  {pr:>+10.4f}  {100*hw_pct:>9.1f}%")

    # Summary: is the signal consistent across months?
    auc_vals = []
    for month in sorted(month_data):
        X_m, y_m = month_data[month]
        if len(X_m) >= 10:
            auc_vals.append(roc_auc(y_m, X_m))
    if auc_vals:
        auc_above_half = sum(1 for v in auc_vals if v > 0.50) / len(auc_vals)
        auc_mean = sum(auc_vals) / len(auc_vals)
        auc_std  = math.sqrt(sum((v - auc_mean) ** 2 for v in auc_vals) / len(auc_vals))
        print(f"\n  Monthly AUC summary: mean={auc_mean:.4f}, std={auc_std:.4f}, above-0.5 rate={auc_above_half:.0%}")
        if auc_above_half >= 0.67:
            stability = "STABLE_POSITIVE (signal present majority of months)"
        elif auc_above_half >= 0.50:
            stability = "MIXED (signal present half the months)"
        else:
            stability = "UNSTABLE (signal absent majority of months)"
        print(f"  Stability verdict: {stability}")

    # ─────────────────────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("P33 FINAL SUMMARY")
    print(f"{'='*72}")
    print(f"  Multi-feature AUC     : {multi_auc:.4f}" if multi_probs else "  Multi-feature: UNAVAILABLE")
    print(f"  Multi-feature Brier   : {multi_bs:+.4f}" if multi_probs else "")
    if multi_probs:
        print(f"  ECE (uncalibrated)    : {ece_model:.4f}")
        print(f"  ECE (Platt in-sample) : {ece_platt:.4f}")
    print(f"\n  Individual feature AUC comparison:")
    for feat in FEATURES_1D:
        ir = individual_results.get(feat, {})
        print(f"    {feat:<30}: {ir.get('auc','--')}")
    print(f"\n  [GOVERNANCE]")
    print(f"    diagnostic_only   = {DIAGNOSTIC_ONLY}")
    print(f"    promotion_freeze  = {PROMOTION_FREEZE}")
    print(f"    Champion strategy = UNMODIFIED")
    print(f"    Kelly/bet logic   = UNMODIFIED")
    print(f"\n{'='*72}")
    print("P33 COMPLETE")
    print(f"{'='*72}")


if __name__ == "__main__":
    main()
