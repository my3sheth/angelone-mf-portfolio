import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from angelone.api.client import AngelOneAPIClient
from angelone.api.holdings import HoldingsAPI
from angelone.api.scheme import SchemeAPI
from angelone.api.sip import SIPAPI
from angelone.auth.playwright import AngelOneAuthenticator
from angelone.auth_store import is_auth_valid, get_auth_status
from angelone.models.portfolio import (
    MutualFundHolding,
    PortfolioResponse,
)
from angelone.session_store import (
    get_account_session,
    get_active_account_name,
    list_account_sessions,
    set_active_account_name,
)


ROOT = Path(__file__).resolve().parents[3]

CACHE_FILE = ROOT / "portfolio.json"


def _is_generated_account_name(value):
    value = (value or "").strip()
    if not value:
        return True
    lower = value.lower()
    if lower in {"default", "user", "placeholder", "undefined", "null", "none", "temp", "temporary", "new-account"}:
        return True
    if ":" in value:  # IPv6 address or port
        return True
    if bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", value)):  # IPv4 address
        return True
    if lower.startswith("account_") or lower.startswith("profile_"):
        prefix_len = len("account_") if lower.startswith("account_") else len("profile_")
        suffix = value[prefix_len:]
        return bool(suffix) and (
            suffix.isdigit()
            or bool(re.fullmatch(r"\d{8,}.*", suffix))
            or bool(re.fullmatch(r"\d{4,}[-_\d]*", suffix))
            or suffix.lower() in {"default", "temp", "new", "placeholder"}
        )
    if bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:-[A-Za-z0-9]+)?", value)):
        return True
    if len(value) >= 12 and not (" " in value) and all(c in "0123456789abcdefABCDEF" for c in value):
        return True
    if len(value) >= 30 and bool(re.fullmatch(r"[A-Za-z0-9_-]+", value)) and not (" " in value):
        return True
    return False


def _cache_file_for(account_name=None):
    """
    Get the portfolio cache file for an account.
    Each user gets their own portfolio_<username>.json file.

    Raises ValueError if account_name is invalid.
    """
    if not account_name or not account_name.strip():
        raise ValueError("Account name is required - no default portfolio allowed")

    raw_name = account_name.strip()
    if _is_generated_account_name(raw_name):
        raise ValueError(f"Invalid account identifier '{raw_name}'. Please log in again to create a valid user record.")

    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name).strip("_")

    if not safe_name:
        raise ValueError("Invalid account name after sanitization")

    return ROOT / f"portfolio_{safe_name}.json"


class PortfolioService:

    def __init__(self):

        self.client: Optional[
            AngelOneAPIClient
        ] = None

    def clear_saved_auth(self):
        env_file = ROOT / ".env"
        if env_file.exists():
            try:
                env_lines = env_file.read_text(encoding="utf-8").splitlines()
                cleaned = [
                    line for line in env_lines
                    if not line.startswith("ANGELONE_MF_")
                ]
                env_file.write_text("\n".join(cleaned).rstrip() + ("\n" if cleaned else ""), encoding="utf-8")
            except OSError:
                pass

    def list_sessions(self):
        return list_account_sessions()

    def set_active_session(self, account_name):
        session = get_account_session(account_name)
        if not session:
            raise RuntimeError(f"No session found for account '{account_name}'.")

        set_active_account_name(account_name)
        self.client = AngelOneAPIClient(account_name)
        return self

    def login_existing_session(self, account_name="default"):
        session = get_account_session(account_name)
        if not session:
            raise RuntimeError(f"No saved session found for account '{account_name}'.")

        # Check if auth is valid and not expired
        auth_valid, auth_details = is_auth_valid(account_name)
        if not auth_valid:
            auth_status = get_auth_status(account_name)
            raise RuntimeError(
                f"Authentication for '{account_name}' is {auth_status.get('status_code')}. "
                "Please log in again."
            )

        self.set_active_session(account_name)
        return self

    def login_and_fetch(self, account_name=None):

        requested_account = account_name.strip() if account_name and account_name.strip() else None
        profile_tag = requested_account or f"profile_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        active_account = get_active_account_name() or ""

        # --------------------------------------------------
        # 1. Reuse only the same saved account; never the prior user's session.
        # --------------------------------------------------

        print()
        print("=" * 60)
        print(f"Login Flow for: {requested_account}")
        print("=" * 60)

        authenticated = False
        if requested_account == active_account:
            try:
                self.client = AngelOneAPIClient(requested_account)

                print(
                    "Existing authentication found for this account."
                )

                print(
                    "Validating stored authentication..."
                )

                authenticated = True

            except Exception as exc:

                print(
                    f"Stored authentication unavailable: "
                    f"{exc}"
                )
        else:
            print(
                f"New account or account change detected. "
                "Starting fresh browser login..."
            )

        # --------------------------------------------------
        # 2. Login only if required
        # --------------------------------------------------

        if authenticated:

            print(
                "Reusing existing authentication."
            )

            print(
                "Skipping browser login."
            )

        else:

            print(
                "Starting Angel One browser login..."
            )

            self.clear_saved_auth()
            resolved_login_name = AngelOneAuthenticator().login(account_name=profile_tag, headless=False)

            saved_sessions = list_account_sessions()
            valid_sessions = [
                s.get("account_name")
                for s in saved_sessions
                if s.get("account_name")
                and not _is_generated_account_name(s["account_name"])
            ]

            resolved_account = (
                resolved_login_name
                if resolved_login_name and not _is_generated_account_name(resolved_login_name)
                else (valid_sessions[-1] if valid_sessions else None)
            )

            if not resolved_account:
                raise RuntimeError("No valid user account was detected after login. The Angel One session did not expose a real profile name.")

            self.client = AngelOneAPIClient(resolved_account)
            requested_account = resolved_account

        # --------------------------------------------------
        # 3. APIs
        # --------------------------------------------------

        holdings_api = HoldingsAPI(
            self.client
        )

        scheme_api = SchemeAPI(
            self.client
        )

        sip_api = SIPAPI(
            self.client
        )

        # --------------------------------------------------
        # 4. Fetch Holdings
        # --------------------------------------------------

        print()
        print(
            "Fetching portfolio holdings..."
        )

        holdings = (
            holdings_api.get_holdings()
        )

        print(
            f"Found {len(holdings)} "
            f"mutual fund holdings."
        )

        final_holdings = []

        # --------------------------------------------------
        # 5. Process each scheme
        # --------------------------------------------------

        for index, holding in enumerate(
            holdings,
            start=1,
        ):

            scheme_name = holding.get(
                "schemeName",
                "",
            )

            isin = holding.get(
                "isin",
            )

            scheme_code = holding.get(
                "schemeCode",
            )

            print()
            print(
                f"[{index}/{len(holdings)}] "
                f"{scheme_name}"
            )

            if not isin or not scheme_code:

                print(
                    "Skipping scheme because "
                    "ISIN or scheme code is missing."
                )

                continue

            # --------------------------------------------------
            # API 2
            # --------------------------------------------------

            print(
                "  API 2 - holding details"
            )

            holding_detail = (
                holdings_api
                .get_holding_detail(
                    isin,
                    scheme_code,
                )
            )

            # --------------------------------------------------
            # API 3
            # --------------------------------------------------

            print(
                "  API 3 - scheme details"
            )

            scheme_detail = (
                scheme_api.get_scheme(
                    isin,
                    scheme_code,
                )
            )

            # --------------------------------------------------
            # API 4
            # --------------------------------------------------

            print(
                "  API 4 - SIP details"
            )

            if holding.get(
                "sipEnabled"
            ) is True:

                sip_detail = (
                    sip_api.get_sip(
                        isin,
                        scheme_code,
                    )
                )

            else:

                print(
                    "  SIP not enabled "
                    "for this scheme."
                )

                sip_detail = {
                    "status": "success",
                    "data": {
                        "bookOverView": {},
                        "sips": [],
                        "summary": {},
                    },
                }

            # --------------------------------------------------
            # Format
            # --------------------------------------------------

            formatted = (
                self._format_scheme(
                    holding=holding,
                    holding_detail=holding_detail,
                    scheme_detail=scheme_detail,
                    sip_detail=sip_detail,
                )
            )

            final_holdings.append(
                formatted
            )

        # --------------------------------------------------
        # 6. Build and Cache Portfolio
        # --------------------------------------------------

        print()
        print(f"Building portfolio response for {requested_account}...")

        portfolio = PortfolioResponse(
            holdings_count=len(
                final_holdings
            ),
            holdings=final_holdings,
        )

        result = portfolio.model_dump()
        
        # Add metadata
        result["account_name"] = requested_account
        result["fetched_at"] = datetime.now(timezone.utc).isoformat()
        
        # Save to user-specific portfolio file
        target_cache = _cache_file_for(requested_account)
        target_cache.write_text(
            json.dumps(
                result,
                indent=2,
            ),
            encoding="utf-8",
        )
        
        print(f"✓ Portfolio saved to: {target_cache.name}")
        print(f"  Account: {requested_account}")
        print(f"  Holdings: {len(final_holdings)}")
        print(f"  Fetched at: {result.get('fetched_at')}")
        
        # Set this as the active account
        set_active_account_name(requested_account)

        return result

    def get_cached_portfolio(self, account_name=None):
        """
        Get cached portfolio for a specific account.

        Args:
            account_name: Required - which user's portfolio to load

        Returns:
            dict: Portfolio data for the user

        Raises:
            RuntimeError: If no portfolio cached for this account
        """
        if not account_name or not account_name.strip():
            raise RuntimeError(
                "Account name is required. "
                "No default portfolio - please log in to fetch portfolio data."
            )

        try:
            target_cache = _cache_file_for(account_name)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        if not target_cache.exists():
            raise RuntimeError(
                f"No portfolio found for '{account_name}'. "
                "The saved account is invalid or stale. Please log in again."
            )

        return json.loads(
            target_cache.read_text(
                encoding="utf-8",
            )
        )

    @staticmethod
    def _format_scheme(
        holding,
        holding_detail,
        scheme_detail,
        sip_detail,
    ):

        folio_numbers = (
            holding_detail.get(
                "folioNumbers"
            )
            or []
        )

        if not folio_numbers:

            folio_holdings = (
                holding_detail.get(
                    "folioHoldings"
                )
                or []
            )

            folio_numbers = [
                item.get("folioNumber")
                for item in folio_holdings
                if item.get("folioNumber")
            ]

        sip_list = (
            sip_detail
            .get("data", {})
            .get("sips", [])
        )

        active_sip = (
            sip_list[0]
            if sip_list
            else None
        )

        monthly_sip = None
        start_date = None
        sip_date = None

        if active_sip:

            monthly_sip = (
                active_sip.get(
                    "installmentAmount"
                )
            )

            start_date = (
                active_sip.get(
                    "startDate"
                )
            )

            next_sip_date = (
                active_sip.get(
                    "nextSipDueDate"
                )
            )

            if next_sip_date:

                sip_date = (
                    PortfolioService
                    ._timestamp_to_day(
                        next_sip_date
                    )
                )

        return MutualFundHolding(

            scheme_name=holding.get(
                "schemeName"
            ),

            folio_no=folio_numbers,

            sip_date=sip_date,

            start_date=start_date,

            monthly_sip=monthly_sip,

            total_invested=holding.get(
                "investedValue"
            ),

            current_units=holding.get(
                "totalUnitsAllocated"
            ),

            current_nav=holding.get(
                "currentNav"
            ),

            ter=scheme_detail.get(
                "expenseRatio"
            ),
        )

    @staticmethod
    def _timestamp_to_day(
        timestamp
    ):

        from datetime import (
            datetime,
            timezone,
        )

        try:

            date = datetime.fromtimestamp(
                timestamp / 1000,
                tz=timezone.utc,
            )

            return date.day

        except Exception:

            return None