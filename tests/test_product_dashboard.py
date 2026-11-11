from __future__ import annotations

import unittest

from wbc_backend.ux.product_dashboard import build_product_dashboard


class TestProductDashboard(unittest.TestCase):
    def test_dashboard_includes_mode_map_and_current_statuses(self):
        dashboard = build_product_dashboard()
        self.assertIn("BETTING-POOL PRODUCT DASHBOARD", dashboard)
        self.assertIn("WBC PRODUCTION", dashboard)
        self.assertIn("MLB PAPER-ONLY RESEARCH", dashboard)
        self.assertIn("SPRING TRAINING SANDBOX", dashboard)
        self.assertIn("PAPER_ONLY", dashboard)
        self.assertIn("SANDBOX_ONLY", dashboard)
        self.assertIn("NOT RECOMMENDED FOR BETTING", dashboard)

    def test_mode_filter_works(self):
        mlb = build_product_dashboard(mode="mlb")
        self.assertIn("MLB PAPER-ONLY RESEARCH", mlb)
        self.assertNotIn("WBC PRODUCTION", mlb)
        self.assertNotIn("SPRING TRAINING SANDBOX", mlb)


if __name__ == "__main__":
    unittest.main()
