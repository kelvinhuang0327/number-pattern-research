"""P541A static tests for AutoFetch confirmation dialog descriptions."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _modal_markup(html: str, modal_id: str) -> str:
    return html.split(f'id="{modal_id}"', 1)[1].split("</div>\n\n                    <!--", 1)[0]


def test_fetch_latest_confirmation_dialog_describes_warning_text() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    modal = _modal_markup(html, "af-fetch-confirm-modal")

    assert 'aria-describedby="af-fetch-confirm-warning"' in modal
    assert 'id="af-fetch-confirm-warning"' in modal
    assert "不會繞過後端資料寫入 Gate" in modal


def test_backfill_confirmation_dialog_describes_warning_text() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    modal = _modal_markup(html, "af-bf-confirm-modal")

    assert 'aria-describedby="af-bf-confirm-warning"' in modal
    assert 'id="af-bf-confirm-warning"' in modal
    assert "UI 不儲存 token" in modal
