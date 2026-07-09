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


def test_frontend_csv_parser_preserves_quoted_commas_in_game_name():
    script = """
        import { DataProcessor } from './src/core/DataProcessor.js';
        const processor = new DataProcessor();
        const rows = processor.parseStandardFormat([
          '遊戲名稱,期別,開獎日期,銷售總額,獎金總額,備註,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號',
          '"大樂透,測試備註",115000001,2026/07/08,,,,"01","02","03","04","05","06","07"'
        ]);
        console.log(JSON.stringify(rows[0] || null));
    """

    row = run_node(script)

    assert row == {
        "draw": "115000001",
        "date": "2026-07-08",
        "lotteryType": "BIG_LOTTO",
        "numbers": [1, 2, 3, 4, 5, 6],
        "special": 7,
    }


def test_frontend_csv_parser_preserves_escaped_quotes():
    script = '''
        import { DataProcessor } from './src/core/DataProcessor.js';
        const processor = new DataProcessor();
        console.log(JSON.stringify({
          parts: processor.splitCSVLine('"大樂透 ""春節""",115000002,2026/07/09')
        }));
    '''

    payload = run_node(script)

    assert payload["parts"] == ["大樂透 \"春節\"", "115000002", "2026/07/09"]
