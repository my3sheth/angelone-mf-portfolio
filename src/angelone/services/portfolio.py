import json
import re
from pathlib import Path
from typing import Optional

from angelone.api.client import AngelOneAPIClient
from angelone.api.holdings import HoldingsAPI
from angelone.api.scheme import SchemeAPI
from angelone.api.sip import SIPAPI
from angelone.auth.playwright import AngelOneAuthenticator
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


def _cache_file_for(account_name=None):
    safe_name = (account_name or "default").strip() or "default"
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe_name).strip("_")
    if not safe_name:
        safe_name = "default"
    if safe_name == "default":
        return ROOT / "portfolio.json"
    return ROOT / f"portfolio_{safe_name}.json"


class PortfolioService:

    def __init__(self):

        self.client: Optional[
            AngelOneAPIClient
        ] = None

    def list_sessions(self):
        return list_account_sessions()

    def set_active_session(self, account_name):
        session = get_account_session(account_name)
        if not session:
            raise RuntimeError(f"No session found for account '{account_name}'.")

        from dotenv import set_key

        set_key(".env", "ANGELONE_MF_HEADERS", json.dumps(session.get("headers", {})))
        set_key(".env", "ANGELONE_MF_COOKIES", json.dumps(session.get("cookies", [])))
        set_key(".env", "ANGELONE_MF_URL", session.get("url", ""))
        set_active_account_name(account_name)
        self.client = AngelOneAPIClient()
        return self

    def login_existing_session(self, account_name="default"):
        session = get_account_session(account_name)
        if not session:
            raise RuntimeError(f"No saved session found for account '{account_name}'.")

        self.set_active_session(account_name)
        return self

    def login_and_fetch(self, account_name="default"):

        requested_account = (account_name or "default").strip() or "default"
        active_account = get_active_account_name() or "default"

        # --------------------------------------------------
        # 1. Reuse only the same saved account; never the prior user's session.
        # --------------------------------------------------

        print()
        print("=" * 60)
        print("Checking existing Angel One authentication")
        print("=" * 60)

        authenticated = False
        if requested_account == active_account:
            try:
                self.client = AngelOneAPIClient()

                print(
                    "Authentication data found in .env."
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
                f"Requested account '{requested_account}' differs from active account '{active_account}'. "
                "Forcing fresh browser login for this account."
            )

        # --------------------------------------------------
        # 2. Login only if required
        # --------------------------------------------------

        if authenticated:

            print(
                "Existing authentication is valid."
            )

            print(
                "Skipping browser login."
            )

        else:

            print(
                "Authentication is missing or expired."
            )

            print(
                "Starting Angel One browser login..."
            )

            AngelOneAuthenticator().login(account_name=account_name, headless=False)

            # Reload newly saved authentication.
            self.client = AngelOneAPIClient()

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
        # 4. API 1
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
        # 6. Final response
        # --------------------------------------------------

        portfolio = PortfolioResponse(
            holdings_count=len(
                final_holdings
            ),
            holdings=final_holdings,
        )

        result = portfolio.model_dump()
        target_cache = _cache_file_for(account_name)

        target_cache.write_text(
            json.dumps(
                result,
                indent=2,
            ),
            encoding="utf-8",
        )

        return result

    def get_cached_portfolio(self, account_name=None):
        target_cache = _cache_file_for(account_name)

        if not target_cache.exists():
            raise RuntimeError(
                "No portfolio has been fetched yet for this account. "
                "Call POST /auth/login first."
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