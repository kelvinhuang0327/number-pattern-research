"""
Integration tests for the restored ingest pipeline.

Confirms:
  - /api/ingest/scan-missing   returns valid missing-draw data
  - /api/ingest/fetch-latest   fetches real data (dry_run=True)
  - /api/ingest/backfill       dry-run returns correct structure
  - DB is NOT modified (dry_run guard)

Requires: backend running on http://127.0.0.1:8002
"""
import pytest
import requests
import hashlib
import sqlite3
import os

BASE = "http://127.0.0.1:8002"
DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lottery_api", "data", "lottery_v2.db"
)


def _db_sha() -> str:
    """SHA-256 of DB file (for write-guard assertion)."""
    h = hashlib.sha256()
    try:
        with open(DB_PATH, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
    except FileNotFoundError:
        return "no-db"
    return h.hexdigest()


def _is_backend_up() -> bool:
    try:
        r = requests.get(f"{BASE}/api/ping", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# Skip all tests if backend not running
pytestmark = pytest.mark.skipif(
    not _is_backend_up(),
    reason="Backend not running on port 8002"
)


# ---------------------------------------------------------------------------
# scan-missing
# ---------------------------------------------------------------------------

class TestScanMissing:
    def test_returns_all_three_types(self):
        r = requests.get(f"{BASE}/api/ingest/scan-missing", timeout=30)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
        j = r.json()
        assert "results" in j
        assert "total_missing" in j
        for lt in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
            assert lt in j["results"], f"{lt} missing from results"

    def test_result_schema(self):
        r = requests.get(f"{BASE}/api/ingest/scan-missing", timeout=30)
        j = r.json()
        for lt, v in j["results"].items():
            assert "missing_count" in v, f"{lt}: no missing_count"
            assert "scan_error" in v, f"{lt}: no scan_error"
            assert v["scan_error"] is None, f"{lt}: scan_error={v['scan_error']}"

    def test_total_missing_is_consistent(self):
        r = requests.get(f"{BASE}/api/ingest/scan-missing", timeout=30)
        j = r.json()
        sum_missing = sum(v["missing_count"] for v in j["results"].values())
        assert j["total_missing"] == sum_missing

    def test_per_type_filter(self):
        r = requests.get(
            f"{BASE}/api/ingest/scan-missing?lottery_type=BIG_LOTTO", timeout=30
        )
        assert r.status_code == 200
        j = r.json()
        assert "BIG_LOTTO" in j["results"]
        # Only one type
        assert len(j["results"]) == 1


# ---------------------------------------------------------------------------
# fetch-latest (dry_run=True — no DB writes)
# ---------------------------------------------------------------------------

class TestFetchLatest:
    LOTTERY_TYPES = ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]

    def test_dry_run_returns_success(self):
        sha_before = _db_sha()
        for lt in self.LOTTERY_TYPES:
            r = requests.post(
                f"{BASE}/api/ingest/fetch-latest",
                json={"lottery_type": lt, "dry_run": True, "insert_if_new": False},
                timeout=30,
            )
            assert r.status_code == 200, f"{lt}: HTTP {r.status_code} — {r.text[:200]}"
            j = r.json()
            assert j.get("success") is True, f"{lt}: success=False — {j}"
            assert "draw" in j, f"{lt}: no draw field"
            assert "draw_data" in j, f"{lt}: no draw_data"
        # DB must not change
        assert _db_sha() == sha_before, "DB was modified during dry_run!"

    def test_draw_data_schema(self):
        r = requests.post(
            f"{BASE}/api/ingest/fetch-latest",
            json={"lottery_type": "BIG_LOTTO", "dry_run": True},
            timeout=30,
        )
        j = r.json()
        d = j.get("draw_data", {})
        assert "draw" in d, "draw_data missing 'draw'"
        assert "date" in d, "draw_data missing 'date'"
        assert "numbers" in d, "draw_data missing 'numbers'"
        assert isinstance(d["numbers"], list), "numbers is not a list"
        assert len(d["numbers"]) >= 5, "too few numbers"


# ---------------------------------------------------------------------------
# backfill (dry_run=True — no DB writes)
# ---------------------------------------------------------------------------

class TestBackfillDryRun:
    def test_dry_run_big_lotto(self):
        sha_before = _db_sha()
        r = requests.post(
            f"{BASE}/api/ingest/backfill",
            json={"lottery_type": "BIG_LOTTO", "dry_run": True, "max_draws": 5},
            timeout=60,
        )
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
        j = r.json()
        assert j.get("success") is True, f"success=False: {j}"
        assert "summary" in j
        s = j["summary"]
        assert s["dry_run"] is True
        # Confirm no write
        assert _db_sha() == sha_before, "DB was modified during dry_run!"

    def test_dry_run_power_lotto(self):
        sha_before = _db_sha()
        r = requests.post(
            f"{BASE}/api/ingest/backfill",
            json={"lottery_type": "POWER_LOTTO", "dry_run": True, "max_draws": 5},
            timeout=60,
        )
        j = r.json()
        assert j.get("success") is True
        assert j["summary"]["dry_run"] is True
        assert _db_sha() == sha_before

    def test_dry_run_daily_539(self):
        sha_before = _db_sha()
        r = requests.post(
            f"{BASE}/api/ingest/backfill",
            json={"lottery_type": "DAILY_539", "dry_run": True, "max_draws": 5},
            timeout=60,
        )
        j = r.json()
        assert j.get("success") is True
        assert j["summary"]["dry_run"] is True
        assert _db_sha() == sha_before

    def test_summary_schema(self):
        r = requests.post(
            f"{BASE}/api/ingest/backfill",
            json={"lottery_type": "BIG_LOTTO", "dry_run": True, "max_draws": 5},
            timeout=60,
        )
        j = r.json()
        s = j["summary"]
        for field in ("lottery_type", "dry_run", "total", "inserted", "skipped",
                      "conflict", "failed", "details"):
            assert field in s, f"summary missing '{field}'"
