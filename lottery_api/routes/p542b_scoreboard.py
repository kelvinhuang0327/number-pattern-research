"""P542B read-only API for the committed P542A historical scoreboard."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

_SOURCE_ARTIFACT = (
    "outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json"
)
_ARTIFACT_PATH = Path(__file__).resolve().parents[2] / _SOURCE_ARTIFACT
_DESCRIPTIVE_NOTICE = (
    "Historical descriptive scoreboard artifact only; it is not a prediction, "
    "betting recommendation, or readiness claim."
)


def _load_scoreboard_artifact() -> tuple[dict[str, Any], str, int]:
    """Read and validate the single committed P542A JSON artifact."""
    try:
        raw = _ARTIFACT_PATH.read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="P542A scoreboard artifact is not available.",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=422,
            detail="P542A scoreboard artifact cannot be read safely.",
        ) from exc

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="P542A scoreboard artifact is not valid JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail="P542A scoreboard artifact must contain a JSON object.",
        )
    return payload, hashlib.sha256(raw).hexdigest(), len(raw)


@router.get("/api/research/p542a/scoreboard")
def get_p542a_scoreboard() -> dict[str, Any]:
    """Expose the already-committed P542A report without regenerating it."""
    data, artifact_sha256, artifact_bytes = _load_scoreboard_artifact()
    return {
        "ok": True,
        "task": "P542A",
        "descriptive_only": True,
        "notice": _DESCRIPTIVE_NOTICE,
        "source_artifact": _SOURCE_ARTIFACT,
        "artifact_sha256": artifact_sha256,
        "artifact_bytes": artifact_bytes,
        "data": data,
    }
