#!/usr/bin/env python3
"""
V2 ARTIFACT_ONLY Controlled Apply Script
Applies 200 candidate rows from dry-run parser to production DB.

Usage:
  python3 scripts/v2_artifact_only_apply_rows.py --dry-run
  python3 scripts/v2_artifact_only_apply_rows.py --apply
  python3 scripts/v2_artifact_only_apply_rows.py --rollback <controlled_apply_id>
"""

import json
import sys
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

class V2ArtifactOnlyApply:
    """Controlled apply for V2 ARTIFACT_ONLY candidate rows."""

    def __init__(self, db_path: str, candidate_rows_path: str):
        self.db_path = db_path
        self.candidate_rows_path = candidate_rows_path
        self.controlled_apply_id = self._generate_apply_id()
        self.apply_log = []
        self.stats = {
            "would_insert": 0,
            "would_skip_existing": 0,
            "invalid_rows": 0,
            "inserted": 0,
            "skipped_existing": 0,
            "per_strategy": {}
        }

    def _generate_apply_id(self) -> str:
        """Generate V2 controlled_apply_id (timestamp-based)."""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d%H%M%S")
        # Add short hash for uniqueness
        import hashlib
        hash_part = hashlib.md5(f"{timestamp}-v2".encode()).hexdigest()[:8]
        return f"{timestamp}-{hash_part}"

    def load_candidate_rows(self) -> List[dict]:
        """Load candidate rows from JSONL file."""
        rows = []
        try:
            with open(self.candidate_rows_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        rows.append(row)
                    except json.JSONDecodeError as e:
                        print(f"ERROR: Invalid JSON at line {line_num}: {e}")
                        return []
        except FileNotFoundError:
            print(f"ERROR: Candidate rows file not found: {self.candidate_rows_path}")
            return []

        return rows

    def validate_row(self, row: dict) -> Tuple[bool, str]:
        """Validate a single candidate row."""
        required_fields = [
            'strategy_id', 'lottery_type', 'target_draw', 'target_date',
            'predicted_numbers', 'actual_numbers',
            'hit_numbers', 'hit_count', 'special_hit',
            'truth_level', 'source', 'provenance_source', 'provenance_hash',
            'dry_run_only', 'history_window_end', 'leakage_guard_pass'
        ]

        for field in required_fields:
            if field not in row:
                return False, f"missing_field:{field}"

        # Verify it's marked as dry-run candidate
        if row['dry_run_only'] != 1:
            return False, "not_marked_dry_run_only"

        if row['controlled_apply_id'] is not None:
            return False, "already_has_controlled_apply_id"

        if row['truth_level'] != 'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE':
            return False, "invalid_truth_level"

        if row['leakage_guard_pass'] != 1:
            return False, "leakage_guard_failed"

        return True, None

    def check_existing(self, conn: sqlite3.Connection, row: dict) -> bool:
        """Check if row already exists in DB (idempotency check)."""
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM strategy_prediction_replays
                WHERE strategy_id = ? AND target_draw = ? AND truth_level = ?
            """, (row['strategy_id'], row['target_draw'], row['truth_level']))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            print(f"ERROR: Failed to check existing row: {e}")
            return False

    def insert_row(self, cursor: sqlite3.Cursor, row: dict):
        """Insert a single row into the database."""
        # Convert boolean/int fields
        predicted_numbers_json = json.dumps(row['predicted_numbers'])
        actual_numbers_json = json.dumps(row['actual_numbers'])
        hit_numbers_json = json.dumps(row['hit_numbers'])

        cursor.execute("""
            INSERT INTO strategy_prediction_replays (
                strategy_id, lottery_type, target_draw, target_date,
                predicted_numbers, predicted_special, actual_numbers, actual_special,
                hit_numbers, hit_count, special_hit,
                truth_level, source, provenance_source, provenance_hash,
                controlled_apply_id, dry_run_only
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['strategy_id'],
            row['lottery_type'],
            row['target_draw'],
            row['target_date'],
            predicted_numbers_json,
            row['predicted_special'],
            actual_numbers_json,
            row['actual_special'],
            hit_numbers_json,
            row['hit_count'],
            row['special_hit'],
            'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE',  # truth_level
            'v2_artifact_only_controlled_apply',     # source (updated for apply)
            row['provenance_source'],
            row['provenance_hash'],
            self.controlled_apply_id,
            0  # dry_run_only=0 for production
        ))

    def dry_run(self) -> bool:
        """Execute dry-run (no DB modifications)."""
        print("\n=== V2 ARTIFACT_ONLY Controlled Apply — DRY-RUN ===")
        print(f"Controlled Apply ID: {self.controlled_apply_id}")
        print(f"Candidate rows file: {self.candidate_rows_path}\n")

        # Load candidate rows
        rows = self.load_candidate_rows()
        if not rows:
            print("ERROR: Failed to load candidate rows")
            return False

        print(f"Loaded {len(rows)} candidate rows\n")

        # Validate all rows
        invalid_count = 0
        for i, row in enumerate(rows):
            is_valid, reason = self.validate_row(row)
            if not is_valid:
                print(f"Row {i+1}: INVALID ({reason})")
                invalid_count += 1
                self.stats['invalid_rows'] += 1
                continue

            strategy_id = row['strategy_id']
            if strategy_id not in self.stats['per_strategy']:
                self.stats['per_strategy'][strategy_id] = {'would_insert': 0, 'would_skip': 0}
            self.stats['per_strategy'][strategy_id]['would_insert'] += 1

        if invalid_count > 0:
            print(f"\nERROR: {invalid_count} invalid rows found")
            return False

        # Check existing rows (idempotency)
        try:
            conn = sqlite3.connect(self.db_path)
            for row in rows:
                if self.check_existing(conn, row):
                    self.stats['would_skip_existing'] += 1
                    strategy_id = row['strategy_id']
                    self.stats['per_strategy'][strategy_id]['would_skip'] += 1
                else:
                    self.stats['would_insert'] += 1

            conn.close()
        except Exception as e:
            print(f"ERROR: Failed to check existing rows: {e}")
            return False

        # Print summary
        print("\n=== DRY-RUN SUMMARY ===")
        print(f"Would insert: {self.stats['would_insert']}")
        print(f"Would skip (existing): {self.stats['would_skip_existing']}")
        print(f"Invalid rows: {self.stats['invalid_rows']}")

        print("\n=== Per-Strategy Summary ===")
        for strategy_id in sorted(self.stats['per_strategy'].keys()):
            stats = self.stats['per_strategy'][strategy_id]
            print(f"{strategy_id}: {stats['would_insert']} would insert, {stats['would_skip']} would skip")

        if self.stats['would_insert'] == 200 and self.stats['would_skip_existing'] == 0 and self.stats['invalid_rows'] == 0:
            print("\n✅ DRY-RUN PASS: Ready for controlled apply")
            return True
        else:
            print("\n❌ DRY-RUN FAIL: Issues detected")
            return False

    def apply(self) -> bool:
        """Execute controlled apply (writes to DB)."""
        print("\n=== V2 ARTIFACT_ONLY Controlled Apply — LIVE APPLY ===")
        print(f"Controlled Apply ID: {self.controlled_apply_id}")
        print(f"Candidate rows file: {self.candidate_rows_path}\n")

        # Load candidate rows
        rows = self.load_candidate_rows()
        if not rows:
            print("ERROR: Failed to load candidate rows")
            return False

        print(f"Loaded {len(rows)} candidate rows\n")

        # Connect to DB
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
        except Exception as e:
            print(f"ERROR: Failed to connect to DB: {e}")
            return False

        # Validate and insert rows in transaction
        try:
            cursor.execute("BEGIN TRANSACTION")

            inserted_count = 0
            skipped_count = 0
            invalid_count = 0

            for i, row in enumerate(rows, 1):
                # Validate row
                is_valid, reason = self.validate_row(row)
                if not is_valid:
                    print(f"Row {i}: INVALID ({reason})")
                    invalid_count += 1
                    self.apply_log.append({
                        "row_index": i,
                        "status": "INVALID",
                        "reason": reason,
                        "strategy_id": row.get('strategy_id')
                    })
                    continue

                # Check if already exists (idempotency)
                if self.check_existing(conn, row):
                    skipped_count += 1
                    self.apply_log.append({
                        "row_index": i,
                        "status": "SKIPPED_EXISTING",
                        "strategy_id": row['strategy_id'],
                        "target_draw": row['target_draw']
                    })
                    continue

                # Insert row
                try:
                    self.insert_row(cursor, row)
                    inserted_count += 1

                    strategy_id = row['strategy_id']
                    if strategy_id not in self.stats['per_strategy']:
                        self.stats['per_strategy'][strategy_id] = 0
                    self.stats['per_strategy'][strategy_id] = self.stats['per_strategy'].get(strategy_id, 0) + 1

                    self.apply_log.append({
                        "row_index": i,
                        "status": "INSERTED",
                        "strategy_id": strategy_id,
                        "target_draw": row['target_draw'],
                        "controlled_apply_id": self.controlled_apply_id
                    })

                    if i % 50 == 0:
                        print(f"Progress: {i}/{len(rows)}")

                except Exception as e:
                    print(f"Row {i}: FAILED TO INSERT ({e})")
                    invalid_count += 1
                    self.apply_log.append({
                        "row_index": i,
                        "status": "INSERT_FAILED",
                        "reason": str(e),
                        "strategy_id": row.get('strategy_id')
                    })

            # Update stats
            self.stats['inserted'] = inserted_count
            self.stats['skipped_existing'] = skipped_count
            self.stats['invalid_rows'] = invalid_count

            # Commit transaction
            cursor.execute("COMMIT")
            conn.close()

        except Exception as e:
            print(f"ERROR: Transaction failed: {e}")
            try:
                cursor.execute("ROLLBACK")
                conn.close()
            except:
                pass
            return False

        # Verify insertion
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
                (self.controlled_apply_id,)
            )
            actual_count = cursor.fetchone()[0]
            conn.close()

            if actual_count != inserted_count:
                print(f"ERROR: Verification failed: expected {inserted_count}, found {actual_count}")
                return False
        except Exception as e:
            print(f"ERROR: Failed to verify insertion: {e}")
            return False

        # Write apply log
        self._write_apply_log()

        # Print summary
        print("\n=== APPLY SUMMARY ===")
        print(f"Inserted: {inserted_count}")
        print(f"Skipped (existing): {skipped_count}")
        print(f"Invalid: {invalid_count}")
        print(f"Total: {inserted_count + skipped_count + invalid_count}")

        print("\n=== Per-Strategy Insert Count ===")
        for strategy_id in sorted(self.stats['per_strategy'].keys()):
            count = self.stats['per_strategy'].get(strategy_id, 0)
            print(f"{strategy_id}: {count}")

        if inserted_count == 200 and invalid_count == 0:
            print("\n✅ APPLY COMPLETE")
            print(f"Controlled Apply ID: {self.controlled_apply_id}")
            return True
        else:
            print("\n❌ APPLY INCOMPLETE: Issues detected")
            return False

    def _write_apply_log(self):
        """Write apply log to file."""
        log_file = f"outputs/replay/v2_artifact_only_apply_log_{self.controlled_apply_id}.jsonl"
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                for entry in self.apply_log:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            print(f"\nApply log written to: {log_file}")
        except Exception as e:
            print(f"ERROR: Failed to write apply log: {e}")

    def rollback(self, apply_id: str) -> bool:
        """Rollback rows inserted with a specific controlled_apply_id."""
        print(f"\n=== V2 ARTIFACT_ONLY Rollback: {apply_id} ===\n")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Count rows to delete
            cursor.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
                (apply_id,)
            )
            count = cursor.fetchone()[0]

            if count == 0:
                print(f"No rows found with controlled_apply_id={apply_id}")
                conn.close()
                return False

            print(f"Found {count} rows to delete")

            # Delete rows in transaction
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute(
                "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
                (apply_id,)
            )
            cursor.execute("COMMIT")

            # Verify deletion
            cursor.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
                (apply_id,)
            )
            remaining = cursor.fetchone()[0]

            conn.close()

            if remaining == 0:
                print(f"✅ Rollback complete: {count} rows deleted")
                return True
            else:
                print(f"❌ Rollback incomplete: {remaining} rows remain")
                return False

        except Exception as e:
            print(f"ERROR: Rollback failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="V2 ARTIFACT_ONLY Controlled Apply")
    parser.add_argument('--dry-run', action='store_true', help='Dry-run mode (no DB write)')
    parser.add_argument('--apply', action='store_true', help='Live apply mode')
    parser.add_argument('--rollback', metavar='APPLY_ID', help='Rollback rows with this apply ID')
    parser.add_argument('--db-path', default='lottery_api/data/lottery_v2.db', help='Database path')
    parser.add_argument('--candidate-rows', default='outputs/replay/v2_artifact_only_candidate_rows_20260514.jsonl',
                       help='Candidate rows JSONL file')

    args = parser.parse_args()

    if not args.dry_run and not args.apply and not args.rollback:
        parser.print_help()
        return 1

    app = V2ArtifactOnlyApply(args.db_path, args.candidate_rows)

    if args.rollback:
        result = app.rollback(args.rollback)
        return 0 if result else 1

    if args.dry_run:
        result = app.dry_run()
        return 0 if result else 1

    if args.apply:
        result = app.apply()
        return 0 if result else 1

    return 1

if __name__ == '__main__':
    sys.exit(main())
