"""P542A static tests for AutoFetch confirmation modal focus return."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
AUTO_FETCH_JS = REPO_ROOT / "src" / "ui" / "AutoFetchManager.js"


def _js() -> str:
    return AUTO_FETCH_JS.read_text(encoding="utf-8")


def _method(js: str, name: str) -> str:
    return js.split(f"\n    {name}(", 1)[1].split("\n    }\n", 1)[0]


def test_fetch_latest_confirm_modal_restores_invoking_focus() -> None:
    js = _js()
    open_method = _method(js, "_openFetchLatestConfirmModal")
    close_method = _method(js, "_closeFetchLatestConfirmModal")

    assert "this._fetchConfirmReturnFocus = document.activeElement" in open_method
    assert "this.fetchConfirmAck?.focus()" in open_method
    assert "this._restoreModalFocus('_fetchConfirmReturnFocus')" in close_method


def test_backfill_confirm_modal_restores_invoking_focus() -> None:
    js = _js()
    open_method = _method(js, "_openBackfillConfirmModal")
    close_method = _method(js, "_closeBackfillConfirmModal")

    assert "this._backfillConfirmReturnFocus = document.activeElement" in open_method
    assert "this.bfConfirmToken?.focus()" in open_method
    assert "this._restoreModalFocus('_backfillConfirmReturnFocus')" in close_method


def test_modal_focus_restore_helper_clears_and_validates_target() -> None:
    helper = _method(_js(), "_restoreModalFocus")

    assert "const target = this[slot]" in helper
    assert "this[slot] = null" in helper
    assert "typeof target.focus === 'function'" in helper
    assert "document.contains(target)" in helper
    assert "target.focus()" in helper


def test_focus_return_change_does_not_add_endpoint_or_db_behavior() -> None:
    helper = _method(_js(), "_restoreModalFocus")

    for forbidden in (
        "fetch(",
        "getApiUrl",
        "sqlite",
        "lottery_v2.db",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ):
        assert forbidden not in helper
