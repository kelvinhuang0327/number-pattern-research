"""P551A focused static tests for notification render safety."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
UI_MANAGER_JS = REPO_ROOT / "src" / "ui" / "UIManager.js"


def _show_notification_helper() -> str:
    script = UI_MANAGER_JS.read_text(encoding="utf-8")
    return script.split("showNotification(message, type = 'info') {", 1)[1].split(
        "\n    }\n\n    updateLotteryTypeSelector", 1
    )[0]


def test_notification_message_uses_text_content_not_html() -> None:
    helper = _show_notification_helper()

    assert "notification.textContent = String(message ?? '');" in helper
    assert "notification.innerHTML" not in helper
    assert "replace(/\\n/g, '<br>')" not in helper


def test_notification_preserves_multiline_display_without_html_breaks() -> None:
    helper = _show_notification_helper()

    assert "whiteSpace: 'pre-line'" in helper
    assert "document.body.appendChild(notification)" in helper
