#!/usr/bin/env python3
"""
PHASE 6 — Final Validation + Activation Log

Collect key runtime metrics and append a final integrity entry to
logs/activation_loop_log.jsonl.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


LEDGER = Path("research/trade_ledger.jsonl")
ROI_PATH = Path("research/roi_tracking.json")
POSTMORTEM_DIR = Path("research/postmortem_reports")
ACCURACY_REPORT = Path("scripts/activation/phase3_accuracy_report.py")
LOG_PATH = Path("logs/activation_loop_log.jsonl")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _count_ledger() -> dict[str, int]:
    out = {
        "predictions_total": 0,
        "predictions_wbc": 0,
        "predictions_mlb": 0,
        "predictions_mlb_paper_only": 0,
        "settlements_total": 0,
    }

    if not LEDGER.exists():
        return out

    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        et = str(row.get("event_type", ""))
        league = str(row.get("league", "")).upper()
        mode = str(row.get("execution_mode", "")).upper()

        if et == "prediction":
            out["predictions_total"] += 1
            if league == "WBC":
                out["predictions_wbc"] += 1
            if league == "MLB":
                out["predictions_mlb"] += 1
                if mode == "PAPER_ONLY":
                    out["predictions_mlb_paper_only"] += 1
        elif et == "settlement":
            out["settlements_total"] += 1

    return out


def main() -> int:
    counts = _count_ledger()
    roi = _load_json(ROI_PATH, {})

    postmortem_count = 0
    if POSTMORTEM_DIR.exists():
        postmortem_count = len(list(POSTMORTEM_DIR.glob("*.md")))

    win_rate = roi.get("win_rate")
    if win_rate is None:
        wins = roi.get("wins")
        losses = roi.get("losses")
        if isinstance(wins, int) and isinstance(losses, int) and (wins + losses) > 0:
            win_rate = wins / (wins + losses)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "job": "INTEGRITY_8H",
        "bug_fixed": False,
        "bug_type": "model_calibration_not_data_inversion",
        "status": "success" if counts["predictions_mlb_paper_only"] >= 3 else "partial",
        "wbc_predictions": counts["predictions_wbc"],
        "mlb_predictions": counts["predictions_mlb"],
        "mlb_paper_only_predictions": counts["predictions_mlb_paper_only"],
        "settlements": counts["settlements_total"],
        "win_rate": win_rate,
        "bankroll": roi.get("current_bankroll"),
        "postmortem_count": postmortem_count,
        "roi_sample_size": roi.get("sample_size"),
        "phase3_accuracy_report_present": ACCURACY_REPORT.exists(),
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("=" * 60)
    print("PHASE 6 — FINAL VALIDATION")
    print("=" * 60)
    for key, value in entry.items():
        print(f"{key}: {value}")
    print(f"log_path: {LOG_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
