# P329A Browser DOM / Screenshot Evidence

## Tooling used
- Chrome extension (claude-in-chrome): checked via `list_connected_browsers` → **empty list, no browser connected**. Confirms P328A's note that the extension is unavailable in this environment.
- Playwright: not installed (`ModuleNotFoundError: No module named 'playwright'`; Node `require.resolve('playwright')` also fails). Not installed per "no new dependency unless separately authorized."
- Used instead: the system-installed `/Applications/Google Chrome.app` binary in `--headless=new` mode — an existing system tool, no new dependency, no custom protocol client written. Served via a temporary `python3 -m http.server 8931` bound to `127.0.0.1` from the repo root (no repo file written).

## What was captured
1. **Full rendered DOM dump** (`dom_dump_default.html`, `dom_dump_console_run.html`) via `--dump-dom` after `--virtual-time-budget=8000` (JS execution + async fetches settle). This is a real Chromium layout/JS engine render, not a static file read.
2. **Full-page screenshot of default app load** (`screenshot_default_load.png`, 1440x2200 viewport) — shows the app shell rendering correctly (default "upload" nav tab active).

## Required values — confirmed present in the JS-rendered DOM
All grepped directly from `dom_dump_default.html` (line numbers from that file):

| Value | Found | Line |
|---|---|---|
| DESCRIPTIVE_ONLY | ✅ | 3526, 3544 (+ repeated status chips) |
| matched-budget random baseline: computed | ✅ | 3545 |
| raw per-draw equal-budget subsampling: insufficient raw data | ✅ | 3546 |
| hit>=1 -0.0279 | ✅ | 3556 |
| hit>=2 +0.0075 | ✅ | 3556 |
| hit>=3 -0.0091 | ✅ | 3556 |
| single hit>=2 70.0% | ✅ | 3557 |
| triple hit>=2 49.8% | ✅ | 3557 |
| BIG_LOTTO 0 rows pass | ✅ ("0 rows pass the equal-budget screen") | 3558 |
| carrier 34 / 41 | ✅ | 3559 |
| 7 non-carrier | ✅ ("7 are non-carrier") | 3559 |
| no prediction / no betting / does not recommend any numbers to play | ✅ ("not a prediction, not a betting recommendation, and it does not recommend any numbers to play") | 3563 |

## Limitation — pixel screenshot of the toggled-open D5 section specifically
The D5 Budget Bias panel lives inside `<section id="lottery-d5-section" class="section d5-app">`, which the app shows/hides via a nav-tab click handler (`data-section="lottery-d5"`), not a URL parameter or hash route (confirmed by reading `index.html`'s nav-wiring code — no `location.hash`/`URLSearchParams`-driven section selection exists for this tab). Headless Chrome's single-shot CLI (`--dump-dom` / `--screenshot`) cannot perform an interactive click within the same page load; doing so would require a CDP WebSocket client, which is out of scope per the task's explicit ban on "building custom browser tooling" when no existing safe tool (extension, Playwright) is available.

**Net effect:** the DOM dump proves — via a real JS-executing Chromium engine — that every required value renders correctly and is present in the document produced by the already-pushed UI. The screenshot proves the app shell paints correctly in that same engine. A pixel screenshot of the *specific* toggled-open D5 tab was not captured, for the reason above, matching the same class of limitation P328A already documented (browser tooling gap), now narrowed to "DOM-confirmed, click-screenshot not captured" rather than "no browser evidence at all."
