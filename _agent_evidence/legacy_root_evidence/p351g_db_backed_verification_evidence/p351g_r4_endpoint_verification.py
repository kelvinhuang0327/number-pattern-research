#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import asyncio
import json
import re
import sqlite3
import sys
import types
from pathlib import Path


WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p351g-db-backed-verification")
OWNER_DB = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db")
EVIDENCE = Path("/Users/kelvin/Kelvin-WorkSpace/p351g_db_backed_verification_evidence")

V2_STRATEGIES = [
    ("BIG_LOTTO", "biglotto_ts3_acb_4bet", 4),
    ("BIG_LOTTO", "biglotto_ts3_markov_freq_5bet", 5),
    ("DAILY_539", "p1_deviation_2bet_539", 2),
    ("POWER_LOTTO", "power_shlc_midfreq", 1),
]

FORBIDDEN_DISPLAY_TERMS = (
    "recommended bet",
    "best strategy",
    "increase win rate",
    "推薦投注",
    "最佳策略",
    "提高中獎率",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def owner_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def assert_ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _StubHTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: str | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _StubAPIRouter:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    post = get
    put = get
    delete = get


def _stub_query(default=None, *args, **kwargs):
    return default


def install_fastapi_stub() -> None:
    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.APIRouter = _StubAPIRouter
    fastapi_stub.HTTPException = _StubHTTPException
    fastapi_stub.Query = _stub_query
    sys.modules.setdefault("fastapi", fastapi_stub)


def assert_json(data: dict, label: str) -> dict:
    assert_ok(isinstance(data, dict), f"{label} did not return a JSON object")
    return data


async def call_grouped(replay_mod, *, lottery_type: str, strategy_id: str, bet_index: int, page_size: int) -> dict:
    return assert_json(
        await replay_mod.get_history_replay_detail_grouped(
            lottery_type=lottery_type,
            strategy_id=strategy_id,
            bet_index=bet_index,
            page=1,
            page_size=page_size,
            sort="target_draw_desc",
            hit_filter="all",
            target_draw=None,
        ),
        "history-detail-grouped",
    )


async def call_overview(
    replay_mod,
    *,
    coverage_mode: bool,
    bet_index: int,
    replay_status_category: str | None = None,
) -> dict:
    return assert_json(
        await replay_mod.get_history_replay_overview(
            lottery_type=None,
            bet_index=bet_index,
            replay_status_category=replay_status_category,
            coverage_mode=coverage_mode,
        ),
        "history-overview",
    )


def compact_grouped_payload(data: dict) -> dict:
    rows = data.get("rows") or []
    first = rows[0] if rows else {}
    bets = first.get("bets") or []
    first_bet = bets[0] if bets else {}
    return {
        "lottery_type": data.get("lottery_type"),
        "strategy_id": data.get("strategy_id"),
        "lifecycle_status": data.get("lifecycle_status"),
        "display_depth_policy": data.get("display_depth_policy"),
        "display_depth_limit": data.get("display_depth_limit"),
        "total_count": data.get("total_count"),
        "row_count_returned": len(rows),
        "first_row": {
            "target_draw": first.get("target_draw"),
            "truth_level": first.get("truth_level"),
            "display_trust_label": first.get("display_trust_label"),
            "display_trust_detail": first.get("display_trust_detail"),
            "display_trust_is_live": first.get("display_trust_is_live"),
            "n_bets": first.get("n_bets"),
            "bet_count_returned": len(bets),
        },
        "first_bet": {
            "bet_index": first_bet.get("bet_index"),
            "truth_level": first_bet.get("truth_level"),
            "display_trust_label": first_bet.get("display_trust_label"),
            "display_trust_detail": first_bet.get("display_trust_detail"),
            "display_trust_is_live": first_bet.get("display_trust_is_live"),
        },
        "flags": {
            "no_db_write": data.get("no_db_write"),
            "no_replay_backfill": data.get("no_replay_backfill"),
            "no_strategy_adapter_changes": data.get("no_strategy_adapter_changes"),
        },
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert_ok(OWNER_DB == Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"), "owner DB path mismatch")
    assert_ok(OWNER_DB.is_file(), f"owner DB is not a regular file: {OWNER_DB}")
    before = sha256(OWNER_DB)
    print(f"owner_db_path={OWNER_DB}")
    print(f"owner_db_size={OWNER_DB.stat().st_size}")
    print(f"owner_db_sha256_before={before}")

    with owner_conn() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table'
                  AND name IN ('strategy_prediction_replays','strategy_replay_runs','live_strategy_predictions','draws')
                """
            )
        }
        print("expected_tables_present=" + ",".join(sorted(tables)))
        assert_ok("strategy_prediction_replays" in tables, "strategy_prediction_replays table missing")
        assert_ok("strategy_replay_runs" in tables, "strategy_replay_runs table missing")
        assert_ok("draws" in tables, "draws table missing")
        print("live_strategy_predictions_present=" + str("live_strategy_predictions" in tables))

    sys.path.insert(0, str(WORKTREE))
    sys.path.insert(0, str(WORKTREE / "lottery_api"))

    install_fastapi_stub()
    from routes import replay as replay_mod

    replay_mod._open_conn = owner_conn

    rejected_cap_sample = None
    rejected_probe_payloads = []
    for lottery_type, strategy_id, bet_index in V2_STRATEGIES:
        data = asyncio.run(
            call_grouped(
                replay_mod,
                lottery_type=lottery_type,
                strategy_id=strategy_id,
                bet_index=bet_index,
                page_size=300,
            )
        )
        rejected_probe_payloads.append(compact_grouped_payload(data))
        if data.get("total_count", 0) > 0 and data.get("lifecycle_status") == "REJECTED":
            rejected_cap_sample = (lottery_type, strategy_id, bet_index)
            break

    if rejected_cap_sample is None:
        for meta in replay_mod.list_strategy_lifecycle_metadata("REJECTED"):
            strategy_id = meta["strategy_id"]
            bet_index = replay_mod._derive_bet_count(strategy_id) or 1
            for lottery_type in meta["supported_lottery_types"]:
                data = asyncio.run(
                    call_grouped(
                        replay_mod,
                        lottery_type=lottery_type,
                        strategy_id=strategy_id,
                        bet_index=bet_index,
                        page_size=300,
                    )
                )
                rejected_probe_payloads.append(compact_grouped_payload(data))
                if data.get("total_count", 0) > 0 and data.get("lifecycle_status") == "REJECTED":
                    rejected_cap_sample = (lottery_type, strategy_id, bet_index)
                    break
            if rejected_cap_sample is not None:
                break

    assert_ok(rejected_cap_sample is not None, "no DB-backed REJECTED rows found for latest-300 verification")
    lottery_type, strategy_id, bet_index = rejected_cap_sample
    rejected = asyncio.run(
        call_grouped(
            replay_mod,
            lottery_type=lottery_type,
            strategy_id=strategy_id,
            bet_index=bet_index,
            page_size=1500,
        )
    )
    assert_ok(rejected["display_depth_policy"] == "LATEST_300_PERIODS_FOR_REJECTED", "REJECTED latest-300 policy missing")
    assert_ok(rejected["display_depth_limit"] == 300, "REJECTED display limit is not 300")
    assert_ok(rejected["total_count"] <= 300, f"REJECTED total_count exceeds 300: {rejected['total_count']}")
    draws = [int(row["target_draw"]) for row in rejected["rows"]]
    assert_ok(draws == sorted(draws, reverse=True), "REJECTED rows are not latest-first")
    assert_ok(rejected["rows"], "REJECTED sample returned no rows")
    artifact_rows = [
        row for row in rejected["rows"]
        if row.get("truth_level") == "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
    ]
    artifact_rows_present = bool(artifact_rows)
    if artifact_rows_present:
        for row in artifact_rows:
            assert_ok(row["display_trust_label"] == "RETROSPECTIVE", "row trust label is not RETROSPECTIVE")
            assert_ok(row["display_trust_detail"] == "Artifact Reconstructed", "row trust detail mismatch")
            assert_ok(row["display_trust_is_live"] is False, "retrospective row labeled live")
            for bet in row["bets"]:
                if bet.get("truth_level") == "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE":
                    assert_ok(bet["display_trust_label"] == "RETROSPECTIVE", "bet trust label mismatch")
                    assert_ok(bet["display_trust_is_live"] is False, "retrospective bet labeled live")
    else:
        with owner_conn() as conn:
            artifact_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM strategy_prediction_replays
                WHERE truth_level = 'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE'
                """
            ).fetchone()[0]
        assert_ok(artifact_count == 0, "artifact rows exist in DB but were not surfaced by endpoint sample")
        print("artifact_reconstructed_rows_present=False")
    print(f"rejected_sample={lottery_type}/{strategy_id}/bet_index_{bet_index}")
    print(f"rejected_total_count={rejected['total_count']}")
    print(f"artifact_reconstructed_row_level_check={'VERIFIED' if artifact_rows_present else 'NOT_APPLICABLE_DB_HAS_ZERO_ARTIFACT_ROWS'}")

    overview_all = asyncio.run(call_overview(replay_mod, coverage_mode=True, bet_index=0))
    overview_no_rows = asyncio.run(
        call_overview(
            replay_mod,
            coverage_mode=True,
            bet_index=0,
            replay_status_category="no_production_replay",
        )
    )
    retired_zero = [
        row for row in overview_no_rows["rows"]
        if row["lifecycle_status"] == "RETIRED" and not row["has_replay_rows"]
    ]
    retired_zero_check = "NOT_APPLICABLE_DB_HAS_NO_ZERO_ROW_RETIRED_STRATEGIES"
    if retired_zero:
        assert_ok({row["can_open_detail"] for row in retired_zero} == {False}, "RETIRED zero-row detail open flag mismatch")
        assert_ok({row["missing_reason"] for row in retired_zero} == {"retired_no_rows"}, "RETIRED missing reason mismatch")
        retired_zero_check = "VERIFIED"
    print(f"retired_zero_row_count={len(retired_zero)}")
    print(f"retired_zero_row_tombstone_check={retired_zero_check}")

    retired_with_rows = [
        row for row in overview_all["rows"]
        if row["lifecycle_status"] == "RETIRED" and row["has_replay_rows"]
    ]
    retired_with_rows_sample = None
    if retired_with_rows:
        sample = retired_with_rows[0]
        retired_detail = asyncio.run(
            call_grouped(
                replay_mod,
                lottery_type=sample["lottery_type"],
                strategy_id=sample["strategy_id"],
                bet_index=sample["derived_bet_count"] or 1,
                page_size=10,
            )
        )
        assert_ok(retired_detail["display_depth_policy"] == "ALL_LEGALLY_AVAILABLE_ROWS", "RETIRED preserved rows unexpectedly capped")
        assert_ok(retired_detail["total_count"] == sample["distinct_draw_count"], "RETIRED detail count mismatch")
        assert_ok(len(retired_detail["rows"]) <= 10, "RETIRED detail page_size ignored")
        retired_with_rows_sample = compact_grouped_payload(retired_detail)
    print(f"retired_with_rows_count={len(retired_with_rows)}")

    observation_rows = [row for row in overview_all["rows"] if row["lifecycle_status"] == "OBSERVATION"]
    no_row_observation = [row for row in observation_rows if not row["has_replay_rows"]]
    assert_ok(observation_rows, "OBSERVATION strategies are not visible")
    assert_ok(no_row_observation, "no zero-row OBSERVATION rows found")
    assert_ok({row["can_open_detail"] for row in no_row_observation} == {False}, "OBSERVATION no-row detail open flag mismatch")
    assert_ok({row["missing_reason"] for row in no_row_observation} == {"observation_no_data"}, "OBSERVATION missing reason mismatch")
    print(f"observation_total_count={len(observation_rows)}")
    print(f"observation_no_row_count={len(no_row_observation)}")

    payload_text = json.dumps(
        {
            "rejected": rejected,
            "overview_all": overview_all,
            "overview_no_rows": overview_no_rows,
        },
        ensure_ascii=False,
    ).lower()
    source_text = (
        (WORKTREE / "index.html").read_text(encoding="utf-8")
        + "\n"
        + (WORKTREE / "lottery_api" / "routes" / "replay.py").read_text(encoding="utf-8")
    ).lower()
    forbidden_hits = [
        term for term in FORBIDDEN_DISPLAY_TERMS
        if term.lower() in payload_text or term.lower() in source_text
    ]
    assert_ok(not forbidden_hits, f"forbidden display terms found: {forbidden_hits}")
    print("forbidden_language_check=PASS")

    replay_source = (WORKTREE / "lottery_api" / "routes" / "replay.py").read_text(encoding="utf-8")
    registry_source = (WORKTREE / "lottery_api" / "models" / "replay_strategy_registry.py").read_text(encoding="utf-8")
    assert_ok("random_baseline" not in replay_source.lower(), "random_baseline appears in replay route")
    assert_ok("random_baseline" not in registry_source.lower(), "random_baseline appears in registry")
    mutation_sql = re.findall(
        r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)\b",
        replay_source,
        re.I,
    )
    assert_ok(not mutation_sql, f"mutation SQL tokens found in replay route: {mutation_sql}")
    print("decision_e_random_baseline_and_mutation_scan=PASS")

    samples = {
        "db_open_method": f"file:{OWNER_DB}?mode=ro with PRAGMA query_only=ON",
        "rejected_probe_payloads": rejected_probe_payloads,
        "rejected_verified_sample": compact_grouped_payload(rejected),
        "artifact_reconstructed_rows_present": artifact_rows_present,
        "artifact_reconstructed_row_level_check": (
            "VERIFIED"
            if artifact_rows_present
            else "NOT_APPLICABLE_DB_HAS_ZERO_ARTIFACT_RECONSTRUCTED_RETROSPECTIVE_ROWS"
        ),
        "retired_zero_row_example": retired_zero[0] if retired_zero else None,
        "retired_zero_row_tombstone_check": retired_zero_check,
        "retired_with_rows_count": len(retired_with_rows),
        "retired_with_rows_sample": retired_with_rows_sample,
        "observation_no_row_example": no_row_observation[0],
        "overview_coverage_summary": overview_all.get("coverage_summary"),
    }
    (EVIDENCE / "endpoint_payload_samples_redacted.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    after = sha256(OWNER_DB)
    print(f"owner_db_sha256_after={after}")
    assert_ok(after == before, "owner DB hash changed during verification")
    print("db_hash_unchanged=PASS")
    print("P351G_R4_DB_BACKED_ENDPOINT_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
