from typing import Literal, TypedDict

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from app.api.errors import register_error_handlers
from app.api.routes import agent, auth, dashboard, evidence, flowtwin, inspections, memory, sensors, warehouse
from app.config import Settings, get_settings
from app.db.session import is_database_available


class PublicHealthResponse(TypedDict):
    status: Literal["ok"]


class DemoHealthResponse(PublicHealthResponse):
    environment: Literal["DEMO"]
    database: Literal["connected"]


app = FastAPI(
    title="AeroTwin Core",
    version="0.1.0",
    description="Client-agnostic API for AeroTwin warehouse inspections.",
)
register_error_handlers(app)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(warehouse.router, prefix="/api/v1")
app.include_router(inspections.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(sensors.sensor_router, prefix="/api/v1")
app.include_router(sensors.supervisor_router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(flowtwin.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"], response_model=None)
def health(
    settings: Settings = Depends(get_settings),
    database_available: bool = Depends(is_database_available),
) -> PublicHealthResponse | DemoHealthResponse | JSONResponse:
    if not database_available:
        content: dict[str, str] = {"status": "degraded"}
        if settings.demo_mode:
            content.update(environment="DEMO", database="unavailable")
        return JSONResponse(status_code=503, content=content)

    if settings.demo_mode:
        return {
            "status": "ok",
            "environment": "DEMO",
            "database": "connected",
        }

    return {"status": "ok"}
