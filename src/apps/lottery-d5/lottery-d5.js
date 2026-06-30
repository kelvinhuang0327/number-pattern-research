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
  if (!select) return;
  const windows = [...new Set(state.matrixRows.map((row) => row.window_segment).filter(Boolean))];
  select.innerHTML = '<option value="">All windows</option>' +
    windows.map((windowSegment) => `<option value="${escapeHtml(windowSegment)}">${escapeHtml(windowSegment)}</option>`).join('');
}

function renderMatrix() {
  const body = byId('d5-matrix-body');
  if (!body) return;

  const lotteryFilter = byId('d5-matrix-lottery-filter')?.value || '';
  const windowFilter = byId('d5-matrix-window-filter')?.value || '';
  const rows = state.matrixRows.filter((row) => {
    if (lotteryFilter && row.lottery !== lotteryFilter) return false;
    if (windowFilter && row.window_segment !== windowFilter) return false;
    return true;
  });

  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="${MATRIX_COLUMNS.length}">No rows for current filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr>
      ${MATRIX_COLUMNS.map((key) => `<td data-label="${escapeHtml(key)}">${displayValue(row, key)}</td>`).join('')}
    </tr>
  `).join('');
}

function renderCoverage() {
  const body = byId('d5-coverage-body');
  if (!body) return;

  const lotteryFilter = byId('d5-coverage-lottery-filter')?.value || '';
  const rows = state.coverageRows.filter((row) => !lotteryFilter || row.lottery === lotteryFilter);

  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="${COVERAGE_COLUMNS.length}">No rows for current filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr class="${row.readiness === 'NOT_READY' ? 'd5-row-muted' : ''}">
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
  byId('d5-coverage-lottery-filter')?.addEventListener('change', renderCoverage);
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
  loadD5Artifacts();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLotteryD5);
} else {
  initLotteryD5();
}
