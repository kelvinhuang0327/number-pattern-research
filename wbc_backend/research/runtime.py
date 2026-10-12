from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .execution import V3ResearchExecutor


DEFAULT_RESEARCH_ARTIFACT = Path("data/wbc_backend/artifacts/v3_research_cycle.json")


def run_research_cycle(
    seed: int = 42,
    artifact_path: Path | None = None,
) -> dict:
    executor = V3ResearchExecutor(seed=seed)
    results = executor.execute_all()
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "phase_results": [asdict(r) for r in results],
        "all_passed": all(r.passed for r in results),
        "phase_count": len(results),
    }

    target = artifact_path or DEFAULT_RESEARCH_ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2))
    return payload
