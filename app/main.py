from io import BytesIO

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from angelone.services.portfolio import PortfolioService


app = FastAPI(
    title="Angel One MF Portfolio API",
    version="1.0.0",
    description="Fetches Angel One mutual fund portfolio information.",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("app/static/index.html")


@app.get("/login")
def serve_login():
    return FileResponse("app/static/login.html")


def _get_portfolio_payload(account_name=None):
    service = PortfolioService()
    return service.get_cached_portfolio(account_name=account_name)


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
        pagesize=letter,
        title="Portfolio Report",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Mutual Fund Portfolio", styles["Title"]),
        Spacer(1, 12),
    ]

    data = [[column["label"] for column in table["columns"]]]
    for row in table["rows"]:
        data.append([
            row.get(column["key"]) for column in table["columns"]
        ])

    pdf_table = Table(data, repeatRows=1)
    pdf_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f5aa6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
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


@app.post("/auth/login")
def login_and_fetch_portfolio(account_name: str = "default"):
    try:
        service = PortfolioService()
        portfolio = service.login_and_fetch(account_name=account_name)

        return {
            "status": "success",
            "data": portfolio,
            "account_name": account_name,
        }

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        )


@app.get("/auth/sessions")
def get_saved_sessions():
    try:
        service = PortfolioService()
        return {
            "status": "success",
            "sessions": service.list_sessions(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/auth/sessions/select")
def select_saved_session(account_name: str):
    try:
        service = PortfolioService()
        service.login_existing_session(account_name)
        portfolio = service.get_cached_portfolio(account_name)
        return {
            "status": "success",
            "account_name": account_name,
            "data": portfolio,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.get("/portfolio")
def get_portfolio(account_name: str | None = None):
    try:
        return {
            "status": "success",
            "account_name": account_name,
            "data": _get_portfolio_payload(account_name),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.get("/portfolio/dashboard")
def get_portfolio_dashboard(account_name: str | None = None):
    try:
        portfolio = _get_portfolio_payload(account_name)
        return {
            "status": "success",
            "account_name": account_name,
            **_portfolio_summary(portfolio),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@app.get("/portfolio/table")
def get_portfolio_table(account_name: str | None = None):
    try:
        portfolio = _get_portfolio_payload(account_name)
        return {
            "status": "success",
            "account_name": account_name,
            **_portfolio_table(portfolio),
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