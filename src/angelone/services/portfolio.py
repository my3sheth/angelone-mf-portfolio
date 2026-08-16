import json
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


ROOT = Path(__file__).resolve().parents[3]

CACHE_FILE = ROOT / "portfolio.json"


class PortfolioService:

    def __init__(self):

        self.client: Optional[
            AngelOneAPIClient
        ] = None

    def login_and_fetch(self):

        # --------------------------------------------------
        # 1. Try existing authentication
        # --------------------------------------------------

        print()
        print("=" * 60)
        print("Checking existing Angel One authentication")
        print("=" * 60)

        authenticated = False

        try:

            self.client = AngelOneAPIClient()

            print(
                "Authentication data found in .env."
            )

            print(
                "Validating stored authentication..."
            )

            authenticated = (
                self.client
                .validate_authentication()
            )

        except Exception as exc:

            print(
                f"Stored authentication unavailable: "
                f"{exc}"
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

            AngelOneAuthenticator().login()

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

        CACHE_FILE.write_text(
            json.dumps(
                result,
                indent=2,
            ),
            encoding="utf-8",
        )

        return result

    def get_cached_portfolio(self):

        if not CACHE_FILE.exists():

            raise RuntimeError(
                "No portfolio has been fetched yet. "
                "Call POST /auth/login first."
            )

        return json.loads(
            CACHE_FILE.read_text(
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