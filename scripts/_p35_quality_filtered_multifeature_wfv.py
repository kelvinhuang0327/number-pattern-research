"""
P35: Quality-Filtered Multi-Feature WFV + Calibration + Park Factor Audit
diagnostic_only=True | promotion_freeze=True

Changes vs P33:
  - EXCLUDE league_average_fallback rows (29.5% constant-zero contamination)
  - Add park_run_factor quintile direction audit
  - Maintain 3-way join: phase56 + SSOT bullpen + asplayed outcomes

Sources:
  phase56 : data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
  bullpen  : data/mlb_context/bullpen_usage_3d.jsonl
  asplayed : data/mlb_2025/mlb-2025-asplayed.csv
"""
from __future__ import annotations
import json, csv, math, re, collections
from typing import NamedTuple

# ── Governance ─────────────────────────────────────────────────────────────────
DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True

PHASE56   = "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
BULLPEN   = "data/mlb_context/bullpen_usage_3d.jsonl"
ASPLAYED  = "data/mlb_2025/mlb-2025-asplayed.csv"
EXCLUDED_TIER = "league_average_fallback"

# ── Math primitives ────────────────────────────────────────────────────────────
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
    return sum((yi - pi)**2 for yi, pi in zip(y, p)) / len(y)

def log_loss(y: list[int], p: list[float]) -> float:
    eps = 1e-9
    return -sum(yi * math.log(pi + eps) + (1 - yi) * math.log(1 - pi + eps)
                for yi, pi in zip(y, p)) / len(y)

def brier_skill(y: list[int], p: list[float]) -> float:
    br = sum(y) / len(y)
    bs_naive = brier(y, [br] * len(y))
    return 1 - brier(y, p) / bs_naive if bs_naive > 0 else 0.0

def ll_skill(y: list[int], p: list[float]) -> float:
    br = sum(y) / len(y)
    eps = 1e-9
    ll_naive = -(br * math.log(br + eps) + (1 - br) * math.log(1 - br + eps))
    return 1 - log_loss(y, p) / ll_naive if ll_naive > 0 else 0.0

def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((ai - ma) * (bi - mb) for ai, bi in zip(a, b))
    da = math.sqrt(sum((ai - ma)**2 for ai in a))
    db = math.sqrt(sum((bi - mb)**2 for bi in b))
    return num / (da * db) if da > 0 and db > 0 else 0.0

def standardize(X: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    """Per-column z-score. Returns (Xs, means, stds)."""
    if not X:
        return X, [], []
    n_feat = len(X[0])
    means = [sum(row[j] for row in X) / len(X) for j in range(n_feat)]
    stds = [
        math.sqrt(sum((row[j] - means[j])**2 for row in X) / len(X)) or 1.0
        for j in range(n_feat)
    ]
    Xs = [[(row[j] - means[j]) / stds[j] for j in range(n_feat)] for row in X]
    return Xs, means, stds

def standardize_1d(X: list[float]) -> tuple[list[float], float, float]:
    n = len(X)
    mu = sum(X) / n
    var = sum((xi - mu)**2 for xi in X) / n
    sd = math.sqrt(var) if var > 0 else 1.0
    return [(xi - mu) / sd for xi in X], mu, sd

def train_logistic_nd(X: list[list[float]], y: list[int],
                      lr: float = 0.05, epochs: int = 800):
    """Multi-feature gradient descent. Returns (weights, bias)."""
    n_feat = len(X[0])
    w = [0.0] * n_feat
    b = 0.0
    n = len(X)
    for _ in range(epochs):
        gw = [0.0] * n_feat
        gb = 0.0
        for xi, yi in zip(X, y):
            pred = sigmoid(sum(w[j] * xi[j] for j in range(n_feat)) + b)
            err = pred - yi
            for j in range(n_feat):
                gw[j] += err * xi[j]
            gb += err
        w = [w[j] - lr * gw[j] / n for j in range(n_feat)]
        b -= lr * gb / n
    return w, b

def train_logistic_1d(X: list[float], y: list[int],
                      lr: float = 0.05, epochs: int = 600) -> tuple[float, float]:
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

def ece(y: list[int], p: list[float], n_bins: int = 10) -> float:
    bins = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((pi, yi))
    total = len(y)
    ece_val = 0.0
    for b in bins:
        if not b:
            continue
        conf = sum(x[0] for x in b) / len(b)
        acc = sum(x[1] for x in b) / len(b)
        ece_val += abs(conf - acc) * len(b) / total
    return ece_val

def reliability_diagram(y: list[int], p: list[float], n_bins: int = 10) -> None:
    edges = [i / n_bins for i in range(n_bins + 1)]
    bins = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((pi, yi))
    print(f"  {'Bin':15s} {'Conf':>7s} {'Acc':>7s} {'n':>5s}  Note")
    print("  " + "-" * 60)
    for i, b in enumerate(bins):
        lo, hi = edges[i], edges[i + 1]
        if not b:
            print(f"  [{lo:.1f}-{hi:.1f}]{'':6s}  --      --      0")
            continue
        conf = sum(x[0] for x in b) / len(b)
        acc = sum(x[1] for x in b) / len(b)
        bar = "█" * int(acc * 30)
        note = ""
        if abs(conf - acc) > 0.05:
            note = "▼UNDERCONF" if acc > conf else "▲OVERCONF"
        print(f"  [{lo:.1f}-{hi:.1f}]  {conf:.3f}   {acc:.3f}  {len(b):5d}  {bar} {note}")

def platt_scale(y_val: list[int], scores_val: list[float]) -> tuple[float, float]:
    """In-sample Platt scaling (diagnostic upper bound only)."""
    return train_logistic_1d(scores_val, y_val, lr=0.1, epochs=1000)

# ── Team normalization ─────────────────────────────────────────────────────────
TEAM_OVERRIDES = {"ST_LOUIS_CARDINALS": "St. Louis Cardinals"}

def canon_to_display(canon: str) -> str:
    if canon in TEAM_OVERRIDES:
        return TEAM_OVERRIDES[canon]
    return " ".join(w.capitalize() for w in canon.split("_"))

_GID_PATTERN = re.compile(r"MLB-(\d{4}_\d{2}_\d{2})-.*-AT-(.+)$")

def parse_gid(game_id: str) -> tuple[str, str] | None:
    m = _GID_PATTERN.match(game_id)
    if not m:
        return None
    date_str = m.group(1).replace("_", "-")
    home_display = canon_to_display(m.group(2))
    return date_str, home_display

# ── Data loading ───────────────────────────────────────────────────────────────
def build_phase56_lookup() -> dict:
    """Returns {(game_date, home_team): {sp_fip_delta, park_run_factor, src}}"""
    lookup: dict = {}
    total = fallback_skip = 0
    for line in open(PHASE56):
        r = json.loads(line)
        total += 1
        p0 = r.get("p0_features", {})
        src = p0.get("sp_context_source", "")
        if src == EXCLUDED_TIER:
            fallback_skip += 1
            continue
        key = (r["game_date"], r["home_team"])
        if key not in lookup:
            lookup[key] = {
                "sp_fip_delta": float(p0.get("sp_fip_delta", 0)),
                "park_run_factor": float(p0.get("park_run_factor", 1.0)),
                "src": src,
            }
    print(f"[PHASE56 LOOKUP] total={total} | excluded_fallback={fallback_skip} | keys={len(lookup)}")
    return lookup

def build_bp_lookup() -> dict:
    """Returns {(date, home_display): bullpen_usage_diff}"""
    lookup: dict = {}
    for line in open(BULLPEN):
        r = json.loads(line)
        gid = r.get("game_id", "")
        parsed = parse_gid(gid)
        if not parsed:
            continue
        date_str, home_display = parsed
        bp_home = r.get("bullpen_usage_last_3d_home")
        bp_away = r.get("bullpen_usage_last_3d_away")
        if bp_home is None or bp_away is None:
            continue
        try:
            diff = float(bp_home) - float(bp_away)
        except (TypeError, ValueError):
            continue
        key = (date_str, home_display)
        if key not in lookup:
            lookup[key] = diff
    print(f"[BP LOOKUP] keys={len(lookup)}")
    return lookup

def load_asplayed() -> dict:
    """Returns {(date, home_team): home_win}"""
    lookup: dict = {}
    with open(ASPLAYED) as f:
        for row in csv.DictReader(f):
            hw = row.get("home_win")
            if hw is None or row.get("status", "").upper() != "FINAL":
                continue
            try:
                lookup[(row["date"], row["home_team"])] = int(float(hw))
            except (ValueError, KeyError):
                continue
    print(f"[ASPLAYED] keys={len(lookup)}")
    return lookup

# ── 3-way join ─────────────────────────────────────────────────────────────────
class Record(NamedTuple):
    game_date: str
    home_team: str
    sp_fip_delta: float
    park_run_factor: float
    bullpen_usage_diff: float | None
    home_win: int
    src: str

def build_dataset(p56: dict, bp: dict, asp: dict) -> list[Record]:
    records = []
    sp_miss = bp_miss = outcome_miss = 0
    for (date, home), outcome in sorted(asp.items()):
        sp_data = p56.get((date, home))
        if sp_data is None:
            sp_miss += 1
            continue
        bp_diff = bp.get((date, home))
        if bp_diff is None:
            bp_miss += 1
        records.append(Record(
            game_date=date,
            home_team=home,
            sp_fip_delta=sp_data["sp_fip_delta"],
            park_run_factor=sp_data["park_run_factor"],
            bullpen_usage_diff=bp_diff,
            home_win=outcome,
            src=sp_data["src"],
        ))
    print(f"[3-WAY JOIN] records={len(records)} | sp_miss={sp_miss} | bp_miss={bp_miss} | outcome_miss={outcome_miss}")
    complete = [r for r in records if r.bullpen_usage_diff is not None]
    print(f"  Complete (all 3 features): {len(complete)}/{len(records)}")
    return records

# ── Quintile analysis ──────────────────────────────────────────────────────────
def park_quintile_audit(records: list[Record]) -> None:
    """Divide park_run_factor into 5 equal-count bins and compare home_win rate."""
    valid = [(r.park_run_factor, r.home_win) for r in records if r.park_run_factor is not None]
    valid.sort(key=lambda x: x[0])
    n = len(valid)
    q_size = n // 5

    print(f"\n  Park Run Factor Quintile Analysis (n={n})")
    print(f"  {'Quintile':10s} {'PRF range':20s} {'n':>5s} {'HW%':>7s} {'Pearson r':>10s}")
    print("  " + "-" * 58)

    hw_rates = []
    prf_mids = []
    for q in range(5):
        lo = q * q_size
        hi = (q + 1) * q_size if q < 4 else n
        chunk = valid[lo:hi]
        prfs = [x[0] for x in chunk]
        wins = [x[1] for x in chunk]
        hw_rate = sum(wins) / len(wins)
        prf_lo, prf_hi = min(prfs), max(prfs)
        prf_mid = sum(prfs) / len(prfs)
        hw_rates.append(hw_rate)
        prf_mids.append(prf_mid)
        print(f"  Q{q+1:d}        [{prf_lo:.3f}-{prf_hi:.3f}]  {len(chunk):5d}  {hw_rate:.3f}  ")

    # Direction
    first_hw = hw_rates[0]
    last_hw = hw_rates[-1]
    direction = "NEGATIVE (higher PRF → lower HW%)" if last_hw < first_hw else "POSITIVE (higher PRF → higher HW%)"
    print(f"\n  Direction: {direction}")
    print(f"  Q1 HW%={first_hw:.3f} → Q5 HW%={last_hw:.3f} (Δ={last_hw-first_hw:+.3f})")

    # Pearson on full dataset
    all_prfs = [x[0] for x in valid]
    all_hws = [x[1] for x in valid]
    pr = pearson(all_prfs, all_hws)
    print(f"  Pearson r (park_run_factor vs home_win): {pr:+.4f}")

    # 1D LR coefficient
    Xs, mu, sd = standardize_1d(all_prfs)
    w, b = train_logistic_1d(Xs, all_hws)
    print(f"  1D LR coefficient (standardized): {w:+.4f} | raw-scale: {w/sd:+.4f}")

# ── Walk-forward + Calibration ─────────────────────────────────────────────────
def run_wfv(complete: list[Record], feature_names: list[str]) -> None:
    """3-feature walk-forward + calibration on quality-filtered complete-row dataset."""
    complete.sort(key=lambda r: r.game_date)
    cut = int(len(complete) * 0.70)
    train = complete[:cut]
    val   = complete[cut:]

    print(f"\n  [SPLIT] n_complete={len(complete)}")
    print(f"  Train: {len(train)} | {train[0].game_date} → {train[-1].game_date}")
    print(f"  Val  : {len(val)}   | {val[0].game_date} → {val[-1].game_date}")

    # Build feature vectors
    def feats(r: Record) -> list[float]:
        return [r.sp_fip_delta, r.park_run_factor, r.bullpen_usage_diff]

    X_train = [feats(r) for r in train]
    y_train = [r.home_win for r in train]
    X_val   = [feats(r) for r in val]
    y_val   = [r.home_win for r in val]

    # Standardize
    Xs_train, means, stds = standardize(X_train)
    Xs_val = [[(x - m) / s for x, m, s in zip(row, means, stds)] for row in X_val]

    # Train multi-feature model
    w, b = train_logistic_nd(Xs_train, y_train)
    preds_val = [sigmoid(sum(wi * xi for wi, xi in zip(w, row)) + b) for row in Xs_val]

    # Metrics
    auc  = roc_auc(y_val, preds_val)
    bs_skill = brier_skill(y_val, preds_val)
    ll_s = ll_skill(y_val, preds_val)
    ece_raw = ece(y_val, preds_val)
    hw_rate = sum(y_val) / len(y_val)

    print(f"\n  [MULTI-FEATURE RESULTS — quality-filtered]")
    print(f"  AUC        = {auc:.4f}")
    print(f"  Brier Skill= {bs_skill:+.4f}")
    print(f"  LL Skill   = {ll_s:+.4f}")
    print(f"  ECE (raw)  = {ece_raw:.4f}")
    print(f"  HW% (val)  = {hw_rate:.3f}")
    print(f"\n  Coefficients (raw feature scale, via standardized weights):")
    for name, wi, sd in zip(feature_names, w, stds):
        raw = wi / sd if sd > 0 else 0.0
        print(f"    {name:30s}: standardized={wi:+.4f}  raw-scale={raw:+.6f}")
    print(f"  Intercept: {b:+.4f}")

    # Classification
    if auc >= 0.540 and bs_skill > 0.001:
        cls = "STABLE_DIAGNOSTIC_SIGNAL"
    elif auc >= 0.520 and bs_skill > 0:
        cls = "WEAK_SIGNAL (calibration OK)"
    elif auc >= 0.510:
        cls = "WEAK_SIGNAL (CALIBRATION_REQUIRED)"
    else:
        cls = "NOISE"
    if PROMOTION_FREEZE:
        cls += " | PROMOTION_BLOCKED_BY_GOVERNANCE"
    print(f"  Classification: {cls}")

    # Calibration
    print(f"\n  [CALIBRATION]")
    base_rate = sum(y_val) / len(y_val)
    preds_naive = [base_rate] * len(y_val)
    ece_naive = ece(y_val, preds_naive)
    print(f"  ECE (naive base rate): {ece_naive:.4f}")
    print(f"  ECE (multi-feature)  : {ece_raw:.4f}")
    print(f"\n  Reliability Diagram:")
    reliability_diagram(y_val, preds_val)

    # Platt scaling (in-sample diagnostic)
    pw, pb = platt_scale(y_val, preds_val)
    preds_platt = [sigmoid(pw * pi + pb) for pi in preds_val]
    ece_platt = ece(y_val, preds_platt)
    bs_platt = brier_skill(y_val, preds_platt)
    auc_platt = roc_auc(y_val, preds_platt)
    print(f"\n  ⚠  In-sample Platt (diagnostic upper bound, NOT deployment-ready):")
    print(f"    Platt w={pw:.4f}, b={pb:.4f}")
    print(f"    ECE after Platt : {ece_platt:.4f} (vs {ece_raw:.4f} before)")
    print(f"    AUC after Platt : {auc_platt:.4f}")
    print(f"    Brier Skill     : {bs_platt:+.4f}")

    return auc, bs_skill, ece_raw, w, stds

# ── Individual feature baselines (quality-filtered) ────────────────────────────
def run_individual_baselines(complete: list[Record]) -> None:
    complete.sort(key=lambda r: r.game_date)
    cut = int(len(complete) * 0.70)
    train, val = complete[:cut], complete[cut:]

    print(f"\n  Individual Feature Baselines (quality-filtered, same split as multi-feature)")
    print(f"  {'Feature':30s} {'AUC':>7s} {'Brier Sk':>10s} {'Pearson r':>10s}")
    print("  " + "-" * 64)

    features = [
        ("sp_fip_delta",       [r.sp_fip_delta for r in train],       [r.sp_fip_delta for r in val]),
        ("park_run_factor",    [r.park_run_factor for r in train],    [r.park_run_factor for r in val]),
        ("bullpen_usage_diff", [r.bullpen_usage_diff for r in train], [r.bullpen_usage_diff for r in val]),
    ]
    y_train = [r.home_win for r in train]
    y_val   = [r.home_win for r in val]

    for name, X_tr, X_va in features:
        Xs, mu, sd = standardize_1d(X_tr)
        Xs_v = [(xi - mu) / sd for xi in X_va]
        w, b = train_logistic_1d(Xs, y_train)
        preds = [sigmoid(w * xi + b) for xi in Xs_v]
        auc = roc_auc(y_val, preds)
        bs  = brier_skill(y_val, preds)
        pr  = pearson(X_tr, y_train)
        print(f"  {name:30s} {auc:.4f}  {bs:+.6f}  {pr:+.4f}")

# ── Monthly stability (full dataset, raw sp_fip_delta) ─────────────────────────
def monthly_stability_sp(records: list[Record]) -> None:
    by_month = collections.defaultdict(list)
    for r in records:
        by_month[r.game_date[:7]].append(r)
    aucs = []
    print(f"\n  {'Month':10s} {'n':>5s} {'sp_fip AUC':>11s} {'park AUC':>9s} {'Pearson(sp)':>12s} {'hw%':>7s}")
    print("  " + "-" * 62)
    for month in sorted(by_month):
        mrs = by_month[month]
        if len(mrs) < 10:
            continue
        X_sp = [r.sp_fip_delta for r in mrs]
        X_pk = [r.park_run_factor for r in mrs]
        y = [r.home_win for r in mrs]
        auc_sp = roc_auc(y, X_sp)
        auc_pk = roc_auc(y, X_pk)
        pr = pearson(X_sp, y)
        hw = sum(y) / len(y)
        aucs.append(auc_sp)
        print(f"  {month:10s} {len(mrs):5d}  {auc_sp:.4f}     {auc_pk:.4f}     {pr:+.4f}  {hw:.1%}")
    if aucs:
        mn = sum(aucs) / len(aucs)
        sd = math.sqrt(sum((a - mn)**2 for a in aucs) / len(aucs))
        ab = sum(1 for a in aucs if a > 0.5)
        print(f"\n  sp_fip_delta monthly AUC: mean={mn:.4f}, std={sd:.4f}, above-0.5 rate={ab}/{len(aucs)} ({ab/len(aucs):.0%})")
        verdict = "STABLE" if ab / len(aucs) >= 0.70 else "UNSTABLE"
        print(f"  Stability verdict: {verdict}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 72)
    print("P35: Quality-Filtered Multi-Feature WFV + Calibration + Park Audit")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print(f"Excluded tier: '{EXCLUDED_TIER}' (constant sp_fip_delta=0.0)")
    print("=" * 72)

    # Load
    p56  = build_phase56_lookup()
    bp   = build_bp_lookup()
    asp  = load_asplayed()

    # Join
    print()
    records = build_dataset(p56, bp, asp)
    complete = [r for r in records if r.bullpen_usage_diff is not None]
    src_dist = collections.Counter(r.src for r in records)
    print(f"  Source distribution in joined set:")
    for k, v in sorted(src_dist.items(), key=lambda x: -x[1]):
        print(f"    {k:30s}: {v}")

    # Park factor quintile audit
    print(f"\n{'='*72}")
    print("SECTION 1: Park Run Factor Direction Audit")
    print(f"{'='*72}")
    park_quintile_audit(records)

    # Individual feature baselines
    print(f"\n{'='*72}")
    print("SECTION 2: Individual Feature Baselines (quality-filtered)")
    print(f"{'='*72}")
    run_individual_baselines(complete)

    # Multi-feature WFV
    print(f"\n{'='*72}")
    print("SECTION 3: Multi-Feature WFV (quality-filtered)")
    print(f"{'='*72}")
    feature_names = ["sp_fip_delta", "park_run_factor", "bullpen_usage_diff"]
    run_wfv(complete, feature_names)

    # Monthly stability
    print(f"\n{'='*72}")
    print("SECTION 4: Monthly Stability (quality-filtered, raw feature AUC)")
    print(f"{'='*72}")
    monthly_stability_sp(records)

    # Comparison vs P33 / P34
    print(f"\n{'='*72}")
    print("SECTION 5: Comparison vs P33/P34 Baselines")
    print(f"{'='*72}")
    print(f"""
  P33 multi-feature (all-sample, n_val=721):
    AUC=0.5280 | Brier Skill=+0.0009 | ECE=0.0213
    park_run_factor coeff (standardized) = -0.3725

  P34 sp_fip_delta individual (quality-filtered, per tier):
    historical_proxy  AUC=0.542, monthly STABLE 83%
    mixed             AUC=0.522, monthly STABLE 83%

  P35 quality-filtered multi-feature (see Section 3 above):
    → Compare AUC, Brier Skill, ECE, and park_run_factor coefficient
    → Key question: does excluding league_average_fallback flip park coeff sign?
    → Key question: does Brier Skill become positive (target: > +0.001)?
""")

    # Governance
    print(f"{'='*72}")
    print("GOVERNANCE")
    print(f"{'='*72}")
    print(f"  diagnostic_only   = {DIAGNOSTIC_ONLY}")
    print(f"  promotion_freeze  = {PROMOTION_FREEZE}")
    print(f"  Champion strategy = UNMODIFIED")
    print(f"  Kelly/bet logic   = UNMODIFIED")
    print(f"\n{'='*72}")
    print("P35 COMPLETE")
    print(f"{'='*72}")

if __name__ == "__main__":
    main()
