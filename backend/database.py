import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool


def sqlalchemy_url(url: str) -> str:
    return url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(
    sqlalchemy_url(DATABASE_URL),
    pool_pre_ping=True,
    poolclass=NullPool,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
