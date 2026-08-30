from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    parcel_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(300),
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
    )

    state: Mapped[str | None] = mapped_column(
        String(2),
    )

    zip_code: Mapped[str | None] = mapped_column(
        String(10),
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
    )

    assessed_value: Mapped[float | None] = mapped_column(
        Numeric(14, 2),
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
