"""SpacePilot FastAPI Application Factory."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.pluto.core.config import Settings, get_settings
from src.pluto.services.watchdog import idle_watchdog_loop
from src.pluto.api.routes import (
    health_router,
    views_router,
    assets_router,
    compute_router,
    recipes_router,
    engines_router,
    storyboard_router,
    gpu_router,
    generate_router,
    audio_router,
    checkpoints_router,
    lora_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle: run background watchdog
    watchdog_task = asyncio.create_task(idle_watchdog_loop())
    yield
    # Shutdown lifecycle
    watchdog_task.cancel()
    try:
        await watchdog_task
    except asyncio.CancelledError:
        pass


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the SpacePilot FastAPI application instance."""
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Validation Error Handler (Avoids echoing unparseable inf/nan values)
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc: RequestValidationError):
        detail = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    # Register Routers
    app.include_router(health_router)
    app.include_router(compute_router)
    app.include_router(recipes_router)
    app.include_router(engines_router)
    app.include_router(storyboard_router)
    app.include_router(gpu_router)
    app.include_router(generate_router)
    app.include_router(audio_router)
    app.include_router(lora_router)
    app.include_router(assets_router)
    app.include_router(views_router)
    app.include_router(checkpoints_router)

    # Mount static frontend if available
    if settings.studio_dir.exists():
        app.mount("/", StaticFiles(directory=str(settings.studio_dir), html=True), name="studio")

    return app
