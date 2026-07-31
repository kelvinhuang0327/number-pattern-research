# P555A gap selection

Selected gap: P536L lift-candidate-shortlist UI response handling.

Evidence:
- `index.html` P536L loader used `fetch(...).then(function(r) { return r.json(); })` without checking `r.ok`.
- The route has a tested 500 JSON error path for a missing artifact, but the UI would treat that JSON as successful payload, render empty sections, and clear the status.

Why safe:
- Frontend-only/client-side behavior gap.
- No DB open/write, no migration, no service startup, no scheduler.
- Small focused PR touching the P536L UI script and its existing static contract tests only.
- Native Fetch promises are sufficient; no dependency is justified.

Rejected alternatives:
- SmartBetting/UIManager/ChartManager render hardening, because recent P550A-P553A already covered similar repeated patterns.
- Replay denominator/filter behavior, because `.ai` marks those as user-visible semantics requiring stricter authorization.
