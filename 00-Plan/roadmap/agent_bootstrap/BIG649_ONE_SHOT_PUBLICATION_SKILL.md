# BIG 6/49 One-Shot Publication Skill

This skill is only for dry-run publication planning and manifest validation.

## Non-Negotiable Rules

- This skill never selects target by itself.
- This skill never publishes real tickets by itself.
- Use the runner, do not manually assemble strategies.
- One Owner authorization = one run.
- One run = one manifest candidate.
- Check duplicate before write.
- Check idempotency before write.
- Check randomness policy before write.
- If deterministic rerun differs, STOP.
- If random strategy lacks seed/policy, STOP.
- If any DB path is touched, STOP.
- If official deadline is needed, the future task must use the primary source and cite it.
- Real publication requires separate explicit Owner authorization.

## Expected Flow

1. Build a dry-run manifest candidate with the frozen 11 BIG / 大樂透 / 6-49 strategies.
2. Validate the manifest schema and ticket shape.
3. Check duplicate publication state before any write.
4. Check idempotency before any write.
5. Check randomness policy before any write.
6. Stop immediately on unexplained nondeterminism.

## Stop Conditions

- Missing strategy
- Extra strategy
- Invalid ticket
- Duplicate manifest conflict
- Unexplained deterministic rerun difference
- Randomness without a recorded seed or policy
- Any DB access attempt
- Any real target selection
- Any real publication action

## Scope Boundary

This skill is a runbook, not a source-of-truth for strategy logic, target selection, or publication.
It is only a guardrail for the dry-run-only runner.

## Real-Publication Pointer

- P280X is dry-run planning.
- For real-publication tooling, see `BIG649_REAL_PUBLICATION_RUNBOOK.md`.
- Real publication remains separate Owner authorization.
