from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import get_settings
from core.logging import setup_logging
from api.endpoints import invoices, contracts, webhooks, family, stats, merkur, oegk

settings = get_settings()
setup_logging()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)

@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """422 without echoing the rejected value back (it may be PII, e.g. an insurance number)."""
    errors = [{k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(invoices.router, prefix="/api/v1")
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(family.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(merkur.router, prefix="/api/v1")
app.include_router(oegk.router, prefix="/api/v1")


@app.get("/healthz")
async def health():
    return {"status": "ok"}


_FRONTEND_DIR = Path(__file__).parent / "static" / "frontend"

if _FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(_FRONTEND_DIR / "index.html")
