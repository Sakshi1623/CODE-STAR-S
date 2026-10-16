"""FastAPI application for DriftShield Control Room backend."""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from driftshield.api.routes import create_api_router
from driftshield.api.sse import SSEBroadcaster
from driftshield.shield import Shield


def create_app(
    shield: Shield | None = None,
    broadcaster: SSEBroadcaster | None = None,
    client: Any | None = None,
    enable_sentinel: bool = False,
    sentinel_poll_interval: float = 10.0,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the DriftShield Control Room FastAPI application."""
    owns_shield = False

    if broadcaster is None:
        broadcaster = SSEBroadcaster()

    if shield is None:
        shield = Shield(
            client=client,
            enable_sentinel=enable_sentinel,
            sentinel_poll_interval=sentinel_poll_interval,
            on_event=broadcaster.on_shield_event,
        )
        owns_shield = True
    else:
        shield.subscribe(broadcaster.on_shield_event)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            loop = asyncio.get_running_loop()
            broadcaster.set_loop(loop)
        except Exception:
            pass
        yield
        if owns_shield and not shield.is_closed:
            shield.close()

    app = FastAPI(title="DriftShield Control Room API", lifespan=lifespan)

    if cors_origins is None:
        raw_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://localhost:8000",
        )
        cors_origins = [orig.strip() for orig in raw_origins.split(",") if orig.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    api_router = create_api_router(shield, broadcaster)
    app.include_router(api_router, prefix="/api")

    app.state.shield = shield
    app.state.broadcaster = broadcaster
    app.state.owns_shield = owns_shield

    return app


# Default standalone app instance
app = create_app()
