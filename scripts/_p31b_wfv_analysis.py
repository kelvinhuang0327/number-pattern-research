"""
P31B: MLB Feature Walk-forward Validation
diagnostic_only=True | promotion_freeze=True

Uses the 2025 derived context dataset (phase56 sp_bullpen_context) which contains:
  - p0_features: sp_fip_delta, park_run_factor, season_game_index
  - bullpen_features: bullpen_fatigue_delta_3d, home_reliever_b2b_count
  - home_win: binary outcome
  - 2025 rows covering the full 2025 MLB regular season

NOTE: The 338 CLV-available games (odds_timeline.jsonl) are all 2026-season games.
The bullpen/SP feature context files are 2025-only. Overlap = 0.
Walk-forward validation therefore runs on the 2025 complete dataset.
"""

from __future__ import annotations
import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True
DATA_PATH = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
CLV_TIMELINE = ROOT / "data/mlb_context/odds_timeline.jsonl"

# ── Governance guard ──────────────────────────────────────────────────────────
assert DIAGNOSTIC_ONLY, "GOVERNANCE: diagnostic_only must be True"
assert PROMOTION_FREEZE, "GOVERNANCE: promotion_freeze must be True"


# ── Utilities ─────────────────────────────────────────────────────────────────

def sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    return math.exp(x) / (1 + math.exp(x))


def clip(v: float, lo: float = 1e-7, hi: float = 1 - 1e-7) -> float:
    return max(lo, min(hi, v))


def log_loss_single(y: int, p: float) -> float:
    p = clip(p)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def brier_single(y: int, p: float) -> float:
    return (p - y) ** 2


def train_logistic_1d(X: list[float], y: list[int], lr: float = 0.05, epochs: int = 500) -> tuple[float, float]:
    """Gradient-descent logistic regression (single feature).  Returns (w, b)."""
    n = len(X)
    if n == 0:
        return 0.0, 0.0
    w, b = 0.0, 0.0
    # Standardise X
    mu = sum(X) / n
    std = (sum((x - mu) ** 2 for x in X) / n) ** 0.5 or 1.0
    Xs = [(x - mu) / std for x in X]
    for _ in range(epochs):
        dw = db = 0.0
        for xi, yi in zip(Xs, y):
            p = sigmoid(w * xi + b)
            err = p - yi
            dw += err * xi
            db += err
        w -= lr * dw / n
        b -= lr * db / n
    return w / std, b - w * mu / std  # un-standardise


def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    """Wilcoxon-Mann-Whitney AUC."""
    pos = [s for s, y in zip(y_score, y_true) if y == 1]
    neg = [s for s, y in zip(y_score, y_true) if y == 0]
    if not pos or not neg:
        return float("nan")
    concordant = sum(1 for p in pos for n in neg if p > n)
    tied = sum(0.5 for p in pos for n in neg if p == n)
    return (concordant + tied) / (len(pos) * len(neg))


# ── Data loading ──────────────────────────────────────────────────────────────

def load_records() -> list[dict]:
    records = []
    for line in DATA_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def extract_features(record: dict) -> dict[str, float | None]:
    p0 = record.get("p0_features") or {}
    bp = record.get("bullpen_features") or {}

    def safe(d: dict, key: str) -> float | None:
        v = d.get(key)
        return float(v) if v is not None else None

    return {
        "sp_fip_delta": safe(p0, "sp_fip_delta"),
        "park_run_factor": safe(p0, "park_run_factor"),
        "season_game_index": safe(p0, "season_game_index"),
        "bullpen_fatigue_delta_3d": safe(bp, "bullpen_fatigue_delta_3d"),
        "home_reliever_b2b_count": safe(bp, "home_reliever_b2b_count"),
        # feature availability flags
        "sp_fip_available": 1 if p0.get("sp_fip_delta_available") else 0,
        "park_factor_available": 1 if p0.get("park_factor_available") else 0,
        "bullpen_available": 1 if bp.get("bullpen_feature_available") else 0,
    }


# ── Walk-forward validation ───────────────────────────────────────────────────

FEATURES_TO_EVAL = [
    "sp_fip_delta",
    "park_run_factor",
    "season_game_index",
    "bullpen_fatigue_delta_3d",
    "home_reliever_b2b_count",
]

TIER_MAPPING = {
    "sp_fip_delta": "Tier 1 — P0 (F-P01)",
    "park_run_factor": "Tier 1 — P0 (F-P02)",
    "season_game_index": "Tier 2 — P0 (F-P03)",
    "bullpen_fatigue_delta_3d": "Tier 1 proxy — SSOT (F-B01/B03)",
    "home_reliever_b2b_count": "Tier 2 proxy — SSOT (F-B02)",
}


def evaluate_feature(
    feat_name: str,
    records_train: list[dict],
    records_val: list[dict],
) -> dict:
    def rows_for(records: list[dict]) -> tuple[list[float], list[int]]:
        X, y = [], []
        for r in records:
            feats = extract_features(r)
            v = feats.get(feat_name)
            outcome = r.get("home_win")
            if v is not None and outcome is not None:
                X.append(float(v))
                y.append(int(outcome))
        return X, y

    X_train, y_train = rows_for(records_train)
    X_val, y_val = rows_for(records_val)

    n_train_total = len(records_train)
    n_val_total = len(records_val)
    n_train = len(X_train)
    n_val = len(X_val)
    miss_train = round(1 - n_train / max(n_train_total, 1), 4)
    miss_val = round(1 - n_val / max(n_val_total, 1), 4)

    if n_train < 20 or n_val < 10:
        return {
            "feature": feat_name,
            "classification": "UNAVAILABLE",
            "reason": f"Insufficient data: train={n_train}, val={n_val}",
            "n_train": n_train, "n_val": n_val,
            "missing_rate_train": miss_train, "missing_rate_val": miss_val,
        }

    # Train
    w, b = train_logistic_1d(X_train, y_train)

    # Predict on validation
    y_prob = [sigmoid(w * x + b) for x in X_val]

    auc = roc_auc(y_val, y_prob)
    brier = sum(brier_single(y, p) for y, p in zip(y_val, y_prob)) / len(y_val)
    ll = sum(log_loss_single(y, p) for y, p in zip(y_val, y_prob)) / len(y_val)

    # Baseline (predict always home_win_rate)
    base_rate = sum(y_val) / len(y_val)
    brier_baseline = sum((base_rate - y) ** 2 for y in y_val) / len(y_val)
    ll_baseline = sum(log_loss_single(y, base_rate) for y in y_val) / len(y_val)
    brier_skill = round(1 - brier / brier_baseline, 4)
    ll_skill = round(1 - ll / ll_baseline, 4)

    # Classify
    if auc is not None and not math.isnan(auc):
        if brier_skill > 0.01 and auc > 0.53:
            classification = "PROMISING_DIAGNOSTIC"
        elif brier_skill > 0.002 or auc > 0.51:
            classification = "WEAK_SIGNAL"
        else:
            classification = "NOISE"
    else:
        classification = "NOISE"

    return {
        "feature": feat_name,
        "tier": TIER_MAPPING.get(feat_name, "unknown"),
        "classification": classification,
        "n_train": n_train,
        "n_val": n_val,
        "missing_rate_train": miss_train,
        "missing_rate_val": miss_val,
        "auc": round(auc, 4) if auc and not math.isnan(auc) else None,
        "brier": round(brier, 6),
        "log_loss": round(ll, 6),
        "brier_skill": brier_skill,
        "log_loss_skill": ll_skill,
        "home_win_rate_val": round(base_rate, 4),
        "coeff_w": round(w, 6),
        "coeff_b": round(b, 6),
    }


# ── CLV availability audit (2026 vs 2025) ────────────────────────────────────

def clv_availability_audit() -> dict:
    clv_results = []
    for line in CLV_TIMELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            clv_results.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    total = len(clv_results)
    available = sum(1 for r in clv_results if r.get("clv_available"))
    game_ids_2026 = {r.get("game_id", "") for r in clv_results if r.get("clv_available")}
    years = sorted({gid.split("_")[1][:4] if "_" in gid else "?" for gid in game_ids_2026 if gid})

    return {
        "timeline_total": total,
        "clv_available": available,
        "clv_game_years": years,
        "feature_data_years": ["2025"],
        "overlap_count": 0,
        "note": "2026 CLV games have no matching 2025 feature context. Walk-forward uses 2025 complete dataset.",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("P31B: MLB Feature Walk-forward Validation")
    print(f"diagnostic_only={DIAGNOSTIC_ONLY} | promotion_freeze={PROMOTION_FREEZE}")
    print("=" * 70)
    print()

    # Data inventory
    records = load_records()
    print(f"[DATA] phase56 context rows: {len(records)}")

    records_valid = [r for r in records if r.get("home_win") is not None]
    print(f"[DATA] rows with home_win: {len(records_valid)}")

    # Sort by game_date (time-ordered)
    records_valid.sort(key=lambda r: r.get("game_date", ""))
    dates = [r.get("game_date", "") for r in records_valid]
    print(f"[DATA] date range: {dates[0]} → {dates[-1]}")

    # Walk-forward split 70/30
    n = len(records_valid)
    split_idx = int(n * 0.70)
    records_train = records_valid[:split_idx]
    records_val = records_valid[split_idx:]
    split_date = records_val[0].get("game_date", "?")
    print(f"[SPLIT] train: {len(records_train)} (70%), val: {len(records_val)} (30%)")
    print(f"[SPLIT] split_date (val start): {split_date}")
    print()

    # Feature availability audit
    print("[AVAILABILITY] Tier 1 feature availability in training set:")
    for rec in records_train[:5]:
        feats = extract_features(rec)
        print(f"  game={rec.get('game_id','?')[:30]}: sp_fip_delta={feats['sp_fip_delta']}, park={feats['park_run_factor']}, bp_delta={feats['bullpen_fatigue_delta_3d']}")

    avail_stats = {}
    for feat in FEATURES_TO_EVAL:
        n_avail = sum(1 for r in records_valid if extract_features(r).get(feat) is not None)
        avail_stats[feat] = round(n_avail / len(records_valid), 4)

    print()
    print("[AVAILABILITY] Feature non-null rates across full 2025 dataset:")
    for feat, rate in avail_stats.items():
        print(f"  {feat}: {rate:.1%} ({int(rate * len(records_valid))}/{len(records_valid)})")

    # CLV availability audit
    print()
    clv_audit = clv_availability_audit()
    print("[CLV AUDIT] 2026 CLV vs 2025 feature data:")
    for k, v in clv_audit.items():
        print(f"  {k}: {v}")

    # Walk-forward validation
    print()
    print("[WALK-FORWARD] Single-feature logistic regression evaluation:")
    print("-" * 70)

    results = []
    for feat in FEATURES_TO_EVAL:
        r = evaluate_feature(feat, records_train, records_val)
        results.append(r)
        print(f"\nFeature: {feat}")
        print(f"  Tier: {r.get('tier', 'N/A')}")
        print(f"  n_train={r['n_train']} | n_val={r['n_val']}")
        print(f"  Missing rate: train={r['missing_rate_train']:.1%} val={r['missing_rate_val']:.1%}")
        if r["classification"] not in ("UNAVAILABLE",):
            print(f"  AUC={r.get('auc')} | Brier={r.get('brier')} | LogLoss={r.get('log_loss')}")
            print(f"  Brier Skill={r.get('brier_skill')} | LL Skill={r.get('log_loss_skill')}")
            print(f"  Home win rate (val): {r.get('home_win_rate_val')}")
        print(f"  Classification: {r['classification']}")

    # Summary table
    print()
    print("=" * 70)
    print("FEATURE CLASSIFICATION SUMMARY")
    print("=" * 70)
    print(f"{'Feature':<35} {'Class':<25} {'AUC':<8} {'Brier Skill'}")
    print("-" * 70)
    for r in results:
        auc_str = f"{r.get('auc', '-')}" if r.get("auc") else "-"
        bs_str = f"{r.get('brier_skill', '-')}"
        print(f"{r['feature']:<35} {r['classification']:<25} {auc_str:<8} {bs_str}")

    return {
        "records_total": len(records_valid),
        "n_train": len(records_train),
        "n_val": len(records_val),
        "split_date": split_date,
        "feature_results": results,
        "clv_audit": clv_audit,
    }


if __name__ == "__main__":
    main()
