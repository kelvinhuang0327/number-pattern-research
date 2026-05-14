#!/usr/bin/env python3
"""
Post-V3 Replay API Regression Test Suite

Comprehensive API verification for all 16 lottery prediction strategies.
Tests V1 (EXECUTABLE_NOW), V2 (ARTIFACT_ONLY), and V3 (CODE_MISSING) categories.

Output: Detailed regression report with test results, response verification, and data integrity checks.
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Configuration
API_BASE_URL = "http://127.0.0.1:8002/api"
ENDPOINTS = {
    "history": "/replay/history",
    "summary": "/replay/summary",
}

# Test Data: All 16 strategies
V1_STRATEGIES = [
    ("BIG_LOTTO", "biglotto_deviation_2bet"),
    ("BIG_LOTTO", "biglotto_triple_strike"),
    ("DAILY_539", "daily539_f4cold"),
    ("DAILY_539", "daily539_markov_cold"),
    ("POWER_LOTTO", "power_orthogonal_5bet"),
    ("POWER_LOTTO", "power_precision_3bet"),
]

V2_STRATEGIES = [
    ("BIG_LOTTO", "biglotto_ts3_acb_4bet"),
    ("BIG_LOTTO", "biglotto_ts3_markov_freq_5bet"),
    ("DAILY_539", "p1_deviation_2bet_539"),
    ("POWER_LOTTO", "power_shlc_midfreq"),
]

V3_STRATEGIES = [
    ("DAILY_539", "acb_1bet"),
    ("DAILY_539", "acb_markov_midfreq"),
    ("DAILY_539", "acb_markov_midfreq_3bet"),
    ("DAILY_539", "midfreq_acb_2bet"),
    ("DAILY_539", "midfreq_fourier_2bet"),
    ("POWER_LOTTO", "h6_gate_mk20_ew85"),
]


class APIRegressionTester:
    """API regression test suite for replay endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = {
            "v1": [],
            "v2": [],
            "v3": [],
            "summary": {},
        }
        self.errors = []

    def test_history_endpoint(
        self, lottery_type: str, strategy_id: str, category: str
    ) -> Dict[str, Any]:
        """Test /api/replay/history endpoint for a strategy."""
        url = f"{self.base_url}{ENDPOINTS['history']}"
        params = {"lottery_type": lottery_type, "strategy_id": strategy_id}

        try:
            response = requests.get(url, params=params, timeout=10)

            test_result = {
                "strategy_id": strategy_id,
                "lottery_type": lottery_type,
                "category": category,
                "http_status": response.status_code,
                "http_ok": response.status_code == 200,
                "response_size_bytes": len(response.content),
            }

            if response.status_code == 200:
                data = response.json()
                test_result.update(
                    {
                        "records_count": len(data.get("records", [])),
                        "total_count": data.get("total", 0),
                        "pages": data.get("pages", 0),
                        "has_records": len(data.get("records", [])) > 0,
                    }
                )

                # Verify response schema
                schema_valid = self._verify_response_schema(data, category)
                test_result["schema_valid"] = schema_valid

                # Verify truth_level for V1/V2, absence for V3
                truth_level_valid = self._verify_truth_level(
                    data.get("records", []), category
                )
                test_result["truth_level_valid"] = truth_level_valid

                # Verify no fake data
                no_fake_data = self._verify_no_fake_data(data.get("records", []))
                test_result["no_fake_data"] = no_fake_data

                test_result["test_pass"] = (
                    schema_valid and truth_level_valid and no_fake_data
                )
            else:
                test_result["test_pass"] = False
                test_result["error"] = f"HTTP {response.status_code}"

            return test_result

        except requests.exceptions.RequestException as e:
            self.errors.append(
                f"Error testing {strategy_id} ({lottery_type}): {str(e)}"
            )
            return {
                "strategy_id": strategy_id,
                "lottery_type": lottery_type,
                "category": category,
                "test_pass": False,
                "error": str(e),
            }

    def _verify_response_schema(self, data: Dict, category: str) -> bool:
        """Verify response schema matches expected structure."""
        required_fields = ["records", "total", "pages"]
        if not all(field in data for field in required_fields):
            return False

        records = data.get("records", [])
        if len(records) > 0:
            # Verify each record has required fields
            required_record_fields = [
                "id",
                "strategy_id",
                "target_draw",
                "predicted_numbers",
                "actual_numbers",
                "hit_count",
            ]
            for record in records:
                if not all(field in record for field in required_record_fields):
                    return False

        return True

    def _verify_truth_level(self, records: List[Dict], category: str) -> bool:
        """Verify truth_level field presence and correctness."""
        if category == "V1":
            # V1 must have truth_level = REGENERATED_RETROSPECTIVE
            if len(records) == 0:
                return True
            for record in records:
                if record.get("truth_level") != "REGENERATED_RETROSPECTIVE":
                    return False
            return True
        elif category == "V2":
            # V2 must have truth_level = ARTIFACT_RECONSTRUCTED_RETROSPECTIVE
            if len(records) == 0:
                return True
            for record in records:
                if record.get("truth_level") != "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE":
                    return False
            return True
        elif category == "V3":
            # V3 must have NO records (0 rows)
            return len(records) == 0
        return False

    def _verify_no_fake_data(self, records: List[Dict]) -> bool:
        """Verify no fake or invalid data in records."""
        for record in records:
            # Check for unknown truth_level values
            valid_levels = [
                "REGENERATED_RETROSPECTIVE",
                "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE",
                None,
            ]
            if record.get("truth_level") not in valid_levels:
                return False

            # Check for invalid hit counts
            hit_count = record.get("hit_count", -1)
            if hit_count < 0 or hit_count > 6:
                return False

            # Check for empty predicted_numbers on V1/V2
            if len(record.get("predicted_numbers", [])) == 0:
                return False

        return True

    def test_all_strategies(self) -> None:
        """Run tests for all 16 strategies."""
        print("=" * 80)
        print("POST-V3 REPLAY API REGRESSION TEST SUITE")
        print(f"Started: {datetime.now().isoformat()}")
        print("=" * 80)

        # Test V1 strategies
        print("\n[V1 EXECUTABLE_NOW] Testing 6 strategies...")
        for lottery_type, strategy_id in V1_STRATEGIES:
            result = self.test_history_endpoint(lottery_type, strategy_id, "V1")
            self.results["v1"].append(result)
            status = "✅ PASS" if result["test_pass"] else "❌ FAIL"
            print(f"  {status} {strategy_id} ({lottery_type})")

        # Test V2 strategies
        print("\n[V2 ARTIFACT_ONLY] Testing 4 strategies...")
        for lottery_type, strategy_id in V2_STRATEGIES:
            result = self.test_history_endpoint(lottery_type, strategy_id, "V2")
            self.results["v2"].append(result)
            status = "✅ PASS" if result["test_pass"] else "❌ FAIL"
            print(f"  {status} {strategy_id} ({lottery_type})")

        # Test V3 strategies
        print("\n[V3 CODE_MISSING] Testing 6 strategies...")
        for lottery_type, strategy_id in V3_STRATEGIES:
            result = self.test_history_endpoint(lottery_type, strategy_id, "V3")
            self.results["v3"].append(result)
            status = "✅ PASS" if result["test_pass"] else "❌ FAIL"
            print(f"  {status} {strategy_id} ({lottery_type})")

        # Summarize results
        self._summarize_results()

    def _summarize_results(self) -> None:
        """Generate summary statistics."""
        v1_pass = sum(1 for r in self.results["v1"] if r.get("test_pass"))
        v2_pass = sum(1 for r in self.results["v2"] if r.get("test_pass"))
        v3_pass = sum(1 for r in self.results["v3"] if r.get("test_pass"))

        v1_total = len(self.results["v1"])
        v2_total = len(self.results["v2"])
        v3_total = len(self.results["v3"])

        self.results["summary"] = {
            "total_strategies": v1_total + v2_total + v3_total,
            "v1_pass": f"{v1_pass}/{v1_total}",
            "v2_pass": f"{v2_pass}/{v2_total}",
            "v3_pass": f"{v3_pass}/{v3_total}",
            "total_pass": f"{v1_pass + v2_pass + v3_pass}/{v1_total + v2_total + v3_total}",
            "all_pass": (v1_pass == v1_total)
            and (v2_pass == v2_total)
            and (v3_pass == v3_total),
        }

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"V1 (EXECUTABLE_NOW): {self.results['summary']['v1_pass']}")
        print(f"V2 (ARTIFACT_ONLY):  {self.results['summary']['v2_pass']}")
        print(f"V3 (CODE_MISSING):   {self.results['summary']['v3_pass']}")
        print(f"Total:               {self.results['summary']['total_pass']}")
        print()

        if self.results["summary"]["all_pass"]:
            print("✅ ALL TESTS PASSED")
        else:
            print("❌ SOME TESTS FAILED")

        if self.errors:
            print("\nErrors encountered:")
            for error in self.errors:
                print(f"  - {error}")

    def generate_report(self, output_file: str) -> None:
        """Generate detailed regression report."""
        report = self._build_report()
        with open(output_file, "w") as f:
            f.write(report)
        print(f"\nReport written to: {output_file}")

    def _build_report(self) -> str:
        """Build markdown regression report."""
        lines = []
        lines.append("# Post-V3 Replay API Regression Report\n")
        lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Status**: {'✅ ALL PASS' if self.results['summary']['all_pass'] else '❌ FAILURES DETECTED'}\n")
        lines.append("\n---\n")

        # Summary section
        lines.append("## Executive Summary\n")
        lines.append(
            f"- V1 EXECUTABLE_NOW: {self.results['summary']['v1_pass']}\n"
        )
        lines.append(f"- V2 ARTIFACT_ONLY: {self.results['summary']['v2_pass']}\n")
        lines.append(f"- V3 CODE_MISSING: {self.results['summary']['v3_pass']}\n")
        lines.append(f"- **Total: {self.results['summary']['total_pass']}**\n")

        # V1 Results
        lines.append("\n## V1: EXECUTABLE_NOW Results (6 strategies)\n")
        lines.append("| Strategy | Lottery | HTTP | Records | Schema | Truth Level | No Fake | Pass |\n")
        lines.append("|----------|---------|------|---------|--------|-------------|---------|------|\n")
        for result in self.results["v1"]:
            lines.append(
                f"| {result['strategy_id']} | {result['lottery_type']} | "
                f"{result.get('http_status', 'ERR')} | "
                f"{result.get('records_count', 'N/A')} | "
                f"{'✅' if result.get('schema_valid') else '❌'} | "
                f"{'✅' if result.get('truth_level_valid') else '❌'} | "
                f"{'✅' if result.get('no_fake_data') else '❌'} | "
                f"{'✅' if result['test_pass'] else '❌'} |\n"
            )

        # V2 Results
        lines.append("\n## V2: ARTIFACT_ONLY Results (4 strategies)\n")
        lines.append("| Strategy | Lottery | HTTP | Records | Schema | Truth Level | No Fake | Pass |\n")
        lines.append("|----------|---------|------|---------|--------|-------------|---------|------|\n")
        for result in self.results["v2"]:
            lines.append(
                f"| {result['strategy_id']} | {result['lottery_type']} | "
                f"{result.get('http_status', 'ERR')} | "
                f"{result.get('records_count', 'N/A')} | "
                f"{'✅' if result.get('schema_valid') else '❌'} | "
                f"{'✅' if result.get('truth_level_valid') else '❌'} | "
                f"{'✅' if result.get('no_fake_data') else '❌'} | "
                f"{'✅' if result['test_pass'] else '❌'} |\n"
            )

        # V3 Results
        lines.append("\n## V3: CODE_MISSING Results (6 strategies)\n")
        lines.append("| Strategy | Lottery | HTTP | Records | Tombstone | No Fake | Pass |\n")
        lines.append("|----------|---------|------|---------|-----------|---------|------|\n")
        for result in self.results["v3"]:
            lines.append(
                f"| {result['strategy_id']} | {result['lottery_type']} | "
                f"{result.get('http_status', 'ERR')} | "
                f"{result.get('records_count', 'N/A')} | "
                f"{'✅' if result.get('truth_level_valid') else '❌'} | "
                f"{'✅' if result.get('no_fake_data') else '❌'} | "
                f"{'✅' if result['test_pass'] else '❌'} |\n"
            )

        # Verification checks
        lines.append("\n## Verification Checklist\n")
        lines.append(
            f"- ✅ V1 strategies accessible (all 6 return HTTP 200)\n"
            if all(r.get('http_status') == 200 for r in self.results['v1'])
            else "- ❌ V1 accessibility issue\n"
        )
        lines.append(
            f"- ✅ V2 strategies accessible (all 4 return HTTP 200)\n"
            if all(r.get('http_status') == 200 for r in self.results['v2'])
            else "- ❌ V2 accessibility issue\n"
        )
        lines.append(
            f"- ✅ V3 strategies return 0 rows (safe tombstones)\n"
            if all(r.get('records_count') == 0 for r in self.results['v3'])
            else "- ❌ V3 tombstone issue\n"
        )
        lines.append(
            f"- ✅ V1 truth_level correct (REGENERATED_RETROSPECTIVE)\n"
            if all(r.get('truth_level_valid') for r in self.results['v1'])
            else "- ❌ V1 truth_level issue\n"
        )
        lines.append(
            f"- ✅ V2 truth_level correct (ARTIFACT_RECONSTRUCTED_RETROSPECTIVE)\n"
            if all(r.get('truth_level_valid') for r in self.results['v2'])
            else "- ❌ V2 truth_level issue\n"
        )
        lines.append(
            f"- ✅ No fake data in any response\n"
            if all(
                r.get('no_fake_data', False)
                for r in self.results['v1'] + self.results['v2'] + self.results['v3']
            )
            else "- ❌ Fake data detected\n"
        )

        if self.errors:
            lines.append("\n## Errors\n")
            for error in self.errors:
                lines.append(f"- {error}\n")

        lines.append("\n---\n")
        lines.append(f"**Result**: {'✅ API REGRESSION TEST PASSED' if self.results['summary']['all_pass'] else '❌ API REGRESSION TEST FAILED'}\n")

        return "".join(lines)

    def to_json(self) -> str:
        """Export results as JSON."""
        return json.dumps(self.results, indent=2)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = API_BASE_URL

    print(f"Testing API at: {api_url}")
    print()

    tester = APIRegressionTester(api_url)
    tester.test_all_strategies()

    # Generate report
    report_path = "outputs/replay/post_v3_api_regression_report_20260514.md"
    tester.generate_report(report_path)

    # Export JSON
    json_path = "outputs/replay/post_v3_api_regression_results_20260514.json"
    with open(json_path, "w") as f:
        f.write(tester.to_json())
    print(f"Results exported to: {json_path}")

    # Exit with appropriate code
    sys.exit(0 if tester.results["summary"]["all_pass"] else 1)


if __name__ == "__main__":
    main()
