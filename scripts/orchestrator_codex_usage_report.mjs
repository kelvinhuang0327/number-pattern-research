#!/usr/bin/env node
/**
 * scripts/orchestrator_codex_usage_report.mjs
 *
 * Read-only Codex / Copilot usage reporter for the Betting-pool Orchestrator.
 *
 * Data sources (ALL READ-ONLY):
 *   1. runtime/agent_orchestrator/orchestrator.db  (SQLite via sqlite3 CLI)
 *   2. runtime/agent_orchestrator/logs/launchd/worker_tick.{out,err}.log
 *   3. runtime/agent_orchestrator/logs/launchd/planner_tick.{out,err}.log
 *   4. runtime/agent_orchestrator/tasks/{date}/*-task-completed*.md  (artifacts)
 *
 * Usage:
 *   node scripts/orchestrator_codex_usage_report.mjs --last 24h
 *   node scripts/orchestrator_codex_usage_report.mjs --today
 *   node scripts/orchestrator_codex_usage_report.mjs --limit 50
 *   node scripts/orchestrator_codex_usage_report.mjs --last 7d
 */

import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const ORCH_ROOT = join(REPO_ROOT, 'runtime', 'agent_orchestrator');
const DB_PATH   = join(ORCH_ROOT, 'orchestrator.db');
const LOGS_DIR  = join(ORCH_ROOT, 'logs', 'launchd');
const TASKS_DIR = join(ORCH_ROOT, 'tasks');

// ─── CLI argument parsing ────────────────────────────────────────────────────

function parseCLI(argv) {
  const args = argv.slice(2);
  let cutoffMs = null;
  let limit = 20;
  let label = 'last 24h';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--last' && args[i + 1]) {
      const spec = args[++i];
      const m = spec.match(/^(\d+)(h|d|m)$/i);
      if (!m) { console.error(`Unknown --last spec: ${spec}`); process.exit(1); }
      const n = parseInt(m[1], 10);
      const unit = m[2].toLowerCase();
      const ms = unit === 'h' ? n * 3600000
               : unit === 'd' ? n * 86400000
               : n * 60000;
      cutoffMs = Date.now() - ms;
      label = `last ${spec}`;
    } else if (args[i] === '--today') {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      cutoffMs = start.getTime();
      label = 'today (local midnight)';
    } else if (args[i] === '--limit' && args[i + 1]) {
      limit = parseInt(args[++i], 10);
    }
  }
  if (cutoffMs === null) {
    // Default: last 24h
    cutoffMs = Date.now() - 86400000;
    label = 'last 24h (default)';
  }
  return { cutoffMs, cutoffISO: new Date(cutoffMs).toISOString(), label, limit };
}

// ─── SQLite helper (uses system sqlite3 CLI — no npm deps) ──────────────────

function sqliteQuery(sql) {
  if (!existsSync(DB_PATH)) return [];
  try {
    const out = execSync(
      `sqlite3 -json "${DB_PATH}" "${sql.replace(/"/g, '\\"')}"`,
      { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
    ).trim();
    if (!out) return [];
    return JSON.parse(out);
  } catch {
    return [];
  }
}

// ─── Log file reader helpers ─────────────────────────────────────────────────

function readLog(filename) {
  const p = join(LOGS_DIR, filename);
  if (!existsSync(p)) return '';
  return readFileSync(p, 'utf8');
}

/** Parse worker_tick.out.log — entries are [timestamp header] + JSON blocks */
function parseWorkerOutLog(content, cutoffMs) {
  const entries = [];
  // Split on tick start/end boundaries
  const tickBlocks = content.split(/\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] worker tick (start|end)/);
  // Each tick-start block contains a JSON payload between start and end
  // Pattern: timestamp, "start", payload_lines..., timestamp, "end"
  let currentTs = null;
  let accumJson = '';
  let inBlock = false;

  for (let i = 1; i < tickBlocks.length; i += 3) {
    const ts = tickBlocks[i];
    const marker = tickBlocks[i + 1];
    const body = tickBlocks[i + 2] ?? '';
    if (marker === 'start') {
      currentTs = ts;
      accumJson = body.trim();
      inBlock = true;
    } else if (marker === 'end' && inBlock) {
      const tsMs = new Date(ts).getTime();
      if (tsMs >= cutoffMs) {
        let parsed = null;
        try { parsed = JSON.parse(accumJson); } catch { parsed = null; }
        entries.push({ ts, tsMs, raw: accumJson, parsed });
      }
      inBlock = false;
      accumJson = '';
    }
  }
  return entries;
}

/** Parse worker_tick.err.log — copilot-daemon structured log lines */
function parseWorkerErrLog(content, cutoffMs) {
  const lines = content.split('\n');
  const events = [];
  for (const line of lines) {
    // Format: 2026-04-25T13:50:26 [copilot-daemon] LEVEL [Component] message
    const m = line.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+\[([^\]]+)\]\s+(\w+)\s+\[([^\]]+)\]\s+(.*)/);
    if (!m) continue;
    const [, tsStr, daemon, level, component, message] = m;
    const tsMs = new Date(tsStr + 'Z').getTime(); // assume UTC
    if (tsMs < cutoffMs) continue;
    events.push({ ts: tsStr, tsMs, daemon, level, component, message, raw: line });
  }
  return events;
}

/** Parse planner_tick.out.log — same structure as worker out */
function parsePlannerOutLog(content, cutoffMs) {
  const entries = [];
  const tickBlocks = content.split(/\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] planner tick (start|end)/);
  let currentTs = null;
  let accumJson = '';
  let inBlock = false;

  for (let i = 1; i < tickBlocks.length; i += 3) {
    const ts = tickBlocks[i];
    const marker = tickBlocks[i + 1];
    const body = tickBlocks[i + 2] ?? '';
    if (marker === 'start') {
      currentTs = ts;
      accumJson = body.trim();
      inBlock = true;
    } else if (marker === 'end' && inBlock) {
      const tsMs = new Date(ts).getTime();
      if (tsMs >= cutoffMs) {
        let parsed = null;
        try { parsed = JSON.parse(accumJson); } catch { parsed = null; }
        entries.push({ ts, tsMs, raw: accumJson, parsed });
      }
      inBlock = false;
      accumJson = '';
    }
  }
  return entries;
}

// ─── Task artifact scanner ───────────────────────────────────────────────────

/**
 * Scan tasks/{date}/*-task-completed*.md files within the time window.
 * Returns array of { date, filename, ts, provider, taskType, status, isCodex }
 */
function scanTaskArtifacts(cutoffMs) {
  const results = [];
  if (!existsSync(TASKS_DIR)) return results;

  const dateDirs = readdirSync(TASKS_DIR).filter(d => /^\d{8}$/.test(d)).sort();

  for (const dateDir of dateDirs) {
    // Quick filter: skip folders clearly before window
    // Folder name is YYYYMMDD local time — convert to rough epoch
    const folderDateMs = new Date(
      `${dateDir.slice(0,4)}-${dateDir.slice(4,6)}-${dateDir.slice(6,8)}T00:00:00Z`
    ).getTime();
    // Allow folders within 2 days before cutoff (to catch timezone boundaries)
    if (folderDateMs + 2 * 86400000 < cutoffMs) continue;

    const dirPath = join(TASKS_DIR, dateDir);
    const files = readdirSync(dirPath).filter(f =>
      f.endsWith('.md') && f.includes('-task-completed')
    );

    for (const filename of files) {
      // Extract timestamp from filename: 20260425003105059173-task-completed.md
      const tsMatch = filename.match(/^(\d{14})\d*-task-completed/);
      let tsMs = null;
      if (tsMatch) {
        const tsStr = tsMatch[1];
        const iso = `${tsStr.slice(0,4)}-${tsStr.slice(4,6)}-${tsStr.slice(6,8)}T` +
                    `${tsStr.slice(8,10)}:${tsStr.slice(10,12)}:${tsStr.slice(12,14)}Z`;
        tsMs = new Date(iso).getTime();
      }
      if (tsMs !== null && tsMs < cutoffMs) continue;

      const filePath = join(dirPath, filename);
      let content = '';
      try { content = readFileSync(filePath, 'utf8'); } catch { continue; }

      // Extract Provider field
      const provMatch = content.match(/^Provider:\s*(.+)$/m);
      const provider = provMatch ? provMatch[1].trim() : null;

      // Extract Task Type
      const typeMatch = content.match(/^\*\*Task Type:\*\*\s*(.+)$|^Task Type:\s*(.+)$/m);
      const taskType = typeMatch ? (typeMatch[1] || typeMatch[2] || '').trim() : null;

      // Extract Status
      const statusMatch = content.match(/^\*\*Status:\*\*\s*(.+)$|^Status:\s*(.+)$/m);
      const status = statusMatch ? (statusMatch[1] || statusMatch[2] || '').trim() : null;

      // Extract Task ID
      const idMatch = content.match(/^\*\*Task ID:\*\*\s*(\d+)$/m);
      const taskId = idMatch ? idMatch[1] : null;

      // Extract title from first heading
      const titleMatch = content.match(/^#\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1].replace(/^(Completed|COMPLETED):\s*/i, '').trim() : filename;

      // Detect execution method
      const isHardOff = /llm_execution_mode=hard-off|hard.off bypass|smoke_test/i.test(content);
      const isCodex = /provider.*codex|codex exec|executing.*codex/i.test(content) && !isHardOff;
      const isCopilotDaemon = /provider.*copilot.daemon|copilot-daemon/i.test(content);
      const isDeterministic = /deterministic|safe_task_executor|SafeExecutor/i.test(content) || 
                              /closing.monitor|closing.availability|refresh.*closing/i.test(filename);

      results.push({
        date: dateDir, filename, filePath, tsMs,
        ts: tsMs ? new Date(tsMs).toISOString() : null,
        provider, taskType, status, taskId, title,
        isCodex, isCopilotDaemon, isDeterministic, isHardOff,
      });
    }
  }
  return results;
}

// ─── DB queries ──────────────────────────────────────────────────────────────

function queryDB(cutoffISO) {
  // tasks table (old orchestrator format)
  const tasksInWindow = sqliteQuery(
    `SELECT id, task_key, objective, status, planner_provider, worker_provider,
            gate_verdict, gate_reason, result_path, created_at, finished_at
     FROM tasks
     WHERE created_at >= '${cutoffISO}'
     ORDER BY created_at DESC`
  );

  // runs table
  const runsInWindow = sqliteQuery(
    `SELECT r.id, r.tick_type, r.status, r.message, r.task_id, r.started_at, r.finished_at,
            t.planner_provider, t.worker_provider, t.task_key, t.objective
     FROM runs r
     LEFT JOIN tasks t ON r.task_id = t.id
     WHERE r.started_at >= '${cutoffISO}'
     ORDER BY r.started_at DESC`
  );

  // Multiple-attempt tasks (tasks with > 1 run)
  const multiAttemptTasks = sqliteQuery(
    `SELECT task_id, COUNT(*) as run_count,
            MIN(started_at) as first_run, MAX(finished_at) as last_run
     FROM runs
     WHERE started_at >= '${cutoffISO}'
     GROUP BY task_id
     HAVING run_count > 1
     ORDER BY run_count DESC`
  );

  // Top tasks by run count
  const topByRuns = sqliteQuery(
    `SELECT r.task_id, COUNT(*) as run_count, t.objective, t.planner_provider, t.worker_provider, t.status
     FROM runs r
     LEFT JOIN tasks t ON r.task_id = t.id
     WHERE r.started_at >= '${cutoffISO}'
     GROUP BY r.task_id
     ORDER BY run_count DESC
     LIMIT 10`
  );

  // agent_tasks table (newer format)
  const agentTasksInWindow = sqliteQuery(
    `SELECT id, title, task_type, worker_type, status, created_at, epoch_id
     FROM agent_tasks
     WHERE created_at >= '${cutoffISO}'
     ORDER BY created_at DESC
     LIMIT 100`
  );

  return { tasksInWindow, runsInWindow, multiAttemptTasks, topByRuns, agentTasksInWindow };
}

// ─── Main analysis ───────────────────────────────────────────────────────────

function buildReport(opts) {
  const { cutoffMs, cutoffISO, label, limit } = opts;

  // 1. Log files
  const workerOut = readLog('worker_tick.out.log');
  const workerErr = readLog('worker_tick.err.log');
  const plannerOut = readLog('planner_tick.out.log');

  const workerOutEntries = parseWorkerOutLog(workerOut, cutoffMs);
  const workerErrEvents  = parseWorkerErrLog(workerErr, cutoffMs);
  const plannerOutEntries = parsePlannerOutLog(plannerOut, cutoffMs);

  // 2. Task artifacts
  const artifacts = scanTaskArtifacts(cutoffMs);

  // 3. DB queries
  const db = queryDB(cutoffISO);

  // ── Metric derivation ─────────────────────────────────────────────────────

  // worker_tick: GLOBAL_HARD_OFF skips
  const workerSkipped = workerOutEntries.filter(e => e.parsed?.message?.includes('GLOBAL_HARD_OFF'));
  const workerFailed  = workerOutEntries.filter(e =>
    e.parsed?.message?.toLowerCase().includes('worker tick failed') ||
    e.parsed?.status === 'FAILED'
  );
  const workerCodexFailed = workerOutEntries.filter(e =>
    e.parsed?.message?.toLowerCase().includes('[codex] exited')
  );
  const workerSuccess = workerOutEntries.filter(e => e.parsed?.result_path);

  // planner_tick
  const plannerSkipped = plannerOutEntries.filter(e => e.parsed?.message?.includes('GLOBAL_HARD_OFF'));
  const plannerSuccess = plannerOutEntries.filter(e => e.parsed?.status === 'TASK_CREATED' || e.parsed?.task_id);
  const plannerCodexCall = plannerOutEntries.filter(e =>
    !plannerSkipped.includes(e) && e.parsed && e.parsed.status !== 'SKIPPED'
  );

  // copilot-daemon events (from worker_tick.err.log)
  const daemonProviderEvents  = workerErrEvents.filter(e => /provider.*→/i.test(e.message));
  const daemonFallbackToCodex = workerErrEvents.filter(e => /falling back to codex|fallback.*codex/i.test(e.message));
  const daemonCodexExec       = workerErrEvents.filter(e => /Executing task.*with Codex|provider.*codex exec/i.test(e.message));
  const daemonCompleted       = workerErrEvents.filter(e => /Completed task #\d+ in/i.test(e.message));
  const daemonCriticalFailure = workerErrEvents.filter(e => /Critical failure/i.test(e.message));
  const daemonTimeout         = workerErrEvents.filter(e => /timeout|timed.out/i.test(e.message));

  // Artifacts
  const codexArtifacts         = artifacts.filter(a => a.isCodex);
  const copilotDaemonArtifacts = artifacts.filter(a => a.isCopilotDaemon);
  const deterministicArtifacts = artifacts.filter(a => a.isDeterministic);
  const hardOffArtifacts       = artifacts.filter(a => a.isHardOff);

  // DB metrics
  const dbPlannerCodex = db.tasksInWindow.filter(t => t.planner_provider === 'codex');
  const dbWorkerCodex  = db.tasksInWindow.filter(t => t.worker_provider === 'codex');
  const dbWorkerCopilot = db.tasksInWindow.filter(t => t.worker_provider?.includes('copilot'));
  const dbResultSuccess = db.tasksInWindow.filter(t => t.result_path && t.result_path.trim());
  const dbInvalidGate   = db.tasksInWindow.filter(t =>
    t.gate_verdict?.toLowerCase().includes('reject') ||
    t.gate_verdict?.toLowerCase().includes('invalid') ||
    t.gate_verdict?.toLowerCase().includes('fail')
  );
  const dbReplansRequired = db.tasksInWindow.filter(t => t.status === 'REPLAN_REQUIRED');

  const dbPlannerRuns = db.runsInWindow.filter(r => r.tick_type === 'planner_tick' && r.status === 'SUCCESS');
  const dbWorkerRuns  = db.runsInWindow.filter(r => r.tick_type === 'worker_tick'  && r.status === 'SUCCESS');
  const dbRetryRuns   = db.runsInWindow.filter(r => r.message?.toLowerCase().includes('retry') || r.status === 'RETRY');
  const dbRecoveryRuns = db.runsInWindow.filter(r => r.message?.toLowerCase().includes('recover'));

  // ── Consolidated metrics ──────────────────────────────────────────────────
  //
  // "Codex calls" = invocations of the actual `codex` binary (OpenAI Codex CLI).
  //   - Planner uses codex binary when tasks.planner_provider='codex' (DB)
  //   - Worker uses codex binary only when copilot-daemon falls back:
  //       "gh copilot rc=1, falling back to codex" or "Executing task with Codex (real)"
  //
  // "Copilot-daemon calls" = worker invocations via copilot-daemon (primary: gh copilot).
  //   These are NOT codex calls unless a fallback happened.
  //
  // Separation is important: 5617 artifacts from Apr 24-25 are copilot-daemon (gh copilot),
  // but only 2 of them fell back to the actual Codex binary.

  // planner_codex_calls: tasks where planner_provider='codex' OR successful planner runs
  const planner_codex_calls = Math.max(dbPlannerRuns.length, dbPlannerCodex.length);

  // worker_codex_calls: ONLY actual `codex` binary invocations
  //   = explicit daemon codex-exec events + DB worker_provider='codex' tasks
  //   (does NOT include copilot-daemon primary gh-copilot calls)
  const worker_codex_calls = daemonCodexExec.length + dbWorkerCodex.length;

  // worker_copilot_daemon_calls: all copilot-daemon (gh copilot primary) worker invocations
  const worker_copilot_daemon_calls = Math.max(
    copilotDaemonArtifacts.length,
    dbWorkerCopilot.length,
    daemonCompleted.length + daemonCriticalFailure.length + daemonProviderEvents.length,
  );

  // total_codex_calls = strict Codex binary calls only (planner + worker)
  const total_codex_calls = planner_codex_calls + worker_codex_calls;

  const retry_calls       = dbRetryRuns.length + dbReplansRequired.length;
  const recovery_calls    = dbRecoveryRuns.length;
  const timeout_count     = daemonTimeout.length + daemonCriticalFailure.length + workerCodexFailed.length;
  const invalid_delivery_count = dbInvalidGate.length;
  const result_json_success_count = workerSuccess.length + dbResultSuccess.length + daemonCompleted.length;
  const mechanical_fallback_count = daemonFallbackToCodex.length;
  const tasks_with_multiple_attempts = db.multiAttemptTasks.length;

  // Top tasks by Codex calls (from DB)
  const top_tasks_by_codex_calls = db.topByRuns.slice(0, limit).map(t => ({
    task_id: t.task_id,
    run_count: t.run_count,
    title: (t.objective || '').slice(0, 80),
    planner: t.planner_provider || '-',
    worker: t.worker_provider || '-',
    status: t.status || '-',
  }));

  return {
    window: { label, cutoff: cutoffISO, generated_at: new Date().toISOString() },
    metrics: {
      total_codex_calls,
      planner_codex_calls,
      worker_codex_calls,
      worker_copilot_daemon_calls,
      retry_calls,
      recovery_calls,
      timeout_count,
      invalid_delivery_count,
      result_json_success_count,
      mechanical_fallback_count,
      tasks_with_multiple_attempts,
    },
    top_tasks_by_codex_calls,
    data_sources: {
      db: {
        tasks_in_window: db.tasksInWindow.length,
        agent_tasks_in_window: db.agentTasksInWindow.length,
        planner_runs_success: dbPlannerRuns.length,
        worker_runs_success: dbWorkerRuns.length,
        tasks_replan_required: dbReplansRequired.length,
        tasks_result_json: dbResultSuccess.length,
        tasks_gate_invalid: dbInvalidGate.length,
      },
      worker_tick_out: {
        total_ticks: workerOutEntries.length,
        skipped_hard_off: workerSkipped.length,
        failed_ticks: workerFailed.length,
        codex_exit_errors: workerCodexFailed.length,
        result_json_delivered: workerSuccess.length,
      },
      worker_tick_err: {
        total_events: workerErrEvents.length,
        provider_switch_events: daemonProviderEvents.length,
        fallback_to_codex: daemonFallbackToCodex.length,
        codex_executions: daemonCodexExec.length,
        completed: daemonCompleted.length,
        critical_failures: daemonCriticalFailure.length,
        timeouts: daemonTimeout.length,
      },
      planner_tick_out: {
        total_ticks: plannerOutEntries.length,
        skipped_hard_off: plannerSkipped.length,
        task_created: plannerSuccess.length,
        codex_calls_inferred: plannerCodexCall.length,
      },
      task_artifacts: {
        total_in_window: artifacts.length,
        codex_provider: codexArtifacts.length,
        copilot_daemon: copilotDaemonArtifacts.length,
        deterministic: deterministicArtifacts.length,
        hard_off_bypass: hardOffArtifacts.length,
      },
    },
    detail: {
      copilot_daemon_events: workerErrEvents.slice(0, limit).map(e => ({
        ts: e.ts, level: e.level, component: e.component, msg: e.message.slice(0, 100),
      })),
      recent_artifacts: artifacts.slice(0, limit).map(a => ({
        ts: a.ts, provider: a.provider, taskType: a.taskType, title: a.title.slice(0, 80),
        isCodex: a.isCodex, isCopilotDaemon: a.isCopilotDaemon,
        isDeterministic: a.isDeterministic, isHardOff: a.isHardOff,
      })),
    },
  };
}

// ─── Rendering ───────────────────────────────────────────────────────────────

function renderReport(report) {
  const { window: win, metrics: m, top_tasks_by_codex_calls, data_sources: ds } = report;
  const line = '─'.repeat(72);

  console.log('\n' + line);
  console.log(' 🤖  Orchestrator Codex / Copilot Usage Report');
  console.log(line);
  console.log(` Window : ${win.label}`);
  console.log(` Cutoff : ${win.cutoff}`);
  console.log(` Report : ${win.generated_at}`);
  console.log(line);

  console.log('\n📊  SUMMARY METRICS\n');
  const pad = (s, n) => String(s).padStart(n);
  const rows = [
    ['total_codex_calls (strict)',   m.total_codex_calls],
    ['  planner_codex_calls',        m.planner_codex_calls],
    ['  worker_codex_calls',         m.worker_codex_calls],
    ['worker_copilot_daemon_calls',  m.worker_copilot_daemon_calls],
    ['retry_calls',                  m.retry_calls],
    ['recovery_calls',               m.recovery_calls],
    ['timeout_count',                m.timeout_count],
    ['invalid_delivery_count',       m.invalid_delivery_count],
    ['result_json_success_count',    m.result_json_success_count],
    ['mechanical_fallback_count',    m.mechanical_fallback_count],
    ['tasks_with_multiple_attempts', m.tasks_with_multiple_attempts],
  ];
  for (const [label, val] of rows) {
    const flag = val > 0 ? '' : '  (zero)';
    console.log(`  ${label.padEnd(34)}${pad(val, 6)}${flag}`);
  }

  // Top tasks
  if (top_tasks_by_codex_calls.length > 0) {
    console.log('\n📋  TOP TASKS BY CODEX CALLS\n');
    for (const t of top_tasks_by_codex_calls) {
      console.log(`  [#${t.task_id}] runs=${t.run_count}  planner=${t.planner}  worker=${t.worker}`);
      console.log(`       ${t.title}`);
    }
  } else {
    console.log('\n📋  TOP TASKS BY CODEX CALLS: (none in window)');
  }

  // Data source breakdown
  console.log('\n📁  DATA SOURCES BREAKDOWN\n');

  console.log('  [orchestrator.db]');
  console.log(`    tasks in window          : ${ds.db.tasks_in_window}`);
  console.log(`    agent_tasks in window    : ${ds.db.agent_tasks_in_window}`);
  console.log(`    planner runs (SUCCESS)   : ${ds.db.planner_runs_success}`);
  console.log(`    worker runs (SUCCESS)    : ${ds.db.worker_runs_success}`);
  console.log(`    tasks REPLAN_REQUIRED    : ${ds.db.tasks_replan_required}`);
  console.log(`    tasks with result.json   : ${ds.db.tasks_result_json}`);
  console.log(`    gate invalid/rejected    : ${ds.db.tasks_gate_invalid}`);

  console.log('\n  [worker_tick.out.log]');
  console.log(`    ticks in window          : ${ds.worker_tick_out.total_ticks}`);
  console.log(`    GLOBAL_HARD_OFF skipped  : ${ds.worker_tick_out.skipped_hard_off}`);
  console.log(`    failed ticks             : ${ds.worker_tick_out.failed_ticks}`);
  console.log(`    [Codex] exit errors      : ${ds.worker_tick_out.codex_exit_errors}`);
  console.log(`    result_json delivered    : ${ds.worker_tick_out.result_json_delivered}`);

  console.log('\n  [worker_tick.err.log — copilot-daemon]');
  console.log(`    events in window         : ${ds.worker_tick_err.total_events}`);
  console.log(`    provider switch events   : ${ds.worker_tick_err.provider_switch_events}`);
  console.log(`    fallback → Codex         : ${ds.worker_tick_err.fallback_to_codex}`);
  console.log(`    Codex exec invocations   : ${ds.worker_tick_err.codex_executions}`);
  console.log(`    completed                : ${ds.worker_tick_err.completed}`);
  console.log(`    critical failures        : ${ds.worker_tick_err.critical_failures}`);
  console.log(`    timeouts                 : ${ds.worker_tick_err.timeouts}`);

  console.log('\n  [planner_tick.out.log]');
  console.log(`    ticks in window          : ${ds.planner_tick_out.total_ticks}`);
  console.log(`    GLOBAL_HARD_OFF skipped  : ${ds.planner_tick_out.skipped_hard_off}`);
  console.log(`    task_created ticks       : ${ds.planner_tick_out.task_created}`);
  console.log(`    codex calls inferred     : ${ds.planner_tick_out.codex_calls_inferred}`);

  console.log('\n  [task artifact files]');
  console.log(`    total completed in window: ${ds.task_artifacts.total_in_window}`);
  console.log(`    provider=codex           : ${ds.task_artifacts.codex_provider}`);
  console.log(`    provider=copilot-daemon  : ${ds.task_artifacts.copilot_daemon}`);
  console.log(`    deterministic (safe_exec): ${ds.task_artifacts.deterministic}`);
  console.log(`    llm_execution hard-off   : ${ds.task_artifacts.hard_off_bypass}`);

  // Detail: copilot-daemon events
  if (report.detail.copilot_daemon_events.length > 0) {
    console.log('\n🔍  COPILOT-DAEMON EVENTS (in window)\n');
    for (const e of report.detail.copilot_daemon_events) {
      const lvlColor = e.level === 'ERROR' ? '❌' : e.level === 'WARNING' ? '⚠️' : 'ℹ️';
      console.log(`  ${lvlColor} ${e.ts}  [${e.component}]  ${e.msg}`);
    }
  }

  // Detail: recent artifacts
  if (report.detail.recent_artifacts.length > 0) {
    console.log('\n📄  RECENT COMPLETED TASK ARTIFACTS (in window)\n');
    for (const a of report.detail.recent_artifacts) {
      const badge = a.isCodex ? '[CODEX]'
                  : a.isCopilotDaemon ? '[COPILOT-DAEMON]'
                  : a.isDeterministic ? '[DETERMINISTIC]'
                  : a.isHardOff ? '[HARD-OFF]'
                  : '[OTHER]';
      console.log(`  ${badge.padEnd(18)} ${a.ts ?? 'ts?'}  ${a.title}`);
    }
  } else {
    console.log('\n📄  RECENT COMPLETED TASK ARTIFACTS: (none in window)');
  }

  console.log('\n' + line);
  console.log(' ✅  Report complete. All data read-only. No APIs called. No files modified.');
  console.log(line + '\n');
}

// ─── Entry point ─────────────────────────────────────────────────────────────

const opts = parseCLI(process.argv);
const report = buildReport(opts);
renderReport(report);

// Also emit raw JSON to stdout if --json flag
if (process.argv.includes('--json')) {
  console.log('\n--- JSON ---\n');
  console.log(JSON.stringify(report, null, 2));
}
