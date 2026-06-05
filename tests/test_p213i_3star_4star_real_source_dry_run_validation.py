from pathlib import Path
import tempfile
import unittest

from scripts import p213i_3star_4star_real_source_dry_run_validation as module


class TestP213IRealSourceDryRunValidation(unittest.TestCase):
    def test_normalize_date_handles_zero_padded_and_non_padded_days(self):
        self.assertEqual(module.normalize_date("2024/12/3"), "2024/12/03")
        self.assertEqual(module.normalize_date("2024-12-03"), "2024/12/03")

    def test_parse_source_file_reads_positional_columns(self):
        path = Path(
            "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/00-Plan/roadmap/number/100/3星彩_2011.csv"
        )
        rows = module.parse_source_file(path, "3_STAR")

        self.assertGreaterEqual(len(rows), 5)
        first = rows[0]
        self.assertEqual(first["draw"], "100000001")
        self.assertEqual(first["source_date_normalized"], "2011/01/01")
        self.assertEqual(first["positional_numbers"], [8, 2, 2])
        self.assertEqual(first["canonical_numbers"], [2, 2, 8])

    def test_build_report_matches_db_and_source_counts(self):
        report = module.build_report()
        summary = report["summary"]

        self.assertEqual(summary["source_status"], "REAL_SOURCE_PRESENT_FORMAT_NEEDS_ADAPTATION")
        self.assertEqual(summary["real_source_file_count"], 40)
        self.assertEqual(summary["total_rows"], 11700)
        self.assertEqual(summary["total_matched"], 7101)
        self.assertEqual(summary["total_missing"], 4599)
        self.assertEqual(summary["total_mismatched"], 0)

        self.assertEqual(summary["per_type"]["3_STAR"]["source_rows"], 5850)
        self.assertEqual(summary["per_type"]["3_STAR"]["db_rows"], 4179)
        self.assertEqual(summary["per_type"]["3_STAR"]["matched"], 4179)
        self.assertEqual(summary["per_type"]["3_STAR"]["missing"], 1671)
        self.assertEqual(summary["per_type"]["3_STAR"]["mismatched"], 0)

        self.assertEqual(summary["per_type"]["4_STAR"]["source_rows"], 5850)
        self.assertEqual(summary["per_type"]["4_STAR"]["db_rows"], 2922)
        self.assertEqual(summary["per_type"]["4_STAR"]["matched"], 2922)
        self.assertEqual(summary["per_type"]["4_STAR"]["missing"], 2928)
        self.assertEqual(summary["per_type"]["4_STAR"]["mismatched"], 0)

        self.assertEqual(summary["status_counts"]["MATCH"], 7101)
        self.assertEqual(summary["status_counts"]["MISSING_IN_DB"], 4599)
        self.assertEqual(summary["status_counts"].get("MISMATCH", 0), 0)

    def test_render_and_write_artifacts(self):
        report = module.build_report()
        markdown = module.render_markdown(report)
        self.assertIn("P213I 3_STAR / 4_STAR Real Source Dry-run Validation", markdown)
        self.assertIn("REAL_SOURCE_PRESENT_FORMAT_NEEDS_ADAPTATION", markdown)

        original_summary_md = module.SUMMARY_MD_PATH
        original_summary_json = module.SUMMARY_JSON_PATH
        original_rows_json = module.ROWS_JSON_PATH
        original_mismatches_json = module.MISMATCHES_JSON_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp_dir_name:
                tmp_dir = Path(tmp_dir_name)
                module.SUMMARY_MD_PATH = tmp_dir / original_summary_md.name
                module.SUMMARY_JSON_PATH = tmp_dir / original_summary_json.name
                module.ROWS_JSON_PATH = tmp_dir / original_rows_json.name
                module.MISMATCHES_JSON_PATH = tmp_dir / original_mismatches_json.name
                module.write_artifacts(report, tmp_dir)

                self.assertTrue(module.SUMMARY_MD_PATH.exists())
                self.assertTrue(module.SUMMARY_JSON_PATH.exists())
                self.assertTrue(module.ROWS_JSON_PATH.exists())
                self.assertTrue(module.MISMATCHES_JSON_PATH.exists())
        finally:
            module.SUMMARY_MD_PATH = original_summary_md
            module.SUMMARY_JSON_PATH = original_summary_json
            module.ROWS_JSON_PATH = original_rows_json
            module.MISMATCHES_JSON_PATH = original_mismatches_json


if __name__ == "__main__":
    unittest.main()
