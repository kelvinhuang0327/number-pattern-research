# P559A Gap Selection

Selected gap: `src/services/ApiClient.js` left the per-request abort timer uncleared when `fetch()` or response JSON handling threw before the successful response path.

Why this is safe and small:
- Client-only behavior; no service startup, scheduler, DB open, DB write, migration, generated rows, or deployment required.
- One narrow correctness fix in the shared API client retry loop.
- Focused static tests cover the timeout cleanup contract without network calls.
- Native `AbortController`/`clearTimeout` are already used; no external dependency is justified.

Excluded areas:
- PR #444 is hard-excluded and was not touched.
- Replay denominator/scope semantics, prediction methodology, p273a files, `.ai`, governance docs, DB/data/runtime files, and prior repeated AutoFetch/AutoLearning/SmartBetting patterns were not selected.
