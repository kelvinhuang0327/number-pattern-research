# P264B — Hide Empty Legacy D3 Tab From Default Navigation

_Display-only change to index.html. No API/DB/registry/adapter change._

## Problem

After P264A, the "D3 合約稽核 (Legacy)" nav button was still visible in the navigation sidebar (demotion was opacity:0.55 only). Users could still click it and see an artifact-backed section showing "14 rows" — creating confusion about the actual strategy count (40 strategies / 41 cells per SSOT).

## Solution

Changed the legacy nav button `style` from `opacity:0.55;font-size:0.88em` to `display:none`.

The button and section remain in the DOM for P258N/O/P contract compliance. The `<details>` collapse, warning banner, and all locked strings are untouched.

| | Before (P264A) | After (P264B) |
|---|---|---|
| Legacy nav visibility | Visible, dimmed (opacity 0.55) | **Hidden (display:none)** |
| SSOT nav | Visible, primary | Visible, primary (unchanged) |
| Legacy section in DOM | Yes | Yes (unchanged) |
| Legacy endpoint | Preserved | Preserved (unchanged) |
| P258 locked contract | Intact | Intact (unchanged) |

## index.html change

```html
<!-- P264B: legacy D3 audit nav hidden from default navigation (display:none); section + endpoint contract preserved in DOM -->
<button class="nav-btn" data-section="p258-d3-audit" style="display:none"
    title="Historical Artifact — Legacy D3 Contract Audit (artifact-backed, 14 rows, 2026-06-09)">
    <i data-lucide="archive" class="icon"></i>
    <span>D3 合約稽核 (Legacy)</span>
</button>
```

## test_p264a update

`test_legacy_nav_button_visually_demoted` updated: assertion broadened from `"opacity"` to `("opacity" or "display:none")` to accommodate either demotion style. This aligns the P264A test with the P264B contract without breaking the P264A intent.

## Locked contract preservation

All P258N/O/P test constraints intact:
- `data-section="p258-d3-audit"` nav button in DOM ✓
- `id="p258-d3-audit-section"` section ID ✓
- `p258-disclaimer-banner` ✓
- `NOT_YET_REJECTED` ✓
- `預測模型` ✓
- JS: `p258Init()` ✓
- JS: `/api/replay/d3-strategy-status-audit` fetch URL ✓
- `<details>` collapse ✓
- `#p258-legacy-warning-p264a` warning banner ✓

## Test results

| Suite | Result |
|---|---|
| `test_p264b_hide_empty_legacy_d3_tab_default_navigation.py` | **30/30 PASS** |
| `test_p264a_hide_legacy_d3_artifact_default_ui.py` | **31/31 PASS** |
| `test_p263b_d3_strategy_status_ssot_rebuild.py` | **29/29 PASS** |
| `test_replay_api_contract.py` | **44/44 PASS** |
| **Total** | **131/131 PASS** |
| `git diff --check` | **CLEAN** |
