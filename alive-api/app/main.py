from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes_auth import router as auth_router
from app.api.routes_checkin import router as checkin_router
from app.api.routes_contacts import router as contacts_router
from app.api.routes_settings import router as settings_router
from app.api.routes_logs import router as logs_router
from app.api.routes_account import router as account_router

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(checkin_router, prefix="/api/v1")
app.include_router(contacts_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(logs_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"ok": True}
