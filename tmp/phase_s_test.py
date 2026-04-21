"""Quick Phase S validation."""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from engine.rule_weight_manager import (
    get_rule_weight_map, summarize_weight_map, _classify,
    GATING_ENABLED, HARD_DISABLE_ENABLED,
    WEIGHT_DOWNGRADE, WEIGHT_BOOST, WEIGHT_NEUTRAL,
    STATUS_BOOSTED, STATUS_DOWNGRADED, STATUS_NEUTRAL, STATUS_LOW_CONF,
)

# Unit tests on classifier
assert _classify(-0.5, 6)[0] == WEIGHT_DOWNGRADE
assert _classify(-0.5, 6)[1] == STATUS_DOWNGRADED
assert _classify(0.5, 6)[0] == WEIGHT_BOOST
assert _classify(0.5, 6)[1] == STATUS_BOOSTED
assert _classify(0.0, 6)[0] == WEIGHT_NEUTRAL
assert _classify(0.0, 6)[1] == STATUS_NEUTRAL
assert _classify(0.8, 3)[0] == WEIGHT_NEUTRAL
assert _classify(0.8, 3)[1] == STATUS_LOW_CONF
assert _classify(-0.35, 5)[1] == STATUS_DOWNGRADED
assert _classify(-0.29, 5)[1] == STATUS_NEUTRAL
print("classifier: OK (9 assertions)")
print(f"GATING_ENABLED={GATING_ENABLED}, HARD_DISABLE_ENABLED={HARD_DISABLE_ENABLED}")

# Live integration
wmap = get_rule_weight_map(persist=True)
print(f"weight_map rules: {len(wmap)}")
summary = summarize_weight_map(wmap)
print(
    "summary: boosted={}, downgraded={}, disabled={}, low_conf={}, neutral={}".format(
        len(summary["boosted"]),
        len(summary["downgraded"]),
        len(summary["disabled"]),
        len(summary["low_conf"]),
        len(summary["neutral"]),
    )
)
for code, entry in wmap.items():
    print(
        "  {}: w={} status={} score={} n={}".format(
            code, entry["weight"], entry["status"],
            entry.get("rule_score"), entry.get("samples"),
        )
    )

# Actionable summary integration
from engine.actionable_intelligence import get_actionable_summary
full = get_actionable_summary()
for lt in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]:
    entry = full.get(lt, {})
    gating = entry.get("rule_gating") or {}
    print(
        "{}: applied={} dropped={} downgraded={} boosted={}".format(
            lt,
            gating.get("applied"),
            len(gating.get("dropped_rules", [])),
            len(gating.get("downgraded", [])),
            len(gating.get("boosted", [])),
        )
    )
    for ins in (entry.get("insights") or [])[:2]:
        print(
            "  {} weight={} status={} note={}".format(
                ins.get("code"),
                ins.get("rule_weight"),
                ins.get("weight_status"),
                ins.get("weight_note"),
            )
        )
print("=== Phase S integration OK ===")
