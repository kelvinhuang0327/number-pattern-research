# LotteryNew — Converged Master Roadmap (2026-2027)

> ⚠️ SUPERSEDED 2026-05-07: 本檔的 P0–P3 priority 已被 `00-LotteryPlan/20260507/lottery_roadmap_20260507.md` 取代；P0-02/04/06 與 GOV-01 全部完成。Locked Invariants、Stop List、四層定位仍適用。本檔保留為歷史版本。

**版本**: Converged v1.0
**基準日期**: 2026-05-04
**Status**: SUPERSEDED by `00-LotteryPlan/20260507/lottery_roadmap_20260507.md`
**前身**: `MASTER_ROADMAP_20260503.md`
**收斂原則**: 已完成項目不重列為待辦；只減不增；每 Phase 有可執行 prompt。

---

## 1. Executive Decision

### 原 roadmap 同意程度：約 85%

**正確之處（保留）：**
- Phase 順序：Safety → Architecture → Science → Self-learning → Framework 正確
- 彩票定位轉移：statistical lab + agent platform + backtest framework seed ✅
- No-audit-no-call 作為平台 invariant ✅
- EvidenceCollector v0.1 早期啟動（不等 Month 6）✅
- Production mutation 雙人確認 ✅
- Rollback 禁止自動執行 ✅

**需要修正（已修正於本文）：**

| 原 roadmap 問題 | 修正方式 |
|----------------|---------|
| Phase -1 Recovery 未列出 | 已補 Phase -1，但今已完成 → 標記 DONE |
| Phase 0 部分項目混在一起 | 已拆分，並標明哪些已完成 |
| 30-day 計畫未扣除已完成工作 | 重新以今日為起點計算 |
| EvidenceCollector 列為 Month 6–9 | 移至 Day 30–60 視窗 |
| 原 backlog P0-01/03 仍列為 pending | 已完成，移除 |
| GOV-01 (LLM caps) 列為 P1 | 已完成，移除 |

**最重要的修正：** 把今日日期（2026-05-04）作為起點重算 30/60/90 day plan。不重複已完成工作。

**現在最該做的第一件事：** Outcome Gate Unified Interface（P0-02），因為它是 production safety 的最後一塊未完成拼圖，且風險低、收益高。

---

## 2. Corrected North Star

LotteryNew 不再是「彩票預測系統」。

**新定位（四層）：**

```
Layer 1: Statistical Validation Lab
  → 任何策略必須通過 v2 predict-vs-actual + permutation + Bonferroni + BH-FDR
  → 彩票研究進入 maintenance-only；NO SIGNAL 是科學成功，不是失敗

Layer 2: Agent Orchestration Platform  
  → Planner / Worker / Light Worker / CTO / Copilot-Daemon
  → LLM caps enforced, audit mandatory, scheduler default-off
  → Evidence-driven local planner replaces backlog-driven human queue

Layer 3: Safe Autonomous Scheduling System
  → Evidence → Score → Task → Cap Guard → Audit → Execute → Outcome
  → Production mutations require human confirmation always
  → Rollback requires CTO approval, never automatic

Layer 4: Transferable Backtesting Framework
  → tools/backtest_framework/ seed project
  → permutation_null / walk_forward_oos / circular_bias_detector / leakage_detector
  → Applicable to Stock / Betting / Novel / A-B testing
```

**這個定位的理由：**
- 彩票本身 ROI 極低，已有三款 NO SIGNAL 結論；方法論資產遠比任何策略更有價值
- Orchestrator / LLM Governance / Rollback Guard 已具備平台輪廓，值得繼續深化
- Backtest framework 的 circular-bias detector、leakage detector、permutation null 等工具在 Stock / Betting 有明確遷移路徑

---

## 3. Completed Items Registry (已完成，移除出 Next Work)

以下項目已驗證完成，**不再列入任何 pending 清單**：

| 原 ID | 原名稱 | 完成日期 | 驗證證據 | Action |
|-------|-------|---------|---------|--------|
| Phase -1 | H6 false rollback restore | 2026-05-04 | active=H6_gate_mk20→ew85, rollback_status=ACTIVE | DONE_REMOVE_FROM_NEXT |
| P0-01 | Rollback guard config-managed module | 2026-05-04 | `orchestrator/rollback_guard.py`, 88 tests pass, API verified | DONE_KEEP_AS_INVARIANT |
| P0-03 | No-audit-no-call CI gate | 2026-05-04 | `tests/test_no_audit_no_call_ci.py`, scanner, allowlist, 64 tests | DONE_KEEP_AS_INVARIANT |
| P0-05 | Restore script dry-run / backup | 2026-05-04 | `h6_pre_restore_backup.json`, `h6_restore_execution_result.md` | DONE_KEEP_AS_INVARIANT |
| GOV-01 | LLM caps enforcement per-role/provider | 2026-05-04 | `orchestrator/llm_caps.py`, 33 tests, `/api/orchestrator/llm-caps/status` | DONE_KEEP_AS_INVARIANT |
| GOV-01+ | No-cap-no-call CI gate | 2026-05-04 | cap → audit → subprocess order verified in all call sites | DONE_KEEP_AS_INVARIANT |
| — | Worker GPT-5 mini config | 2026-05-04 | `worker_copilot_model=gpt-5-mini`, 12 tests | DONE_REMOVE_FROM_NEXT |
| — | Safe defaults configured | 2026-05-04 | scheduler_enabled=0, planner=off, CTO=local, safe-run=on | DONE_KEEP_AS_INVARIANT |
| — | LLM usage dashboard | 2026-05-04 | Planner/Worker/CTO summary, Copilot focus, Top tasks, Recent calls | DONE_REMOVE_FROM_NEXT |

**Locked Invariants（以下不得回退，CI gate 強制）：**
- ✅ no-audit-no-call (scanner + allowlist + 64 tests)
- ✅ no-cap-no-call (check_llm_cap before all external calls)
- ✅ rollback guard config-managed (min_outcomes=5, 88 tests)
- ✅ scheduler default-off
- ✅ planner external LLM cap=0
- ✅ CTO external LLM cap=0
- ✅ production write requires --confirm-production-outcome

---

## 4. Updated Priority Table (P0/P1/P2/P3/STOP)

### P0 — Must Do Next (Day 1–30 from 2026-05-04)

| ID | Item | Reason | Dependency | Acceptance Criteria |
|----|------|--------|------------|---------------------|
| **P0-02** | Outcome Gate Unified Interface | Last missing production safety piece; per-game custom paths are risk | None | `orchestrator/outcome_gate.py`, 3 games unified, 100% tests |
| **P0-04** | Stale RUNNING Lock Auto-release | Worker crash = stuck lock = blocked queue; risk is real | None | mock crash test passes; no stale lock >5 min |
| **P0-06** | EvidenceCollector v0.1 | 3 sources only (rollback_false_positive, llm_usage_high, missing_outcomes) | P0-02, P0-04 done preferred | 3 sources → EvidenceItem; unit tests pass |

### P1 — Do Soon (Day 30–60)

| ID | Item | Reason | Dependency | Acceptance Criteria |
|----|------|--------|------------|---------------------|
| **P2-01** | Randomness Audit Final Verdict | Closes lottery research; enables maintenance-only decision | None | `wiki/system/randomness_final_verdict.md`, 3 games, Bonferroni+BH-FDR |
| **P2-03** | Hypothesis Registry CLI | Prevents post-hoc correction bypass; low effort, high governance value | None | `registry/hypotheses.jsonl` + CLI; strategy_eval needs --hypothesis-id |
| **P2-04** | Circular-bias Detector CI Gate | Prevents re-introducing v1 circular-match bias | None | `tests/test_no_circular_match.py`; passes on current, fails on fixture |
| **P2-02a** | Strategy Evaluation Framework v0.5 | Pre-requisite for scientific closure | P2-01 | CLI runs multi-window+perm+Bonferroni+BH-FDR on 1 game |
| **P1-01** | Module boundary doc | Architecture clarity; low effort | None | `wiki/system/module_boundaries.md` |

### P2 — Do Later (Day 60–90)

| ID | Item | Reason | Dependency | Acceptance Criteria |
|----|------|--------|------------|---------------------|
| **P3-01b** | EvidenceCollector v0.3 (6 sources) | Expand from v0.1 (3 sources) to 6 | P0-06 | 6 sources: failed_tests, stale_data, missing_outcomes, monitoring_degraded, llm_usage_high, strategy_no_signal |
| **P2-02b** | Strategy Evaluation Framework v1 | Full OOS automation | P2-02a | one-command WF OOS; leakage detector integrated |
| **P2-05** | Leakage Detector | DataLeakageError on RollingBacktester | P2-02a | test passes; integrated into backtest flow |
| **P1-02a** | BFF API v0.5 | UI consolidation foundation | P1-01 | `/api/bff/` handles top-3 UI data sources |
| **P1-06a** | Dashboard consolidation v0.5 | Reduce multi-entry confusion | P1-02a | single nav entry, 3 sub-pages merged |

### P3 — Defer (Month 3+)

| ID | Item | Reason |
|----|------|--------|
| P1-03 | Schema versioning + migration registry | Correct but complex; lower urgency than science closure |
| P1-04 | Config management (pydantic) | Already have DB settings; incremental |
| P3-01c | EvidenceCollector v1 (18 sources) | Build up from v0.1 → v0.3 → v1 |
| P3-04 | Local Planner v2 | Needs EvidenceCollector v0.3+ stable first |
| P4-01 | tools/backtest_framework/ v0.1 | After P2-02b (Strategy Eval Framework v1) proves the API |
| P4-03/04 | Stock / Betting POC | After backtest_framework v0.1 |
| GOV-02 | Token/premium/rate limit unified parser | Minor optimization, not blocking |
| GOV-03 | Copilot overuse alert | Enhancement to existing cap system |

### STOP — Do Not Pursue

| Item | Reason |
|------|--------|
| historical-pool max-hit evaluation | v1 INVALID; Circular-Match Bias root cause confirmed |
| Uncorrected grid search conclusions | Violates multiple-comparison correction invariant |
| SHORT_MOMENTUM strategy promotion | Pattern discredited (L-series lessons) |
| Any strategy without McNemar vs incumbent | Validation gate violation |
| Gap Dynamic Threshold pseudo-signal | L07 封項 |
| Day-of-Week effect research | L27 封項 |
| Cross-game conclusion borrowing | L21 封項 |
| "Guaranteed lottery win rate improvement" | Scientific impossibility given NO SIGNAL verdict |
| Neighbor co-occurrence / Lift<1.0 injection | L08 封項 |

---

## 5. Oversized Items — Split Plan

| Oversized Item | Problem | Split Into | First Step (do now) |
|---------------|---------|------------|---------------------|
| EvidenceCollector (18 sources) | Too many unknowns; 18 sources not tested | v0.1 (3 sources) → v0.3 (6) → v1 (18) | v0.1: rollback_false_positive, llm_usage_high, missing_outcomes |
| Strategy Evaluation Framework v1 | Full OOS + all corrections complex | v0.5 (single game, no WF OOS) → v1 (full) | v0.5: multi-window + perm + Bonferroni + BH-FDR, 1 game |
| BFF API "full migration" | All endpoints at once = breakage risk | v0.5 (top-3 data sources) → v1 (all) | v0.5: summary + strategies + tasks |
| tools/backtest_framework/ full extraction | 9 modules at once = over-engineering | Start with circular_bias_detector + leakage_detector (already exist as scripts) | Extract 2 modules, test standalone, then expand |
| UI Dashboard "full consolidation" | All pages at once = regression risk | v0.5 (nav + 3 merged sub-pages) → v1 (all) | v0.5: consolidate System Health + LLM Usage + Strategies |
| Local Planner v2 (full evidence-driven) | Needs EvidenceCollector stable | Local Planner v0.5 (reads from evidence/items.jsonl, scores, dedupes) | After EvidenceCollector v0.3 |

---

## 6. Revised 30 / 60 / 90 Day Plan (from 2026-05-04)

### Next 30 Days (2026-05-04 → 2026-06-03)

**Target Outcome**: Phase 0 complete; Phase 2 scientific closure started; EvidenceCollector seeded

| # | Deliverable | Tests | Success Criteria |
|---|-------------|-------|-----------------|
| 1 | `orchestrator/outcome_gate.py` — 3-stage unified interface | `tests/test_outcome_gate.py` 100% | 3 games use same interface; no per-game custom code |
| 2 | Stale RUNNING lock auto-release on startup | mock crash test | No stale lock >5 min after worker death |
| 3 | `orchestrator/evidence/collector.py` v0.1 (3 sources) | 3 unit tests, each source produces EvidenceItem | Non-empty EvidenceItem stream from known fixture |
| 4 | `wiki/system/randomness_final_verdict.md` draft | Script run logged | 3-game verdict draft with Bonferroni+BH-FDR applied |
| 5 | `registry/hypotheses.jsonl` + CLI v0.1 | CLI test | register + list commands work; 2 example hypotheses |

**Measurable Success Criteria (Day 30):**
- ✅ outcome_gate used by all 3 games
- ✅ rollback false positive count = 0 (guard invariant holds)
- ✅ EvidenceCollector produces ≥1 EvidenceItem/day on staging
- ✅ Randomness audit draft written
- ✅ Hypothesis registry seeded

---

### Next 60 Days (2026-06-03 → 2026-07-03)

**Target Outcome**: Scientific closure progressing; Architecture doc started; Strategy Eval v0.5

| # | Deliverable | Tests | Success Criteria |
|---|-------------|-------|-----------------|
| 1 | `tests/test_no_circular_match.py` CI gate | Catches fixture violation | Current codebase PASS; v1-style code FAIL |
| 2 | Strategy Evaluation Framework v0.5 (`tools/strategy_eval/`) | CLI test on power_lotto | One-command multi-window + perm + Bonferroni + BH-FDR |
| 3 | EvidenceCollector v0.3 (6 sources) | 6 unit tests | 6 sources producing EvidenceItems |
| 4 | `wiki/system/module_boundaries.md` | None required | Module boundaries defined and linked from README |
| 5 | BFF API v0.5 (`api/bff.py`) | Smoke test | Top-3 UI data sources routed through BFF |

**Measurable Success Criteria (Day 60):**
- ✅ Circular-bias CI gate blocking v1-style code
- ✅ strategy_eval CLI runs end-to-end on 1 game
- ✅ EvidenceCollector v0.3 running daily on staging
- ✅ UI 60% using BFF

---

### Next 90 Days (2026-07-03 → 2026-08-02)

**Target Outcome**: Scientific closure complete; Architecture v0.5; EvidenceCollector → Local Planner pipeline seeded

| # | Deliverable | Tests | Success Criteria |
|---|-------------|-------|-----------------|
| 1 | Strategy Evaluation Framework v1 (+ WF OOS + leakage detector) | Full test suite | One-command WF OOS on 3 games; leakage error on bad input |
| 2 | `wiki/system/randomness_final_verdict.md` final | 3-game verdict | Each verdict: draws_count, tests_run, raw_p, Bonferroni_p, BH-FDR_q, VERDICT |
| 3 | Dashboard consolidation v0.5 | Smoke | Single nav, 3 merged sub-pages, 0 dead links |
| 4 | Local Planner v0.5 (evidence-driven, no LLM) | 7-day run metric | ≥50% tasks from Local Planner; no same task type >50%/day |
| 5 | `tools/backtest_framework/` v0.1 skeleton (circular_bias_detector + leakage_detector extracted) | Tests | 2 modules standalone-testable; lottery v2 reproduces NO SIGNAL |

**Measurable Success Criteria (Day 90):**
- ✅ Randomness audit final verdict written for all 3 games
- ✅ Strategy Evaluation Framework v1 complete
- ✅ Local Planner v0.5 running (external LLM tasks <50%/day)
- ✅ backtest_framework v0.1 with 2 core modules
- ✅ All production mutations still require manual confirmation (invariant holds)

---

## 7. Stop / Maintenance Decisions

### Research Direction Classification

| Research Direction | Decision | Reason | Gate If Continued |
|-------------------|----------|--------|-------------------|
| Randomness audit (per-game, periodic) | **CONTINUE** | Every 50 draws; enables maintenance-only decision | Run only when ≥50 new draws; output to wiki |
| Payout EV / unpopular-number advisory | **MAINTENANCE-ONLY** | Advisory value; no active signal research | Advisory output only; no betting recommendation |
| Physical bias candidate detection | **MAINTENANCE-ONLY** | Per-ball drift monitoring only | Advisory only; flag if >3σ drift |
| Covering design / wheel system | **MAINTENANCE-ONLY** | Pure mathematical optimization; no prediction | Only if user-requested |
| Strategy retire policy automation | **CONTINUE** (P2-06) | Cleans up ADVISORY_ONLY strategies | Needs Hypothesis Registry CLI first |
| Predict-vs-actual v2 SOP | **CONTINUE** | Mandatory gate for any strategy promotion | Already enforced; keep as CI gate |
| Multiple Testing Registry | **CONTINUE** (P2-03) | Prevents post-hoc bypass | Required before any new strategy claim |
| Circular-bias detector | **CONTINUE** → CI gate | Foundation for everything else | P2-04 |
| Walk-forward OOS automation | **CONTINUE** → P2-02b | Prevents in-sample overfitting | Part of Strategy Eval Framework v1 |
| Prediction-signal exploration (new) | **STOP** | NO SIGNAL across all 3 games; Bonferroni+BH-FDR applied | Only resumes if ≥200 new draws AND new methodology |
| historical-pool max-hit | **STOP** | v1 INVALID; Circular-Match Bias confirmed | Never |
| Grid search without correction | **STOP** | Violates platform invariant | Never |
| SHORT_MOMENTUM / LATE_BLOOMER promotion | **STOP** | L-lessons pattern discredited | Never |
| Gap Dynamic Threshold | **STOP** | L07 封項 | Never |
| Day-of-Week effect | **STOP** | L27 封項 | Never |

---

## 8. Governance Rules — Now Locked

These are **permanent platform invariants**. Any PR/change violating these must be rejected by CI.

1. **no-audit-no-call**: Every external LLM call must pass through `provider_audit_guard.py`'s `audit_external_llm_call()`. Static scanner (`tools/scan_external_llm_calls.py`) enforces this in CI.

2. **no-cap-no-call**: `check_llm_cap()` must be called before every external LLM call. Enforcement order: cap_check → audit_attempt → execute → audit_result.

3. **rollback-guard invariant**: `evaluate_rollback_guard()` in `orchestrator/rollback_guard.py`. Thresholds are config-managed in `orchestrator_settings`. min_outcomes_for_rollback=5. One-outcome rollback is permanently blocked.

4. **scheduler-default-off**: `scheduler_enabled=0` in DB. Any change requires explicit user action.

5. **planner-external-llm-cap=0**: `planner_external_llm_daily_cap=0` in DB. Planner is local-only by default.

6. **production-write-requires-confirm**: All production DB writes require `--write` AND `--confirm-production-outcome`. No automatic writes.

7. **no-auto-rollback**: Rollback execution requires CTO review and human approval. `_apply_live_rollback_swap()` only called on explicit confirmation.

8. **multiple-comparison-correction-mandatory**: Bonferroni + BH-FDR required for any strategy promotion. This is enforced by Hypothesis Registry.

9. **circular-bias-ci-gate**: No v1-style historical-pool max-hit allowed. Enforced by `tests/test_no_circular_match.py`.

10. **backup-before-restore**: Any restore script requires backup before write. `outputs/` backup must exist.

---

## 9. Next 10 Agent Prompts

### Prompt 1 — Outcome Gate Unified Interface (P0, Day 1–7)

```
# ROLE
You are a LotteryNew production safety engineer.

# TASK
Create orchestrator/outcome_gate.py — a unified 3-stage outcome recording interface
for all games (big_lotto / power_lotto / daily_539).

Three stages: dry_run → isolated_db → production_with_confirm
- Each stage emits audit event before action.
- Production stage requires --write AND --confirm-production-outcome.
- No skipping isolated_db stage.
- All 3 games must call the same interface; remove per-game custom code.

# STRICT RULES
- Do not write production DB without both flags.
- Do not call external LLM.
- Do not modify active_strategy_state.
- Do not trigger rollback.
- No automatic production write.
- Scheduler remains disabled.

# FILES TO INSPECT
- scripts/h6_record_outcome.py
- lottery_api/engine/h6_live_monitor.py
- orchestrator/db.py
- tests/ (existing outcome tests)

# ACCEPTANCE CRITERIA
- tests/test_outcome_gate.py 100% coverage.
- 3 games tested end-to-end with isolated DB.
- Production write audit events match write events 1:1.
- dry_run produces no DB writes (verified via isolated DB).

# FINAL VERDICT OPTIONS
OUTCOME_GATE_UNIFIED_VERIFIED | OUTCOME_GATE_PARTIAL | OUTCOME_GATE_REQUIRES_FIX
Expected: OUTCOME_GATE_UNIFIED_VERIFIED
```

---

### Prompt 2 — Stale RUNNING Lock Auto-Release (P0, Day 7–14)

```
# ROLE
You are a LotteryNew orchestrator reliability engineer.

# TASK
Add stale RUNNING lock detection and auto-release on orchestrator startup.

For each task with status=RUNNING:
- Check if the PID is still alive (os.kill(pid, 0) or equivalent).
- If dead: mark task FAILED with failure_reason=lock_timeout.
- Release the lock.
- Emit failure_taxonomy event LOCK_TIMEOUT.
- Write audit event before each release.

# STRICT RULES
- Do NOT release locks for tasks with alive PIDs.
- Do NOT auto-restart failed tasks (only mark FAILED).
- Do NOT call external LLM.
- Scheduler remains disabled.
- No production strategy state modifications.

# FILES TO INSPECT
- orchestrator/worker_tick.py
- orchestrator/db.py
- orchestrator/api.py
- tests/ (existing lock tests)

# ACCEPTANCE CRITERIA
- Mock crash test: kill worker PID → lock auto-released within 1 startup cycle.
- No live-PID task is released.
- LOCK_TIMEOUT audit event written for each released lock.
- All existing tests still pass.

# FINAL VERDICT OPTIONS
STALE_LOCK_RELEASE_VERIFIED | STALE_LOCK_RELEASE_PARTIAL | STALE_LOCK_RELEASE_REQUIRES_FIX
Expected: STALE_LOCK_RELEASE_VERIFIED
```

---

### Prompt 3 — EvidenceCollector v0.1 (P0, Day 14–21)

```
# ROLE
You are a LotteryNew self-learning scheduler engineer.

# TASK
Implement orchestrator/evidence/collector.py covering 3 evidence sources:

1. rollback_false_positive
   - Source: llm_audit_events / rollback history
   - Signal: rollback proposed but guard blocked it (should_rollback=False but triggered)
   
2. llm_usage_high
   - Source: /api/orchestrator/llm-caps/status
   - Signal: any role at >80% of daily cap
   
3. missing_outcomes
   - Source: active_strategy_state / live_strategy_outcomes
   - Signal: next_draw has passed but no outcome recorded

Each source emits EvidenceItem (schema below):
{
  "evidence_id": "uuid",
  "source": "rollback_false_positive|llm_usage_high|missing_outcomes",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "confidence": 0.0–1.0,
  "affected_module": "...",
  "evidence_text": "human readable",
  "suggested_task_type": "...",
  "requires_llm": false,
  "dedupe_key": "evidence:{source}:{module}:{utc_date}",
  "first_seen": "ISO8601",
  "last_seen": "ISO8601",
  "occurrence_count": 1
}

Persist to evidence/items.jsonl (append-only, newline-delimited JSON).

# STRICT RULES
- Pure function: collect(snapshot) -> list[EvidenceItem]
- No external LLM calls.
- No production DB writes (only reads + evidence/items.jsonl append).
- requires_llm=false by default.
- dedupe_key follows UTC date convention.
- Scheduler remains disabled.

# FILES TO INSPECT
- orchestrator/llm_caps.py (get_cap_status)
- orchestrator/rollback_guard.py (evaluate_rollback_guard)
- orchestrator/db.py
- tests/test_llm_caps.py (example pattern)

# ACCEPTANCE CRITERIA
- Each of 3 sources has unit test producing ≥1 EvidenceItem on known fixture.
- evidence/items.jsonl appended correctly (no truncation).
- Duplicate evidence same day is deduplicated.
- Non-empty EvidenceItem stream on staging read.

# FINAL VERDICT OPTIONS
EVIDENCE_COLLECTOR_V01_VERIFIED | EVIDENCE_COLLECTOR_PARTIAL | EVIDENCE_COLLECTOR_REQUIRES_FIX
Expected: EVIDENCE_COLLECTOR_V01_VERIFIED
```

---

### Prompt 4 — Randomness Audit Final Verdict (P1, Day 21–30)

```
# ROLE
You are a LotteryNew statistical validation researcher.

# TASK
Run randomness audit for all 3 games and produce final verdicts.

For each of {big_lotto, power_lotto, daily_539}:
1. Run scripts/randomness_audit.py with full historical data.
2. Apply Bonferroni correction across 3 games.
3. Apply BH-FDR within-game across all sub-tests.
4. Write verdict to wiki/system/randomness_final_verdict.md:
   Game | draws_count | tests_run | raw_p | bonferroni_p | bh_fdr_q | VERDICT
   VERDICT = SIGNIFICANT_BIAS | WEAK_DEVIATIONS_NOT_SIGNIFICANT | NO_BIAS_DETECTED

# STRICT RULES
- Do not interpret NO_BIAS as system failure (it is a valid scientific outcome).
- Do not rerun unless ≥100 new draws have been added.
- No external LLM calls.
- Use scripts/predict_vs_actual.py v2 only.
- No production DB writes.

# FILES TO INSPECT
- scripts/randomness_audit.py
- scripts/predict_vs_actual.py
- data/big_lotto_draws_full.csv
- data/power_lotto_draws_full.csv
- data/daily_539_draws_full.csv
- wiki/system/predict_vs_actual_sop.md

# ACCEPTANCE CRITERIA
- 3 verdicts written to wiki/system/randomness_final_verdict.md.
- Each verdict references the audit script run timestamp.
- Bonferroni + BH-FDR correction explicitly documented.
- wiki/README.md updated to reference the verdict file.

# FINAL VERDICT OPTIONS
RANDOMNESS_AUDIT_FINAL_VERDICT_WRITTEN | RANDOMNESS_AUDIT_PARTIAL | RANDOMNESS_AUDIT_DATA_INSUFFICIENT
Expected: RANDOMNESS_AUDIT_FINAL_VERDICT_WRITTEN
```

---

### Prompt 5 — Hypothesis Registry CLI (P1, Day 21–30)

```
# ROLE
You are a LotteryNew scientific governance engineer.

# TASK
Create registry/hypotheses.jsonl + tools/registry/cli.py:

Commands:
  register --hypothesis-id <id> --description "..." --predictor <module> --window <N>
  list [--status open|closed|retired]
  close --hypothesis-id <id> --verdict SIGNAL|NO_SIGNAL --evidence-file <path>

Constraints:
- jsonl is append-only (no in-place edit for existing entries).
- Each entry: id, description, predictor, window, status, registered_at, registrant, attempts, verdict.
- CI gate: strategy_eval run WITHOUT --hypothesis-id must fail.

# STRICT RULES
- No external LLM calls.
- No production DB writes.
- jsonl file in registry/hypotheses.jsonl.
- Scheduler remains disabled.

# ACCEPTANCE CRITERIA
- CLI: register + list + close commands all work.
- strategy_eval run without --hypothesis-id exits with error.
- 2 example hypotheses registered (one for big_lotto, one for power_lotto).
- tests/test_hypothesis_registry.py passes.

# FINAL VERDICT OPTIONS
HYPOTHESIS_REGISTRY_VERIFIED | HYPOTHESIS_REGISTRY_PARTIAL | HYPOTHESIS_REGISTRY_REQUIRES_FIX
Expected: HYPOTHESIS_REGISTRY_VERIFIED
```

---

### Prompt 6 — Strategy Evaluation Framework v0.5 (P1, Day 30–45)

```
# ROLE
You are a LotteryNew strategy validation engineer.

# TASK
Create tools/strategy_eval/ v0.5 — a CLI that runs multi-window statistical evaluation.

CLI: python3 tools/strategy_eval/cli.py --game power_lotto --hypothesis-id <id>

Pipeline:
1. Load historical predictions from predictions/retro/<game>/
2. Run multi-window (150 / 500 / 1500 draws) predict-vs-actual
3. Permutation null (≥1000 simulations, Monte Carlo)
4. Bonferroni correction within-game
5. BH-FDR correction across strategies
6. Output JSON report to outputs/strategy_eval/<game>/<timestamp>/report.json

v0.5 scope (single game only, no walk-forward OOS yet — that is v1).

# STRICT RULES
- Must reference --hypothesis-id (else fail with HypothesisNotRegisteredError).
- No external LLM calls.
- No production writes.
- No new prediction-signal research beyond what's already registered.

# FILES TO INSPECT
- scripts/predict_vs_actual.py
- scripts/retro_predictions.py
- registry/hypotheses.jsonl (from Prompt 5)
- wiki/system/predict_vs_actual_sop.md

# ACCEPTANCE CRITERIA
- CLI runs end-to-end on power_lotto.
- Output report contains: game, window_results, permutation_p, bonferroni_p, bh_fdr_q, verdict.
- Missing --hypothesis-id raises error.
- tests/test_strategy_eval.py passes.

# FINAL VERDICT OPTIONS
STRATEGY_EVAL_V05_VERIFIED | STRATEGY_EVAL_PARTIAL | STRATEGY_EVAL_REQUIRES_FIX
Expected: STRATEGY_EVAL_V05_VERIFIED
```

---

### Prompt 7 — Circular-Bias Detector CI Gate (P1, Day 30–45)

```
# ROLE
You are a LotteryNew statistical integrity engineer.

# TASK
Implement tests/test_no_circular_match.py — CI gate preventing v1-style circular-match bias.

Detection pattern:
- v1-style = predictions evaluated against ALL historical draws (max-hit across pool)
- v2-correct = predictions evaluated against ONLY the actual target draw

Scanner must:
1. Scan Python files in scripts/ and tools/ for pool-vs-all patterns.
2. Allow v2-correct patterns (single target draw evaluation).
3. Fail on v1-style patterns unless marked @approved_circular_match.

Also add fixture test:
- Intentional v1-style code in tests/fixtures/circular_match_violation.py
- Test must FAIL on the fixture (proving the detector works).
- Test must PASS on current codebase.

# STRICT RULES
- No false positives on scripts/predict_vs_actual.py (v2 correct).
- Must run < 60s.
- No external LLM calls.

# ACCEPTANCE CRITERIA
- Current codebase: PASS.
- Fixture violation: FAIL (detected).
- Documented in wiki/system/llm_governance.md as CI gate.

# FINAL VERDICT OPTIONS
CIRCULAR_BIAS_CI_GATE_VERIFIED | CIRCULAR_BIAS_CI_PARTIAL | CIRCULAR_BIAS_CI_REQUIRES_FIX
Expected: CIRCULAR_BIAS_CI_GATE_VERIFIED
```

---

### Prompt 8 — Leakage Detector Integration (P2, Day 45–60)

```
# ROLE
You are a LotteryNew backtest integrity engineer.

# TASK
Create tools/leakage_detector.py and integrate into rolling backtest flow.

Leakage patterns to detect:
1. Future draw data accessed before prediction time (look-ahead bias).
2. Target draw included in training window.
3. Feature computed using post-draw information.

Public API:
  check_leakage(
      prediction_time: datetime,
      training_window: pd.DataFrame,
      target_draw: dict,
  ) -> LeakageReport

If leakage detected: raise DataLeakageError with details.

Integration: Any RollingBacktester / strategy_eval CLI call must run check_leakage.

# STRICT RULES
- No external LLM calls.
- No production writes.
- DataLeakageError must be hard fail (not warning).

# FILES TO INSPECT
- scripts/predict_vs_actual.py
- scripts/retro_predictions.py
- tools/strategy_eval/ (from Prompt 6)

# ACCEPTANCE CRITERIA
- check_leakage() raises DataLeakageError on known leak fixture.
- check_leakage() passes on clean backtest fixture.
- Integrated into strategy_eval CLI (v0.5+).
- tests/test_leakage_detector.py passes.

# FINAL VERDICT OPTIONS
LEAKAGE_DETECTOR_VERIFIED | LEAKAGE_DETECTOR_PARTIAL | LEAKAGE_DETECTOR_REQUIRES_FIX
Expected: LEAKAGE_DETECTOR_VERIFIED
```

---

### Prompt 9 — BFF API v0.5 (P2, Day 60–75)

```
# ROLE
You are a LotteryNew API consolidation engineer.

# TASK
Create api/bff.py — Backend-for-Frontend layer consolidating top-3 UI data sources.

Endpoints:
  GET /api/bff/summary        → orchestrator summary + LLM caps status + strategy states
  GET /api/bff/strategies     → active/shadow + rollback guard decision + outcome counts
  GET /api/bff/tasks          → today tasks + queue health + recent LLM calls

All BFF endpoints read-only. They aggregate from existing internal APIs.

UI should use BFF endpoints; direct endpoint calls can remain during transition.

# STRICT RULES
- BFF is read-only aggregation only.
- No new DB tables.
- No external LLM calls.
- No modification of existing endpoints.
- Scheduler remains disabled.

# FILES TO INSPECT
- orchestrator/api.py
- src/ui/OrchestrationManager.js
- orchestrator/llm_caps.py (get_cap_status)
- orchestrator/rollback_guard.py (get_cap_status equivalent)

# ACCEPTANCE CRITERIA
- 3 BFF endpoints work and return consolidated data.
- UI uses at least 1 BFF endpoint.
- tests/test_bff_api.py smoke passes.
- Existing endpoints unchanged.

# FINAL VERDICT OPTIONS
BFF_API_V05_VERIFIED | BFF_API_PARTIAL | BFF_API_REQUIRES_FIX
Expected: BFF_API_V05_VERIFIED
```

---

### Prompt 10 — Dashboard Consolidation v0.5 (P2, Day 75–90)

```
# ROLE
You are a LotteryNew UI consolidation engineer.

# TASK
Consolidate the UI dashboard to a single nav entry with 3 merged sub-pages.

Current state: multiple entry points (monitoring_status.md, /api/strategy-states,
/api/next-draw-summary, Copilot-Daemon Dashboard, etc.)

Target: Single OrchestrationManager.js with nav:
  Tab 1: System Health (scheduler status + LLM caps + rollback guard)
  Tab 2: Tasks (today queue + failure taxonomy + LLM usage)
  Tab 3: Strategies (active/shadow + outcome count + evidence items)

# STRICT RULES
- No changes to backend API endpoints.
- No external LLM calls.
- Existing DOM IDs must remain (do not break: #orc-llm-caps-status, #orc-rollback-guard-status, etc.)
- No production state modifications.

# FILES TO INSPECT
- src/ui/OrchestrationManager.js
- orchestrator/api.py
- api/bff.py (from Prompt 9)

# ACCEPTANCE CRITERIA
- Single nav with 3 tabs functional.
- All existing DOM IDs present and working.
- No 404 on data fetches.
- tests/test_dashboard_consolidation_ui.py passes (DOM ID presence + API references).

# FINAL VERDICT OPTIONS
DASHBOARD_CONSOLIDATION_V05_VERIFIED | DASHBOARD_CONSOLIDATION_PARTIAL | DASHBOARD_CONSOLIDATION_REQUIRES_FIX
Expected: DASHBOARD_CONSOLIDATION_V05_VERIFIED
```

---

## 10. Final Recommendation

### 10.1 System Engineering (強烈建議繼續投入)

**High ROI.** Phase 0 是三個已知缺口：outcome_gate 統一、stale lock release、EvidenceCollector v0.1。  
完成後 Phase 0 production safety 才算真正閉環。之後 Phase 1 (Architecture) + Phase 2 (Science Closure) 可並行推進。

### 10.2 Lottery Research (Maintenance-Only)

三款遊戲均為 NO SIGNAL（Bonferroni+BH-FDR 後）。科學封項條件已滿足。  
**應做：** Randomness audit final verdict doc（一次性工作）、 每 50 draws rerun audit（週期性）。  
**禁止：** 任何新 prediction-signal exploration 研究。

### 10.3 Self-learning Scheduler (高 ROI，需分步驟)

EvidenceCollector → v0.1 (3 sources) → v0.3 (6 sources) → v1 (18 sources) 分步走。  
Local Planner v0.5 在 EvidenceCollector v0.3 穩定後啟動。  
外部 LLM 用量目標：Day 90 後 <50% 任務數；Day 180 後 <30%。

### 10.4 Transferable Framework (Month 3+)

`tools/backtest_framework/` 從 circular_bias_detector + leakage_detector 開始提取。  
Stock POC 在 framework v0.1 穩定後啟動（Month 4–5）。  
保留核心原則：preregistered hypothesis、multiple comparison correction、no auto-rollback、production write requires confirm。

### 10.5 Next Single Task

> **Start with: Outcome Gate Unified Interface**  
> It is the last missing production safety piece.  
> Risk: low. Impact: high. Dependency: none. No external LLM needed.  
> Use Prompt 1 above.

---

## Appendix — Locked Governance Constraints (不可修改)

1. ✅ 不承諾彩票一定能提升中獎率
2. ✅ NO SIGNAL = 科學成功（非系統失敗）
3. ✅ Circular-Match Bias → CI gate，禁止 v1 重蹈
4. ✅ Local Planner 預設不呼叫外部 LLM（cap=0）
5. ✅ 未驗證自動寫 production DB 全面禁止
6. ✅ 自動 rollback 全面禁止；rollback 需 CTO + 人工確認
7. ✅ Audit guard 不得移除，CI scanner 強制
8. ✅ Cap guard 不得移除，cap → audit → subprocess 順序強制
9. ✅ 任何 production mutation 仍須手動確認
10. ✅ 多重比較校正（Bonferroni + BH-FDR）強制，禁止 post-hoc 豁免

---

**End of Converged Master Roadmap v1.0 (2026-05-04)**  
Previous version: `MASTER_ROADMAP_20260503.md`  
Next review checkpoint: when Day-30 deliverables are complete.
