#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 5C: Generate live_validation_summary_2026_04_20.json
"""
import json, os
from datetime import datetime

ROOT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
DATA_DIR = os.path.join(ROOT, "data")

def load(fname):
    p = os.path.join(DATA_DIR, fname)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

gen_audit   = load("prediction_generation_audit.json")
live_audit  = load("live_performance_audit.json")
api_audit   = load("api_health_audit.json")
perf_30p    = load("recent_30p_performance.json")

# --- Prediction generation OK? ---
by_lt = gen_audit.get("by_lottery", {})
gen_ok = all(
    v.get("strategy_correct") and v.get("bet_count_ok") and v.get("number_range_ok") and v.get("no_duplicates")
    for v in by_lt.values()
) and not gen_audit.get("format_issues")
prediction_generation = "OK" if gen_ok else "ISSUES"

# --- Live vs backtest ---
live_vs_bt = {}
anomalies_found = []
for lt, d in live_audit.get("by_lottery", {}).items():
    n = d.get("draws_with_result", 0)
    if n < 5:
        status = "INSUFFICIENT_DATA"
    elif d.get("anomaly_detected"):
        status = "ANOMALY"
        anomalies_found.append(lt)
    else:
        status = "WITHIN_CI"
    live_vs_bt[lt] = status

# --- API health ---
issues = api_audit.get("critical_issues", [])
api_health = "OK" if not issues else "DEGRADED"

# --- 30p status ---
recent_30p = {}
alerts = []
for lt, d in perf_30p.get("by_lottery", {}).items():
    st = d.get("status", "N/A")
    recent_30p[lt] = st
    if st == "ALERT":
        alerts.append(lt)
    elif st == "WATCH":
        alerts.append(f"{lt}(WATCH)")

# --- System status ---
if anomalies_found or alerts:
    sys_status = "YELLOW"
    if any("ALERT" in a for a in alerts):
        sys_status = "RED"
else:
    sys_status = "GREEN"

# --- Action items ---
action_items = []
for lt in anomalies_found:
    action_items.append({
        "priority": "HIGH",
        "type": "ANOMALY",
        "lottery": lt,
        "description": f"{lt} live M3+ rate diverges from backtest by >2σ — requires manual review",
    })
for a in alerts:
    lt_name = a.split("(")[0]
    prio = "HIGH" if "ALERT" in a else "MEDIUM"
    action_items.append({
        "priority": prio,
        "type": "EDGE_DEGRADATION",
        "lottery": lt_name,
        "description": f"{lt_name} 近30期 edge 衰退 ({a}) — 觀察後續走勢",
    })
if not action_items:
    action_items.append({
        "priority": "NONE",
        "type": "INFO",
        "description": "All metrics within expected range. Continue monitoring weekly.",
    })

# --- 詳細數據 ---
detail = {}
for lt in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
    la = live_audit.get("by_lottery", {}).get(lt, {})
    p = perf_30p.get("by_lottery", {}).get(lt, {})
    detail[lt] = {
        "draws_with_result": la.get("draws_with_result"),
        "m3plus_rate_live": la.get("m3plus_rate_live"),
        "m3plus_rate_backtest": la.get("m3plus_rate_backtest_1500p"),
        "within_ci_95": la.get("within_ci_95"),
        "edge_30p": p.get("edge_30p"),
        "status_30p": p.get("status"),
    }

summary = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "audit_date": "2026-04-20",
    "prediction_generation": prediction_generation,
    "live_vs_backtest": live_vs_bt,
    "api_health": api_health,
    "recent_30p_status": recent_30p,
    "system_status": sys_status,
    "action_items": action_items,
    "detail": detail,
}

out = os.path.join(DATA_DIR, "live_validation_summary_2026_04_20.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"Written: {out}")
print(json.dumps(summary, ensure_ascii=False, indent=2))
