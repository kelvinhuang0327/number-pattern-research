"""P47 live operator demo runner — 7 scenarios."""
from playwright.sync_api import sync_playwright
import os

OUT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/screenshots/p47"
FRONTEND = "http://127.0.0.1:8081"
results = []

os.makedirs(OUT, exist_ok=True)


def capture(page, name, label):
    path = f"{OUT}/{name}"
    page.screenshot(path=path, full_page=True)
    size = os.path.getsize(path)
    status = "OK" if size > 5000 else "SMALL"
    results.append(f"{status} {label}: {name} ({size}b)")
    print(f"  [{status}] {label} -> {name} ({size}b)")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        extra_http_headers={"Accept-Language": "zh-TW"},
    )
    page = ctx.new_page()
    page.set_default_timeout(15000)

    print("\n=== P47 LIVE OPERATOR DEMO — 7 SCENARIOS ===\n")

    # 1. ONLINE production mode
    page.goto(f"{FRONTEND}/?lifecycle=ONLINE", wait_until="networkidle")
    capture(page, "01_live_online_production.png", "ONLINE production mode")

    # 2. REJECTED display-only
    page.goto(f"{FRONTEND}/?lifecycle=REJECTED", wait_until="networkidle")
    capture(page, "02_live_rejected_display_only.png", "REJECTED display-only")

    # 3. RETIRED display-only
    page.goto(f"{FRONTEND}/?lifecycle=RETIRED", wait_until="networkidle")
    capture(page, "03_live_retired_display_only.png", "RETIRED display-only")

    # 4. OBSERVATION display-only
    page.goto(f"{FRONTEND}/?lifecycle=OBSERVATION", wait_until="networkidle")
    capture(page, "04_live_observation_display_only.png", "OBSERVATION display-only")

    # 5. OFFLINE coming soon
    page.goto(f"{FRONTEND}/?lifecycle=OFFLINE", wait_until="networkidle")
    capture(page, "05_live_offline_coming_soon.png", "OFFLINE coming soon")

    # 6. Fixture mode ON banner
    page.goto(f"{FRONTEND}/?fixture=true", wait_until="networkidle")
    capture(page, "06_live_fixture_on_banner.png", "Fixture mode ON banner")

    # 7. Fixture mode OFF clean
    page.goto(f"{FRONTEND}/", wait_until="networkidle")
    capture(page, "07_live_fixture_off_clean.png", "Fixture mode OFF clean")

    browser.close()

print(f"\n=== RESULT: {len(results)}/7 scenarios captured ===")
ok = sum(1 for r in results if r.startswith("OK"))
print(f"OK: {ok}/7  SMALL: {len(results)-ok}/7")
