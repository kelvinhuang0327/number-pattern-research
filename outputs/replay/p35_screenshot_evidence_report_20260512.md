# P35 Screenshot Evidence Report — Display-Only Catalog
**Version:** P35 / 2026-05-12  
**Feature:** P25 Display-Only Catalog for Non-ONLINE Strategies  
**Main SHA:** `2e4c1e7`  
**Status:** ✅ ACTUAL_CAPTURED — 7 / 7 screenshots successfully captured

---

## 1. Screenshot Capture Status

| Metric | Value |
|--------|-------|
| **Overall Status** | ✅ ACTUAL_CAPTURED |
| Total target screenshots | 7 |
| Successfully captured | **7** |
| Blocked / Failed | 0 |
| Placeholder remaining | 0 |

**P34 placeholder guide has been superseded by actual captured screenshots.**

---

## 2. Environment

| Item | Value |
|------|-------|
| Main SHA | `2e4c1e7` |
| Branch | `main` (up to date with origin/main) |
| Server method | Python `socketserver.TCPServer` (local static file server, port auto-assigned) |
| API mock | Playwright route interception — all `/api/replay/**` calls mocked; no real backend required; no DB write |
| Browser | Playwright Chromium 1.59.0 / Chrome for Testing 147.0.7727.15 (headless) |
| Viewport | 1280 × 800 |
| Script | `scripts/p35_capture_screenshots.py` |
| Python venv | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv/bin/python3` |
| Output dir | `outputs/replay/screenshots/p35/` |
| Capture summary | `outputs/relay/screenshots/p35/capture_summary.json` |

---

## 3. Screenshot Evidence — Per Lifecycle

### Screenshot 01 — ONLINE Production Mode
**File:** `outputs/replay/screenshots/p35/01_replay_online_production.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Lifecycle filter | 「上線 (ONLINE)」| ✅ 「🟢 上線 (ONLINE)」 |
| Fixture mode | OFF | ✅ "Fixture Mode OFF" button visible |
| Replay result row | PREDICTED record visible | ✅ `期號 99000105 / 2010-12-31 / biglotto_triple_strike / PREDICTED` |
| Disclaimer | 不代表提高中獎率 | ✅ Present |
| No catalog rows | Should not show 無歷史回放資料 | ✅ Absent |

**Body snippet verified:**
```
99000105  2010/12/31  biglotto_triple_strike  [3 8 22 35 38 43]  [4 9 27 36 38 39]  38  1  PREDICTED
```

---

### Screenshot 02 — REJECTED Display-Only
**File:** `outputs/replay/screenshots/p35/02_replay_rejected_display_only.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Lifecycle filter | 「🔴 拒絕 (REJECTED)」 | ✅ |
| Catalog banner text | 此生命週期（REJECTED）策略目前無歷史回放資料 | ✅ |
| Lifecycle badge | 🔴 已拒絕 (REJECTED) | ✅ |
| Strategy entry | Catalog row visible | ✅ `Catalog Example (REJECTED) / example_rejected_01` |
| "無歷史回放資料" | Must appear | ✅ |
| Disclaimer | 不代表預測成績、不構成下注建議 | ✅ |
| No production replay rows | Must NOT appear | ✅ Absent |

**Body snippet verified:**
```
此生命週期（REJECTED）策略目前無歷史回放資料，以下為已登錄策略目錄。
不代表預測成績、不構成下注建議。
— — Catalog Example (REJECTED) / example_rejected_01  🔴 已拒絕 (REJECTED)  無歷史回放資料
```

---

### Screenshot 03 — RETIRED Display-Only
**File:** `outputs/replay/screenshots/p35/03_replay_retired_display_only.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Lifecycle filter | 「⚪ 退役 (RETIRED)」 | ✅ |
| Catalog banner text | 此生命週期（RETIRED）策略目前無歷史回放資料 | ✅ |
| Lifecycle badge | ⚪ 已退役 (RETIRED) | ✅ |
| "無歷史回放資料" | Must appear | ✅ |
| Disclaimer | 不代表預測成績、不構成下注建議 | ✅ |
| No production replay rows | Must NOT appear | ✅ Absent |

**Body snippet verified:**
```
此生命週期（RETIRED）策略目前無歷史回放資料，以下為已登錄策略目錄。
— — Catalog Example (RETIRED) / example_retired_01  ⚪ 已退役 (RETIRED)  無歷史回放資料
```

---

### Screenshot 04 — OBSERVATION Display-Only
**File:** `outputs/replay/screenshots/p35/04_replay_observation_display_only.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Lifecycle filter | 「🟡 觀察中 (OBSERVATION)」 | ✅ |
| Catalog banner text | 此生命週期（OBSERVATION）策略目前無歷史回放資料 | ✅ |
| Lifecycle badge | 🟡 觀察中 (OBSERVATION) | ✅ |
| "無歷史回放資料" | Must appear | ✅ |
| Disclaimer | 不代表預測成績、不構成下注建議 | ✅ |
| No production replay rows | Must NOT appear | ✅ Absent |

**Body snippet verified:**
```
此生命週期（OBSERVATION）策略目前無歷史回放資料，以下為已登錄策略目錄。
— — Catalog Example (OBSERVATION) / example_observation_01  🟡 觀察中 (OBSERVATION)  無歷史回放資料
```

> ⚠️ OBSERVATION 策略不代表推薦候選。顯示 catalog row 僅為審核用途。

---

### Screenshot 05 — OFFLINE Coming Soon
**File:** `outputs/replay/screenshots/p35/05_replay_offline_coming_soon.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Lifecycle filter | 「⚫ 下線 (OFFLINE)」 | ✅ |
| Coming soon message | ⚫ OFFLINE 策略目前無已登錄項目（coming soon） | ✅ Exact match |
| No catalog table | Must NOT show table | ✅ "目錄模式：0 個" |
| No production replay rows | Must NOT appear | ✅ Absent |
| Fixture Mode | OFF | ✅ "Fixture Mode OFF" button |

**Body snippet verified:**
```
⚫ OFFLINE 策略目前無已登錄項目（coming soon）
```

---

### Screenshot 06 — Fixture Mode ON Banner
**File:** `outputs/replay/screenshots/p35/06_fixture_mode_on_banner.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Fixture Mode button | 「✅ Fixture Mode ON」 | ✅ Green/highlighted button visible |
| Fixture banner | Banner with non-production text | ✅ "⚠ FIXTURE MODE — 合成資料、僅供驗收、不代表真實預測" |
| Banner prominence | Visually distinguishable | ✅ Orange/amber banner across full width |
| REJECTED catalog row | Still visible | ✅ 🔴 已拒絕 (REJECTED) row |
| Disclaimer | 不代表預測成績、不構成下注建議 | ✅ |
| DB write | None | ✅ Mocked API, no DB access |

**Fixture banner text confirmed:**
```
⚠ FIXTURE MODE — 合成資料、僅供驗收、不代表真實預測
```

> ✅ Fixture mode banner is clearly visible and unmistakable. Operators cannot confuse fixture data with production truth.

---

### Screenshot 07 — Fixture Mode OFF (Clean Return)
**File:** `outputs/replay/screenshots/p35/07_fixture_mode_off_clean.png`  
**Status:** ✅ PASS

| Check | Expected | Observed |
|-------|----------|----------|
| Fixture Mode button | 「Fixture Mode OFF」 | ✅ |
| Fixture banner | Must NOT appear | ✅ Absent |
| REJECTED catalog still shows | Yes | ✅ display-only catalog row visible |
| Clean state | No fixture residue | ✅ |

---

## 4. Fixture / Production Separation Evidence

| Evidence | Result |
|----------|--------|
| Fixture mode ON: banner "⚠ FIXTURE MODE — 合成資料、僅供驗收、不代表真實預測" | ✅ Confirmed (Screenshot 06) |
| Fixture mode OFF: banner absent | ✅ Confirmed (Screenshots 01/02/03/04/05/07) |
| API calls: fully mocked (no real backend, no DB) | ✅ Confirmed by route interception |
| Fixture mode toggle button clearly labeled | ✅ "✅ Fixture Mode ON" vs "Fixture Mode OFF" |
| No confusion between fixture and production | ✅ Banner is high-visibility orange/amber |

---

## 5. Safety Wording Confirmation

All screenshots contain the following verified UI text:

| Safety Text | Lifecycle | Confirmed |
|-------------|-----------|-----------|
| 「不代表提高中獎率，也不保證任何回放結果」 | ONLINE page header | ✅ |
| 「不代表預測成績、不構成下注建議」 | REJECTED/RETIRED/OBSERVATION | ✅ |
| 「僅供驗收、不代表真實預測」 | Fixture mode banner | ✅ |
| 「coming soon」 | OFFLINE | ✅ |
| No 必勝 / 保證中獎 / 推薦投注 | All screenshots | ✅ 0 hits |

---

## 6. Known Limitations / Notes

| Item | Detail |
|------|--------|
| Mock data used | API calls mocked; shown catalog entries are `example_LIFECYCLE_01` not real registry entries |
| Real registry counts | REJECTED:4, RETIRED:5, OBSERVATION:1, OFFLINE:0 (see registry file) |
| Production screenshot condition | To capture real registry entries: backend must be running; mock removed |
| Backend startup | Pre-existing `ModuleNotFoundError`; not P25/P35 regression |
| `professional-design.css` 404 | Pre-existing; does not affect functionality |
| Screenshot scope | Viewport 1280×800 (above the fold); full page scrolling not captured |

---

## 7. Remaining Manual Steps

None required for basic evidence. Optional next steps:

1. **Real backend run:** Start lottery_api backend, remove mock routing, re-capture to show actual registry entries (4 REJECTED / 5 RETIRED / 1 OBSERVATION)
2. **Full-page scrolls:** Capture below-fold content (registry table, lifecycle counts)
3. **Mobile viewport:** Optional responsive validation

---

## Files Created This Session

| File | Type | Note |
|------|------|------|
| `scripts/p35_capture_screenshots.py` | Python script | Playwright capture script |
| `outputs/replay/screenshots/p35/01_replay_online_production.png` | PNG 258KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/02_replay_rejected_display_only.png` | PNG 259KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/03_replay_retired_display_only.png` | PNG 259KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/04_replay_observation_display_only.png` | PNG 264KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/05_replay_offline_coming_soon.png` | PNG 255KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/06_fixture_mode_on_banner.png` | PNG 252KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/07_fixture_mode_off_clean.png` | PNG 259KB | ✅ Actual capture |
| `outputs/replay/screenshots/p35/capture_summary.json` | JSON | Machine-readable capture results |
| `outputs/replay/p35_screenshot_evidence_report_20260512.md` | Markdown | This report |

---

## Document Version

| Version | Date | Note |
|---------|------|------|
| P35 / v1.0 | 2026-05-12 | Initial — all 7 screenshots ACTUAL_CAPTURED |
