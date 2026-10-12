"""
Human Review Queue — Phase 24
==============================
Persistent approval gate between autonomous sandbox evaluation and any
production-impacting action.

Persists to:
    runtime/agent_orchestrator/human_review_queue.json

Review life-cycle:
    PENDING → APPROVED | REJECTED | MORE_DATA_REQUESTED

Hard rules (must hold for every code-path):
  - production_patch_allowed  is ALWAYS False in queue items
  - production_model_modified is ALWAYS False
  - external_llm_called       is ALWAYS False
  - APPROVED status only unlocks follow-up validation/proposal tasks,
    NEVER directly applies a production patch.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "human_review_queue.json"

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_PENDING    = "PENDING"
STATUS_APPROVED   = "APPROVED"
STATUS_REJECTED   = "REJECTED"
STATUS_MORE_DATA  = "MORE_DATA_REQUESTED"

# ── Review type constants ─────────────────────────────────────────────────────
RT_PRODUCTION_PROPOSAL = "production_patch_proposal"
RT_SANDBOX_UNCERTAIN   = "sandbox_uncertain"
RT_MANUAL              = "manual_review"

# ── Risk levels ───────────────────────────────────────────────────────────────
RISK_LOW    = "low"
RISK_MEDIUM = "medium"
RISK_HIGH   = "high"

# ── Allowed next task families per review outcome ────────────────────────────
NTF_PROPOSAL_VALIDATION  = "production-proposal-validation"
NTF_PAPER_ROLLOUT        = "paper-rollout-plan"
NTF_ADDITIONAL_VALIDATION = "additional-validation"
NTF_CLV_QUALITY          = "clv-quality-analysis"
NTF_MODEL_VALIDATION     = "model-validation-atomic"

MAX_QUEUE_ITEMS = 200


# ── I/O helpers ───────────────────────────────────────────────────────────────

def load_queue() -> list[dict]:
    """Return queue as a list of item dicts (oldest first)."""
    if not QUEUE_PATH.exists():
        return []
    try:
        raw = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        # Legacy: support {"items": [...]} wrapper
        return raw.get("items", [])
    except Exception as exc:
        logger.warning("[ReviewQueue] Failed to load queue: %s", exc)
        return []


def _save_queue(items: list[dict]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core queue operations ─────────────────────────────────────────────────────

def queue_review_item(
    *,
    source: str,
    source_task_id: str,
    source_decision_id: str,
    review_type: str,
    title: str,
    summary: str,
    risk_level: str = RISK_MEDIUM,
    recommended_action: str = "",
    allowed_next_task_family: Optional[str] = None,
) -> dict:
    """
    Add a review item to the queue and return the created item.
    If a PENDING item with the same ``source_decision_id`` already exists,
    return it without creating a duplicate.

    Never modifies production model; always sets:
        production_patch_allowed  = False
        production_model_modified = False
        external_llm_called       = False
    """
    items = load_queue()

    # Deduplication: skip if already queued (any status) for same source_decision_id
    for existing in items:
        if existing.get("source_decision_id") == source_decision_id:
            logger.info(
                "[ReviewQueue] Skipping duplicate for source_decision_id=%s (existing review_id=%s)",
                source_decision_id,
                existing.get("review_id"),
            )
            return existing

    review_id = f"hrq_{uuid.uuid4().hex[:12]}"
    item: dict = {
        "review_id": review_id,
        "created_at_utc": _now_iso(),
        "source": source,
        "source_task_id": source_task_id,
        "source_decision_id": source_decision_id,
        "review_type": review_type,
        "title": title,
        "summary": summary,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "status": STATUS_PENDING,
        "reviewer": None,
        "reviewed_at_utc": None,
        "review_notes": None,
        "allowed_next_task_family": allowed_next_task_family,
        # Hard-coded safety invariants — NEVER overridable
        "production_patch_allowed": False,
        "production_model_modified": False,
        "external_llm_called": False,
    }

    items.append(item)
    # Cap at MAX_QUEUE_ITEMS (keep newest)
    if len(items) > MAX_QUEUE_ITEMS:
        items = items[-MAX_QUEUE_ITEMS:]

    _save_queue(items)
    logger.info(
        "[ReviewQueue] Queued %s review_id=%s source_decision_id=%s",
        review_type,
        review_id,
        source_decision_id,
    )
    return item


def _update_item(review_id: str, updates: dict) -> Optional[dict]:
    """Apply ``updates`` to the item with ``review_id`` and persist."""
    items = load_queue()
    for item in items:
        if item.get("review_id") == review_id:
            item.update(updates)
            _save_queue(items)
            return item
    logger.warning("[ReviewQueue] review_id=%s not found", review_id)
    return None


def approve_review(
    review_id: str,
    reviewer: str,
    notes: str = "",
) -> Optional[dict]:
    """
    Mark a review item APPROVED.

    APPROVED only unlocks follow-up validation/proposal task creation.
    It does NOT apply a production patch or modify any model.
    """
    return _update_item(
        review_id,
        {
            "status": STATUS_APPROVED,
            "reviewer": reviewer,
            "reviewed_at_utc": _now_iso(),
            "review_notes": notes,
            # Invariants must remain False even after approval
            "production_patch_allowed": False,
            "production_model_modified": False,
        },
    )


def reject_review(
    review_id: str,
    reviewer: str,
    notes: str = "",
) -> Optional[dict]:
    """Mark a review item REJECTED — blocks all follow-up tasks."""
    return _update_item(
        review_id,
        {
            "status": STATUS_REJECTED,
            "reviewer": reviewer,
            "reviewed_at_utc": _now_iso(),
            "review_notes": notes,
        },
    )


def request_more_data(
    review_id: str,
    reviewer: str,
    notes: str = "",
) -> Optional[dict]:
    """
    Mark a review item MORE_DATA_REQUESTED.
    Allows clv_quality_analysis or model-validation-atomic follow-up.
    """
    return _update_item(
        review_id,
        {
            "status": STATUS_MORE_DATA,
            "reviewer": reviewer,
            "reviewed_at_utc": _now_iso(),
            "review_notes": notes,
            "allowed_next_task_family": NTF_CLV_QUALITY,
        },
    )


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_all_reviews(n: int = 50) -> list[dict]:
    """Return last n items (newest first)."""
    return list(reversed(load_queue()[-n:]))


def get_pending_reviews() -> list[dict]:
    return [i for i in load_queue() if i.get("status") == STATUS_PENDING]


def get_approved_reviews() -> list[dict]:
    return [i for i in load_queue() if i.get("status") == STATUS_APPROVED]


def get_rejected_reviews() -> list[dict]:
    return [i for i in load_queue() if i.get("status") == STATUS_REJECTED]


def get_more_data_reviews() -> list[dict]:
    return [i for i in load_queue() if i.get("status") == STATUS_MORE_DATA]


def get_review_by_id(review_id: str) -> Optional[dict]:
    for item in load_queue():
        if item.get("review_id") == review_id:
            return item
    return None


def get_latest_review() -> Optional[dict]:
    items = load_queue()
    return items[-1] if items else None


def has_pending_reviews() -> bool:
    return bool(get_pending_reviews())


def get_queue_summary() -> dict:
    """Return a lightweight summary for ops/readiness exposure."""
    items = load_queue()
    pending   = [i for i in items if i.get("status") == STATUS_PENDING]
    approved  = [i for i in items if i.get("status") == STATUS_APPROVED]
    rejected  = [i for i in items if i.get("status") == STATUS_REJECTED]
    more_data = [i for i in items if i.get("status") == STATUS_MORE_DATA]

    latest = items[-1] if items else None
    latest_card: Optional[dict] = None
    if latest:
        latest_card = {
            "review_id":         latest.get("review_id"),
            "review_type":       latest.get("review_type"),
            "risk_level":        latest.get("risk_level"),
            "status":            latest.get("status"),
            "recommended_action": latest.get("recommended_action"),
            "created_at_utc":    latest.get("created_at_utc"),
            "reviewed_at_utc":   latest.get("reviewed_at_utc"),
            "reviewer":          latest.get("reviewer"),
            "production_patch_allowed": latest.get("production_patch_allowed", False),
        }

    return {
        "total":               len(items),
        "pending_count":       len(pending),
        "approved_count":      len(approved),
        "rejected_count":      len(rejected),
        "more_data_count":     len(more_data),
        "blocked_by_human_review": bool(pending),
        "latest_review":       latest_card,
        # Full lists (trimmed to 10 for display)
        "pending_reviews":     pending[-10:],
        "approved_reviews":    approved[-10:],
        "rejected_reviews":    rejected[-10:],
        "more_data_requested": more_data[-10:],
    }
