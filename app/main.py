from fastapi import FastAPI, HTTPException

from angelone.services.portfolio import PortfolioService


app = FastAPI(
    title="Angel One MF Portfolio API",
    version="1.0.0",
    description="Fetches Angel One mutual fund portfolio information.",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "angelone-mf-portfolio",
    }


@app.post("/auth/login")
def login_and_fetch_portfolio():
    try:
        service = PortfolioService()

        portfolio = service.login_and_fetch()

        return {
            "status": "success",
            "data": portfolio,
        }

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        )


@app.get("/portfolio")
def get_portfolio():
    try:
        service = PortfolioService()

        return {
            "status": "success",
            "data": service.get_cached_portfolio(),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )