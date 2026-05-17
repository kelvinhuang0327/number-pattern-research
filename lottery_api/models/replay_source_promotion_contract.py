"""Replay source promotion contract for P5A."""
from __future__ import annotations

from typing import Any


PROMOTION_METHODS: tuple[str, ...] = (
    "MIGRATION",
    "SEED",
    "ARTIFACT_PROMOTION",
    "CONTROLLED_DB_APPLY",
    "HYBRID",
    "UNSUPPORTED",
)

PROMOTION_METHOD_METADATA: dict[str, dict[str, Any]] = {
    "MIGRATION": {
        "method": "MIGRATION",
        "deployment_safe": True,
        "reproducible": True,
        "auditable": True,
        "requires_db_write": True,
        "requires_human_approval": True,
        "supports_rollback": True,
        "recommended_for_historical_reconstruction": True,
        "notes": "Best for stable schema-managed promotion when replay rows are materialized through a versioned migration path.",
    },
    "SEED": {
        "method": "SEED",
        "deployment_safe": True,
        "reproducible": True,
        "auditable": True,
        "requires_db_write": True,
        "requires_human_approval": True,
        "supports_rollback": True,
        "recommended_for_historical_reconstruction": True,
        "notes": "Useful for bootstrapping a known-good deployment DB when replay rows are treated as seedable reference data.",
    },
    "ARTIFACT_PROMOTION": {
        "method": "ARTIFACT_PROMOTION",
        "deployment_safe": True,
        "reproducible": True,
        "auditable": True,
        "requires_db_write": False,
        "requires_human_approval": True,
        "supports_rollback": True,
        "recommended_for_historical_reconstruction": True,
        "notes": "Preferred for promoting dry-run replay artifacts into a deployment-controlled DB or packaged artifact pipeline.",
    },
    "CONTROLLED_DB_APPLY": {
        "method": "CONTROLLED_DB_APPLY",
        "deployment_safe": True,
        "reproducible": True,
        "auditable": True,
        "requires_db_write": True,
        "requires_human_approval": True,
        "supports_rollback": True,
        "recommended_for_historical_reconstruction": True,
        "notes": "Explicit controlled apply is acceptable when accompanied by diff, approval, rollback, and post-apply verification gates.",
    },
    "HYBRID": {
        "method": "HYBRID",
        "deployment_safe": True,
        "reproducible": True,
        "auditable": True,
        "requires_db_write": True,
        "requires_human_approval": True,
        "supports_rollback": True,
        "recommended_for_historical_reconstruction": True,
        "notes": "Hybrid promotion may combine artifact promotion for review and controlled DB apply for final deployment.",
    },
    "UNSUPPORTED": {
        "method": "UNSUPPORTED",
        "deployment_safe": False,
        "reproducible": False,
        "auditable": False,
        "requires_db_write": False,
        "requires_human_approval": False,
        "supports_rollback": False,
        "recommended_for_historical_reconstruction": False,
        "notes": "Malformed or insufficient promotion plan.",
    },
}


def _normalize_method(method: str | None) -> str:
    if not method:
        return "UNSUPPORTED"
    method = method.upper()
    return method if method in PROMOTION_METHODS else "UNSUPPORTED"


def get_promotion_method_metadata(method: str | None) -> dict[str, Any]:
    return dict(PROMOTION_METHOD_METADATA[_normalize_method(method)])


def is_deployment_safe_method(method: str | None) -> bool:
    return bool(get_promotion_method_metadata(method)["deployment_safe"])


def is_reproducible_method(method: str | None) -> bool:
    return bool(get_promotion_method_metadata(method)["reproducible"])


def requires_db_write(method: str | None) -> bool:
    return bool(get_promotion_method_metadata(method)["requires_db_write"])


def requires_human_approval(method: str | None) -> bool:
    return bool(get_promotion_method_metadata(method)["requires_human_approval"])


def supports_rollback(method: str | None) -> bool:
    return bool(get_promotion_method_metadata(method)["supports_rollback"])


def recommended_for_historical_reconstruction(method: str | None) -> bool:
    return bool(get_promotion_method_metadata(method)["recommended_for_historical_reconstruction"])


def can_execute_in_p5a(_method: str | None) -> bool:
    return False
