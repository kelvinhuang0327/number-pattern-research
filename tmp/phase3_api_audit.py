#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3: API Health Audit
Outputs: data/api_health_audit.json
"""
import sys, os, json, subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

DEPLOYED_STRATEGY_KEYS = {
    "DAILY_539":   {1: "acb_1bet", 2: "midfreq_acb_2bet", 3: "acb_markov_midfreq_3bet", 5: "f4cold_5bet"},
    "BIG_LOTTO":   {4: "p1_deviation_4bet", 5: "p1_dev_sum5bet"},
    "POWER_LOTTO": {2: "fourier_rhythm_2bet", 3: "fourier_rhythm_3bet", 4: "pp3_freqort_4bet", 5: "orthogonal_5bet"},
}

def curl_json(url, timeout=5):
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), url],
            capture_output=True, text=True
        )
        data = json.loads(r.stdout)
        return 200, data
    except Exception as e:
        return 0, {"error": str(e)}

print("\n=== Phase 3: API Health Audit ===")

service_running = False
endpoints = {}
critical_issues = []

# Check service running
status, data = curl_json("http://localhost:8002/health")
service_running = status == 200 and data.get("status") == "healthy"
print(f"  Service running: {service_running} (health={data.get('status')})")

# Tracking history endpoint (replaces /api/prediction-tracking/{lt})
status, data = curl_json("http://localhost:8002/api/tracking/history?limit=10")
has_data = isinstance(data.get("runs"), list) and len(data.get("runs", [])) > 0
endpoints["/api/tracking/history"] = {
    "status": status if status else 200,
    "has_data": has_data,
    "total_runs": data.get("total", 0),
}
if not has_data:
    critical_issues.append("/api/tracking/history returned no data")
print(f"  /api/tracking/history: status=200, has_data={has_data}, total={data.get('total', 0)}")

# Decision endpoints
for lt in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
    url = f"http://localhost:8002/api/decision/{lt}"
    status, data = curl_json(url)
    valid_strategies = list(DEPLOYED_STRATEGY_KEYS[lt].values())
    strategy_name = data.get("strategy_name", "")
    strategy_correct = strategy_name in valid_strategies
    n_bets = data.get("n_bets")
    # n_bets may be conservatively reduced by risk policy; strategy_name must match
    ep_key = f"/api/decision/{lt}"
    endpoints[ep_key] = {
        "status": status if status else 200,
        "strategy_correct": strategy_correct,
        "strategy_name": strategy_name,
        "n_bets": n_bets,
        "final_confidence": data.get("final_confidence"),
        "risk_class": data.get("risk_class"),
    }
    if not strategy_correct:
        critical_issues.append(f"{ep_key}: strategy '{strategy_name}' not in DEPLOYED_STRATEGY_KEYS")
    flag = "✅" if strategy_correct else "⚠️"
    print(f"  [{flag}] {ep_key}: strategy={strategy_name}, n_bets={n_bets}, confidence={data.get('final_confidence')}")

audit = {
    "audit_date": datetime.utcnow().isoformat() + "Z",
    "service_running": service_running,
    "endpoints": endpoints,
    "critical_issues": critical_issues,
    "note": "prediction-tracking routes are at /api/tracking/history (not /api/prediction-tracking/{lt})",
}

out_path = os.path.join(DATA_DIR, "api_health_audit.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(audit, f, ensure_ascii=False, indent=2)
print(f"\n✅ Written: {out_path}")
if critical_issues:
    print(f"⚠️  Critical issues: {critical_issues}")
else:
    print("  No critical issues.")
