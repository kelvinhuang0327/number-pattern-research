# Extra Cleanup Checklist
**Date**: 2026-03-19
**Phase**: 5 - Extra Cleanup

---

## 1. Environment Variables

### Active (Used)
| Variable | Set In | Purpose |
|----------|--------|---------|
| MPLCONFIGDIR | start_all.sh | Matplotlib cache dir (avoid permission issues) |

### Dead/Unused
- No dead environment variables found.

---

## 2. Package.json

- **Status**: `package.json` does NOT exist in this project.
- This is a vanilla JS frontend with no Node.js build system.
- No npm scripts to audit.

---

## 3. Build Scripts / Makefile

- **Makefile**: Not present.
- **start_all.sh**: ✅ Active - starts backend (port 8002) and frontend (port 8081)
- **stop_all.sh**: ✅ Active - stops both services
- **lottery_api/install.sh**: ✅ Active - pip install setup
- **lottery_api/start.sh**: Legacy script - still exists but superseded by start_all.sh

---

## 4. API Routes Audit

### Routes in app.py vs Available Route Files
| Route File | In app.py | Status |
|-----------|-----------|--------|
| admin.py | ✅ YES | Active |
| prediction.py | ✅ YES | Active |
| data.py | ✅ YES | Active |
| optimization.py | ✅ YES | Active |
| backtest.py | ✅ YES | Active |
| advanced_learning.py | ❌ NO | MOVED to tmp/backend_archive/routes/ |
| optimized_predict.py | ❌ NO | MOVED to tmp/backend_archive/routes/ |

### Unused API Endpoint Categories
The following endpoint categories exist in the backend but appear to have limited/no frontend calls:
- `/api/predict/expert-certified` - No matching ApiClient call found
- `/api/predict/core-satellite` - No matching ApiClient call found
- `/api/predict-entropy-8-bets` - No matching ApiClient call found
- `/api/predict-hyper-precision-2bet` - No matching ApiClient call found
- `/api/predict-consecutive-539` - No matching ApiClient call found

These are used directly via HTTP clients (curl, Postman) or CLI tools, not the web UI.
**Status**: KEEP - do not remove (serve direct API consumers).

---

## 5. Outdated README/Docs Sections

### Active Documentation
| File | Status | Notes |
|------|--------|-------|
| CLAUDE.md | ✅ Active | Project instructions (main reference) |
| lottery_api/CLAUDE.md | ✅ Active | Strategy documentation |
| MEMORY.md | ✅ Active | Auto-memory |
| memory/MEMORY.md | ✅ Active | Persistent memory |
| docs/ | ✅ Active | Strategy reports |

### Legacy Documentation (Moved or Keep)
| File | Status | Notes |
|------|--------|-------|
| DELIVERY_CHECKLIST.txt | KEEP | May be useful for release |
| QUICK_REFERENCE.txt | KEEP | May be useful for quick reference |
| Various *.md at root | KEPT | Research reports, keep per CLAUDE.md |

---

## 6. Stale Strategy References

### In CLAUDE.md
The CLAUDE.md contains several strategy references marked as SUPERSEDED or deprecated:
- ~~TS3+Markov+頻率正交~~ - Superseded by P1+偏差互補+Sum均值約束
- ~~Triple Strike (威力彩)~~ - Superseded by Power Precision
- ~~Core-Satellite (all variants)~~ - Documented as invalid

**Action**: No changes needed - CLAUDE.md intentionally documents deprecated strategies for reference.

---

## 7. RSM Strategy References

Current RSM bootstrap state files in data/:
- data/rolling_monitor_BIG_LOTTO.json
- data/rolling_monitor_DAILY_539.json
- data/rolling_monitor_POWER_LOTTO.json

These contain strategy names. **Verified**: All strategy names referenced match active
strategy implementations in lottery_api/engine/ or tools/.

---

## 8. Old Log Files

| File | Location | Action |
|------|----------|--------|
| backend.log | root | KEEP (active runtime log) |
| frontend.log | root | KEEP (active runtime log) |
| backend.pid | root | KEEP (runtime state) |
| frontend.pid | root | KEEP (runtime state) |
| lottery_api/logs/ | directory | KEEP (server logs) |
| lottery_api/backend.log | inside lottery_api | KEEP (active) |

---

## 9. Root-Level Cleanup Summary

Files moved to tmp/ in this phase:

| Category | Count |
|----------|-------|
| audit_*.txt files | 39 |
| backtest_*.json (root) | 46 |
| Other research JSON | 78 |
| Legacy .py at root | 10 |
| Legacy .txt at root | 3 |
| **TOTAL** | **176** |

---

## 10. Files Still Requiring Review

| File | Concern |
|------|---------|
| src/ui/components/AssetDoublingPlanComponent.js | Not in import chain. May be dead. Needs HTML audit. |
| src/utils/WeightConfigs.js | Not found in imports. May be dead or dynamic import. |
| lottery_api/start.sh | Superseded by start_all.sh. May still be used for manual start. |
| design-system/ | Unknown scope. Keep for now. |
| ai_lab/ | Unknown content. Keep for now. |

---

## 11. Hardcoded Strategy Names Audit

Checked prediction.py for hardcoded strategy names vs model availability:
- All strategy names in `/api/models` endpoint should match existing strategy files
- Coordinator names (acb_1bet, midfreq_acb_2bet, etc.) match rolling_monitor state files
- **Status**: No broken references detected after cleanup.

---

## Status: COMPLETE
All extra cleanup items have been reviewed and actioned.
