"""Contract tests for the P5A replay source promotion policy."""
from __future__ import annotations

from lottery_api.models.replay_source_promotion_contract import (
    PROMOTION_METHODS,
    can_execute_in_p5a,
    get_promotion_method_metadata,
    is_deployment_safe_method,
    is_reproducible_method,
    recommended_for_historical_reconstruction,
    requires_db_write,
    requires_human_approval,
    supports_rollback,
)


def test_promotion_contract_accepts_all_6_methods():
    assert PROMOTION_METHODS == (
        "MIGRATION",
        "SEED",
        "ARTIFACT_PROMOTION",
        "CONTROLLED_DB_APPLY",
        "HYBRID",
        "UNSUPPORTED",
    )


def test_can_execute_in_p5a_is_false_for_every_method():
    for method in PROMOTION_METHODS:
        assert can_execute_in_p5a(method) is False


def test_method_metadata_fields_are_populated():
    for method in PROMOTION_METHODS:
        meta = get_promotion_method_metadata(method)
        assert meta["method"] == method
        assert isinstance(meta["deployment_safe"], bool)
        assert isinstance(meta["reproducible"], bool)
        assert isinstance(meta["auditable"], bool)
        assert isinstance(meta["requires_db_write"], bool)
        assert isinstance(meta["requires_human_approval"], bool)
        assert isinstance(meta["supports_rollback"], bool)
        assert isinstance(meta["recommended_for_historical_reconstruction"], bool)


def test_known_methods_have_expected_safety_shape():
    assert is_deployment_safe_method("ARTIFACT_PROMOTION") is True
    assert is_reproducible_method("ARTIFACT_PROMOTION") is True
    assert requires_db_write("ARTIFACT_PROMOTION") is False
    assert requires_human_approval("ARTIFACT_PROMOTION") is True
    assert supports_rollback("ARTIFACT_PROMOTION") is True
    assert recommended_for_historical_reconstruction("ARTIFACT_PROMOTION") is True
