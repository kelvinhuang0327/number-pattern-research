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

let state = {
  matrixRows: [],
  coverageRows: [],
  contract: null,
  powerlottoNote: '',
  manifest: null,
};

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

function findCoverageRow(lottery, strategyId) {
  return state.coverageRows.find((row) => row.lottery === lottery && row.strategy_id === strategyId) || null;
}

function findMatrixRows(lottery, strategyId) {
  return state.matrixRows.filter((row) => row.lottery === lottery && row.strategy_id === strategyId);
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
  if (!drawer || !body || !title || !subtitle) return;

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
  const totalRows = coverageRow ? displayValue(coverageRow, 'rows') : matrixRows.length.toLocaleString();
  const distinctDraws = coverageRow ? displayValue(coverageRow, 'distinct_draws') : summarizeNumbers(matrixRows, 'sample_size_draws');

  title.textContent = strategyId;
  subtitle.textContent = `${lottery} historical strategy metrics from ${source === 'coverage' ? 'coverage' : 'matrix'} artifact rows.`;
  body.innerHTML = `
    <div class="d5-detail-metrics" aria-label="Selected strategy summary">
      ${detailMetric('strategy_id', escapeHtml(strategyId))}
      ${detailMetric('lottery', escapeHtml(lottery))}
      ${detailMetric('Total rows available', totalRows)}
      ${detailMetric('Matrix rows', matrixRows.length.toLocaleString())}
      ${detailMetric('Distinct draws', distinctDraws || 'Not available')}
      ${detailMetric('Distinct window segments', windows.length.toLocaleString())}
      ${detailMetric('Distinct top_k values', topKValues.length.toLocaleString())}
    </div>

    <div class="d5-detail-grid">
      ${detailField('Window segments', formatList(windows, 'Not available'))}
      ${detailField('top_k values', formatList(topKValues, 'Not available'))}
      ${detailField('sample_size_draws summary', summarizeNumbers(matrixRows, 'sample_size_draws'))}
      ${detailField('sample_size_rows summary', summarizeNumbers(matrixRows, 'sample_size_rows'))}
      ${DETAIL_RATE_COLUMNS.map((key) => detailField(DETAIL_RATE_LABELS[key], summarizeRates(matrixRows, key))).join('')}
      ${detailField('baseline_mode status', formatList(baselineModes, 'Not available'))}
      ${detailField('baseline_value status', formatList(baselineValues, 'Not computed'))}
      ${detailField('delta status', formatList(deltaValues, 'Not computed'))}
      ${detailField('delta_pp status', formatList(deltaPpValues, 'Not computed'))}
      ${DETAIL_STATUS_COLUMNS.map((key) => detailField(key, formatList(uniqueDisplayValues(matrixRows, key), 'Not available'))).join('')}
      ${detailField('coverage readiness', coverageRow ? displayValue(coverageRow, 'readiness') : 'Not available')}
      ${detailField('coverage blocked_reason', coverageRow ? (displayValue(coverageRow, 'blocked_reason') || 'None') : 'Not available')}
    </div>

    <div class="d5-detail-section">
      <h4>Historical windows/top_k rows</h4>
      ${renderDetailWindowRows(matrixRows)}
    </div>
  `;
  drawer.hidden = false;
  drawer.classList.add('is-open');
}

function closeStrategyDetail() {
  const drawer = byId('d5-strategy-detail-drawer');
  if (!drawer) return;
  drawer.classList.remove('is-open');
  drawer.hidden = true;
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
    body.innerHTML = `<tr><td colspan="${MATRIX_COLUMNS.length}">No matrix rows match the current filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr class="d5-clickable-row" role="button" tabindex="0" data-detail-source="matrix" data-detail-key="${escapeHtml(detailKey(row.lottery, row.strategy_id))}" aria-label="Open strategy detail for ${escapeHtml(row.strategy_id)} ${escapeHtml(row.lottery)}">
      ${MATRIX_COLUMNS.map((key) => `<td data-label="${escapeHtml(key)}">${displayValue(row, key)}</td>`).join('')}
    </tr>
  `).join('');
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
    body.innerHTML = `<tr><td colspan="${COVERAGE_COLUMNS.length}">No coverage rows match the current filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr class="d5-clickable-row ${row.readiness === 'NOT_READY' ? 'd5-row-muted' : ''}" role="button" tabindex="0" data-detail-source="coverage" data-detail-key="${escapeHtml(detailKey(row.lottery, row.strategy_id))}" aria-label="Open strategy detail for ${escapeHtml(row.strategy_id)} ${escapeHtml(row.lottery)}">
      ${COVERAGE_COLUMNS.map((key) => `<td data-label="${escapeHtml(key)}">${displayValue(row, key)}</td>`).join('')}
    </tr>
  `).join('');
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
      const tab = button.dataset.d5Tab;
      document.querySelectorAll('.d5-tab').forEach((node) => {
        const active = node === button;
        node.classList.toggle('active', active);
        node.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      document.querySelectorAll('.d5-panel').forEach((panel) => {
        panel.classList.toggle('active', panel.dataset.d5Panel === tab);
      });
    });
  });
}

function wireFilters() {
  byId('d5-matrix-lottery-filter')?.addEventListener('change', renderMatrix);
  byId('d5-matrix-window-filter')?.addEventListener('change', renderMatrix);
  byId('d5-matrix-topk-filter')?.addEventListener('change', renderMatrix);
  byId('d5-matrix-strategy-search')?.addEventListener('input', renderMatrix);
  byId('d5-coverage-lottery-filter')?.addEventListener('change', renderCoverage);
  byId('d5-coverage-strategy-search')?.addEventListener('input', renderCoverage);
}

function openDetailFromEvent(event) {
  const row = event.target.closest?.('.d5-clickable-row');
  if (!row) return;
  const [lottery, strategyId] = String(row.dataset.detailKey || '').split('::');
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
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeStrategyDetail();
  });
}

async function loadD5Artifacts() {
  const section = byId('lottery-d5-section');
  if (!section) return;
  const root = section.dataset.artifactRoot || 'public/demo-data/lottery-d5/p299a';

  try {
    const [manifestText, matrixText, coverageText, contractText, powerlottoText] = await Promise.all([
      fetchText(root, DATA_FILES.manifest),
      fetchText(root, DATA_FILES.matrix),
      fetchText(root, DATA_FILES.coverage),
      fetchText(root, DATA_FILES.contract),
      fetchText(root, DATA_FILES.powerlotto),
    ]);

    state = {
      manifest: JSON.parse(manifestText),
      matrixRows: csvToObjects(matrixText),
      coverageRows: csvToObjects(coverageText),
      contract: JSON.parse(contractText),
      powerlottoNote: powerlottoText,
    };

    setError('');
    renderSummary();
    populateWindowFilter();
    populateTopKFilter();
    renderMatrix();
    renderCoverage();
    renderContract();
    renderPowerlottoNote();
  } catch (error) {
    setError(`Failed to load verified P299A artifacts: ${error.message}`);
  }
}

function initLotteryD5() {
  if (!byId('lottery-d5-section')) return;
  wireTabs();
  wireFilters();
  wireDetailDrawer();
  loadD5Artifacts();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLotteryD5);
} else {
  initLotteryD5();
}
