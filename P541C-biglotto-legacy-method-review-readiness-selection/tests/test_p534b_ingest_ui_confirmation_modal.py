"""P534B/P255E static contract for the ingest backfill G03 UI confirmation modal.

The tests are DB-free and do not call ingest endpoints. They verify that the
non-dry-run backfill UI now collects explicit confirmation data instead of
submitting hardcoded write-guard fields from the browser.
"""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
AUTO_FETCH_JS = REPO_ROOT / "src" / "ui" / "AutoFetchManager.js"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _js() -> str:
    return AUTO_FETCH_JS.read_text(encoding="utf-8")


def test_p255e_g03_modal_markup_present() -> None:
    html = _html()
    assert 'id="af-bf-confirm-modal"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert "P255E/G03" in html
    for field_id in (
        "af-bf-confirm-token",
        "af-bf-confirm-requested-by",
        "af-bf-confirm-reason",
        "af-bf-confirm-apply",
        "af-bf-confirm-cancel",
    ):
        assert field_id in html


def test_non_dry_run_opens_modal_before_fetch() -> None:
    js = _js()
    assert "_openBackfillConfirmModal(payload)" in js
    assert "await this._submitBackfill(payload, true)" in js
    assert "await this._submitBackfill(payload, false)" in js
    assert "apply_confirmed: true" in js
    assert "confirm_token: token" in js
    assert "requested_by: requestedBy" in js
    assert "reason," in js


def test_ui_does_not_hardcode_write_guard_confirmation() -> None:
    js = _js()
    assert "p255-write-confirm" not in js
    assert "ui-user" not in js
    assert "Manual backfill from UI" not in js


def test_modal_validation_requires_all_confirmation_fields() -> None:
    js = _js()
    assert "if (!token || !requestedBy || requestedBy === 'unknown' || !reason)" in js
    assert "confirm_token、requested_by 與 reason" in js


def test_dry_run_payload_remains_safe_default() -> None:
    js = _js()
    assert "dry_run:      dryRun" in js
    assert "max_draws:    30" in js
    assert "if (!dryRun && !confirmed)" in js
