from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TSL_STATUS_PATH = ROOT / "data" / "tsl_fetch_status.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_tsl_fetch_status(
    *,
    success: bool,
    games_count: int,
    source: str,
    error: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": source,
        "success": success,
        "games_count": games_count,
        "error": error or "",
        "note": note or "",
        "fetched_at": _utc_now(),
    }
    TSL_STATUS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def read_tsl_fetch_status() -> dict[str, Any]:
    if not TSL_STATUS_PATH.exists():
        return {}
    try:
        return json.loads(TSL_STATUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def classify_tsl_feed_status(status: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize raw fetch status into a reusable health classification."""
    if not status:
        return {
            "state": "unknown",
            "severity": "MEDIUM",
            "blocked": False,
            "stale_or_degraded": True,
            "summary": "TSL feed status unavailable",
        }

    if status.get("success"):
        return {
            "state": "healthy",
            "severity": "LOW",
            "blocked": False,
            "stale_or_degraded": False,
            "summary": f"TSL healthy via {status.get('source', '')}",
        }

    note = str(status.get("note") or status.get("error") or "")
    source = str(status.get("source") or "")
    if "modern_pre_" in note and "403" in note:
        return {
            "state": "blocked",
            "severity": "HIGH",
            "blocked": True,
            "stale_or_degraded": True,
            "summary": f"TSL pre-match blocked at official source ({source})",
        }
    if "legacy_fetch_failed" in note:
        return {
            "state": "migrating",
            "severity": "MEDIUM",
            "blocked": False,
            "stale_or_degraded": True,
            "summary": f"Legacy TSL endpoint no longer machine-readable ({source})",
        }
    return {
        "state": "degraded",
        "severity": "MEDIUM",
        "blocked": False,
        "stale_or_degraded": True,
        "summary": f"TSL degraded ({source})",
    }
