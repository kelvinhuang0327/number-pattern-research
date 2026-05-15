"""
Guard test: Ensure pool-size fields are properly populated before H013 validation.
Prevents regression where all-null fields are sent to formal hypothesis testing.
"""
import sqlite3
import pytest


class TestPoolSizeDataIntegrity:
    """Validate pool-size data is available and complete before research."""
    
    DB_PATH = "lottery_api/data/lottery_v2.db"
    
    @pytest.fixture(scope="class")
    def db_connection(self):
        """Connect to lottery database."""
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()
    
    def test_daily539_pool_columns_exist(self, db_connection):
        """Verify sell_amount and total_amount columns exist in schema."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(draws)")
        columns = {row[1] for row in cursor.fetchall()}
        
        assert "sell_amount" in columns, "Column 'sell_amount' missing from draws table"
        assert "total_amount" in columns, "Column 'total_amount' missing from draws table"
    
    def test_daily539_pool_coverage_high(self, db_connection):
        """Ensure pool-size data has >95% coverage for DAILY_539."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(sell_amount) as nonnull_sell,
                COUNT(total_amount) as nonnull_total
            FROM draws
            WHERE lottery_type = 'DAILY_539'
        """)
        row = cursor.fetchone()
        total = row["total"]
        nonnull_sell = row["nonnull_sell"]
        nonnull_total = row["nonnull_total"]
        
        sell_coverage = 100.0 * nonnull_sell / total if total > 0 else 0
        total_coverage = 100.0 * nonnull_total / total if total > 0 else 0
        
        assert sell_coverage >= 95.0, (
            f"sell_amount coverage {sell_coverage:.1f}% < 95% threshold. "
            f"Cannot proceed with H013 validation."
        )
        assert total_coverage >= 95.0, (
            f"total_amount coverage {total_coverage:.1f}% < 95% threshold. "
            f"Cannot proceed with H013 validation."
        )
    
    def test_daily539_pool_values_reasonable(self, db_connection):
        """Sanity check: pool amounts are positive and not extreme outliers."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT sell_amount, total_amount
            FROM draws
            WHERE lottery_type = 'DAILY_539'
            AND sell_amount IS NOT NULL
            AND total_amount IS NOT NULL
            LIMIT 100
        """)
        
        for row in cursor.fetchall():
            sell = row["sell_amount"]
            total = row["total_amount"]
            
            # Basic sanity: amounts should be positive (in TWD)
            assert sell > 0, f"Invalid sell_amount: {sell}"
            assert total > 0, f"Invalid total_amount: {total}"
            
            # Market ratio check: total prize pool / ticket sales
            # DAILY_539 has high payout (often 50-100% depending on draw structure)
            ratio = total / sell
            assert 0.01 < ratio < 1.5, (
                f"Suspicious market ratio: total/sell = {ratio:.2f} "
                f"(sell={sell}, total={total})"
            )
    
    def test_h013_research_guard_pass_condition(self, db_connection):
        """
        Explicit guard: H013 research can only proceed if this test passes.
        Prevents previous situation where 0% coverage silently failed validation.
        """
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(sell_amount) as nonnull_sell
            FROM draws
            WHERE lottery_type = 'DAILY_539'
        """)
        row = cursor.fetchone()
        total = row["total"]
        nonnull_sell = row["nonnull_sell"]
        
        # This is the critical check: 100% coverage required for H013
        coverage = 100.0 * nonnull_sell / total if total > 0 else 0
        
        assert coverage == 100.0, (
            f"❌ H013 research BLOCKED: sell_amount coverage is {coverage:.1f}%, "
            f"not 100%. All {total} draws must have valid pool-size data "
            f"before formal hypothesis testing. Current nonnull: {nonnull_sell}. "
            f"\n→ Run: python3 tools/backfill_daily539_pool_data.py"
        )


if __name__ == "__main__":
    # Run with: pytest tests/test_h013_pool_data_guard.py -v
    pytest.main([__file__, "-v"])
