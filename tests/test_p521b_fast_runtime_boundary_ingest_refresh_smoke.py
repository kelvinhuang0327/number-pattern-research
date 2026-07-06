"""P521B runtime-boundary smoke for ingest after-insert scheduler refresh.

This imports lottery_api.routes.ingest only after capturing DB file state,
checks that import did not create or modify guarded DB files, then replaces
the scheduler import target with a fake scheduler before calling the refresh
helper. It does not execute draw insertion or real after-insert hooks.
"""
from __future__ import annotations

import hashlib
import importlib
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_PATH = REPO_ROOT / "lottery_api" / "routes" / "ingest.py"
DB_PATHS = (
    REPO_ROOT / "data" / "lottery_v2.db",
    REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db",
)
REMOVED_HOOK_RESIDUE = {
    "_MISSING_AFTERINSERT_HOOKS_ENABLED",
    "refresh_hedge_fund_outputs",
    "weight_adjuster",
    "learning_integrator",
    "_schedule_after_insert",
    "snapshot_scheduler",
    "prediction_tracker",
}
DB_SIDE_EFFECT_MESSAGE = "P521B_FAST_BLOCKED_RUNTIME_IMPORT_OR_DB_SIDE_EFFECT"


class FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def load_data(self) -> None:
        self.calls.append("load_data")


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


def test_refresh_after_insert_runtime_import_reaches_fake_scheduler_once(monkeypatch):
    before_import = _db_state()

    sys.modules.pop("lottery_api.routes.ingest", None)
    ingest = importlib.import_module("lottery_api.routes.ingest")

    after_import = _db_state()
    assert after_import == before_import, DB_SIDE_EFFECT_MESSAGE

    source = INGEST_PATH.read_text(encoding="utf-8")
    for residue in sorted(REMOVED_HOOK_RESIDUE):
        assert residue not in source, residue

    fake_scheduler = FakeScheduler()
    ingest.scheduler = fake_scheduler
    monkeypatch.setitem(
        sys.modules,
        "utils.scheduler",
        types.SimpleNamespace(scheduler=fake_scheduler),
    )

    ingest._refresh_after_insert()

    assert fake_scheduler.calls == ["load_data"]
