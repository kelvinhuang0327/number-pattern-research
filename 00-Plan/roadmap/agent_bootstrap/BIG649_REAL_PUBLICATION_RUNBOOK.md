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

## No-DB Strategy-Output Adapter

- Before manifest construction, run the no-DB strategy-output adapter against
  caller-supplied history and cutoff data.
- The adapter must supply the exact 11 frozen strategy outputs at `bet_index=1`.
- Missing any frozen strategy callable or output = STOP.
- Any adapter DB access = STOP.
- Any target outcome or result access = STOP.
- Target selection or deadline lookup inside the adapter = STOP.
- Invented or fallback output = STOP.
- Stochastic output without seed and policy = STOP.
- Duplicate complete-ticket conflict = STOP unless a future protocol change is
  separately and explicitly authorized.
- Real target selection, deadline lookup, and publication remain a separate
  explicit Owner authorization.

### P280AJ Deterministic Source-Candidate Selection

Authorized by Owner under P280AJ for the BIG no-DB adapter only:

- Deterministic source-candidate selection is allowed **only** when explicitly
  authorized. When the frozen `bet_index=1` output of a strategy structurally
  duplicates a sibling strategy, the adapter may publish a deterministic
  alternate candidate exposed by that strategy's own scoring/ranking family.
- Each strategy exposes an ordered candidate list; the adapter selects the first
  complete ticket not already claimed by an earlier frozen strategy and fails
  closed (`UNRESOLVED_DUPLICATE_STOP`) if none remain.
- Candidate provenance is required: source callable, candidate index, candidate
  count, selection rule, source digest, and the old/new source hash for every
  changed source file.
- P280D freeze reconciliation is required whenever the source-interface files
  change: update the frozen source `sha256`/`git_blob_sha1` and record the change
  as a forward publication-interface revision, never as retroactive evidence.
- No fabricated or fake fallback output. No outcome-aware selection. No
  historical-best (past-performance) selection. No registry mutation.
- The first real publication remains a separate explicit Owner authorization.

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
