#!/usr/bin/env python3
"""
P0 Strategy Universe Inventory
===============================

Read-only inventory generator for every strategy artifact we can discover
without executing strategy logic, writing the DB, or mutating replay rows.

Inputs scanned:
  - lottery_api/engine/*.py
  - strategies/*/*/strategy.yaml and sibling artifacts
  - src/core/App.js and src/engine/PredictionEngine.js
  - lottery_api/models/*.py
  - rejected/*.json
  - tools/*.py / *.js / *.cjs / *.json
  - MEMORY.md, memory/lessons.md, memory/todo.md
  - data/rolling_monitor_*.json
  - replay/analysis docs for lifecycle evidence
  - SQLite read-only tables: prediction_runs, prediction_items,
    strategy_prediction_replays

Outputs:
  - outputs/replay/p0_strategy_universe_inventory_20260517.json
  - docs/replay/p0_strategy_universe_inventory_report_20260517.md
"""

from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON = REPO_ROOT / "outputs" / "replay" / "p0_strategy_universe_inventory_20260517.json"
OUT_MD = REPO_ROOT / "docs" / "replay" / "p0_strategy_universe_inventory_report_20260517.md"

LIFECYCLE_ORDER = [
    "PRODUCTION",
    "WATCHING",
    "PROVISIONAL",
    "REJECTED",
    "OFFLINE",
    "EXPERIMENTAL",
    "UNKNOWN",
]

LOTTERY_ORDER = [
    "DAILY_539",
    "BIG_LOTTO",
    "POWER_LOTTO",
    "CROSS_GAME",
    "UNSPECIFIED",
]

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

PROJECT_ID_HINTS = {
    "539": "DAILY_539",
    "BIG_LOTTO": "BIG_LOTTO",
    "大樂透": "BIG_LOTTO",
    "POWER_LOTTO": "POWER_LOTTO",
    "威力彩": "POWER_LOTTO",
    "今彩539": "DAILY_539",
}

STRATEGY_WORDS = {
    "frequency",
    "trend",
    "bayesian",
    "markov",
    "montecarlo",
    "monte_carlo",
    "deviation",
    "ensemble",
    "backend_optimized",
    "optimized_ensemble",
    "dual_bet_hybrid",
    "hot_cold",
    "sum_range",
    "wheeling",
    "number_pairs",
    "statistical",
    "odd_even",
    "zone_balance",
    "zone_split",
    "core_satellite",
    "cluster",
    "clustering",
    "dynamic_ensemble",
    "entropy",
    "temporal",
    "feature_engineering",
    "random_forest",
    "ai_prophet",
    "ai_xgboost",
    "ai_lstm",
    "ai_transformer",
    "ai_bayesian_ensemble",
    "ai_maml",
    "apriori",
    "acb",
    "pp3",
    "f4cold",
    "fourier",
    "orthogonal",
    "ts3",
    "regime",
    "midfreq",
    "echo",
    "pivot",
    "streak",
    "gap",
    "cold",
    "hot",
    "precision",
    "triple",
    "residue",
    "dispersion",
    "odd_tail",
    "microfish",
    "power",
    "biglotto",
    "daily539",
}


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

    def add_source(self, path: str) -> None:
        self.source_paths.add(path)

    def add_lifecycle(self, state: Optional[str]) -> None:
        if not state:
            return
        self.lifecycle_votes.append(state)

    def add_lottery(self, lottery: Optional[str]) -> None:
        if not lottery:
            return
        self.lottery_votes.append(lottery)

    def add_note(self, note: str) -> None:
        if note:
            self.notes.add(note)


def slugify(raw: str) -> str:
    text = raw.strip().lower()
    text = text.replace("/", "_")
    text = text.replace("(", "_").replace(")", "_")
    text = text.replace("+", "_")
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def is_strategy_like(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"multi_strategy", "coordinator-direct (7 agents)", "coordinator-direct (6 agents)"}:
        return False
    if any(word in lowered for word in STRATEGY_WORDS):
        return True
    if re.search(r"\b\d+bet\b", lowered):
        return True
    if re.search(r"\b(f4cold|ts3|pp3|acb|midfreq|orthogonal|fourier|markov)\b", lowered):
        return True
    if "strategy" in lowered:
        return True
    return False


def canonicalize(raw: str, source_hint: str = "") -> str:
    if raw in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[raw]
    raw_norm = raw.strip()
    if raw_norm in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[raw_norm]
    if raw_norm in LESSON_ALIAS_HINTS:
        return LESSON_ALIAS_HINTS[raw_norm]
    if raw_norm in PROJECT_ID_HINTS:
        return PROJECT_ID_HINTS[raw_norm]
    if re.fullmatch(r"[A-Za-z0-9_.\-+/() ]+", raw_norm) and any(ch.isalpha() for ch in raw_norm):
        slug = slugify(raw_norm)
    else:
        slug = slugify(raw_norm)

    # Keep well-formed ids stable; prefix strategy-package folders to avoid collisions.
    if source_hint.startswith("strategies/") and "/" in source_hint:
        parent = source_hint.split("/")[1]
        if parent == "big_lotto":
            return f"biglotto_{slug}"
        if parent == "power_lotto":
            return f"powerlotto_{slug}"
        if parent == "daily_539":
            return f"daily539_{slug}"
    return slug


def infer_lottery_from_text(text: str) -> str:
    joined = text.lower()
    if "big_lotto" in joined or "大樂透" in text:
        return "BIG_LOTTO"
    if "power_lotto" in joined or "威力彩" in text:
        return "POWER_LOTTO"
    if "daily_539" in joined or "539" in text or "今彩" in text:
        return "DAILY_539"
    return "UNSPECIFIED"


def infer_lottery_from_id(strategy_id: str) -> str:
    sid = strategy_id.lower()
    if "539" in sid or sid.startswith("daily539") or "acb_1bet" == sid or "midfreq_acb" in sid or "f4cold" in sid:
        return "DAILY_539"
    if "power" in sid or "pp3" in sid or "orthogonal" in sid or "fourier_rhythm_3bet" in sid or "ts3" in sid or "h6_gate" in sid:
        return "POWER_LOTTO"
    if "biglotto" in sid or "triple_strike" in sid or "deviation" in sid or "echo" in sid or "regime_2bet" in sid:
        return "BIG_LOTTO"
    if sid in {"frequency", "trend", "bayesian", "markov", "montecarlo", "deviation", "ensemble", "statistical", "hot_cold", "sum_range", "number_pairs", "wheeling", "odd_even", "zone_balance", "zone_split", "core_satellite"}:
        return "CROSS_GAME"
    return "UNSPECIFIED"


def infer_historical_source(paths: Iterable[str], entry_id: str, replay_ids: Set[str], pred_run_ids: Set[str], pred_item_ids: Set[str], rejected_ids: Set[str]) -> str:
    if entry_id in replay_ids:
        return "prediction_runs"
    if entry_id in pred_run_ids or entry_id in pred_item_ids:
        return "prediction_runs"
    if entry_id in rejected_ids:
        return "rejected_json"
    if any(p.endswith(".json") or p.endswith(".md") or p.endswith(".yaml") for p in paths):
        if any("/strategies/" in p or p.startswith("strategies/") for p in paths):
            return "simulation_log"
    return "none"


def pick_lifecycle(votes: Sequence[str], source_paths: Sequence[str]) -> str:
    if not votes:
        if any("deprecated" in p.lower() or "retired" in p.lower() or "offline" in p.lower() for p in source_paths):
            return "OFFLINE"
        return "UNKNOWN"
    priority = {state: i for i, state in enumerate(LIFECYCLE_ORDER)}
    return sorted(votes, key=lambda s: priority.get(s, 999))[0]


def pick_lottery(votes: Sequence[str], strategy_id: str, source_paths: Sequence[str]) -> str:
    if votes:
        counts = Counter(votes)
        best = counts.most_common()
        if len(best) == 1 or best[0][1] > best[1][1]:
            return best[0][0]
        # prefer explicit main lotteries over unspecified/cross-game
        for preferred in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "CROSS_GAME", "UNSPECIFIED"]:
            if preferred in counts:
                return preferred
    inferred = infer_lottery_from_id(strategy_id)
    if inferred != "UNSPECIFIED":
        return inferred
    text = " ".join(source_paths + [strategy_id])
    inferred = infer_lottery_from_text(text)
    return inferred if inferred in LOTTERY_ORDER else "UNSPECIFIED"


def open_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_entry(entries: Dict[str, EntryState], strategy_id: str, display_name: Optional[str] = None) -> EntryState:
    strategy_id = strategy_id.strip()
    if strategy_id not in entries:
        entries[strategy_id] = EntryState(strategy_id=strategy_id)
    if display_name and entries[strategy_id].display_name == "UNKNOWN":
        entries[strategy_id].display_name = display_name
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
    entry = ensure_entry(entries, strategy_id, display_name)
    if display_name and entry.display_name == "UNKNOWN":
        entry.display_name = display_name
    if source_path:
        entry.add_source(source_path)
    if lifecycle:
        entry.add_lifecycle(lifecycle)
    if lottery:
        entry.add_lottery(lottery)
    if historical_source:
        entry.historical_sources.add(historical_source)
    if lesson_ref:
        entry.lessons_refs.add(lesson_ref)
    if rsm_referenced:
        entry.rsm_referenced = True
    if note:
        entry.add_note(note)
    if alias:
        entry.aliases.add(alias)


def parse_strategy_yaml(path: Path) -> Dict[str, str]:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml is not None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

    # Minimal fallback parser for the simple YAML files in strategies/.
    data: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().split("#", 1)[0].strip()
        if val.startswith(("'", '"')) and val.endswith(("'", '"')):
            val = val[1:-1]
        data[key] = val
    return data


def collect_replay_registry(entries: Dict[str, EntryState]) -> None:
    path = REPO_ROOT / "lottery_api" / "models" / "replay_strategy_registry.py"
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
                in_block = False
                current = []
    for block in blocks:
        sid_m = re.search(r'strategy_id="([^"]+)"', block)
        name_m = re.search(r'strategy_name="([^"]+)"', block)
        status_m = re.search(r'status="([^"]+)"', block)
        lot_m = re.search(r"supported_lottery_types=\[([^\]]+)\]", block)
        if not sid_m:
            continue
        sid = sid_m.group(1)
        name = name_m.group(1) if name_m else sid
        status = status_m.group(1) if status_m else "UNKNOWN"
        if lot_m:
            lottery_raw = lot_m.group(1)
            if "BIG_LOTTO" in lottery_raw:
                lottery = "BIG_LOTTO"
            elif "POWER_LOTTO" in lottery_raw:
                lottery = "POWER_LOTTO"
            elif "DAILY_539" in lottery_raw:
                lottery = "DAILY_539"
            else:
                lottery = "UNSPECIFIED"
        else:
            lottery = "UNSPECIFIED"
        attach(
            entries,
            sid,
            display_name=name,
            source_path=str(path.relative_to(REPO_ROOT)),
            lifecycle=STATUS_MAP.get(status, "UNKNOWN"),
            lottery=lottery,
            historical_source="prediction_runs",
            note="replay_registry",
            rsm_referenced=status in {"ONLINE", "ACTIVE"},
        )


def collect_strategy_packages(entries: Dict[str, EntryState]) -> None:
    strategies_root = REPO_ROOT / "strategies"
    for yaml_path in sorted(strategies_root.glob("*/*/strategy.yaml")):
        data = parse_strategy_yaml(yaml_path)
        parent = yaml_path.parent.parent.name
        folder = yaml_path.parent.name
        lottery = data.get("lottery") or data.get("lottery_type") or infer_lottery_from_text(str(yaml_path))
        if lottery == "BIG_LOTTO":
            prefix = "biglotto"
        elif lottery == "POWER_LOTTO":
            prefix = "powerlotto"
        elif lottery == "DAILY_539":
            prefix = "daily539"
        else:
            prefix = parent
        raw_id = data.get("strategy_id") or f"{folder}"
        sid = canonicalize(raw_id, f"strategies/{parent}/{folder}/strategy.yaml")
        if not data.get("strategy_id"):
            sid = f"{prefix}_{slugify(folder)}"
        display = data.get("name") or data.get("description", "").splitlines()[0] if data.get("description") else sid
        status = (data.get("status") or "UNKNOWN").split()[0].upper()
        lifecycle = STATUS_MAP.get(status, "UNKNOWN")
        historical_source = "simulation_log" if any((yaml_path.parent / n).exists() for n in ["sim_result.json", "performance_log.json", "backtest_report.md", "stat_test.txt"]) else "none"
        attach(
            entries,
            sid,
            display_name=display,
            source_path=str(yaml_path.relative_to(REPO_ROOT)),
            lifecycle=lifecycle,
            lottery=lottery,
            historical_source=historical_source,
            note=f"strategy_package_status:{status}",
            rsm_referenced=lifecycle == "PRODUCTION",
        )
        for sibling in ["sim_result.json", "performance_log.json", "backtest_report.md", "stat_test.txt", "version_tag.txt"]:
            sibling_path = yaml_path.parent / sibling
            if sibling_path.exists():
                attach(entries, sid, source_path=str(sibling_path.relative_to(REPO_ROOT)))


def extract_object_keys(js_text: str, object_name: str) -> List[Tuple[str, str]]:
    # Return list of (key, value) pairs from a simple JS object literal.
    m = re.search(rf"{re.escape(object_name)}\s*=\s*\{{(.*?)\n\s*\}};", js_text, re.S)
    if not m:
        return []
    body = m.group(1)
    pairs = re.findall(r"'([^']+)'\s*:\s*'([^']+)'", body)
    return pairs


def collect_frontend_defs(entries: Dict[str, EntryState]) -> None:
    app_path = REPO_ROOT / "src" / "core" / "App.js"
    engine_path = REPO_ROOT / "src" / "engine" / "PredictionEngine.js"
    app_text = app_path.read_text(encoding="utf-8")
    pairs = extract_object_keys(app_text, "const strategyNames")
    for sid, display in pairs:
        attach(
            entries,
            sid,
            display_name=display,
            source_path=str(app_path.relative_to(REPO_ROOT)),
            lifecycle="EXPERIMENTAL",
            lottery="CROSS_GAME",
            historical_source="none",
            note="frontend_strategy_definition",
        )
        if engine_path.exists():
            attach(entries, sid, source_path=str(engine_path.relative_to(REPO_ROOT)))


def collect_model_methods(entries: Dict[str, EntryState]) -> None:
    model_paths = [
        REPO_ROOT / "lottery_api" / "models" / "unified_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "special_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "fourier_rhythm.py",
        REPO_ROOT / "lottery_api" / "models" / "orthogonal_2bet.py",
        REPO_ROOT / "lottery_api" / "models" / "dual_bet_strategy.py",
        REPO_ROOT / "lottery_api" / "models" / "bayesian_ensemble.py",
        REPO_ROOT / "lottery_api" / "models" / "selective_ensemble.py",
        REPO_ROOT / "lottery_api" / "models" / "constraint_filter_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "arima_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "attention_lstm_torch.py",
        REPO_ROOT / "lottery_api" / "models" / "dynamic_ensemble_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "optimized_bayesian_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "advanced_bayesian_analyzer.py",
        REPO_ROOT / "lottery_api" / "models" / "meta_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "ensemble_predictor.py",
        REPO_ROOT / "lottery_api" / "models" / "auto_optimizer.py",
        REPO_ROOT / "lottery_api" / "models" / "big_lotto_optimizer.py",
        REPO_ROOT / "lottery_api" / "models" / "biglotto_tme_optimizer.py",
        REPO_ROOT / "lottery_api" / "models" / "regime_monitor.py",
    ]
    for path in model_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(REPO_ROOT))
        attach(entries, canonicalize(path.stem, rel), source_path=rel, lifecycle="EXPERIMENTAL", lottery=infer_lottery_from_text(rel), historical_source="none")
        # function/method names ending with _predict are strategy-like entry points.
        for fn in sorted(set(re.findall(r"def\s+([A-Za-z0-9_]+_predict)\s*\(", text))):
            sid = fn[:-8] if fn.endswith("_predict") else fn
            if not is_strategy_like(sid):
                continue
            attach(
                entries,
                canonicalize(sid, rel),
                display_name=sid,
                source_path=rel,
                lifecycle="EXPERIMENTAL",
                lottery=infer_lottery_from_text(rel + " " + sid),
                historical_source="none",
                note=f"model_method:{fn}",
            )
        # explicit strategy_id / strategy_name strings
        for sid in re.findall(r"strategy_id\s*=\s*['\"]([^'\"]+)['\"]", text):
            if is_strategy_like(sid) or sid in ALIAS_TO_CANONICAL:
                attach(entries, canonicalize(sid, rel), display_name=sid, source_path=rel, lifecycle="EXPERIMENTAL", lottery=infer_lottery_from_text(rel + " " + sid), note="model_strategy_id")
        for sid in re.findall(r"strategy_name\s*=\s*['\"]([^'\"]+)['\"]", text):
            if is_strategy_like(sid) or sid in ALIAS_TO_CANONICAL:
                attach(entries, canonicalize(sid, rel), display_name=sid, source_path=rel, lifecycle="EXPERIMENTAL", lottery=infer_lottery_from_text(rel + " " + sid), note="model_strategy_name")


def collect_rejected(entries: Dict[str, EntryState]) -> Set[str]:
    rejected_root = REPO_ROOT / "rejected"
    rejected_ids: Set[str] = set()
    for path in sorted(rejected_root.glob("*.json")):
        if path.name == "README.md":
            continue
        data = open_json(path)
        raw_id = path.stem
        sid = canonicalize(raw_id, f"rejected/{path.name}")
        rejected_ids.add(sid)
        display = data.get("strategy") or data.get("reason") or raw_id
        lottery = infer_lottery_from_text(raw_id + " " + json.dumps(data, ensure_ascii=False))
        attach(
            entries,
            sid,
            display_name=display,
            source_path=str(path.relative_to(REPO_ROOT)),
            lifecycle="REJECTED",
            lottery=lottery,
            historical_source="rejected_json",
            note="rejected_artifact",
        )
        # Track a more human-readable alias if present.
        if isinstance(display, str) and display != raw_id:
            alias_sid = canonicalize(display, f"rejected/{path.name}")
            if alias_sid != sid:
                attach(
                    entries,
                    alias_sid,
                    display_name=display,
                    source_path=str(path.relative_to(REPO_ROOT)),
                    lifecycle="REJECTED",
                    lottery=lottery,
                    historical_source="rejected_json",
                    note=f"possible_duplicate_of:{sid}",
                    alias=raw_id,
                )
                rejected_ids.add(alias_sid)
    return rejected_ids


def collect_rsm(entries: Dict[str, EntryState]) -> Set[str]:
    rsm_ids: Set[str] = set()
    for path in sorted((REPO_ROOT / "data").glob("rolling_monitor_*.json")):
        try:
            data = open_json(path)
        except Exception:
            continue
        records = data.get("records", {})
        if not isinstance(records, dict):
            continue
        for raw_id in sorted(records.keys()):
            sid = canonicalize(raw_id, str(path.relative_to(REPO_ROOT)))
            rsm_ids.add(sid)
            lottery = data.get("lottery_type") or infer_lottery_from_text(path.name)
            attach(
                entries,
                sid,
                display_name=raw_id,
                source_path=str(path.relative_to(REPO_ROOT)),
                lifecycle="PRODUCTION",
                lottery=lottery,
                historical_source="prediction_runs",
                note="rsm_current_strategy",
                rsm_referenced=True,
            )
    return rsm_ids


def parse_lesson_lines(text: str, source_label: str, entries: Dict[str, EntryState]) -> None:
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        ref = f"{source_label}:L{i}"
        # Explicit backticked ids and title snippets.
        tokens = set(re.findall(r"`([^`]+)`", line))
        # Add likely strategy fragments from quoted text and bare tokens.
        for m in re.findall(r"([A-Za-z][A-Za-z0-9_+\-]+(?: [A-Za-z][A-Za-z0-9_+\-]+){0,4})", line):
            if len(m) >= 3 and (is_strategy_like(m) or m in LESSON_ALIAS_HINTS):
                tokens.add(m)
        # Focus on the requested L1-L107 region, but allow later lines for lifecycle evidence.
        if i <= 107 or any(key in line for key in ["REJECT", "WATCH", "OBSERVE", "PROVISIONAL", "OFFLINE", "RETIRED", "生產策略", "production", "現役"]):
            for tok in tokens:
                if not tok or tok in {"M3+", "M2+", "OOS", "Edge", "p"}:
                    continue
                sid = canonicalize(tok, source_label)
                if not is_strategy_like(tok) and sid not in LESSON_ALIAS_HINTS.values():
                    continue
                lifecycle = None
                upper = line.upper()
                if "FAST_REJECT" in upper or "REJECT" in upper:
                    lifecycle = "REJECTED"
                elif "WATCH" in upper or "OBSERVE" in upper:
                    lifecycle = "WATCHING"
                elif "PROVISIONAL" in upper:
                    lifecycle = "PROVISIONAL"
                elif "OFFLINE" in upper or "RETIRED" in upper or "DEPRECATED" in upper:
                    lifecycle = "OFFLINE"
                elif "生產策略" in line or "production" in line.lower() or "現役" in line:
                    lifecycle = "PRODUCTION"
                lottery = infer_lottery_from_text(line)
                display = tok
                attach(
                    entries,
                    sid,
                    display_name=display,
                    source_path=ref,
                    lifecycle=lifecycle,
                    lottery=lottery,
                    historical_source="none",
                    lesson_ref=f"L{i}",
                    note=f"lesson_reference:{source_label}:L{i}",
                )


def collect_lessons_and_memory(entries: Dict[str, EntryState]) -> None:
    for rel in ["MEMORY.md", "memory/lessons.md", "memory/todo.md"]:
        path = REPO_ROOT / rel
        if path.exists():
            parse_lesson_lines(path.read_text(encoding="utf-8"), rel, entries)


def collect_db_names(entries: Dict[str, EntryState]) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    replay_ids: Set[str] = set()
    pred_run_ids: Set[str] = set()
    pred_item_ids: Set[str] = set()
    db_alias_names: Set[str] = set()

    # strategy_prediction_replays.strategy_id
    for row in cur.execute("SELECT DISTINCT strategy_id FROM strategy_prediction_replays WHERE strategy_id IS NOT NULL"):
        sid = row["strategy_id"]
        replay_ids.add(sid)
        attach(
            entries,
            canonicalize(sid, "lottery_v2.db::strategy_prediction_replays"),
            display_name=sid,
            source_path="lottery_api/data/lottery_v2.db::strategy_prediction_replays",
            lifecycle="PRODUCTION",
            lottery="UNSPECIFIED",
            historical_source="prediction_runs",
            note="db_replay_row",
        )

    # prediction_runs.strategy_name
    for row in cur.execute("SELECT DISTINCT strategy_name FROM prediction_runs WHERE strategy_name IS NOT NULL"):
        raw = row["strategy_name"]
        if raw in {"MULTI_STRATEGY", "Coordinator-Direct (7 agents)", "Coordinator-Direct (6 agents)"}:
            continue
        sid = canonicalize(raw, "lottery_v2.db::prediction_runs")
        pred_run_ids.add(sid)
        db_alias_names.add(raw)
        attach(
            entries,
            sid,
            display_name=raw,
            source_path="lottery_api/data/lottery_v2.db::prediction_runs",
            lifecycle="PRODUCTION" if raw in ALIAS_TO_CANONICAL.values() or is_strategy_like(raw) else "UNKNOWN",
            lottery="UNSPECIFIED",
            historical_source="prediction_runs",
            note="db_prediction_run",
        )

    # prediction_items.strategy_name
    for row in cur.execute("SELECT DISTINCT strategy_name FROM prediction_items WHERE strategy_name IS NOT NULL"):
        raw = row["strategy_name"]
        if raw in {"MULTI_STRATEGY", "Coordinator-Direct (7 agents)", "Coordinator-Direct (6 agents)"}:
            continue
        sid = canonicalize(raw, "lottery_v2.db::prediction_items")
        pred_item_ids.add(sid)
        db_alias_names.add(raw)
        attach(
            entries,
            sid,
            display_name=raw,
            source_path="lottery_api/data/lottery_v2.db::prediction_items",
            lifecycle="UNKNOWN",
            lottery="UNSPECIFIED",
            historical_source="prediction_runs",
            note="db_prediction_item",
        )
    conn.close()
    return replay_ids, pred_run_ids, pred_item_ids, db_alias_names


def collect_tools(entries: Dict[str, EntryState]) -> None:
    root = REPO_ROOT / "tools"
    allowed_suffixes = {".py", ".js", ".cjs", ".json", ".md", ".txt"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in allowed_suffixes:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        name = path.name.lower()
        if not any(
            name.startswith(prefix)
            for prefix in [
                "predict_",
                "backtest_",
                "optimize_",
                "generate_",
                "audit_",
                "verify_",
                "review_",
                "discover_",
                "power_",
                "biglotto_",
                "p3_",
            ]
        ) and "strategy" not in name and "bet" not in name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Explicit strategy labels
        string_hits = set()
        for pat in [
            r"strategy_id\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"strategy_name\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"name\s*:\s*['\"]([^'\"]+)['\"]",
            r"name\s*=\s*['\"]([^'\"]+)['\"]",
        ]:
            string_hits.update(re.findall(pat, text))

        # Function / class derived ids.
        fn_hits = set(re.findall(r"def\s+([A-Za-z0-9_]+)\s*\(", text))
        class_hits = set(re.findall(r"class\s+([A-Za-z0-9_]+Strategy)\b", text))

        for raw in sorted(string_hits | fn_hits | class_hits):
            if not is_strategy_like(raw) and raw not in ALIAS_TO_CANONICAL and raw not in LESSON_ALIAS_HINTS:
                continue
            sid = canonicalize(raw, rel)
            lifecycle = "EXPERIMENTAL"
            if "rejected" in text.lower():
                lifecycle = "REJECTED"
            elif "provisional" in text.lower():
                lifecycle = "PROVISIONAL"
            elif "watch" in text.lower() or "observe" in text.lower():
                lifecycle = "WATCHING"
            elif "active" in text.lower() or "production" in text.lower() or "現役" in text:
                lifecycle = "PRODUCTION"
            attach(
                entries,
                sid,
                display_name=raw,
                source_path=rel,
                lifecycle=lifecycle,
                lottery=infer_lottery_from_text(rel + " " + raw + " " + text[:3000]),
                historical_source="simulation_log" if any(k in name for k in ["backtest", "sim", "benchmark"]) else "none",
                note="tools_candidate",
            )


def derive_summary(entries: Dict[str, EntryState], replay_ids: Set[str], pred_run_ids: Set[str], pred_item_ids: Set[str], rejected_ids: Set[str]) -> Tuple[List[Dict], Dict[str, int], Dict[str, int], Dict[str, int]]:
    out = []
    lifecycle_counts = Counter()
    lottery_counts = Counter()
    gaps = {
        "strategies_with_replay_rows": 0,
        "strategies_without_replay_rows": 0,
        "strategies_with_historical_records_but_no_replay": 0,
        "strategies_with_no_records_anywhere": 0,
    }

    for sid, entry in sorted(entries.items(), key=lambda kv: (kv[1].lifecycle_votes[:1] or ["UNKNOWN"], kv[1].lottery_votes[:1] or ["UNSPECIFIED"], kv[0])):
        if not entry.source_paths:
            continue
        lifecycle = pick_lifecycle(entry.lifecycle_votes, list(entry.source_paths))
        lottery = pick_lottery(entry.lottery_votes, sid, list(entry.source_paths))
        historical_source = infer_historical_source(entry.source_paths, sid, replay_ids, pred_run_ids, pred_item_ids, rejected_ids)
        has_hist = historical_source != "none"
        replay_row = sid in replay_ids
        if replay_row:
            gaps["strategies_with_replay_rows"] += 1
        else:
            gaps["strategies_without_replay_rows"] += 1
            if has_hist:
                gaps["strategies_with_historical_records_but_no_replay"] += 1
            else:
                gaps["strategies_with_no_records_anywhere"] += 1

        notes = sorted(entry.notes)
        if lifecycle == "UNKNOWN" and not notes:
            notes = ["no lifecycle evidence"]
        if len(entry.source_paths) > 1:
            notes.append(f"source_count:{len(entry.source_paths)}")
        if entry.aliases:
            notes.append("aliases:" + ",".join(sorted(entry.aliases)))
        if sid in pred_run_ids or sid in pred_item_ids:
            notes.append("db_history_present")

        record = {
            "strategy_id": sid,
            "display_name": entry.display_name,
            "source_paths": sorted(entry.source_paths),
            "lifecycle_state": lifecycle,
            "lottery_type": lottery,
            "has_historical_predictions": has_hist,
            "historical_record_source": historical_source,
            "lessons_reference": sorted(entry.lessons_refs),
            "rsm_referenced": bool(entry.rsm_referenced or lifecycle == "PRODUCTION"),
            "notes": "; ".join(notes) if notes else "",
        }
        out.append(record)
        lifecycle_counts[lifecycle] += 1
        lottery_counts[lottery] += 1

    return out, dict(lifecycle_counts), dict(lottery_counts), gaps


def build_report(payload: Dict) -> str:
    lines: List[str] = []
    lines.append("# P0 Strategy Universe Inventory Report - 20260517")
    lines.append("")
    lines.append(f"Generated at: `{payload['generated_at']}`")
    lines.append("")
    lines.append("## Final Classification")
    lines.append("P0_STRATEGY_UNIVERSE_INVENTORY_COMPLETED")
    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Total strategies: **{payload['total_count']}**")
    lines.append("- Lifecycle breakdown:")
    for key in LIFECYCLE_ORDER:
        lines.append(f"  - {key}: {payload['by_lifecycle'].get(key, 0)}")
    lines.append("- Lottery breakdown:")
    for key in LOTTERY_ORDER:
        lines.append(f"  - {key}: {payload['by_lottery'].get(key, 0)}")
    lines.append("")
    lines.append("## Coverage Gap Summary")
    gap = payload["coverage_gap_analysis"]
    lines.append(f"- Strategies with replay rows: {gap['strategies_with_replay_rows']}")
    lines.append(f"- Strategies without replay rows: {gap['strategies_without_replay_rows']}")
    lines.append(f"- Strategies with historical records but no replay: {gap['strategies_with_historical_records_but_no_replay']}")
    lines.append(f"- Strategies with no records anywhere: {gap['strategies_with_no_records_anywhere']}")
    lines.append("")
    lines.append("## Top 10 Ambiguous Classifications")
    unknowns = [s for s in payload["strategies"] if s["lifecycle_state"] == "UNKNOWN"]
    if not unknowns:
        lines.append("- None")
    else:
        for item in unknowns[:10]:
            lines.append(
                f"- `{item['strategy_id']}` | {item['display_name']} | {item['lottery_type']} | notes: {item['notes'] or 'none'}"
            )
    lines.append("")
    lines.append("## Safety Confirmation")
    lines.append("- No DB writes were performed.")
    lines.append("- No draw execution/import was performed.")
    lines.append("- No prediction_runs / prediction_items / replay rows were modified.")
    lines.append("- Inventory generation is read-only and classification-only.")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This inventory uses conservative deduplication. Unclear aliases remain separate and are marked in `notes`.")
    lines.append("- `UNKNOWN` is reserved for entries without enough lifecycle evidence.")
    lines.append("- Production evidence prioritizes RSM / MEMORY / replay registry / current monitor files.")
    return "\n".join(lines) + "\n"


def main() -> int:
    entries: Dict[str, EntryState] = {}

    collect_replay_registry(entries)
    collect_strategy_packages(entries)
    collect_frontend_defs(entries)
    collect_model_methods(entries)
    rejected_ids = collect_rejected(entries)
    rsm_ids = collect_rsm(entries)
    collect_lessons_and_memory(entries)
    collect_tools(entries)
    replay_ids, pred_run_ids, pred_item_ids, _db_alias_names = collect_db_names(entries)

    # Re-attach RSM source evidence to known production entries from memory/replay registry.
    for sid in rsm_ids:
        if sid in entries:
            entries[sid].rsm_referenced = True

    strategies, by_lifecycle, by_lottery, coverage = derive_summary(
        entries, replay_ids, pred_run_ids, pred_item_ids, rejected_ids
    )

    total_count = len(strategies)
    assert total_count == sum(by_lifecycle.get(k, 0) for k in LIFECYCLE_ORDER), "lifecycle sum mismatch"
    assert total_count == sum(by_lottery.get(k, 0) for k in LOTTERY_ORDER), "lottery sum mismatch"
    assert all("strategy_id" in s and "source_paths" in s and s["source_paths"] for s in strategies), "missing required strategy fields"
    for item in strategies:
        for field in item.values():
            if isinstance(field, str):
                assert field not in {"TBD", "TODO", "null"}, f"forbidden placeholder in {item['strategy_id']}"

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_count": total_count,
        "by_lifecycle": {k: by_lifecycle.get(k, 0) for k in LIFECYCLE_ORDER},
        "by_lottery": {k: by_lottery.get(k, 0) for k in LOTTERY_ORDER},
        "strategies": sorted(strategies, key=lambda s: (LIFECYCLE_ORDER.index(s["lifecycle_state"]) if s["lifecycle_state"] in LIFECYCLE_ORDER else 999, LOTTERY_ORDER.index(s["lottery_type"]) if s["lottery_type"] in LOTTERY_ORDER else 999, s["strategy_id"])),
        "coverage_gap_analysis": coverage,
    }
    payload["total_count"] = len(payload["strategies"])

    # Final consistency guard.
    assert payload["total_count"] == sum(payload["by_lifecycle"].values()), "total/lifecycle mismatch"
    assert payload["total_count"] == sum(payload["by_lottery"].values()), "total/lottery mismatch"
    for row in payload["strategies"]:
        assert row["strategy_id"] and row["source_paths"], f"invalid strategy row: {row}"
        for key in ("display_name", "lifecycle_state", "lottery_type", "historical_record_source", "notes"):
            assert key in row, f"missing field {key} in {row['strategy_id']}"
            assert row[key] != "TBD" and row[key] != "TODO", f"placeholder found in {row['strategy_id']}"
        if row["lessons_reference"] is None:
            row["lessons_reference"] = []

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(build_report(payload), encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "total_count": payload["total_count"],
        "by_lifecycle": payload["by_lifecycle"],
        "by_lottery": payload["by_lottery"],
        "coverage_gap_analysis": payload["coverage_gap_analysis"],
        "output_json": str(OUT_JSON.relative_to(REPO_ROOT)),
        "output_md": str(OUT_MD.relative_to(REPO_ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
