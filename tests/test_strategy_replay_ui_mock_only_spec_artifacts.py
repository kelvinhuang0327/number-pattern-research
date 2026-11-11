from pathlib import Path


BASE = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool/00-BettingPlan/20260510")


def test_mock_only_spec_artifacts_exist() -> None:
    expected_files = [
        BASE / "strategy_replay_ui_mock_only_wireframe_spec.md",
        BASE / "strategy_replay_ui_mock_only_interaction_flow.md",
        BASE / "strategy_replay_ui_mock_only_component_inventory.md",
        BASE / "strategy_replay_ui_mock_only_frontend_acceptance_checklist.md",
        BASE / "strategy_replay_ui_mock_only_wireframe_spec_report.md",
    ]

    for path in expected_files:
        assert path.is_file(), f"missing artifact: {path}"


def test_mock_only_spec_artifacts_contain_required_blockers() -> None:
    report_path = BASE / "strategy_replay_ui_mock_only_wireframe_spec_report.md"
    spec_path = BASE / "strategy_replay_ui_mock_only_wireframe_spec.md"
    flow_path = BASE / "strategy_replay_ui_mock_only_interaction_flow.md"
    checklist_path = BASE / "strategy_replay_ui_mock_only_frontend_acceptance_checklist.md"
    inventory_path = BASE / "strategy_replay_ui_mock_only_component_inventory.md"

    report_text = report_path.read_text(encoding="utf-8")
    spec_text = spec_path.read_text(encoding="utf-8")
    flow_text = flow_path.read_text(encoding="utf-8")
    checklist_text = checklist_path.read_text(encoding="utf-8")
    inventory_text = inventory_path.read_text(encoding="utf-8")

    required_report_lines = [
        "UI mock-only wireframe/spec package exists = true",
        "no frontend implementation was created = true",
        "production UI can start = false",
        "runtime production enablement can start = false",
        "production migration can start = false",
        "mock-only UI spec is not production UI = true",
        "P41_STRATEGY_REPLAY_UI_MOCK_ONLY_WIREFRAME_SPEC_READY",
    ]
    for line in required_report_lines:
        assert line in report_text

    required_warning_text = [
        "Mock-data/spec-only. Not production UI.",
        "No production migration has been executed.",
        "Historical strategy identity remains blocked unless explicit metadata source is accepted.",
        "Runtime production enablement is blocked.",
    ]
    for text in required_warning_text:
        assert text in spec_text
        assert text in flow_text or text in checklist_text

    required_components = [
        "StrategyReplayMockPage",
        "ProductionBlockedBanner",
        "ReplayReadinessPanel",
        "ReplayFilterPanel",
        "ReplayMockTable",
        "ReplayQualityBadge",
        "ReplayDetailDrawer",
        "ReplayDisabledActionNotice",
        "ReplayPagination",
        "ReplayEmptyState",
        "ReplayErrorState",
    ]
    for component in required_components:
        assert component in inventory_text

    assert "No production API call is allowed." in flow_text
    assert "No production launch button" in checklist_text
    assert "No migration button" in checklist_text
    assert "production UI can start = false" in checklist_text
    assert "runtime production enablement can start = false" in checklist_text
    assert "production migration can start = false" in checklist_text
