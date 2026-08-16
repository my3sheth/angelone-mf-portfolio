const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 4,
});

async function checkAuthStatus(accountName) {
  try {
    const response = await fetch(`/auth/status/${encodeURIComponent(accountName)}`);
    if (!response.ok) {
      throw new Error('Unable to check auth status.');
    }

    const payload = await response.json();
    return payload.auth || {};
  } catch (error) {
    console.error('Auth status check failed:', error);
    return { valid: false, status_code: 'unknown', message: 'Auth check failed' };
  }
}

async function validateAndSwitchAccount(accountName) {
  // Check if auth is valid for this account
  const authStatus = await checkAuthStatus(accountName);
  
  if (!authStatus.valid) {
    // Auth is expired or invalid, redirect to login
    console.warn(`Auth for '${accountName}' is ${authStatus.status_code}. Redirecting to login...`);
    alert(`Authentication for '${accountName}' is ${authStatus.status_code}.\n\nPlease log in again.`);
    window.location.href = '/login';
    return false;
  }
  
  return true;
}


const state = {
  dashboard: null,
  table: null,
  accountName: '',
};

function formatUserTime(dateStr) {
  if (!dateStr) return '';
  let str = String(dateStr).trim();
  // If no timezone offset is provided, treat as UTC
  if (!str.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(str)) {
    str += 'Z';
  }
  const date = new Date(str);
  if (isNaN(date.getTime())) return dateStr;

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

function updateUserInfo() {
  const userInfo = document.getElementById('userInfo');
  if (!state.accountName) {
    userInfo.style.display = 'none';
    return;
  }

  const fetchedAt = state.dashboard?.fetched_at;
  if (fetchedAt) {
    const formattedDate = formatUserTime(fetchedAt);
    userInfo.textContent = `📊 ${state.accountName} • Updated ${formattedDate}`;
    userInfo.style.display = 'block';
  } else {
    userInfo.textContent = `📊 ${state.accountName}`;
    userInfo.style.display = 'block';
  }
}

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
    const urlParams = new URLSearchParams(window.location.search);
    const paramAccount = (urlParams.get('account_name') || '').trim();

    const response = await fetch('/auth/sessions');
    if (!response.ok) {
      throw new Error('Could not load saved sessions.');
    }

    const payload = await response.json();
    const sessions = (payload.sessions || []).filter((session) => {
      const name = (session.account_name || '').trim();
      return name && !/^account_[0-9]+/i.test(name) && !/^[0-9a-f]{8,}$/i.test(name) && !name.includes(':');
    });

    if (paramAccount && sessions.some((s) => s.account_name === paramAccount)) {
      state.accountName = paramAccount;
    } else if (payload.active_account && sessions.some((s) => s.account_name === payload.active_account)) {
      state.accountName = payload.active_account;
    } else if (!state.accountName && sessions.length) {
      state.accountName = sessions[0].account_name;
    }

    const accountSelect = document.getElementById('accountSelect');
    if (sessions.length > 1) {
      accountSelect.style.display = 'inline-block';
      accountSelect.innerHTML = sessions.map((s) => {
        const name = s.account_name;
        const selected = name === state.accountName ? 'selected' : '';
        const statusLabel = s.is_valid ? '' : ' (Expired)';
        return `<option value="${name}" ${selected}>👤 ${name}${statusLabel}</option>`;
      }).join('');
      accountSelect.value = state.accountName;
    } else {
      accountSelect.style.display = 'none';
    }
  } catch (error) {
    console.error(error);
  }
}

async function checkAndDisplayAuthBanner() {
  const authBanner = document.getElementById('authBanner');
  if (!state.accountName) {
    authBanner.style.display = 'none';
    return;
  }

  const authStatus = await checkAuthStatus(state.accountName);
  if (!authStatus.valid) {
    authBanner.style.display = 'flex';
  } else {
    authBanner.style.display = 'none';
  }
}

async function fetchData() {
  const accountName = state.accountName || '';
  if (!accountName) {
    window.location.href = '/login';
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
    updateUserInfo();
    renderCardGrid();
    renderSummary();
    renderTable();
    checkAndDisplayAuthBanner();
  } catch (error) {
    console.error('Error fetching data:', error);
    document.getElementById('cardGrid').innerHTML = `<div class="empty-state">No portfolio data cached yet. <a href="/login" style="color:var(--accent-2);margin-left:8px;text-decoration:underline;">Click here to log in</a></div>`;
    document.getElementById('tableBody').innerHTML = '<tr><td colspan="9" class="empty-state">No portfolio found. <a href="/login" style="color:var(--accent-2);margin-left:8px;text-decoration:underline;">Please log in</a> to fetch holdings.</td></tr>';
  }
}

function bindActions() {
  const accountSelect = document.getElementById('accountSelect');
  if (accountSelect) {
    accountSelect.addEventListener('change', async (e) => {
      state.accountName = e.target.value;
      const newUrl = `${window.location.pathname}?account_name=${encodeURIComponent(state.accountName)}`;
      window.history.replaceState(null, '', newUrl);
      await fetchData();
    });
  }

  const excelBtn = document.getElementById('excelBtn');
  if (excelBtn) {
    excelBtn.addEventListener('click', () => {
      const accountName = state.accountName ? `?account_name=${encodeURIComponent(state.accountName)}` : '';
      window.open(`/portfolio/export/excel${accountName}`, '_blank');
    });
  }

  const pdfBtn = document.getElementById('pdfBtn');
  if (pdfBtn) {
    pdfBtn.addEventListener('click', () => {
      const accountName = state.accountName ? `?account_name=${encodeURIComponent(state.accountName)}` : '';
      window.open(`/portfolio/export/pdf${accountName}`, '_blank');
    });
  }
}

async function init() {
  await loadAccounts();
  bindActions();
  await fetchData();
}

init();
