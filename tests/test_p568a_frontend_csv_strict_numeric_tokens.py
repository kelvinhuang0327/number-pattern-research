import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_node(script: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-"],
        input=script,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_frontend_csv_standard_parser_rejects_partial_numeric_tokens():
    script = """
        import { DataProcessor } from './src/core/DataProcessor.js';
        const processor = new DataProcessor();
        const rows = processor.parseStandardFormat([
          '遊戲名稱,期別,開獎日期,銷售總額,獎金總額,備註,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號',
          '大樂透,115000006,2026/07/13,,,,01x,02,03,04,05,06,07'
        ]);
        console.log(JSON.stringify({ rows }));
    """

    payload = run_node(script)

    assert payload["rows"] == []


def test_frontend_csv_heuristic_parser_rejects_partial_numeric_tokens():
    script = """
        import { DataProcessor } from './src/core/DataProcessor.js';
        const processor = new DataProcessor();
        console.log = () => {};
        const rows = processor.parseHeuristic([
          '大樂透,115000006,2026/07/13,,,,01x,02,03,04,05,06,07'
        ]);
        process.stdout.write(JSON.stringify({ rows }));
    """

    payload = run_node(script)

    assert payload["rows"] == []


def test_frontend_csv_parser_preserves_zero_padded_numeric_tokens():
    script = """
        import { DataProcessor } from './src/core/DataProcessor.js';
        const processor = new DataProcessor();
        const rows = processor.parseStandardFormat([
          '遊戲名稱,期別,開獎日期,銷售總額,獎金總額,備註,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號',
          '大樂透,115000007,2026/07/14,,,,01,02,03,04,05,06,07'
        ]);
        console.log(JSON.stringify(rows[0] || null));
    """

    row = run_node(script)

    assert row == {
        "draw": "115000007",
        "date": "2026-07-14",
        "lotteryType": "BIG_LOTTO",
        "numbers": [1, 2, 3, 4, 5, 6],
        "special": 7,
    }
