#!/usr/bin/env python3
"""P356A standalone all-strategy inventory closure.

This script is intentionally artifact-only:
  - reads the canonical DB through SQLite immutable/read-only URI;
  - scans the isolated source tree and git history;
  - writes only artifacts/P356A_* files in the current worktree;
  - does not execute strategy prediction/replay code.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_REPO = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew")
CANONICAL_DB = CANONICAL_REPO / "lottery_api" / "data" / "lottery_v2.db"
ALT_DB = CANONICAL_REPO / "data" / "lottery_v2.db"
ARTIFACT_DIR = REPO_ROOT / "artifacts"

TASK_ID = "P356A"
BRANCH = "feature/P356-all-strategy-inventory-replay"
WORKTREE = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P356-all-strategy-inventory-replay"

SEED_BIG_LOTTO = [
    "biglotto_ts3_markov_freq_5bet",
    "biglotto_ts3_markov_4bet_w30",
    "coldpool15_biglotto",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "ts3_regime_3bet",
    "cold_complement_biglotto",
    "markov_single_biglotto",
    "markov_2bet_biglotto",
    "fourier30_markov30_biglotto",
    "biglotto_ts3_acb_4bet",
    "bet2_fourier_expansion_biglotto",
]

ALLOWED_EXECUTABLE_STATUS = {
    "EXECUTABLE",
    "YAML_ONLY",
    "MISSING_CODE",
    "BROKEN_IMPORT",
    "ID_REUSED",
    "DB_ONLY",
    "DOC_ONLY",
    "HISTORICAL_DELETED",
    "UNSUPPORTED",
    "UNKNOWN",
}

ALLOWED_IMPLEMENTATION_KIND = {
    "python",
    "yaml",
    "json",
    "db_only",
    "doc_only",
    "historical_deleted",
    "alias",
    "mixed",
    "unknown",
}

TEXT_EXTS = {
    ".py",
    ".json",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".tsv",
    ".txt",
}
SOURCE_EXTS = {".py"}
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml"}
DOC_EXTS = {".md", ".txt"}
EXCLUDED_PARTS = {
    ".git",
    "node_modules",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "artifacts",
    ".venv",
    "venv",
}
SCAN_ROOTS = [
    "lottery_api",
    "tools",
    "scripts",
    "analysis",
    "config",
    "docs",
    "outputs",
    "data",
    "rejected",
    "tests",
    "00-Plan",
    "ai_lab",
    "public",
    "provisional",
]

SEARCH_TERMS = [
    "strategy_id",
    "strategy",
    "generator",
    "biglotto",
    "lotto",
    "markov",
    "fourier",
    "cold",
    "hot",
    "ts3",
    "regime",
    "echo",
    "deviation",
    "triple",
    "acb",
    "replay",
]

TOKEN_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9]*(?:[_+-][A-Za-z0-9]+){1,}\b")
QUOTED_FIELD_RE = re.compile(
    r"['\"](?:strategy_id|strategy_name|strategy|base_strategy|experiment_strategy|method|generator|model)['\"]\s*:\s*['\"]([^'\"]+)['\"]"
)

NON_STRATEGY_TOKENS = {
    "strategy_id",
    "strategy_name",
    "strategy_prediction_replays",
    "strategy_replay_runs",
    "replay_status",
    "lottery_type",
    "target_draw",
    "history_cutoff",
    "prediction_status",
    "source_path",
    "source_artifact",
    "lifecycle_status",
    "current_status",
    "review_status",
    "generator_version",
    "replay_rows",
    "strategy_scope",
    "strategy_count",
    "strategy_ids",
    "all_strategy_scoreboard",
}

TERM_HINTS = {
    "daily539",
    "markov",
    "fourier",
    "cold",
    "hot",
    "ts3",
    "regime",
    "echo",
    "deviation",
    "triple",
    "acb",
    "zonal",
    "entropy",
    "orthogonal",
    "precision",
    "midfreq",
    "freqort",
    "f4cold",
    "pp3",
    "p0b",
    "p0c",
    "zone_gap",
    "h6",
    "shlc",
    "lag",
    "zone_gap",
    "m3plus",
}


@dataclass
class Occurrence:
    path: str
    line: int
    source_group: str


@dataclass
class InventoryRow:
    strategy_id: str
    lineage_id: str
    game: str = "UNKNOWN"
    bet_count: str = "UNKNOWN"
    current_status: str = "UNKNOWN"
    executable_status: str = "UNKNOWN"
    implementation_kind: str = "unknown"
    source_paths: set[str] = field(default_factory=set)
    git_first_seen_commit: str = "UNKNOWN"
    git_last_seen_commit: str = "UNKNOWN"
    current_exists: bool = False
    callable_entrypoint: str = ""
    parameter_source: str = ""
    implementation_signature_hash: str = ""
    notes: list[str] = field(default_factory=list)
    skip_reason: str = ""
    db_sources: list[dict[str, Any]] = field(default_factory=list)
    evidence_level: str = "[Inferred]"

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "lineage_id": self.lineage_id,
            "game": self.game,
            "bet_count": self.bet_count,
            "current_status": self.current_status,
            "executable_status": self.executable_status,
            "implementation_kind": self.implementation_kind,
            "source_paths": sorted(self.source_paths),
            "git_first_seen_commit": self.git_first_seen_commit,
            "git_last_seen_commit": self.git_last_seen_commit,
            "current_exists": self.current_exists,
            "callable_entrypoint": self.callable_entrypoint,
            "parameter_source": self.parameter_source,
            "implementation_signature_hash": self.implementation_signature_hash,
            "notes": " | ".join(dict.fromkeys(self.notes)),
            "skip_reason": self.skip_reason,
            "db_sources": self.db_sources,
            "evidence_level": self.evidence_level,
        }


def run(cmd: list[str], cwd: Path = REPO_ROOT, timeout: int = 30, check: bool = False) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if check and proc.returncode != 0:
        raise RuntimeError(f"{cmd!r} failed:\n{proc.stdout}")
    return proc.stdout.strip()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_group(path: Path) -> str:
    parts = set(path.parts)
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "source"
    if suffix in CONFIG_EXTS:
        return "config"
    if "docs" in parts or "00-Plan" in parts or suffix in DOC_EXTS:
        return "docs"
    if "outputs" in parts or "public" in parts or "rejected" in parts:
        return "evidence"
    if "tests" in parts:
        return "tests"
    return "other"


def iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = set(path.relative_to(REPO_ROOT).parts)
            if rel_parts & EXCLUDED_PARTS:
                continue
            if path.suffix.lower() not in TEXT_EXTS:
                continue
            if path.stat().st_size > 12 * 1024 * 1024:
                continue
            files.append(path)
    for name in ["README.md", "MEMORY.md", "CLAUDE.md"]:
        path = REPO_ROOT / name
        if path.exists():
            files.append(path)
    return sorted(set(files))


def is_strategy_token(token: str) -> bool:
    s = token.strip().strip("`").strip()
    low = s.lower()
    if s != low:
        return False
    if s.startswith(("p356a_", "http_", "https_")):
        return False
    if re.match(r"^(analy[sz]e|audit|backtest|benchmark|check|debug|test|verify|p\d+[a-z]?_|expected_|actual_|current_|canonical_)", s):
        return False
    if low in NON_STRATEGY_TOKENS:
        return False
    if len(s) < 5 or len(s) > 90:
        return False
    if "/" in s or "." in s:
        return False
    if not any(ch in s for ch in "_+-"):
        return False
    if re.fullmatch(r"[0-9_+-]+", s):
        return False
    if low.endswith(("_id", "_ids", "_rows", "_count", "_status", "_path")):
        return False
    has_method_hint = any(h in low for h in TERM_HINTS)
    has_bet_count = re.search(r"\d+bet\b", low) is not None
    has_strategy_prefix = low.startswith(("daily539_", "539_", "p0b_", "p0c_", "p1_"))
    return has_method_hint or has_bet_count or has_strategy_prefix


def scan_strategy_mentions() -> tuple[dict[str, list[Occurrence]], dict[str, Any]]:
    mentions: dict[str, list[Occurrence]] = defaultdict(list)
    counters: Counter[str] = Counter()
    files = iter_scan_files()
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        group = source_group(path)
        counters[group] += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            found = set()
            for match in TOKEN_RE.finditer(line):
                token = match.group(0)
                if is_strategy_token(token):
                    found.add(token)
            for match in QUOTED_FIELD_RE.finditer(line):
                token = match.group(1)
                if is_strategy_token(token):
                    found.add(token)
            for token in found:
                if len(mentions[token]) < 80:
                    mentions[token].append(Occurrence(rel, lineno, group))
    for seed in SEED_BIG_LOTTO:
        mentions.setdefault(seed, [])
    summary = {
        "files_scanned": len(files),
        "files_by_group": dict(sorted(counters.items())),
        "unique_strategy_like_tokens": len(mentions),
        "search_terms": SEARCH_TERMS,
    }
    return mentions, summary


def connect_immutable(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def db_column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def db_minmax_expr(cols: list[str]) -> str:
    for col in [
        "created_at",
        "updated_at",
        "target_date",
        "draw_date",
        "prediction_date",
        "timestamp",
        "target_draw",
        "draw_number",
        "period",
        "period_number",
        "run_id",
        "id",
    ]:
        if col in cols:
            return col
    return ""


def db_introspection(db_path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    info: dict[str, Any] = {
        "db_path": str(db_path),
        "db_sha256": sha256_path(db_path),
        "immutable_uri": f"file:{db_path}?mode=ro&immutable=1",
    }
    strategy_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with connect_immutable(db_path) as conn:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        schema_dump = "\n".join(
            r["sql"] or ""
            for r in conn.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
            )
        )
        info["tables"] = tables
        info["schema_dump_sha256"] = hashlib.sha256(schema_dump.encode()).hexdigest()
        info["draw_row_count"] = (
            conn.execute('SELECT COUNT(*) FROM "draws"').fetchone()[0]
            if "draws" in tables
            else None
        )
        info["strategy_prediction_replays_rows"] = (
            conn.execute('SELECT COUNT(*) FROM "strategy_prediction_replays"').fetchone()[0]
            if "strategy_prediction_replays" in tables
            else None
        )
        info["strategy_replay_runs_rows"] = (
            conn.execute('SELECT COUNT(*) FROM "strategy_replay_runs"').fetchone()[0]
            if "strategy_replay_runs" in tables
            else None
        )
        table_columns: list[dict[str, Any]] = []
        for table in tables:
            cols = db_column_names(conn, table)
            hits = [
                c
                for c in cols
                if any(
                    term in c.lower()
                    for term in [
                        "strategy_id",
                        "strategy",
                        "generator",
                        "method",
                        "model",
                        "status",
                        "game",
                        "lottery",
                    ]
                )
            ]
            if not hits:
                continue
            table_columns.append({"table": table, "columns": hits})
            time_col = db_minmax_expr(cols)
            game_col = next((c for c in ["lottery_type", "game"] if c in cols), "")
            status_col = next(
                (c for c in ["status", "replay_status", "prediction_status"] if c in cols),
                "",
            )
            id_cols = [c for c in hits if c == "strategy_id"] or [
                c for c in hits if "strategy" in c.lower()
            ]
            for col in id_cols:
                try:
                    rows = conn.execute(
                        f'''
                        SELECT "{col}" AS sid,
                               COUNT(*) AS n
                        FROM "{table}"
                        WHERE "{col}" IS NOT NULL AND TRIM(CAST("{col}" AS TEXT)) != ''
                        GROUP BY "{col}"
                        ORDER BY n DESC, sid
                        '''
                    ).fetchall()
                except sqlite3.Error:
                    continue
                for row in rows:
                    sid = str(row["sid"])
                    if not is_strategy_token(sid) and sid not in SEED_BIG_LOTTO:
                        continue
                    detail: dict[str, Any] = {
                        "table": table,
                        "column": col,
                        "count": row["n"],
                    }
                    if time_col:
                        mm = conn.execute(
                            f'SELECT MIN("{time_col}") AS first, MAX("{time_col}") AS last FROM "{table}" WHERE "{col}"=?',
                            (sid,),
                        ).fetchone()
                        detail["earliest_available_timestamp_or_period"] = mm["first"]
                        detail["latest_available_timestamp_or_period"] = mm["last"]
                    if game_col:
                        games = [
                            str(r[0])
                            for r in conn.execute(
                                f'SELECT DISTINCT "{game_col}" FROM "{table}" WHERE "{col}"=? AND "{game_col}" IS NOT NULL ORDER BY "{game_col}"',
                                (sid,),
                            ).fetchall()
                        ]
                        detail["game"] = games
                    if status_col:
                        statuses = [
                            str(r[0])
                            for r in conn.execute(
                                f'SELECT DISTINCT "{status_col}" FROM "{table}" WHERE "{col}"=? AND "{status_col}" IS NOT NULL ORDER BY "{status_col}"',
                                (sid,),
                            ).fetchall()
                        ]
                        detail["status"] = statuses
                    strategy_sources[sid].append(detail)
        info["strategy_like_columns"] = table_columns
        info["distinct_db_strategy_ids"] = sorted(strategy_sources)
    return info, strategy_sources


def load_registry() -> tuple[dict[str, dict[str, Any]], set[str], set[str]]:
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.replay_strategy_registry import (  # type: ignore
        list_executable_strategy_ids,
        list_strategy_lifecycle_metadata,
    )

    registry: dict[str, dict[str, Any]] = {}
    for row in list_strategy_lifecycle_metadata():
        registry[row["strategy_id"]] = row
    executable = set(list_executable_strategy_ids())
    stubbed = set(registry) - executable
    return registry, executable, stubbed


def ast_literal_from_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    return None


def load_big649_specs() -> dict[str, dict[str, Any]]:
    path = REPO_ROOT / "tools" / "big649_no_db_strategy_output_adapter.py"
    specs: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return specs
    try:
        value = ast_literal_from_assignment(path, "_SPECS")
    except Exception:
        return specs
    for spec in value or []:
        sid = spec.get("strategy_id")
        if sid:
            specs[sid] = spec | {"spec_source_path": path.relative_to(REPO_ROOT).as_posix()}
    return specs


def infer_game(strategy_id: str, row: InventoryRow, registry: dict[str, dict[str, Any]]) -> str:
    if strategy_id in registry:
        lts = registry[strategy_id].get("supported_lottery_types") or []
        if len(lts) == 1:
            return lts[0]
        if lts:
            return ",".join(lts)
    for source in row.db_sources:
        games = source.get("game") or []
        if len(games) == 1:
            return games[0]
    low = strategy_id.lower()
    if "biglotto" in low or "big_lotto" in low or "big649" in low:
        return "BIG_LOTTO"
    if "daily539" in low or low.startswith("539") or "_539" in low:
        return "DAILY_539"
    if "power" in low:
        return "POWER_LOTTO"
    return "UNKNOWN"


def infer_bet_count(strategy_id: str, text: str = "") -> str:
    joined = f"{strategy_id} {text}".lower()
    m = re.search(r"(\d+)\s*bet", joined)
    if m:
        return m.group(1)
    m = re.search(r"(\d+)\s*注", text)
    if m:
        return m.group(1)
    if "single" in joined or "1bet" in joined:
        return "1"
    return "UNKNOWN"


def classify_source_paths(paths: set[str]) -> str:
    exts = {Path(p).suffix.lower() for p in paths}
    if ".py" in exts and (exts & (CONFIG_EXTS | DOC_EXTS | {".csv", ".tsv"})):
        return "mixed"
    if ".py" in exts:
        return "python"
    if exts & {".yaml", ".yml"}:
        return "yaml"
    if ".json" in exts:
        return "json"
    if exts & DOC_EXTS or ".csv" in exts or ".tsv" in exts:
        return "doc_only"
    return "unknown"


def current_implementation_paths(paths: set[str]) -> set[str]:
    result = set()
    for p in paths:
        if p.startswith(("docs/", "outputs/", "public/", "rejected/", "00-Plan/")):
            continue
        if Path(p).suffix.lower() in {".py", ".json", ".yaml", ".yml", ".toml"}:
            result.add(p)
    return result


def signature_hash(strategy_id: str, paths: set[str]) -> str:
    h = hashlib.sha256()
    h.update(strategy_id.encode())
    for rel in prioritized_paths(paths, limit=24):
        path = REPO_ROOT / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = [
            line.strip()
            for line in text.splitlines()
            if strategy_id in line or any(term in line.lower() for term in strategy_id.lower().split("_")[:2])
        ]
        h.update(rel.encode())
        h.update("\n".join(lines[:80]).encode())
    return h.hexdigest()


def prioritized_paths(paths: set[str], limit: int = 24) -> list[str]:
    def key(rel: str) -> tuple[int, str]:
        if rel == "lottery_api/models/replay_strategy_registry.py":
            return (0, rel)
        if rel.startswith(("lottery_api/", "tools/", "scripts/", "analysis/")) and rel.endswith(".py"):
            return (1, rel)
        if rel.startswith(("config/", "rejected/")):
            return (2, rel)
        if rel.startswith(("outputs/replay/", "outputs/research/")):
            return (3, rel)
        if rel.startswith(("docs/", "00-Plan/")):
            return (4, rel)
        return (5, rel)

    return sorted(paths, key=key)[:limit]


def source_history_for_paths(paths: set[str]) -> tuple[str, str]:
    real_paths = [p for p in prioritized_paths(paths, limit=3) if (REPO_ROOT / p).exists()]
    if not real_paths:
        return "UNKNOWN", "UNKNOWN"
    last = run(["git", "log", "--all", "-n", "1", "--format=%H", "--", *real_paths], timeout=4).strip()
    first = run(["git", "log", "--all", "--reverse", "-n", "1", "--format=%H", "--", *real_paths], timeout=4).strip()
    if not first or not last or first == "TIMEOUT" or last == "TIMEOUT":
        return "UNKNOWN", "UNKNOWN"
    return first, last


def string_history(strategy_id: str) -> tuple[str, str]:
    # Conservative bounded pickaxe. Failure leaves UNKNOWN rather than inventing history.
    pattern = strategy_id
    try:
        last = run(["git", "log", "--all", "-n", "1", "--format=%H", "-S", pattern, "--", "."], timeout=4).strip()
        first = run(["git", "log", "--all", "--reverse", "-n", "1", "--format=%H", "-S", pattern, "--", "."], timeout=4).strip()
    except Exception:
        return "UNKNOWN", "UNKNOWN"
    if not first or not last or first == "TIMEOUT" or last == "TIMEOUT":
        return "UNKNOWN", "UNKNOWN"
    return first, last


def strong_mention_ids(mentions: dict[str, list[Occurrence]]) -> set[str]:
    strong: set[str] = set()
    for sid, occs in mentions.items():
        if sid in SEED_BIG_LOTTO:
            strong.add(sid)
            continue
        groups = {o.source_group for o in occs}
        paths = {o.path for o in occs}
        if groups & {"source", "config", "tests"}:
            strong.add(sid)
            continue
        if any(p.startswith("rejected/") for p in paths):
            strong.add(sid)
            continue
        if len(paths) >= 2 and infer_game(sid, InventoryRow(strategy_id=sid, lineage_id=sid), {}) != "UNKNOWN":
            strong.add(sid)
            continue
        if len(paths) >= 3 and re.search(r"\d+bet\b", sid.lower()):
            strong.add(sid)
    return strong


def build_inventory(
    mentions: dict[str, list[Occurrence]],
    db_sources: dict[str, list[dict[str, Any]]],
    registry: dict[str, dict[str, Any]],
    executable_registry: set[str],
    stubbed_registry: set[str],
    big649_specs: dict[str, dict[str, Any]],
) -> list[InventoryRow]:
    ids = strong_mention_ids(mentions) | set(db_sources) | set(registry) | set(big649_specs) | set(SEED_BIG_LOTTO)

    # Include alias evidence for TS3+ACB artifact but report canonical strategy_id.
    if "ts3_acb_4bet_biglotto" in ids:
        ids.add("biglotto_ts3_acb_4bet")

    rows: list[InventoryRow] = []
    for sid in sorted(ids):
        if not is_strategy_token(sid) and sid not in registry and sid not in db_sources and sid not in SEED_BIG_LOTTO:
            continue
        occurrences = mentions.get(sid, [])
        source_paths = {o.path for o in occurrences}

        # Alias source mapping for rejected artifact filename.
        if sid == "biglotto_ts3_acb_4bet" and "ts3_acb_4bet_biglotto" in mentions:
            source_paths |= {o.path for o in mentions["ts3_acb_4bet_biglotto"]}

        row = InventoryRow(strategy_id=sid, lineage_id=f"{sid}__current")
        row.source_paths = set(prioritized_paths(source_paths, limit=40))
        row.db_sources = db_sources.get(sid, [])
        if sid in registry:
            meta = registry[sid]
            row.current_status = meta.get("lifecycle_status", "UNKNOWN")
            row.parameter_source = f"registry:min_history={meta.get('min_history')};version={meta.get('strategy_version')}"
            row.notes.append(f"[Confirmed] current registry entry: {meta.get('strategy_name', sid)}")
            row.evidence_level = "[Confirmed]"
            row.source_paths.add("lottery_api/models/replay_strategy_registry.py")
        if sid in big649_specs:
            spec = big649_specs[sid]
            row.source_paths.add(spec["spec_source_path"])
            row.source_paths.add(spec["source_path"])
            row.callable_entrypoint = (
                f'{spec["module"]}.{spec.get("candidate_function") or spec.get("frozen_function")}'
            )
            row.parameter_source = f"{spec['spec_source_path']}:_SPECS kwargs={spec.get('kwargs', {})}"
            row.notes.append("[Confirmed] frozen BIG 6/49 no-DB adapter spec")
            row.evidence_level = "[Confirmed]"
        if row.db_sources:
            row.notes.append("[Confirmed] DB strategy evidence from immutable read-only introspection")
            row.evidence_level = "[Confirmed]"

        row.game = infer_game(sid, row, registry)
        row.bet_count = infer_bet_count(sid, " ".join(row.notes))

        impl_paths = current_implementation_paths(row.source_paths)
        row.current_exists = bool(impl_paths)
        row.implementation_kind = classify_source_paths(row.source_paths)

        if sid in executable_registry:
            row.executable_status = "EXECUTABLE"
            row.implementation_kind = "python"
            row.callable_entrypoint = row.callable_entrypoint or f"lottery_api.models.replay_strategy_registry.get_adapter('{sid}')"
            row.skip_reason = "NOT_RUN: P356A primary deliverable is inventory; replay not run in this task."
        elif sid in big649_specs:
            row.executable_status = "EXECUTABLE"
            row.implementation_kind = "python"
            row.skip_reason = "NOT_RUN: executable frozen BIG 6/49 callable found, but replay readiness blocked by lineage/readiness scope."
        elif sid == "biglotto_ts3_acb_4bet":
            row.executable_status = "MISSING_CODE"
            row.implementation_kind = "json" if row.source_paths else "unknown"
            row.current_exists = False
            row.skip_reason = "MISSING_CODE: registry lifecycle stub/rejected artifact only; no predict tool found."
            row.notes.append("[Confirmed] special handling: do not fake execution for biglotto_ts3_acb_4bet")
        elif sid in stubbed_registry:
            row.executable_status = "MISSING_CODE"
            row.skip_reason = "MISSING_CODE: registry lifecycle stub is non-executable."
        elif row.db_sources and not row.source_paths:
            row.executable_status = "DB_ONLY"
            row.implementation_kind = "db_only"
            row.skip_reason = "DB_ONLY: DB strategy evidence exists but no current implementation/config/doc source found."
        elif row.db_sources and not impl_paths:
            row.executable_status = "DB_ONLY"
            if row.implementation_kind == "unknown":
                row.implementation_kind = "db_only"
            row.skip_reason = "DB_ONLY: DB rows exist; current executable implementation not found."
        elif row.source_paths and all(p.startswith(("docs/", "outputs/", "public/", "00-Plan/")) for p in row.source_paths):
            row.executable_status = "DOC_ONLY"
            row.implementation_kind = "doc_only"
            row.current_exists = False
            row.skip_reason = "DOC_ONLY: mentioned only in docs/evidence/report artifacts."
        elif row.source_paths and any(p.startswith("rejected/") for p in row.source_paths):
            row.executable_status = "MISSING_CODE"
            row.implementation_kind = "json"
            row.current_exists = False
            row.skip_reason = "MISSING_CODE: rejected artifact evidence without callable entrypoint."
        elif row.source_paths:
            row.executable_status = "UNKNOWN"
            row.skip_reason = "UNKNOWN: source mention found but callable entrypoint not established."
        else:
            first, last = string_history(sid) if sid in SEED_BIG_LOTTO else ("UNKNOWN", "UNKNOWN")
            if first != "UNKNOWN":
                row.executable_status = "HISTORICAL_DELETED"
                row.implementation_kind = "historical_deleted"
                row.skip_reason = "HISTORICAL_DELETED: git pickaxe found historical mention but no current source path."
                row.git_first_seen_commit, row.git_last_seen_commit = first, last
            else:
                row.executable_status = "UNKNOWN"
                row.skip_reason = "UNKNOWN: seed or inferred ID lacks current source/DB evidence."

        if row.executable_status not in ALLOWED_EXECUTABLE_STATUS:
            row.executable_status = "UNKNOWN"
        if row.implementation_kind not in ALLOWED_IMPLEMENTATION_KIND:
            row.implementation_kind = "unknown"
        row.implementation_signature_hash = signature_hash(sid, row.source_paths)
        should_collect_history = (
            sid in registry
            or sid in db_sources
            or sid in big649_specs
            or sid in SEED_BIG_LOTTO
        )
        if should_collect_history and (
            row.git_first_seen_commit == "UNKNOWN" or row.git_last_seen_commit == "UNKNOWN"
        ):
            first, last = source_history_for_paths(row.source_paths)
            if first == "UNKNOWN" and sid in SEED_BIG_LOTTO:
                first, last = string_history(sid)
            row.git_first_seen_commit = first
            row.git_last_seen_commit = last
        rows.append(row)

    # Explicit split for known reused strategy_id: rejected JSON lineage vs P42/P280 frozen code.
    base_rows = [r for r in rows if r.strategy_id == "bet2_fourier_expansion_biglotto"]
    if base_rows:
        base = base_rows[0]
        base.lineage_id = "bet2_fourier_expansion_biglotto__p42_p280_frozen_code"
        base.executable_status = "ID_REUSED"
        base.implementation_kind = "python"
        base.current_exists = True
        base.notes.append(
            "[Confirmed] ID reused/split: current P42/P280 frozen code differs from rejected JSON rationale lineage"
        )
        base.skip_reason = "ID_REUSED: lineage split required; replay not run."

        artifact = InventoryRow(
            strategy_id="bet2_fourier_expansion_biglotto",
            lineage_id="bet2_fourier_expansion_biglotto__rejected_json_historical",
            game="BIG_LOTTO",
            bet_count="2",
            current_status=registry.get("bet2_fourier_expansion_biglotto", {}).get("lifecycle_status", "REJECTED"),
            executable_status="ID_REUSED",
            implementation_kind="json",
            source_paths={"rejected/bet2_fourier_expansion_biglotto.json"},
            git_first_seen_commit="UNKNOWN",
            git_last_seen_commit="UNKNOWN",
            current_exists=False,
            callable_entrypoint="",
            parameter_source="rejected/bet2_fourier_expansion_biglotto.json",
            notes=[
                "[Confirmed] rejected artifact describes Fourier expansion replacement/zone-filter lineage",
                "[Confirmed] split from later P42/P280 frozen code lineage sharing same strategy_id",
            ],
            skip_reason="ID_REUSED: rejected artifact lineage is not executable as current code.",
            db_sources=db_sources.get("bet2_fourier_expansion_biglotto", []),
            evidence_level="[Confirmed]",
        )
        artifact.git_first_seen_commit, artifact.git_last_seen_commit = source_history_for_paths(artifact.source_paths)
        artifact.implementation_signature_hash = signature_hash(artifact.strategy_id, artifact.source_paths)
        rows.append(artifact)

    return sorted(rows, key=lambda r: (r.game, r.strategy_id, r.lineage_id))


def phase0_evidence(db_info: dict[str, Any], alt_db_info: dict[str, Any] | None) -> dict[str, Any]:
    gh_status = "GH_NOT_AVAILABLE"
    if shutil.which("gh"):
        gh_status = run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                "20",
                "--json",
                "number,title,headRefName,baseRefName,state,url",
            ],
            cwd=CANONICAL_REPO,
            timeout=20,
        )
    return {
        "authorization": "Confirmed as separate standalone user message immediately preceding task execution.",
        "canonical_repo": str(CANONICAL_REPO),
        "canonical_cwd": run(["pwd"], cwd=CANONICAL_REPO),
        "canonical_git_status_short": run(["git", "status", "--short"], cwd=CANONICAL_REPO),
        "canonical_branch": run(["git", "branch", "--show-current"], cwd=CANONICAL_REPO),
        "canonical_head": run(["git", "rev-parse", "HEAD"], cwd=CANONICAL_REPO),
        "local_main_sha": run(["git", "rev-parse", "main"], cwd=CANONICAL_REPO),
        "origin_main_sha": run(["git", "rev-parse", "origin/main"], cwd=CANONICAL_REPO),
        "main_vs_origin_main_left_right": run(
            ["git", "rev-list", "--left-right", "--count", "main...origin/main"],
            cwd=CANONICAL_REPO,
        ),
        "target_worktree": WORKTREE,
        "target_worktree_exists_after_phase1": Path(WORKTREE).exists(),
        "branch_exists_after_phase1": bool(
            run(
                ["git", "show-ref", "--verify", "--hash", f"refs/heads/{BRANCH}"],
                cwd=CANONICAL_REPO,
            )
        ),
        "gh_open_pr_status": gh_status,
        "db_candidates": {
            str(CANONICAL_DB): {"exists": CANONICAL_DB.exists()},
            str(ALT_DB): {"exists": ALT_DB.exists(), "sha256": sha256_path(ALT_DB) if ALT_DB.exists() else None},
        },
        "selected_db": db_info,
        "alternate_db": alt_db_info,
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[InventoryRow]) -> None:
    fieldnames = list(rows[0].to_dict().keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            d = row.to_dict()
            d["source_paths"] = ";".join(d["source_paths"])
            d["db_sources"] = json.dumps(d["db_sources"], ensure_ascii=False, sort_keys=True)
            writer.writerow(d)


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(x).replace("\n", " ") for x in row) + " |")
    return "\n".join(out)


def count_by(rows: list[InventoryRow], attr: str) -> dict[str, int]:
    c: Counter[str] = Counter(str(getattr(r, attr) or "UNKNOWN") for r in rows)
    return dict(sorted(c.items()))


def summary_payload(rows: list[InventoryRow], scan_summary: dict[str, Any], db_info: dict[str, Any]) -> dict[str, Any]:
    big = [r for r in rows if r.game == "BIG_LOTTO" or "biglotto" in r.strategy_id]
    executable = [r for r in rows if r.executable_status == "EXECUTABLE"]
    non_exec = [r for r in rows if r.executable_status != "EXECUTABLE"]
    seed = {}
    for sid in SEED_BIG_LOTTO:
        matches = [r for r in rows if r.strategy_id == sid]
        seed[sid] = {
            "covered": bool(matches),
            "lineage_count": len(matches),
            "statuses": sorted({r.executable_status for r in matches}),
            "source_paths": sorted({p for r in matches for p in r.source_paths})[:20],
        }
    id_reuse = [r for r in rows if r.executable_status == "ID_REUSED"]
    return {
        "task": TASK_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branch": BRANCH,
        "worktree": WORKTREE,
        "head": run(["git", "rev-parse", "HEAD"]),
        "replay_status": "NOT_RUN",
        "replay_status_reason": (
            "Inventory closure was the primary deliverable. Replay readiness is blocked by "
            "mixed executable/stub/artifact-only lineages and explicit ID reuse handling."
        ),
        "counts": {
            "total_strategy_lineages": len(rows),
            "big_lotto_lineages": len(big),
            "executable_count": len(executable),
            "non_executable_count": len(non_exec),
            "db_only_count": sum(1 for r in rows if r.executable_status == "DB_ONLY" or r.implementation_kind == "db_only"),
            "doc_only_count": sum(1 for r in rows if r.executable_status == "DOC_ONLY" or r.implementation_kind == "doc_only"),
            "historical_deleted_count": sum(1 for r in rows if r.executable_status == "HISTORICAL_DELETED"),
            "id_reuse_cases": len({r.strategy_id for r in id_reuse}),
        },
        "skipped_by_reason": count_by(rows, "executable_status"),
        "status_distribution": count_by(rows, "current_status"),
        "implementation_kind_distribution": count_by(rows, "implementation_kind"),
        "big_lotto_seed_coverage": seed,
        "id_reuse_strategy_ids": sorted({r.strategy_id for r in id_reuse}),
        "scan_summary": scan_summary,
        "db_summary": {
            "path": db_info["db_path"],
            "sha256": db_info["db_sha256"],
            "draw_row_count": db_info["draw_row_count"],
            "strategy_prediction_replays_rows": db_info["strategy_prediction_replays_rows"],
            "strategy_replay_runs_rows": db_info["strategy_replay_runs_rows"],
            "distinct_db_strategy_ids": db_info["distinct_db_strategy_ids"],
        },
        "old_replay_overview_gaps": [
            "[Confirmed] P262B notes prior overview coverage mode was required to expose all 40 known strategies / 41 cells.",
            "[Confirmed] P263A/P263B notes D3 status audit previously covered only a subset and required SSOT rebuild.",
            "[Inferred] P356A extends beyond ONLINE/current overview by including registry stubs, DB-only rows, rejected artifacts, docs/evidence, and git history.",
        ],
    }


def write_markdown_artifacts(
    rows: list[InventoryRow],
    phase0: dict[str, Any],
    summary: dict[str, Any],
    db_before: dict[str, Any],
    db_after: dict[str, Any],
) -> None:
    phase0_md = [
        "# P356A Phase 0 Evidence",
        "",
        "- Standalone Owner authorization: [Confirmed]",
        f"- Canonical repo: `{phase0['canonical_repo']}`",
        f"- Canonical cwd: `{phase0['canonical_cwd']}`",
        f"- Canonical branch: `{phase0['canonical_branch']}`",
        f"- Canonical HEAD: `{phase0['canonical_head']}`",
        f"- local main: `{phase0['local_main_sha']}`",
        f"- origin/main: `{phase0['origin_main_sha']}`",
        f"- main...origin/main left/right: `{phase0['main_vs_origin_main_left_right']}`",
        f"- Target worktree exists after Phase 1: `{phase0['target_worktree_exists_after_phase1']}`",
        f"- Branch exists after Phase 1: `{phase0['branch_exists_after_phase1']}`",
        "",
        "## Canonical Git Status",
        "```text",
        phase0["canonical_git_status_short"],
        "```",
        "",
        "## Open PR Status",
        "```json",
        phase0["gh_open_pr_status"],
        "```",
        "",
        "## DB Read-Only Evidence",
        f"- Selected DB: `{phase0['selected_db']['db_path']}`",
        f"- Immutable URI: `{phase0['selected_db']['immutable_uri']}`",
        f"- DB SHA256: `{phase0['selected_db']['db_sha256']}`",
        f"- Draw row count: `{phase0['selected_db']['draw_row_count']}`",
        f"- Schema dump hash: `{phase0['selected_db']['schema_dump_sha256']}`",
        f"- strategy_prediction_replays rows: `{phase0['selected_db']['strategy_prediction_replays_rows']}`",
        f"- strategy_replay_runs rows: `{phase0['selected_db']['strategy_replay_runs_rows']}`",
        f"- Distinct DB strategy IDs: `{len(phase0['selected_db']['distinct_db_strategy_ids'])}`",
        "",
        "## DB Strategy IDs",
        "```text",
        "\n".join(phase0["selected_db"]["distinct_db_strategy_ids"]),
        "```",
    ]
    (ARTIFACT_DIR / "P356A_phase0_evidence.md").write_text("\n".join(phase0_md) + "\n", encoding="utf-8")

    skipped_rows = [
        [r.strategy_id, r.lineage_id, r.game, r.executable_status, r.skip_reason]
        for r in rows
        if r.skip_reason
    ]
    skipped_md = [
        "# P356A Replay Skipped Strategies",
        "",
        "Replay status: `NOT_RUN`.",
        "",
        "Every inventory lineage is represented here because P356A did not execute replay.",
        "",
        markdown_table(skipped_rows, ["strategy_id", "lineage_id", "game", "executable_status", "skip_reason"]),
    ]
    (ARTIFACT_DIR / "P356A_replay_skipped_strategies.md").write_text("\n".join(skipped_md) + "\n", encoding="utf-8")

    reuse_rows = [
        [r.strategy_id, r.lineage_id, r.implementation_kind, r.executable_status, "; ".join(sorted(r.source_paths)), " | ".join(r.notes)]
        for r in rows
        if r.executable_status == "ID_REUSED"
    ]
    reuse_md = [
        "# P356A Strategy ID Reuse Cases",
        "",
        "Policy: do not merge by `strategy_id` alone.",
        "",
        markdown_table(reuse_rows, ["strategy_id", "lineage_id", "kind", "status", "source_paths", "notes"])
        if reuse_rows
        else "No ID reuse cases identified.",
    ]
    (ARTIFACT_DIR / "P356A_strategy_id_reuse_cases.md").write_text("\n".join(reuse_md) + "\n", encoding="utf-8")

    seed_rows = [
        [sid, data["covered"], data["lineage_count"], ",".join(data["statuses"])]
        for sid, data in summary["big_lotto_seed_coverage"].items()
    ]
    summary_md = [
        "# P356A Strategy Inventory Summary",
        "",
        f"- Total strategy lineages: `{summary['counts']['total_strategy_lineages']}`",
        f"- Big Lotto lineages: `{summary['counts']['big_lotto_lineages']}`",
        f"- Executable count: `{summary['counts']['executable_count']}`",
        f"- Non-executable count: `{summary['counts']['non_executable_count']}`",
        f"- DB-only count: `{summary['counts']['db_only_count']}`",
        f"- Doc-only count: `{summary['counts']['doc_only_count']}`",
        f"- Historical-deleted count: `{summary['counts']['historical_deleted_count']}`",
        f"- ID reuse cases: `{summary['counts']['id_reuse_cases']}`",
        f"- Replay: `{summary['replay_status']}`",
        "",
        "## Status Distribution",
        "```json",
        json.dumps(summary["status_distribution"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Skipped By Reason",
        "```json",
        json.dumps(summary["skipped_by_reason"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Big Lotto Seed Coverage",
        markdown_table(seed_rows, ["seed_strategy_id", "covered", "lineage_count", "executable_statuses"]),
        "",
        "## Old Replay Overview Gaps",
        "\n".join(f"- {x}" for x in summary["old_replay_overview_gaps"]),
        "",
        "## Evidence Labels",
        "- `[Confirmed]`: direct registry, DB, source, artifact, or git evidence.",
        "- `[Inferred]`: classification inferred from naming/source grouping when direct metadata is absent.",
        "- `[Unknown]`: no reliable current or historical evidence beyond seed/inference.",
        "- `NOT_RUN`: no replay was executed by P356A.",
    ]
    (ARTIFACT_DIR / "P356A_inventory_summary.md").write_text("\n".join(summary_md) + "\n", encoding="utf-8")

    completeness = {
        "every_inventory_lineage_has_skipped_row": len([r for r in rows if r.skip_reason]) == len(rows),
        "every_skipped_row_has_skip_reason": all(bool(r.skip_reason) for r in rows),
        "big_lotto_seed_list_fully_accounted_for": all(
            data["covered"] for data in summary["big_lotto_seed_coverage"].values()
        ),
        "db_sha_before": db_before["db_sha256"],
        "db_sha_after": db_after["db_sha256"],
        "db_draw_rows_before": db_before["draw_row_count"],
        "db_draw_rows_after": db_after["draw_row_count"],
        "db_replay_rows_before": db_before["strategy_prediction_replays_rows"],
        "db_replay_rows_after": db_after["strategy_prediction_replays_rows"],
    }
    validation_md = [
        "# P356A Validation Log",
        "",
        "- Replay readiness: `NOT_RUN`",
        "- Reason: executable entrypoints are not uniformly reliable across all lineages; ID reuse and artifact/stub-only cases would contaminate replay.",
        "- Strategy status changes: `NONE`",
        "- Canonical DB writes: `NONE`",
        "",
        "## Artifact Completeness",
        "```json",
        json.dumps(completeness, ensure_ascii=False, indent=2),
        "```",
        "",
        "## DB Before/After",
        f"- SHA before: `{db_before['db_sha256']}`",
        f"- SHA after: `{db_after['db_sha256']}`",
        f"- Draw rows before/after: `{db_before['draw_row_count']}` / `{db_after['draw_row_count']}`",
        f"- Replay rows before/after: `{db_before['strategy_prediction_replays_rows']}` / `{db_after['strategy_prediction_replays_rows']}`",
        "",
        "## Checks To Run After Generation",
        "- `git status --short`",
        "- `git diff --check`",
        "- `python3 -m py_compile scripts/p356a_all_strategy_inventory.py tests/test_p356a_inventory_artifacts.py`",
        "- `python3 -m pytest tests/test_p356a_inventory_artifacts.py`",
    ]
    (ARTIFACT_DIR / "P356A_validation_log.md").write_text("\n".join(validation_md) + "\n", encoding="utf-8")


def main() -> int:
    if Path.cwd().resolve() != REPO_ROOT:
        print(f"Run from isolated worktree root: {REPO_ROOT}", file=sys.stderr)
        return 2
    ARTIFACT_DIR.mkdir(exist_ok=True)

    selected_db = CANONICAL_DB if CANONICAL_DB.exists() else ALT_DB
    if not selected_db.exists():
        print("No DB candidate exists", file=sys.stderr)
        return 3

    db_before, db_sources = db_introspection(selected_db)
    alt_info = None
    if ALT_DB.exists() and ALT_DB != selected_db:
        alt_info, _ = db_introspection(ALT_DB)

    mentions, scan_summary = scan_strategy_mentions()
    registry, executable_registry, stubbed_registry = load_registry()
    big649_specs = load_big649_specs()
    rows = build_inventory(mentions, db_sources, registry, executable_registry, stubbed_registry, big649_specs)
    db_after, _ = db_introspection(selected_db)

    phase0 = phase0_evidence(db_before, alt_info)
    summary = summary_payload(rows, scan_summary, db_before)

    write_json(ARTIFACT_DIR / "P356A_strategy_inventory_all.json", {
        "summary": summary,
        "phase0": phase0,
        "inventory": [r.to_dict() for r in rows],
    })
    write_csv(ARTIFACT_DIR / "P356A_strategy_inventory_all.csv", rows)
    write_markdown_artifacts(rows, phase0, summary, db_before, db_after)

    print(json.dumps({
        "inventory_rows": len(rows),
        "big_lotto_rows": summary["counts"]["big_lotto_lineages"],
        "replay_status": summary["replay_status"],
        "db_sha_before": db_before["db_sha256"],
        "db_sha_after": db_after["db_sha256"],
        "artifacts": sorted(p.name for p in ARTIFACT_DIR.glob("P356A_*")),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
