# P2 Lifecycle Backfill Gated Apply Test Plan

## Purpose

Define future tests for a gated apply skeleton without implementing any write path.

## Test Areas

### 1. Apply Skeleton Future Tests

- The skeleton should load an approved manifest but perform no write when the approval artifact is missing
- The skeleton should exit cleanly when the mode is dry-run by default

### 2. No-Write Default Tests

- Default invocation must not write to the DB
- The runtime write guard must stay disabled without explicit approval

### 3. Approval Artifact Missing Tests

- Missing approval artifact must fail fast
- Invalid approval scope must fail fast

### 4. Blocked Row Exclusion Tests

- Blocked rows must never be promoted to the apply set
- Blocked rows must remain audit-only

### 5. Parse-Error Exclusion Tests

- Parse-error rows must never enter the apply set
- Malformed evidence must remain quarantined

### 6. Rollback Simulation Tests

- A simulated apply must produce a rollback record
- Row-level revert data must be retained for each planned change

### 7. DB Snapshot Required Tests

- Apply skeleton must reject runs when no snapshot exists
- Snapshot identifiers must be required in the approval artifact

### 8. Production DB Forbidden Tests

- Production DB access must remain blocked without explicit approval
- No test path may implicitly switch to production DB targets

## Expected Outcome

These tests should support a future no-write apply skeleton and keep execution blocked until a separate approval gate exists.