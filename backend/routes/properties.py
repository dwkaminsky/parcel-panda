from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Property
from backend.schemas import PropertyRead


router = APIRouter(prefix="/api/properties", tags=["properties"])


@router.get("", response_model=list[PropertyRead])
def list_properties(db: Session = Depends(get_db)) -> list[Property]:
    return list(db.scalars(select(Property).order_by(Property.id)).all())
