#!/usr/bin/env python3
"""
MLB Odds Capture Daemon — Health Check

Quick status report covering:
  - process alive
  - launchd loaded
  - last capture timestamp
  - timeline data growth
  - CLV readiness score

Usage:
  python3 scripts/check_odds_daemon.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.mlb.odds_capture"
PID_PATH = ROOT / "build" / "runtime_artifacts" / "odds_capture.pid"
TIMELINE_PATH = ROOT / "data" / "mlb_context" / "odds_timeline.jsonl"
SCHEDULE_PATH = ROOT / "data" / "mlb_context" / "odds_capture_schedule.json"
LOG_PATH = ROOT / "logs" / "odds_capture.log"
PLIST_DST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pid_alive() -> tuple[int | None, bool]:
    try:
        pid = int(PID_PATH.read_text().strip())
    except (OSError, ValueError):
        return None, False
    try:
        os.kill(pid, 0)
        return pid, True
    except (ProcessLookupError, PermissionError):
        return pid, False


def _launchd_loaded() -> bool:
    try:
        out = subprocess.check_output(["launchctl", "list"], text=True, stderr=subprocess.DEVNULL)
        return LABEL in out
    except Exception:
        return False


def _check_process() -> dict:
    pid, alive = _pid_alive()
    loaded = _launchd_loaded()
    return {
        "launchd_installed": PLIST_DST.exists(),
        "launchd_loaded": loaded,
        "pid": pid,
        "process_alive": alive,
    }


def _check_schedule() -> dict:
    if not SCHEDULE_PATH.exists():
        return {"schedule_found": False}
    d = json.loads(SCHEDULE_PATH.read_text())
    last_run_str = d.get("last_run")
    captures = d.get("captures", [])
    result: dict = {
        "schedule_found": True,
        "capture_records": len(captures),
        "last_run": last_run_str,
        "minutes_since_last_run": None,
        "last_run_ok": False,
    }
    if last_run_str:
        lr = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
        minutes_ago = (_now() - lr).total_seconds() / 60
        result["minutes_since_last_run"] = round(minutes_ago, 1)
        result["last_run_ok"] = minutes_ago <= 20
    return result


def _check_data() -> dict:
    if not TIMELINE_PATH.exists():
        return {"timeline_found": False}
    rows = [json.loads(l) for l in TIMELINE_PATH.read_text().splitlines() if l.strip()]
    total = len(rows)
    hist_lens = [len(r.get("odds_history") or []) for r in rows]
    dist = Counter(hist_lens)

    with_decision = sum(1 for r in rows if r.get("decision_ts"))
    with_pregame = sum(1 for r in rows if r.get("latest_pregame_ts"))
    with_closing = sum(1 for r in rows if r.get("closing_ts"))

    multi2 = sum(v for k, v in dist.items() if k >= 2)
    multi5 = sum(v for k, v in dist.items() if k >= 5)
    avg_snaps = sum(hist_lens) / max(total, 1)

    now = _now()
    cutoff_1h = now - timedelta(hours=1)
    cutoff_24h = now - timedelta(hours=24)
    recent_1h = 0
    recent_24h = 0
    for r in rows:
        for snap in r.get("odds_history") or []:
            ts_str = snap.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff_1h:
                    recent_1h += 1
                if ts >= cutoff_24h:
                    recent_24h += 1
            except Exception:
                pass

    # CLV readiness score
    score = 0
    score_notes = []
    if with_decision > 0:
        score += 40
        score_notes.append(f"+40  decision_ts ({with_decision} games)")
    if multi2 > 0:
        score += 30
        score_notes.append(f"+30  multi-snapshot ({multi2} games)")
    if with_closing > 0:
        score += 30
        score_notes.append(f"+30  closing_ts ({with_closing} games)")

    # Verdict
    if score >= 100:
        verdict = "CLV_READY"
    elif score >= 70 and with_closing > 0:
        verdict = "NEAR_CLV_READY"
    elif score >= 40:
        verdict = "DATA_ACCUMULATING"
    elif recent_1h > 0:
        verdict = "RUNNING_NO_DATA"
    else:
        verdict = "NOT_RUNNING"

    return {
        "timeline_found": True,
        "total_games": total,
        "games_1_snapshot": dist.get(1, 0),
        "games_2plus_snapshots": multi2,
        "games_5plus_snapshots": multi5,
        "games_with_decision_ts": with_decision,
        "games_with_pregame_ts": with_pregame,
        "games_with_closing_ts": with_closing,
        "avg_snapshots_per_game": round(avg_snaps, 3),
        "snapshots_last_1h": recent_1h,
        "snapshots_last_24h": recent_24h,
        "clv_score": score,
        "score_notes": score_notes,
        "verdict": verdict,
    }


def _check_errors() -> dict:
    if not LOG_PATH.exists():
        return {"log_found": False}
    lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    recent = lines[-200:]
    errors = [l for l in recent if "[ERROR]" in l or "ERROR" in l.upper() and "[INFO]" not in l]
    retries = [l for l in recent if "retry" in l.lower() or "attempt" in l.lower() and "OK" not in l]
    return {
        "log_found": True,
        "log_lines": len(lines),
        "recent_errors": len(errors),
        "recent_retries": len(retries),
        "last_5_lines": lines[-5:],
    }


def _pct(n: int, total: int) -> str:
    return f"{n/total*100:.1f}%" if total else "N/A"


def main() -> None:
    now_str = _now().strftime("%Y-%m-%d %H:%M UTC")
    print(f"{'='*60}")
    print(f"  MLB ODDS DAEMON — HEALTH CHECK   {now_str}")
    print(f"{'='*60}")

    proc = _check_process()
    sched = _check_schedule()
    data = _check_data()
    errs = _check_errors()

    # ── Section 1: Process ──
    print()
    print("PROCESS")
    print("-" * 30)
    installed = proc["launchd_installed"]
    loaded = proc["launchd_loaded"]
    alive = proc["process_alive"]
    pid = proc["pid"]
    print(f"  launchd installed : {'YES ✓' if installed else 'NO  ✗'}")
    print(f"  launchd loaded    : {'YES ✓' if loaded else 'NO  ✗'}")
    print(f"  process alive     : {'YES ✓' if alive else 'NO  ✗'} (pid={pid})")

    # ── Section 2: Schedule ──
    print()
    print("SCHEDULER")
    print("-" * 30)
    if sched.get("schedule_found"):
        ok = sched.get("last_run_ok", False)
        mins = sched.get("minutes_since_last_run")
        print(f"  last_run : {sched.get('last_run', 'N/A')}")
        print(f"  ago      : {mins} min  {'✓ (<20 min)' if ok else '✗ (>20 min — STALE)'}")
        print(f"  records  : {sched.get('capture_records', 0)}")
    else:
        print("  ✗ Schedule file not found — scheduler has never run")

    # ── Section 3 & 4: Data & Timeline ──
    print()
    print("DATA ACCUMULATION")
    print("-" * 30)
    if data.get("timeline_found"):
        total = data["total_games"]
        print(f"  total games       : {total}")
        print(f"  1-snapshot games  : {data['games_1_snapshot']}")
        print(f"  2+ snapshots      : {data['games_2plus_snapshots']} ({_pct(data['games_2plus_snapshots'], total)})")
        print(f"  5+ snapshots      : {data['games_5plus_snapshots']} ({_pct(data['games_5plus_snapshots'], total)})")
        print()
        print(f"  decision_ts       : {data['games_with_decision_ts']} ({_pct(data['games_with_decision_ts'], total)})")
        print(f"  pregame_ts        : {data['games_with_pregame_ts']} ({_pct(data['games_with_pregame_ts'], total)})")
        print(f"  closing_ts        : {data['games_with_closing_ts']} ({_pct(data['games_with_closing_ts'], total)})")
        print()
        print(f"  avg snaps/game    : {data['avg_snapshots_per_game']}")
        print(f"  snaps last 1h     : {data['snapshots_last_1h']}")
        print(f"  snaps last 24h    : {data['snapshots_last_24h']}")
    else:
        print("  ✗ Timeline file not found")

    # ── Section 5: Errors ──
    print()
    print("ERROR DETECTION")
    print("-" * 30)
    if errs.get("log_found"):
        print(f"  log lines         : {errs['log_lines']}")
        print(f"  recent errors     : {errs['recent_errors']}")
        print(f"  recent retries    : {errs['recent_retries']}")
        print("  last 5 lines:")
        for line in errs.get("last_5_lines", []):
            print(f"    {line}")
    else:
        print("  log not found")

    # ── Section 6: CLV Score & Verdict ──
    print()
    print("CLV READINESS")
    print("-" * 30)
    if data.get("timeline_found"):
        print(f"  score : {data['clv_score']} / 100")
        for note in data.get("score_notes", []):
            print(f"    {note}")
        if data["clv_score"] < 100:
            missing = []
            if not data["games_with_decision_ts"]:
                missing.append("  -40  missing decision_ts")
            if not data["games_2plus_snapshots"]:
                missing.append("  -30  missing multi-snapshot")
            if not data["games_with_closing_ts"]:
                missing.append("   -30  missing closing_ts (need daemon running pre-game)")
            for m in missing:
                print(m)
        print()
        print(f"  VERDICT: {data['verdict']}")

    # ── Section 7: Next Action ──
    print()
    print("NEXT ACTION")
    print("-" * 30)
    if not installed:
        print("  1. Install launchd agent:")
        print("     bash scripts/manage_daemon.sh install")
    elif not loaded:
        print("  1. Load launchd agent:")
        print("     bash scripts/manage_daemon.sh start")
    elif not alive:
        print("  1. Daemon not running despite being loaded — check logs:")
        print(f"     tail -50 {LOG_PATH}")
    elif not sched.get("last_run_ok"):
        print("  Daemon is running but last capture is stale.")
        print("  Check for silent errors in logs:")
        print(f"     tail -50 {LOG_PATH}")
    elif not data.get("games_with_closing_ts"):
        print("  Daemon running. Wait for today's games to start.")
        print("  closing_ts fills automatically at T-30min before each game.")
        print("  Re-run this check in 30 minutes:")
        print("     python3 scripts/check_odds_daemon.py")
    else:
        print("  All systems nominal. CLV data is accumulating.")
    print()


if __name__ == "__main__":
    main()
