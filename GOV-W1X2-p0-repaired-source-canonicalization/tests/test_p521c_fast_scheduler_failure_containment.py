"""P521C failure-containment smoke for ingest after-insert scheduler refresh.

This imports lottery_api.routes.ingest only after capturing DB file state,
replaces the scheduler import target with a fake scheduler that raises, and
checks the refresh helper contains that failure without touching guarded DB
files. It does not execute draw insertion or the real scheduler.
"""
from __future__ import annotations

import hashlib
import importlib
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATHS = (
    REPO_ROOT / "data" / "lottery_v2.db",
    REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db",
)
DB_SIDE_EFFECT_MESSAGE = "P521C_FAST_BLOCKED_DB_HASH_CHANGED_OR_DB_CREATED"


class RaisingScheduler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def load_data(self) -> None:
        self.calls.append("load_data")
        raise RuntimeError("fake scheduler failure")


class FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as db_file:
        for chunk in iter(lambda: db_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db_state() -> dict[str, tuple[bool, int | None, str | None]]:
    state: dict[str, tuple[bool, int | None, str | None]] = {}
    for path in DB_PATHS:
        if path.exists():
            stat = path.stat()
            state[str(path.relative_to(REPO_ROOT))] = (True, stat.st_size, _sha256(path))
        else:
            state[str(path.relative_to(REPO_ROOT))] = (False, None, None)
    return state


def test_refresh_after_insert_contains_fake_scheduler_failure(monkeypatch):
    before_import = _db_state()

    sys.modules.pop("lottery_api.routes.ingest", None)
    ingest = importlib.import_module("lottery_api.routes.ingest")

    after_import = _db_state()
    assert after_import == before_import, DB_SIDE_EFFECT_MESSAGE

    fake_scheduler = RaisingScheduler()
    fake_logger = FakeLogger()
    monkeypatch.setattr(ingest, "logger", fake_logger)
    monkeypatch.setitem(
        sys.modules,
        "utils.scheduler",
        types.SimpleNamespace(scheduler=fake_scheduler),
    )

    ingest._refresh_after_insert()

    after_refresh = _db_state()
    assert after_refresh == before_import, DB_SIDE_EFFECT_MESSAGE
    assert fake_scheduler.calls == ["load_data"]
    assert fake_logger.warnings == [
        "scheduler.load_data() failed: fake scheduler failure"
    ]
