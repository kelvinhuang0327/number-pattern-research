const MATRIX_COLUMNS = [
  'lottery',
  'strategy_id',
  'window_segment',
  'top_k',
  'sample_size_draws',
  'sample_size_rows',
  'm1_rate',
  'm2_rate',
  'm3_rate',
  'm3plus_hit_rate',
  'baseline_mode',
  'baseline_value',
  'delta',
  'delta_pp',
  'inferential_status',
  'readiness_status',
];

const COVERAGE_COLUMNS = [
  'lottery',
  'strategy_id',
  'rows',
  'distinct_draws',
  'available_windows',
  'available_top_k',
  'readiness',
  'blocked_reason',
];

const DATA_FILES = {
  manifest: 'manifest.json',
  matrix: 'd5_hit_rate_matrix.csv',
  coverage: 'strategy_coverage_summary.csv',
  contract: 'optimizer_input_contract.json',
  powerlotto: 'powerlotto_exclusion_note.md',
};

const COMBINATION_DATA_FILES = {
  manifest: 'source_provenance.json',
  metrics: 'strategy_combination_metrics.csv',
  candidates: 'top_descriptive_candidates.csv',
  summary: 'window_summary.csv',
};

const BASELINE_DATA_FILE = 'baseline_summary.json';

const NOT_COMPUTED_COLUMNS = new Set(['baseline_value', 'delta', 'delta_pp']);
const RATE_COLUMNS = new Set(['m1_rate', 'm2_rate', 'm3_rate', 'm3plus_hit_rate']);
const INTEGER_COLUMNS = new Set(['top_k', 'sample_size_draws', 'sample_size_rows', 'rows', 'distinct_draws']);
const DETAIL_RATE_COLUMNS = ['m1_rate', 'm2_rate', 'm3_rate', 'm3plus_hit_rate'];
const DETAIL_STATUS_COLUMNS = [
  'inferential_status',
  'readiness_status',
  'eligibility_status',
  'exclusion_reason',
];
const DETAIL_RATE_LABELS = {
  m1_rate: 'm1_rate summary',
  m2_rate: 'm2_rate summary',
  m3_rate: 'm3_rate summary',
  m3plus_hit_rate: 'm3plus_hit_rate summary',
};
const COMPARE_LIMIT = 4;
const REVIEW_STATE_HASH_PREFIX = 'd5-review';
const REVIEW_STATE_VERSION = '1';
const VALID_TABS = new Set(['combination', 'matrix', 'coverage', 'contract', 'powerlotto', 'limitations']);
const SNAPSHOT_SOURCE_LABEL = 'P299A static artifact-backed D5 demo';
const SNAPSHOT_CAVEATS = [
  'Retrospective-only.',
  'No future prediction.',
  'No betting recommendation.',
  'No production readiness.',
  'Baselines/deltas not computed.',
  'POWER_LOTTO full scoring excluded.',
];
const REVIEW_PRESETS = {
  'biglotto-triple': {
    tab: 'matrix',
    matrixLottery: 'BIG_LOTTO',
    matrixSearch: 'triple',
    coverageLottery: 'BIG_LOTTO',
    coverageSearch: 'triple',
    status: 'Preset applied: BIG_LOTTO rows filtered by strategy_id search term "triple".',
  },
  'daily539-acb': {
    tab: 'matrix',
    matrixLottery: 'DAILY_539',
    matrixSearch: 'acb',
    coverageLottery: 'DAILY_539',
    coverageSearch: 'acb',
    status: 'Preset applied: DAILY_539 rows filtered by strategy_id search term "acb".',
  },
  'powerlotto-exclusion': {
    tab: 'powerlotto',
    matrixLottery: '',
    matrixSearch: '',
    coverageLottery: '',
    coverageSearch: '',
    status: 'Preset applied: POWER_LOTTO exclusion note is visible.',
  },
  reset: {
    tab: 'matrix',
    matrixLottery: '',
    matrixSearch: '',
    coverageLottery: '',
    coverageSearch: '',
    status: 'Review filters reset.',
  },
};

let state = {
  matrixRows: [],
  coverageRows: [],
  contract: null,
  powerlottoNote: '',
  manifest: null,
  combinationManifest: null,
  combinationMetricRows: [],
  combinationCandidateRows: [],
  combinationSummaryRows: [],
  baselineSummary: null,
};

let compareKeys = [];
let activeDetailKey = '';

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function isNullish(value) {
  return value == null || String(value).trim() === '' || String(value).trim().toUpperCase() === 'NULL';
}

function displayValue(row, key) {
  const value = row[key];
  if (isNullish(value)) {
    return NOT_COMPUTED_COLUMNS.has(key) ? 'Not computed' : '';
  }
  if (RATE_COLUMNS.has(key)) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(2)}%` : escapeHtml(value);
  }
  if (INTEGER_COLUMNS.has(key)) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toLocaleString() : escapeHtml(value);
  }
  if (key === 'baseline_mode' && value === 'not_computed') {
    return 'not_computed';
  }
  return escapeHtml(value);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      row.push(cell);
      cell = '';
      continue;
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') index += 1;
      row.push(cell);
      if (row.some((item) => item !== '')) rows.push(row);
      row = [];
      cell = '';
      continue;
    }

    cell += char;
  }

  row.push(cell);
  if (row.some((item) => item !== '')) rows.push(row);
  return rows;
}

function csvToObjects(text) {
  const rows = parseCsv(text);
  const headers = rows.shift() || [];
  return rows.map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ''])));
}

async function fetchText(root, file) {
  const response = await fetch(`${root}/${file}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`${file}: HTTP ${response.status}`);
  }
  return response.text();
}

function setError(message) {
  const error = byId('d5-load-error');
  if (!error) return;
  error.hidden = !message;
  error.textContent = message || '';
}

function setText(id, value) {
  const node = byId(id);
  if (node) node.textContent = value;
}

function setControlValue(id, value) {
  const node = byId(id);
  if (node) node.value = value;
}

function setSelectValue(id, value) {
  const node = byId(id);
  if (!node) return;
  const nextValue = String(value || '');
  if (nextValue && ![...node.options].some((option) => option.value === nextValue)) return;
  node.value = nextValue;
}

function uniqueValues(rows, key) {
  return [...new Set(rows.map((row) => row[key]).filter(Boolean))];
}

function uniqueDisplayValues(rows, key) {
  const values = rows.map((row) => displayValue(row, key)).filter(Boolean);
  return [...new Set(values)];
}

function splitPipeValues(value) {
  if (isNullish(value)) return [];
  return String(value).split('|').map((item) => item.trim()).filter(Boolean);
}

function formatList(values, emptyLabel = 'None') {
  if (!values.length) return emptyLabel;
  return values.map((value) => escapeHtml(value)).join(', ');
}

function summarizeNumbers(rows, key) {
  const numbers = rows
    .map((row) => Number(row[key]))
    .filter((value) => Number.isFinite(value));
  if (!numbers.length) return 'Not available';
  const min = Math.min(...numbers);
  const max = Math.max(...numbers);
  if (min === max) return min.toLocaleString();
  return `${min.toLocaleString()} - ${max.toLocaleString()}`;
}

function summarizeRates(rows, key) {
  const values = rows
    .map((row) => Number(row[key]))
    .filter((value) => Number.isFinite(value))
    .map((value) => value * 100);
  if (!values.length) return 'Not available';
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return `${min.toFixed(2)}%`;
  return `${min.toFixed(2)}% - ${max.toFixed(2)}%`;
}

function detailKey(lottery, strategyId) {
  return `${lottery || ''}::${strategyId || ''}`;
}

function parseDetailKey(key) {
  const value = String(key || '');
  const delimiterIndex = value.indexOf('::');
  if (delimiterIndex < 0) return ['', ''];
  return [
    value.slice(0, delimiterIndex),
    value.slice(delimiterIndex + 2),
  ];
}

function findCoverageRow(lottery, strategyId) {
  return state.coverageRows.find((row) => row.lottery === lottery && row.strategy_id === strategyId) || null;
}

function findMatrixRows(lottery, strategyId) {
  return state.matrixRows.filter((row) => row.lottery === lottery && row.strategy_id === strategyId);
}

function selectedStrategySummary(lottery, strategyId) {
  const matrixRows = findMatrixRows(lottery, strategyId);
  const coverageRow = findCoverageRow(lottery, strategyId);
  const windows = matrixRows.length
    ? uniqueValues(matrixRows, 'window_segment')
    : splitPipeValues(coverageRow?.available_windows);
  const topKValues = matrixRows.length
    ? sortMaybeNumeric(uniqueValues(matrixRows, 'top_k'))
    : sortMaybeNumeric(splitPipeValues(coverageRow?.available_top_k));
  const baselineModes = uniqueDisplayValues(matrixRows, 'baseline_mode');
  const baselineValues = uniqueDisplayValues(matrixRows, 'baseline_value');
  const deltaValues = uniqueDisplayValues(matrixRows, 'delta');
  const deltaPpValues = uniqueDisplayValues(matrixRows, 'delta_pp');

  return {
    key: detailKey(lottery, strategyId),
    lottery,
    strategyId,
    matrixRows,
    coverageRow,
    windows,
    topKValues,
    totalRows: coverageRow ? displayValue(coverageRow, 'rows') : matrixRows.length.toLocaleString(),
    distinctDraws: coverageRow ? displayValue(coverageRow, 'distinct_draws') : summarizeNumbers(matrixRows, 'sample_size_draws'),
    sampleDraws: summarizeNumbers(matrixRows, 'sample_size_draws'),
    sampleRows: summarizeNumbers(matrixRows, 'sample_size_rows'),
    rates: Object.fromEntries(DETAIL_RATE_COLUMNS.map((key) => [key, summarizeRates(matrixRows, key)])),
    baselineMode: formatList(baselineModes, 'Not available'),
    baselineValue: formatList(baselineValues, 'Not computed'),
    delta: formatList(deltaValues, 'Not computed'),
    deltaPp: formatList(deltaPpValues, 'Not computed'),
    statuses: Object.fromEntries(DETAIL_STATUS_COLUMNS.map((key) => [
      key,
      formatList(uniqueDisplayValues(matrixRows, key), 'Not available'),
    ])),
    coverageReadiness: coverageRow ? displayValue(coverageRow, 'readiness') : 'Not available',
    coverageBlockedReason: coverageRow ? (displayValue(coverageRow, 'blocked_reason') || 'None') : 'Not available',
  };
}

function detailMetric(label, value) {
  return `
    <div class="d5-detail-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function detailField(label, value) {
  return `
    <div class="d5-detail-field">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function renderOptions(select, values, allLabel) {
  if (!select) return;
  select.innerHTML = `<option value="">${escapeHtml(allLabel)}</option>` +
    values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
}

function sortMaybeNumeric(values) {
  return [...values].sort((left, right) => {
    const leftNumber = Number(left);
    const rightNumber = Number(right);
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
      return leftNumber - rightNumber;
    }
    return String(left).localeCompare(String(right));
  });
}

function strategyMatches(row, query) {
  if (!query) return true;
  return String(row.strategy_id || '').toLowerCase().includes(query.trim().toLowerCase());
}

function rowCountLabel(filtered, total) {
  return `Showing ${filtered.toLocaleString()} of ${total.toLocaleString()} rows`;
}

function renderDetailWindowRows(rows) {
  if (!rows.length) {
    return '<p class="d5-detail-empty">No matrix rows are available for this strategy in the copied artifact.</p>';
  }

  return `
    <div class="d5-detail-table-wrap">
      <table class="d5-detail-table">
        <thead>
          <tr>
            <th>window_segment</th>
            <th>top_k</th>
            <th>sample_size_draws</th>
            <th>sample_size_rows</th>
            <th>m1_rate</th>
            <th>m2_rate</th>
            <th>m3_rate</th>
            <th>m3plus_hit_rate</th>
            <th>baseline_value</th>
            <th>delta_pp</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${displayValue(row, 'window_segment')}</td>
              <td>${displayValue(row, 'top_k')}</td>
              <td>${displayValue(row, 'sample_size_draws')}</td>
              <td>${displayValue(row, 'sample_size_rows')}</td>
              <td>${displayValue(row, 'm1_rate')}</td>
              <td>${displayValue(row, 'm2_rate')}</td>
              <td>${displayValue(row, 'm3_rate')}</td>
              <td>${displayValue(row, 'm3plus_hit_rate')}</td>
              <td>${displayValue(row, 'baseline_value')}</td>
              <td>${displayValue(row, 'delta_pp')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderStrategyDetail(lottery, strategyId, source = 'row') {
  const drawer = byId('d5-strategy-detail-drawer');
  const body = byId('d5-detail-body');
  const title = byId('d5-detail-title');
  const subtitle = byId('d5-detail-subtitle');
  const addButton = byId('d5-detail-add-compare');
  if (!drawer || !body || !title || !subtitle) return;

  const summary = selectedStrategySummary(lottery, strategyId);
  activeDetailKey = summary.key;
  updateDetailCompareButton();

  title.textContent = strategyId;
  subtitle.textContent = `${lottery} historical strategy metrics from ${source === 'coverage' ? 'coverage' : 'matrix'} artifact rows.`;
  body.innerHTML = `
    <div class="d5-detail-metrics" aria-label="Selected strategy summary">
      ${detailMetric('strategy_id', escapeHtml(strategyId))}
      ${detailMetric('lottery', escapeHtml(lottery))}
      ${detailMetric('Total rows available', summary.totalRows)}
      ${detailMetric('Matrix rows', summary.matrixRows.length.toLocaleString())}
      ${detailMetric('Distinct draws', summary.distinctDraws || 'Not available')}
      ${detailMetric('Distinct window segments', summary.windows.length.toLocaleString())}
      ${detailMetric('Distinct top_k values', summary.topKValues.length.toLocaleString())}
    </div>

    <div class="d5-detail-grid">
      ${detailField('Window segments', formatList(summary.windows, 'Not available'))}
      ${detailField('top_k values', formatList(summary.topKValues, 'Not available'))}
      ${detailField('sample_size_draws summary', summary.sampleDraws)}
      ${detailField('sample_size_rows summary', summary.sampleRows)}
      ${DETAIL_RATE_COLUMNS.map((key) => detailField(DETAIL_RATE_LABELS[key], summary.rates[key])).join('')}
      ${detailField('baseline_mode status', summary.baselineMode)}
      ${detailField('baseline_value status', summary.baselineValue)}
      ${detailField('delta status', summary.delta)}
      ${detailField('delta_pp status', summary.deltaPp)}
      ${DETAIL_STATUS_COLUMNS.map((key) => detailField(key, summary.statuses[key])).join('')}
      ${detailField('coverage readiness', summary.coverageReadiness)}
      ${detailField('coverage blocked_reason', summary.coverageBlockedReason)}
    </div>

    <div class="d5-detail-section">
      <h4>Historical windows/top_k rows</h4>
      ${renderDetailWindowRows(summary.matrixRows)}
    </div>
  `;
  if (addButton) addButton.dataset.detailKey = summary.key;
  drawer.hidden = false;
  drawer.classList.add('is-open');
}

function closeStrategyDetail() {
  const drawer = byId('d5-strategy-detail-drawer');
  if (!drawer) return;
  drawer.classList.remove('is-open');
  drawer.hidden = true;
}

function compareLabel() {
  return `${compareKeys.length} selected`;
}

function updateDetailCompareButton() {
  const button = byId('d5-detail-add-compare');
  if (!button) return;
  const isSelected = activeDetailKey && compareKeys.includes(activeDetailKey);
  const limitReached = compareKeys.length >= COMPARE_LIMIT && !isSelected;
  button.disabled = !activeDetailKey || limitReached;
  button.textContent = isSelected ? 'Selected for compare' : 'Add to compare';
}

function updateCompareRowButtons() {
  document.querySelectorAll('[data-compare-key]').forEach((button) => {
    const key = button.dataset.compareKey || '';
    const isSelected = compareKeys.includes(key);
    const limitReached = compareKeys.length >= COMPARE_LIMIT && !isSelected;
    button.disabled = limitReached;
    button.textContent = isSelected ? 'Selected' : 'Compare';
    button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
  });
}

function compareField(label, value) {
  return `
    <div class="d5-compare-field">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function compareSnapshotSectionMarkup() {
  return `
    <div class="d5-compare-snapshot" aria-label="Comparison snapshot export">
      <div class="d5-compare-snapshot-header">
        <div>
          <h4>Comparison snapshot</h4>
          <p>Copyable review text generated from the selected static artifact rows only.</p>
        </div>
        <button id="d5-compare-snapshot-copy" class="d5-secondary-button" type="button" disabled>Copy comparison snapshot</button>
      </div>
      <div id="d5-compare-snapshot-status" class="d5-compare-snapshot-status" aria-live="polite">Select at least 2 strategies to enable snapshot copy.</div>
      <pre id="d5-compare-snapshot-output" class="d5-compare-snapshot-output" tabindex="0" aria-label="Manual comparison snapshot copy fallback">Select 2-4 strategies to generate a review-safe comparison snapshot.</pre>
    </div>
  `;
}

function ensureCompareSnapshotSection() {
  if (byId('d5-compare-snapshot-output')) return;
  const panel = byId('d5-compare-panel');
  const caveats = panel?.querySelector('.d5-compare-caveats');
  if (!panel || !caveats) return;
  caveats.insertAdjacentHTML('beforebegin', compareSnapshotSectionMarkup());
}

function localGeneratedAt() {
  return new Date().toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZoneName: 'short',
  });
}

function selectedSummaries() {
  return compareKeys.map((key) => {
    const [lottery, strategyId] = parseDetailKey(key);
    return selectedStrategySummary(lottery, strategyId);
  });
}

function snapshotStrategyPayload(summary) {
  return {
    strategy_id: summary.strategyId,
    lottery: summary.lottery,
    row_count: summary.totalRows,
    matrix_rows: summary.matrixRows.length,
    distinct_window_segments: summary.windows.length,
    window_segments: summary.windows,
    distinct_top_k_values: summary.topKValues.length,
    top_k_values: summary.topKValues,
    sample_size_draws_summary: summary.sampleDraws,
    sample_size_rows_summary: summary.sampleRows,
    rates: {
      m1_rate: summary.rates.m1_rate,
      m2_rate: summary.rates.m2_rate,
      m3_rate: summary.rates.m3_rate,
      m3plus_hit_rate: summary.rates.m3plus_hit_rate,
    },
    baseline_mode_status: summary.baselineMode,
    baseline_value_status: summary.baselineValue,
    delta_status: summary.delta,
    delta_pp_status: summary.deltaPp,
    inferential_status: summary.statuses.inferential_status,
    readiness_status: summary.statuses.readiness_status,
    eligibility_status: summary.statuses.eligibility_status,
    exclusion_reason: summary.statuses.exclusion_reason,
    coverage_readiness: summary.coverageReadiness,
    coverage_blocked_reason: summary.coverageBlockedReason,
  };
}

function buildCompareSnapshot() {
  if (compareKeys.length < 2) {
    return 'Select 2-4 strategies to generate a review-safe comparison snapshot.';
  }

  const generatedAt = localGeneratedAt();
  const strategies = selectedSummaries().map(snapshotStrategyPayload);
  const payload = {
    generated_at: generatedAt,
    source_label: SNAPSHOT_SOURCE_LABEL,
    selected_strategy_count: strategies.length,
    caveats: SNAPSHOT_CAVEATS,
    strategies,
  };

  const lines = [
    '# D5 selected strategy comparison snapshot',
    '',
    `generated_at: ${generatedAt}`,
    `source_label: ${SNAPSHOT_SOURCE_LABEL}`,
    `selected_strategy_count: ${strategies.length}`,
    '',
    '## No-claims caveats',
    ...SNAPSHOT_CAVEATS.map((caveat) => `- ${caveat}`),
    '',
    '## Selected strategies',
  ];

  strategies.forEach((strategy, index) => {
    lines.push(
      '',
      `### ${index + 1}. ${strategy.strategy_id}`,
      `- lottery: ${strategy.lottery}`,
      `- row count: ${strategy.row_count}`,
      `- matrix rows: ${strategy.matrix_rows}`,
      `- distinct window segments: ${strategy.distinct_window_segments}`,
      `- window segments: ${strategy.window_segments.join(', ') || 'Not available'}`,
      `- distinct top_k values: ${strategy.distinct_top_k_values}`,
      `- top_k values: ${strategy.top_k_values.join(', ') || 'Not available'}`,
      `- sample_size_draws summary: ${strategy.sample_size_draws_summary}`,
      `- sample_size_rows summary: ${strategy.sample_size_rows_summary}`,
      `- m1_rate summary: ${strategy.rates.m1_rate}`,
      `- m2_rate summary: ${strategy.rates.m2_rate}`,
      `- m3_rate summary: ${strategy.rates.m3_rate}`,
      `- m3plus_hit_rate summary: ${strategy.rates.m3plus_hit_rate}`,
      `- baseline_mode status: ${strategy.baseline_mode_status}`,
      `- baseline_value status: ${strategy.baseline_value_status}`,
      `- delta status: ${strategy.delta_status}`,
      `- delta_pp status: ${strategy.delta_pp_status}`,
      `- inferential_status: ${strategy.inferential_status}`,
      `- readiness_status: ${strategy.readiness_status}`,
      `- eligibility_status: ${strategy.eligibility_status}`,
      `- exclusion_reason: ${strategy.exclusion_reason}`,
      `- coverage readiness: ${strategy.coverage_readiness}`,
      `- coverage blocked_reason: ${strategy.coverage_blocked_reason}`,
    );
  });

  lines.push('', '## JSON', '```json', JSON.stringify(payload, null, 2), '```');
  return lines.join('\n');
}

function renderCompareSnapshot() {
  ensureCompareSnapshotSection();
  const output = byId('d5-compare-snapshot-output');
  const button = byId('d5-compare-snapshot-copy');
  const status = byId('d5-compare-snapshot-status');
  if (!output || !button || !status) return;

  output.textContent = buildCompareSnapshot();
  button.disabled = compareKeys.length < 2;
  status.textContent = compareKeys.length < 2
    ? 'Select at least 2 strategies to enable snapshot copy.'
    : 'Snapshot includes selected strategies only and can be copied manually from the visible text block.';
}

async function copyCompareSnapshot() {
  const output = byId('d5-compare-snapshot-output');
  const status = byId('d5-compare-snapshot-status');
  if (!output || !status || compareKeys.length < 2) return;

  const selectAndCopy = () => {
    const selection = window.getSelection?.();
    if (!selection || !document.createRange || !document.execCommand) return false;
    const range = document.createRange();
    range.selectNodeContents(output);
    selection.removeAllRanges();
    selection.addRange(range);
    const copied = document.execCommand('copy');
    selection.removeAllRanges();
    return copied;
  };

  if (!navigator.clipboard?.writeText) {
    status.textContent = selectAndCopy()
      ? 'Comparison snapshot copied.'
      : 'Clipboard API unavailable; use the visible snapshot text block.';
    return;
  }

  try {
    await navigator.clipboard.writeText(output.textContent || '');
    status.textContent = 'Comparison snapshot copied.';
  } catch (error) {
    status.textContent = selectAndCopy()
      ? 'Comparison snapshot copied.'
      : 'Clipboard copy failed; use the visible snapshot text block.';
  }
}

function renderCompareCard(summary) {
  return `
    <article class="d5-compare-card" data-selected-key="${escapeHtml(summary.key)}">
      <div class="d5-compare-card-header">
        <div>
          <span>${escapeHtml(summary.lottery)}</span>
          <h4>${escapeHtml(summary.strategyId)}</h4>
        </div>
        <button class="d5-compare-remove" type="button" data-remove-compare-key="${escapeHtml(summary.key)}" aria-label="Remove ${escapeHtml(summary.strategyId)} from compare">Remove</button>
      </div>
      <div class="d5-compare-card-grid">
        ${compareField('row count', summary.totalRows)}
        ${compareField('matrix rows', summary.matrixRows.length.toLocaleString())}
        ${compareField('distinct window segments', summary.windows.length.toLocaleString())}
        ${compareField('window segments', formatList(summary.windows, 'Not available'))}
        ${compareField('distinct top_k values', summary.topKValues.length.toLocaleString())}
        ${compareField('top_k values', formatList(summary.topKValues, 'Not available'))}
        ${compareField('sample_size_draws summary', summary.sampleDraws)}
        ${compareField('sample_size_rows summary', summary.sampleRows)}
        ${DETAIL_RATE_COLUMNS.map((key) => compareField(DETAIL_RATE_LABELS[key], summary.rates[key])).join('')}
        ${compareField('baseline_mode status', summary.baselineMode)}
        ${compareField('baseline_value status', summary.baselineValue)}
        ${compareField('delta status', summary.delta)}
        ${compareField('delta_pp status', summary.deltaPp)}
        ${DETAIL_STATUS_COLUMNS.map((key) => compareField(key, summary.statuses[key])).join('')}
        ${compareField('coverage readiness', summary.coverageReadiness)}
        ${compareField('coverage blocked_reason', summary.coverageBlockedReason)}
      </div>
    </article>
  `;
}

function renderComparePanel() {
  const count = byId('d5-compare-count');
  const status = byId('d5-compare-status');
  const grid = byId('d5-compare-grid');
  if (!count || !status || !grid) return;

  count.textContent = compareLabel();
  if (compareKeys.length < 2) {
    status.textContent = 'Select at least 2 strategies to compare.';
  } else if (compareKeys.length >= COMPARE_LIMIT) {
    status.textContent = 'Compare selection is full at 4 strategies.';
  } else {
    status.textContent = 'Selected strategies are shown side-by-side for retrospective review only.';
  }

  if (!compareKeys.length) {
    grid.innerHTML = '<p class="d5-compare-empty">No strategies selected yet.</p>';
  } else {
    grid.innerHTML = compareKeys.map((key) => {
      const [lottery, strategyId] = parseDetailKey(key);
      return renderCompareCard(selectedStrategySummary(lottery, strategyId));
    }).join('');
  }

  renderCompareSnapshot();
  updateCompareRowButtons();
  updateDetailCompareButton();
  updateReviewLinkOutput();
}

function addCompareStrategy(key) {
  if (!key || compareKeys.includes(key)) {
    renderComparePanel();
    return;
  }
  if (compareKeys.length >= COMPARE_LIMIT) {
    renderComparePanel();
    return;
  }
  compareKeys = [...compareKeys, key];
  renderComparePanel();
}

function removeCompareStrategy(key) {
  compareKeys = compareKeys.filter((selectedKey) => selectedKey !== key);
  renderComparePanel();
}

function activeTabName() {
  return document.querySelector('.d5-tab.active')?.dataset.d5Tab || 'matrix';
}

function normalizeReviewTab(tab) {
  return VALID_TABS.has(tab) ? tab : 'matrix';
}

function normalizeReviewSearch(value) {
  return String(value || '').trim().slice(0, 80);
}

function isKnownStrategyKey(key) {
  const [lottery, strategyId] = parseDetailKey(key);
  if (!lottery || !strategyId) return false;
  return Boolean(findCoverageRow(lottery, strategyId) || findMatrixRows(lottery, strategyId).length);
}

function sanitizeCompareKeys(keys) {
  const seen = new Set();
  const safeKeys = [];
  keys.forEach((key) => {
    const value = String(key || '');
    if (!value || seen.has(value) || !isKnownStrategyKey(value)) return;
    seen.add(value);
    safeKeys.push(value);
  });
  return safeKeys.slice(0, COMPARE_LIMIT);
}

function currentDemoState() {
  return {
    tab: activeTabName(),
    matrixLottery: byId('d5-matrix-lottery-filter')?.value || '',
    matrixWindow: byId('d5-matrix-window-filter')?.value || '',
    matrixTopK: byId('d5-matrix-topk-filter')?.value || '',
    matrixSearch: byId('d5-matrix-strategy-search')?.value || '',
    coverageLottery: byId('d5-coverage-lottery-filter')?.value || '',
    coverageSearch: byId('d5-coverage-strategy-search')?.value || '',
    compareKeys: [...compareKeys],
  };
}

function encodeDemoStateHash(demoState = currentDemoState()) {
  const params = new URLSearchParams();
  params.set('v', REVIEW_STATE_VERSION);
  params.set('tab', normalizeReviewTab(demoState.tab || 'matrix'));
  [
    ['ml', demoState.matrixLottery],
    ['mw', demoState.matrixWindow],
    ['mt', demoState.matrixTopK],
    ['ms', normalizeReviewSearch(demoState.matrixSearch)],
    ['cl', demoState.coverageLottery],
    ['cs', normalizeReviewSearch(demoState.coverageSearch)],
  ].forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  sanitizeCompareKeys(demoState.compareKeys || []).forEach((key) => params.append('cmp', key));
  return `#${REVIEW_STATE_HASH_PREFIX}?${params.toString()}`;
}

function parseDemoStateFromHash(hash = window.location.hash) {
  const rawHash = String(hash || '').replace(/^#/, '');
  if (!rawHash.startsWith(`${REVIEW_STATE_HASH_PREFIX}?`)) return null;

  const params = new URLSearchParams(rawHash.slice(`${REVIEW_STATE_HASH_PREFIX}?`.length));
  return {
    tab: normalizeReviewTab(params.get('tab') || 'matrix'),
    matrixLottery: params.get('ml') || '',
    matrixWindow: params.get('mw') || '',
    matrixTopK: params.get('mt') || '',
    matrixSearch: normalizeReviewSearch(params.get('ms') || ''),
    coverageLottery: params.get('cl') || '',
    coverageSearch: normalizeReviewSearch(params.get('cs') || ''),
    compareKeys: sanitizeCompareKeys(params.getAll('cmp')),
  };
}

function applyDemoState(demoState, statusText = 'Demo state restored from review link.') {
  if (!demoState) return false;

  setSelectValue('d5-matrix-lottery-filter', demoState.matrixLottery);
  setSelectValue('d5-matrix-window-filter', demoState.matrixWindow);
  setSelectValue('d5-matrix-topk-filter', demoState.matrixTopK);
  setControlValue('d5-matrix-strategy-search', normalizeReviewSearch(demoState.matrixSearch));
  setSelectValue('d5-coverage-lottery-filter', demoState.coverageLottery);
  setControlValue('d5-coverage-strategy-search', normalizeReviewSearch(demoState.coverageSearch));
  compareKeys = sanitizeCompareKeys(demoState.compareKeys || []);
  activateTab(normalizeReviewTab(demoState.tab));
  renderMatrix();
  renderCoverage();
  renderComparePanel();
  setText('d5-preset-status', statusText);
  return true;
}

function showD5SectionForReviewLink() {
  document.querySelectorAll('.nav-btn').forEach((button) => {
    button.classList.toggle('active', button.dataset.section === 'lottery-d5');
  });
  document.querySelectorAll('.section').forEach((section) => {
    section.classList.toggle('active', section.id === 'lottery-d5-section');
  });
}

function restoreDemoStateFromUrl() {
  const demoState = parseDemoStateFromHash(window.location.hash);
  if (!demoState) return false;
  showD5SectionForReviewLink();
  return applyDemoState(demoState);
}

function buildDemoStateLink() {
  const url = new URL(window.location.href);
  url.hash = encodeDemoStateHash();
  return url.toString();
}

function updateReviewLinkOutput() {
  const output = byId('d5-review-link-output');
  if (!output) return;
  output.value = buildDemoStateLink();
}

async function copyReviewLink() {
  const output = byId('d5-review-link-output');
  const status = byId('d5-review-link-status');
  if (!output || !status) return;

  updateReviewLinkOutput();
  output.focus();
  output.select();

  const link = output.value;
  const fallbackMessage = 'Clipboard API unavailable; copy the visible demo state link text.';

  if (!navigator.clipboard?.writeText) {
    status.textContent = fallbackMessage;
    return;
  }

  try {
    await navigator.clipboard.writeText(link);
    status.textContent = 'Review link copied.';
  } catch (error) {
    status.textContent = 'Clipboard copy failed; copy the visible demo state link text.';
  }
}

function renderSummary() {
  const matrixRows = state.matrixRows.length;
  const bigRows = state.matrixRows.filter((row) => row.lottery === 'BIG_LOTTO').length;
  const dailyRows = state.matrixRows.filter((row) => row.lottery === 'DAILY_539').length;
  const strategies = new Set(state.coverageRows.map((row) => `${row.lottery}:${row.strategy_id}`)).size;
  const baselineComputed = state.matrixRows.some((row) => row.baseline_mode && row.baseline_mode !== 'not_computed');

  setText('d5-summary-matrix-rows', matrixRows.toLocaleString());
  setText('d5-summary-big-rows', bigRows.toLocaleString());
  setText('d5-summary-daily-rows', dailyRows.toLocaleString());
  setText('d5-summary-strategies', strategies.toLocaleString());
  setText('d5-summary-baseline', baselineComputed ? 'computed' : 'not computed');
  setText('d5-summary-powerlotto', 'excluded / blocked');

  if (state.manifest) {
    const provenance = byId('d5-provenance');
    if (provenance) {
      provenance.innerHTML = [
        state.manifest.final_classification,
        state.manifest.created_at_taipei,
        state.manifest.scope?.included_lotteries?.join(' + '),
      ].filter(Boolean).map((item) => `<span>${escapeHtml(item)}</span>`).join('');
    }
  }
}

function combinationSizeLabel(value) {
  return ({ '1': 'single', '2': 'pair', '3': 'triple' })[String(value)] || String(value);
}

function formatCombinationRate(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(2)}%` : escapeHtml(value);
}

function compareCombinationRows(left, right) {
  return Number(right.hit_at_least_3_rate) - Number(left.hit_at_least_3_rate)
    || Number(right.hit_at_least_2_rate) - Number(left.hit_at_least_2_rate)
    || Number(left.mean_number_overlap_fraction) - Number(right.mean_number_overlap_fraction)
    || String(left.strategy_ids).localeCompare(String(right.strategy_ids));
}

function singleCombinationRows(lotteryFilter, windowFilter) {
  const lotteries = lotteryFilter ? [lotteryFilter] : ['BIG_LOTTO', 'DAILY_539'];
  return lotteries.flatMap((lottery) => state.combinationMetricRows
    .filter((row) => row.lottery_type === lottery
      && row.window === windowFilter
      && row.combination_size === '1')
    .sort(compareCombinationRows)
    .slice(0, 5));
}

function selectedCombinationRows(lotteryFilter, windowFilter, sizeFilter) {
  if (sizeFilter === '1') return singleCombinationRows(lotteryFilter, windowFilter);
  return state.combinationCandidateRows.filter((row) => {
    if (lotteryFilter && row.lottery_type !== lotteryFilter) return false;
    return row.window === windowFilter && row.combination_size === sizeFilter;
  });
}

function renderCombinationResults() {
  const body = byId('d5-combination-body');
  if (!body) return;

  const lotteryFilter = byId('d5-combination-lottery-filter')?.value || '';
  const windowFilter = byId('d5-combination-window-filter')?.value || 'recent_750';
  const sizeFilter = byId('d5-combination-size-filter')?.value || '3';
  const rows = selectedCombinationRows(lotteryFilter, windowFilter, sizeFilter);
  const windowRows = state.combinationSummaryRows.filter((row) => {
    if (lotteryFilter && row.lottery_type !== lotteryFilter) return false;
    return row.window === windowFilter;
  });

  setText('d5-combination-row-count', `${rows.length} descriptive rows`);
  setText('d5-combination-window-summary', windowRows.map((row) => (
    `${row.lottery_type}: ${Number(row.common_draw_count_available).toLocaleString()} available draws; displayed sample denominator ${windowFilter.replace('recent_', '')}`
  )).join(' | '));

  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="10">No P320A descriptive rows match these selectors.</td></tr>';
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr>
      <td data-label="lottery">${escapeHtml(row.lottery_type)}</td>
      <td data-label="combination size">${escapeHtml(combinationSizeLabel(row.combination_size))}</td>
      <td data-label="strategy IDs"><code>${escapeHtml(row.strategy_ids).split('|').join('<br>')}</code></td>
      <td data-label="window">${escapeHtml(row.window)}</td>
      <td data-label="sample draws">${Number(row.sample_size_draws).toLocaleString()}</td>
      <td data-label="sample rows">${Number(row.sample_size_rows).toLocaleString()}</td>
      <td data-label="hit >= 1">${formatCombinationRate(row.hit_at_least_1_rate)}</td>
      <td data-label="hit >= 2">${formatCombinationRate(row.hit_at_least_2_rate)}</td>
      <td data-label="hit >= 3">${formatCombinationRate(row.hit_at_least_3_rate)}</td>
      <td data-label="status"><span class="d5-status-chip">${escapeHtml(row.inferential_status)}</span><br><small>baseline_mode=${escapeHtml(row.baseline_mode)}</small></td>
    </tr>
  `).join('');
}

function formatSignedRate(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return escapeHtml(value);
  // 4 dp preserves the source-reported delta precision (e.g. +0.0075 must not floor to +0.007).
  const sign = parsed > 0 ? '+' : (parsed < 0 ? '-' : '');
  return `${sign}${Math.abs(parsed).toFixed(4)}`;
}

function formatPercent1(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(1)}%` : escapeHtml(value);
}

const BASELINE_FACT_IDS = [
  'd5-baseline-budget',
  'd5-baseline-mean-delta',
  'd5-baseline-same-budget',
  'd5-baseline-biglotto',
  'd5-baseline-carrier',
];

function renderBaselineBudgetBias() {
  const setFact = (id, html) => {
    const node = byId(id);
    if (node) node.innerHTML = html;
  };
  const summary = state.baselineSummary;
  if (!summary) {
    BASELINE_FACT_IDS.forEach((id) => setFact(id, 'Not available'));
    return;
  }

  const delta = summary.mean_matched_budget_delta || {};
  const sameBudget = summary.same_budget_example || {};
  const screen = summary.inferential_screen || {};
  const bigLotto = summary.big_lotto_summary || {};
  const totalRows = Number(summary.n_metric_rows).toLocaleString();

  setFact('d5-baseline-budget', escapeHtml(summary.budget_definition));

  setFact('d5-baseline-mean-delta',
    `hit&ge;1 <strong>${formatSignedRate(delta.hit_at_least_1)}</strong> &middot; `
    + `hit&ge;2 <strong>${formatSignedRate(delta.hit_at_least_2)}</strong> &middot; `
    + `hit&ge;3 <strong>${formatSignedRate(delta.hit_at_least_3)}</strong> `
    + `<small>mean over ${totalRows} rows &asymp; 0 &mdash; the raw climb is bought with extra tickets, not structure.</small>`);

  setFact('d5-baseline-same-budget',
    `${escapeHtml(sameBudget.lottery)} ${escapeHtml(sameBudget.window)}, budget m=${escapeHtml(String(sameBudget.budget_m))}: `
    + `single hit&ge;2 <strong>${formatPercent1(sameBudget.single_rate)}</strong> vs triple <strong>${formatPercent1(sameBudget.triple_rate)}</strong>. `
    + `${escapeHtml(sameBudget.conclusion)}`);

  setFact('d5-baseline-biglotto',
    `${escapeHtml(bigLotto.label)} `
    + `<small>${Number(bigLotto.rows_passing_screen).toLocaleString()} rows pass the equal-budget screen.</small>`);

  setFact('d5-baseline-carrier',
    `${Number(screen.signal_carrier_rows).toLocaleString()} / ${Number(screen.signal_carrier_of_passing).toLocaleString()} `
    + `equal-budget-screen survivors carry <code>${escapeHtml(screen.signal_carrier_strategy)}</code> `
    + `(observed single-strategy signal carrier). All ${Number(screen.rows_passing).toLocaleString()} survivors are DAILY_539 at k=2; `
    + `${Number(screen.non_carrier_passing).toLocaleString()} are non-carrier. `
    + `<small>Inherited single-strategy signal, not combination synergy.</small>`);
}

function populateWindowFilter() {
  const select = byId('d5-matrix-window-filter');
  renderOptions(select, uniqueValues(state.matrixRows, 'window_segment'), 'All windows');
}

function populateTopKFilter() {
  const select = byId('d5-matrix-topk-filter');
  renderOptions(select, sortMaybeNumeric(uniqueValues(state.matrixRows, 'top_k')), 'All top_k');
}

function renderMatrix() {
  const body = byId('d5-matrix-body');
  if (!body) return;

  const lotteryFilter = byId('d5-matrix-lottery-filter')?.value || '';
  const windowFilter = byId('d5-matrix-window-filter')?.value || '';
  const topKFilter = byId('d5-matrix-topk-filter')?.value || '';
  const strategySearch = byId('d5-matrix-strategy-search')?.value || '';
  const rows = state.matrixRows.filter((row) => {
    if (lotteryFilter && row.lottery !== lotteryFilter) return false;
    if (windowFilter && row.window_segment !== windowFilter) return false;
    if (topKFilter && row.top_k !== topKFilter) return false;
    if (!strategyMatches(row, strategySearch)) return false;
    return true;
  });
  setText('d5-matrix-row-count', rowCountLabel(rows.length, state.matrixRows.length));

  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="${MATRIX_COLUMNS.length + 1}">No matrix rows match the current filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr class="d5-clickable-row" role="button" tabindex="0" data-detail-source="matrix" data-detail-key="${escapeHtml(detailKey(row.lottery, row.strategy_id))}" aria-label="Open strategy detail for ${escapeHtml(row.strategy_id)} ${escapeHtml(row.lottery)}">
      <td data-label="compare"><button class="d5-compare-toggle" type="button" data-compare-key="${escapeHtml(detailKey(row.lottery, row.strategy_id))}" aria-pressed="false">Compare</button></td>
      ${MATRIX_COLUMNS.map((key) => `<td data-label="${escapeHtml(key)}">${displayValue(row, key)}</td>`).join('')}
    </tr>
  `).join('');
  updateCompareRowButtons();
}

function renderCoverage() {
  const body = byId('d5-coverage-body');
  if (!body) return;

  const lotteryFilter = byId('d5-coverage-lottery-filter')?.value || '';
  const strategySearch = byId('d5-coverage-strategy-search')?.value || '';
  const rows = state.coverageRows.filter((row) => {
    if (lotteryFilter && row.lottery !== lotteryFilter) return false;
    if (!strategyMatches(row, strategySearch)) return false;
    return true;
  });
  setText('d5-coverage-row-count', rowCountLabel(rows.length, state.coverageRows.length));

  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="${COVERAGE_COLUMNS.length + 1}">No coverage rows match the current filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr class="d5-clickable-row ${row.readiness === 'NOT_READY' ? 'd5-row-muted' : ''}" role="button" tabindex="0" data-detail-source="coverage" data-detail-key="${escapeHtml(detailKey(row.lottery, row.strategy_id))}" aria-label="Open strategy detail for ${escapeHtml(row.strategy_id)} ${escapeHtml(row.lottery)}">
      <td data-label="compare"><button class="d5-compare-toggle" type="button" data-compare-key="${escapeHtml(detailKey(row.lottery, row.strategy_id))}" aria-pressed="false">Compare</button></td>
      ${COVERAGE_COLUMNS.map((key) => `<td data-label="${escapeHtml(key)}">${displayValue(row, key)}</td>`).join('')}
    </tr>
  `).join('');
  updateCompareRowButtons();
}

function renderContract() {
  const gates = byId('d5-readiness-gates');
  const required = byId('d5-required-fields');
  const code = byId('d5-contract-json');
  const contract = state.contract || {};

  if (gates) {
    const readinessGates = contract.readiness_gates || [];
    gates.innerHTML = readinessGates.map((gate) => `<li>${escapeHtml(gate)}</li>`).join('');
  }

  if (required) {
    required.innerHTML = (contract.required || [])
      .map((field) => `<span class="d5-chip">${escapeHtml(field)}</span>`)
      .join('');
  }

  if (code) {
    code.textContent = JSON.stringify(contract, null, 2);
  }
}

function renderPowerlottoNote() {
  const target = byId('d5-powerlotto-note');
  if (!target) return;
  target.innerHTML = markdownLite(state.powerlottoNote);
}

function activateTab(tab) {
  document.querySelectorAll('.d5-tab').forEach((node) => {
    const active = node.dataset.d5Tab === tab;
    node.classList.toggle('active', active);
    node.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  document.querySelectorAll('.d5-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.dataset.d5Panel === tab);
  });
}

function clearMatrixSecondaryFilters() {
  setControlValue('d5-matrix-window-filter', '');
  setControlValue('d5-matrix-topk-filter', '');
}

function applyReviewPreset(presetName) {
  const preset = REVIEW_PRESETS[presetName];
  if (!preset) return;

  clearMatrixSecondaryFilters();
  setControlValue('d5-matrix-lottery-filter', preset.matrixLottery);
  setControlValue('d5-matrix-strategy-search', preset.matrixSearch);
  setControlValue('d5-coverage-lottery-filter', preset.coverageLottery);
  setControlValue('d5-coverage-strategy-search', preset.coverageSearch);
  activateTab(preset.tab);
  renderMatrix();
  renderCoverage();
  setText('d5-preset-status', preset.status);
  updateReviewLinkOutput();
}

function markdownLite(markdown) {
  const html = [];
  let inList = false;

  markdown.split(/\r?\n/).forEach((line) => {
    if (line.startsWith('- ')) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${formatInline(line.slice(2))}</li>`);
      return;
    }

    if (inList) {
      html.push('</ul>');
      inList = false;
    }

    if (line.startsWith('# ')) {
      html.push(`<h3>${formatInline(line.slice(2))}</h3>`);
    } else if (line.startsWith('## ')) {
      html.push(`<h4>${formatInline(line.slice(3))}</h4>`);
    } else if (line.trim()) {
      html.push(`<p>${formatInline(line)}</p>`);
    }
  });

  if (inList) html.push('</ul>');
  return html.join('');
}

function formatInline(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function wireTabs() {
  document.querySelectorAll('.d5-tab').forEach((button) => {
    button.addEventListener('click', () => {
      activateTab(button.dataset.d5Tab);
      updateReviewLinkOutput();
    });
  });
}

function wireFilters() {
  const renderMatrixAndLink = () => {
    renderMatrix();
    updateReviewLinkOutput();
  };
  const renderCoverageAndLink = () => {
    renderCoverage();
    updateReviewLinkOutput();
  };
  byId('d5-matrix-lottery-filter')?.addEventListener('change', renderMatrixAndLink);
  byId('d5-matrix-window-filter')?.addEventListener('change', renderMatrixAndLink);
  byId('d5-matrix-topk-filter')?.addEventListener('change', renderMatrixAndLink);
  byId('d5-matrix-strategy-search')?.addEventListener('input', renderMatrixAndLink);
  byId('d5-coverage-lottery-filter')?.addEventListener('change', renderCoverageAndLink);
  byId('d5-coverage-strategy-search')?.addEventListener('input', renderCoverageAndLink);
  byId('d5-combination-lottery-filter')?.addEventListener('change', renderCombinationResults);
  byId('d5-combination-window-filter')?.addEventListener('change', renderCombinationResults);
  byId('d5-combination-size-filter')?.addEventListener('change', renderCombinationResults);
}

function wireReviewPresets() {
  byId('lottery-d5-section')?.addEventListener('click', (event) => {
    const button = event.target.closest?.('[data-d5-preset]');
    if (!button) return;
    applyReviewPreset(button.dataset.d5Preset || '');
  });
}

function openDetailFromEvent(event) {
  if (event.target.closest?.('[data-compare-key]')) return;
  const row = event.target.closest?.('.d5-clickable-row');
  if (!row) return;
  const [lottery, strategyId] = parseDetailKey(row.dataset.detailKey);
  if (!lottery || !strategyId) return;
  renderStrategyDetail(lottery, strategyId, row.dataset.detailSource || 'row');
}

function openDetailFromKeyboard(event) {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const row = event.target.closest?.('.d5-clickable-row');
  if (!row) return;
  event.preventDefault();
  openDetailFromEvent(event);
}

function wireDetailDrawer() {
  byId('d5-matrix-body')?.addEventListener('click', openDetailFromEvent);
  byId('d5-matrix-body')?.addEventListener('keydown', openDetailFromKeyboard);
  byId('d5-coverage-body')?.addEventListener('click', openDetailFromEvent);
  byId('d5-coverage-body')?.addEventListener('keydown', openDetailFromKeyboard);
  byId('d5-detail-close')?.addEventListener('click', closeStrategyDetail);
  byId('d5-detail-add-compare')?.addEventListener('click', (event) => {
    const key = event.currentTarget.dataset.detailKey || activeDetailKey;
    addCompareStrategy(key);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeStrategyDetail();
  });
}

function wireComparePanel() {
  const section = byId('lottery-d5-section');
  section?.addEventListener('click', (event) => {
    const snapshotButton = event.target.closest?.('#d5-compare-snapshot-copy');
    if (snapshotButton) {
      event.stopPropagation();
      copyCompareSnapshot();
      return;
    }

    const compareButton = event.target.closest?.('[data-compare-key]');
    if (compareButton) {
      event.stopPropagation();
      addCompareStrategy(compareButton.dataset.compareKey || '');
      return;
    }

    const removeButton = event.target.closest?.('[data-remove-compare-key]');
    if (removeButton) {
      event.stopPropagation();
      removeCompareStrategy(removeButton.dataset.removeCompareKey || '');
    }
  });
}

function wireReviewLink() {
  byId('d5-copy-review-link')?.addEventListener('click', copyReviewLink);
  window.addEventListener('hashchange', () => {
    if (restoreDemoStateFromUrl()) {
      updateReviewLinkOutput();
    }
  });
}

async function loadD5Artifacts() {
  const section = byId('lottery-d5-section');
  if (!section) return;
  const root = section.dataset.artifactRoot || 'public/demo-data/lottery-d5/p299a';
  const combinationRoot = section.dataset.combinationArtifactRoot || 'public/demo-data/lottery-d5/p320a';
  const baselineRoot = section.dataset.baselineArtifactRoot || 'public/demo-data/lottery-d5/p325a';

  try {
    const [
      manifestText,
      matrixText,
      coverageText,
      contractText,
      powerlottoText,
      combinationManifestText,
      combinationMetricsText,
      combinationCandidatesText,
      combinationSummaryText,
      baselineSummaryText,
    ] = await Promise.all([
      fetchText(root, DATA_FILES.manifest),
      fetchText(root, DATA_FILES.matrix),
      fetchText(root, DATA_FILES.coverage),
      fetchText(root, DATA_FILES.contract),
      fetchText(root, DATA_FILES.powerlotto),
      fetchText(combinationRoot, COMBINATION_DATA_FILES.manifest),
      fetchText(combinationRoot, COMBINATION_DATA_FILES.metrics),
      fetchText(combinationRoot, COMBINATION_DATA_FILES.candidates),
      fetchText(combinationRoot, COMBINATION_DATA_FILES.summary),
      fetchText(baselineRoot, BASELINE_DATA_FILE),
    ]);

    state = {
      manifest: JSON.parse(manifestText),
      matrixRows: csvToObjects(matrixText),
      coverageRows: csvToObjects(coverageText),
      contract: JSON.parse(contractText),
      powerlottoNote: powerlottoText,
      combinationManifest: JSON.parse(combinationManifestText),
      combinationMetricRows: csvToObjects(combinationMetricsText),
      combinationCandidateRows: csvToObjects(combinationCandidatesText),
      combinationSummaryRows: csvToObjects(combinationSummaryText),
      baselineSummary: JSON.parse(baselineSummaryText),
    };

    setError('');
    renderSummary();
    populateWindowFilter();
    populateTopKFilter();
    renderMatrix();
    renderCoverage();
    renderContract();
    renderPowerlottoNote();
    renderCombinationResults();
    renderBaselineBudgetBias();
    renderComparePanel();
    if (!restoreDemoStateFromUrl()) {
      updateReviewLinkOutput();
    }
  } catch (error) {
    setError(`Failed to load verified D5 artifacts: ${error.message}`);
  }
}

function initLotteryD5() {
  if (!byId('lottery-d5-section')) return;
  wireTabs();
  wireFilters();
  wireReviewPresets();
  wireDetailDrawer();
  wireComparePanel();
  wireReviewLink();
  loadD5Artifacts();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLotteryD5);
} else {
  initLotteryD5();
}
