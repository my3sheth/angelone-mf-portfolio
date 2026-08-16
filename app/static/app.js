const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
});

const state = {
  dashboard: null,
  table: null,
  accountName: '',
  accounts: [],
};

function formatCurrency(value) {
  const numericValue = Number(value ?? 0);
  return currencyFormatter.format(numericValue);
}

function formatPercent(value) {
  const numericValue = Number(value ?? 0);
  return `${numericValue.toFixed(2)}%`;
}

function renderCardGrid() {
  const grid = document.getElementById('cardGrid');
  if (!state.dashboard?.cards?.length) {
    grid.innerHTML = '<div class="empty-state">No portfolio data available yet.</div>';
    return;
  }

  grid.innerHTML = state.dashboard.cards.map((card) => {
    const isPercent = card.unit === '%';
    const value = isPercent ? formatPercent(card.value) : formatCurrency(card.value);
    return `
      <article class="card">
        <div class="label">${card.label}</div>
        <div class="value">${value}</div>
        <div class="meta">${card.unit}</div>
      </article>
    `;
  }).join('');
}

function renderSummary() {
  const summary = state.dashboard?.summary || {};
  const holdingsCount = document.getElementById('holdingsCount');
  const gainValue = document.getElementById('gainValue');

  holdingsCount.textContent = summary.holdings_count ?? '--';
  const gain = Number(summary.total_gain ?? 0);
  const gainText = `${gain >= 0 ? '+' : '-'} ${formatCurrency(Math.abs(gain))}`;
  gainValue.textContent = `${gainText} total gain`;
}

function renderTable() {
  const thead = document.getElementById('tableHead');
  const tbody = document.getElementById('tableBody');

  if (!state.table?.columns?.length || !state.table?.rows?.length) {
    thead.innerHTML = '';
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No holdings found.</td></tr>';
    return;
  }

  thead.innerHTML = `
    <tr>
      ${state.table.columns.map((column) => `<th>${column.label}</th>`).join('')}
    </tr>
  `;

  tbody.innerHTML = state.table.rows.map((row) => {
    return `
      <tr>
        ${state.table.columns.map((column) => {
          const value = row[column.key];
          let displayValue = value ?? '--';

          if (column.key === 'total_invested' || column.key === 'current_value' || column.key === 'monthly_sip' || column.key === 'current_nav' || column.key === 'current_units') {
            displayValue = Number(value ?? 0);
            if (column.key === 'current_nav' || column.key === 'current_units') {
              displayValue = numberFormatter.format(displayValue);
            } else {
              displayValue = formatCurrency(displayValue);
            }
          }

          if (column.key === 'ter') {
            displayValue = formatPercent(value ?? 0);
          }

          if (column.key === 'sip_date') {
            displayValue = value === null || value === undefined ? '—' : value;
          }

          return `<td>${displayValue}</td>`;
        }).join('')}
      </tr>
    `;
  }).join('');
}

async function loadAccounts() {
  try {
    const response = await fetch('/auth/sessions');
    if (!response.ok) {
      throw new Error('Could not load saved accounts.');
    }

    const payload = await response.json();
    const sessions = payload.sessions || [];
    const select = document.getElementById('accountFilter');
    state.accounts = sessions.map((session) => session.account_name || 'default');

    select.innerHTML = `
      <option value="__change_account__">Change account / add account</option>
      ${state.accounts.map((account) => `
        <option value="${account}">${account}</option>
      `).join('')}
    `;

    if (!state.accountName && state.accounts.length) {
      state.accountName = state.accounts[0];
    }

    select.value = state.accountName || '__change_account__';
  } catch (error) {
    console.error(error);
  }
}

async function fetchData() {
  const accountName = state.accountName || '';
  if (!accountName || accountName === '__change_account__') {
    return;
  }

  try {
    const urlParams = accountName ? `?account_name=${encodeURIComponent(accountName)}` : '';
    const [dashboardResponse, tableResponse] = await Promise.all([
      fetch(`/portfolio/dashboard${urlParams}`),
      fetch(`/portfolio/table${urlParams}`),
    ]);

    if (!dashboardResponse.ok || !tableResponse.ok) {
      throw new Error('Could not load portfolio data.');
    }

    state.dashboard = await dashboardResponse.json();
    state.table = await tableResponse.json();
    renderCardGrid();
    renderSummary();
    renderTable();
  } catch (error) {
    document.getElementById('cardGrid').innerHTML = `<div class="empty-state">${error.message}</div>`;
    document.getElementById('tableBody').innerHTML = '<tr><td colspan="9" class="empty-state">Unable to load holdings.</td></tr>';
  }
}

function bindActions() {
  document.getElementById('refreshBtn').addEventListener('click', fetchData);
  document.getElementById('excelBtn').addEventListener('click', () => {
    const accountName = state.accountName && state.accountName !== '__change_account__' ? `?account_name=${encodeURIComponent(state.accountName)}` : '';
    window.open(`/portfolio/export/excel${accountName}`, '_blank');
  });
  document.getElementById('pdfBtn').addEventListener('click', () => {
    const accountName = state.accountName && state.accountName !== '__change_account__' ? `?account_name=${encodeURIComponent(state.accountName)}` : '';
    window.open(`/portfolio/export/pdf${accountName}`, '_blank');
  });

  document.getElementById('accountFilter').addEventListener('change', (event) => {
    const nextValue = event.target.value;
    if (nextValue === '__change_account__') {
      window.location.href = '/login';
      return;
    }

    state.accountName = nextValue;
    fetchData();
  });
}

async function init() {
  await loadAccounts();
  bindActions();
  await fetchData();
}

init();
