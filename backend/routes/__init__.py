"""API route exports."""

from backend.routes.health import router as health_router
from backend.routes.properties import router as properties_router

__all__ = ["health_router", "properties_router"]
