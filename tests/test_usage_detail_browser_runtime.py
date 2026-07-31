"""
tests/test_usage_detail_browser_runtime.py

Phase UI-2: Usage Detail Browser Runtime Verification
=====================================================
Verifies that the served HTML and live API data support correct
browser-side rendering of the Usage 詳細 card.

Test classes:
  TestServedHtmlContent       — served index.html has required markers
  TestApiUsageRecentRows      — /api/orchestrator/usage?hours=24 recent rows have provider
  TestRebuildAgentsLogic      — _rebuildAgentsFromRecent logic (Python simulation)
  TestNormalisePayloadLogic   — _normaliseUsageReaderPayload logic (Python simulation)
  TestProviderDisplayMapping  — _PROVIDER_DISPLAY_MAP coverage
  TestApiStructureLive        — live API integration (skipped without running server)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
INDEX_HTML = PROJECT_ROOT / "runtime" / "agent_orchestrator" / "frontend" / "index.html"

# ── Helpers ───────────────────────────────────────────────────────────────

def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _api_get(path: str, timeout: int = 5) -> dict[str, Any] | None:
    """HTTP GET against the running proxy; returns parsed JSON or None."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8789{path}", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _server_live() -> bool:
    """Return True if proxy is reachable."""
    return _api_get("/api/orchestrator/summary") is not None


# ── Python simulation of JS functions ─────────────────────────────────────

_PROVIDER_DISPLAY_MAP: dict[str, str] = {
    "github-copilot": "Copilot-Daemon",
    "copilot": "Copilot-Daemon",
    "copilot-daemon": "Copilot-Daemon",
    "codex": "Codex",
    "codex-cli": "Codex CLI",
    "claude": "Claude",
    "claude-cli": "Claude CLI",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "github-cli": "GitHub CLI",
    "github-api": "GitHub API",
    "git-remote": "Git Remote",
    "gemini": "Gemini",
    "gemini-cli": "Gemini CLI",
}


def _provider_display(raw: str | None) -> str:
    if not raw or raw == "—":
        return raw or "—"
    return _PROVIDER_DISPLAY_MAP.get(raw.lower(), raw)


def _normalise_usage_reader_payload(d: dict) -> dict:
    """Python equivalent of JS _normaliseUsageReaderPayload."""
    by_role = d.get("by_role", {})
    roles: dict[str, Any] = {}
    for role, data in by_role.items():
        roles[role] = {
            "calls": data.get("total", 0),
            "blocked": data.get("blocked", 0),
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "premium_requests": 0,
            "agents": {},
        }
    tokens = d.get("tokens", {})
    recent = []
    for r in d.get("recent", []):
        recent.append({
            "time": r.get("timestamp", "—")[:8] if r.get("timestamp") else "—",
            "role": r.get("role") or "—",
            "agent": _provider_display(r.get("provider")) or "—",
            "task_id": r.get("task_id"),
            "parsed": r.get("success") is True,
            "premium_requests": r.get("premium_requests", 0),
            "rate_limit": "⚠️ RL" if r.get("rate_limit") else "—",
            "blocked": bool(r.get("blocked")),
            "block_reason": r.get("block_reason"),
        })
    return {
        "roles": roles,
        "total": {
            "calls": d.get("total", 0),
            "input_tokens": tokens.get("input", 0),
            "output_tokens": tokens.get("output", 0),
        },
        "warnings": [],
        "recent": recent,
        "malformed_count": d.get("malformed", 0),
    }


def _rebuild_agents_from_recent(payload: dict) -> None:
    """Python equivalent of JS _rebuildAgentsFromRecent (mutates in-place)."""
    roles = payload.get("roles", {})
    for row in payload.get("recent", []):
        if row.get("blocked"):
            continue
        role = row.get("role") or "unknown"
        agent = row.get("agent") or "—"
        if not agent or agent == "—":
            continue
        if role not in roles:
            roles[role] = {"calls": 0, "blocked": 0, "input_tokens": 0,
                           "output_tokens": 0, "cached_tokens": 0, "premium_requests": 0, "agents": {}}
        if "agents" not in roles[role]:
            roles[role]["agents"] = {}
        if agent not in roles[role]["agents"]:
            roles[role]["agents"][agent] = {"calls": 0, "input_tokens": 0,
                                             "output_tokens": 0, "cached_tokens": 0}
        roles[role]["agents"][agent]["calls"] += 1


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1 — Served HTML content
# ══════════════════════════════════════════════════════════════════════════════

class TestServedHtmlContent:
    """Verify the index.html on disk has all required markers for Usage 詳細."""

    def test_html_file_exists(self):
        assert INDEX_HTML.exists(), f"index.html not found: {INDEX_HTML}"

    def test_html_contains_usage_detail_text(self):
        assert "Usage 詳細" in _html()

    def test_html_contains_rebuild_agents_function(self):
        assert "_rebuildAgentsFromRecent" in _html()

    def test_html_contains_provider_display_map(self):
        assert "_PROVIDER_DISPLAY_MAP" in _html()

    def test_html_contains_normalise_function(self):
        assert "_normaliseUsageReaderPayload" in _html()

    def test_html_contains_provider_display_function(self):
        assert "_providerDisplay" in _html()

    def test_html_contains_usage_section_id(self):
        assert 'id="usage-section"' in _html()

    def test_html_contains_worker_body_id(self):
        assert 'id="usage-worker-body"' in _html()

    def test_html_contains_planner_body_id(self):
        assert 'id="usage-planner-body"' in _html()

    def test_html_contains_cto_body_id(self):
        assert 'id="usage-cto-body"' in _html()

    def test_html_contains_recent_table_id(self):
        assert 'id="usage-recent-tbody"' in _html()

    def test_html_github_copilot_maps_to_copilot_daemon(self):
        html = _html()
        assert "'github-copilot': 'Copilot-Daemon'" in html or \
               '"github-copilot": "Copilot-Daemon"' in html or \
               "'github-copilot':'Copilot-Daemon'" in html

    def test_html_claude_maps_to_claude(self):
        html = _html()
        # Map entries are space-padded for alignment: 'claude':         'Claude'
        assert "'claude'" in html and "'Claude'" in html

    def test_html_priority_2_hours_24(self):
        """_fetchUsageDetail must include hours=24 fallback."""
        assert "hours=24" in _html()

    def test_html_priority_1_summary_usage_detail(self):
        """_fetchUsageDetail must check summary.usage_detail first."""
        assert "usage_detail" in _html()

    def test_html_fetch_priority_order(self):
        """Priority 1 (summary) must appear before Priority 2 (hours=24) in source."""
        html = _html()
        idx_summary = html.find("api/orchestrator/summary")
        idx_hours24 = html.find("hours=24")
        assert idx_summary < idx_hours24, \
            "Priority 1 (summary) must appear before Priority 2 (hours=24)"


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2 — API recent rows have provider field
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _server_live(), reason="requires running server at 8789")
class TestApiUsageRecentRows:
    """Verify live API returns recent rows with provider field."""

    def test_usage_hours24_returns_data(self):
        d = _api_get("/api/orchestrator/usage?hours=24&tail=50")
        assert d is not None, "API returned None"

    def test_usage_hours24_has_recent(self):
        d = _api_get("/api/orchestrator/usage?hours=24&tail=50")
        assert "recent" in d

    def test_usage_hours24_recent_rows_have_provider(self):
        d = _api_get("/api/orchestrator/usage?hours=24&tail=50")
        recent = d.get("recent", [])
        if not recent:
            pytest.skip("No recent rows in 24h window")
        for row in recent:
            assert "provider" in row, f"Row missing provider: {row}"

    def test_usage_hours24_recent_rows_have_role(self):
        d = _api_get("/api/orchestrator/usage?hours=24&tail=50")
        recent = d.get("recent", [])
        if not recent:
            pytest.skip("No recent rows in 24h window")
        for row in recent:
            assert "role" in row, f"Row missing role: {row}"

    def test_usage_hours24_by_role_has_worker(self):
        d = _api_get("/api/orchestrator/usage?hours=24&tail=50")
        by_role = d.get("by_role", {})
        assert "worker" in by_role, f"by_role has no 'worker': {by_role}"

    def test_summary_usage_detail_has_roles(self):
        d = _api_get("/api/orchestrator/summary")
        assert d is not None
        ud = d.get("usage_detail")
        assert ud is not None, "summary missing usage_detail"
        assert "roles" in ud, "usage_detail missing roles"

    def test_summary_usage_detail_roles_has_worker(self):
        d = _api_get("/api/orchestrator/summary")
        ud = d.get("usage_detail", {})
        assert "worker" in ud.get("roles", {}), "usage_detail.roles missing 'worker'"


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3 — _rebuildAgentsFromRecent logic (Python simulation)
# ══════════════════════════════════════════════════════════════════════════════

class TestRebuildAgentsLogic:
    """Test _rebuildAgentsFromRecent using Python simulation of the JS logic."""

    def _make_payload(self, recent_rows: list[dict]) -> dict:
        payload: dict[str, Any] = {
            "roles": {"worker": {"calls": len(recent_rows), "blocked": 0, "agents": {}}},
            "recent": recent_rows,
        }
        return payload

    def test_rebuild_adds_provider_as_agent(self):
        payload = self._make_payload([
            {"role": "worker", "agent": "Copilot-Daemon", "blocked": False},
        ])
        _rebuild_agents_from_recent(payload)
        assert "Copilot-Daemon" in payload["roles"]["worker"]["agents"]

    def test_rebuild_increments_calls(self):
        payload = self._make_payload([
            {"role": "worker", "agent": "Claude", "blocked": False},
            {"role": "worker", "agent": "Claude", "blocked": False},
        ])
        _rebuild_agents_from_recent(payload)
        assert payload["roles"]["worker"]["agents"]["Claude"]["calls"] == 2

    def test_rebuild_skips_blocked_rows(self):
        payload = self._make_payload([
            {"role": "worker", "agent": "Copilot-Daemon", "blocked": True},
        ])
        _rebuild_agents_from_recent(payload)
        assert len(payload["roles"]["worker"]["agents"]) == 0

    def test_rebuild_skips_dash_agent(self):
        payload = self._make_payload([
            {"role": "worker", "agent": "—", "blocked": False},
        ])
        _rebuild_agents_from_recent(payload)
        assert len(payload["roles"]["worker"]["agents"]) == 0

    def test_rebuild_skips_none_agent(self):
        payload = self._make_payload([
            {"role": "worker", "agent": None, "blocked": False},
        ])
        _rebuild_agents_from_recent(payload)
        assert len(payload["roles"]["worker"]["agents"]) == 0

    def test_rebuild_multiple_providers(self):
        payload = self._make_payload([
            {"role": "worker", "agent": "Claude", "blocked": False},
            {"role": "worker", "agent": "Copilot-Daemon", "blocked": False},
            {"role": "worker", "agent": "Copilot-Daemon", "blocked": False},
            {"role": "worker", "agent": "Copilot-Daemon", "blocked": True},  # skip
        ])
        _rebuild_agents_from_recent(payload)
        agents = payload["roles"]["worker"]["agents"]
        assert agents["Claude"]["calls"] == 1
        assert agents["Copilot-Daemon"]["calls"] == 2

    def test_rebuild_with_actual_api_data(self):
        """Simulate full pipeline: normalise API payload → rebuild agents."""
        mock_api_response = {
            "by_role": {"worker": {"total": 3, "allowed": 2, "blocked": 1, "rate_limited": 0}},
            "recent": [
                {"role": "worker", "provider": "claude", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T13:05:31+00:00", "success": True, "task_id": 77,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0,
                 "rate_limit": False, "block_reason": None},
                {"role": "worker", "provider": "github-copilot", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T13:05:31+00:00", "success": True, "task_id": 78,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0,
                 "rate_limit": False, "block_reason": None},
                {"role": "worker", "provider": "github-copilot", "allowed": False, "blocked": True,
                 "timestamp": "2026-05-01T13:05:33+00:00", "success": False, "task_id": 79,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0,
                 "rate_limit": False, "block_reason": "hard-off"},
            ],
            "total": 3,
            "tokens": {},
            "malformed": 0,
        }
        payload = _normalise_usage_reader_payload(mock_api_response)
        _rebuild_agents_from_recent(payload)
        agents = payload["roles"]["worker"]["agents"]
        assert "Claude" in agents, "Claude not found after rebuild"
        assert "Copilot-Daemon" in agents, "Copilot-Daemon not found after rebuild"
        assert agents["Claude"]["calls"] == 1
        assert agents["Copilot-Daemon"]["calls"] == 1

    def test_rebuild_creates_missing_role(self):
        """Rebuild should create a role if it doesn't exist in by_role."""
        payload: dict[str, Any] = {
            "roles": {},
            "recent": [
                {"role": "cto", "agent": "Claude", "blocked": False},
            ],
        }
        _rebuild_agents_from_recent(payload)
        assert "cto" in payload["roles"]
        assert "Claude" in payload["roles"]["cto"]["agents"]


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4 — _normaliseUsageReaderPayload logic
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalisePayloadLogic:
    """Test _normaliseUsageReaderPayload Python simulation."""

    def test_normalise_converts_by_role_to_roles(self):
        d = {"by_role": {"worker": {"total": 5, "allowed": 4, "blocked": 1, "rate_limited": 0}}}
        p = _normalise_usage_reader_payload(d)
        assert "roles" in p
        assert "worker" in p["roles"]
        assert p["roles"]["worker"]["calls"] == 5
        assert p["roles"]["worker"]["blocked"] == 1

    def test_normalise_recent_maps_provider_to_agent(self):
        d = {
            "by_role": {},
            "recent": [
                {"role": "worker", "provider": "github-copilot", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T10:00:00+00:00", "success": True, "task_id": 1,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": None},
            ],
        }
        p = _normalise_usage_reader_payload(d)
        assert len(p["recent"]) == 1
        # provider 'github-copilot' must be display-mapped to 'Copilot-Daemon'
        assert p["recent"][0]["agent"] == "Copilot-Daemon"

    def test_normalise_recent_claude_maps_to_claude(self):
        d = {
            "by_role": {},
            "recent": [
                {"role": "worker", "provider": "claude", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T10:00:00+00:00", "success": True, "task_id": 2,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": None},
            ],
        }
        p = _normalise_usage_reader_payload(d)
        assert p["recent"][0]["agent"] == "Claude"

    def test_normalise_blocked_row_marked(self):
        d = {
            "by_role": {},
            "recent": [
                {"role": "worker", "provider": "github-copilot", "allowed": False,
                 "blocked": True, "timestamp": "2026-05-01T10:00:00+00:00",
                 "success": False, "task_id": 3, "premium_requests": 0,
                 "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0,
                 "rate_limit": False, "block_reason": "hard-off"},
            ],
        }
        p = _normalise_usage_reader_payload(d)
        assert p["recent"][0]["blocked"] is True
        assert p["recent"][0]["block_reason"] == "hard-off"

    def test_normalise_empty_payload_ok(self):
        p = _normalise_usage_reader_payload({})
        assert p["roles"] == {}
        assert p["recent"] == []
        assert p["total"]["calls"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 5 — Provider display name mapping
# ══════════════════════════════════════════════════════════════════════════════

class TestProviderDisplayMapping:
    """Verify _PROVIDER_DISPLAY_MAP covers expected provider names."""

    @pytest.mark.parametrize("raw,expected", [
        ("github-copilot", "Copilot-Daemon"),
        ("copilot", "Copilot-Daemon"),
        ("copilot-daemon", "Copilot-Daemon"),
        ("claude", "Claude"),
        ("claude-cli", "Claude CLI"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("codex", "Codex"),
        ("git-remote", "Git Remote"),
    ])
    def test_known_provider_maps(self, raw: str, expected: str):
        assert _provider_display(raw) == expected

    def test_unknown_provider_passthrough(self):
        assert _provider_display("my-custom-ai") == "my-custom-ai"

    def test_none_provider_returns_dash(self):
        assert _provider_display(None) == "—"

    def test_empty_string_returns_dash(self):
        assert _provider_display("") == "—"

    def test_case_insensitive(self):
        assert _provider_display("GITHUB-COPILOT") == "Copilot-Daemon"
        assert _provider_display("Claude") == "Claude"


# ══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 6 — Missing agents fallback rebuilds from recent
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingAgentsFallback:
    """Verify the full pipeline when usage_reader returns no agents."""

    def test_full_pipeline_github_copilot_becomes_copilot_daemon(self):
        """Simulate: by_role has no agents → recent has github-copilot → rebuild gives Copilot-Daemon."""
        raw = {
            "by_role": {"worker": {"total": 2, "allowed": 2, "blocked": 0, "rate_limited": 0}},
            "recent": [
                {"role": "worker", "provider": "github-copilot", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T10:00:00+00:00", "success": True, "task_id": 1,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": None},
                {"role": "worker", "provider": "github-copilot", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T10:01:00+00:00", "success": True, "task_id": 2,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": None},
            ],
            "total": 2,
            "tokens": {},
            "malformed": 0,
        }
        payload = _normalise_usage_reader_payload(raw)
        assert payload["roles"]["worker"]["agents"] == {}, "agents must be empty before rebuild"
        _rebuild_agents_from_recent(payload)
        agents = payload["roles"]["worker"]["agents"]
        assert "Copilot-Daemon" in agents
        assert agents["Copilot-Daemon"]["calls"] == 2

    def test_full_pipeline_no_無_provider_明細(self):
        """After pipeline, Worker card with real data must NOT show 無 provider 明細."""
        raw = {
            "by_role": {"worker": {"total": 1, "allowed": 1, "blocked": 0, "rate_limited": 0}},
            "recent": [
                {"role": "worker", "provider": "claude", "allowed": True, "blocked": False,
                 "timestamp": "2026-05-01T10:00:00+00:00", "success": True, "task_id": 1,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": None},
            ],
            "total": 1,
            "tokens": {},
            "malformed": 0,
        }
        payload = _normalise_usage_reader_payload(raw)
        _rebuild_agents_from_recent(payload)
        agents = payload["roles"]["worker"]["agents"]
        # If agents dict is non-empty, the card renders agent rows — NOT "無 provider 明細"
        assert len(agents) > 0, "Worker card should have at least 1 agent after rebuild"

    def test_all_blocked_shows_no_agents(self):
        """If all rows are blocked, rebuild should add no agents (correct — no allowed calls)."""
        raw = {
            "by_role": {"planner": {"total": 2, "allowed": 0, "blocked": 2, "rate_limited": 0}},
            "recent": [
                {"role": "planner", "provider": "github-copilot", "allowed": False, "blocked": True,
                 "timestamp": "2026-05-01T10:00:00+00:00", "success": False, "task_id": 1,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": "ROLE_PROVIDER_VIOLATION"},
                {"role": "planner", "provider": "claude", "allowed": False, "blocked": True,
                 "timestamp": "2026-05-01T10:01:00+00:00", "success": False, "task_id": 2,
                 "premium_requests": 0, "input_tokens": 0, "output_tokens": 0,
                 "cached_tokens": 0, "rate_limit": False, "block_reason": "hard-off"},
            ],
            "total": 2,
            "tokens": {},
            "malformed": 0,
        }
        payload = _normalise_usage_reader_payload(raw)
        _rebuild_agents_from_recent(payload)
        agents = payload["roles"].get("planner", {}).get("agents", {})
        assert len(agents) == 0, "Planner should have no agents when all calls are blocked"
