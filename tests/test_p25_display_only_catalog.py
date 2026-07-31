"""
test_p25_display_only_catalog.py
================================
P25 — Display-Only Catalog: Contract + UI-string tests

Safety invariants (enforced by this test suite):
  - No production DB write
  - No backfill, no replay generation, no strategy promotion
  - All tests are READ-ONLY

Coverage:
  A. API contract — GET /api/replay/strategies with lifecycle filters
  B. Registry completeness — all 16 canonical strategies present
  C. UI string checks — rpRenderCatalogDisplayMode in index.html
  D. Non-regression — ONLINE strategies still have replay rows (no data loss)
  E. Safety strings — no backfill / no-write invariants in UI code
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"

sys.path.insert(0, str(LOTTERY_API))

from routes.replay import get_strategies_response
from models.replay_strategy_registry import (
    list_strategies,
    list_non_executable_strategy_ids,
    list_executable_strategy_ids,
)

INDEX_HTML = REPO_ROOT / "index.html"


def _strategies(
    lottery_type: str | None = None,
    lifecycle_status: str | None = None,
    public_only: bool = False,
) -> Dict[str, Any]:
    # Use get_strategies_response (sync) directly to avoid FastAPI Query-object
    # coercion issues that occur when calling async route functions directly.
    return get_strategies_response(
        lottery_type=lottery_type,
        lifecycle_status=lifecycle_status,
        public_only=public_only,
    )


# ─── Section A: API contract ──────────────────────────────────────────────────

class TestStrategiesApiContract:
    """GET /api/replay/strategies contract tests (P25 catalog visibility)."""

    def test_no_filter_returns_all_strategies(self):
        data = _strategies()
        assert "strategies" in data
        assert "count" in data
        assert isinstance(data["strategies"], list)
        assert data["count"] == len(data["strategies"])
        assert data["count"] >= 16, (
            f"Expected at least 16 canonical strategies, got {data['count']}"
        )

    def test_response_has_required_fields(self):
        data = _strategies()
        required = {"strategies", "count", "filter_lottery_type",
                    "filter_lifecycle_status", "filter"}
        for field in required:
            assert field in data, f"Missing required field: {field!r}"

    def test_each_strategy_has_required_keys(self):
        data = _strategies()
        required_keys = {
            "strategy_id", "strategy_name", "strategy_version",
            "supported_lottery_types", "strategy_lifecycle_status",
        }
        for s in data["strategies"]:
            for k in required_keys:
                assert k in s, (
                    f"Strategy {s.get('strategy_id')} missing key {k!r}"
                )

    def test_filter_rejected_returns_only_rejected(self):
        data = _strategies(lifecycle_status="REJECTED")
        strategies = data["strategies"]
        assert len(strategies) >= 1, "Expected at least 1 REJECTED strategy"
        for s in strategies:
            assert s["strategy_lifecycle_status"] == "REJECTED", (
                f"{s['strategy_id']} is not REJECTED: {s['strategy_lifecycle_status']}"
            )

    def test_filter_retired_returns_only_retired(self):
        data = _strategies(lifecycle_status="RETIRED")
        strategies = data["strategies"]
        assert len(strategies) >= 1, "Expected at least 1 RETIRED strategy"
        for s in strategies:
            assert s["strategy_lifecycle_status"] == "RETIRED", (
                f"{s['strategy_id']} is not RETIRED: {s['strategy_lifecycle_status']}"
            )

    def test_filter_observation_returns_only_observation(self):
        data = _strategies(lifecycle_status="OBSERVATION")
        strategies = data["strategies"]
        assert len(strategies) >= 1, "Expected at least 1 OBSERVATION strategy"
        for s in strategies:
            assert s["strategy_lifecycle_status"] == "OBSERVATION", (
                f"{s['strategy_id']} is not OBSERVATION: {s['strategy_lifecycle_status']}"
            )

    def test_filter_online_returns_only_online(self):
        data = _strategies(lifecycle_status="ONLINE")
        strategies = data["strategies"]
        assert len(strategies) >= 1, "Expected at least 1 ONLINE strategy"
        for s in strategies:
            assert s["strategy_lifecycle_status"] == "ONLINE", (
                f"{s['strategy_id']} is not ONLINE: {s['strategy_lifecycle_status']}"
            )

    def test_filter_offline_returns_list(self):
        # OFFLINE may be empty list — must still return valid shape
        data = _strategies(lifecycle_status="OFFLINE")
        assert isinstance(data["strategies"], list)
        assert data["count"] == len(data["strategies"])

    def test_lottery_type_filter_narrows_results(self):
        all_data = _strategies()
        power_data = _strategies(lottery_type="POWER_LOTTO")
        assert power_data["count"] <= all_data["count"], (
            "Lottery type filter should return <= total strategies"
        )
        for s in power_data["strategies"]:
            assert "POWER_LOTTO" in s["supported_lottery_types"], (
                f"{s['strategy_id']} does not support POWER_LOTTO"
            )

    def test_combined_filter_lifecycle_and_lottery(self):
        data = _strategies(lifecycle_status="REJECTED", lottery_type="BIG_LOTTO")
        for s in data["strategies"]:
            assert s["strategy_lifecycle_status"] == "REJECTED"
            assert "BIG_LOTTO" in s["supported_lottery_types"]


# ─── Section B: Registry completeness ────────────────────────────────────────

class TestRegistryCompleteness:
    """Ensures all 16 canonical strategies are discoverable via list_strategies."""

    # Known canonical IDs as of P25 + P1.3 (8b4ffc8 added fourier_rhythm_3bet
    # and ts3_regime_3bet as ONLINE on 2026-05-19).
    ONLINE_IDS = {
        "power_precision_3bet",
        "power_orthogonal_5bet",
        "biglotto_triple_strike",
        "biglotto_deviation_2bet",
        "daily539_f4cold",
        "daily539_markov_cold",
        "fourier_rhythm_3bet",   # added P1.3 (commit 8b4ffc8, 2026-05-19)
        "ts3_regime_3bet",       # added P1.3 (commit 8b4ffc8, 2026-05-19)
    }
    REJECTED_IDS = {
        "biglotto_ts3_acb_4bet",
        "biglotto_ts3_markov_freq_5bet",
        "power_shlc_midfreq",
        "p1_deviation_2bet_539",
    }
    RETIRED_IDS = {
        "acb_1bet",
        "acb_markov_midfreq",
        "acb_markov_midfreq_3bet",
        "midfreq_acb_2bet",
        "midfreq_fourier_2bet",
    }
    OBSERVATION_IDS = {
        "h6_gate_mk20_ew85",
    }

    def _all_ids(self) -> set:
        return {s["strategy_id"] for s in list_strategies()}

    def test_total_canonical_count(self):
        all_ids = self._all_ids()
        assert len(all_ids) >= 16, (
            f"Expected >= 16 canonical strategies, got {len(all_ids)}: {sorted(all_ids)}"
        )

    def test_all_online_ids_present(self):
        all_ids = self._all_ids()
        for sid in self.ONLINE_IDS:
            assert sid in all_ids, f"ONLINE strategy missing: {sid!r}"

    def test_all_rejected_ids_present(self):
        all_ids = self._all_ids()
        for sid in self.REJECTED_IDS:
            assert sid in all_ids, f"REJECTED strategy missing: {sid!r}"

    def test_all_retired_ids_present(self):
        all_ids = self._all_ids()
        for sid in self.RETIRED_IDS:
            assert sid in all_ids, f"RETIRED strategy missing: {sid!r}"

    def test_all_observation_ids_present(self):
        all_ids = self._all_ids()
        for sid in self.OBSERVATION_IDS:
            assert sid in all_ids, f"OBSERVATION strategy missing: {sid!r}"

    def test_non_online_strategies_are_non_executable(self):
        exec_ids = set(list_executable_strategy_ids())
        non_exec_ids = set(list_non_executable_strategy_ids())
        for sid in (self.REJECTED_IDS | self.RETIRED_IDS | self.OBSERVATION_IDS):
            # Should NOT be in the generation-eligible set
            assert sid not in exec_ids, (
                f"Non-ONLINE strategy {sid!r} should not be executable"
            )
            assert sid in non_exec_ids, (
                f"Non-ONLINE strategy {sid!r} should appear in non-executable set"
            )

    def test_online_strategies_are_executable(self):
        exec_ids = set(list_executable_strategy_ids())
        for sid in self.ONLINE_IDS:
            assert sid in exec_ids, (
                f"ONLINE strategy {sid!r} should be executable"
            )


# ─── Section C: UI string validation ─────────────────────────────────────────

class TestDisplayOnlyCatalogUI:
    """
    Static HTML/JS inspection for P25 Catalog Display Mode.
    Reads index.html as text — no browser, no Playwright, no external calls.
    """

    @pytest.fixture(scope="class")
    def html(self) -> str:
        assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
        return INDEX_HTML.read_text(encoding="utf-8")

    def test_rpRenderCatalogDisplayMode_function_present(self, html):
        assert "rpRenderCatalogDisplayMode" in html, (
            "Missing rpRenderCatalogDisplayMode function in index.html"
        )

    def test_rpEscapeHtml_function_present(self, html):
        assert "rpEscapeHtml" in html, (
            "Missing rpEscapeHtml helper in index.html"
        )

    def test_rpCatalogLifecycleBadge_function_present(self, html):
        assert "rpCatalogLifecycleBadge" in html, (
            "Missing rpCatalogLifecycleBadge function in index.html"
        )

    def test_catalog_mode_calls_strategies_api(self, html):
        # The catalog display function must fetch from /strategies
        assert "/strategies?" in html or "strategies?lifecycle_status" in html, (
            "rpRenderCatalogDisplayMode must call /api/replay/strategies endpoint"
        )

    def test_catalog_mode_dispatches_for_non_online(self, html):
        # The rpQuery must branch on non-ONLINE lifecycle
        assert "lc !== 'ONLINE'" in html or "lc != 'ONLINE'" in html, (
            "rpQuery must dispatch to catalog mode when lc !== 'ONLINE'"
        )

    def test_catalog_rows_have_data_catalog_mode_attribute(self, html):
        assert 'data-catalog-mode="true"' in html, (
            "Catalog display rows must have data-catalog-mode='true' for test targeting"
        )

    def test_old_backfill_placeholder_text_removed(self, html):
        # The old text implied a backfill would happen — must be gone
        assert "等待 catalog backfill" not in html, (
            "Old backfill placeholder text must be removed in P25"
        )

    def test_lifecycle_badge_covers_rejected(self, html):
        assert "REJECTED" in html, "Must display REJECTED lifecycle badge"

    def test_lifecycle_badge_covers_retired(self, html):
        assert "RETIRED" in html, "Must display RETIRED lifecycle badge"

    def test_lifecycle_badge_covers_observation(self, html):
        assert "OBSERVATION" in html, "Must display OBSERVATION lifecycle badge"

    def test_no_prediction_claim_in_catalog_mode(self, html):
        # Catalog mode must show disclaimer, not a prediction claim
        assert "不代表預測成績" in html or "不構成下注建議" in html, (
            "Catalog mode must have safety disclaimer"
        )

    def test_no_generate_call_in_catalog_path(self, html):
        # Catalog display path must not trigger any /generate or /run endpoint
        import re
        # Check that the catalog function body does not contain /generate
        catalog_fn_match = re.search(
            r"async function rpRenderCatalogDisplayMode.*?(?=\n  (?:async )?function |\Z)",
            html,
            re.DOTALL,
        )
        if catalog_fn_match:
            fn_body = catalog_fn_match.group(0)
            assert "/generate" not in fn_body, (
                "rpRenderCatalogDisplayMode must not call /generate endpoint"
            )
            assert "/run" not in fn_body, (
                "rpRenderCatalogDisplayMode must not call /run endpoint"
            )


# ─── Section D: Non-regression (ONLINE strategies) ───────────────────────────

class TestOnlineStrategiesNonRegression:
    """ONLINE strategies must remain unchanged — no data loss."""

    def test_online_strategy_count_unchanged(self):
        # P25 baseline = 6 strategies; P1.3 (commit 8b4ffc8, 2026-05-19) added
        # fourier_rhythm_3bet and ts3_regime_3bet → updated baseline = 8.
        online = list_strategies(lifecycle_status="ONLINE")
        assert len(online) == 8, (
            f"Expected exactly 8 ONLINE strategies (P1.3 updated baseline), got {len(online)}"
        )

    def test_online_strategy_ids_unchanged(self):
        online = list_strategies(lifecycle_status="ONLINE")
        ids = {s["strategy_id"] for s in online}
        # P1.3 (commit 8b4ffc8, 2026-05-19) added fourier_rhythm_3bet and ts3_regime_3bet.
        expected = {
            "power_precision_3bet", "power_orthogonal_5bet",
            "biglotto_triple_strike", "biglotto_deviation_2bet",
            "daily539_f4cold", "daily539_markov_cold",
            "fourier_rhythm_3bet",
            "ts3_regime_3bet",
        }
        assert ids == expected, (
            f"ONLINE strategy IDs changed.\nExpected: {sorted(expected)}\nGot: {sorted(ids)}"
        )

    def test_no_lifecycle_status_in_online_row_is_not_online(self):
        """All ONLINE strategies must have lifecycle_status == 'ONLINE'."""
        online = list_strategies(lifecycle_status="ONLINE")
        for s in online:
            assert s["strategy_lifecycle_status"] == "ONLINE", (
                f"{s['strategy_id']} has wrong lifecycle: {s['strategy_lifecycle_status']}"
            )


# ─── Section E: Safety / no-write invariants ─────────────────────────────────

class TestSafetyInvariants:
    """
    Enforce hard safety rules for P25:
      - No DB write in catalog display path
      - No backfill-related text in UI
      - Catalog rows are display-only (no action triggers)
    """

    @pytest.fixture(scope="class")
    def html(self) -> str:
        return INDEX_HTML.read_text(encoding="utf-8")

    def test_no_backfill_word_in_index_html(self, html):
        # Any "backfill" reference in the replay JS must not imply an action
        # The word may appear in comments but not as user-facing text
        import re
        # Look for user-facing backfill text (not in comments)
        lines = html.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "backfill" in stripped.lower() and not stripped.startswith("//") and not stripped.startswith("*"):
                pytest.fail(
                    f"Unexpected 'backfill' user-facing text at line {i}: {stripped[:120]}"
                )

    def test_catalog_display_mode_is_read_only(self):
        """
        list_strategies() must not modify any state.
        We call it twice and assert the result is identical (idempotent / read-only).
        """
        result1 = list_strategies()
        result2 = list_strategies()
        ids1 = [s["strategy_id"] for s in result1]
        ids2 = [s["strategy_id"] for s in result2]
        assert ids1 == ids2, "list_strategies() is not idempotent — possible state mutation"

    def test_catalog_mode_does_not_write_db(self, html):
        """
        The catalog display path must not contain INSERT/UPDATE/DELETE SQL patterns.
        Static check only.
        """
        import re
        catalog_fn_match = re.search(
            r"async function rpRenderCatalogDisplayMode.*?(?=\n  (?:async )?function |\Z)",
            html,
            re.DOTALL,
        )
        if catalog_fn_match:
            fn_body = catalog_fn_match.group(0).lower()
            for forbidden in ("insert into", "update ", "delete from", "drop table"):
                assert forbidden not in fn_body, (
                    f"Catalog display mode contains SQL write operation: {forbidden!r}"
                )
