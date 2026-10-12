"""
P27A: Replay Page UI Console 404 Cleanup
Validates that all console.error sources are eliminated / demoted.
No DB writes. No migrations. No strategy execution.
"""
import re
import pytest


INDEX_HTML = 'index.html'
UIMANAGER_JS = 'src/ui/UIManager.js'
APP_JS = 'src/core/App.js'


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ── Fix 1: Method description card console.error removed ────────────────────
class TestMethodDescriptionCard:
    def test_no_console_error_missing_elements(self):
        """App.js must not fire console.error for missing method description card."""
        src = _read(APP_JS)
        assert 'Missing elements for method description card' not in src

    def test_silent_return_on_missing_elements(self):
        """App.js must silently return when card elements are absent."""
        src = _read(APP_JS)
        # The guard block must exist and return without error
        assert 'if (!card || !icon || !title || !description)' in src


# ── Fix 2: UIManager waterline uses absolute URL ─────────────────────────────
class TestWaterlineApiUrl:
    def test_no_bare_relative_regime_url(self):
        """UIManager must not use bare relative /api/performance/regime."""
        src = _read(UIMANAGER_JS)
        assert "fetch('/api/performance/regime')" not in src

    def test_uses_apiclient_base(self):
        """UIManager must use apiClient.baseUrl for regime fetch."""
        src = _read(UIMANAGER_JS)
        assert 'apiClient.baseUrl' in src
        assert '/api/performance/regime' in src

    def test_imports_apiclient(self):
        """UIManager must import apiClient."""
        src = _read(UIMANAGER_JS)
        assert "import { apiClient } from '../services/ApiClient.js'" in src

    def test_waterline_error_demoted_to_warn(self):
        """UIManager waterline catch must use console.warn, not console.error."""
        src = _read(UIMANAGER_JS)
        assert "console.error('Failed to update waterline:')" not in src
        assert 'console.warn' in src


# ── Fix 3 & 4: index.html window.API_BASE injected & lifecycle demoted ───────
class TestIndexHtmlFixes:
    def test_window_api_base_script_present(self):
        """index.html must inject window.API_BASE before any fetch calls."""
        src = _read(INDEX_HTML)
        assert 'window.API_BASE' in src

    def test_api_base_uses_port_8002(self):
        """window.API_BASE injection must point to port 8002."""
        src = _read(INDEX_HTML)
        assert ':8002' in src

    def test_api_base_script_before_replay_iife(self):
        """window.API_BASE assignment must appear before the replay IIFE."""
        src = _read(INDEX_HTML)
        pos_inject = src.index('window.API_BASE =')
        pos_iife = src.index('// ===== REPLAY PAGE JS =====')
        assert pos_inject < pos_iife, 'window.API_BASE must be injected before replay IIFE'

    def test_lifecycle_error_demoted(self):
        """[P7] lifecycle registry error must be console.warn, not console.error."""
        src = _read(INDEX_HTML)
        assert "console.error('[P7] lifecycle registry load error:'" not in src
        assert "console.warn('[P7] lifecycle registry load error:'" in src

    def test_freshness_still_warn(self):
        """[replay] freshness load failed must remain console.warn."""
        src = _read(INDEX_HTML)
        assert "console.warn('[replay] freshness load failed'" in src

    def test_no_console_error_in_replay_iife(self):
        """Replay IIFE must contain zero console.error calls."""
        src = _read(INDEX_HTML)
        # Extract text from replay IIFE onwards
        start = src.index('// ===== REPLAY PAGE JS =====')
        replay_section = src[start:]
        assert 'console.error' not in replay_section

    def test_production_rows_unchanged(self):
        """DB row count must remain 12460 (no writes)."""
        import sqlite3
        conn = sqlite3.connect('lottery_api/data/lottery_v2.db')
        try:
            (count,) = conn.execute('SELECT COUNT(*) FROM strategy_prediction_replays').fetchone()
        finally:
            conn.close()
        assert count == 12460, f'Expected 12460 rows, got {count}'
