"""SQLAlchemy declarative base and metadata conventions.

The naming convention below is what makes this project "Alembic-ready".
Without it, Alembic autogenerate emits unnamed constraints, which PostgreSQL
then names itself; the generated migration is not reproducible and later
``ALTER``/``DROP`` statements cannot reliably target the constraint.

Fixing the convention before the first table exists is far cheaper than
retrofitting it after.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

__all__ = ["NAMING_CONVENTION", "Base", "metadata"]

NAMING_CONVENTION: dict[str, Any] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: Shared metadata for every ORM model in the project.
metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    No models are defined in Phase 1. Subclasses will appear alongside the
    data-ingestion work, together with their Alembic migrations.
    """

    metadata = metadata
