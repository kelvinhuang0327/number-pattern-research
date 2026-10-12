"""Phase 68 probe script — run once to gather statistics."""
import json
import statistics

rows = [
    json.loads(l)
    for l in open(
        "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
    )
]
print("Total rows:", len(rows))
print("model_versions:", set(r.get("model_version", "") for r in rows))
print("feature_versions:", set(r.get("feature_version", "") for r in rows))
print("source_backtest:", set(r.get("source_backtest", "") for r in rows))

mps = [r["model_home_prob"] for r in rows]
mkts = [r["market_home_prob_no_vig"] for r in rows]
print(
    f"model_home_prob: mean={sum(mps)/len(mps):.4f} "
    f"std={statistics.stdev(mps):.4f} "
    f"min={min(mps):.4f} max={max(mps):.4f}"
)
print(
    f"market_home_prob: mean={sum(mkts)/len(mkts):.4f} "
    f"std={statistics.stdev(mkts):.4f} "
    f"min={min(mkts):.4f} max={max(mkts):.4f}"
)

ALPHA = 0.40
blends = [(1 - ALPHA) * r["model_home_prob"] + ALPHA * r["market_home_prob_no_vig"] for r in rows]
fav_probs = [max(b, 1 - b) for b in blends]

buckets = {"50-55": 0, "55-60": 0, "60-65": 0, "65-70": 0, "70-75": 0, "75+": 0}
for fp in fav_probs:
    if fp < 0.55:
        buckets["50-55"] += 1
    elif fp < 0.60:
        buckets["55-60"] += 1
    elif fp < 0.65:
        buckets["60-65"] += 1
    elif fp < 0.70:
        buckets["65-70"] += 1
    elif fp < 0.75:
        buckets["70-75"] += 1
    else:
        buckets["75+"] += 1
print("fav_prob dist:", buckets)

model_fav = [max(r["model_home_prob"], 1 - r["model_home_prob"]) for r in rows]
mkt_fav = [max(r["market_home_prob_no_vig"], 1 - r["market_home_prob_no_vig"]) for r in rows]
print(
    f"model sharpness: mean={sum(model_fav)/len(model_fav):.4f} "
    f"std={statistics.stdev(model_fav):.4f}"
)
print(
    f"market sharpness: mean={sum(mkt_fav)/len(mkt_fav):.4f} "
    f"std={statistics.stdev(mkt_fav):.4f}"
)
print(
    f"blend sharpness: mean={sum(fav_probs)/len(fav_probs):.4f} "
    f"std={statistics.stdev(fav_probs):.4f}"
)

disagree = [abs(r["model_home_prob"] - r["market_home_prob_no_vig"]) for r in rows]
print(
    f"model-market disagreement: mean={sum(disagree)/len(disagree):.4f} "
    f"std={statistics.stdev(disagree):.4f} max={max(disagree):.4f}"
)

splits = sorted(set(r.get("split_id", "") for r in rows))
print("split_ids count:", len(splits), "first:", splits[:3])

# model vs market vs blend accuracy by confidence band
def brier(probs, labels):
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)

bands = [
    ("all", 0.0, 1.0),
    ("60-65", 0.60, 0.65),
    ("65-70", 0.65, 0.70),
    ("70-75", 0.70, 0.75),
    ("75+", 0.75, 1.01),
]
print("\n--- Brier by fav_prob band (model_only vs market_only vs blend) ---")
for band_name, lo, hi in bands:
    seg = [
        r for r, fp in zip(rows, fav_probs)
        if lo <= fp < hi
    ]
    if not seg:
        continue
    model_probs = [r["model_home_prob"] for r in seg]
    mkt_probs = [r["market_home_prob_no_vig"] for r in seg]
    blend_probs = [
        (1 - ALPHA) * r["model_home_prob"] + ALPHA * r["market_home_prob_no_vig"]
        for r in seg
    ]
    labels = [r["home_win"] for r in seg]
    mb = brier(model_probs, labels)
    mkb = brier(mkt_probs, labels)
    bb = brier(blend_probs, labels)
    wr = sum(labels) / len(labels)
    print(
        f"  {band_name:8s} n={len(seg):4d}  "
        f"model={mb:.4f}  mkt={mkb:.4f}  blend={bb:.4f}  "
        f"win_rate={wr:.3f}"
    )
