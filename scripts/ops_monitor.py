#!/usr/bin/env python3
"""
8-hour operational monitoring loop.

Monitors system health, detects snapshot/CLV growth, watches the closing-price
trigger window, and periodically attempts settlement ingestion.

Output files (append-only JSONL):
  logs/system_health_log.jsonl
  logs/settlement_run_log.jsonl
  logs/runtime_events.jsonl

Usage:
  python scripts/ops_monitor.py              # foreground (prints progress)
  nohup python scripts/ops_monitor.py > logs/ops_monitor.log 2>&1 &
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

# ── Output log paths ───────────────────────────────────────────────────────────
HEALTH_LOG      = REPO_ROOT / "logs/system_health_log.jsonl"
SETTLEMENT_LOG  = REPO_ROOT / "logs/settlement_run_log.jsonl"
EVENTS_LOG      = REPO_ROOT / "logs/runtime_events.jsonl"

# ── Input data paths ───────────────────────────────────────────────────────────
TIMELINE_PATH   = REPO_ROOT / "data/mlb_context/odds_timeline.jsonl"
CLOSING_STATE   = REPO_ROOT / "data/mlb_context/external_closing_state.json"
POSTGAME_PATH   = REPO_ROOT / "data/wbc_backend/reports/postgame_results.jsonl"
DAEMON_LOG      = REPO_ROOT / "logs/odds_capture.log"
HEARTBEAT_PATH  = REPO_ROOT / "logs/daemon_heartbeat.jsonl"

# ── Timing constants ───────────────────────────────────────────────────────────
LOOP_INTERVAL_SEC       = 900          # 15 min between cycles
TOTAL_DURATION_SEC      = 8 * 3600    # 8-hour run
SETTLEMENT_EVERY_N      = 4           # settlement ingestion every 4 cycles (60 min)
DAEMON_STALE_MINUTES    = 20          # warn if daemon hasn't logged in 20 min
NO_GROWTH_WARN_MINUTES  = 60          # warn if no snapshot growth in 60 min


# ── Utilities ─────────────────────────────────────────────────────────────────

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, record: dict) -> None:
    """Append one JSON line. Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[WARN] _append_jsonl({path.name}): {exc}")


def _read_json(path: Path) -> dict:
    """Read a JSON object file. Returns {} on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── Data collectors ────────────────────────────────────────────────────────────

def _count_timeline() -> tuple[int, int, int]:
    """
    Returns (total_rows, external_closing_rows, games_with_2plus_snapshots).
    Reads the timeline once.
    """
    if not TIMELINE_PATH.exists():
        return 0, 0, 0
    total = 0
    closing = 0
    game_counts: dict[str, int] = {}
    try:
        for raw in TIMELINE_PATH.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            total += 1
            try:
                row = json.loads(raw)
                if row.get("external_closing_home_ml") is not None:
                    closing += 1
                gid = str(row.get("game_id", ""))
                if gid:
                    game_counts[gid] = game_counts.get(gid, 0) + 1
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    games_2plus = sum(1 for v in game_counts.values() if v >= 2)
    return total, closing, games_2plus


def _daemon_last_run() -> tuple[str | None, float | None]:
    """
    Returns (last_run_iso, minutes_ago) parsed from the daemon log.
    """
    if not DAEMON_LOG.exists():
        return None, None
    try:
        lines = DAEMON_LOG.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if m:
                # Log timestamps are in local time; astimezone(utc) on a naive
                # datetime converts from local → UTC correctly on Python 3.6+
                ts_local = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                ts = ts_local.astimezone(timezone.utc)
                ago = (_utc_now() - ts).total_seconds() / 60
                return ts.isoformat().replace("+00:00", "Z"), round(ago, 1)
    except Exception:
        pass
    return None, None


def _last_heartbeat() -> dict:
    """Returns the last heartbeat entry or {} if missing/corrupt."""
    if not HEARTBEAT_PATH.exists():
        return {}
    try:
        lines = [l for l in HEARTBEAT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            return json.loads(lines[-1])
    except Exception:
        pass
    return {}


# ── Settlement ingestion ───────────────────────────────────────────────────────

def _build_settlement_inputs() -> list[dict]:
    """
    Derive settlement inputs from postgame_results.jsonl.
    Includes every game that has final scores, regardless of whether
    a prediction was made (ingestion layer handles the match).
    """
    if not POSTGAME_PATH.exists():
        return []
    results = []
    try:
        for raw in POSTGAME_PATH.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            gid = str(row.get("game_id", "")).strip()
            if not gid:
                continue
            hs = row.get("home_score")
            aws = row.get("away_score")
            if hs is None or aws is None:
                continue
            try:
                result = "home_win" if int(hs) > int(aws) else "away_win"
            except (ValueError, TypeError):
                continue
            settle_t = (
                row.get("game_date")
                or row.get("game_time")
                or row.get("timestamp")
            )
            if not settle_t:
                continue
            if "T" not in str(settle_t):
                settle_t = f"{settle_t}T00:00:00Z"
            results.append({
                "game_id": gid,
                "result": result,
                "settlement_time": str(settle_t),
                "final_score": f"{hs}-{aws}",
            })
    except Exception:
        pass
    return results


def _run_settlement() -> dict:
    """
    Attempt settlement ingestion. Returns a summary. Never raises.
    """
    out: dict = {
        "timestamp": _iso(),
        "new_settlements_count": 0,
        "roi_delta": 0.0,
        "triggers_fired": 0,
        "postmortem_generated": False,
        "error": None,
    }
    try:
        inputs = _build_settlement_inputs()
        if not inputs:
            out["error"] = "no_settlement_inputs_from_postgame"
            return out

        from research.settlement_ingestion import ingest_settlements  # type: ignore[import]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(inputs, tf, ensure_ascii=False)
            tmp_path = tf.name

        try:
            summary = ingest_settlements(tmp_path)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

        out["new_settlements_count"] = int(summary.get("settled_count", 0) or 0)
        out["roi_delta"] = float(summary.get("roi_delta", 0.0) or 0.0)
        out["triggers_fired"] = int(summary.get("triggers_fired", 0) or 0)
        out["postmortem_generated"] = bool(summary.get("postmortem_generated", False))

    except Exception as exc:
        out["error"] = str(exc)

    return out


# ── Main loop ─────────────────────────────────────────────────────────────────

def run() -> None:
    print(f"[{_iso()}] ops_monitor starting — PID={os.getpid()}, duration=8h, interval=15min")

    state: dict = {
        "start": _utc_now(),
        "cycle": 0,
        "prev_snapshots": None,
        "prev_closing": None,
        "last_growth_at": _utc_now(),
        "prev_eta": None,
        # accumulators for final report
        "acc_snapshots": 0,
        "acc_closing": 0,
        "acc_settlements": 0,
        "acc_postmortems": 0,
        "acc_roi": 0.0,
    }

    _append_jsonl(
        EVENTS_LOG,
        {
            "timestamp": _iso(),
            "type": "monitor_start",
            "pid": os.getpid(),
            "duration_hours": 8,
            "interval_minutes": 15,
        },
    )

    while True:
        cycle_start = _utc_now()
        elapsed_sec = (cycle_start - state["start"]).total_seconds()
        if elapsed_sec >= TOTAL_DURATION_SEC:
            break

        state["cycle"] += 1
        cyc = state["cycle"]
        print(f"[{_iso()}] ── Cycle {cyc} (elapsed {int(elapsed_sec // 60)}m) ──")

        # ── STEP 1: Health check ──────────────────────────────────────────────
        snap_total, close_total, games_2plus = _count_timeline()
        daemon_ts, daemon_ago = _daemon_last_run()
        hb = _last_heartbeat()
        cs = _read_json(CLOSING_STATE)

        api_calls   = int(cs.get("api_calls_today", 0))
        fetched     = bool(cs.get("fetched", False))
        next_eta    = hb.get("next_trigger_minutes")  # None if heartbeat missing

        health_flags: list[str] = []
        if daemon_ago is not None and daemon_ago > DAEMON_STALE_MINUTES:
            health_flags.append("DAEMON_STALE")

        health_rec = {
            "timestamp": _iso(),
            "cycle": cyc,
            "daemon_last_run": daemon_ts,
            "daemon_minutes_ago": daemon_ago,
            "api_calls_today": api_calls,
            "snapshot_total": snap_total,
            "external_closing_total": close_total,
            "games_with_2plus_snapshots": games_2plus,
            "next_trigger_minutes": next_eta,
            "fetched": fetched,
            "flags": health_flags,
        }
        _append_jsonl(HEALTH_LOG, health_rec)

        # ── STEP 2: Growth detection ──────────────────────────────────────────
        if state["prev_snapshots"] is not None:
            d_snap  = snap_total  - state["prev_snapshots"]
            d_close = close_total - state["prev_closing"]  # type: ignore[operator]

            if d_snap > 0 or d_close > 0:
                state["last_growth_at"] = _utc_now()
                state["acc_snapshots"] += d_snap
                state["acc_closing"]   += d_close
            else:
                stale_min = (_utc_now() - state["last_growth_at"]).total_seconds() / 60
                if stale_min > NO_GROWTH_WARN_MINUTES:
                    _append_jsonl(
                        EVENTS_LOG,
                        {
                            "timestamp": _iso(),
                            "type": "no_growth_warning",
                            "duration_minutes": round(stale_min, 1),
                        },
                    )
                    if "DAEMON_STALE" in health_flags:
                        _append_jsonl(
                            EVENTS_LOG,
                            {
                                "timestamp": _iso(),
                                "type": "CRITICAL",
                                "reason": "no_snapshot_growth_and_daemon_stale",
                                "duration_minutes": round(stale_min, 1),
                            },
                        )

        state["prev_snapshots"] = snap_total
        state["prev_closing"]   = close_total

        # ── STEP 3: Trigger window watch ──────────────────────────────────────
        if next_eta is not None:
            in_window = -15 <= float(next_eta) <= 30
            prev_eta  = state["prev_eta"]

            if in_window and not fetched:
                if prev_eta is not None and float(prev_eta) <= 0:
                    # We passed the trigger window without fetching
                    _append_jsonl(
                        EVENTS_LOG,
                        {
                            "timestamp": _iso(),
                            "type": "missed_trigger_warning",
                            "prev_eta_minutes": prev_eta,
                        },
                    )
                    _append_jsonl(
                        EVENTS_LOG,
                        {
                            "timestamp": _iso(),
                            "type": "CRITICAL",
                            "reason": "external_closing_not_executed_after_trigger_window",
                        },
                    )
            state["prev_eta"] = next_eta

        # API over-use guard
        if api_calls > 2:
            _append_jsonl(
                EVENTS_LOG,
                {
                    "timestamp": _iso(),
                    "type": "CRITICAL",
                    "reason": "api_calls_exceeds_expected",
                    "api_calls_today": api_calls,
                },
            )

        # ── STEP 4: Settlement ingestion (every SETTLEMENT_EVERY_N cycles) ────
        if cyc % SETTLEMENT_EVERY_N == 0:
            print(f"[{_iso()}] Running settlement ingestion (cycle {cyc})…")
            sett = _run_settlement()
            _append_jsonl(SETTLEMENT_LOG, sett)
            state["acc_settlements"] += sett["new_settlements_count"]
            state["acc_roi"]         += sett["roi_delta"]
            if sett["postmortem_generated"]:
                state["acc_postmortems"] += 1
            print(f"[{_iso()}] Settlement: {sett}")

        # ── STEP 5: Runtime event ─────────────────────────────────────────────
        stale_for = (_utc_now() - state["last_growth_at"]).total_seconds() / 60
        if "DAEMON_STALE" in health_flags and stale_for > NO_GROWTH_WARN_MINUTES:
            run_status = "degraded"
        elif health_flags or stale_for > NO_GROWTH_WARN_MINUTES:
            run_status = "warning"
        else:
            run_status = "ok"

        _append_jsonl(
            EVENTS_LOG,
            {
                "timestamp": _iso(),
                "cycle": cyc,
                "snapshot_count": snap_total,
                "external_closing_count": close_total,
                "api_calls_today": api_calls,
                "games_with_2plus_snapshots": games_2plus,
                "status": run_status,
            },
        )

        print(
            f"[{_iso()}] Cycle {cyc} done — "
            f"status={run_status}, snap={snap_total}, ext_close={close_total}, "
            f"api={api_calls}/2"
        )

        # ── Sleep ─────────────────────────────────────────────────────────────
        cycle_took = (_utc_now() - cycle_start).total_seconds()
        sleep_for  = max(0.0, LOOP_INTERVAL_SEC - cycle_took)
        wake_at    = _utc_now() + timedelta(seconds=sleep_for)
        print(f"[{_iso()}] Sleeping {int(sleep_for)}s → next cycle at {wake_at.strftime('%H:%M:%S')} UTC")
        time.sleep(sleep_for)

    # ── Final report ──────────────────────────────────────────────────────────
    elapsed_min = int((_utc_now() - state["start"]).total_seconds() / 60)
    snaps   = state["acc_snapshots"]
    closing = state["acc_closing"]

    if snaps > 0 and closing > 0:
        classification = "SUCCESS"
        reason = f"snapshots +{snaps}, external_closing +{closing}"
    elif snaps > 0:
        classification = "PARTIAL_SUCCESS"
        reason = f"snapshots +{snaps} but external_closing still 0"
    else:
        classification = "FAILED"
        reason = "no snapshot growth over 8 hours"

    banner = "\n" + "─" * 50
    print(banner)
    print("SYSTEM RUN SUMMARY")
    print("─" * 50)
    print(f"  Duration:               {elapsed_min} min")
    print(f"  Cycles completed:       {state['cycle']}")
    print(f"  Total snapshots added:  {snaps}")
    print(f"  External closing added: {closing}")
    print(f"  Settlements ingested:   {state['acc_settlements']}")
    print(f"  ROI change:             {state['acc_roi']:+.4f}")
    print(f"  Postmortems triggered:  {state['acc_postmortems']}")
    print(f"  Classification:         {classification}")
    print(f"  Reason: {reason}")
    print("─" * 50)

    final = {
        "timestamp": _iso(),
        "type": "final_summary",
        "cycles_completed": state["cycle"],
        "duration_minutes": elapsed_min,
        "total_snapshots_added": snaps,
        "total_external_closing_added": closing,
        "settlements_ingested": state["acc_settlements"],
        "roi_delta": state["acc_roi"],
        "postmortems_triggered": state["acc_postmortems"],
        "classification": classification,
        "reason": reason,
    }
    _append_jsonl(EVENTS_LOG, final)
    print(f"[{_iso()}] ops_monitor finished.")


if __name__ == "__main__":
    run()
