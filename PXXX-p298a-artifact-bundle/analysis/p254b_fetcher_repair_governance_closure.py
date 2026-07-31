"""P254B — Fetcher repair governance closure script.

Verifies the closure artifact and prints a summary.
Read-only: no DB writes, no registry mutations, no strategy promotions.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p254b_fetcher_repair_governance_closure_20260608.json"

ACCEPTED_BASELINE = {
    "BIG_LOTTO_raw": 22_239,
    "BIG_LOTTO_canonical": 2_114,
    "BIG_LOTTO_add_on": 19_100,
    "POWER_LOTTO_raw": 1_917,
    "DAILY_539_raw": 5_882,
    "strategy_prediction_replays": 94_924,
}

STALE_VALUES = {
    "BIG_LOTTO_raw_stale": 22_238,
    "BIG_LOTTO_canonical_stale": 2_113,
}


def verify_artifact() -> dict:
    assert JSON_PATH.exists(), f"Artifact not found: {JSON_PATH}"
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    checks = {}

    checks["task_id"] = data.get("task_id") == "P254B"
    checks["classification"] = data.get("classification") == "FETCHER_REPAIR_GOVERNANCE_CLOSURE_COMPLETE"
    checks["pr360_merged"] = data.get("pr360_status", {}).get("state") == "MERGED"
    checks["pr361_merged"] = data.get("pr361_status", {}).get("state") == "MERGED"

    baseline = data.get("accepted_db_baseline", {})
    checks["big_lotto_raw_22239"] = baseline.get("BIG_LOTTO_raw") == 22_239
    checks["big_lotto_canonical_2114"] = baseline.get("BIG_LOTTO_canonical") == 2_114
    checks["add_on_19100"] = baseline.get("BIG_LOTTO_add_on") == 19_100
    checks["power_1917"] = baseline.get("POWER_LOTTO_raw") == 1_917
    checks["daily539_5882"] = baseline.get("DAILY_539_raw") == 5_882
    checks["replays_94924"] = baseline.get("strategy_prediction_replays") == 94_924

    stale = baseline.get("stale_values_must_not_reuse", {})
    checks["stale_raw_22238_documented"] = stale.get("BIG_LOTTO_raw_stale") == 22_238
    checks["stale_canonical_2113_documented"] = stale.get("BIG_LOTTO_canonical_stale") == 2_113

    skipped = data.get("skipped_test_explanation", {})
    checks["skipped_mentions_numpy"] = "numpy" in skipped.get("reason", "").lower()
    checks["skipped_mentions_venv_smoke"] = ".venv" in skipped.get("compensating_verification", "")

    lessons = data.get("governance_lessons", [])
    lesson_titles = " ".join(l.get("title", "") for l in lessons).lower()
    checks["lesson_separation_mentioned"] = "separate" in lesson_titles
    checks["lesson_stale_mentioned"] = "stale" in lesson_titles or "22238" in lesson_titles or "2113" in lesson_titles

    checks["no_db_write"] = data.get("no_db_write_confirmed") is True
    checks["no_registry_mutation"] = data.get("no_registry_mutation_confirmed") is True
    checks["no_strategy_promotion"] = data.get("no_strategy_promotion_confirmed") is True
    checks["no_betting_advice"] = data.get("no_betting_advice_confirmed") is True

    final = data.get("final_decision", "").upper()
    checks["final_decision_hold"] = "HOLD" in final or "WAITING_FOR_USER_AUTHORIZATION" in final

    return checks


def main():
    print("=" * 60)
    print("P254B Fetcher Repair Governance Closure — Verification")
    print("=" * 60)

    checks = verify_artifact()
    all_pass = all(checks.values())

    for key, result in checks.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {key}")

    print()
    print(f"Accepted baseline (stale 22238/2113 invalidated):")
    for k, v in ACCEPTED_BASELINE.items():
        print(f"  {k}: {v}")

    print()
    if all_pass:
        print("RESULT: ALL CHECKS PASS")
        print("Classification: FETCHER_REPAIR_GOVERNANCE_CLOSURE_COMPLETE")
        print("Final state: HOLD / WAITING_FOR_USER_AUTHORIZATION")
    else:
        failed = [k for k, v in checks.items() if not v]
        print(f"RESULT: FAIL — {len(failed)} check(s) failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
