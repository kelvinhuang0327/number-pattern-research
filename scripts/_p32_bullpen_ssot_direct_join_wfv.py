"""
P32: SSOT Bullpen Direct Join Walk-forward Validation
diagnostic_only=True | promotion_freeze=True

Directly joins:
  data/mlb_context/bullpen_usage_3d.jsonl  (SSOT, 2430 rows, game_id keyed)
  data/mlb_context/injury_rest.jsonl       (SSOT, 2430 rows, game_id keyed)
  data/mlb_2025/mlb-2025-asplayed.csv      (outcomes, date+team keyed)

Features evaluated:
  F-B01: bullpen_usage_last_3d_home   (raw innings pitched by bullpen)
  F-B01: bullpen_usage_last_3d_away
  F-B01d: bullpen_usage_diff          (home - away differential)
  F-B02: rest_days_home               (proxy for bullpen rest; from injury_rest)
  F-B02d: rest_days_diff              (home - away differential)

Walk-forward: time-ordered 70/30 split on joined 2025 games.
"""

from __future__ import annotations
import csv, json, math, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True
assert DIAGNOSTIC_ONLY, "GOVERNANCE: diagnostic_only must be True"
assert PROMOTION_FREEZE, "GOVERNANCE: promotion_freeze must be True"

BP_PATH    = ROOT / "data/mlb_context/bullpen_usage_3d.jsonl"
IR_PATH    = ROOT / "data/mlb_context/injury_rest.jsonl"
PLAYED_PATH = ROOT / "data/mlb_2025/mlb-2025-asplayed.csv"

# ── Team name normalization ────────────────────────────────────────────────────
# Special cases where simple capitalize() produces wrong output
TEAM_OVERRIDES: dict[str, str] = {
    "ST_LOUIS_CARDINALS": "St. Louis Cardinals",
    "ST_LOUIS_BROWNS": "St. Louis Browns",
}

def canon_to_display(raw: str) -> str:
    """Convert 'LOS_ANGELES_DODGERS' → 'Los Angeles Dodgers'."""
    if raw in TEAM_OVERRIDES:
        return TEAM_OVERRIDES[raw]
    return " ".join(w.capitalize() for w in raw.split("_"))


# ── Game-id parsing ────────────────────────────────────────────────────────────
_GID_RE = re.compile(r"MLB-(\d{4})_(\d{2})_(\d{2})-.*-AT-(.+)$")

def parse_gid(gid: str) -> tuple[str | None, str | None, str | None]:
    """Returns (iso_date, away_display, home_display) or (None, None, None)."""
    m = _GID_RE.match(gid)
    if not m:
        return None, None, None
    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # away: between time-token and -AT-
    m2 = re.search(r"\d{1,2}_\d{2}_(AM|PM)-(.+)-AT-", gid)
    away_raw = m2.group(2) if m2 else ""
    home_raw = m.group(4)
    return date, canon_to_display(away_raw), canon_to_display(home_raw)


# ── Data loading ───────────────────────────────────────────────────────────────
def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_asplayed(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── Build join lookup ─────────────────────────────────────────────────────────
def build_bp_lookup(bp_records: list[dict]) -> dict[tuple, dict]:
    lookup: dict[tuple, dict] = {}
    skipped = 0
    for r in bp_records:
        date, _, home = parse_gid(r["game_id"])
        if not date:
            skipped += 1
            continue
        key = (date, home)
        if key not in lookup:
            lookup[key] = r
    return lookup, skipped


def build_ir_lookup(ir_records: list[dict]) -> dict[tuple, dict]:
    lookup: dict[tuple, dict] = {}
    for r in ir_records:
        date, _, home = parse_gid(r["game_id"])
        if date:
            key = (date, home)
            if key not in lookup:
                lookup[key] = r
    return lookup


# ── Math helpers (pure Python, no sklearn) ────────────────────────────────────
def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-max(-500, min(500, x))))


def train_logistic_1d(
    X: list[float], y: list[int], lr: float = 0.05, epochs: int = 600
) -> tuple[float, float]:
    n = len(X)
    if n == 0:
        return 0.0, 0.0
    mu = sum(X) / n
    std = math.sqrt(sum((v - mu) ** 2 for v in X) / n) or 1.0
    Xs = [(v - mu) / std for v in X]
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
    return -sum(yi * math.log(clip(pi)) + (1 - yi) * math.log(1 - clip(pi)) for pi, yi in zip(p, y)) / len(y)


# ── Feature evaluation ─────────────────────────────────────────────────────────
def evaluate_feature(
    name: str,
    records: list[dict],
    split_idx: int,
) -> dict:
    train_r = records[:split_idx]
    val_r   = records[split_idx:]

    def extract(subset: list[dict]) -> tuple[list[float], list[int]]:
        X, y = [], []
        for r in subset:
            v = r.get(name)
            hw = r.get("home_win")
            if v is not None and hw is not None:
                X.append(float(v))
                y.append(int(hw))
        return X, y

    X_tr, y_tr = extract(train_r)
    X_vl, y_vl = extract(val_r)

    miss_tr = round(1 - len(X_tr) / max(len(train_r), 1), 4)
    miss_vl = round(1 - len(X_vl) / max(len(val_r), 1), 4)

    if len(X_tr) < 20 or len(X_vl) < 10:
        return {
            "feature": name, "classification": "UNAVAILABLE",
            "reason": f"train={len(X_tr)}, val={len(X_vl)}",
            "n_train": len(X_tr), "n_val": len(X_vl),
            "missing_train": miss_tr, "missing_val": miss_vl,
        }

    w, b = train_logistic_1d(X_tr, y_tr)
    y_prob = [sigmoid(w * x + b) for x in X_vl]

    auc = roc_auc(y_vl, y_prob)
    br  = brier(y_vl, y_prob)
    ll  = log_loss(y_vl, y_prob)

    base = sum(y_vl) / len(y_vl)
    br_base = brier(y_vl, [base] * len(y_vl))
    ll_base = log_loss(y_vl, [base] * len(y_vl))

    br_skill = round(1 - br / br_base, 4)
    ll_skill = round(1 - ll / ll_base, 4)

    # Classify
    if not math.isnan(auc) and auc > 0.53 and br_skill > 0.01:
        cls = "PROMISING_DIAGNOSTIC"
    elif not math.isnan(auc) and (auc > 0.51 or br_skill > 0.002):
        cls = "WEAK_SIGNAL"
    else:
        cls = "NOISE"

    return {
        "feature": name,
        "classification": cls,
        "n_train": len(X_tr), "n_val": len(X_vl),
        "missing_train": miss_tr, "missing_val": miss_vl,
        "auc": round(auc, 4), "brier": round(br, 6),
        "log_loss": round(ll, 6), "brier_skill": br_skill,
        "ll_skill": ll_skill, "home_win_rate_val": round(base, 4),
        "coeff_w": round(w, 6), "coeff_b": round(b, 6),
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("P32: SSOT Bullpen Direct Join Walk-forward Validation")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print("=" * 70)

    # ── Load sources
    bp_records = load_jsonl(BP_PATH)
    ir_records = load_jsonl(IR_PATH)
    asplayed   = load_asplayed(PLAYED_PATH)

    print(f"\n[DATA INVENTORY]")
    print(f"  bullpen_usage_3d.jsonl : {len(bp_records)} rows")
    print(f"  injury_rest.jsonl      : {len(ir_records)} rows")
    print(f"  mlb-2025-asplayed.csv  : {len(asplayed)} rows")

    # ── Field availability in bp source
    print(f"\n[BP SOURCE FIELD AVAILABILITY]")
    for field in ["bullpen_usage_last_3d_home", "bullpen_usage_last_3d_away"]:
        n = sum(1 for r in bp_records if r.get(field) is not None)
        print(f"  {field}: {n}/{len(bp_records)} ({100*n//len(bp_records)}%)")
    for field in ["closer_used_last_1d_home", "closer_used_last_1d_away", "bullpen_rest_imbalance"]:
        n = sum(1 for r in bp_records if r.get(field) is not None)
        print(f"  {field}: {n}/{len(bp_records)} ({100*n//len(bp_records)}%) — NOT IN SSOT FILE")

    # ── Build lookups
    bp_lookup, bp_skipped = build_bp_lookup(bp_records)
    ir_lookup = build_ir_lookup(ir_records)
    print(f"\n[JOIN SETUP]")
    print(f"  BP lookup keys: {len(bp_lookup)} (unparsed: {bp_skipped})")
    print(f"  IR lookup keys: {len(ir_lookup)}")

    # ── Join asplayed with SSOT
    joined: list[dict] = []
    bp_miss = ir_miss = 0

    for row in asplayed:
        date  = row.get("date", "")
        home  = row.get("home_team", "")
        status = row.get("status", "")
        home_win_raw = row.get("home_win")

        if not date or not home:
            continue
        # Only use Final games
        if status != "Final":
            continue

        try:
            hw = int(float(home_win_raw)) if home_win_raw not in (None, "", "nan") else None
        except (ValueError, TypeError):
            hw = None

        if hw is None:
            continue

        key = (date, home)
        bp_row = bp_lookup.get(key)
        ir_row = ir_lookup.get(key)

        if bp_row is None:
            bp_miss += 1
        if ir_row is None:
            ir_miss += 1

        bp_home = bp_row.get("bullpen_usage_last_3d_home") if bp_row else None
        bp_away = bp_row.get("bullpen_usage_last_3d_away") if bp_row else None
        rest_home = ir_row.get("rest_days_home") if ir_row else None
        rest_away = ir_row.get("rest_days_away") if ir_row else None

        joined.append({
            "date": date,
            "home_team": home,
            "home_win": hw,
            "bullpen_usage_last_3d_home": bp_home,
            "bullpen_usage_last_3d_away": bp_away,
            "bullpen_usage_diff": (bp_home - bp_away) if (bp_home is not None and bp_away is not None) else None,
            "rest_days_home": rest_home,
            "rest_days_away": rest_away,
            "rest_days_diff": (rest_home - rest_away) if (rest_home is not None and rest_away is not None) else None,
        })

    n_final  = sum(1 for r in asplayed if r.get("status") == "Final")
    bp_hit   = len(joined) - bp_miss  # approximate — actually we count bp misses separately
    bp_hit   = sum(1 for r in joined if r["bullpen_usage_last_3d_home"] is not None)
    ir_hit   = sum(1 for r in joined if r["rest_days_home"] is not None)
    total_j  = len(joined)

    print(f"\n[JOIN RESULTS]")
    print(f"  Final games in asplayed       : {n_final}")
    print(f"  Joined rows (Final + outcome) : {total_j}")
    print(f"  BP hit (bullpen_usage non-null): {bp_hit}/{total_j} ({100*bp_hit//max(total_j,1)}%)")
    print(f"  IR hit (rest_days non-null)   : {ir_hit}/{total_j} ({100*ir_hit//max(total_j,1)}%)")
    print(f"  BP miss (game_id not in lookup): {bp_miss}")
    print(f"  IR miss (game_id not in lookup): {ir_miss}")

    # ── Feature availability in joined set
    print(f"\n[FEATURE AVAILABILITY IN JOINED SET]")
    for feat in ["bullpen_usage_last_3d_home", "bullpen_usage_last_3d_away",
                 "bullpen_usage_diff", "rest_days_home", "rest_days_away", "rest_days_diff"]:
        n = sum(1 for r in joined if r.get(feat) is not None)
        print(f"  {feat}: {n}/{total_j} ({100*n//max(total_j,1)}%)")

    # Check variance
    print(f"\n[BULLPEN USAGE VALUE STATS (non-null)]")
    bp_vals = [r["bullpen_usage_last_3d_home"] for r in joined if r.get("bullpen_usage_last_3d_home") is not None]
    if bp_vals:
        mu = sum(bp_vals) / len(bp_vals)
        std = math.sqrt(sum((v - mu) ** 2 for v in bp_vals) / len(bp_vals))
        print(f"  bullpen_usage_last_3d_home: n={len(bp_vals)}, mean={mu:.2f}, std={std:.2f}, min={min(bp_vals):.2f}, max={max(bp_vals):.2f}")
    diff_vals = [r["bullpen_usage_diff"] for r in joined if r.get("bullpen_usage_diff") is not None]
    if diff_vals:
        mu = sum(diff_vals) / len(diff_vals)
        std = math.sqrt(sum((v - mu) ** 2 for v in diff_vals) / len(diff_vals))
        print(f"  bullpen_usage_diff:         n={len(diff_vals)}, mean={mu:.3f}, std={std:.3f}, min={min(diff_vals):.2f}, max={max(diff_vals):.2f}")

    rest_vals = [r["rest_days_home"] for r in joined if r.get("rest_days_home") is not None]
    if rest_vals:
        mu = sum(rest_vals) / len(rest_vals)
        std = math.sqrt(sum((v - mu) ** 2 for v in rest_vals) / len(rest_vals))
        print(f"  rest_days_home:             n={len(rest_vals)}, mean={mu:.2f}, std={std:.2f}, min={min(rest_vals):.2f}, max={max(rest_vals):.2f}")

    # ── Walk-forward split (time-ordered)
    joined.sort(key=lambda r: r["date"])
    split_idx = int(len(joined) * 0.70)
    split_date = joined[split_idx]["date"] if joined else "?"
    print(f"\n[WALK-FORWARD SPLIT]")
    print(f"  Total: {len(joined)} | Train: {split_idx} (70%) | Val: {len(joined)-split_idx} (30%)")
    print(f"  Train: {joined[0]['date']} → {joined[split_idx-1]['date']}")
    print(f"  Val  : {split_date} → {joined[-1]['date']}")

    # P31B neutral baseline for comparison
    P31B_BASELINE = {
        "bullpen_fatigue_delta_3d": {"auc": 0.500, "brier_skill": -0.0002, "classification": "NOISE (constant-zero fallback)"},
        "home_reliever_b2b_count": {"auc": 0.500, "brier_skill": -0.0002, "classification": "NOISE (constant-zero fallback)"},
    }

    # ── Evaluate each feature
    features_to_eval = [
        "bullpen_usage_last_3d_home",
        "bullpen_usage_last_3d_away",
        "bullpen_usage_diff",
        "rest_days_home",
        "rest_days_away",
        "rest_days_diff",
    ]

    TIER_MAP = {
        "bullpen_usage_last_3d_home": "SSOT F-B01 (home)",
        "bullpen_usage_last_3d_away": "SSOT F-B01 (away)",
        "bullpen_usage_diff":         "SSOT F-B01 differential",
        "rest_days_home":             "SSOT F-B02 proxy (home)",
        "rest_days_away":             "SSOT F-B02 proxy (away)",
        "rest_days_diff":             "SSOT F-B02 proxy differential",
    }

    print(f"\n[WALK-FORWARD EVALUATION]")
    print("-" * 70)
    results = []
    for feat in features_to_eval:
        r = evaluate_feature(feat, joined, split_idx)
        results.append(r)
        print(f"\nFeature : {feat}")
        print(f"  Tier   : {TIER_MAP.get(feat,'?')}")
        print(f"  Train  : {r['n_train']} rows | Val: {r['n_val']} rows")
        print(f"  Missing: train={r['missing_train']:.1%} val={r['missing_val']:.1%}")
        if r["classification"] != "UNAVAILABLE":
            print(f"  AUC={r.get('auc')} | Brier Skill={r.get('brier_skill')} | LL Skill={r.get('ll_skill')}")
            print(f"  Home win rate (val): {r.get('home_win_rate_val')}")
        print(f"  Classification: {r['classification']}")

    # ── Summary table
    print(f"\n{'='*70}")
    print("P32 FEATURE CLASSIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"{'Feature':<35} {'Class':<25} {'AUC':<8} {'Brier Skill'}")
    print("-" * 70)
    for r in results:
        auc_s = str(r.get("auc", "-"))
        bs_s  = str(r.get("brier_skill", "-"))
        print(f"{r['feature']:<35} {r['classification']:<25} {auc_s:<8} {bs_s}")

    # ── Compare vs P31B
    print(f"\n[P31B vs P32 COMPARISON]")
    print(f"  P31B bullpen_fatigue_delta_3d (neutral fallback): AUC=0.500, Brier Skill=-0.0002, NOISE")
    bp_diff_r = next((r for r in results if r["feature"] == "bullpen_usage_diff"), None)
    if bp_diff_r and bp_diff_r.get("auc"):
        improvement = round(bp_diff_r["auc"] - 0.500, 4)
        print(f"  P32 bullpen_usage_diff (SSOT real values): AUC={bp_diff_r['auc']}, Brier Skill={bp_diff_r.get('brier_skill')}")
        print(f"  Delta AUC vs P31B neutral: {improvement:+.4f}")

    print(f"\n[GOVERNANCE]")
    print(f"  diagnostic_only    = {DIAGNOSTIC_ONLY}")
    print(f"  promotion_freeze   = {PROMOTION_FREEZE}")
    print("  Champion strategy  = UNMODIFIED")
    print("  Kelly/betting logic= UNMODIFIED")
    print("  Live APIs called   = NONE")
    print(f"\n{'='*70}")
    print("P32 COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
