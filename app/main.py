import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import get_settings
from app.core.logging import logger
from app.database.connection import engine
import app.database.models  # Ensures all models are registered
from app.api.auth import router as auth_router
from app.api.businesses import router as business_router
from app.api.products import router as products_router
from app.api.inventory import router as inventory_router
from app.api.sales import router as sales_router
from app.api.expenses import router as expenses_router
from app.api.blockchain import router as blockchain_router
from app.api.analytics import router as analytics_router
from app.api.approvals import router as approvals_router
from app.api.ai import router as ai_router
from app.api.pools import router as pools_router
from app.api.webhooks import router as webhooks_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("UbuntuBiz backend started.")
    yield
    # Shutdown
    logger.info("Shutting down UbuntuBiz backend...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-oriented Backend OS for South African Spaza Shops & Informal Township Retailers.",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_logging(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    logger.debug(f"{request.method} {request.url.path} returned {response.status_code} in {process_time:.4f}s")
    return response


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled {type(exc).__name__} on {request.method} {request.url.path}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."}
    )


# Health Check Endpoints
@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "currency": settings.DEFAULT_CURRENCY,
        "chain_id": settings.AVAX_FUJI_CHAIN_ID,
    }


@app.get("/ready", tags=["Health"])
@app.get(f"{settings.API_V1_PREFIX}/ready", tags=["Health"])
def readiness_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error(f"Database readiness check failed ({type(exc).__name__})")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready"
        ) from exc
    return {"status": "ready"}


# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(business_router, prefix=settings.API_V1_PREFIX)
app.include_router(products_router, prefix=settings.API_V1_PREFIX)
app.include_router(inventory_router, prefix=settings.API_V1_PREFIX)
app.include_router(sales_router, prefix=settings.API_V1_PREFIX)
app.include_router(expenses_router, prefix=settings.API_V1_PREFIX)
app.include_router(blockchain_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(approvals_router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_router, prefix=settings.API_V1_PREFIX)
app.include_router(pools_router, prefix=settings.API_V1_PREFIX)
app.include_router(webhooks_router, prefix=settings.API_V1_PREFIX)
