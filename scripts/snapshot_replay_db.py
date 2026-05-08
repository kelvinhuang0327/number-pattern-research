#!/usr/bin/env python3
"""
snapshot_replay_db.py
=====================
P0-5-C  G3 — One-shot pre-go-live DB snapshot

Copies lottery_api/data/lottery_v2.db to:
    outputs/db_snapshots/lottery_v2_pre_replay_golive_YYYYMMDDHHMM.db

Computes SHA256 of the copy and appends to:
    outputs/db_snapshots/SHA256SUMS

Safety rules:
  - Read-only access to source DB (opens via shutil.copy2, never via sqlite3 write)
  - Does NOT modify the source DB
  - Does NOT schedule itself (one-shot only)
  - Never overwrites an existing snapshot file
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SOURCE_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
SNAPSHOTS_DIR = REPO_ROOT / "outputs" / "db_snapshots"
SHA256SUMS_FILE = SNAPSHOTS_DIR / "SHA256SUMS"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not SOURCE_DB.exists():
        print(f"ERROR: Source DB not found: {SOURCE_DB}", file=sys.stderr)
        return 1

    # Create snapshot directory if needed
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build timestamped filename
    ts = datetime.now().strftime("%Y%m%d%H%M")
    dest = SNAPSHOTS_DIR / f"lottery_v2_pre_replay_golive_{ts}.db"

    if dest.exists():
        print(f"ERROR: Snapshot already exists (refusing overwrite): {dest}", file=sys.stderr)
        return 1

    # Copy (preserves metadata, never opens DB for write)
    shutil.copy2(SOURCE_DB, dest)
    print(f"Snapshot written: {dest}")

    # Compute and record SHA256
    digest = _sha256(dest)
    checksum_line = f"{digest}  {dest.name}\n"

    with SHA256SUMS_FILE.open("a") as f:
        f.write(checksum_line)

    print(f"SHA256: {digest}")
    print(f"Recorded in: {SHA256SUMS_FILE}")

    # Verify source was not modified (sizes must match)
    src_size = SOURCE_DB.stat().st_size
    dst_size = dest.stat().st_size
    if src_size != dst_size:
        print(
            f"ERROR: Size mismatch after copy ({src_size} vs {dst_size}). "
            "Snapshot may be corrupt.",
            file=sys.stderr,
        )
        return 1

    print(f"Size verified: {dst_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
