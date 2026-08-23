"""Resolve vector index configuration for search indexes."""

from __future__ import annotations

import config
from database import models as search_models
from powerhub import crud, models


def resolve_vector_config(
    db,
    org_id: str,
    *,
    search_index: search_models.SearchIndex | None = None,
    embedding_model: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict:
    settings = crud.ensure_settings(db, org_id)
    resolved_embedding = (
        embedding_model
        or (search_index.embedding_model if search_index else None)
        or settings.default_embedding_model
        or config.BASE_EMBEDDING_MODEL
    )
    resolved_chunk_size = (
        chunk_size
        if chunk_size is not None
        else (
            search_index.chunk_size
            if search_index and search_index.chunk_size is not None
            else settings.default_chunk_size
        )
    )
    if resolved_chunk_size is None:
        resolved_chunk_size = config.DEFAULT_CHUNK_SIZE

    resolved_chunk_overlap = (
        chunk_overlap
        if chunk_overlap is not None
        else (
            search_index.chunk_overlap
            if search_index and search_index.chunk_overlap is not None
            else settings.default_chunk_overlap
        )
    )
    if resolved_chunk_overlap is None:
        resolved_chunk_overlap = config.DEFAULT_CHUNK_OVERLAP

    return {
        "embedding_model": resolved_embedding,
        "chunk_size": int(resolved_chunk_size),
        "chunk_overlap": int(resolved_chunk_overlap),
    }
