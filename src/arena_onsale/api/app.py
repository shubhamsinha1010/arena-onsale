from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response

from arena_onsale.api.deps import get_runtime
from arena_onsale.api.health import router as health_router
from arena_onsale.shared.metrics import CONTENT_TYPE_LATEST, render_metrics
from arena_onsale.shared.runtime import build_runtime
from arena_onsale.shared.settings import Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    runtime = build_runtime(settings)
    app.state.runtime = runtime
    try:
        yield
    finally:
        await runtime.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(
        title="Arena Onsale",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.include_router(health_router)

    @application.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        runtime = get_runtime(request)
        payload = render_metrics(runtime.pool_collector, runtime.engine)
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()
