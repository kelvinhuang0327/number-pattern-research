"""Phase 68 Probe 2 — Calibration residuals, disagreement analysis, heavy fav deep dive."""
import json, math
from collections import Counter

ALPHA = 0.40
rows = [json.loads(l) for l in open("data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl")]

for r in rows:
    r["_blend"] = (1-ALPHA)*r["model_home_prob"] + ALPHA*r["market_home_prob_no_vig"]
    r["_fav_prob"] = max(r["_blend"], 1-r["_blend"])
    r["_fav_is_home"] = r["_blend"] >= 0.5
    r["_fav_win"] = r["home_win"] if r["_fav_is_home"] else 1 - r["home_win"]
    r["_model_fav_prob"] = max(r["model_home_prob"], 1-r["model_home_prob"])
    r["_mkt_fav_prob"] = max(r["market_home_prob_no_vig"], 1-r["market_home_prob_no_vig"])
    r["_disagree"] = r["model_home_prob"] - r["market_home_prob_no_vig"]

def brier(probs, labels):
    if not probs: return 0.0
    return sum((p-y)**2 for p,y in zip(probs,labels))/len(probs)

# === MODEL VERSION DISTRIBUTION ===
print("\n=== MODEL VERSIONS ===")
for mv, cnt in Counter(r.get("model_version","") for r in rows).most_common():
    print(f"  {mv}: {cnt}")

# === CALIBRATION RESIDUAL BY BLEND FAV_PROB BAND ===
print("\n=== CALIBRATION RESIDUAL (blend fav_prob - actual fav_win_rate) ===")
for lo, hi in [(0.50,0.55),(0.55,0.60),(0.60,0.65),(0.65,0.70),(0.70,0.75),(0.75,1.01)]:
    seg = [r for r in rows if lo <= r["_fav_prob"] < hi]
    if not seg:
        continue
    mean_pred = sum(r["_fav_prob"] for r in seg)/len(seg)
    mean_actual = sum(r["_fav_win"] for r in seg)/len(seg)
    residual = mean_pred - mean_actual
    model_mean = sum(r["_model_fav_prob"] for r in seg)/len(seg)
    mkt_mean = sum(r["_mkt_fav_prob"] for r in seg)/len(seg)
    print(f"  {lo:.2f}-{hi:.2f}: n={len(seg):4d}  blend_pred={mean_pred:.4f}  actual={mean_actual:.4f}  "
          f"residual={residual:+.4f}  model_pred={model_mean:.4f}  mkt_pred={mkt_mean:.4f}")

# === MODEL CONFIDENCE BAND (model_fav_prob) CALIBRATION ===
print("\n=== MODEL CONFIDENCE BAND CALIBRATION (model_fav_prob bands) ===")
for lo, hi in [(0.50,0.55),(0.55,0.60),(0.60,0.65),(0.65,0.70),(0.70,0.75),(0.75,1.01)]:
    seg = [r for r in rows if lo <= r["_model_fav_prob"] < hi]
    if not seg:
        continue
    model_pred = sum(r["_model_fav_prob"] for r in seg)/len(seg)
    blend_pred = sum(r["_fav_prob"] for r in seg)/len(seg)
    mkt_pred = sum(r["_mkt_fav_prob"] for r in seg)/len(seg)
    actual = sum(r["_fav_win"] for r in seg)/len(seg)
    model_b = brier([r["_model_fav_prob"] for r in seg], [r["_fav_win"] for r in seg])
    mkt_b = brier([r["_mkt_fav_prob"] for r in seg], [r["_fav_win"] for r in seg])
    blend_b = brier([r["_fav_prob"] for r in seg], [r["_fav_win"] for r in seg])
    print(f"  {lo:.2f}-{hi:.2f}: n={len(seg):4d}  model_pred={model_pred:.4f}  actual={actual:.4f}  "
          f"residual={model_pred-actual:+.4f}  model_b={model_b:.4f} mkt_b={mkt_b:.4f} blend_b={blend_b:.4f}")

# === DISAGREEMENT ANALYSIS ===
print("\n=== MODEL-MARKET DISAGREEMENT ANALYSIS ===")
bands = [
    ("model_large_fav (model > mkt by 5%+)",  0.05, 1.0),
    ("mkt_large_fav  (mkt > model by 5%+)",  -1.0, -0.05),
    ("agree          (diff < 5%)",            -0.05, 0.05),
]
for name, lo, hi in bands:
    seg = [r for r in rows if lo <= r["_disagree"] < hi]
    if not seg:
        continue
    blend_b = brier([r["_blend"] for r in seg], [r["home_win"] for r in seg])
    mkt_b = brier([r["market_home_prob_no_vig"] for r in seg], [r["home_win"] for r in seg])
    model_b = brier([r["model_home_prob"] for r in seg], [r["home_win"] for r in seg])
    print(f"  {name:40s} n={len(seg):4d}  model_b={model_b:.4f} mkt_b={mkt_b:.4f} blend_b={blend_b:.4f}")

# === HEAVY FAVORITE DEEP DIVE ===
print("\n=== HEAVY FAVORITE DEEP DIVE (fav_prob >= 0.70) ===")
hf = [r for r in rows if r["_fav_prob"] >= 0.70]
print(f"  n={len(hf)}")
print(f"  fav_win_rate={sum(r['_fav_win'] for r in hf)/len(hf):.4f}")
print(f"  mean_blend_fav_prob={sum(r['_fav_prob'] for r in hf)/len(hf):.4f}")
print(f"  mean_model_fav_prob={sum(r['_model_fav_prob'] for r in hf)/len(hf):.4f}")
print(f"  mean_mkt_fav_prob={sum(r['_mkt_fav_prob'] for r in hf)/len(hf):.4f}")
blend_b = brier([r["_fav_prob"] for r in hf], [r["_fav_win"] for r in hf])
model_b = brier([r["_model_fav_prob"] for r in hf], [r["_fav_win"] for r in hf])
mkt_b = brier([r["_mkt_fav_prob"] for r in hf], [r["_fav_win"] for r in hf])
print(f"  model_brier={model_b:.4f}  mkt_brier={mkt_b:.4f}  blend_brier={blend_b:.4f}")
print(f"  BSS(blend vs mkt)={1-blend_b/mkt_b:.4f}  BSS(model vs mkt)={1-model_b/mkt_b:.4f}")

# === NEGATIVE CONTROL: shuffled confidence bucket ===
print("\n=== NEGATIVE CONTROL: SHUFFLED CONFIDENCE BUCKET ===")
import random
random.seed(42)
shuffled_fp = [r["_fav_prob"] for r in rows]
random.shuffle(shuffled_fp)
actual_wins = [r["_fav_win"] for r in rows]
shuffled_b = brier(shuffled_fp, actual_wins)
real_b = brier([r["_fav_prob"] for r in rows], actual_wins)
ref_b = brier([0.5]*len(rows), actual_wins)
print(f"  ref_brier (naive 0.5): {ref_b:.4f}")
print(f"  real_brier:            {real_b:.4f}")
print(f"  shuffled_brier:        {shuffled_b:.4f}")
print(f"  BSS(real):             {1-real_b/ref_b:+.4f}")
print(f"  BSS(shuffled):         {1-shuffled_b/ref_b:+.4f}")
print(f"  (if BSS real ≈ BSS shuffled → overfit signal)")

# === ECE CALCULATION ===
print("\n=== ECE (Expected Calibration Error) ===")
def ece(probs, labels, n_bins=10):
    bins = [[] for _ in range(n_bins)]
    for p, y in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins-1)
        bins[idx].append((p, y))
    total = len(probs)
    ece_val = sum(len(b)/total * abs(sum(p for p,y in b)/len(b) - sum(y for p,y in b)/len(b))
                  for b in bins if b)
    return ece_val

all_blend = [r["_blend"] for r in rows]
all_model = [r["model_home_prob"] for r in rows]
all_mkt = [r["market_home_prob_no_vig"] for r in rows]
all_hw = [r["home_win"] for r in rows]

print(f"  ECE(blend):  {ece(all_blend, all_hw):.4f}")
print(f"  ECE(model):  {ece(all_model, all_hw):.4f}")
print(f"  ECE(market): {ece(all_mkt, all_hw):.4f}")

# Heavy fav ECE
hf_blend = [r["_fav_prob"] for r in hf]
hf_wins = [r["_fav_win"] for r in hf]
hf_model = [r["_model_fav_prob"] for r in hf]
hf_mkt = [r["_mkt_fav_prob"] for r in hf]
print(f"\n  Heavy fav (>=0.70) ECE:")
print(f"    ECE(blend):  {ece(hf_blend, hf_wins):.4f}")
print(f"    ECE(model):  {ece(hf_model, hf_wins):.4f}")
print(f"    ECE(market): {ece(hf_mkt, hf_wins):.4f}")

print("\n=== DONE ===")
