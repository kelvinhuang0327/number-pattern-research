---
name: frontend-style-refresh
description: "Use when redesigning or refreshing frontend visual style (UI風格改版, redesign, theme refresh, 視覺重做) for index.html and styles_trend_2026.css while preserving existing JS behavior and IDs."
---

# Frontend Style Refresh Skill

## Goal
Deliver a clearly visible visual redesign without breaking behavior.

## Scope
- Primary files:
  - `index.html`
  - `styles_trend_2026.css`
- Optional mirror entry:
  - `tools/web-demos/index.html`

## Guardrails
- Keep all existing element IDs used by JavaScript.
- Avoid changing API calls and runtime logic.
- Prefer class-based styling and CSS variables.
- Preserve mobile usability.

## Workflow
1. Confirm entrypoint and stylesheet loading.
- Verify `index.html` links `styles_trend_2026.css` last.
- Add cache-busting query string when users report no visual changes.

2. Choose one explicit visual direction.
- Examples: editorial-light, terminal-dark, newspaper-contrast, playful-card.
- Do not mix multiple style directions in one pass.

3. Define token layer first.
- Update only `:root` variables (colors, shadows, radius, typography).
- Ensure `body`, `.header`, `.section`, `.card`, and `.btn` have coherent look.

4. Apply component-level overrides.
- Prioritize high-visibility components:
  - header/nav
  - section cards
  - primary/secondary buttons
  - table/panel containers
- Use concise utility classes only when needed.

5. Validate safely.
- Run diagnostics for HTML/CSS files.
- Confirm no duplicate `class` attributes.
- Confirm no inline style regressions in root `index.html`.

6. Verify user-visible outcome.
- Provide a short "what should look different" list.
- If needed, bump cache query version again.

## Quick Commands
```bash
# verify theme file is loaded in root entry
rg -n "styles_trend_2026.css" index.html

# verify no inline style left in root entry
grep -n 'style="' index.html

# start services
./start_all.sh --skip-verify
```

## Done Criteria
- Theme changes are visually obvious at first glance.
- Root page renders without diagnostics errors.
- Core interactions still work (upload, section switch, prediction triggers).
