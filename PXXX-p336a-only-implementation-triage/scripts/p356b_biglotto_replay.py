#!/usr/bin/env python3
"""P356B replay-eligible manifest and Big Lotto in-memory replay.

Safety contract:
  - reads P356A artifacts from this isolated worktree;
  - opens the canonical DB only through SQLite immutable/read-only URI;
  - writes only P356B artifacts under artifacts/;
  - does not call project replay writers or mutate strategy lifecycle state.
"""
from __future__ import annotations

import csv
import hashlib
import importlib
import json
import math
import sqlite3
import subprocess
import sys
import types
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_REPO = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew")
CANONICAL_DB = CANONICAL_REPO / "lottery_api" / "data" / "lottery_v2.db"
ARTIFACT_DIR = REPO_ROOT / "artifacts"
INVENTORY_CSV = ARTIFACT_DIR / "P356A_strategy_inventory_all.csv"
ID_REUSE_MD = ARTIFACT_DIR / "P356A_strategy_id_reuse_cases.md"

WINDOWS = [30, 150, 750, 1500]
BIG_LOTTO_POOL = 49
BIG_LOTTO_PICK = 6
M3_PLUS_SINGLE_BASELINE = sum(
    math.comb(BIG_LOTTO_PICK, k) * math.comb(BIG_LOTTO_POOL - BIG_LOTTO_PICK, BIG_LOTTO_PICK - k)
    for k in range(3, BIG_LOTTO_PICK + 1)
) / math.comb(BIG_LOTTO_POOL, BIG_LOTTO_PICK)

SEED_BIG_LOTTO = {
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
}

P356A_REQUIRED = {
    "P356A_phase0_evidence.md",
    "P356A_strategy_inventory_all.csv",
    "P356A_strategy_inventory_all.json",
    "P356A_replay_skipped_strategies.md",
    "P356A_strategy_id_reuse_cases.md",
    "P356A_inventory_summary.md",
    "P356A_validation_log.md",
}


class P356BStop(RuntimeError):
    """Fail-closed task stop."""


def run(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.stdout.strip()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def connect_immutable(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def db_metrics(db_path: Path) -> dict[str, Any]:
    with connect_immutable(db_path) as conn:
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        strategy_replay_runs_rows = (
            conn.execute('SELECT COUNT(*) FROM "strategy_replay_runs"').fetchone()[0]
            if "strategy_replay_runs" in tables
            else 0
        )
        strategy_prediction_replays_rows = (
            conn.execute('SELECT COUNT(*) FROM "strategy_prediction_replays"').fetchone()[0]
            if "strategy_prediction_replays" in tables
            else 0
        )
        prediction_ids = set()
        if "strategy_prediction_replays" in tables:
            prediction_ids = {
                str(r[0])
                for r in conn.execute(
                    '''
                    SELECT DISTINCT strategy_id
                    FROM strategy_prediction_replays
                    WHERE strategy_id IS NOT NULL AND TRIM(strategy_id) != ''
                    '''
                )
            }
        scope_tokens = set()
        if "strategy_replay_runs" in tables:
            for (scope,) in conn.execute(
                '''
                SELECT DISTINCT strategy_scope
                FROM strategy_replay_runs
                WHERE strategy_scope IS NOT NULL AND TRIM(strategy_scope) != ''
                '''
            ):
                scope_text = str(scope)
                scope_tokens.add(scope_text)
                scope_tokens.update(part.strip() for part in scope_text.split(",") if part.strip())
        p356a_broad_ids = p356a_db_strategy_ids(db_path)
        return {
            "db_path": str(db_path),
            "db_sha256": sha256_path(db_path),
            "draw_rows": conn.execute('SELECT COUNT(*) FROM "draws"').fetchone()[0],
            "strategy_prediction_replays_rows": strategy_prediction_replays_rows,
            "strategy_replay_runs_rows": strategy_replay_runs_rows,
            "distinct_prediction_strategy_ids": sorted(prediction_ids),
            "distinct_prediction_strategy_id_count": len(prediction_ids),
            "distinct_scope_expanded_strategy_ids": sorted(prediction_ids | scope_tokens),
            "distinct_scope_expanded_strategy_id_count": len(prediction_ids | scope_tokens),
            "distinct_broad_db_strategy_ids": p356a_broad_ids,
            "distinct_broad_db_strategy_id_count": len(p356a_broad_ids),
        }


def p356a_db_strategy_ids(db_path: Path) -> list[str]:
    """Reuse P356A's DB evidence classifier for the 35-vs-42 reconciliation."""
    import importlib.util

    module_name = "_p356a_all_strategy_inventory_for_p356b"
    module_path = REPO_ROOT / "scripts" / "p356a_all_strategy_inventory.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise P356BStop("Unable to load P356A inventory script for DB reconciliation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    info, _sources = module.db_introspection(db_path)
    return list(info["distinct_db_strategy_ids"])


def load_inventory() -> list[dict[str, str]]:
    with INVENTORY_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def current_source_exists(row: dict[str, str]) -> bool:
    if row.get("current_exists") != "True":
        return False
    entrypoint = row.get("callable_entrypoint", "")
    if entrypoint:
        module_path = entrypoint.rsplit(".", 1)[0].replace(".", "/") + ".py"
        if (REPO_ROOT / module_path).exists():
            return True
    return any((REPO_ROOT / p.strip()).exists() for p in row.get("source_paths", "").split(";") if p.strip())


def import_callable(entrypoint: str) -> Callable[..., Any] | None:
    if not entrypoint or "." not in entrypoint:
        return None
    install_scipy_fft_fallback()
    module_name, function_name = entrypoint.rsplit(".", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    func = getattr(module, function_name, None)
    return func if callable(func) else None


def install_scipy_fft_fallback() -> None:
    """Provide scipy.fft-compatible names when only numpy is available.

    Three legacy Big Lotto strategy modules import only
    ``from scipy.fft import fft, fftfreq``. The bundled runtime has numpy but not
    scipy, and numpy.fft exposes compatible functions for this replay use.
    """
    if "scipy.fft" in sys.modules:
        return
    try:
        import scipy.fft  # type: ignore  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    import numpy as np  # type: ignore

    scipy_module = sys.modules.get("scipy") or types.ModuleType("scipy")
    fft_module = types.ModuleType("scipy.fft")
    fft_module.fft = np.fft.fft
    fft_module.fftfreq = np.fft.fftfreq
    scipy_module.fft = fft_module
    sys.modules["scipy"] = scipy_module
    sys.modules["scipy.fft"] = fft_module


def exclusion_reason(row: dict[str, str], id_reuse_ids: set[str]) -> str:
    status = row.get("executable_status", "")
    strategy_id = row.get("strategy_id", "")
    if row.get("game") != "BIG_LOTTO":
        return "NON_BIG_LOTTO"
    if status == "ID_REUSED" or strategy_id in id_reuse_ids:
        return "ID_REUSED"
    if status == "MISSING_CODE":
        return "MISSING_CODE"
    if status == "DOC_ONLY":
        return "DOC_ONLY"
    if status == "DB_ONLY":
        return "DB_ONLY"
    if status == "UNKNOWN":
        return "UNKNOWN"
    if status != "EXECUTABLE":
        return status or "NON_EXECUTABLE"
    if not row.get("callable_entrypoint"):
        return "MISSING_CALLABLE_ENTRYPOINT"
    if not current_source_exists(row):
        return "CURRENT_SOURCE_MISSING"
    if import_callable(row["callable_entrypoint"]) is None:
        return "CALLABLE_IMPORT_FAILED"
    return ""


def load_id_reuse_ids() -> set[str]:
    text = ID_REUSE_MD.read_text(encoding="utf-8") if ID_REUSE_MD.exists() else ""
    ids: set[str] = set()
    for line in text.splitlines():
        if line.startswith("| ") and not line.startswith("| ---"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if parts and parts[0] != "strategy_id":
                ids.add(parts[0])
    return ids


def build_manifest(inventory: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    id_reuse_ids = load_id_reuse_ids()
    manifest: list[dict[str, str]] = []
    eligible: list[dict[str, str]] = []
    for row in inventory:
        if row.get("game") != "BIG_LOTTO":
            continue
        reason = exclusion_reason(row, id_reuse_ids)
        item = {
            "strategy_id": row["strategy_id"],
            "lineage_id": row["lineage_id"],
            "game": row["game"],
            "bet_count": row["bet_count"],
            "current_status": row["current_status"],
            "executable_status": row["executable_status"],
            "callable_entrypoint": row["callable_entrypoint"],
            "source_paths": row["source_paths"],
            "implementation_signature_hash": row["implementation_signature_hash"],
            "eligibility_status": "EXCLUDED" if reason else "ELIGIBLE",
            "exclusion_reason": reason,
            "replay_notes": "Eligible for P356B in-memory replay." if not reason else f"Excluded: {reason}.",
        }
        manifest.append(item)
        if not reason:
            eligible.append(item)
    return manifest, eligible


def parse_numbers(raw: str) -> list[int]:
    value = json.loads(raw)
    return [int(n) for n in value]


def load_biglotto_draws(db_path: Path) -> list[dict[str, Any]]:
    with connect_immutable(db_path) as conn:
        rows = conn.execute(
            '''
            SELECT draw, date, numbers, special
            FROM draws
            WHERE lottery_type='BIG_LOTTO'
            ORDER BY date ASC, CAST(draw AS INTEGER) ASC, draw ASC
            '''
        ).fetchall()
    return [
        {
            "draw": str(row["draw"]),
            "date": row["date"],
            "numbers": parse_numbers(row["numbers"]),
            "special": row["special"] or 0,
        }
        for row in rows
    ]


def canonical_bet(raw: Any) -> list[int]:
    if not isinstance(raw, (list, tuple)) or len(raw) != BIG_LOTTO_PICK:
        raise ValueError(f"bet must contain six numbers: {raw!r}")
    bet = sorted(int(n) for n in raw)
    if len(set(bet)) != BIG_LOTTO_PICK:
        raise ValueError(f"bet has duplicate numbers: {bet!r}")
    if any(n < 1 or n > BIG_LOTTO_POOL for n in bet):
        raise ValueError(f"bet has out-of-range numbers: {bet!r}")
    return bet


def normalize_bets(raw: Any, requested_bet_count: str) -> list[list[int]]:
    if isinstance(raw, (list, tuple)) and raw and all(isinstance(n, int) for n in raw):
        bets = [canonical_bet(raw)]
    elif isinstance(raw, (list, tuple)) and raw and all(isinstance(b, (list, tuple)) for b in raw):
        bets = [canonical_bet(b) for b in raw]
    else:
        raise ValueError(f"unsupported callable output shape: {raw!r}")
    if requested_bet_count.isdigit():
        expected = int(requested_bet_count)
        if len(bets) > expected:
            bets = bets[:expected]
    return bets


def baseline_for_bet_count(bet_count: int) -> float:
    return 1 - ((1 - M3_PLUS_SINGLE_BASELINE) ** bet_count)


def replay_strategy(item: dict[str, str], draws: list[dict[str, Any]]) -> list[dict[str, Any]]:
    func = import_callable(item["callable_entrypoint"])
    if func is None:
        raise P356BStop(f"missing callable during replay: {item['strategy_id']}")
    max_window = max(WINDOWS)
    if len(draws) <= max_window:
        raise P356BStop(f"not enough BIG_LOTTO draws for {max_window}-period replay")
    start = len(draws) - max_window
    outcomes: list[dict[str, Any]] = []
    for idx in range(start, len(draws)):
        history = draws[:idx]
        target = set(draws[idx]["numbers"])
        raw = func(history)
        bets = normalize_bets(raw, item["bet_count"])
        best_hit = max(len(set(bet) & target) for bet in bets)
        outcomes.append(
            {
                "hit": best_hit >= 3,
                "best_hit": best_hit,
                "bet_count": len(bets),
            }
        )
    rows: list[dict[str, Any]] = []
    for window in WINDOWS:
        subset = outcomes[-window:]
        total = len(subset)
        effective_bet_counts = {o["bet_count"] for o in subset}
        if len(effective_bet_counts) != 1:
            raise P356BStop(f"non-stable bet count for {item['strategy_id']}: {sorted(effective_bet_counts)}")
        bet_count = effective_bet_counts.pop()
        hit_count = sum(1 for o in subset if o["hit"])
        hit_rate = hit_count / total if total else 0.0
        baseline = baseline_for_bet_count(bet_count)
        rows.append(
            {
                "strategy_id": item["strategy_id"],
                "lineage_id": item["lineage_id"],
                "current_status": item["current_status"],
                "bet_count": bet_count,
                "window": window,
                "total_periods": total,
                "hit_count": hit_count,
                "hit_rate": hit_rate,
                "baseline": baseline,
                "edge": hit_rate - baseline,
                "replay_status": "COMPLETED",
                "notes": (
                    "M3+ coverage replay; history is draws strictly before target; "
                    "special number not evaluated."
                ),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        rendered = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, float):
                value = f"{value:.6f}"
            rendered.append(str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    return lines


def write_manifest_md(manifest: list[dict[str, str]], eligible: list[dict[str, str]]) -> None:
    excluded = [r for r in manifest if r["eligibility_status"] == "EXCLUDED"]
    reason_counts = Counter(r["exclusion_reason"] for r in excluded)
    lines = [
        "# P356B Replay-Eligible Manifest",
        "",
        f"- Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Big Lotto lineages evaluated: `{len(manifest)}`",
        f"- Eligible lineages: `{len(eligible)}`",
        f"- Excluded lineages: `{len(excluded)}`",
        "",
        "## Exclusions By Reason",
        "```json",
        json.dumps(dict(sorted(reason_counts.items())), indent=2, sort_keys=True),
        "```",
        "",
        "## Eligible Lineages",
    ]
    lines.extend(md_table(eligible, ["strategy_id", "lineage_id", "current_status", "bet_count", "callable_entrypoint"]))
    lines.extend(["", "## Explicit Guarded Exclusions"])
    explicit = [
        r
        for r in manifest
        if r["strategy_id"]
        in {
            "biglotto_ts3_acb_4bet",
            "ts3_acb_4bet_biglotto",
            "bet2_fourier_expansion_biglotto",
            "biglotto_ts3_markov_freq_5bet",
            "ts3_markov_freq_5bet_biglotto",
        }
    ]
    lines.extend(md_table(explicit, ["strategy_id", "lineage_id", "executable_status", "eligibility_status", "exclusion_reason"]))
    (ARTIFACT_DIR / "P356B_replay_eligible_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_replay_md(
    manifest: list[dict[str, str]],
    eligible: list[dict[str, str]],
    replay_rows: list[dict[str, Any]],
) -> None:
    excluded = [r for r in manifest if r["eligibility_status"] == "EXCLUDED"]
    reason_counts = Counter(r["exclusion_reason"] for r in excluded)
    rank_1500 = sorted(
        [r for r in replay_rows if int(r["window"]) == 1500],
        key=lambda r: (-float(r["edge"]), r["strategy_id"]),
    )
    lines = [
        "# P356B Big Lotto Replay 30/150/750/1500",
        "",
        f"- Eligible strategy count: `{len(eligible)}`",
        f"- Excluded Big Lotto lineage count: `{len(excluded)}`",
        "- Warning: coverage Edge is not governance approval and not betting advice.",
        "- Replay mode: in-memory only; canonical DB was opened read-only/immutable and was not written.",
        "",
        "## Skipped / Excluded By Reason",
        "```json",
        json.dumps(dict(sorted(reason_counts.items())), indent=2, sort_keys=True),
        "```",
        "",
        "## Big Lotto Ranking By 1500p Edge",
    ]
    lines.extend(md_table(rank_1500, ["strategy_id", "lineage_id", "current_status", "bet_count", "hit_rate", "baseline", "edge"]))
    for window in WINDOWS:
        lines.extend(["", f"## {window}p Table"])
        rows = sorted([r for r in replay_rows if int(r["window"]) == window], key=lambda r: (-float(r["edge"]), r["strategy_id"]))
        lines.extend(md_table(rows, ["strategy_id", "current_status", "bet_count", "total_periods", "hit_count", "hit_rate", "baseline", "edge", "replay_status"]))
    (ARTIFACT_DIR / "P356B_biglotto_replay_30_150_750_1500.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_validation_log(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    manifest: list[dict[str, str]],
    eligible: list[dict[str, str]],
    replay_rows: list[dict[str, Any]],
    phase0: dict[str, Any],
    validation: dict[str, Any],
) -> None:
    excluded = [r for r in manifest if r["eligibility_status"] == "EXCLUDED"]
    rows_by_strategy = Counter(r["strategy_id"] for r in replay_rows)
    lines = [
        "# P356B Validation Log",
        "",
        "## Phase 0 Safety Re-check",
        f"- cwd: `{phase0['cwd']}`",
        f"- branch: `{phase0['branch']}`",
        f"- HEAD: `{phase0['head']}`",
        "- git status before:",
        "```text",
        phase0["git_status_before"],
        "```",
        f"- P356A artifacts exist: `{phase0['p356a_artifacts_exist']}`",
        f"- P356A script/test exist: `{phase0['p356a_script_test_exist']}`",
        f"- canonical repo separate: `{CANONICAL_REPO}`",
        f"- immutable DB URI: `file:{CANONICAL_DB}?mode=ro&immutable=1`",
        "",
        "## DB Before / After",
        f"- SHA before: `{before['db_sha256']}`",
        f"- SHA after: `{after['db_sha256']}`",
        f"- Draw rows before/after: `{before['draw_rows']}` / `{after['draw_rows']}`",
        f"- Replay rows before/after: `{before['strategy_prediction_replays_rows']}` / `{after['strategy_prediction_replays_rows']}`",
        f"- Replay runs before/after: `{before['strategy_replay_runs_rows']}` / `{after['strategy_replay_runs_rows']}`",
        f"- Distinct strategy IDs in strategy_prediction_replays: `{before['distinct_prediction_strategy_id_count']}`",
        f"- Broad P356A DB strategy-like IDs: `{before['distinct_broad_db_strategy_id_count']}`",
        "",
        "## Distinct Strategy ID Reconciliation",
        "- The value `35` is the direct count of `strategy_prediction_replays.strategy_id`.",
        "- The value `42` from P356A is the broader strategy-like DB evidence set, which also includes `strategy_replay_runs.strategy_scope` tokens and comma-joined scope labels.",
        "- They are different definitions, not a data mutation.",
        "",
        "## Artifact Guards",
        f"- Big Lotto lineages in manifest: `{len(manifest)}`",
        f"- Eligible lineages: `{len(eligible)}`",
        f"- Excluded lineages: `{len(excluded)}`",
        f"- Every eligible strategy has rows for all windows: `{all(rows_by_strategy[e['strategy_id']] == len(WINDOWS) for e in eligible)}`",
        f"- Every excluded Big Lotto lineage has exclusion reason: `{all(r['exclusion_reason'] for r in excluded)}`",
        f"- Known Big Lotto seed list fully accounted for: `{SEED_BIG_LOTTO.issubset({r['strategy_id'] for r in manifest})}`",
        "",
        "## Validation Commands",
    ]
    for key, value in validation.items():
        lines.append(f"- `{key}`: {value}")
    (ARTIFACT_DIR / "P356B_validation_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def phase0() -> dict[str, Any]:
    missing = sorted(name for name in P356A_REQUIRED if not (ARTIFACT_DIR / name).exists())
    if missing:
        raise P356BStop(f"P356B_BLOCKED_MISSING_P356A_ARTIFACTS: {missing}")
    status = run(["git", "status", "--short"])
    unexpected = [
        line
        for line in status.splitlines()
        if line
        and not line.startswith("?? artifacts/")
        and not line.startswith("?? scripts/p356a_all_strategy_inventory.py")
        and not line.startswith("?? scripts/p356b_biglotto_replay.py")
        and not line.startswith("?? tests/test_p356a_inventory_artifacts.py")
        and not line.startswith("?? tests/test_p356b_biglotto_replay.py")
    ]
    if unexpected:
        raise P356BStop(f"P356B_BLOCKED_UNEXPECTED_WORKTREE_DIRT: {unexpected}")
    return {
        "cwd": str(REPO_ROOT),
        "branch": run(["git", "branch", "--show-current"]),
        "head": run(["git", "rev-parse", "HEAD"]),
        "git_status_before": status,
        "p356a_artifacts_exist": not missing,
        "p356a_script_test_exist": (
            (REPO_ROOT / "scripts" / "p356a_all_strategy_inventory.py").exists()
            and (REPO_ROOT / "tests" / "test_p356a_inventory_artifacts.py").exists()
        ),
    }


def main() -> int:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    phase0_info = phase0()
    before = db_metrics(CANONICAL_DB)
    inventory = load_inventory()
    manifest, eligible = build_manifest(inventory)

    write_csv(
        ARTIFACT_DIR / "P356B_replay_eligible_manifest.csv",
        manifest,
        [
            "strategy_id",
            "lineage_id",
            "game",
            "bet_count",
            "current_status",
            "executable_status",
            "callable_entrypoint",
            "source_paths",
            "implementation_signature_hash",
            "eligibility_status",
            "exclusion_reason",
            "replay_notes",
        ],
    )
    write_manifest_md(manifest, eligible)

    draws = load_biglotto_draws(CANONICAL_DB)
    replay_rows: list[dict[str, Any]] = []
    for item in eligible:
        replay_rows.extend(replay_strategy(item, draws))
    write_csv(
        ARTIFACT_DIR / "P356B_biglotto_replay_30_150_750_1500.csv",
        replay_rows,
        [
            "strategy_id",
            "lineage_id",
            "current_status",
            "bet_count",
            "window",
            "total_periods",
            "hit_count",
            "hit_rate",
            "baseline",
            "edge",
            "replay_status",
            "notes",
        ],
    )
    write_replay_md(manifest, eligible, replay_rows)

    after = db_metrics(CANONICAL_DB)
    validation = {
        "db_sha_guard": "PASS" if before["db_sha256"] == after["db_sha256"] else "FAIL",
        "draw_rows_guard": "PASS" if before["draw_rows"] == after["draw_rows"] else "FAIL",
        "replay_rows_guard": (
            "PASS"
            if before["strategy_prediction_replays_rows"] == after["strategy_prediction_replays_rows"]
            else "FAIL"
        ),
        "eligible_rows_guard": (
            "PASS"
            if all(Counter(r["strategy_id"] for r in replay_rows)[e["strategy_id"]] == len(WINDOWS) for e in eligible)
            else "FAIL"
        ),
        "excluded_reason_guard": (
            "PASS"
            if all(r["exclusion_reason"] for r in manifest if r["eligibility_status"] == "EXCLUDED")
            else "FAIL"
        ),
        "seed_coverage_guard": (
            "PASS" if SEED_BIG_LOTTO.issubset({r["strategy_id"] for r in manifest}) else "FAIL"
        ),
    }
    write_validation_log(
        before=before,
        after=after,
        manifest=manifest,
        eligible=eligible,
        replay_rows=replay_rows,
        phase0=phase0_info,
        validation=validation,
    )
    if any(value == "FAIL" for value in validation.values()):
        raise P356BStop(f"P356B_VALIDATION_GUARD_FAILED: {validation}")
    print(json.dumps({"eligible": len(eligible), "replay_rows": len(replay_rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
