from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from angelone.auth_store import list_all_auth_details, get_auth_status, clear_all_auth_details, is_auth_valid, mark_auth_expired
from angelone.session_store import clear_all_sessions, set_active_account_name, get_active_account_name
from angelone.services.portfolio import PortfolioService


app = FastAPI(
    title="Angel One MF Portfolio API",
    version="1.0.0",
    description="Fetches Angel One mutual fund portfolio information.",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def serve_root():
    return FileResponse("app/static/login.html")


@app.get("/login")
def serve_login():
    return FileResponse("app/static/login.html")


@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("app/static/index.html")


def _get_portfolio_payload(account_name=None, force_refresh=False):
    service = PortfolioService()
    target_account = account_name or get_active_account_name()
    if force_refresh:
        if not target_account:
            raise RuntimeError("Account name is required to refresh live data.")
        return service.login_and_fetch(account_name=target_account, force_login=False)

    try:
        return service.get_cached_portfolio(account_name=target_account)
    except Exception:
        # If cache is missing, but session is valid, fetch recent live details automatically
        if target_account:
            valid, _ = is_auth_valid(target_account)
            if valid:
                return service.login_and_fetch(account_name=target_account, force_login=False)
        raise


def _normalize_money(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _portfolio_summary(portfolio):
    holdings = portfolio.get("holdings", [])

    total_invested = sum(
        _normalize_money(holding.get("total_invested"))
        for holding in holdings
    )
    total_current_value = sum(
        _normalize_money(holding.get("current_units"))
        * _normalize_money(holding.get("current_nav"))
        for holding in holdings
    )
    total_monthly_sip = sum(
        _normalize_money(holding.get("monthly_sip"))
        for holding in holdings
    )
    total_units = sum(
        _normalize_money(holding.get("current_units"))
        for holding in holdings
    )
    average_ter = (
        sum(_normalize_money(holding.get("ter")) for holding in holdings)
        / len(holdings)
        if holdings
        else 0.0
    )
    total_gain = total_current_value - total_invested
    gain_percent = (
        (total_gain / total_invested * 100) if total_invested else 0.0
    )

    summary = {
        "holdings_count": portfolio.get("holdings_count", len(holdings)),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current_value, 2),
        "total_monthly_sip": round(total_monthly_sip, 2),
        "total_units": round(total_units, 2),
        "average_ter": round(average_ter, 2),
        "total_gain": round(total_gain, 2),
        "gain_percent": round(gain_percent, 2),
    }

    cards = [
        {
            "key": "total_invested",
            "label": "Total Invested",
            "value": summary["total_invested"],
            "unit": "INR",
        },
        {
            "key": "total_current_value",
            "label": "Current Value",
            "value": summary["total_current_value"],
            "unit": "INR",
        },
        {
            "key": "total_gain",
            "label": "Absolute Gain",
            "value": summary["total_gain"],
            "unit": "INR",
        },
        {
            "key": "gain_percent",
            "label": "Gain %",
            "value": summary["gain_percent"],
            "unit": "%",
        },
        {
            "key": "total_monthly_sip",
            "label": "Monthly SIP",
            "value": summary["total_monthly_sip"],
            "unit": "INR",
        },
        {
            "key": "average_ter",
            "label": "Avg TER",
            "value": summary["average_ter"],
            "unit": "%",
        },
    ]

    return {
        "summary": summary,
        "cards": cards,
    }


def _portfolio_table(portfolio):
    holdings = portfolio.get("holdings", [])
    columns = [
        {"key": "scheme_name", "label": "Scheme Name"},
        {"key": "folio_no", "label": "Folio No"},
        {"key": "total_invested", "label": "Invested"},
        {"key": "current_units", "label": "Units"},
        {"key": "current_nav", "label": "NAV"},
        {"key": "current_value", "label": "Current Value"},
        {"key": "monthly_sip", "label": "Monthly SIP"},
        {"key": "sip_date", "label": "SIP Date"},
        {"key": "start_date", "label": "Start Date"},
        {"key": "ter", "label": "TER"},
    ]

    rows = []
    for holding in holdings:
        current_value = (
            _normalize_money(holding.get("current_units"))
            * _normalize_money(holding.get("current_nav"))
        )
        row = {
            "scheme_name": holding.get("scheme_name"),
            "folio_no": ", ".join(
                str(item) for item in (holding.get("folio_no") or [])
            ),
            "total_invested": _normalize_money(holding.get("total_invested")),
            "current_units": _normalize_money(holding.get("current_units")),
            "current_nav": _normalize_money(holding.get("current_nav")),
            "current_value": round(current_value, 2),
            "monthly_sip": _normalize_money(holding.get("monthly_sip")),
            "sip_date": holding.get("sip_date"),
            "start_date": holding.get("start_date"),
            "ter": _normalize_money(holding.get("ter")),
        }
        rows.append(row)

    return {"columns": columns, "rows": rows}


def _excel_response(portfolio):
    table = _portfolio_table(portfolio)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Portfolio"

    sheet.append([column["label"] for column in table["columns"]])
    for row in table["rows"]:
        sheet.append([
            row.get(column["key"]) for column in table["columns"]
        ])

    for column_cells in sheet.columns:
        max_length = 0
        column = column_cells[0].column_letter
        for cell in column_cells:
            if cell.value is not None:
                max_length = max(max_length, len(str(cell.value)))
        adjusted_width = max_length + 2
        sheet.column_dimensions[column].width = adjusted_width

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="portfolio.xlsx"',
        },
    )


def _pdf_response(portfolio):
    table = _portfolio_table(portfolio)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=18,
        rightMargin=18,
        topMargin=20,
        bottomMargin=20,
        title="Portfolio Report",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Mutual Fund Portfolio", styles["Title"]),
        Spacer(1, 12),
    ]

    data = [[column["label"] for column in table["columns"]]]
    for row in table["rows"]:
        row_cells = []
        for column in table["columns"]:
            val = row.get(column["key"])
            if val is None:
                row_cells.append("—")
            elif column["key"] in ("total_invested", "current_value", "monthly_sip"):
                row_cells.append(f"₹{val:,.2f}" if isinstance(val, (int, float)) else str(val))
            elif column["key"] == "ter":
                row_cells.append(f"{val}%")
            else:
                row_cells.append(str(val))
        data.append(row_cells)

    pdf_table = Table(data, repeatRows=1)
    pdf_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f5aa6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ])
    )
    story.append(pdf_table)
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="portfolio.pdf"',
        },
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "angelone-mf-portfolio",
    }


@app.get("/auth/tracking")
def get_auth_tracking():
    """View all tracked authentication details across all accounts."""
    try:
        auth_list = list_all_auth_details()
        return {
            "status": "success",
            "total_accounts": len(auth_list),
            "accounts": auth_list,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/auth/status/{account_name}")
def check_auth_status(account_name: str):
    """Check if authentication for an account is valid and not expired."""
    try:
        auth_status = get_auth_status(account_name)
        return {
            "status": "success",
            "account_name": account_name,
            "auth": auth_status,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/auth/login")
def login_and_fetch_portfolio(account_name: str | None = None):
    try:
        service = PortfolioService()
        portfolio = service.login_and_fetch(account_name=account_name)
        active_account = portfolio.get("account_name")
        if not active_account:
            sessions = service.list_sessions()
            active_account = next(
                (
                    s["account_name"]
                    for s in sessions
                    if s.get("account_name")
                ),
                (account_name or "active-account"),
            )

        if active_account:
            from angelone.session_store import set_active_account_name
            set_active_account_name(active_account)

        return {
            "status": "success",
            "data": portfolio,
            "account_name": active_account,
        }

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/auth/sessions")
def get_saved_sessions():
    try:
        from angelone.session_store import get_active_account_name
        service = PortfolioService()
        sessions = service.list_sessions()
        # Enrich sessions with real-time auth status
        enriched = []
        for s in sessions:
            name = s.get("account_name")
            status_info = get_auth_status(name)
            enriched.append({
                **s,
                "auth_status": status_info.get("status_code", "unknown"),
                "is_valid": status_info.get("valid", False),
                "expires_at": status_info.get("expires_at"),
            })
        return {
            "status": "success",
            "active_account": get_active_account_name(),
            "sessions": enriched,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/auth/sessions/select")
async def select_saved_session(
    request: Request,
    account_name: str | None = None,
    refresh: bool = True,
):
    """
    Select an account and use its non-expired session to fetch the most recent
    portfolio details from Angel One APIs.
    """
    try:
        if not account_name:
            try:
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await request.json()
                    account_name = body.get("account_name")
                    if "refresh" in body:
                        refresh = bool(body.get("refresh"))
                elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                    form_data = await request.form()
                    account_name = form_data.get("account_name")
                    if "refresh" in form_data:
                        val = form_data.get("refresh")
                        refresh = val in (True, "true", "True", "1", 1)
            except Exception:
                pass

        target_name = (account_name or get_active_account_name() or "").strip()
        if not target_name:
            raise HTTPException(status_code=400, detail="Account name is required.")

        service = PortfolioService()
        valid, auth_details = is_auth_valid(target_name)
        if not valid:
            auth_status = get_auth_status(target_name)
            raise HTTPException(
                status_code=401,
                detail=f"Authentication for '{target_name}' is {auth_status.get('status_code', 'expired')}. Please log in again.",
            )

        set_active_account_name(target_name)

        if refresh:
            try:
                portfolio = service.login_and_fetch(account_name=target_name, force_login=False)
            except Exception as e:
                # If network or API error occurs, fallback to cached data if available
                try:
                    portfolio = service.get_cached_portfolio(target_name)
                except Exception:
                    raise e
        else:
            try:
                portfolio = service.get_cached_portfolio(target_name)
            except Exception:
                portfolio = service.login_and_fetch(account_name=target_name, force_login=False)

        return {
            "status": "success",
            "account_name": target_name,
            "data": portfolio,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/portfolio/refresh")
async def refresh_portfolio(
    request: Request,
    account_name: str | None = None,
):
    """
    Refresh live portfolio details for an account using its non-expired session.
    """
    try:
        if not account_name:
            try:
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await request.json()
                    account_name = body.get("account_name")
                elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                    form_data = await request.form()
                    account_name = form_data.get("account_name")
            except Exception:
                pass

        target_account = (account_name or get_active_account_name() or "").strip()
        if not target_account:
            raise HTTPException(status_code=400, detail="No active account specified.")

        valid, _ = is_auth_valid(target_account)
        if not valid:
            auth_status = get_auth_status(target_account)
            raise HTTPException(
                status_code=401,
                detail=f"Authentication for '{target_account}' is {auth_status.get('status_code', 'expired')}. Please log in again.",
            )

        service = PortfolioService()
        portfolio = service.login_and_fetch(account_name=target_account, force_login=False)
        return {
            "status": "success",
            "account_name": target_account,
            "data": portfolio,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.delete("/auth/sessions/{account_name}")
def delete_session(account_name: str):
    try:
        from angelone.session_store import remove_account_session
        from angelone.auth_store import delete_auth_details
        from angelone.services.portfolio import _cache_file_for
        remove_account_session(account_name)
        delete_auth_details(account_name)
        try:
            cache_file = _cache_file_for(account_name)
            if cache_file.exists():
                cache_file.unlink()
        except Exception:
            pass
        return {"status": "success", "message": f"Account '{account_name}' deleted."}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/portfolio")
def get_portfolio(account_name: str | None = None, refresh: bool = False):
    try:
        return {
            "status": "success",
            "account_name": account_name,
            "data": _get_portfolio_payload(account_name, force_refresh=refresh),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.get("/portfolio/dashboard")
def get_portfolio_dashboard(account_name: str | None = None, refresh: bool = False):
    try:
        portfolio = _get_portfolio_payload(account_name, force_refresh=refresh)
        summary_data = _portfolio_summary(portfolio)
        return {
            "status": "success",
            "account_name": portfolio.get("account_name", account_name),
            "fetched_at": portfolio.get("fetched_at"),
            **summary_data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.get("/portfolio/table")
def get_portfolio_table(account_name: str | None = None, refresh: bool = False):
    try:
        portfolio = _get_portfolio_payload(account_name, force_refresh=refresh)
        table_data = _portfolio_table(portfolio)
        return {
            "status": "success",
            "account_name": portfolio.get("account_name", account_name),
            "fetched_at": portfolio.get("fetched_at"),
            **table_data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.get("/portfolio/export/excel")
def export_portfolio_excel(account_name: str | None = None):
    try:
        portfolio = _get_portfolio_payload(account_name)
        return _excel_response(portfolio)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/portfolio/export/pdf")
def export_portfolio_pdf(account_name: str | None = None):
    try:
        portfolio = _get_portfolio_payload(account_name)
        return _pdf_response(portfolio)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = Path(__file__).resolve().parent / "static" / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")