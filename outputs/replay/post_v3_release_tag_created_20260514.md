# Post-V3 Release Tag Closure Report
Generated: 2026-05-14T17:11:17+08:00

## Classification
**POST_V3_RELEASE_TAG_CREATED**

---

## 1. Tag Details
| 項目 | 值 |
|------|----|
| Tag name | `post-v3-replay-lifecycle-release-20260514` |
| Tag type | Annotated |
| Tag object | `b48daf4abdf806cba3570d0fbe5d9d74d090ce35` |
| Tag target (commit) | `5809445472bcec0cf9430340b1bfb67ca520e206` |
| Tag message | Post-V3 replay lifecycle release: PR97 merge, truth-level API contract, UI truth badges, verified replay rows and tombstones |
| Remote | `origin` (https://github.com/kelvinhuang0327/number-pattern-research.git) |
| Push status | **PUSHED** ✓ |

---

## 2. PR #97 Merge Commit
| 項目 | 值 |
|------|----|
| PR | #97 `fix(replay): close Post-V3 truth-level API contract` |
| Merge commit | `2ff4422e3b4269dbcda776e303f4c9f7c3dd2d6f` |
| Merged at | 2026-05-14T08:01:27Z |
| Branch | `post-v3-replay-lifecycle-closure` → `main` (deleted after merge) |

---

## 3. UI Truth Badge Patch Commit
| 項目 | 值 |
|------|----|
| Commit | `5809445472bcec0cf9430340b1bfb67ca520e206` |
| Message | `docs(replay): add PR97 post-merge API regression + UI smoke reports + truth badge patch` |
| Files | `index.html`, `outputs/replay/post_v3_pr97_postmerge_api_regression_20260514.json`, `outputs/replay/post_v3_pr97_postmerge_ui_smoke_20260514.md`, `outputs/replay/post_v3_pr97_merged_waiting_tag_authorization_20260514.md` |
| Note | This commit is the tag target (main HEAD at tag time) |

---

## 4. API Regression Result
| Tier | Strategies | Result |
|------|-----------|--------|
| V1 EXECUTABLE_NOW | 6/6 | **PASS** ✓ |
| V2 ARTIFACT_ONLY | 4/4 | **PASS** ✓ |
| V3 CODE_MISSING | 6/6 | **PASS** ✓ |
| **Total** | **16/16** | **ALL PASS** ✓ |

---

## 5. pytest Result
| Suite | Result |
|-------|--------|
| `tests/test_replay_truth_level_contract.py` | **PASS** ✓ |
| `tests/test_replay_api_contract.py` | **PASS** ✓ |
| **Total** | **81/81 passed** (1 deprecation warning, non-blocking) |

---

## 6. DB Baseline (lottery_api/data/lottery_v2.db — read-only, unchanged)
| Category | Expected | Actual | Match |
|----------|---------|--------|-------|
| V1 `controlled_apply_id=20260514033100-13acaf34996e` | 300 | **300** | ✓ |
| V2 `controlled_apply_id=20260514134953-cf683424` | 200 | **200** | ✓ |
| legacy `controlled_apply_id IS NULL` | 460 | **460** | ✓ |
| **total** | 960 | **960** | ✓ |

truth_level distribution:
- `REGENERATED_RETROSPECTIVE`: 300 rows (V1)
- `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`: 200 rows (V2)
- `NULL` (legacy): 460 rows

---

## 7. Browser Smoke Summary
| Strategy | Tier | Badge | Rows |
|----------|------|-------|------|
| `biglotto_deviation_2bet` | V1 | REGENERATED_RETROSPECTIVE | ✓ |
| `biglotto_triple_strike` | V1 | REGENERATED_RETROSPECTIVE | ✓ |
| `daily539_f4cold` | V1 | REGENERATED_RETROSPECTIVE | ✓ |
| `biglotto_ts3_acb_4bet` | V2 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | ✓ |
| `power_shlc_midfreq` | V2 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | ✓ |
| `acb_1bet` | V3 | tombstone / 0 rows | ✓ |
| `acb_markov_midfreq_3bet` | V3 | tombstone / 0 rows | ✓ |

---

## 8. Remaining Risks
- Static frontend requires hard-refresh after deploy (browser cache)
- Legacy NULL rows display no badge by design; not a bug
- `renderTruthLevelBadge()` has UNKNOWN fallback for any future unmapped values
- Backend must be started from `LotteryNew-clean/` root to resolve `lottery_api/data/lottery_v2.db` correctly

---

## 9. Files Modified / Committed in This Release
| File | Change |
|------|--------|
| `lottery_api/routes/replay.py` | fix: truth-level API contract (PR #97) |
| `index.html` | fix: render truth_level badges for V1/V2 rows |
| `scripts/post_v3_replay_api_regression.py` | regression script |
| `tests/test_replay_truth_level_contract.py` | new test suite |
| `outputs/replay/post_v3_pr97_postmerge_api_regression_20260514.json` | post-merge gate evidence |
| `outputs/replay/post_v3_pr97_postmerge_ui_smoke_20260514.md` | UI smoke report |
| `outputs/replay/post_v3_release_tag_gate_api_regression_20260514.json` | tag gate evidence |
| `outputs/replay/post_v3_release_tag_created_20260514.md` | this file |

---

## 10. Final Classification
```
POST_V3_RELEASE_TAG_CREATED
```

Tag `post-v3-replay-lifecycle-release-20260514` pushed to origin at commit `5809445`.
All gates passed. Post-V3 replay lifecycle closure complete.

---

## 11. Next Executable Prompt
No further action required for Post-V3 release.

For future sessions, next research trigger:
- **200期 per-agent tracking**（weibull_gap/markov2 降權評估，L77）
- PSI monitoring次輪：DAILY_539 PSI WARNING 持續追蹤
