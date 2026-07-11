#!/usr/bin/env python3
"""Build a fail-closed P0 strategy-universe inventory.

This generator collects heuristic inventory evidence from repository artifacts and
an explicitly selected, verified SQLite snapshot. Its classifications are not
governance ground truth and require review before governance use.

All paths and provenance values are explicit CLI inputs. The default mode is
``PLAN_ONLY_NO_DB_NO_WRITE``: it validates configuration, but does not scan the
repository, hash or open the DB, generate an inventory, create directories, or
write output files. Full collection requires ``--execute-readonly``; output files
also require ``--write-outputs``. Existing outputs additionally require
``--overwrite-existing``.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote


GENERATOR_VERSION = "p0-strategy-universe-inventory-v1"
PLAN_MODE = "PLAN_ONLY_NO_DB_NO_WRITE"
READONLY_MODE = "EXECUTE_READONLY_NO_WRITE"
WRITE_MODE = "EXECUTE_READONLY_WRITE_OUTPUTS"
HEURISTIC_CAVEAT = (
    "This inventory is heuristic evidence, not governance ground truth; "
    "classifications require independent review."
)

LIFECYCLE_ORDER = [
    "PRODUCTION",
    "WATCHING",
    "PROVISIONAL",
    "REJECTED",
    "OFFLINE",
    "EXPERIMENTAL",
    "UNKNOWN",
]
LOTTERY_ORDER = ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "CROSS_GAME", "UNSPECIFIED"]

STATUS_MAP = {
    "ACTIVE": "PRODUCTION",
    "ONLINE": "PRODUCTION",
    "REJECTED": "REJECTED",
    "OBSERVATION": "WATCHING",
    "WATCHING": "WATCHING",
    "OBSERVE": "WATCHING",
    "PROVISIONAL": "PROVISIONAL",
    "RETIRED": "OFFLINE",
    "OFFLINE": "OFFLINE",
    "DEPRECATED": "OFFLINE",
    "SUPERSEDED": "OFFLINE",
}

ALIAS_TO_CANONICAL = {
    "Triple Strike": "biglotto_triple_strike",
    "大樂透 Triple Strike": "biglotto_triple_strike",
    "Power Precision (Edge +2.23%)": "power_precision_3bet",
    "威力彩 Precision 3注": "power_precision_3bet",
    "威力彩 Orthogonal 5注": "power_orthogonal_5bet",
    "大樂透 Deviation 2注": "biglotto_deviation_2bet",
    "今彩539 F4 Cold": "daily539_f4cold",
    "今彩539 Markov Cold": "daily539_markov_cold",
    "TS3+Markov(w=30)+頻率正交 5注": "biglotto_5bet_ts3_markov_freq",
    "PP3+頻率正交 5注": "powerlotto_5bet_orthogonal",
    "TS3+Regime 3注": "ts3_regime_3bet",
    "biglotto_triple_strike": "biglotto_triple_strike",
    "power_precision_3bet": "power_precision_3bet",
}

LESSON_ALIAS_HINTS = {
    "Cluster Pivot": "cluster_pivot",
    "SHORT_MOMENTUM": "short_momentum",
    "LATE_BLOOMER": "late_bloomer",
    "Core-Satellite": "core_satellite",
    "Gap Dynamic Threshold": "gap_dynamic_threshold",
    "Zone Constraint": "zone_constraint",
    "Sum公式修正": "sum_formula_fix",
    "Streak Boost": "streak_boost",
}

STRATEGY_WORDS = {
    "frequency", "trend", "bayesian", "markov", "montecarlo", "monte_carlo",
    "deviation", "ensemble", "optimized", "hybrid", "hot_cold", "sum_range",
    "wheeling", "number_pairs", "statistical", "odd_even", "zone", "cluster",
    "entropy", "temporal", "feature_engineering", "random_forest", "prophet",
    "xgboost", "lstm", "transformer", "maml",
    "apriori", "acb", "pp3", "f4cold", "fourier", "orthogonal", "ts3",
    "regime", "midfreq", "echo", "pivot", "streak", "gap", "cold", "hot",
    "precision", "triple", "residue", "dispersion", "odd_tail", "microfish", "power",
    "biglotto", "daily539", "strategy",
}


class SafetyError(RuntimeError):
    """Raised when fail-closed configuration or output validation fails."""


@dataclasses.dataclass(frozen=True)
class Config:
    repo_root: Path
    db_path: Path
    output_json: Path
    output_markdown: Path
    provenance_label: str
    expected_db_sha256: str
    execute_readonly: bool
    write_outputs: bool
    overwrite_existing: bool

    @property
    def execution_mode(self) -> str:
        if not self.execute_readonly:
            return PLAN_MODE
        return WRITE_MODE if self.write_outputs else READONLY_MODE


@dataclasses.dataclass
class EntryState:
    strategy_id: str
    display_name: str = "UNKNOWN"
    source_paths: Set[str] = dataclasses.field(default_factory=set)
    lifecycle_votes: List[str] = dataclasses.field(default_factory=list)
    lottery_votes: List[str] = dataclasses.field(default_factory=list)
    historical_sources: Set[str] = dataclasses.field(default_factory=set)
    lessons_refs: Set[str] = dataclasses.field(default_factory=set)
    rsm_referenced: bool = False
    notes: Set[str] = dataclasses.field(default_factory=set)
    aliases: Set[str] = dataclasses.field(default_factory=set)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build heuristic P0 inventory evidence, not governance ground truth. "
            "Default: plan-only, with no DB access, scan, generation, or writes."
        )
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--db-path", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-markdown", required=True, type=Path)
    parser.add_argument("--provenance-label", required=True)
    parser.add_argument("--expected-db-sha256", required=True)
    parser.add_argument(
        "--execute-readonly",
        action="store_true",
        help="Hash the verified snapshot, then scan inputs and open SQLite read-only.",
    )
    parser.add_argument(
        "--write-outputs",
        action="store_true",
        help="Write JSON and Markdown; requires --execute-readonly.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Permit replacing existing output files; requires --write-outputs.",
    )
    return parser


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_db_like(path: Path) -> bool:
    return path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".db3"}


def validate_config(args: argparse.Namespace) -> Config:
    config = Config(
        repo_root=_resolve(args.repo_root),
        db_path=_resolve(args.db_path),
        output_json=_resolve(args.output_json),
        output_markdown=_resolve(args.output_markdown),
        provenance_label=args.provenance_label.strip(),
        expected_db_sha256=args.expected_db_sha256.strip().lower(),
        execute_readonly=bool(args.execute_readonly),
        write_outputs=bool(args.write_outputs),
        overwrite_existing=bool(args.overwrite_existing),
    )

    if not config.repo_root.is_dir() or not (config.repo_root / ".git").exists():
        raise SafetyError("--repo-root must identify an existing Git worktree")
    if not config.provenance_label:
        raise SafetyError("--provenance-label must not be blank")
    if "::" in config.provenance_label:
        raise SafetyError("--provenance-label must not contain the reserved '::' separator")
    if any(ord(character) < 32 for character in config.provenance_label):
        raise SafetyError("--provenance-label must not contain control characters")
    if not re.fullmatch(r"[0-9a-f]{64}", config.expected_db_sha256):
        raise SafetyError("--expected-db-sha256 must be exactly 64 hexadecimal characters")
    if config.write_outputs and not config.execute_readonly:
        raise SafetyError("--write-outputs requires --execute-readonly")
    if config.overwrite_existing and not config.write_outputs:
        raise SafetyError("--overwrite-existing requires --write-outputs")
    if config.output_json == config.output_markdown:
        raise SafetyError("JSON and Markdown output paths must be distinct")
    if config.output_json == config.db_path or config.output_markdown == config.db_path:
        raise SafetyError("an output path must not equal the DB path")
    if _is_db_like(config.output_json) or _is_db_like(config.output_markdown):
        raise SafetyError("output paths must not use a DB-like extension")
    if config.output_json.suffix.lower() != ".json":
        raise SafetyError("--output-json must end in .json")
    if config.output_markdown.suffix.lower() not in {".md", ".markdown"}:
        raise SafetyError("--output-markdown must end in .md or .markdown")
    for output in (config.output_json, config.output_markdown):
        if not _is_within(output, config.repo_root):
            raise SafetyError(f"output path is outside --repo-root: {output}")
        if output.exists() and not config.overwrite_existing:
            raise SafetyError(f"output already exists; refusing overwrite: {output}")

    live_paths = {
        _resolve(config.repo_root / "lottery_api" / "data" / "lottery_v2.db"),
        _resolve(config.repo_root / "data" / "lottery_v2.db"),
    }
    if config.db_path in live_paths:
        raise SafetyError("refusing known live DB path; provide a verified snapshot")
    return config


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_snapshot(config: Config) -> None:
    if not config.db_path.exists() or not config.db_path.is_file():
        raise SafetyError(f"verified snapshot does not exist or is not a file: {config.db_path}")
    actual = sha256_file(config.db_path)
    if actual != config.expected_db_sha256:
        raise SafetyError(
            "snapshot SHA-256 mismatch; refusing DB open "
            f"(expected {config.expected_db_sha256}, got {actual})"
        )


def slugify(raw: str) -> str:
    text = raw.strip().lower().replace("/", "_").replace("+", "_")
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "unknown"


def is_strategy_like(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(sep in lowered for sep in ["/", ":", "|"]):
        return False
    if lowered.endswith((".json", ".md", ".py", ".js", ".cjs", ".txt")):
        return False
    if " vs " in lowered or "monitor" in lowered:
        return False
    if lowered in {
        "big lotto", "power lotto", "daily 539", "big_lotto", "power_lotto",
        "daily_539", "biglotto", "powerlotto", "daily539",
    }:
        return False
    if lowered in {
        "multi_strategy", "coordinator-direct (7 agents)",
        "coordinator-direct (6 agents)",
    }:
        return False
    if any(word in lowered for word in STRATEGY_WORDS):
        return True
    return bool(re.search(r"\b\d+bet\b|\b(f4cold|ts3|pp3|acb|midfreq)\b", lowered))


def canonicalize(raw: str, source_hint: str = "") -> str:
    raw_norm = raw.strip()
    if raw_norm in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[raw_norm]
    if raw_norm in LESSON_ALIAS_HINTS:
        return LESSON_ALIAS_HINTS[raw_norm]
    slug = slugify(raw_norm)
    if source_hint.startswith("strategies/"):
        parts = source_hint.split("/")
        if len(parts) > 1:
            prefix = {
                "big_lotto": "biglotto",
                "power_lotto": "powerlotto",
                "daily_539": "daily539",
            }.get(parts[1])
            if prefix and not slug.startswith(prefix + "_"):
                return f"{prefix}_{slug}"
    return slug


def infer_lottery(text: str) -> str:
    lowered = text.lower()
    if "power_lotto" in lowered or "powerlotto" in lowered or "威力彩" in text:
        return "POWER_LOTTO"
    if "big_lotto" in lowered or "biglotto" in lowered or "大樂透" in text:
        return "BIG_LOTTO"
    if "daily_539" in lowered or "daily539" in lowered or "539" in text or "今彩" in text:
        return "DAILY_539"
    return "UNSPECIFIED"


def infer_lottery_from_id(strategy_id: str) -> str:
    sid = strategy_id.lower()
    if (
        "539" in sid
        or sid.startswith("daily539")
        or sid == "acb_1bet"
        or "midfreq_acb" in sid
        or "f4cold" in sid
    ):
        return "DAILY_539"
    if any(
        marker in sid
        for marker in (
            "power", "pp3", "orthogonal", "fourier_rhythm_3bet", "ts3", "h6_gate",
        )
    ):
        return "POWER_LOTTO"
    if any(
        marker in sid
        for marker in ("biglotto", "triple_strike", "deviation", "echo", "regime_2bet")
    ):
        return "BIG_LOTTO"
    if sid in {
        "frequency", "trend", "bayesian", "markov", "montecarlo", "ensemble",
        "statistical", "hot_cold", "sum_range", "number_pairs", "wheeling",
        "odd_even", "zone_balance", "zone_split", "core_satellite",
    }:
        return "CROSS_GAME"
    return "UNSPECIFIED"


def ensure_entry(entries: Dict[str, EntryState], strategy_id: str) -> EntryState:
    if strategy_id not in entries:
        entries[strategy_id] = EntryState(strategy_id=strategy_id)
    return entries[strategy_id]


def attach(
    entries: Dict[str, EntryState],
    strategy_id: str,
    *,
    display_name: Optional[str] = None,
    source_path: Optional[str] = None,
    lifecycle: Optional[str] = None,
    lottery: Optional[str] = None,
    historical_source: Optional[str] = None,
    lesson_ref: Optional[str] = None,
    rsm_referenced: bool = False,
    note: Optional[str] = None,
    alias: Optional[str] = None,
) -> None:
    if not strategy_id:
        return
    entry = ensure_entry(entries, strategy_id)
    if display_name and entry.display_name == "UNKNOWN":
        entry.display_name = display_name
    if source_path:
        entry.source_paths.add(source_path)
    if lifecycle:
        entry.lifecycle_votes.append(lifecycle)
    if lottery:
        entry.lottery_votes.append(lottery)
    if historical_source:
        entry.historical_sources.add(historical_source)
    if lesson_ref:
        entry.lessons_refs.add(lesson_ref)
    if rsm_referenced:
        entry.rsm_referenced = True
    if note:
        entry.notes.add(note)
    if alias:
        entry.aliases.add(alias)


def _read_json_or_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            return yaml.safe_load(text)
        except Exception:
            pass

    # Preserve the orphan generator's dependency-free fallback for the simple,
    # top-level strategy metadata files used by this collector.
    data: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().split("#", 1)[0].strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            value = value[1:-1]
        data[key] = value
    if data:
        return data
    raise SafetyError(f"cannot parse JSON/YAML artifact: {path}")


def collect_registry(entries: Dict[str, EntryState], repo_root: Path) -> None:
    path = repo_root / "lottery_api" / "models" / "replay_strategy_registry.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    blocks: List[str] = []
    current: List[str] = []
    depth = 0
    in_block = False
    for line in text.splitlines():
        if "_StrategyMeta(" in line:
            in_block = True
            current = [line]
            depth = line.count("(") - line.count(")")
            continue
        if in_block:
            current.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                blocks.append("\n".join(current))
                current = []
                in_block = False
    for block in blocks:
        sid_match = re.search(r'strategy_id="([^"]+)"', block)
        if not sid_match:
            continue
        sid = sid_match.group(1)
        name_match = re.search(r'strategy_name="([^"]+)"', block)
        status_match = re.search(r'status="([^"]+)"', block)
        status = status_match.group(1) if status_match else "UNKNOWN"
        attach(
            entries,
            sid,
            display_name=name_match.group(1) if name_match else sid,
            source_path=str(path.relative_to(repo_root)),
            lifecycle=STATUS_MAP.get(status, "UNKNOWN"),
            lottery=infer_lottery(block),
            historical_source="prediction_runs",
            rsm_referenced=status in {"ACTIVE", "ONLINE"},
            note="replay_registry",
        )


def collect_strategy_packages(entries: Dict[str, EntryState], repo_root: Path) -> None:
    for path in sorted((repo_root / "strategies").glob("*/*/strategy.yaml")):
        data = _read_json_or_yaml(path)
        if not isinstance(data, dict):
            continue
        rel = str(path.relative_to(repo_root))
        raw_id = str(data.get("strategy_id") or path.parent.name)
        sid = canonicalize(raw_id, rel)
        status = str(data.get("status") or "UNKNOWN").split()[0].upper()
        lottery = str(data.get("lottery") or data.get("lottery_type") or infer_lottery(rel))
        sibling_names = (
            "sim_result.json", "performance_log.json", "backtest_report.md",
            "stat_test.txt", "version_tag.txt",
        )
        has_history = any(
            (path.parent / name).exists()
            for name in sibling_names
            if name != "version_tag.txt"
        )
        lifecycle = STATUS_MAP.get(status, "UNKNOWN")
        attach(
            entries,
            sid,
            display_name=str(data.get("name") or sid),
            source_path=rel,
            lifecycle=lifecycle,
            lottery=lottery,
            historical_source="simulation_log" if has_history else "none",
            rsm_referenced=lifecycle == "PRODUCTION",
            note=f"strategy_package_status:{status}",
        )
        for sibling_name in sibling_names:
            sibling = path.parent / sibling_name
            if sibling.exists():
                attach(entries, sid, source_path=str(sibling.relative_to(repo_root)))


def collect_frontend(entries: Dict[str, EntryState], repo_root: Path) -> None:
    app_rel = "src/core/App.js"
    engine_rel = "src/engine/PredictionEngine.js"
    app_path = repo_root / app_rel
    engine_path = repo_root / engine_rel
    if not app_path.is_file():
        return
    text = app_path.read_text(encoding="utf-8")
    match = re.search(r"const\s+strategyNames\s*=\s*\{(.*?)\n\s*\};", text, re.DOTALL)
    if not match:
        return
    pairs = re.findall(
        r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", match.group(1)
    )
    for raw, display in pairs:
        attach(
            entries,
            canonicalize(raw, app_rel),
            display_name=display,
            source_path=app_rel,
            lifecycle="EXPERIMENTAL",
            lottery="CROSS_GAME",
            historical_source="none",
            note="frontend_strategy_definition",
        )
        if engine_path.is_file():
            attach(entries, canonicalize(raw, app_rel), source_path=engine_rel)


def collect_models(entries: Dict[str, EntryState], repo_root: Path) -> None:
    model_root = repo_root / "lottery_api" / "models"
    model_names = (
        "unified_predictor.py", "special_predictor.py", "fourier_rhythm.py",
        "orthogonal_2bet.py", "dual_bet_strategy.py", "bayesian_ensemble.py",
        "selective_ensemble.py", "constraint_filter_predictor.py",
        "arima_predictor.py", "attention_lstm_torch.py",
        "dynamic_ensemble_predictor.py", "optimized_bayesian_predictor.py",
        "advanced_bayesian_analyzer.py", "meta_predictor.py",
        "ensemble_predictor.py", "auto_optimizer.py", "big_lotto_optimizer.py",
        "biglotto_tme_optimizer.py", "regime_monitor.py",
    )
    for path in (model_root / name for name in model_names):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(repo_root))
        attach(
            entries,
            canonicalize(path.stem, rel),
            display_name=path.stem,
            source_path=rel,
            lifecycle="EXPERIMENTAL",
            lottery=infer_lottery(rel),
            historical_source="none",
            note="model_module",
        )
        candidates = set(re.findall(r"def\s+([A-Za-z0-9_]+_predict)\s*\(", text))
        candidates.update(re.findall(r"strategy_(?:id|name)\s*=\s*['\"]([^'\"]+)['\"]", text))
        for raw in candidates:
            raw_id = raw[:-8] if raw.endswith("_predict") else raw
            if not is_strategy_like(raw_id) and raw_id not in ALIAS_TO_CANONICAL:
                continue
            attach(
                entries,
                canonicalize(raw_id, rel),
                display_name=raw_id,
                source_path=rel,
                lifecycle="EXPERIMENTAL",
                lottery=infer_lottery(rel + " " + raw_id),
                historical_source="none",
                note="model_candidate",
            )


def collect_rejected(entries: Dict[str, EntryState], repo_root: Path) -> Set[str]:
    rejected_ids: Set[str] = set()
    for path in sorted((repo_root / "rejected").glob("*.json")):
        rel = str(path.relative_to(repo_root))
        text = path.read_text(encoding="utf-8")
        sid = canonicalize(path.stem, rel)
        rejected_ids.add(sid)
        display_match = re.search(
            r'"(?:strategy|name|failure_reason|reason)"\s*:\s*"([^"]+)"', text
        )
        display = display_match.group(1) if display_match else path.stem
        attach(
            entries,
            sid,
            display_name=display,
            source_path=rel,
            lifecycle="REJECTED",
            lottery=infer_lottery(path.stem + " " + text),
            historical_source="rejected_json",
            note="rejected_artifact",
        )
        alias_sid = canonicalize(display, rel)
        if alias_sid != sid and is_strategy_like(display):
            rejected_ids.add(alias_sid)
            attach(
                entries,
                alias_sid,
                display_name=display,
                source_path=rel,
                lifecycle="REJECTED",
                lottery=infer_lottery(path.stem + " " + text),
                historical_source="rejected_json",
                note=f"possible_duplicate_of:{sid}",
                alias=path.stem,
            )
    return rejected_ids


def collect_monitors(entries: Dict[str, EntryState], repo_root: Path) -> Set[str]:
    rsm_ids: Set[str] = set()
    for path in sorted((repo_root / "data").glob("rolling_monitor_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = data.get("records", {})
        if not isinstance(records, dict):
            continue
        rel = str(path.relative_to(repo_root))
        for raw_id in records:
            sid = canonicalize(str(raw_id), rel)
            rsm_ids.add(sid)
            attach(
                entries,
                sid,
                display_name=str(raw_id),
                source_path=rel,
                lifecycle="PRODUCTION",
                lottery=str(data.get("lottery_type") or infer_lottery(rel)),
                historical_source="prediction_runs",
                rsm_referenced=True,
                note="rsm_current_strategy",
            )
    return rsm_ids


def collect_lessons(entries: Dict[str, EntryState], repo_root: Path) -> None:
    for rel in ("MEMORY.md", "memory/lessons.md", "memory/todo.md"):
        path = repo_root / rel
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            tokens = set(re.findall(r"`([^`]+)`", line))
            for match in re.findall(
                r"([A-Za-z][A-Za-z0-9_+\-]+(?: [A-Za-z][A-Za-z0-9_+\-]+){0,4})",
                line,
            ):
                if len(match) >= 3 and (
                    is_strategy_like(match) or match in LESSON_ALIAS_HINTS
                ):
                    tokens.add(match)
            lifecycle_evidence = any(
                marker in line
                for marker in (
                    "REJECT", "WATCH", "OBSERVE", "PROVISIONAL", "OFFLINE",
                    "RETIRED", "生產策略", "production", "現役",
                )
            )
            if line_number > 107 and not lifecycle_evidence:
                continue
            for token in tokens:
                if token in {"M3+", "M2+", "OOS", "Edge", "p"}:
                    continue
                if (
                    len(token.split()) == 1
                    and token not in LESSON_ALIAS_HINTS
                    and not re.search(r"[_\-0-9]", token)
                ):
                    continue
                if any(
                    noise in token.lower()
                    for noise in ("grid_search", "report", "analysis", "benchmark", "study")
                ):
                    continue
                if not is_strategy_like(token) and token not in LESSON_ALIAS_HINTS:
                    continue
                upper = line.upper()
                lifecycle: Optional[str] = None
                if "REJECT" in upper:
                    lifecycle = "REJECTED"
                elif "WATCH" in upper or "OBSERVE" in upper:
                    lifecycle = "WATCHING"
                elif "PROVISIONAL" in upper:
                    lifecycle = "PROVISIONAL"
                elif "OFFLINE" in upper or "RETIRED" in upper or "DEPRECATED" in upper:
                    lifecycle = "OFFLINE"
                elif "PRODUCTION" in upper or "生產策略" in line or "現役" in line:
                    lifecycle = "PRODUCTION"
                attach(
                    entries,
                    canonicalize(token, rel),
                    display_name=token,
                    source_path=f"{rel}:L{line_number}",
                    lifecycle=lifecycle,
                    lottery=infer_lottery(line),
                    historical_source="none",
                    lesson_ref=f"L{line_number}",
                    note=f"lesson_reference:{rel}:L{line_number}",
                )


def collect_tools(entries: Dict[str, EntryState], repo_root: Path) -> None:
    tools_root = repo_root / "tools"
    if not tools_root.is_dir():
        return
    for path in sorted(tools_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".js", ".cjs", ".json", ".md", ".txt"}:
            continue
        name = path.name.lower()
        prefixes = (
            "predict_", "backtest_", "optimize_", "generate_", "audit_",
            "verify_", "review_", "discover_", "power_", "biglotto_", "p3_",
        )
        if (
            not name.startswith(prefixes)
            and "strategy" not in name
            and "bet" not in name
        ):
            continue
        rel = str(path.relative_to(repo_root))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        candidates = set(re.findall(r"strategy_(?:id|name)\s*[:=]\s*['\"]([^'\"]+)['\"]", text))
        candidates.update(re.findall(r"\bname\s*[:=]\s*['\"]([^'\"]+)['\"]", text))
        candidates.update(re.findall(r"def\s+([A-Za-z0-9_]+)\s*\(", text))
        candidates.update(re.findall(r"class\s+([A-Za-z0-9_]+Strategy)\b", text))
        for raw in candidates:
            if not is_strategy_like(raw) and raw not in ALIAS_TO_CANONICAL:
                continue
            lowered_text = text.lower()
            lifecycle = "EXPERIMENTAL"
            if "rejected" in lowered_text:
                lifecycle = "REJECTED"
            elif "provisional" in lowered_text:
                lifecycle = "PROVISIONAL"
            elif "watch" in lowered_text or "observe" in lowered_text:
                lifecycle = "WATCHING"
            elif "active" in lowered_text or "production" in lowered_text or "現役" in text:
                lifecycle = "PRODUCTION"
            attach(
                entries,
                canonicalize(raw, rel),
                display_name=raw,
                source_path=rel,
                lifecycle=lifecycle,
                lottery=infer_lottery(rel + " " + raw + " " + text[:3000]),
                historical_source=(
                    "simulation_log"
                    if any(marker in name for marker in ("backtest", "sim", "benchmark"))
                    else "none"
                ),
                note="tools_candidate",
            )


def collect_db_names(
    entries: Dict[str, EntryState], config: Config
) -> Tuple[Set[str], Set[str], Set[str]]:
    uri = f"file:{quote(str(config.db_path), safe='/')}?mode=ro&immutable=1"
    replay_ids: Set[str] = set()
    pred_run_ids: Set[str] = set()
    pred_item_ids: Set[str] = set()
    labels = {
        "replay": f"{config.provenance_label}::strategy_prediction_replays",
        "runs": f"{config.provenance_label}::prediction_runs",
        "items": f"{config.provenance_label}::prediction_items",
    }

    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        for row in conn.execute(
            "SELECT DISTINCT strategy_id FROM strategy_prediction_replays "
            "WHERE strategy_id IS NOT NULL"
        ):
            raw = str(row["strategy_id"])
            sid = canonicalize(raw, labels["replay"])
            replay_ids.add(sid)
            attach(
                entries, sid, display_name=raw, source_path=labels["replay"],
                lifecycle="PRODUCTION", lottery="UNSPECIFIED",
                historical_source="prediction_runs", note="db_replay_row",
            )
        for row in conn.execute(
            "SELECT DISTINCT strategy_name FROM prediction_runs "
            "WHERE strategy_name IS NOT NULL"
        ):
            raw = str(row["strategy_name"])
            if raw in {"MULTI_STRATEGY", "Coordinator-Direct (7 agents)", "Coordinator-Direct (6 agents)"}:
                continue
            sid = canonicalize(raw, labels["runs"])
            pred_run_ids.add(sid)
            attach(
                entries, sid, display_name=raw, source_path=labels["runs"],
                lifecycle="PRODUCTION" if is_strategy_like(raw) else "UNKNOWN",
                lottery="UNSPECIFIED", historical_source="prediction_runs",
                note="db_prediction_run",
            )
        for row in conn.execute(
            "SELECT DISTINCT strategy_name FROM prediction_items "
            "WHERE strategy_name IS NOT NULL"
        ):
            raw = str(row["strategy_name"])
            if raw in {"MULTI_STRATEGY", "Coordinator-Direct (7 agents)", "Coordinator-Direct (6 agents)"}:
                continue
            sid = canonicalize(raw, labels["items"])
            pred_item_ids.add(sid)
            attach(
                entries, sid, display_name=raw, source_path=labels["items"],
                lifecycle="UNKNOWN", lottery="UNSPECIFIED",
                historical_source="prediction_runs", note="db_prediction_item",
            )
    return replay_ids, pred_run_ids, pred_item_ids


def _pick_lifecycle(votes: Sequence[str], paths: Iterable[str]) -> str:
    if not votes:
        return (
            "OFFLINE"
            if any(
                marker in path.lower()
                for path in paths
                for marker in ("offline", "retired", "deprecated")
            )
            else "UNKNOWN"
        )
    priority = {state: index for index, state in enumerate(LIFECYCLE_ORDER)}
    return min(votes, key=lambda state: priority.get(state, len(priority)))


def _pick_lottery(votes: Sequence[str], strategy_id: str, paths: Iterable[str]) -> str:
    normalized = [vote if vote in LOTTERY_ORDER else infer_lottery(vote) for vote in votes]
    normalized = [vote for vote in normalized if vote in LOTTERY_ORDER]
    if normalized:
        counts = Counter(normalized)
        best = counts.most_common()
        if len(best) == 1 or best[0][1] > best[1][1]:
            return best[0][0]
        for preferred in LOTTERY_ORDER:
            if preferred in counts:
                return preferred
    inferred = infer_lottery_from_id(strategy_id)
    if inferred != "UNSPECIFIED":
        return inferred
    return infer_lottery(" ".join([strategy_id, *paths]))


def derive_summary(
    entries: Dict[str, EntryState],
    replay_ids: Set[str],
    pred_run_ids: Set[str],
    pred_item_ids: Set[str],
    rejected_ids: Set[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, int], Dict[str, int]]:
    strategies: List[Dict[str, Any]] = []
    lifecycle_counts: Counter[str] = Counter()
    lottery_counts: Counter[str] = Counter()
    gaps = {
        "strategies_with_replay_rows": 0,
        "strategies_without_replay_rows": 0,
        "strategies_with_historical_records_but_no_replay": 0,
        "strategies_with_no_records_anywhere": 0,
    }
    for sid, entry in sorted(entries.items()):
        if not entry.source_paths:
            continue
        lifecycle = _pick_lifecycle(entry.lifecycle_votes, entry.source_paths)
        lottery = _pick_lottery(entry.lottery_votes, sid, entry.source_paths)
        replay_row = sid in replay_ids
        if replay_row or sid in pred_run_ids or sid in pred_item_ids:
            historical_source = "prediction_runs"
        elif sid in rejected_ids:
            historical_source = "rejected_json"
        elif entry.historical_sources - {"none"}:
            historical_source = sorted(entry.historical_sources - {"none"})[0]
        else:
            historical_source = "none"
        has_history = historical_source != "none"
        gaps["strategies_with_replay_rows" if replay_row else "strategies_without_replay_rows"] += 1
        if not replay_row:
            key = (
                "strategies_with_historical_records_but_no_replay"
                if has_history else "strategies_with_no_records_anywhere"
            )
            gaps[key] += 1
        notes = sorted(entry.notes)
        if len(entry.source_paths) > 1:
            notes.append(f"source_count:{len(entry.source_paths)}")
        if entry.aliases:
            notes.append("aliases:" + ",".join(sorted(entry.aliases)))
        strategies.append({
            "strategy_id": sid,
            "display_name": entry.display_name,
            "source_paths": sorted(entry.source_paths),
            "lifecycle_state": lifecycle,
            "lottery_type": lottery,
            "has_historical_predictions": has_history,
            "historical_record_source": historical_source,
            "lessons_reference": sorted(entry.lessons_refs),
            "rsm_referenced": bool(entry.rsm_referenced or lifecycle == "PRODUCTION"),
            "notes": "; ".join(notes),
        })
        lifecycle_counts[lifecycle] += 1
        lottery_counts[lottery] += 1
    return strategies, dict(lifecycle_counts), dict(lottery_counts), gaps


def validate_payload(payload: Dict[str, Any]) -> None:
    strategies = payload.get("strategies")
    if not isinstance(strategies, list):
        raise SafetyError("payload strategies must be a list")
    total = payload.get("total_count")
    if total != len(strategies):
        raise SafetyError("payload total_count does not match strategies length")
    if total != sum(payload.get("by_lifecycle", {}).values()):
        raise SafetyError("payload total_count does not match lifecycle counts")
    if total != sum(payload.get("by_lottery", {}).values()):
        raise SafetyError("payload total_count does not match lottery counts")
    for row in strategies:
        if not row.get("strategy_id") or not row.get("source_paths"):
            raise SafetyError(f"invalid strategy row: {row!r}")
        for value in row.values():
            if isinstance(value, str) and value in {"TBD", "TODO", "null"}:
                raise SafetyError(f"forbidden placeholder in strategy {row['strategy_id']}")


def generate_inventory(config: Config) -> Dict[str, Any]:
    if not config.execute_readonly:
        raise SafetyError("inventory generation requires --execute-readonly")
    verify_snapshot(config)

    entries: Dict[str, EntryState] = {}
    collect_registry(entries, config.repo_root)
    collect_strategy_packages(entries, config.repo_root)
    collect_frontend(entries, config.repo_root)
    collect_models(entries, config.repo_root)
    rejected_ids = collect_rejected(entries, config.repo_root)
    rsm_ids = collect_monitors(entries, config.repo_root)
    collect_lessons(entries, config.repo_root)
    collect_tools(entries, config.repo_root)
    replay_ids, pred_run_ids, pred_item_ids = collect_db_names(entries, config)
    for sid in rsm_ids:
        if sid in entries:
            entries[sid].rsm_referenced = True

    strategies, by_lifecycle, by_lottery, coverage = derive_summary(
        entries, replay_ids, pred_run_ids, pred_item_ids, rejected_ids
    )
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    strategies.sort(
        key=lambda row: (
            LIFECYCLE_ORDER.index(row["lifecycle_state"]),
            LOTTERY_ORDER.index(row["lottery_type"]),
            row["strategy_id"],
        )
    )
    payload: Dict[str, Any] = {
        "generated_at": generated_at,
        "provenance": {
            "db_path_display": str(config.db_path),
            "provenance_label": config.provenance_label,
            "expected_db_sha256": config.expected_db_sha256,
            "generator_version": GENERATOR_VERSION,
            "generated_at": generated_at,
            "execution_mode": config.execution_mode,
            "caveat": HEURISTIC_CAVEAT,
        },
        "total_count": len(strategies),
        "by_lifecycle": {key: by_lifecycle.get(key, 0) for key in LIFECYCLE_ORDER},
        "by_lottery": {key: by_lottery.get(key, 0) for key in LOTTERY_ORDER},
        "strategies": strategies,
        "coverage_gap_analysis": coverage,
    }
    validate_payload(payload)
    return payload


def build_report(payload: Dict[str, Any]) -> str:
    provenance = payload["provenance"]
    lines = [
        "# P0 Strategy Universe Inventory Report",
        "",
        f"Generated at: `{payload['generated_at']}`",
        f"Generator version: `{provenance['generator_version']}`",
        f"Provenance label: `{provenance['provenance_label']}`",
        f"Expected DB SHA-256: `{provenance['expected_db_sha256']}`",
        f"Execution mode: `{provenance['execution_mode']}`",
        "",
        "## Heuristic Evidence Caveat",
        "",
        HEURISTIC_CAVEAT,
        "",
        "## Totals",
        "",
        f"- Total strategies: **{payload['total_count']}**",
        "- Lifecycle breakdown:",
    ]
    for key in LIFECYCLE_ORDER:
        lines.append(f"  - {key}: {payload['by_lifecycle'].get(key, 0)}")
    lines.append("- Lottery breakdown:")
    for key in LOTTERY_ORDER:
        lines.append(f"  - {key}: {payload['by_lottery'].get(key, 0)}")
    gap = payload["coverage_gap_analysis"]
    lines.extend([
        "",
        "## Coverage Gap Summary",
        "",
        f"- Strategies with replay rows: {gap['strategies_with_replay_rows']}",
        f"- Strategies without replay rows: {gap['strategies_without_replay_rows']}",
        "- Strategies with historical records but no replay: "
        f"{gap['strategies_with_historical_records_but_no_replay']}",
        f"- Strategies with no records anywhere: {gap['strategies_with_no_records_anywhere']}",
        "",
        "## Safety",
        "",
        "- The configured SQLite input was opened read-only after digest verification.",
        "- No strategy logic, migrations, DB writes, VACUUM, backup, or ATTACH were performed.",
        "- Output generation does not promote heuristic classifications to governance truth.",
    ])
    return "\n".join(lines) + "\n"


def write_outputs(config: Config, payload: Dict[str, Any]) -> None:
    if not config.execute_readonly or not config.write_outputs:
        raise SafetyError("output writing requires --execute-readonly and --write-outputs")
    for output in (config.output_json, config.output_markdown):
        if output.exists() and not config.overwrite_existing:
            raise SafetyError(f"output appeared after validation; refusing overwrite: {output}")
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    markdown_text = build_report(payload)
    config.output_json.parent.mkdir(parents=True, exist_ok=True)
    config.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    config.output_json.write_text(json_text, encoding="utf-8")
    config.output_markdown.write_text(markdown_text, encoding="utf-8")


def plan_summary(config: Config) -> Dict[str, Any]:
    return {
        "status": "PLAN_ONLY",
        "execution_mode": config.execution_mode,
        "repo_root": str(config.repo_root),
        "db_path": str(config.db_path),
        "output_json": str(config.output_json),
        "output_markdown": str(config.output_markdown),
        "provenance_label": config.provenance_label,
        "expected_db_sha256": config.expected_db_sha256,
        "db_opened": False,
        "db_hash_computed": False,
        "inventory_generated": False,
        "outputs_written": False,
        "caveat": HEURISTIC_CAVEAT,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    config = validate_config(build_parser().parse_args(argv))
    if not config.execute_readonly:
        print(json.dumps(plan_summary(config), ensure_ascii=False, indent=2))
        return 0

    payload = generate_inventory(config)
    if config.write_outputs:
        write_outputs(config, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
