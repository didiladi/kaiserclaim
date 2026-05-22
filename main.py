from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import get_settings
from api.endpoints import invoices, contracts, webhooks, family, stats

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router, prefix="/api/v1")
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(family.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")


@app.get("/healthz")
async def health():
    return {"status": "ok"}


_FRONTEND_DIR = Path(__file__).parent / "static" / "frontend"

if _FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(_FRONTEND_DIR / "index.html")
