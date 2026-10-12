"""Phase 64-B data exploration script."""
import json
import re

PRED_PATH = "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
BULL_PATH = "data/mlb_context/bullpen_usage_3d.jsonl"

bull = [json.loads(l) for l in open(BULL_PATH)]
preds = [json.loads(l) for l in open(PRED_PATH)]


def norm(n: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", n.upper().replace(" ", "_"))


def parse_bull(gid: str):
    m = re.match(r"MLB-(\d{4})_(\d{2})_(\d{2})-.+-(.+)-AT-(.+)", gid)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", m.group(4), m.group(5)
    return None, None, None


# Build index by (date, norm_home)
bull_idx = {}
for b in bull:
    d, aw, hm = parse_bull(b["game_id"])
    if d:
        bull_idx[(d, norm(hm.replace("_", " ")))] = b

print(f"Bull index size: {len(bull_idx)}")
sample_key = list(bull_idx.keys())[10]
print(f"Sample bull key: {sample_key}")
print(f"Sample pred key: ({preds[0]['game_date']}, {norm(preds[0]['home_team'])})")

# Overall alignment
matched_rows = []
for p in preds:
    k = (p["game_date"], norm(p["home_team"]))
    if k in bull_idx:
        matched_rows.append(p)

matched = len(matched_rows)
print(f"\nAll predictions: {matched}/{len(preds)} = {100*matched/len(preds):.1f}%")

# Heavy fav coverage
hf = [p for p in preds if max(p["model_home_prob"], 1 - p["model_home_prob"]) >= 0.70]
hf_m = [p for p in hf if (p["game_date"], norm(p["home_team"])) in bull_idx]
print(f"Heavy_fav: {len(hf_m)}/{len(hf)} = {100*len(hf_m)/max(len(hf),1):.1f}%")

# High conf coverage
hc = [p for p in preds if max(p["model_home_prob"], 1 - p["model_home_prob"]) >= 0.75]
hc_m = [p for p in hc if (p["game_date"], norm(p["home_team"])) in bull_idx]
print(f"High_conf: {len(hc_m)}/{len(hc)} = {100*len(hc_m)/max(len(hc),1):.1f}%")

# Show a matched row
if matched_rows:
    p = matched_rows[0]
    b = bull_idx[(p["game_date"], norm(p["home_team"]))]
    print(f"\nSample match:")
    print(f"  pred: {p['game_date']} {p['home_team']} vs {p['away_team']}")
    print(f"  bull: {b}")
    print(f"  blend = {(1-0.4)*p['model_home_prob'] + 0.4*p['market_home_prob_no_vig']:.4f}")
    print(f"  home_win: {p['home_win']}")
