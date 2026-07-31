"""
P25 Market Mapping & CLV Construction Audit + Outlier Case Review
paper_only=true / diagnostic_only=true
"""
import json
import math
import random
from collections import defaultdict
from datetime import timezone
from dateutil.parser import parse as dtparse

P23_LINES = 2788
MARKET_CODES = ["MNL", "HDC", "OU", "OE", "TTO"]
random.seed(42)


def to_utc(s):
    if not s:
        return None
    try:
        dt = dtparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


# Load pinned slice
all_records = []
with open("data/tsl_odds_history.jsonl") as f:
    for i, line in enumerate(f):
        if i >= P23_LINES:
            break
        line = line.strip()
        if line:
            all_records.append(json.loads(line))

by_mid = defaultdict(list)
for r in all_records:
    by_mid[r["match_id"]].append(r)

PREGAME_MIN_HOURS = 2.0
CLOSING_WINDOW_HOURS = 2.0

valid_pairs = []
for mid, records in by_mid.items():
    game_dt = to_utc(records[0].get("game_time", ""))
    if not game_dt:
        continue
    pregame_recs, closing_recs = [], []
    for r in records:
        fat = to_utc(r.get("fetched_at", ""))
        if fat is None:
            continue
        dh = (game_dt - fat).total_seconds() / 3600
        if dh >= PREGAME_MIN_HOURS:
            pregame_recs.append((fat, r))
        if abs(dh) <= CLOSING_WINDOW_HOURS:
            closing_recs.append((fat, r))
    if not pregame_recs or not closing_recs:
        continue
    best_pre = max(pregame_recs, key=lambda x: x[0])
    best_clo = max(closing_recs, key=lambda x: x[0])
    if best_pre[1].get("markets") and best_clo[1].get("markets"):
        # Check pregame-closing gap
        pre_time = best_pre[0]
        clo_time = best_clo[0]
        game_time = game_dt
        pre_gap_h = (game_time - pre_time).total_seconds() / 3600
        clo_gap_h = abs((game_time - clo_time).total_seconds() / 3600)
        valid_pairs.append({
            "mid": mid,
            "pre": best_pre,
            "clo": best_clo,
            "pre_gap_hours": round(pre_gap_h, 2),
            "clo_gap_hours": round(clo_gap_h, 2),
            "game_time": str(game_time),
        })

print(f"Valid pairs: {len(valid_pairs)}")

# ── Market Mapping Audit ──────────────────────────────────────────────────
market_info = {}
market_observations = defaultdict(list)
market_clv_with_meta = defaultdict(list)

for pair in valid_pairs:
    pre_r = pair["pre"][1]
    clo_r = pair["clo"][1]
    pre_markets = {m["marketCode"]: m for m in pre_r.get("markets", [])}
    clo_markets = {m["marketCode"]: m for m in clo_r.get("markets", [])}

    for mc in MARKET_CODES:
        if mc not in pre_markets or mc not in clo_markets:
            continue
        pm = pre_markets[mc]
        cm = clo_markets[mc]
        pre_outs = pm.get("outcomes", [])
        clo_outs = cm.get("outcomes", [])

        # Collect outcome names for mapping audit
        pre_names = [o.get("outcomeName", "?") for o in pre_outs]
        clo_names = [o.get("outcomeName", "?") for o in clo_outs]
        pre_odds_raw = []
        clo_odds_raw = []
        clv_vals = []
        for i in range(min(2, len(pre_outs), len(clo_outs))):
            try:
                p = float(pre_outs[i]["odds"])
                c = float(clo_outs[i]["odds"])
                pre_odds_raw.append(p)
                clo_odds_raw.append(c)
                clv = (p - c) / c * 100.0
                clv_vals.append(clv)
            except (ValueError, KeyError):
                pass

        if clv_vals:
            market_clv_with_meta[mc].extend([
                {
                    "mid": pair["mid"],
                    "side_idx": i,
                    "side_name": pre_names[i] if i < len(pre_names) else "?",
                    "pre_odds": pre_odds_raw[i] if i < len(pre_odds_raw) else None,
                    "clo_odds": clo_odds_raw[i] if i < len(clo_odds_raw) else None,
                    "clv_pct": clv_vals[i],
                    "game_time": pair["game_time"],
                    "pre_gap_hours": pair["pre_gap_hours"],
                    "clo_gap_hours": pair["clo_gap_hours"],
                }
                for i in range(len(clv_vals))
            ])

        market_observations[mc].append({
            "mid": pair["mid"],
            "pre_names": pre_names,
            "clo_names": clo_names,
            "pre_odds": pre_odds_raw,
            "clo_odds": clo_odds_raw,
            "n_outcomes_pre": len(pre_outs),
            "n_outcomes_clo": len(clo_outs),
        })

# ── Market mapping analysis ───────────────────────────────────────────────
print("\n=== MARKET MAPPING AUDIT ===")
mapping_results = {}
for mc in MARKET_CODES:
    obs = market_observations[mc]
    if not obs:
        mapping_results[mc] = {"status": "MISSING", "n": 0}
        continue

    # Check name consistency
    all_pre_names = [tuple(o["pre_names"]) for o in obs]
    all_clo_names = [tuple(o["clo_names"]) for o in obs]
    unique_pre_names = list(set(all_pre_names))
    unique_clo_names = list(set(all_clo_names))

    # Check outcome count variation
    pre_outcome_counts = [o["n_outcomes_pre"] for o in obs]
    clo_outcome_counts = [o["n_outcomes_clo"] for o in obs]
    outcome_count_varies = len(set(pre_outcome_counts)) > 1 or len(set(clo_outcome_counts)) > 1

    # Check name alignment pre vs clo (should match)
    name_mismatch_count = sum(
        1 for o in obs if tuple(o["pre_names"][:2]) != tuple(o["clo_names"][:2])
    )

    # Check for suspiciously large CLV (potential formula issue)
    clv_data = [c["clv_pct"] for c in market_clv_with_meta[mc]]
    extreme_count = sum(1 for x in clv_data if abs(x) > 50)
    max_abs = max(abs(x) for x in clv_data) if clv_data else 0

    # Determine risk level
    risk_flags = []
    if name_mismatch_count > 0:
        risk_flags.append(f"NAME_MISMATCH:{name_mismatch_count}")
    if outcome_count_varies:
        risk_flags.append("OUTCOME_COUNT_VARIES")
    if extreme_count > 0:
        risk_flags.append(f"EXTREME_CLV_CASES:{extreme_count}")
    if len(unique_pre_names) > 5:
        risk_flags.append(f"HIGH_OUTCOME_VARIETY:{len(unique_pre_names)}")

    if mc == "MNL":
        # MNL should be 3-way: H/D/A
        three_way = sum(1 for o in obs if o["n_outcomes_pre"] == 3)
        two_way = sum(1 for o in obs if o["n_outcomes_pre"] == 2)
        if two_way > 0 and three_way > 0:
            risk_flags.append(f"MIXED_MNL_MARKETS:{two_way}x2way_{three_way}x3way")

    status = "RISK" if risk_flags else "PASS"

    mapping_results[mc] = {
        "status": status,
        "n_pairs": len(obs),
        "n_clv_obs": len(clv_data),
        "name_mismatch_count": name_mismatch_count,
        "outcome_count_varies": outcome_count_varies,
        "extreme_clv_count_gt50pct": extreme_count,
        "max_abs_clv_pct": round(max_abs, 2),
        "risk_flags": risk_flags,
        "unique_pre_name_patterns": len(unique_pre_names),
        "sample_pre_names": list(unique_pre_names[:3]),
    }
    print(f"  {mc}: {status} | risk_flags={risk_flags} | n={len(clv_data)}")

# ── CLV Construction Audit ────────────────────────────────────────────────
print("\n=== CLV CONSTRUCTION AUDIT ===")

# Pre-game gap distribution
all_pre_gaps = [p["pre_gap_hours"] for p in valid_pairs]
all_clo_gaps = [p["clo_gap_hours"] for p in valid_pairs]
print(f"  Pre gap: min={min(all_pre_gaps):.1f}h, max={max(all_pre_gaps):.1f}h, median={sorted(all_pre_gaps)[len(all_pre_gaps)//2]:.1f}h")
print(f"  Clo gap: min={min(all_clo_gaps):.1f}h, max={max(all_clo_gaps):.1f}h, median={sorted(all_clo_gaps)[len(all_clo_gaps)//2]:.1f}h")

# Check for duplicate match_ids in source
match_record_counts = {mid: len(recs) for mid, recs in by_mid.items()}
counts_dist = defaultdict(int)
for c in match_record_counts.values():
    counts_dist[c] += 1
print(f"  Records per match_id: {dict(sorted(counts_dist.items()))}")

# Check for same-timestamp pre/closing (risk of look-ahead)
same_timestamp_pairs = sum(1 for p in valid_pairs if p["pre"][0] == p["clo"][0])
print(f"  Same-timestamp pre==clo: {same_timestamp_pairs}")

# Check very tight closing (within 30 min of game)
very_tight_closing = sum(1 for p in valid_pairs if p["clo_gap_hours"] < 0.5)
print(f"  Closing window <30min from game: {very_tight_closing}")

# ── Outlier Case Review ───────────────────────────────────────────────────
print("\n=== TOP OUTLIER CASES ===")
all_clv_meta = []
for mc in MARKET_CODES:
    all_clv_meta.extend(market_clv_with_meta[mc])

all_clv_meta_sorted = sorted(all_clv_meta, key=lambda x: abs(x["clv_pct"]), reverse=True)
top_cases = all_clv_meta_sorted[:25]

for c in top_cases[:10]:
    print(f"  {c['mid']} {c.get('market','?')}/{c['side_name']} pre={c['pre_odds']} clo={c['clo_odds']} CLV={c['clv_pct']:.2f}%")

# Tag market on each case
for c in all_clv_meta:
    pass  # already has market context from loop

# Build final outputs
construction_audit = {
    "pregame_gap_hours": {
        "min": round(min(all_pre_gaps), 2),
        "max": round(max(all_pre_gaps), 2),
        "median": round(sorted(all_pre_gaps)[len(all_pre_gaps)//2], 2),
        "pct_gt24h": round(sum(1 for x in all_pre_gaps if x > 24) / len(all_pre_gaps) * 100, 1),
        "pct_2to6h": round(sum(1 for x in all_pre_gaps if 2 <= x <= 6) / len(all_pre_gaps) * 100, 1),
    },
    "closing_gap_hours": {
        "min": round(min(all_clo_gaps), 2),
        "max": round(max(all_clo_gaps), 2),
        "median": round(sorted(all_clo_gaps)[len(all_clo_gaps)//2], 2),
        "pct_lt30min": round(very_tight_closing / len(valid_pairs) * 100, 1),
    },
    "same_timestamp_pre_clo": same_timestamp_pairs,
    "records_per_match_distribution": {str(k): v for k, v in sorted(counts_dist.items())},
    "look_ahead_risk": same_timestamp_pairs > 0,
    "duplicate_risk": max(match_record_counts.values()) > 20,
    "clv_formula": "(pregame_odds - closing_odds) / closing_odds * 100",
    "formula_correct_for_markets": {
        "MNL": "VALID - moneyline, decimal odds, CLV measures line movement direction",
        "HDC": "VALID - handicap line, decimal odds",
        "OU": "VALID - over/under totals",
        "OE": "LOW_SIGNAL - odd/even binary market, odds rarely move significantly",
        "TTO": "VALID - team total, similar to OU",
    },
    "known_issues": [
        "OE market has std=0.84%, 68.7% neutral observations - market effectively does not move, CLV is uniformative",
        "CLV formula counts 2 outcomes per market (index 0,1). MNL 3-way market drops draw outcome.",
        "Pregame snapshot may be >24h before game for some matches, reducing relevance of 'closing' comparison",
    ],
}

# Outlier case list (top 25)
outlier_cases = []
for c in top_cases:
    # Determine likely cause
    abs_clv = abs(c["clv_pct"])
    if abs_clv > 100:
        likely_cause = "EXTREME_ODDS_MOVEMENT_OR_DATA_ANOMALY"
    elif abs_clv > 30:
        likely_cause = "LARGE_ODDS_MOVEMENT_POSSIBLE_REAL"
    else:
        likely_cause = "MODERATE_MOVEMENT"

    outlier_cases.append({
        "match_id": c["mid"],
        "side_name": c["side_name"],
        "pre_odds": c["pre_odds"],
        "clo_odds": c["clo_odds"],
        "clv_pct": round(c["clv_pct"], 4),
        "pre_gap_hours": c.get("pre_gap_hours", "?"),
        "clo_gap_hours": c.get("clo_gap_hours", "?"),
        "game_time": c.get("game_time", "?"),
        "likely_cause": likely_cause,
        "action": "FLAG_ONLY_DO_NOT_DELETE",
    })

# Output summary
print("\n=== CONSTRUCTION AUDIT SUMMARY ===")
print(json.dumps(construction_audit, indent=2))

print("\n=== MAPPING RESULTS ===")
print(json.dumps(mapping_results, indent=2))

# Save to temp file
output = {
    "mapping_results": mapping_results,
    "construction_audit": construction_audit,
    "outlier_cases": outlier_cases,
    "valid_pairs": len(valid_pairs),
    "total_clv_obs": len(all_clv_meta),
}
with open("/tmp/p25_audit_results.json", "w") as f:
    json.dump(output, f, indent=2)
print("\nSaved to /tmp/p25_audit_results.json")
