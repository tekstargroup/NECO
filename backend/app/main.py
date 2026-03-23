"""
NECO - Next-Gen Compliance Engine
Main FastAPI Application
"""

from fastapi import FastAPI, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.classification import router as classification_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.broker import router as broker_router
from app.api.v1.enrichment import router as enrichment_router
from app.api.v1.shipments import router as shipments_router
from app.api.v1.shipment_documents import router as shipment_documents_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.exports import router as exports_router
from app.api.v1.regulatory import router as regulatory_router
from app.api.v1.psc_radar import router as psc_radar_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting NECO application...")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NECO application...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Next-Gen Compliance Engine for U.S. Customs",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    """
    Detailed health check
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected",  # TODO: Add actual DB health check
        "redis": "connected",  # TODO: Add actual Redis health check
    }


# Include routers
app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    documents_router,
    prefix="/api/v1/documents",
    tags=["Documents"]
)

app.include_router(
    health_router,
    prefix="/api/v1/health",
    tags=["Health"]
)

app.include_router(
    classification_router,
    prefix="/api/v1/classification",
    tags=["Classification"]
)

app.include_router(
    compliance_router,
    prefix="/api/v1/compliance",
    tags=["Compliance"]
)

app.include_router(
    broker_router,
    prefix="/api/v1/broker",
    tags=["Broker"]
)

app.include_router(
    enrichment_router,
    prefix="/api/v1/enrichment",
    tags=["Enrichment"]
)

app.include_router(
    shipments_router,
    prefix="/api/v1/shipments",
    tags=["Shipments"]
)

app.include_router(
    shipment_documents_router,
    prefix="/api/v1/shipment-documents",
    tags=["Shipment Documents"]
)

app.include_router(
    reviews_router,
    prefix="/api/v1",
    tags=["Reviews"]
)

# Export creation endpoints (under reviews)
app.include_router(
    exports_router,
    prefix="/api/v1/reviews",
    tags=["Exports"]
)

# Export status/download endpoints (separate prefix)
# Import the functions directly and create routes
from app.api.v1.exports import get_export_status, get_export_download_url, download_export_file

exports_status_router = APIRouter(tags=["Exports"])

exports_status_router.get("/{export_id}/status")(get_export_status)
exports_status_router.get("/{export_id}/download-url")(get_export_download_url)
exports_status_router.get("/{export_id}/download")(download_export_file)

app.include_router(
    exports_status_router,
    prefix="/api/v1/exports",
    tags=["Exports"]
)

app.include_router(
    regulatory_router,
    prefix="/api/v1",
    tags=["Regulatory"]
)

app.include_router(
    psc_radar_router,
    prefix="/api/v1",
    tags=["PSC Radar"]
)


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9000,
        reload=settings.DEBUG,
    )


