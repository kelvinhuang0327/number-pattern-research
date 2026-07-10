#!/usr/bin/env python3
"""P544B — read-only replay artifact inventory.

Inventories the research artifacts committed at a pinned git commit under
``outputs/research/``, classifies each artifact's replay-relatedness,
extracts every declared source link (``path`` + 64-hex ``sha256`` inside the
same JSON object), and verifies the declared integrity chain against the
committed blob bytes of the link targets.

Read-only guarantees:
- All artifact bytes are read from git blobs of the pinned commit via
  ``git ls-tree`` / ``git cat-file --batch`` (never from the mutable working
  tree), so the inventory is a pure function of the commit.
- No database is opened, no network is used, no service is controlled.
- The only writes are the two whitelisted output files
  ``outputs/research/p544b_readonly_replay_artifact_inventory_<date>.{json,md}``.

Determinism: ``generated_at_utc`` is the pinned commit's committer timestamp,
normalized to UTC seconds.  The canonical payload digest remains the SHA-256
of the sorted-key compact JSON payload excluding ``generated_at_utc`` and
``canonical_payload_digest`` itself for schema compatibility. ``main()``
builds the payload twice and refuses to write unless both complete JSON and
Markdown serializations are byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "p544b_readonly_replay_artifact_inventory.v1"
SCOPE_PREFIX = "outputs/research/"
REPLAY_TABLES = ("strategy_prediction_replays", "strategy_replay_runs")
VOLATILE_KEYS = ("generated_at_utc", "canonical_payload_digest")

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_KEY_RE = re.compile(
    r"^(?:raw_|file_|artifact_|canonical_|payload_)?(?:sha256|sha_256|digest|hash)$",
    re.IGNORECASE,
)
_PATHLIKE_RE = re.compile(r"^[A-Za-z0-9_.\-/]{1,300}$")
_PATH_EXTS = (".json", ".md", ".py", ".db", ".txt", ".csv", ".yaml", ".yml", ".jsonl", ".html")
_TASK_ID_RE = re.compile(r"^(p\d+[a-z0-9]*)_", re.IGNORECASE)
_DATE_RE = re.compile(r"_(\d{8})(?:\.|_)")
_LOTTERY_HINTS = ("daily539", "539", "biglotto", "big_lotto", "big649", "power", "powerlotto")


# ---------------------------------------------------------------------------
# pure helpers (unit-tested without git)
# ---------------------------------------------------------------------------

def parse_task_id(basename: str) -> str | None:
    """Extract the leading task id (e.g. ``p543d``) from an artifact basename."""
    m = _TASK_ID_RE.match(basename)
    return m.group(1).lower() if m else None


def parse_artifact_date(basename: str) -> str | None:
    """Extract the 8-digit date token (e.g. ``20260710``) from a basename."""
    m = _DATE_RE.search(basename)
    return m.group(1) if m else None


def _is_pathlike(value: object) -> bool:
    return (
        isinstance(value, str)
        and "/" in value
        and bool(_PATHLIKE_RE.match(value))
        and value.lower().endswith(_PATH_EXTS)
    )


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64_RE.match(value))


def extract_declared_links(node: object, owner_path: str) -> list[dict]:
    """Collect declared (path, sha256) pairs from every JSON object in ``node``.

    Pairing rule per object: a 64-hex value counts only when its key is a bare
    digest key (``sha256``/``digest``/``hash``, optionally prefixed with
    ``raw_``/``file_``/``artifact_``/``canonical_``/``payload_``); qualified
    keys such as ``production_db_sha256_before`` never pair with a path.
    A link is unambiguous only when the object holds exactly one path-like
    value and exactly one distinct qualifying digest; any other combination
    is recorded as ambiguous and never verified.
    """
    links: list[dict] = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, list):
            stack.extend(cur)
            continue
        if not isinstance(cur, dict):
            continue
        stack.extend(cur.values())
        paths = sorted({v for v in cur.values() if _is_pathlike(v)})
        hexes = sorted(
            {
                v
                for k, v in cur.items()
                if isinstance(k, str) and _DIGEST_KEY_RE.match(k) and _is_hex64(v)
            }
        )
        if not paths or not hexes:
            continue
        ambiguous = not (len(paths) == 1 and len(hexes) == 1)
        for path, digest in ((p, h) for p in paths for h in hexes):
            links.append(
                {
                    "owner_path": owner_path,
                    "declared_path": path,
                    "declared_sha256": digest,
                    "ambiguous_pairing": ambiguous,
                }
            )
    dedup = {
        (l["owner_path"], l["declared_path"], l["declared_sha256"], l["ambiguous_pairing"]): l
        for l in links
    }
    return [dedup[k] for k in sorted(dedup)]


def classify_direct(basename: str, text_lower: str) -> str:
    """Tiered direct replay classification for one artifact."""
    if "replay" in basename.lower():
        return "replay_named"
    if any(t in text_lower for t in REPLAY_TABLES):
        return "replay_table_consumer"
    if "replay" in text_lower:
        return "replay_term_content"
    return "non_replay"


def apply_link_closure(classifications: dict[str, str], links: list[dict]) -> dict[str, str]:
    """Mark ``non_replay`` artifacts that declare a replay-related source as
    ``replay_linked`` (transitive fixpoint over declared links)."""
    result = dict(classifications)
    changed = True
    while changed:
        changed = False
        for link in links:
            owner = link["owner_path"]
            target = link["declared_path"]
            if (
                result.get(owner) == "non_replay"
                and result.get(target, "non_replay") != "non_replay"
            ):
                result[owner] = "replay_linked"
                changed = True
    return result


def pair_stem(path: str) -> str | None:
    """Return the pairing stem for ``.json``/``.md`` artifacts, else None."""
    for ext in (".json", ".md"):
        if path.endswith(ext):
            return path[: -len(ext)]
    return None


def lottery_hints(basename: str) -> list[str]:
    low = basename.lower()
    return sorted({h for h in _LOTTERY_HINTS if h in low})


def canonical_payload_digest(payload: dict) -> str:
    """SHA-256 over sorted-key compact JSON, excluding volatile fields."""
    stripped = {k: v for k, v in payload.items() if k not in VOLATILE_KEYS}
    encoded = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def serialize_json(payload: dict) -> str:
    """Return the canonical on-disk JSON representation."""
    return json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# git access (read-only)
# ---------------------------------------------------------------------------

def _git_text(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    ).stdout


def commit_timestamp_utc(repo_root: Path, commit: str) -> str:
    """Return a commit's committer timestamp normalized to UTC seconds."""
    raw = _git_text(repo_root, "show", "-s", "--format=%cI", commit).strip()
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"commit timestamp has no timezone: {raw!r}")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


class BlobReader:
    """Batch reader for git blob bytes at a pinned commit (read-only)."""

    def __init__(self, repo_root: Path, commit: str):
        self.repo_root = repo_root
        self.commit = commit
        self._oids: dict[str, str] = {}
        raw = _git_text(repo_root, "ls-tree", "-r", "-z", "--full-tree", commit)
        for entry in raw.split("\0"):
            if not entry:
                continue
            meta, path = entry.split("\t", 1)
            mode, otype, oid = meta.split(" ")
            if otype == "blob":
                self._oids[path] = oid
        self._proc = subprocess.Popen(
            ["git", "-C", str(repo_root), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        self._cache: dict[str, bytes] = {}

    def tracked_paths(self, prefix: str = "") -> list[str]:
        return sorted(p for p in self._oids if p.startswith(prefix))

    def is_tracked(self, path: str) -> bool:
        return path in self._oids

    def read(self, path: str) -> bytes:
        oid = self._oids[path]
        if oid in self._cache:
            return self._cache[oid]
        assert self._proc.stdin and self._proc.stdout
        self._proc.stdin.write(f"{oid}\n".encode())
        self._proc.stdin.flush()
        header = self._proc.stdout.readline().decode()
        parts = header.strip().split(" ")
        if len(parts) != 3 or parts[1] != "blob":
            raise RuntimeError(f"unexpected cat-file header for {path}: {header!r}")
        size = int(parts[2])
        data = self._proc.stdout.read(size)
        self._proc.stdout.read(1)  # trailing LF
        self._cache[oid] = data
        return data

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.wait(timeout=30)


# ---------------------------------------------------------------------------
# inventory build
# ---------------------------------------------------------------------------

def verify_link(link: dict, reader: BlobReader) -> str:
    if link["owner_path"] == link["declared_path"]:
        return "self_reference"
    if link["ambiguous_pairing"]:
        return "ambiguous_pairing_unverified"
    target = link["declared_path"]
    if target.startswith("/"):
        return "path_not_relative"
    if not reader.is_tracked(target):
        return "path_not_tracked_at_commit"
    data = reader.read(target)
    if hashlib.sha256(data).hexdigest() == link["declared_sha256"]:
        return "verified_raw_bytes"
    if link["declared_sha256"].encode("ascii") in data:
        return "verified_embedded_self_declared"
    return "digest_mismatch"


def explain_mismatch(link: dict, repo_root: Path, commit: str) -> dict | None:
    """For a digest_mismatch link, search the head-ancestry history of the
    declared path for a version whose raw bytes match the declared digest."""
    log = _git_text(
        repo_root, "log", commit, "--format=%H%x09%s", "--", link["declared_path"]
    )
    for line in log.splitlines():
        commit_hash, _, subject = line.partition("\t")
        try:
            blob = subprocess.run(
                ["git", "-C", str(repo_root), "show", f"{commit_hash}:{link['declared_path']}"],
                check=True,
                capture_output=True,
            ).stdout
        except subprocess.CalledProcessError:
            continue
        if hashlib.sha256(blob).hexdigest() == link["declared_sha256"]:
            return {"commit": commit_hash, "subject": subject}
    return None


def build_inventory(repo_root: Path, commit: str = "HEAD") -> dict:
    head_commit = _git_text(repo_root, "rev-parse", commit).strip()
    reader = BlobReader(repo_root, head_commit)
    try:
        corpus_paths = reader.tracked_paths(SCOPE_PREFIX)
        texts: dict[str, str] = {}
        rows: dict[str, dict] = {}
        all_links: list[dict] = []
        json_parse_errors: list[str] = []

        for path in corpus_paths:
            data = reader.read(path)
            text_lower = data.decode("utf-8", errors="replace").lower()
            texts[path] = text_lower
            basename = path.rsplit("/", 1)[-1]
            rows[path] = {
                "path": path,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "task_id": parse_task_id(basename),
                "artifact_date": parse_artifact_date(basename),
                "extension": Path(basename).suffix.lstrip("."),
                "lottery_hints": lottery_hints(basename),
                "classification": classify_direct(basename, text_lower),
            }
            if path.endswith(".json"):
                try:
                    parsed = json.loads(data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    json_parse_errors.append(path)
                else:
                    all_links.extend(extract_declared_links(parsed, path))

        classifications = {p: rows[p]["classification"] for p in rows}
        classifications = apply_link_closure(classifications, all_links)
        for path, cls in classifications.items():
            rows[path]["classification"] = cls

        replay_paths = sorted(p for p, c in classifications.items() if c != "non_replay")
        replay_links = [l for l in all_links if l["owner_path"] in set(replay_paths)]
        for link in replay_links:
            link["verification"] = verify_link(link, reader)
            if link["verification"] == "digest_mismatch":
                link["declared_digest_matches_historical"] = explain_mismatch(
                    link, repo_root, head_commit
                )
        replay_links.sort(
            key=lambda l: (l["owner_path"], l["declared_path"], l["declared_sha256"])
        )

        upstream_inputs = sorted(
            {
                l["declared_path"]
                for l in replay_links
                if l["verification"] != "self_reference"
                and classifications.get(l["declared_path"], "non_replay") == "non_replay"
            }
        )

        stems: dict[str, set] = {}
        for path in corpus_paths:
            stem = pair_stem(path)
            if stem is not None:
                stems.setdefault(stem, set()).add(path.rsplit(".", 1)[-1])
        unpaired = sorted(
            stem + "." + next(iter(exts)) for stem, exts in stems.items() if len(exts) == 1
        )

        lineage: dict[str, dict] = {}
        for path in replay_paths:
            key = rows[path]["task_id"] or "unparsed"
            bucket = lineage.setdefault(key, {"files": 0, "bytes": 0})
            bucket["files"] += 1
            bucket["bytes"] += rows[path]["bytes"]

        hint_counts: dict[str, int] = {}
        for path in replay_paths:
            for hint in rows[path]["lottery_hints"]:
                hint_counts[hint] = hint_counts.get(hint, 0) + 1

        class_counts: dict[str, int] = {}
        for cls in classifications.values():
            class_counts[cls] = class_counts.get(cls, 0) + 1

        verification_counts: dict[str, int] = {}
        for link in replay_links:
            v = link["verification"]
            verification_counts[v] = verification_counts.get(v, 0) + 1

        replay_dates = sorted(
            {rows[p]["artifact_date"] for p in replay_paths if rows[p]["artifact_date"]}
        )
        top_largest = sorted(
            (rows[p] for p in replay_paths), key=lambda r: (-r["bytes"], r["path"])
        )[:10]

        mismatches = verification_counts.get("digest_mismatch", 0)
        chain_integrity = "PASS_NO_DIGEST_MISMATCH" if mismatches == 0 else "DIGEST_MISMATCH_FOUND"

        payload = {
            "schema": SCHEMA,
            "task": "P544B_READONLY_REPLAY_ARTIFACT_INVENTORY",
            "generated_at_utc": commit_timestamp_utc(repo_root, head_commit),
            "head_commit": head_commit,
            "scope": {
                "prefix": SCOPE_PREFIX,
                "source": "git blobs at head_commit (working tree, DB, and untracked files excluded)",
                "replay_tables_probed": list(REPLAY_TABLES),
            },
            "corpus_summary": {
                "total_files": len(corpus_paths),
                "total_bytes": sum(rows[p]["bytes"] for p in corpus_paths),
                "json_parse_errors": json_parse_errors,
                "classification_counts": dict(sorted(class_counts.items())),
            },
            "replay_summary": {
                "replay_related_files": len(replay_paths),
                "replay_related_bytes": sum(rows[p]["bytes"] for p in replay_paths),
                "artifact_date_range": (
                    {"oldest": replay_dates[0], "newest": replay_dates[-1]}
                    if replay_dates
                    else None
                ),
                "unparsed_task_id_paths": sorted(
                    p for p in replay_paths if rows[p]["task_id"] is None
                ),
            },
            "lineage_summary": dict(sorted(lineage.items())),
            "lottery_hint_summary": dict(sorted(hint_counts.items())),
            "link_summary": {
                "replay_owned_links": len(replay_links),
                "verification_counts": dict(sorted(verification_counts.items())),
                "distinct_declared_targets": len(
                    {l["declared_path"] for l in replay_links}
                ),
                "upstream_non_replay_inputs": upstream_inputs,
            },
            "link_records": replay_links,
            "artifacts": [rows[p] for p in replay_paths],
            "unpaired_artifacts": unpaired,
            "top_largest_replay_artifacts": top_largest,
            "chain_integrity": chain_integrity,
            "limitations": [
                "Descriptive inventory only: no statistical, predictive, betting, or deployment claim.",
                "Classification tiers are heuristic (filename/content/link based) and may over-include prose mentions of 'replay'.",
                "Link extraction pairs a path with a digest only when both sit alone in one JSON object under a bare digest key; qualified digests (e.g. production_db_sha256_before) and multi-value objects are never verified.",
                "Only artifacts tracked at head_commit are inventoried; untracked working-tree artifacts are out of scope.",
                "Declared paths that are expected to be untracked (e.g. database files) report path_not_tracked_at_commit by design.",
                "verified_embedded_self_declared means the declared digest is a canonical payload digest restated inside the target, not a raw-byte hash match.",
            ],
            "safety": {
                "database_opened": False,
                "network_used": False,
                "services_controlled": False,
                "writes": "two whitelisted output artifacts only",
            },
            "final_classification": "P544B_READONLY_REPLAY_ARTIFACT_INVENTORY_COMPLETE",
            "recommended_next_task": (
                "Owner decision on remediating any digest_mismatch/unpaired findings and on whether "
                "untracked working-tree research artifacts should be landed or archived."
            ),
        }
        payload["canonical_payload_digest"] = canonical_payload_digest(payload)
        return payload
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(payload: dict) -> str:
    corpus = payload["corpus_summary"]
    replay = payload["replay_summary"]
    links = payload["link_summary"]
    lines = [
        "# P544B — Read-Only Replay Artifact Inventory",
        "",
        "> Descriptive inventory only: not betting advice, no prediction, no production or go-live readiness claim.",
        "> Content is read from git blobs at the pinned commit; the working tree, databases, and untracked files are never read.",
        "",
        "## Provenance",
        "",
        f"- head_commit: `{payload['head_commit']}`",
        f"- scope: `{payload['scope']['prefix']}` (tracked blobs only)",
        f"- schema: `{payload['schema']}`",
        f"- canonical_payload_digest: `{payload['canonical_payload_digest']}`",
        f"- chain_integrity: `{payload['chain_integrity']}`",
        f"- final_classification: `{payload['final_classification']}`",
        "",
        "## Corpus Summary",
        "",
        f"- tracked research artifacts: **{corpus['total_files']}** ({corpus['total_bytes']:,} bytes)",
        f"- replay-related artifacts: **{replay['replay_related_files']}** ({replay['replay_related_bytes']:,} bytes)",
        f"- JSON parse errors: {len(corpus['json_parse_errors'])}",
        f"- replay artifact date range: "
        + (
            f"{replay['artifact_date_range']['oldest']} → {replay['artifact_date_range']['newest']}"
            if replay["artifact_date_range"]
            else "n/a"
        ),
        "",
        "### Classification Tiers (whole corpus)",
        "",
        "| classification | files |",
        "|---|---:|",
    ]
    for cls, count in payload["corpus_summary"]["classification_counts"].items():
        lines.append(f"| `{cls}` | {count} |")
    lines += [
        "",
        "## Replay Lineage (by task id)",
        "",
        "| task | files | bytes |",
        "|---|---:|---:|",
    ]
    for task, bucket in payload["lineage_summary"].items():
        lines.append(f"| `{task}` | {bucket['files']} | {bucket['bytes']:,} |")
    lines += [
        "",
        "## Declared Source-Link Integrity (replay-owned links)",
        "",
        f"- links extracted: **{links['replay_owned_links']}** "
        f"(distinct targets: {links['distinct_declared_targets']})",
        "",
        "| verification | links |",
        "|---|---:|",
    ]
    for status, count in links["verification_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    mismatched = [
        l for l in payload["link_records"] if l["verification"] == "digest_mismatch"
    ]
    if mismatched:
        lines += ["", "### Digest Mismatches", ""]
        for l in mismatched:
            hist = l.get("declared_digest_matches_historical")
            provenance = (
                f" — declared digest matches the file at commit `{hist['commit'][:12]}` ({hist['subject']}); "
                "the file was modified by a later commit, so this is stale-reference drift, not unexplained content"
                if hist
                else " — declared digest matches NO version in head ancestry (unexplained)"
            )
            lines.append(
                f"- `{l['owner_path']}` → `{l['declared_path']}` "
                f"(declared `{l['declared_sha256'][:16]}…`){provenance}"
            )
    if links["upstream_non_replay_inputs"]:
        lines += ["", "### Upstream Non-Replay Inputs Declared by Replay Artifacts", ""]
        lines += [f"- `{p}`" for p in links["upstream_non_replay_inputs"]]
    lines += [
        "",
        "## Largest Replay Artifacts",
        "",
        "| path | bytes | classification |",
        "|---|---:|---|",
    ]
    for row in payload["top_largest_replay_artifacts"]:
        lines.append(f"| `{row['path']}` | {row['bytes']:,} | `{row['classification']}` |")
    if payload["unpaired_artifacts"]:
        lines += [
            "",
            "## Unpaired JSON/MD Artifacts (whole corpus)",
            "",
        ]
        lines += [f"- `{p}`" for p in payload["unpaired_artifacts"]]
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in payload["limitations"]]
    lines += [
        "",
        "## Recommended Next Task",
        "",
        payload["recommended_next_task"],
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default="HEAD", help="commit to inventory (default HEAD)")
    parser.add_argument("--date", default="20260710", help="artifact filename date token")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    payload = build_inventory(repo_root, args.commit)
    recheck = build_inventory(repo_root, args.commit)
    json_text = serialize_json(payload)
    markdown_text = render_markdown(payload)
    if json_text != serialize_json(recheck) or markdown_text != render_markdown(recheck):
        raise SystemExit("non-deterministic artifact bytes; refusing to write artifacts")

    out_dir = repo_root / "outputs" / "research"
    stem = f"p544b_readonly_replay_artifact_inventory_{args.date}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(markdown_text, encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"canonical_payload_digest={payload['canonical_payload_digest']}")
    print(f"chain_integrity={payload['chain_integrity']}")


if __name__ == "__main__":
    main()
