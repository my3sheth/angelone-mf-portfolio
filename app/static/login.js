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
      const badgeClass = isValid ? 'active' : 'expired';
      const badgeText = isValid ? 'Active' : 'Expired';
      const btnText = isValid ? 'Open Dashboard →' : 'Re-login 🔄';
      const btnClass = isValid ? 'primary btn-sm' : 'secondary btn-sm';

      return `
        <div class="account-card" data-account="${encodeURIComponent(name)}">
          <div class="account-info">
            <span class="account-name">👤 ${name}</span>
            <span class="account-meta">
              <span class="badge ${badgeClass}">${badgeText}</span>
              ${s.expires_at ? `Expires: ${new Date(s.expires_at).toLocaleDateString('en-IN')}` : ''}
            </span>
          </div>
          <div class="account-actions">
            <button class="${btnClass}" onclick="handleAccountAction('${encodeURIComponent(name)}', ${isValid})">
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
  if (isValid) {
    try {
      setStatus(`Switching to ${accountName}…`);
      const selectResp = await fetch('/auth/sessions/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `account_name=${encodeURIComponent(accountName)}`,
      });
      if (selectResp.ok) {
        window.location.href = `/?account_name=${encodeURIComponent(accountName)}`;
        return;
      }
    } catch {}
  }

  // If expired or select failed, trigger fresh login
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
      let message = errorText || 'Login failed.';
      try {
        const errorJson = JSON.parse(errorText);
        if (errorJson && errorJson.detail) {
          message = errorJson.detail;
        }
      } catch {}
      throw new Error(message);
    }

    const data = await response.json();
    const resolvedName = data.account_name || '';
    setStatus(`Loaded: ${resolvedName || 'Angel One account'}`, 'success');
    window.location.href = resolvedName ? `/?account_name=${encodeURIComponent(resolvedName)}` : '/';
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

loginForm.addEventListener('submit', (event) => {
  event.preventDefault();
  triggerLogin();
});

loadSavedAccounts();
