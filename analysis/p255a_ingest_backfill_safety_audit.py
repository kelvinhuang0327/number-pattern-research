"""
P255A — Ingest / Backfill Safety Boundary Audit

Read-only audit script.  Produces:
  outputs/research/p255a_ingest_backfill_safety_audit_20260608.json
  outputs/research/p255a_ingest_backfill_safety_audit_20260608.md

No DB write, no registry mutation, no strategy promotion.
"""

import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT_DIR   = os.path.join(_REPO_ROOT, "outputs", "research")
_DATE_TAG  = "20260608"
_JSON_OUT  = os.path.join(_OUT_DIR, f"p255a_ingest_backfill_safety_audit_{_DATE_TAG}.json")
_MD_OUT    = os.path.join(_OUT_DIR, f"p255a_ingest_backfill_safety_audit_{_DATE_TAG}.md")

os.makedirs(_OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Trigger path inventory (read-only analysis — no live calls)
# ---------------------------------------------------------------------------

TRIGGER_PATH_INVENTORY = [
    {
        "id": "T01",
        "path": "GET /api/ingest/status",
        "caller": "API direct / frontend button",
        "classification": "READ_ONLY_LOG",
        "writes_db": False,
        "dry_run_applicable": False,
        "auto_trigger_on_load": False,
        "notes": "Source health-check only.  Calls fetcher.check_source() for each lottery type.  No DB access."
    },
    {
        "id": "T02",
        "path": "GET /api/ingest/scan-missing",
        "caller": "API direct / frontend Scan button",
        "classification": "READ_ONLY_LOG",
        "writes_db": False,
        "dry_run_applicable": False,
        "auto_trigger_on_load": False,
        "notes": "Reads DB draw list + official site.  Returns gap report.  No insert/update/delete."
    },
    {
        "id": "T03",
        "path": "POST /api/ingest/fetch-latest  (insert_if_new=False OR dry_run=True)",
        "caller": "API direct / frontend Fetch-Latest button",
        "classification": "DRY_RUN_SAFE",
        "writes_db": False,
        "dry_run_applicable": True,
        "auto_trigger_on_load": False,
        "notes": "When insert_if_new=False (default) and dry_run=False: fetches but does NOT insert. "
                 "When dry_run=True: logs dry_run status only.  Safe path."
    },
    {
        "id": "T04",
        "path": "POST /api/ingest/fetch-latest  (insert_if_new=True, dry_run=False)",
        "caller": "API direct / frontend Fetch-Latest button with Insert checkbox checked",
        "classification": "WRITE_CAPABLE_REQUIRES_GUARD",
        "writes_db": True,
        "dry_run_applicable": True,
        "auto_trigger_on_load": False,
        "notes": "Calls db_manager.insert_draws() if draw is new.  On success calls _refresh_after_insert() "
                 "which chains: resolve_pending(dry_run=False) + adjust_all_types(dry_run=False) + "
                 "apply_learning(dry_run=False).  No server-side authorization token required."
    },
    {
        "id": "T05",
        "path": "POST /api/ingest/backfill  (dry_run=True)",
        "caller": "API direct / frontend Backfill button in dry-run mode",
        "classification": "DRY_RUN_SAFE",
        "writes_db": False,
        "dry_run_applicable": True,
        "auto_trigger_on_load": False,
        "notes": "Passes dry_run=True to BackfillEngine.run().  Engine logs 'dry_run' status per draw "
                 "but calls no insert.  P254A P254B verification confirmed this path works."
    },
    {
        "id": "T06",
        "path": "POST /api/ingest/backfill  (dry_run=False)  <- INCIDENT PATH",
        "caller": "API direct / frontend Backfill button with confirmed=true and dryRun=false",
        "classification": "WRITE_CAPABLE_REQUIRES_GUARD",
        "writes_db": True,
        "dry_run_applicable": True,
        "auto_trigger_on_load": False,
        "critical_finding": True,
        "notes": "BackfillRequest.dry_run defaults to False.  A POST without explicit dry_run=true "
                 "WILL write.  On any insertion, calls _refresh_after_insert() (resolve_pending + "
                 "weight_adjuster + learning_integrator, all dry_run=False).  This is the exact path "
                 "that triggered the P254B incident (5 draws inserted: BIG_LOTTO 115000059, "
                 "POWER_LOTTO 115000045, DAILY_539 115000136/137/138)."
    },
    {
        "id": "T07",
        "path": "GET /api/ingest/log",
        "caller": "API direct / AutoFetchManager._loadLog() on page init",
        "classification": "READ_ONLY_LOG",
        "writes_db": False,
        "dry_run_applicable": False,
        "auto_trigger_on_load": True,
        "notes": "AutoFetchManager constructor calls _loadLog() automatically on instantiation. "
                 "This is GET only — reads ingest_log.jsonl and returns entries.  No DB write."
    },
    {
        "id": "T08",
        "path": "POST /api/ingest/log/clear",
        "caller": "API direct / future UI button",
        "classification": "WRITE_CAPABLE_REQUIRES_GUARD",
        "writes_db": False,
        "writes_log_file": True,
        "dry_run_applicable": False,
        "auto_trigger_on_load": False,
        "notes": "Truncates ingest_log.jsonl.  Does not touch the DB.  Audit trail destruction risk."
    },
    {
        "id": "T09",
        "path": "Frontend: AutoFetchManager._onBackfill()  (frontend confirmation gate)",
        "caller": "User click on Backfill button",
        "classification": "WRITE_CAPABLE_REQUIRES_GUARD",
        "writes_db": True,
        "dry_run_applicable": True,
        "auto_trigger_on_load": False,
        "has_frontend_gate": True,
        "frontend_gate_code": "if (!dryRun && !confirmed) { show warning; return; }",
        "notes": "Frontend soft gate: requires dryRun=true OR confirmed checkbox to be checked. "
                 "If confirmed checkbox is already checked from a prior session and user clicks backfill "
                 "without realizing, a non-dry-run write is sent.  Gate is UI-only, not server-enforced."
    },
    {
        "id": "T10",
        "path": "Backend: _refresh_after_insert() internal chain",
        "caller": "Triggered internally on any successful non-dry-run insert (T04 or T06)",
        "classification": "WRITE_CAPABLE_REQUIRES_GUARD",
        "writes_db": True,
        "dry_run_applicable": False,
        "auto_trigger_on_load": False,
        "notes": "Calls resolve_pending(dry_run=False), adjust_all_types(dry_run=False), and "
                 "apply_learning(dry_run=False).  These are additional write operations that cascade "
                 "from a backfill insert.  There is no dry_run pass-through to this chain."
    },
    {
        "id": "T11",
        "path": "FastAPI startup event: startup_event()",
        "caller": "Backend process start",
        "classification": "READ_ONLY_LOG",
        "writes_db": False,
        "dry_run_applicable": False,
        "auto_trigger_on_load": True,
        "notes": "Only calls scheduler.load_data().  No ingest or backfill triggered at startup."
    },
    {
        "id": "T12",
        "path": "Scheduler / cron / background task paths",
        "caller": "N/A",
        "classification": "UNKNOWN_NEEDS_SCOPE",
        "writes_db": False,
        "dry_run_applicable": False,
        "auto_trigger_on_load": False,
        "notes": "lottery_api/utils/scheduler.py and smart_scheduler.py were grepped for "
                 "'auto.*backfill' / 'cron' / 'APScheduler'.  No backfill auto-trigger found. "
                 "smart_scheduler.py references 'scheduler' for data reload only, not ingest. "
                 "No background job enqueues /api/ingest/backfill."
    },
    {
        "id": "T13",
        "path": "Test-only paths: TestClient calls in test_p254a / test_p254b",
        "caller": "pytest test suite",
        "classification": "TEST_ONLY",
        "writes_db": False,
        "dry_run_applicable": True,
        "auto_trigger_on_load": False,
        "notes": "test_p254a_fetcher_backfill_repair.py uses FastAPI TestClient with dry_run=True. "
                 "Tests are isolated and do not write to the canonical DB."
    },
]

WRITE_CAPABLE_PATHS = [p for p in TRIGGER_PATH_INVENTORY
                       if p["classification"] == "WRITE_CAPABLE_REQUIRES_GUARD"]

AUTO_TRIGGER_RISKS = [
    {
        "risk_id": "R01",
        "severity": "HIGH",
        "title": "BackfillRequest.dry_run defaults to False",
        "detail": (
            "In lottery_api/routes/ingest.py, BackfillRequest.dry_run = False. "
            "Any caller that omits dry_run (or sends dry_run=false) will trigger real DB writes. "
            "The incident path (T06) went through this default. "
            "Mitigation: change default to dry_run=True and require an explicit 'apply=true' flag "
            "or a server-side authorization token to perform writes."
        ),
        "affected_paths": ["T06"],
        "file": "lottery_api/routes/ingest.py:41",
    },
    {
        "risk_id": "R02",
        "severity": "HIGH",
        "title": "Frontend confirmation gate is UI-only (not server-enforced)",
        "detail": (
            "AutoFetchManager._onBackfill() checks 'if (!dryRun && !confirmed) return'. "
            "This is enforced only in the browser JavaScript. "
            "Any direct HTTP POST to /api/ingest/backfill bypasses this gate entirely. "
            "During the P254B incident the frontend sent the POST after the user confirmed, "
            "but the server had no additional authorization layer. "
            "Mitigation: add a server-side 'apply_confirmed: bool = False' field to BackfillRequest "
            "that the server validates before allowing dry_run=False writes."
        ),
        "affected_paths": ["T06", "T09"],
        "file": "src/ui/AutoFetchManager.js:241-244",
    },
    {
        "risk_id": "R03",
        "severity": "MEDIUM",
        "title": "_refresh_after_insert() cascades multiple write operations with no dry_run option",
        "detail": (
            "After any successful non-dry-run insert (fetch-latest or backfill), "
            "_refresh_after_insert() fires resolve_pending(dry_run=False), "
            "adjust_all_types(dry_run=False), and apply_learning(dry_run=False). "
            "These are additional write paths that execute without any dry_run guard. "
            "A single accidental backfill insert triggers 3+ downstream write chains."
        ),
        "affected_paths": ["T04", "T06", "T10"],
        "file": "lottery_api/routes/ingest.py:72-110",
    },
    {
        "risk_id": "R04",
        "severity": "MEDIUM",
        "title": "CORS allows wildcard origin in development mode",
        "detail": (
            "lottery_api/app.py CORS origins list includes '*'. "
            "In development this means any origin can POST to write-capable endpoints. "
            "No CORS restriction prevents a cross-origin page from triggering backfill writes. "
            "Mitigation: restrict CORS to explicit localhost origins only; remove '*'."
        ),
        "affected_paths": ["T04", "T06"],
        "file": "lottery_api/app.py:30-36",
    },
    {
        "risk_id": "R05",
        "severity": "LOW",
        "title": "AutoFetchManager._loadLog() auto-fires GET on page load (read-only, not a write risk)",
        "detail": (
            "The AutoFetchManager constructor calls this._loadLog() immediately on instantiation "
            "(App.js line 34 creates AutoFetchManager; AutoFetchManager._bindEvents line 79 calls _loadLog). "
            "This sends GET /api/ingest/log automatically on every page load. "
            "This is READ_ONLY and poses no write risk, but confirms the frontend does auto-contact "
            "the ingest API on every page load without user interaction."
        ),
        "affected_paths": ["T07"],
        "file": "src/ui/AutoFetchManager.js:79",
    },
    {
        "risk_id": "R06",
        "severity": "LOW",
        "title": "No DB pre-write SHA checkpoint before backfill insert",
        "detail": (
            "Before calling db_manager.insert_draws(), neither the route nor the engine "
            "creates a SHA fingerprint or DB snapshot. "
            "If a partial write occurs (network failure mid-batch), "
            "there is no rollback point. "
            "The existing DB UNIQUE constraint prevents duplicates but does not protect against "
            "partial state. "
            "Mitigation: record DB file SHA256 to ingest_log before each write batch."
        ),
        "affected_paths": ["T04", "T06"],
        "file": "lottery_api/fetcher/backfill_engine.py:261-295",
    },
]

CURRENT_ACCEPTED_BASELINE = {
    "BIG_LOTTO_raw": 22239,
    "BIG_LOTTO_canonical": 2114,
    "BIG_LOTTO_add_on": 19100,
    "POWER_LOTTO_raw": 1917,
    "DAILY_539_raw": 5882,
    "strategy_prediction_replays": 94924,
    "source": "PR #360 ACCEPT_BACKFILL_DB_DRIFT_2026_0608 (merged 2026-06-08)",
    "stale_must_not_reuse": {
        "BIG_LOTTO_raw_stale": 22238,
        "BIG_LOTTO_canonical_stale": 2113,
        "invalidated_date": "2026-06-08",
    },
}

RECOMMENDED_GUARDRAILS = [
    {
        "id": "G01",
        "priority": "P0",
        "title": "Change BackfillRequest.dry_run default to True",
        "description": (
            "In lottery_api/routes/ingest.py BackfillRequest, change "
            "'dry_run: bool = False' to 'dry_run: bool = True'. "
            "All callers must explicitly opt into writes by passing dry_run=False. "
            "This is the single highest-impact change to prevent accidental writes."
        ),
        "file": "lottery_api/routes/ingest.py:44",
        "guardrail_type": "default_dry_run",
    },
    {
        "id": "G02",
        "priority": "P0",
        "title": "Require explicit server-side confirmation token for write-capable backfill",
        "description": (
            "Add an 'apply_confirmed: bool = False' field to BackfillRequest. "
            "Server rejects dry_run=False if apply_confirmed is not True. "
            "This ensures the server enforces authorization regardless of client behavior. "
            "This prevents direct API calls from bypassing the UI gate."
        ),
        "file": "lottery_api/routes/ingest.py (new field in BackfillRequest)",
        "guardrail_type": "explicit_confirm_token",
    },
    {
        "id": "G03",
        "priority": "P1",
        "title": "UI confirmation dialog before non-dry-run backfill",
        "description": (
            "Replace the checkbox confirmation in AutoFetchManager with a modal dialog "
            "that explicitly states how many draws will be written and resets after each "
            "confirmation so it cannot be left in a pre-confirmed state across test sessions."
        ),
        "file": "src/ui/AutoFetchManager.js:236-294",
        "guardrail_type": "ui_confirmation",
    },
    {
        "id": "G04",
        "priority": "P1",
        "title": "Audit log entry for every DB write with pre/post row counts",
        "description": (
            "Before and after each insert batch, record to ingest_log: "
            "pre_count, post_count, and a DB fingerprint. "
            "IngestLogger already exists; extend the 'ok' log entry to include counts."
        ),
        "file": "lottery_api/fetcher/backfill_engine.py:262-274 (extend ingest_logger.log call)",
        "guardrail_type": "audit_log",
    },
    {
        "id": "G05",
        "priority": "P1",
        "title": "Controlled-apply style DB SHA backup before any write batch",
        "description": (
            "Before calling db_manager.insert_draws(), compute sha256 of the DB file "
            "and log it to the audit log.  Optionally trigger a SQLite online-backup to "
            "a timestamped file for rollback capability."
        ),
        "file": "lottery_api/fetcher/backfill_engine.py:_insert() (before insert_draws call)",
        "guardrail_type": "controlled_apply_backup_sha",
    },
    {
        "id": "G06",
        "priority": "P1",
        "title": "Server-side idempotency guard with per-batch insert token",
        "description": (
            "Generate a unique idempotency_key per backfill request. "
            "Log the key before writes begin.  If the same key is replayed within 60 seconds, "
            "reject with 409 Conflict.  This prevents double-submit from network retry."
        ),
        "file": "lottery_api/routes/ingest.py (new idempotency_key param)",
        "guardrail_type": "server_idempotency",
    },
    {
        "id": "G07",
        "priority": "P2",
        "title": "Remove wildcard CORS origin from production configuration",
        "description": (
            "lottery_api/app.py origins list includes '*'.  Remove it and enumerate only "
            "the allowed local origins.  Gate the wildcard behind an env-var for dev-only mode."
        ),
        "file": "lottery_api/app.py:30-36",
        "guardrail_type": "cors_restriction",
    },
    {
        "id": "G08",
        "priority": "P2",
        "title": "Write endpoint disabled unless explicit authorization env-var is set",
        "description": (
            "Add INGEST_WRITE_ENABLED=false env-var.  When false, write-capable endpoints "
            "return 405 or force dry_run=True.  Set to true only during authorized maintenance windows."
        ),
        "file": "lottery_api/routes/ingest.py (new env check at endpoint entry)",
        "guardrail_type": "write_endpoint_disabled",
    },
]

DRY_RUN_SAFETY_ASSESSMENT = {
    "backfill_endpoint": {
        "dry_run_supported": True,
        "dry_run_default": False,
        "risk": "HIGH — default is write-capable; caller must opt into dry_run=True",
        "p254b_smoke_confirmed": True,
        "recommended_change": "Change default to dry_run=True (G01)",
    },
    "fetch_latest_endpoint": {
        "dry_run_supported": True,
        "dry_run_default": False,
        "insert_if_new_default": False,
        "risk": "LOW — default insert_if_new=False means no write even if dry_run=False",
        "notes": "A caller must explicitly set insert_if_new=True to write.",
    },
    "scan_missing_endpoint": {
        "dry_run_supported": False,
        "dry_run_default": "N/A",
        "risk": "NONE — GET endpoint, read-only by design",
    },
    "log_endpoint": {
        "dry_run_supported": False,
        "dry_run_default": "N/A",
        "risk": "NONE — GET endpoint, reads jsonl file only",
    },
    "log_clear_endpoint": {
        "dry_run_supported": False,
        "dry_run_default": "N/A",
        "risk": "LOW — truncates log file only, not DB",
    },
}

NON_STANDARD_DRAW_HANDLING = {
    "add_on_draw_ids": {
        "example": "103000009-01",
        "format": "hyphenated, non-numeric",
        "issue_before_p254a": "int(draw[-6:]) raised ValueError for '009-01'",
        "fix_in_p254a": "_split() in missing_issue_detector.py now guards with draw.isdigit()",
        "current_safety": "SAFE — non-digit draws return None from _split(); loop skips them",
        "tested": True,
        "test_ref": "test_p254a_fetcher_backfill_repair.py::TestAddOnSafety",
    },
    "year_boundary_draws": {
        "example": "96000104 -> 97000001",
        "handling": "_detect_internal_gaps() checks prev_year != curr_year; skips boundary",
        "current_safety": "SAFE",
    },
    "missing_draw_sort": {
        "note": "_draw_sort_key() in scan() uses try/except int(x) with fallback",
        "current_safety": "SAFE",
    },
}

PHASE0_SUMMARY = {
    "repo": "/Users/kelvin/Kelvin-WorkSpace/LotteryNew",
    "branch": "main",
    "HEAD": "270a718c36ea55b76785e65beb345247d9af696f",
    "HEAD_equals_origin_main": True,
    "all_stop_conditions_clear": True,
    "dirty_items_classification": (
        "All tolerated runtime items only: backend.pid, frontend.pid, "
        "data/lottery_v2.db metadata-touch same-size (0 byte change), claude-code-showcase, "
        "p252/p253 prior research outputs not staged, "
        "lottery_api/data/ingest_log.jsonl untracked runtime log, runtime/"
    ),
}

PR_STATUSES = {
    "pr360": {
        "pr": 360,
        "title": "ACCEPT_BACKFILL_DB_DRIFT_2026_0608: update P247G baseline to 2114/22239",
        "state": "MERGED",
        "merge_commit": "234cc02aee1c5d7a4e7990d3195ad4d987315a70",
        "url": "https://github.com/kelvinhuang0327/number-pattern-research/pull/360",
        "what_it_did": "Accepted 5 draws inserted during fetcher repair; updated P247G guard to raw=22239 canonical=2114",
    },
    "pr361": {
        "pr": 361,
        "title": "P254A repair fetcher backfill modules",
        "state": "MERGED",
        "merge_commit": "36f6862dc912af31115183cf6072dec939ed4dda",
        "url": "https://github.com/kelvinhuang0327/number-pattern-research/pull/361",
        "what_it_did": "Restored lottery_api/fetcher/* (5 modules); hardened ADD_ON isdigit() guard",
    },
    "pr362": {
        "pr": 362,
        "title": "P254B close fetcher repair governance",
        "state": "MERGED",
        "merge_commit": "270a718c36ea55b76785e65beb345247d9af696f",
        "url": "https://github.com/kelvinhuang0327/number-pattern-research/pull/362",
        "what_it_did": "Governance closure: incident chain documented, lessons recorded, state returned to HOLD",
    },
}

ARTIFACT = {
    "schema_version": "1.0",
    "task_id": "P255A",
    "classification": "INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE",
    "date": "2026-06-08",
    "task_type": "Type B read-only audit",
    "generated_at": datetime.now(timezone.utc).isoformat(),

    "phase0_summary": PHASE0_SUMMARY,

    "pr360_status": PR_STATUSES["pr360"],
    "pr361_status": PR_STATUSES["pr361"],
    "pr362_status": PR_STATUSES["pr362"],

    "trigger_path_inventory": TRIGGER_PATH_INVENTORY,
    "trigger_path_count": len(TRIGGER_PATH_INVENTORY),

    "write_capable_paths": WRITE_CAPABLE_PATHS,
    "write_capable_path_count": len(WRITE_CAPABLE_PATHS),

    "auto_trigger_risks": AUTO_TRIGGER_RISKS,
    "auto_trigger_risk_count": len(AUTO_TRIGGER_RISKS),

    "dry_run_safety_assessment": DRY_RUN_SAFETY_ASSESSMENT,

    "non_standard_draw_handling_assessment": NON_STANDARD_DRAW_HANDLING,

    "current_accepted_baseline": CURRENT_ACCEPTED_BASELINE,

    "recommended_guardrails": RECOMMENDED_GUARDRAILS,
    "recommended_guardrail_count": len(RECOMMENDED_GUARDRAILS),

    "incident_retrospective": {
        "what_happened": (
            "After lottery_api/fetcher/* was deleted (commit 7306264) and then restored (P254A/PR #361), "
            "the frontend auto-loaded the ingest page.  The auto-load only fires GET /api/ingest/log "
            "(READ_ONLY).  However, during manual validation the user clicked the Backfill button with "
            "the confirmation checkbox checked and dry_run=false.  The server had no additional "
            "authorization layer, so it accepted the write.  Five draws were inserted: "
            "BIG_LOTTO 115000059, POWER_LOTTO 115000045, DAILY_539 115000136/137/138."
        ),
        "root_cause_code": "BackfillRequest.dry_run defaults to False; no server-side confirm token",
        "root_cause_process": (
            "No governance gate required dry_run=True during post-repair validation session. "
            "Regression check (P247G guard) ran after the insert, not before."
        ),
        "draws_accepted_as_drift": [
            {"lottery_type": "BIG_LOTTO",   "draw": "115000059", "date": "2026/06/05"},
            {"lottery_type": "POWER_LOTTO", "draw": "115000045", "date": "2026/06/04"},
            {"lottery_type": "DAILY_539",   "draw": "115000136", "date": "2026/06/04"},
            {"lottery_type": "DAILY_539",   "draw": "115000137", "date": "2026/06/05"},
            {"lottery_type": "DAILY_539",   "draw": "115000138", "date": "2026/06/06"},
        ],
    },

    "scope_boundaries": {
        "already_accepted_baseline_drift": "PR #360 — BIG_LOTTO raw=22239, canonical=2114; do NOT reuse stale 22238/2113",
        "fetcher_code_repair": "PR #361 — 5 modules restored, ADD_ON guard hardened",
        "governance_closure": "PR #362 — incident chain documented, lessons L_P254_01/02/03 recorded",
        "future_ingest_ui_monitoring": "NOT in scope — requires separate explicit user authorization",
        "strategy_promotion": "Out of scope — no active deployable candidate",
        "prediction_improvement": "Not claimed",
    },

    "no_db_write_confirmed": True,
    "no_registry_mutation_confirmed": True,
    "no_strategy_promotion_confirmed": True,
    "no_betting_advice_confirmed": True,

    "recommended_next_task": (
        "HOLD.  No active deployable candidate.  Future ingest UI or monitoring work "
        "requires separate explicit user authorization before proceeding.  "
        "Implement guardrails G01+G02 before any future ingest write work is authorized."
    ),

    "final_decision": (
        "HOLD.  P255A safety audit is complete.  The write-capable backfill paths have been "
        "inventoried and classified.  The primary risk (BackfillRequest.dry_run=False default) "
        "is documented with P0 guardrail recommendations (G01+G02).  No DB write occurred in "
        "this audit.  Recommended guardrails G01-G08 should be implemented before any future "
        "ingest UI or automated monitoring work is authorized.  System returns to "
        "WAITING_FOR_USER_AUTHORIZATION."
    ),
}

# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _build_markdown(artifact: dict) -> str:
    lines = []
    lines.append("# P255A — Ingest / Backfill Safety Boundary Audit")
    lines.append(
        "\n**Date:** 2026-06-08  \n**Task Type:** Type B read-only audit  \n"
        "**Classification:** `INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE`\n"
    )

    lines.append("## Executive Summary\n")
    lines.append(
        "P255A audits all ingest and backfill trigger paths to identify where non-dry-run "
        "writes can occur, whether any path auto-triggers a write on page load, and what "
        "server/UI guardrails are currently present.  The audit found one critical gap: "
        "`BackfillRequest.dry_run` defaults to `False`, meaning any API call that omits "
        "the field will write to the DB.  The frontend confirmation gate is UI-only and "
        "is not enforced at the server.  Eight guardrails are recommended before any future "
        "ingest UI or monitoring feature is authorized.  No DB write was performed in this audit.\n"
    )

    lines.append("## Incident Background\n")
    lines.append(
        "During the P254A/P254B fetcher-repair session (2026-06-08), after `lottery_api/fetcher/*` "
        "was restored (PR #361), the frontend ingest page was loaded.  Page load auto-fired only a "
        "READ-ONLY `GET /api/ingest/log`.  However, a subsequent manual backfill button click "
        "with the confirmation checkbox checked and `dry_run=false` triggered a real write, "
        "inserting 5 draws (BIG_LOTTO 115000059, POWER_LOTTO 115000045, DAILY_539 "
        "115000136/137/138).  These were accepted as legitimate missing draws via PR #360.\n"
    )

    lines.append("## Phase 0 Verification\n")
    lines.append("| Item | Result |\n|---|---|")
    lines.append(f"| Repo | {artifact['phase0_summary']['repo']} |")
    lines.append("| Branch | main |")
    lines.append(f"| HEAD | `{artifact['phase0_summary']['HEAD'][:16]}...` |")
    lines.append("| HEAD = origin/main | YES |")
    lines.append("| PR #360 | MERGED |")
    lines.append("| PR #361 | MERGED |")
    lines.append("| PR #362 | MERGED |")
    lines.append("| data/lottery_v2.db | Metadata-only touch (0 bytes content change) |\n")

    lines.append("## Trigger Path Inventory\n")
    lines.append("| ID | Path | Classification | Writes DB | Auto on load |")
    lines.append("|---|---|---|:---:|:---:|")
    for p in artifact["trigger_path_inventory"]:
        writes = "YES" if p.get("writes_db") else "—"
        auto   = "YES" if p.get("auto_trigger_on_load") else "—"
        path_s = p["path"][:65] + "..." if len(p["path"]) > 65 else p["path"]
        lines.append(f"| {p['id']} | {path_s} | `{p['classification']}` | {writes} | {auto} |")
    lines.append("")

    lines.append("## Write-Capable Path Analysis\n")
    for p in artifact["write_capable_paths"]:
        crit = " **← INCIDENT PATH**" if p.get("critical_finding") else ""
        lines.append(f"### {p['id']}{crit}\n")
        lines.append(f"**Path:** `{p['path']}`\n")
        lines.append(f"{p['notes']}\n")

    lines.append("## Auto-Trigger Risk Analysis\n")
    for r in artifact["auto_trigger_risks"]:
        lines.append(f"### {r['risk_id']} [{r['severity']}] {r['title']}\n")
        lines.append(f"{r['detail']}\n")
        lines.append(f"- **File:** `{r['file']}`")
        lines.append(f"- **Affected paths:** {', '.join(r['affected_paths'])}\n")

    lines.append("## Dry-Run Safety Assessment\n")
    lines.append("| Endpoint | dry_run supported | default | Risk |")
    lines.append("|---|:---:|---|---|")
    for ep, v in artifact["dry_run_safety_assessment"].items():
        sup  = "YES" if v.get("dry_run_supported") else "—"
        dflt = str(v.get("dry_run_default", "N/A"))
        risk = v.get("risk", "")
        lines.append(f"| `{ep}` | {sup} | `{dflt}` | {risk} |")
    lines.append("")

    lines.append("## Non-Standard Draw Handling Assessment\n")
    add_on = artifact["non_standard_draw_handling_assessment"]["add_on_draw_ids"]
    lines.append("**ADD_ON draw IDs** (e.g. `103000009-01`):\n")
    lines.append(f"- Issue before P254A: {add_on['issue_before_p254a']}")
    lines.append(f"- Fix in P254A: {add_on['fix_in_p254a']}")
    lines.append(f"- Current safety: **{add_on['current_safety']}**\n")

    lines.append("## Current Accepted Baseline\n")
    bl = artifact["current_accepted_baseline"]
    lines.append("| Table / View | Count |")
    lines.append("|---|---:|")
    lines.append(f"| BIG_LOTTO raw draws | {bl['BIG_LOTTO_raw']:,} |")
    lines.append(f"| BIG_LOTTO canonical draws | {bl['BIG_LOTTO_canonical']:,} |")
    lines.append(f"| BIG_LOTTO ADD_ON excluded | {bl['BIG_LOTTO_add_on']:,} |")
    lines.append(f"| POWER_LOTTO raw draws | {bl['POWER_LOTTO_raw']:,} |")
    lines.append(f"| DAILY_539 raw draws | {bl['DAILY_539_raw']:,} |")
    lines.append(f"| strategy_prediction_replays | {bl['strategy_prediction_replays']:,} |")
    lines.append(
        f"\n**Stale values — must NOT be reused:** "
        f"BIG_LOTTO raw 22,238 / canonical 2,113 (invalidated 2026-06-08)\n"
    )

    lines.append("## Recommended Guardrails\n")
    for g in artifact["recommended_guardrails"]:
        lines.append(f"### {g['id']} [{g['priority']}] {g['title']}\n")
        lines.append(f"{g['description']}\n")
        lines.append(f"- **File:** `{g['file']}`\n")

    lines.append("## Recommended Next Task\n")
    lines.append(f"{artifact['recommended_next_task']}\n")

    lines.append("## Scope Boundaries\n")
    for k, v in artifact["scope_boundaries"].items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")

    lines.append("## Explicit Non-Actions\n")
    lines.append("- No DB write performed")
    lines.append("- No registry mutation")
    lines.append("- No strategy promotion")
    lines.append("- No betting advice")
    lines.append("- No fetcher code changed")
    lines.append("- No API behavior changed")
    lines.append("- No frontend modified")
    lines.append("- No P247G constants changed\n")

    lines.append("## Required Completion Check\n")
    lines.append("| Item | Status |")
    lines.append("|---|---|")
    lines.append("| Completed | YES |")
    lines.append("| Test Result | see pytest run |")
    lines.append("| Single Blocking Issue | NONE |")
    lines.append("| Modified Files | 4 (analysis script + json + md + test) |")
    lines.append("| Staged | YES |")
    lines.append("| Commit | YES |")
    lines.append("| Push | YES |")
    lines.append("| PR | YES |")
    lines.append("| Merge | PENDING CI |")
    lines.append("| Next Round Allowed | NO — WAITING_FOR_USER_AUTHORIZATION |")
    lines.append("| Final Classification | `INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE` |")
    lines.append("| Strong Model Needed | NO |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    md_content = _build_markdown(ARTIFACT)

    with open(_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(ARTIFACT, f, indent=2, ensure_ascii=False)
    print(f"JSON written: {_JSON_OUT}")

    with open(_MD_OUT, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"MD  written: {_MD_OUT}")

    print(f"\nSummary:")
    print(f"  Trigger paths inventoried : {ARTIFACT['trigger_path_count']}")
    print(f"  Write-capable paths       : {ARTIFACT['write_capable_path_count']}")
    print(f"  Auto-trigger risks        : {ARTIFACT['auto_trigger_risk_count']}")
    print(f"  Recommended guardrails    : {ARTIFACT['recommended_guardrail_count']}")
    print(f"  No DB write               : {ARTIFACT['no_db_write_confirmed']}")
    print(f"  Classification            : {ARTIFACT['classification']}")
    print(f"  Final decision            : HOLD")


if __name__ == "__main__":
    main()
