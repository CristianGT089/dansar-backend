from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.logging_config import configure_structlog, init_sentry
import app.core.models_registry  # noqa: F401 — registra todos los modelos con SQLAlchemy

configure_structlog()
settings = get_settings()
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sentry(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)
    logger.info("startup", app=settings.APP_NAME, env=settings.ENVIRONMENT)
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_wildcard = settings.ALLOWED_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r".*" if _wildcard else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.modules.auth.router import router as auth_router
from app.modules.companies.router import router as companies_router
from app.modules.users.router import router as users_router
from app.modules.users.router import company_router as company_users_router
from app.modules.catalog.router import router as modules_router
from app.modules.catalog.router import company_modules_router
from app.modules.admin.router import router as admin_router
from app.modules.financial.router import router as financial_router

PREFIX = "/api/v1"

app.include_router(auth_router, prefix=PREFIX)
app.include_router(companies_router, prefix=PREFIX)
app.include_router(users_router, prefix=PREFIX)
app.include_router(company_users_router, prefix=PREFIX)
app.include_router(modules_router, prefix=PREFIX)
app.include_router(company_modules_router, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)
app.include_router(financial_router, prefix=PREFIX)


@app.get("/health")
async def health():
    from sqlalchemy import text
    from app.core.database import get_db

    db_status = "error"
    async for db in get_db():
        try:
            await db.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "error"

    return {"status": "ok", "environment": settings.ENVIRONMENT, "db": db_status}
