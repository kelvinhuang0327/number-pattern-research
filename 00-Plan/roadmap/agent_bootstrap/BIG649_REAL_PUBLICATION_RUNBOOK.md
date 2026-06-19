# BIG 6/49 Real Publication Runbook

This runbook does not authorize real publication by itself. Real publication
requires separate explicit Owner authorization for one bounded target attempt.

## Authorization And Timing

- Official target and deadline lookup must be primary-source based in the real task.
- One Owner authorization = one target attempt.
- One target attempt = one manifest candidate.
- Outcome unavailable must be verified before generation.
- Publication PR must be before the official deadline.
- The publication PR must not be merged or modified unless separately authorized.
- Branch deletion is unauthorized.

## Pre-Write Guards

- Do not rerun to improve numbers.
- Duplicate guard before write.
- Idempotency guard before write.
- Randomness guard before write.
- Deterministic mismatch = STOP.
- Stochastic without seed/policy = STOP.
- A different manifest for an existing target = STOP.
- Validate the exact 11 frozen strategy IDs, `N=1`, `bet_index=1`, endpoint
  `BIG_ANY_PRIZE_AWARE_WIN`, ticket shape, official source metadata, deadline,
  source/tool digests, and manifest self-hash before write.

## Artifact Convention

- JSON: `outputs/publications/big649/pre_draw/<target_draw>/manifest.json`
- Markdown: `outputs/publications/big649/pre_draw/<target_draw>/manifest.md`
- The target must match the strict BIG draw-ID contract. Path traversal = STOP.
- No overwrite is allowed unless the duplicate guard classifies the candidate as
  `ALREADY_PUBLISHED_SAME_MANIFEST`.

## Hard Boundaries

- No post-draw evaluation in the publication task.
- DB write/copy is unauthorized.
- Strategy promotion, activation, registry mutation, production write,
  controlled apply, and deployment are unauthorized.
- `tools/big649_real_publication_runner.py` is validate-only by default. It does
  not select a target, look up a deadline, generate tickets, write artifacts,
  access a DB, use the network, or create a GitHub PR.
- The future task must supply already-generated strategy outputs. If safe
  strategy generation is not yet implemented through an exact no-DB adapter,
  the real task must STOP. Never invent replacement outputs.
