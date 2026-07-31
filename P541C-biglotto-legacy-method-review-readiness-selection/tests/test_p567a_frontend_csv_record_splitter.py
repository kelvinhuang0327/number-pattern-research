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


def test_frontend_csv_parser_preserves_quoted_newlines_in_note_fields():
    script = """
        import { DataProcessor } from './src/core/DataProcessor.js';
        const processor = new DataProcessor();
        const csv = [
          '遊戲名稱,期別,開獎日期,銷售總額,獎金總額,備註,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號',
          '大樂透,115000003,2026/07/10,,,"第一行備註',
          '第二行備註","01","02","03","04","05","06","07"'
        ].join('\\n');
        const records = processor.splitCSVRecords(csv);
        const rows = processor.parseStandardFormat(records);
        console.log(JSON.stringify({ records, row: rows[0] || null }));
    """

    payload = run_node(script)

    assert len(payload["records"]) == 2
    assert payload["row"] == {
        "draw": "115000003",
        "date": "2026-07-10",
        "lotteryType": "BIG_LOTTO",
        "numbers": [1, 2, 3, 4, 5, 6],
        "special": 7,
    }


def test_frontend_csv_record_splitter_does_not_add_runtime_or_data_behavior():
    source = (REPO_ROOT / "src" / "core" / "DataProcessor.js").read_text(
        encoding="utf-8"
    )
    helper = source.split("    splitCSVRecords(text) {", 1)[1].split(
        "\n    }\n\n    parseHeuristic(lines) {", 1
    )[0]

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "localStorage",
        "indexedDB",
        "fetch(",
    ):
        assert forbidden not in helper
