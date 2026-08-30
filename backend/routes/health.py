"""Service health endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import HealthResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    db.execute(text("SELECT 1"))
    return HealthResponse(status="ok", database="connected")
