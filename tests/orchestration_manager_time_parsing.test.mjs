import test from 'node:test';
import assert from 'node:assert/strict';

import {
  OrchestrationManager,
  _find_recent_runner_outcome,
  _runner_outcome_feedback,
  _countdown_state,
  _parse_utc_timestamp,
  _next_tick_by_runner,
} from '../src/ui/OrchestrationManager.js';

test('parses microsecond UTC timestamps returned by orchestrator APIs', () => {
  const parsed = _parse_utc_timestamp('2026-04-22T15:00:54.222665');
  assert.ok(parsed instanceof Date);
  assert.equal(parsed.toISOString(), '2026-04-22T15:00:54.222Z');
});

test('computes next tick from microsecond timestamps', () => {
  const originalNow = Date.now;
  Date.now = () => Date.parse('2026-04-22T15:01:00.000Z');

  try {
    const next = _next_tick_by_runner([
      { runner: 'worker', tick_at: '2026-04-22T15:00:54.222665' },
    ], 'worker');

    assert.ok(next instanceof Date);
    assert.equal(next.toISOString(), '2026-04-22T15:10:54.222Z');
  } finally {
    Date.now = originalNow;
  }
});

test('formats countdown labels for live next-tick display', () => {
  const target = new Date('2026-04-22T15:10:54.222Z');
  assert.deepEqual(
    _countdown_state(target, Date.parse('2026-04-22T15:09:58.000Z')),
    { label: '0m 56s 後', due: false }
  );
  assert.deepEqual(
    _countdown_state(target, Date.parse('2026-04-22T15:10:54.222Z')),
    { label: '0m 0s 後', due: true }
  );
});

test('auto refreshes orchestrator data when countdown reaches zero', async () => {
  const nodes = new Map([
    ['orc-next-planner-at', { textContent: '' }],
    ['orc-next-worker-at', { textContent: '' }],
    ['orc-next-tick-note', { textContent: '' }],
  ]);
  const originalDocument = global.document;
  const originalNow = Date.now;

  global.document = {
    getElementById(id) {
      return nodes.get(id) || null;
    },
  };

  const manager = new OrchestrationManager(null);
  manager._plannerNextAt = new Date('2026-04-22T15:10:00.000Z');
  manager._workerNextAt = null;

  try {
    let refreshCount = 0;
    manager._loadAll = async () => {
      refreshCount += 1;
      manager._plannerNextAt = new Date('2026-04-22T15:20:00.000Z');
    };

    Date.now = () => Date.parse('2026-04-22T15:10:00.000Z');
    manager._tickCountdown();
    assert.equal(nodes.get('orc-next-planner-at').textContent, '0m 0s 後');
    assert.equal(nodes.get('orc-next-tick-note').textContent, '排程到點，正在自動刷新…');
    await manager._countdownRefreshPromise;

    assert.equal(refreshCount, 1);

    Date.now = () => Date.parse('2026-04-22T15:10:01.000Z');
    manager._tickCountdown();
    assert.equal(nodes.get('orc-next-planner-at').textContent, '9m 59s 後');
    assert.equal(nodes.get('orc-next-tick-note').textContent, '每秒倒數，歸零後自動刷新');
  } finally {
    Date.now = originalNow;
    global.document = originalDocument;
  }
});

test('detects the first terminal planner outcome after manual trigger', () => {
  const runs = [
    { runner: 'planner', tick_at: '2026-04-22T16:01:06.775365', outcome: 'PLANNER_FALLBACK_LOCAL', message: 'fallback' },
    { runner: 'planner', tick_at: '2026-04-22T16:01:06.778214', outcome: 'PLANNER_SKIP_PROVIDER_FAILURE', message: 'usage limit' },
    { runner: 'orchestrator', tick_at: '2026-04-22T16:01:18.305031', outcome: 'PLANNER_MANUAL_TRIGGERED', message: 'triggered' },
  ];

  const outcome = _find_recent_runner_outcome(runs, 'planner', Date.parse('2026-04-22T16:01:00.000Z'));
  assert.equal(outcome?.outcome, 'PLANNER_SKIP_PROVIDER_FAILURE');
});

test('maps planner provider failures to human-readable UI feedback', () => {
  assert.deepEqual(
    _runner_outcome_feedback({
      outcome: 'PLANNER_SKIP_PROVIDER_FAILURE',
      message: 'Planner runtime blocked; no task created: codex usage limit',
    }),
    { level: 'warning', message: 'Planner 未建立任務：Codex / Claude 額度已用完。' }
  );

  assert.deepEqual(
    _runner_outcome_feedback({
      outcome: 'PLANNER_PRODUCED',
      message: 'Task created',
    }),
    { level: 'success', message: 'Planner 已建立新任務。' }
  );
});

test('keeps inline runner feedback visible across provider reloads', () => {
  const nodes = new Map([
    ['orc-provider-hint', { textContent: '', style: {} }],
  ]);
  const originalDocument = global.document;
  const originalNow = Date.now;
  const originalSetTimeout = global.setTimeout;
  const originalClearTimeout = global.clearTimeout;

  global.document = {
    getElementById(id) {
      return nodes.get(id) || null;
    },
  };
  Date.now = () => Date.parse('2026-04-22T16:10:00.000Z');
  global.setTimeout = () => 1;
  global.clearTimeout = () => {};

  try {
    const manager = new OrchestrationManager(null);
    const providerData = {
      planner_options: [{ label: 'Codex CLI', available: true }],
      worker_options: [{ value: 'copilot-daemon', label: 'GitHub Copilot Daemon', available: true, reason: 'Daemon running (PID 1493)' }],
    };

    manager._lastProviderData = providerData;
    manager._showInlineRunnerFeedback('info', 'Planner 已送出，正在等待結果…', 12000);
    manager._renderProviderHint(providerData);

    assert.equal(nodes.get('orc-provider-hint').textContent, 'Planner 已送出，正在等待結果…');
    assert.equal(nodes.get('orc-provider-hint').style.color, 'var(--accent-color, #58a6ff)');

    Date.now = () => Date.parse('2026-04-22T16:10:13.000Z');
    manager._renderProviderHint(providerData);

    assert.match(nodes.get('orc-provider-hint').textContent, /Copilot Daemon：Daemon running/);
  } finally {
    global.document = originalDocument;
    Date.now = originalNow;
    global.setTimeout = originalSetTimeout;
    global.clearTimeout = originalClearTimeout;
  }
});
