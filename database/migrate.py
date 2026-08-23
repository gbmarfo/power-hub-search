"""Lightweight SQLite column migrations for existing deployments."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _add_column_if_missing(engine: Engine, table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table)}
    if column in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    logger.info("Added column %s.%s", table, column)


def run_migrations(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    _add_column_if_missing(
        engine,
        "search_index",
        "embedding_model",
        "embedding_model VARCHAR",
    )
    _add_column_if_missing(
        engine,
        "search_index",
        "chunk_size",
        "chunk_size INTEGER",
    )
    _add_column_if_missing(
        engine,
        "search_index",
        "chunk_overlap",
        "chunk_overlap INTEGER",
    )
    _add_column_if_missing(
        engine,
        "powerhub_settings",
        "default_embedding_model",
        "default_embedding_model VARCHAR",
    )
    _add_column_if_missing(
        engine,
        "powerhub_settings",
        "default_chunk_size",
        "default_chunk_size INTEGER",
    )
    _add_column_if_missing(
        engine,
        "powerhub_settings",
        "default_chunk_overlap",
        "default_chunk_overlap INTEGER",
    )
