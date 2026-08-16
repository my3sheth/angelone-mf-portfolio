const statusEl = document.getElementById('status');
const loginForm = document.getElementById('loginForm');
const sessionsSection = document.getElementById('sessionsSection');
const accountsList = document.getElementById('accountsList');

function setStatus(message, type = '') {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`.trim();
}

function isValidSessionName(name) {
  if (!name) return false;
  if (/^account_[0-9]+/i.test(name)) return false;
  if (/^profile_[0-9]+/i.test(name)) return false;
  if (/^[0-9a-f]{8,}$/i.test(name)) return false;
  if (name.includes(':')) return false; // IP addresses
  return true;
}

function extractErrorMessage(errJson, fallback = 'Operation failed.') {
  if (!errJson) return fallback;
  if (typeof errJson === 'string') return errJson;
  if (typeof errJson.detail === 'string') return errJson.detail;
  if (Array.isArray(errJson.detail)) {
    return errJson.detail
      .map((d) => (typeof d === 'string' ? d : d.msg || d.message || JSON.stringify(d)))
      .join(', ');
  }
  if (typeof errJson.message === 'string') return errJson.message;
  return fallback;
}

function isSessionExpired(status, errJson) {
  if (status === 401) return true;
  const msg = extractErrorMessage(errJson, '');
  const lower = msg.toLowerCase();
  return lower.includes('expired') || lower.includes('no authentication') || lower.includes('invalid credentials');
}

async function loadSavedAccounts() {
  try {
    const response = await fetch('/auth/sessions');
    if (!response.ok) return;

    const payload = await response.json();
    const sessions = (payload.sessions || []).filter((s) => isValidSessionName((s.account_name || '').trim()));

    if (!sessions.length) {
      sessionsSection.style.display = 'none';
      return;
    }

    sessionsSection.style.display = 'block';
    accountsList.innerHTML = sessions.map((s) => {
      const name = s.account_name;
      const isValid = s.is_valid;
      const btnText = isValid ? 'Open Dashboard →' : 'Login';
      const btnClass = isValid ? 'primary btn-sm' : 'secondary btn-sm';
      const statusBadge = isValid 
        ? '<span class="badge active">Active</span>' 
        : '<span class="badge expired">Expired</span>';

      return `
        <div class="account-card" data-account="${encodeURIComponent(name)}">
          <div class="account-info">
            <span class="account-name">${name}</span>
            <div class="account-meta">
              ${statusBadge}
            </div>
          </div>
          <div class="account-actions">
            <button class="${btnClass}" id="btn-${encodeURIComponent(name)}" onclick="handleAccountAction('${encodeURIComponent(name)}', ${isValid})">
              ${btnText}
            </button>
            <button class="btn-del" title="Remove account" onclick="deleteAccount('${encodeURIComponent(name)}')">
              🗑️
            </button>
          </div>
        </div>
      `;
    }).join('');
  } catch (error) {
    console.warn('Could not load saved accounts:', error);
  }
}

window.handleAccountAction = async function(encodedName, isValid) {
  const accountName = decodeURIComponent(encodedName);
  const actionBtn = document.getElementById(`btn-${encodedName}`);

  if (isValid) {
    try {
      setStatus(`Using active session for ${accountName} & fetching latest details…`);
      if (actionBtn) {
        actionBtn.disabled = true;
        actionBtn.textContent = 'Syncing…';
      }

      const selectResp = await fetch(`/auth/sessions/select?account_name=${encodeURIComponent(accountName)}&refresh=true`, {
        method: 'POST',
      });

      if (selectResp.ok) {
        setStatus(`Live data refreshed! Opening dashboard…`, 'success');
        window.location.href = `/dashboard?account_name=${encodeURIComponent(accountName)}`;
        return;
      } else {
        const errJson = await selectResp.json().catch(() => ({}));
        if (isSessionExpired(selectResp.status, errJson)) {
          setStatus(`Session expired for ${accountName}. Please log in again.`, 'error');
          await loadSavedAccounts();
          return;
        }
        const errMsg = extractErrorMessage(errJson, 'Could not fetch portfolio with saved session.');
        throw new Error(errMsg);
      }
    } catch (err) {
      console.warn('Session live fetch notice:', err);
      setStatus(err.message || 'Session error. Opening login…', 'error');
      if (actionBtn) {
        actionBtn.disabled = false;
        actionBtn.textContent = 'Open Dashboard →';
      }
      return;
    }
  }

  // If expired or invalid, trigger fresh browser login
  triggerLogin(accountName);
};

window.deleteAccount = async function(encodedName) {
  const accountName = decodeURIComponent(encodedName);
  if (!confirm(`Remove account '${accountName}' from saved sessions?`)) return;
  try {
    const resp = await fetch(`/auth/sessions/${encodeURIComponent(accountName)}`, { method: 'DELETE' });
    if (resp.ok) {
      loadSavedAccounts();
    }
  } catch (err) {
    console.error('Delete failed:', err);
  }
};

async function triggerLogin(accountName = null) {
  setStatus('Opening Angel One login browser…');
  try {
    const url = accountName ? `/auth/login?account_name=${encodeURIComponent(accountName)}` : '/auth/login';
    const response = await fetch(url, { method: 'POST' });

    if (!response.ok) {
      const errorText = await response.text();
      let message = 'Login failed.';
      try {
        const errorJson = JSON.parse(errorText);
        message = extractErrorMessage(errorJson, errorText || message);
      } catch {
        message = errorText || message;
      }
      throw new Error(message);
    }

    const data = await response.json();
    const resolvedName = data.account_name || '';
    setStatus(`Loaded: ${resolvedName || 'Angel One account'}`, 'success');
    window.location.href = resolvedName ? `/dashboard?account_name=${encodeURIComponent(resolvedName)}` : '/dashboard';
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

loginForm.addEventListener('submit', (event) => {
  event.preventDefault();
  triggerLogin();
});

loadSavedAccounts();
