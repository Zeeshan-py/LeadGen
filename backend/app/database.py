from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_runtime_columns()


def _ensure_runtime_columns() -> None:
    inspector = inspect(engine)
    statements: list[str] = []
    if inspector.has_table("leads"):
        columns = {column["name"] for column in inspector.get_columns("leads")}
        if "social_links" not in columns:
            statements.append("ALTER TABLE leads ADD COLUMN social_links JSON NOT NULL DEFAULT '{}'")
        if "social_status" not in columns:
            statements.append("ALTER TABLE leads ADD COLUMN social_status VARCHAR(40) NOT NULL DEFAULT 'missing'")
    for table_name in ("campaigns", "lead_generation_jobs"):
        if inspector.has_table(table_name):
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "continent" not in columns:
                statements.append(
                    f"ALTER TABLE {table_name} ADD COLUMN continent VARCHAR(80) NOT NULL DEFAULT ''"
                )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_leads_social_status ON leads (social_status)"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
