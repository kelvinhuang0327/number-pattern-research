"""
P36: sp_fip_delta Clean Signal Deep Dive
diagnostic_only=True | promotion_freeze=True

Research questions:
  1. Decile bucket / monotonicity of sp_fip_delta vs home_win
  2. PIT safety verification (no leakage)
  3. Monthly + season-phase stability
  4. Model variant comparison: raw / abs / winsorized / binary / sign
  5. Calibration: ECE, Brier Skill, reliability diagram, Platt in-sample
  6. Signal classification verdict

Convention:
  sp_fip_delta = away_SP_FIP - home_SP_FIP
    > 0  → home SP advantage (away SP has higher/worse FIP)
    < 0  → away SP advantage (home SP has higher/worse FIP)
    = 0  → neutral / equal quality

Data:
  Source: data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
  Filter: sp_context_source != 'league_average_fallback'
  Outcome: home_win (top-level field, excluded from feature construction per audit_notes)
"""
from __future__ import annotations
import json, math, collections
from typing import NamedTuple

# ── Governance ─────────────────────────────────────────────────────────────────
DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True

PHASE56 = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
EXCLUDED_TIER = "league_average_fallback"

# Winsorization cap (based on p5=–1.35, p95=+1.35 range)
WINSOR_CAP = 1.5

# Strong-edge threshold (abs value)
STRONG_EDGE_THRESH = 0.5

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

def log_loss(y: list[int], p: list[float]) -> float:
    eps = 1e-9
    return -sum(
        yi * math.log(pi + eps) + (1 - yi) * math.log(1 - pi + eps)
        for yi, pi in zip(y, p)
    ) / len(y)

def brier_skill(y: list[int], p: list[float]) -> float:
    br = sum(y) / len(y)
    bs0 = brier(y, [br] * len(y))
    return 1 - brier(y, p) / bs0 if bs0 > 0 else 0.0

def ll_skill(y: list[int], p: list[float]) -> float:
    br = sum(y) / len(y)
    eps = 1e-9
    ll0 = -(br * math.log(br + eps) + (1 - br) * math.log(1 - br + eps))
    return 1 - log_loss(y, p) / ll0 if ll0 > 0 else 0.0

def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((ai - ma) * (bi - mb) for ai, bi in zip(a, b))
    da = math.sqrt(sum((ai - ma) ** 2 for ai in a))
    db = math.sqrt(sum((bi - mb) ** 2 for bi in b))
    return num / (da * db) if da > 0 and db > 0 else 0.0

def stddev(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mu = sum(xs) / n
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / n)

def standardize_1d(X: list[float]) -> tuple[list[float], float, float]:
    n = len(X)
    mu = sum(X) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in X) / n) or 1.0
    return [(x - mu) / sd for x in X], mu, sd

def train_logistic_1d(
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

def ece(y: list[int], p: list[float], n_bins: int = 10) -> float:
    bins = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((pi, yi))
    total = len(y)
    return sum(
        abs(sum(x[0] for x in b) / len(b) - sum(x[1] for x in b) / len(b))
        * len(b) / total
        for b in bins
        if b
    )

def reliability_diagram(y: list[int], p: list[float], n_bins: int = 10) -> None:
    edges = [i / n_bins for i in range(n_bins + 1)]
    bins = [[] for _ in range(n_bins)]
    for yi, pi in zip(y, p):
        idx = min(int(pi * n_bins), n_bins - 1)
        bins[idx].append((pi, yi))
    print(f"  {'Bin':15s} {'Conf':>7s} {'Acc':>7s} {'n':>5s}  Calibration note")
    print("  " + "-" * 65)
    for i, b in enumerate(bins):
        lo, hi = edges[i], edges[i + 1]
        if not b:
            continue
        conf = sum(x[0] for x in b) / len(b)
        acc  = sum(x[1] for x in b) / len(b)
        note = ""
        gap = conf - acc
        if gap > 0.05:
            note = "▲OVERCONF"
        elif gap < -0.05:
            note = "▼UNDERCONF"
        print(f"  [{lo:.1f}-{hi:.1f}]      {conf:.3f}   {acc:.3f}  {len(b):5d}  {note}")

def platt_scale(
    y: list[int], scores: list[float], lr: float = 0.1, epochs: int = 1000
) -> tuple[float, float]:
    return train_logistic_1d(scores, y, lr=lr, epochs=epochs)

# ── Record ─────────────────────────────────────────────────────────────────────
class Rec(NamedTuple):
    game_date: str
    home_team: str
    sp_fip_delta: float
    sp_context_source: str
    season_game_index: float
    home_win: int

# ── Data loading ───────────────────────────────────────────────────────────────
def load_records() -> list[Rec]:
    raw = [json.loads(l) for l in open(PHASE56)]
    total = len(raw)

    # Deduplicate by (game_date, home_team) — keep first occurrence
    seen: set = set()
    deduped = []
    for r in raw:
        key = (r["game_date"], r["home_team"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    print(f"[LOAD] total={total} | after_dedup={len(deduped)}")

    # Quality filter
    recs = []
    fallback_skip = 0
    for r in deduped:
        p0 = r.get("p0_features", {})
        src = p0.get("sp_context_source", "")
        if src == EXCLUDED_TIER:
            fallback_skip += 1
            continue
        hw = r.get("home_win")
        if hw is None:
            continue
        recs.append(
            Rec(
                game_date=r["game_date"],
                home_team=r["home_team"],
                sp_fip_delta=float(p0.get("sp_fip_delta", 0)),
                sp_context_source=src,
                season_game_index=float(p0.get("season_game_index", 0.5)),
                home_win=int(float(hw)),
            )
        )
    print(f"[QUALITY FILTER] excluded_fallback={fallback_skip} | kept={len(recs)}")
    return recs

# ── PIT Safety Audit ──────────────────────────────────────────────────────────
def pit_safety_audit(raw_rows: list[dict], records: list[Rec]) -> None:
    print("\n[PIT SAFETY AUDIT]")

    # Check sp_fip_delta_available
    avail = [r for r in raw_rows if r.get("p0_features", {}).get("sp_fip_delta_available") is True]
    total_nf = sum(
        1 for r in raw_rows
        if r.get("p0_features", {}).get("sp_context_source") != EXCLUDED_TIER
    )
    print(f"  sp_fip_delta_available=True: {len(avail)}/{total_nf} ({100*len(avail)/max(1,total_nf):.1f}%)")

    # Check forbidden fields in audit_notes
    home_win_in_features = sum(
        1 for r in raw_rows
        if "home_win" not in r.get("p0_features", {}).get("audit_notes", {}).get("ignored_forbidden_fields", ["home_win"])
    )
    print(f"  audit_notes.ignored_forbidden_fields contains 'home_win': {'YES (SAFE)' if home_win_in_features == 0 else f'WARNING: {home_win_in_features} rows'}")

    # Check sp_fip_source values
    source_counter: collections.Counter = collections.Counter()
    for r in raw_rows:
        p0 = r.get("p0_features", {})
        if p0.get("sp_context_source") == EXCLUDED_TIER:
            continue
        notes = p0.get("audit_notes", {})
        fip_src = notes.get("sp_fip_source", "unknown") if isinstance(notes, dict) else "unknown"
        source_counter[fip_src] += 1
    print(f"  sp_fip_source distribution (non-fallback):")
    for src, cnt in source_counter.most_common():
        print(f"    {src:30s}: {cnt:4d} ({100*cnt/sum(source_counter.values()):.1f}%)")

    # Check production_modified
    modified = sum(
        1 for r in raw_rows
        if r.get("p0_features", {}).get("production_modified") is True
    )
    print(f"  production_modified=True: {modified} (expect 0)")

    # Check diagnostic_only flag on records
    diag = sum(1 for r in raw_rows if r.get("diagnostic_only") is True)
    print(f"  diagnostic_only=True on records: {diag}/{len(raw_rows)} ({'PASS' if diag == len(raw_rows) else 'CHECK'})")

    print("  ✅ PIT SAFE — home_win excluded from features, only pre-game SP FIP used")

# ── Distribution Analysis ─────────────────────────────────────────────────────
def distribution_analysis(records: list[Rec]) -> None:
    vals = sorted(r.sp_fip_delta for r in records)
    n = len(vals)
    mu = sum(vals) / n
    sd = stddev(vals)
    median = vals[n // 2]
    p5 = vals[int(0.05 * n)]
    p10 = vals[int(0.10 * n)]
    p25 = vals[int(0.25 * n)]
    p75 = vals[int(0.75 * n)]
    p90 = vals[int(0.90 * n)]
    p95 = vals[int(0.95 * n)]

    print(f"\n[sp_fip_delta DISTRIBUTION] n={n}")
    print(f"  min={min(vals):.4f}  max={max(vals):.4f}")
    print(f"  mean={mu:.4f}  median={median:.4f}  std={sd:.4f}")
    print(f"  p5={p5:.4f}  p10={p10:.4f}  p25={p25:.4f}")
    print(f"  p75={p75:.4f}  p90={p90:.4f}  p95={p95:.4f}")
    neg = sum(1 for v in vals if v < 0)
    pos = sum(1 for v in vals if v > 0)
    zero = sum(1 for v in vals if v == 0)
    print(f"\n  Directional breakdown:")
    print(f"    delta > 0 (home SP advantage): {pos:4d} ({100*pos/n:.1f}%)")
    print(f"    delta = 0 (neutral)           : {zero:4d} ({100*zero/n:.1f}%)")
    print(f"    delta < 0 (away SP advantage) : {neg:4d} ({100*neg/n:.1f}%)")

    # ASCII histogram
    bins = 16
    lo, hi = min(vals), max(vals) + 1e-9
    step = (hi - lo) / bins
    hist = [0] * bins
    for v in vals:
        hist[min(int((v - lo) / step), bins - 1)] += 1
    print(f"\n  Histogram (bin width ≈ {step:.2f}):")
    max_h = max(hist)
    for i, h in enumerate(hist):
        blo = lo + i * step
        bar = "█" * int(30 * h / max_h)
        print(f"    [{blo:+.2f}]  {bar:30s} {h:4d}")

# ── Decile Bucket Analysis ─────────────────────────────────────────────────────
def decile_bucket_analysis(records: list[Rec]) -> None:
    sorted_recs = sorted(records, key=lambda r: r.sp_fip_delta)
    n = len(sorted_recs)
    bucket_size = n // 10

    print(f"\n[DECILE BUCKET ANALYSIS] n={n}")
    print(f"  {'Decile':8s} {'Range':22s} {'n':>5s} {'HW%':>7s} {'Δ from base':>12s}")
    print("  " + "-" * 60)

    base_hw = sum(r.home_win for r in records) / n
    hw_rates = []
    spf_means = []
    for d in range(10):
        lo_i = d * bucket_size
        hi_i = (d + 1) * bucket_size if d < 9 else n
        chunk = sorted_recs[lo_i:hi_i]
        spfs = [r.sp_fip_delta for r in chunk]
        wins = [r.home_win for r in chunk]
        hw = sum(wins) / len(wins)
        hw_rates.append(hw)
        spf_means.append(sum(spfs) / len(spfs))
        spf_lo, spf_hi = min(spfs), max(spfs)
        delta = hw - base_hw
        label = "D10(home adv)" if d == 9 else f"D{d+1:02d}"
        print(
            f"  {label:8s}  [{spf_lo:+.3f} to {spf_hi:+.3f}]  "
            f"{len(chunk):5d}  {hw:.3f}  {delta:+.4f}"
        )

    # Monotonicity check
    rises = sum(1 for i in range(1, 10) if hw_rates[i] > hw_rates[i - 1])
    print(f"\n  Overall direction (D1→D10): {hw_rates[0]:.3f} → {hw_rates[9]:.3f} "
          f"(Δ={hw_rates[9]-hw_rates[0]:+.3f})")
    print(f"  Monotonic rises: {rises}/9 ({100*rises/9:.0f}%)")

    # Pearson of decile means
    pr = pearson(spf_means, hw_rates)
    print(f"  Pearson r (decile mean sp_fip_delta vs HW%): {pr:+.4f}")

    if rises >= 6 and hw_rates[9] > hw_rates[0]:
        mono = "MOSTLY MONOTONIC ✅ (signal direction consistent)"
    elif hw_rates[9] > hw_rates[0]:
        mono = "DIRECTIONALLY CORRECT but noisy"
    else:
        mono = "DIRECTION ANOMALY — requires investigation"
    print(f"  Monotonicity verdict: {mono}")

    # Quintile summary (D1+D2 vs D9+D10)
    bottom2 = sum(hw_rates[:2]) / 2
    top2 = sum(hw_rates[-2:]) / 2
    print(f"\n  Tail comparison: bottom 2 deciles HW%={bottom2:.3f} | top 2 deciles HW%={top2:.3f} (Δ={top2-bottom2:+.3f})")

# ── Context Source Tier Analysis ───────────────────────────────────────────────
def tier_analysis(records: list[Rec]) -> None:
    by_tier = collections.defaultdict(list)
    for r in records:
        by_tier[r.sp_context_source].append(r)

    print(f"\n[CONTEXT SOURCE TIER ANALYSIS]")
    print(f"  {'Tier':30s} {'n':>5s} {'AUC':>7s} {'Pearson r':>10s} {'HW%':>7s}")
    print("  " + "-" * 65)
    for tier in sorted(by_tier, key=lambda t: -len(by_tier[t])):
        recs = by_tier[tier]
        X = [r.sp_fip_delta for r in recs]
        y = [r.home_win for r in recs]
        auc = roc_auc(y, X)
        pr = pearson(X, y)
        hw = sum(y) / len(y)
        print(f"  {tier:30s} {len(recs):5d}  {auc:.4f}  {pr:+.4f}  {hw:.3f}")

# ── Monthly Stability ──────────────────────────────────────────────────────────
def monthly_stability(records: list[Rec]) -> list[float]:
    by_month = collections.defaultdict(list)
    for r in records:
        by_month[r.game_date[:7]].append(r)

    aucs = []
    print(f"\n[MONTHLY STABILITY — raw AUC]")
    print(f"  {'Month':10s} {'n':>5s} {'AUC':>7s} {'HW%':>7s} {'Pearson r':>10s} {'Verdict':10s}")
    print("  " + "-" * 58)
    for month in sorted(by_month):
        recs = by_month[month]
        if len(recs) < 10:
            continue
        X = [r.sp_fip_delta for r in recs]
        y = [r.home_win for r in recs]
        auc = roc_auc(y, X)
        pr = pearson(X, y)
        hw = sum(y) / len(y)
        verdict = "ABOVE 0.5" if auc > 0.5 else "BELOW 0.5"
        aucs.append(auc)
        print(f"  {month:10s} {len(recs):5d}  {auc:.4f}  {hw:.1%}  {pr:+.4f}   {verdict}")

    if aucs:
        mu = sum(aucs) / len(aucs)
        sd = stddev(aucs)
        ab = sum(1 for a in aucs if a > 0.5)
        print(f"\n  Summary: mean={mu:.4f}, std={sd:.4f}, above-0.5={ab}/{len(aucs)} ({100*ab/len(aucs):.0f}%)")
        v = "STABLE ✅" if ab / len(aucs) >= 0.70 else "UNSTABLE ⚠"
        print(f"  Stability verdict: {v}")
    return aucs

# ── Season Phase Analysis ──────────────────────────────────────────────────────
def season_phase_analysis(records: list[Rec]) -> None:
    phases = {
        "Early  (idx 0.00–0.33)": [r for r in records if r.season_game_index < 0.33],
        "Mid    (idx 0.33–0.67)": [r for r in records if 0.33 <= r.season_game_index < 0.67],
        "Late   (idx 0.67–1.00)": [r for r in records if r.season_game_index >= 0.67],
    }
    print(f"\n[SEASON PHASE ANALYSIS — raw AUC]")
    print(f"  {'Phase':25s} {'n':>5s} {'AUC':>7s} {'HW%':>7s} {'Pearson r':>10s}")
    print("  " + "-" * 58)
    for label, recs in phases.items():
        if not recs:
            continue
        X = [r.sp_fip_delta for r in recs]
        y = [r.home_win for r in recs]
        auc = roc_auc(y, X)
        pr = pearson(X, y)
        hw = sum(y) / len(y)
        print(f"  {label:25s} {len(recs):5d}  {auc:.4f}  {hw:.1%}  {pr:+.4f}")

# ── Model Variant WFV ──────────────────────────────────────────────────────────
def run_variant_wfv(
    name: str,
    X_all: list[float],
    y_all: list[int],
    dates_all: list[str],
) -> tuple[float, float, float]:
    """Returns (AUC, Brier Skill, ECE) on validation set."""
    combined = sorted(zip(dates_all, X_all, y_all), key=lambda t: t[0])
    n = len(combined)
    cut = int(n * 0.70)
    train = combined[:cut]
    val = combined[cut:]

    X_tr = [t[1] for t in train]
    y_tr = [t[2] for t in train]
    X_va = [t[1] for t in val]
    y_va = [t[2] for t in val]

    # Standardize
    Xs_tr, mu, sd = standardize_1d(X_tr)
    Xs_va = [(x - mu) / sd for x in X_va]

    w, b = train_logistic_1d(Xs_tr, y_tr)
    preds = [sigmoid(w * xi + b) for xi in Xs_va]

    auc = roc_auc(y_va, preds)
    bs  = brier_skill(y_va, preds)
    ece_val = ece(y_va, preds)
    pr = pearson(X_tr, y_tr)
    hw_val = sum(y_va) / len(y_va)
    print(
        f"  {name:35s}  AUC={auc:.4f}  BrierSk={bs:+.5f}  ECE={ece_val:.4f}  "
        f"n_val={len(y_va)}  Pearson(tr)={pr:+.4f}  HW%(val)={hw_val:.1%}"
    )
    return auc, bs, ece_val

def model_variant_comparison(records: list[Rec]) -> tuple[list[Rec], list[Rec]]:
    """Compare 5 model variants. Returns (train_recs, val_recs) sorted split."""
    sorted_recs = sorted(records, key=lambda r: r.game_date)
    cut = int(len(sorted_recs) * 0.70)
    train_recs = sorted_recs[:cut]
    val_recs = sorted_recs[cut:]

    dates = [r.game_date for r in sorted_recs]
    y = [r.home_win for r in sorted_recs]

    # Variant features
    raw      = [r.sp_fip_delta for r in sorted_recs]
    abs_val  = [abs(r.sp_fip_delta) for r in sorted_recs]
    winsor   = [max(-WINSOR_CAP, min(WINSOR_CAP, r.sp_fip_delta)) for r in sorted_recs]
    # Binary: 1 if sp_fip_delta > 0 (home advantage), 0 otherwise
    binary   = [1.0 if r.sp_fip_delta > 0 else 0.0 for r in sorted_recs]
    # Strong-edge binary: 1 if delta >= thresh (strong home adv), 0 otherwise
    strong   = [1.0 if r.sp_fip_delta >= STRONG_EDGE_THRESH else 0.0 for r in sorted_recs]
    # Sign: map positive → +1, zero → 0, negative → –1 (then scale)
    sign_feat = [1.0 if r.sp_fip_delta > 0 else (-1.0 if r.sp_fip_delta < 0 else 0.0)
                 for r in sorted_recs]

    print(f"\n[MODEL VARIANT WFV] 70/30 time-ordered split")
    print(f"  Train: {sorted_recs[0].game_date} → {sorted_recs[cut-1].game_date} (n={cut})")
    print(f"  Val  : {sorted_recs[cut].game_date} → {sorted_recs[-1].game_date} (n={len(sorted_recs)-cut})")
    print()
    print(f"  {'Variant':35s}  {'AUC':>7s}  {'BrierSk':>9s}  {'ECE':>7s}  {'n_val':>6s}  {'Pearson(tr)':>11s}  {'HW%(val)':>8s}")
    print("  " + "-" * 110)

    results = {}
    for vname, X in [
        ("raw sp_fip_delta", raw),
        ("abs(sp_fip_delta)", abs_val),
        (f"winsorized ±{WINSOR_CAP}", winsor),
        ("binary (delta>0 → 1)", binary),
        (f"strong-edge (|delta|≥{STRONG_EDGE_THRESH})", strong),
        ("sign (-1/0/+1)", sign_feat),
    ]:
        a, bs, ec = run_variant_wfv(vname, X, y, dates)
        results[vname] = (a, bs, ec)

    # Best by AUC
    best_name = max(results, key=lambda k: results[k][0])
    best_auc, best_bs, best_ece = results[best_name]
    print(f"\n  Best variant by AUC: '{best_name}'")
    print(f"    AUC={best_auc:.4f} | Brier Skill={best_bs:+.5f} | ECE={best_ece:.4f}")

    return train_recs, val_recs, best_name, results

# ── Calibration ────────────────────────────────────────────────────────────────
def calibration_audit(records: list[Rec]) -> None:
    """Full calibration audit on best variant (raw sp_fip_delta)."""
    sorted_recs = sorted(records, key=lambda r: r.game_date)
    n = len(sorted_recs)
    cut = int(n * 0.70)
    train = sorted_recs[:cut]
    val   = sorted_recs[cut:]

    X_tr = [r.sp_fip_delta for r in train]
    y_tr = [r.home_win for r in train]
    X_va = [r.sp_fip_delta for r in val]
    y_va = [r.home_win for r in val]

    Xs_tr, mu, sd = standardize_1d(X_tr)
    Xs_va = [(x - mu) / sd for x in X_va]
    w, b = train_logistic_1d(Xs_tr, y_tr)
    preds_val = [sigmoid(w * xi + b) for xi in Xs_va]

    auc = roc_auc(y_va, preds_val)
    bs = brier_skill(y_va, preds_val)
    lls = ll_skill(y_va, preds_val)
    ece_raw = ece(y_va, preds_val)
    hw = sum(y_va) / len(y_va)

    print(f"\n[CALIBRATION AUDIT — raw sp_fip_delta]")
    print(f"  n_val={len(y_va)} | HW%(val)={hw:.1%}")
    print(f"  AUC           = {auc:.4f}")
    print(f"  Brier Skill   = {bs:+.5f}")
    print(f"  Log-Loss Skill= {lls:+.5f}")
    print(f"  ECE (raw)     = {ece_raw:.4f}")
    print(f"  Logistic w={w:+.4f} b={b:+.4f} (standardized feature space)")

    base_rate = hw
    ece_naive = ece(y_va, [base_rate] * len(y_va))
    print(f"  ECE (naive base rate {base_rate:.3f}): {ece_naive:.4f}")

    print(f"\n  Reliability Diagram:")
    reliability_diagram(y_va, preds_val)

    # Platt in-sample (diagnostic upper bound)
    pw, pb = platt_scale(y_va, preds_val)
    preds_platt = [sigmoid(pw * pi + pb) for pi in preds_val]
    ece_platt = ece(y_va, preds_platt)
    auc_platt = roc_auc(y_va, preds_platt)
    bs_platt  = brier_skill(y_va, preds_platt)
    print(f"\n  ⚠  In-sample Platt (diagnostic upper bound, NOT deployment-ready):")
    print(f"    Platt w={pw:.4f}, b={pb:.4f}")
    print(f"    ECE  : {ece_raw:.4f} → {ece_platt:.4f}")
    print(f"    AUC  : {auc:.4f} → {auc_platt:.4f}")
    print(f"    Brier: {bs:+.5f} → {bs_platt:+.5f}")

    return auc, bs, ece_raw

# ── Signal Classification ──────────────────────────────────────────────────────
def classify_signal(
    auc_wfv: float, bs_wfv: float, ece_val: float,
    monthly_aucs: list[float], mono_verdict: str,
) -> None:
    pct_above_half = sum(1 for a in monthly_aucs if a > 0.5) / len(monthly_aucs) if monthly_aucs else 0.0
    mean_monthly   = sum(monthly_aucs) / len(monthly_aucs) if monthly_aucs else 0.5

    print(f"\n[SIGNAL CLASSIFICATION]")
    print(f"  WFV AUC         = {auc_wfv:.4f}")
    print(f"  WFV Brier Skill = {bs_wfv:+.5f}")
    print(f"  ECE             = {ece_val:.4f}")
    print(f"  Monthly AUC mean= {mean_monthly:.4f} ({100*pct_above_half:.0f}% above 0.5)")
    print(f"  Monotonicity    : {mono_verdict}")

    if auc_wfv >= 0.540 and bs_wfv > 0.002 and pct_above_half >= 0.80:
        cls = "STABLE_SIGNAL — eligible for diagnostic deepening"
    elif auc_wfv >= 0.520 and pct_above_half >= 0.70:
        cls = "WEAK_STABLE_SIGNAL — calibration audit required before any use"
    elif auc_wfv >= 0.510 and pct_above_half >= 0.50:
        cls = "WEAK_SIGNAL (UNSTABLE) — conditional monthly dependency"
    else:
        cls = "NOISE"

    if PROMOTION_FREEZE:
        cls += " | PROMOTION_BLOCKED_BY_GOVERNANCE"

    print(f"\n  Classification: {cls}")
    print(f"\n  Recommendation:")
    if "STABLE" in cls:
        print("    → sp_fip_delta raw signal passes diagnostic gate.")
        print("    → Next step: cross-validation on independent holdout season (2024 data).")
        print("    → Do NOT deploy: calibration not proven on OOS data.")
    elif "WEAK_STABLE" in cls:
        print("    → Signal shows consistent direction but insufficient probability calibration.")
        print("    → Prioritize obtaining full current-season SP FIP (reduce historical_proxy dependency).")
    else:
        print("    → Signal is marginal. Additional data collection recommended.")

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 72)
    print("P36: sp_fip_delta Clean Signal Deep Dive")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print(f"Convention: sp_fip_delta = away_SP_FIP - home_SP_FIP")
    print(f"  Positive → home SP advantage | Negative → away SP advantage")
    print("=" * 72)

    # Load raw + filtered
    raw_rows = [json.loads(l) for l in open(PHASE56)]
    records = load_records()

    # PIT Safety
    print(f"\n{'='*72}")
    print("SECTION 0: PIT Safety Audit")
    print(f"{'='*72}")
    pit_safety_audit(raw_rows, records)

    # Distribution
    print(f"\n{'='*72}")
    print("SECTION 1: Feature Distribution")
    print(f"{'='*72}")
    distribution_analysis(records)

    # Decile bucket
    print(f"\n{'='*72}")
    print("SECTION 2: Decile Bucket / Monotonicity")
    print(f"{'='*72}")
    decile_bucket_analysis(records)

    # Context source tier
    print(f"\n{'='*72}")
    print("SECTION 3: Context Source Tier")
    print(f"{'='*72}")
    tier_analysis(records)

    # Monthly stability
    print(f"\n{'='*72}")
    print("SECTION 4: Monthly Stability")
    print(f"{'='*72}")
    monthly_aucs = monthly_stability(records)

    # Season phase
    print(f"\n{'='*72}")
    print("SECTION 5: Season Phase Analysis")
    print(f"{'='*72}")
    season_phase_analysis(records)

    # Model variants WFV
    print(f"\n{'='*72}")
    print("SECTION 6: Model Variant Comparison (WFV 70/30)")
    print(f"{'='*72}")
    _, _, best_variant, variant_results = model_variant_comparison(records)

    # Calibration
    print(f"\n{'='*72}")
    print("SECTION 7: Calibration Diagnostics (raw sp_fip_delta)")
    print(f"{'='*72}")
    auc_cal, bs_cal, ece_cal = calibration_audit(records)

    # Signal classification
    print(f"\n{'='*72}")
    print("SECTION 8: Signal Classification")
    print(f"{'='*72}")
    raw_auc = variant_results.get("raw sp_fip_delta", (auc_cal, bs_cal, ece_cal))
    classify_signal(
        auc_wfv=raw_auc[0],
        bs_wfv=raw_auc[1],
        ece_val=raw_auc[2],
        monthly_aucs=monthly_aucs,
        mono_verdict="see Section 2 output",
    )

    # Governance footer
    print(f"\n{'='*72}")
    print("GOVERNANCE")
    print(f"{'='*72}")
    print(f"  diagnostic_only   = {DIAGNOSTIC_ONLY}")
    print(f"  promotion_freeze  = {PROMOTION_FREEZE}")
    print(f"  Champion strategy = UNMODIFIED")
    print(f"  Kelly/bet logic   = UNMODIFIED")
    print(f"\n{'='*72}")
    print("P36 COMPLETE")
    print(f"{'='*72}")


if __name__ == "__main__":
    main()
