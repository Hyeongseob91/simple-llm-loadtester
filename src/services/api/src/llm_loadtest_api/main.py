"""LLM Loadtest API - FastAPI main application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_loadtest_api import __version__
from llm_loadtest_api.logging_config import (
    configure_logging,
    get_logger,
    RequestLoggingMiddleware,
)
from llm_loadtest_api.routers.benchmarks import router as benchmarks_router
from llm_loadtest_api.routers.websocket import router as websocket_router
from llm_loadtest_api.routers.recommend import router as recommend_router

# Configure structured logging
configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="LLM Loadtest API",
        description="API for running LLM server load tests",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Request logging middleware (add first to capture all requests)
    app.add_middleware(RequestLoggingMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(benchmarks_router)
    app.include_router(websocket_router)
    app.include_router(recommend_router)

    @app.get("/")
    async def root():
        return {
            "service": "llm-loadtest-api",
            "version": __version__,
            "docs": "/docs",
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.on_event("startup")
    async def startup_event():
        """Log application startup."""
        logger.info("application_started", version=__version__)

    @app.on_event("shutdown")
    async def shutdown_event():
        """Log application shutdown."""
        logger.info("application_shutdown")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
