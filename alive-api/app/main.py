import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes_auth import router as auth_router
from app.api.routes_checkin import router as checkin_router
from app.api.routes_contacts import router as contacts_router
from app.api.routes_settings import router as settings_router
from app.api.routes_logs import router as logs_router
from app.api.routes_account import router as account_router

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log the full details
    body = None
    try:
        body = await request.json()
    except Exception:
        pass

    logger.error(f"Validation error on {request.method} {request.url.path}")
    logger.error(f"Request body: {body}")
    logger.error(f"Validation errors: {exc.errors()}")

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

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
