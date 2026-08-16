const accountSelect = document.getElementById('accountSelect');
const statusEl = document.getElementById('status');
const reuseBtn = document.getElementById('reuseBtn');
const loginForm = document.getElementById('loginForm');

function setStatus(message, type = '') {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`.trim();
}

async function loadSessions() {
  try {
    const response = await fetch('/auth/sessions');
    if (!response.ok) {
      throw new Error('Unable to load saved sessions.');
    }

    const payload = await response.json();
    const sessions = payload.sessions || [];

    const options = ['<option value="">Open a new account</option>'];
    sessions.forEach((session) => {
      options.push(`<option value="${session.account_name}">${session.account_name}</option>`);
    });
    accountSelect.innerHTML = options.join('');
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

async function selectSession() {
  const accountName = accountSelect.value;
  if (!accountName) {
    setStatus('Choose a saved account to reuse.', 'error');
    return;
  }

  setStatus('Loading saved account…');

  try {
    const response = await fetch(`/auth/sessions/select?account_name=${encodeURIComponent(accountName)}`, {
      method: 'POST',
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || 'Unable to load selected account.');
    }

    window.location.href = '/';
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  setStatus('Opening Angel One login…');

  try {
    const response = await fetch('/auth/login', {
      method: 'POST',
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || 'Login failed.');
    }

    const data = await response.json();
    setStatus(`Loaded: ${data.account_name || 'Angel One account'}`, 'success');
    window.location.href = '/';
  } catch (error) {
    setStatus(error.message, 'error');
  }
});

reuseBtn.addEventListener('click', selectSession);

loadSessions();
