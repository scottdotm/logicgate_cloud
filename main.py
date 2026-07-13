import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from logicgate_cloud.api import lake, portal, public
from logicgate_cloud.security_toolkit.api import security_toolkit as security_api
from logicgate_cloud.security_toolkit.api import security_toolkit_utilities as security_utilities

REQUIRED_SECRETS = [
    "JWT_SECRET",
]

REQUIRED_SECRET_MIN_LENGTH = {
    "JWT_SECRET": 32,
}


def _validate_secrets():
    """Fail fast on startup if required secrets are missing or insecure."""
    missing = []
    for secret in REQUIRED_SECRETS:
        value = os.environ.get(secret)
        if not value:
            missing.append(secret)
            continue
        min_length = REQUIRED_SECRET_MIN_LENGTH.get(secret)
        if min_length and len(value) < min_length:
            raise RuntimeError(f"{secret} must be at least {min_length} characters long")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def _get_cors_origins():
    """Return allowed CORS origins; reject wildcard origins."""
    origins = os.environ.get("ALLOWED_ORIGINS", "https://scottdotm.com")
    origins = [o.strip() for o in origins.split(",") if o.strip()]
    if any(o == "*" for o in origins):
        raise RuntimeError("ALLOWED_ORIGINS cannot contain the '*' wildcard")
    return origins


def _get_logger():
    try:
        from logicgate_cloud.infrastructure.logging import get_logger

        return get_logger("logicgate_cloud")
    except Exception:
        import logging

        return logging.getLogger("logicgate_cloud")


app = FastAPI(
    title="LogicGate Cloud",
    description="Multi-tenant SaaS backend for the LogicGate industrial asset platform.",
    version="0.1.0",
)

allowed_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(portal.router)
app.include_router(lake.router)
app.include_router(security_api.public_router)
app.include_router(security_api.portal_router)
app.include_router(security_utilities.utilities_router)


@app.on_event("startup")
async def startup_event():
    _validate_secrets()

    # Ensure required directories exist
    db_dir = os.path.dirname(os.environ.get("SHARED_DB_PATH", "logicgate_shared.db"))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    tenant_db_dir = os.environ.get("TENANT_DB_DIR", "tenant_databases")
    if not os.path.exists(tenant_db_dir):
        os.makedirs(tenant_db_dir, exist_ok=True)

    # Create security toolkit SQLAlchemy tables and seed templates
    try:
        from sqlalchemy import create_engine

        from logicgate_cloud.security_toolkit.common.models import Base
        from logicgate_cloud.security_toolkit.policies.service import PolicyService

        db_path = os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(engine)

        policy_service = PolicyService(db_path)
        seeded = await policy_service.seed_templates()
        if seeded:
            logger = _get_logger()
            logger.info("Seeded policy templates", count=seeded)

        from logicgate_cloud.security_toolkit.assessment_service import AssessmentService

        assessment_service = AssessmentService(db_path)
        cleaned = await assessment_service.cleanup_expired()
        if cleaned:
            logger = _get_logger()
            logger.info("Cleaned up expired assessments", count=cleaned)
    except Exception as e:
        logger = _get_logger()
        logger.warning("Failed to initialize security toolkit tables/templates", error=str(e))

    logger = _get_logger()
    logger.info("LogicGate Cloud started", version="0.1.0")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = _get_logger()
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("logicgate_cloud.main:app", host=host, port=port, reload=False)
