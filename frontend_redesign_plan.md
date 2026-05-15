# Frontend Redesign Plan (Phase 3)

Date: 2026-03-13
Target style: shadcn/ui-inspired information architecture while preserving existing behavior.

## Goals
- Keep current business logic and API contracts.
- Reduce orchestration coupling in `App.js`.
- Build migration path from section-driven legacy UI to componentized page modules.

## Proposed Target Structure
- `src/pages/`
- `src/features/`
- `src/components/`
- `src/hooks/`
- `src/services/`
- `src/api/`
- `src/utils/`

## Migration Strategy
1. Stabilize infrastructure
- Shared API origin resolver
- Shared request policy (timeout/retry/error)

2. Extract page controllers
- `upload`, `history`, `simulation`, `prediction`, `smartbetting`, `autolearning`
- Each controller owns section initialization and event binding.

3. Extract feature components
- Dual-bet renderer
- Smart betting generator panel
- Auto-learning schedule panel

4. UI system convergence
- Introduce reusable card/button/badge/tabs patterns aligned with shadcn semantics
- Keep existing CSS classes as compatibility layer during migration

5. Final consolidation
- Trim dead adapters after validation windows pass
- Move hidden/legacy flows to feature flags

## Non-Goals
- No backend API contract changes.
- No immediate framework migration in this phase.
