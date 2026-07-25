"""Focused evidence-contract tests for the BIG_LOTTO 5-bet "expert-certified"
route/producer legacy-continuity correction (2026-07-25).

No canonical DB, no app boot at collection time: producer tests import only
models.multi_bet_optimizer (constructor bypassed via __new__); the one
route-level test does a late import of routes.prediction after moving CWD
under pytest's tmp_path, with the history loader and producer fully mocked
and a sqlite3.connect trip-wire so no canonical DB code path can execute.
"""
from __future__ import annotations

import ast
import asyncio
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
PREDICTION_ROUTE_PATH = LOTTERY_API / "routes" / "prediction.py"
OPTIMIZER_PATH = LOTTERY_API / "models" / "multi_bet_optimizer.py"
BASE_REF = "edf04c1b58e98ae81f616ae2ad9f7b4a35cb83d4"

EXPECTED_SOURCES = [
    "Fourier_Rhythm", "Cold_Numbers", "Tail_Balance", "Markov_Order1", "Freq_Orthogonal",
]
EXPECTED_TICKETS = [
    [2, 10, 15, 24, 34, 49],
    [3, 11, 17, 30, 33, 42],
    [8, 9, 32, 40, 43, 47],
    [5, 6, 7, 28, 38, 45],
    [14, 18, 20, 26, 29, 48],
]
EXPECTED_UNIQUE_NUMBERS = [
    2, 3, 5, 6, 7, 8, 9, 10, 11, 14, 15, 17, 18, 20, 24, 26, 28, 29, 30,
    32, 33, 34, 38, 40, 42, 43, 45, 47, 48, 49,
]
EXPECTED_COVERAGE = 30 / 49
WARNING_TEXT = "No reliable predictive advantage is currently established."


def _synthetic_big_lotto_history(n: int = 600) -> list[dict]:
    rng = random.Random(20260725)
    history = []
    for i in range(n):
        nums = sorted(rng.sample(range(1, 50), 6))
        history.append({"date": f"2020-01-{(i % 28) + 1:02d}", "draw": str(1000 + i), "numbers": nums})
    return history


def _ensure_sys_path() -> None:
    for p in (str(REPO_ROOT), str(LOTTERY_API)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _route_block() -> str:
    source = PREDICTION_ROUTE_PATH.read_text(encoding="utf-8")
    return source.split('@router.post("/api/predict/expert-certified")', 1)[1].split(
        '@router.post("/api/predict/core-satellite")', 1
    )[0]


def _optimizer_block() -> str:
    source = OPTIMIZER_PATH.read_text(encoding="utf-8")
    return source.split("def generate_verified_ts3_plus_5bets", 1)[1].split(
        "\n    def _ts3_fourier_bet", 1
    )[0]


@pytest.fixture()
def producer_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _ensure_sys_path()
    import models.multi_bet_optimizer as mbo

    opt = mbo.MultiBetOptimizer.__new__(mbo.MultiBetOptimizer)
    history = _synthetic_big_lotto_history()
    rules = {"maxNumber": 49, "pickCount": 6, "name": "BIG_LOTTO"}
    return opt.generate_verified_ts3_plus_5bets(history, rules)


# Contract item 1, 3: five legal tickets, fixed ordering + source labels
def test_producer_returns_five_legal_tickets_ordered_with_source_labels(producer_result):
    bets = producer_result["bets"]
    assert len(bets) == 5
    assert [b["source"] for b in bets] == EXPECTED_SOURCES
    for b in bets:
        assert len(b["numbers"]) == 6
        assert len(set(b["numbers"])) == 6
        assert all(1 <= n <= 49 for n in b["numbers"])
        assert b["numbers"] == sorted(b["numbers"])


# Contract item 2: fixed synthetic-history tickets byte-identical to the
# pre-correction Stage A baseline capture (same seed, same producer code path)
def test_producer_ticket_values_byte_identical_to_pre_correction_baseline(producer_result):
    assert [b["numbers"] for b in producer_result["bets"]] == EXPECTED_TICKETS
    assert producer_result["unique_numbers"] == EXPECTED_UNIQUE_NUMBERS
    assert producer_result["coverage"] == pytest.approx(EXPECTED_COVERAGE)


# Contract item 4
def test_producer_method_identity_unchanged(producer_result):
    assert producer_result["method"] == "verified_ts3_plus_5bet"


# Contract item 5
def test_producer_carries_conservative_metadata(producer_result):
    assert producer_result["evidence_status"] == "HISTORICAL_RESEARCH_ONLY"
    assert producer_result["current_significance"] == "NOT_ESTABLISHED"
    assert producer_result["warning"] == WARNING_TEXT
    assert "+1.77%" in producer_result["edge_expected"]
    assert "historical" in producer_result["edge_expected"].lower()
    assert "not currently established" in producer_result["edge_expected"].lower()


# Contract item 6
def test_producer_no_bare_current_advantage_claims():
    block = _optimizer_block()
    assert "Deterministic" not in block
    assert "'STABLE'" not in block and '"STABLE"' not in block
    assert "★ Verified Production Strategy" not in block


# Contract item 7
def test_route_path_and_query_parameters_unchanged():
    block = _route_block()
    assert 'async def predict_expert_certified_route(' in block
    assert 'lottery_type: str = Query(..., description="彩券類型 (POWER_LOTTO, BIG_LOTTO)")' in block
    assert (
        'num_bets: int = Query(5, ge=1, le=10, description="要生成的注數 (建議 5 注以達到 TS3+ 完整增益)")'
    ) in block
    assert "multi_bet_optimizer.generate_verified_ts3_plus_5bets" in block


# Contract items 8, 9, 10
def test_route_response_shape_matches_conservative_contract():
    block = _route_block()
    for key in ('"bets"', '"stability_report"', '"analysis"', '"lotteryType"', '"method"'):
        assert key in block
    assert '"verdict": "NOT_ESTABLISHED"' in block
    assert "\"edge_expected\": result['edge_expected']" in block
    assert '"verification": "HISTORICAL_RESEARCH_ONLY"' in block
    assert "\"evidence_status\": result['evidence_status']" in block
    assert "\"current_significance\": result['current_significance']" in block
    assert "\"warning\": result['warning']" in block
    assert '"verdict": "STABLE"' not in block
    assert '"1500p Three-Window Verified"' not in block


# Contract item 12 (paired with the live-call test below for item 11)
def test_route_exception_handling_unchanged():
    block = _route_block()
    assert "except Exception as e:" in block
    assert 'logger.error(f"Expert Certified 預測失敗: {str(e)}", exc_info=True)' in block
    assert 'raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")' in block


# Contract item 13: diff confined to the expert-certified function spans only
def test_diff_scope_confined_to_expert_certified_function():
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    def _new_line_ranges(path: Path) -> list[tuple[int, int]]:
        rel = path.relative_to(REPO_ROOT)
        proc = subprocess.run(
            ["git", "diff", "--unified=0", BASE_REF, "--", str(rel)],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        ranges = []
        for line in proc.stdout.splitlines():
            m = hunk_re.match(line)
            if m:
                start = int(m.group(1))
                length = int(m.group(2)) if m.group(2) is not None else 1
                ranges.append((start, start + max(length, 1) - 1))
        return ranges

    route_ranges = _new_line_ranges(PREDICTION_ROUTE_PATH)
    assert route_ranges, "expected at least one changed hunk in prediction.py"
    for start, end in route_ranges:
        assert 660 <= start and end <= 720, (
            f"prediction.py change outside expert-certified route span: lines {start}-{end}"
        )

    optimizer_ranges = _new_line_ranges(OPTIMIZER_PATH)
    assert optimizer_ranges, "expected at least one changed hunk in multi_bet_optimizer.py"
    for start, end in optimizer_ranges:
        assert 773 <= start and end <= 830, (
            f"multi_bet_optimizer.py change outside generate_verified_ts3_plus_5bets span: lines {start}-{end}"
        )


# Contract item 13 (predict.md half) + item 15: 4-bet/Power/Daily539 rows and
# the existing dated 2/3-bet blockquote are untouched; only the 5-bet rows
# and a new dated blockquote were added
def test_operator_command_only_touches_5bet_expert_row():
    predict_md = (REPO_ROOT / ".claude/commands/predict.md").read_text(encoding="utf-8")

    assert "| 大樂透 4注 | BIG_LOTTO | 4 | TS3+Markov(w=30) | +1.23% |" in predict_md
    assert "| 威力彩 / power | POWER_LOTTO | 2 | Fourier Rhythm + V3特別號 | +1.91% |" in predict_md
    assert "| 威力彩 3注 | POWER_LOTTO | 3 | Power Precision + V3特別號 | +2.30% |" in predict_md
    assert "| 今彩539 / 539 | DAILY_539 | 3 | SumRange+Bayesian+ZoneBalance | N/A |" in predict_md
    assert "| 大樂透 | 4注 | TS3+Markov(w=30) | 8.47% | 7.25% | +1.23% |" in predict_md
    assert "| 威力彩 | 3注 | Power Precision | 13.47% | 11.17% | +2.30% |" in predict_md
    assert "| 威力彩 | 2注 | Fourier Rhythm | 9.50% | 7.59% | +1.91% |" in predict_md
    assert "| 威力彩 | 特別號 | V3 MAB | 14.70% | 12.50% | +2.20% |" in predict_md

    assert (
        "> ⚠️ **大樂透 2注／3注**：evidence_status=HISTORICAL_RESEARCH_ONLY, "
        "current_significance=NOT_ESTABLISHED。\n"
        "> No reliable predictive advantage is currently established. "
        "Edge 數值僅為歷史回測描述性紀錄。"
    ) in predict_md

    assert "+1.77% (historical)" in predict_md
    assert "+1.77% (historical, NOT_ESTABLISHED)" in predict_md
    assert "大樂透 5注 (Expert-Certified)" in predict_md


def test_ast_parses_modified_python_files():
    for path in (PREDICTION_ROUTE_PATH, OPTIMIZER_PATH):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# Contract item 11 (route returns same five tickets from a mocked producer)
# and item 14 (no canonical DB access): history loader and producer are
# fully mocked, and sqlite3.connect is trip-wired to fail the test loudly if
# any code path reaches for it.
def test_route_returns_same_five_tickets_from_mocked_producer_no_db_access(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _ensure_sys_path()

    import sqlite3

    def _forbidden_connect(*_args, **_kwargs):
        raise AssertionError("canonical DB accessed via sqlite3.connect during mocked-producer route test")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)

    import routes.prediction as prediction_route_module

    fixed_producer_result = {
        "bets": [{"numbers": nums, "source": src} for nums, src in zip(EXPECTED_TICKETS, EXPECTED_SOURCES)],
        "method": "verified_ts3_plus_5bet",
        "edge_expected": "Historical/descriptive only (1500p run, not currently established): +1.77%",
        "evidence_status": "HISTORICAL_RESEARCH_ONLY",
        "current_significance": "NOT_ESTABLISHED",
        "warning": WARNING_TEXT,
        "coverage": EXPECTED_COVERAGE,
        "unique_numbers": EXPECTED_UNIQUE_NUMBERS,
    }

    def _mock_generate(history, lottery_rules):
        return fixed_producer_result

    monkeypatch.setattr(
        prediction_route_module.multi_bet_optimizer,
        "generate_verified_ts3_plus_5bets",
        _mock_generate,
    )

    def _mock_load_backend_history(lottery_type, min_required=10):
        return _synthetic_big_lotto_history(20), {"maxNumber": 49, "pickCount": 6, "name": "BIG_LOTTO"}

    monkeypatch.setattr(prediction_route_module, "load_backend_history", _mock_load_backend_history)

    response = asyncio.run(
        prediction_route_module.predict_expert_certified_route(lottery_type="BIG_LOTTO", num_bets=5)
    )

    assert [b["numbers"] for b in response["bets"]] == EXPECTED_TICKETS
    assert response["method"] == "verified_ts3_plus_5bet"
    assert response["lotteryType"] == "BIG_LOTTO"

    stability_report = response["stability_report"]
    assert stability_report["verdict"] == "NOT_ESTABLISHED"
    assert stability_report["verification"] == "HISTORICAL_RESEARCH_ONLY"
    assert stability_report["evidence_status"] == "HISTORICAL_RESEARCH_ONLY"
    assert stability_report["current_significance"] == "NOT_ESTABLISHED"
    assert stability_report["warning"] == WARNING_TEXT
    assert stability_report["method_chain"] == EXPECTED_SOURCES
