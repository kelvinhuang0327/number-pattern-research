from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from orchestrator import db
from orchestrator.common import DEFAULT_PROFILE_PATH, load_project_profile
from orchestrator.worker_tick import run_worker_tick


def run_worker_daemon(
    profile_path: str | Path | None = None,
    *,
    execute_provider: bool = True,
) -> dict[str, Any]:
    effective_profile = profile_path or DEFAULT_PROFILE_PATH
    profile = load_project_profile(effective_profile)
    db.init_db(profile)
    interval_seconds = int(profile["default_schedule_minutes"]) * 60

    while True:
        state = db.get_scheduler_state(profile)
        if state["enabled"]:
            run_worker_tick(effective_profile, execute_provider=execute_provider)
            interval_seconds = int(state["interval_minutes"]) * 60
        time.sleep(max(interval_seconds, 10))

