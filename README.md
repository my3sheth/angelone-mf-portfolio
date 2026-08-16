# AngelOne Mutual Funds Holdings

A local portfolio analytics and management dashboard for Angel One Mutual Funds.

## Features

- **Automated Authentication**: Secure browser-assisted login with automatic session & token extraction via Playwright.
- **Multi-Account Support**: Store and switch between multiple user accounts seamlessly.
- **Disconnected Architecture**: Caches portfolio snapshots locally (SQLite + JSON) for instant offline loading without API rate limits.
- **Portfolio Analytics**: Track total invested capital, current value, total gain / return %, monthly SIPs, and average TER.
- **Holdings Table**: View all fund schemes with current NAV, units, investment amounts, and category insights.
- **Report Exports**: Export clean, styled Excel spreadsheets (`.xlsx`) and printable PDF reports (`.pdf`).

---

## Getting Started

### 1. Prerequisites

- Python 3.11+
- Google Chrome installed

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/my3sheth/angelone-mf-portfolio.git
cd angelone-mf-portfolio

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install Playwright browser drivers
playwright install chromium
```

### 3. Running the Application

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser:
1. Click **Log in to Angel One** to complete your 2FA authentication in the automated browser window.
2. Once authenticated, your holdings will be automatically captured, analyzed, and displayed on your local dashboard.

---

## Architecture & Privacy

- **100% Local**: All authentication tokens, cookies, and portfolio data are stored locally on your machine in `angelone.sqlite3` and `portfolio_<user>.json`.
- **No Third-Party Telemetry**: Your credentials and financial data never leave your local environment.
- **Isolated Profiles**: Browser profiles and authentication sessions are kept isolated per account in `browser_profile/`.
