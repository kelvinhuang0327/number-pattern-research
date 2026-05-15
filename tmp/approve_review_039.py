import sqlite3, json

db = sqlite3.connect('lottery_api/data/lottery_v2.db')
db.row_factory = sqlite3.Row

# Update all 3 VALID runs (4, 6, 7) with user approval and supplementary notes
for run_id in [4, 6, 7]:
    row = db.execute("SELECT review_json FROM prediction_runs WHERE id=?", (run_id,)).fetchone()
    if not row or not row['review_json']:
        print(f"Run {run_id}: no review_json, skip")
        continue

    r = json.loads(row['review_json'])

    # Add user approval section
    r['user_review'] = {
        "status": "APPROVED",
        "reviewer": "user",
        "date": "2026-03-29",
        "core_agreements": [
            "0 hit = migration artifact, not strategy failure (Coordinator-Direct legacy format)",
            "4 strategies PRODUCTION maintained — 300p Edge positive, Sharpe > 0, 30p negative within noise",
            "Sum=126 is normal mean reversion, not regime failure"
        ],
        "supplementary_notes": [
            {
                "topic": "1500p validation gap",
                "note": "328 records insufficient for 1500p. When approaching 500p, prioritize p1_dev_sum5bet permutation test (5-bet = highest complexity = highest overfit risk).",
                "priority": "P1",
                "trigger": "data_count >= 450"
            },
            {
                "topic": "P2 anti-popularity filter scope",
                "note": "Start with Track B annotation only, NOT direct filtering. Ref L102 lesson: BIG_LOTTO swap rate too low for p<0.05 significance on direct filter.",
                "priority": "P2",
                "action": "Annotate split-risk on predictions, collect data before implementing filter"
            },
            {
                "topic": "30p negative edge monitoring",
                "note": "30p all-negative warrants tracking. Schedule quick review at 50p window to confirm variance vs decay.",
                "priority": "P1",
                "trigger": "50p window reached (~draw 115000055)"
            }
        ]
    }

    # Update action_items P1 with 50p review checkpoint
    if "P1" in r.get("action_items", {}):
        r["action_items"]["P1"].append({
            "action": "50p quick review: check if 30p edge normalizes or signals decay",
            "expected_lift": "Early detection of model decay",
            "cost": "LOW",
            "risk": "LOW",
            "verification": "30p edge turns positive for >=2 strategies",
            "stop_condition": "If 30p stays negative at 50p, escalate to full re-evaluation",
            "trigger": "~draw 115000055"
        })

    # Update P2 to reflect annotation-first approach
    for item in r.get("action_items", {}).get("P2", []):
        if "anti-popularity" in item.get("action", ""):
            item["action"] = "Track B annotation: tag predictions with split-risk score (annotation only, no filtering yet per L102 lesson)"
            item["risk"] = "LOW (annotation only, no coverage impact)"

    db.execute(
        "UPDATE prediction_runs SET review_json=? WHERE id=?",
        (json.dumps(r, ensure_ascii=False), run_id)
    )
    print(f"Run {run_id}: updated with APPROVED status + supplementary notes")

db.commit()

# Verify
for run_id in [4, 6, 7]:
    row = db.execute("SELECT review_json FROM prediction_runs WHERE id=?", (run_id,)).fetchone()
    r = json.loads(row['review_json'])
    ur = r.get('user_review', {})
    print(f"Run {run_id}: status={ur.get('status')}, notes={len(ur.get('supplementary_notes', []))}")

db.close()
