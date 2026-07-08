"""P535A static contract for fetch-latest G03 insert confirmation.

The tests are DB-free and do not call ingest endpoints. They verify that the
write-capable fetch-latest UI path (`insert_if_new=true`, `dry_run=false`) now
opens a one-time confirmation modal before submitting the request.
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


def test_fetch_latest_confirmation_modal_markup_present() -> None:
    html = _html()
    assert 'id="af-fetch-confirm-modal"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert "P535A/G03" in html
    for field_id in (
        "af-fetch-confirm-summary",
        "af-fetch-confirm-ack",
        "af-fetch-confirm-apply",
        "af-fetch-confirm-cancel",
    ):
        assert field_id in html


def test_write_capable_fetch_path_opens_modal_before_submit() -> None:
    js = _js()
    assert "if (insertNew && !dryRun)" in js
    assert "this._openFetchLatestConfirmModal(payload)" in js
    assert "await this._submitFetchLatest(payload)" in js
    assert "insert_if_new: insertNew" in js
    assert "dry_run:       dryRun" in js


def test_confirmation_requires_insert_ack_text() -> None:
    js = _js()
    assert "ack !== 'INSERT'" in js
    assert "請在確認視窗輸入 INSERT" in js
    assert "const payload = { ...this._pendingFetchLatestPayload }" in js


def test_fetch_latest_payload_has_no_backfill_write_guard_fields() -> None:
    js = _js()
    fetch_section = js.split("// ─── Fetch Latest", 1)[1].split("// ─── Scan Missing", 1)[0]
    for forbidden in (
        "apply_confirmed",
        "confirm_token",
        "requested_by",
        "reason",
        "p255-write-confirm",
    ):
        assert forbidden not in fetch_section


def test_p534b_backfill_modal_contract_still_present() -> None:
    html = _html()
    js = _js()
    assert 'id="af-bf-confirm-modal"' in html
    assert "_openBackfillConfirmModal(payload)" in js
    assert "confirm_token: token" in js
