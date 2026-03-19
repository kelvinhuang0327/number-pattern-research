# UI Design Rules (Phase 3)

Date: 2026-03-13
Direction: shadcn/ui-inspired systemized patterns (framework-agnostic in current stack)

## Design Tokens
- Use CSS variables for color, spacing, radius, elevation.
- Keep semantic tokens: `--bg`, `--card`, `--muted`, `--primary`, `--danger`, `--success`.

## Component Rules
- Buttons: primary, secondary, ghost, destructive variants.
- Cards: consistent padding/radius/border hierarchy.
- Inputs/selects: unified focus, disabled, error states.
- Badges: status and confidence labels only.

## Interaction Rules
- All async actions must show loading state and disabled button.
- Toast/notification copy should be concise and action-oriented.
- Hidden legacy features should not break deep links/events.

## Accessibility Rules
- Maintain keyboard focus visibility.
- Avoid color-only status communication.
- Ensure text contrast for all status badges.

## Migration Compatibility
- Existing class names can coexist; add new utility classes progressively.
- Do not rename DOM IDs tied to existing JS handlers in this phase.
