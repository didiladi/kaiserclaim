from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from api.endpoints import invoices, contracts, webhooks

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


@app.get("/healthz")
async def health():
    return {"status": "ok"}
