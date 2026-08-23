"""Bridge Power Hub vault documents into power-hub-search indexes."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from sqlalchemy import Column, MetaData, String, Table, Text, inspect
from sqlalchemy.orm import Session

import config
from database import schemas as search_schemas
from database import search_crud
from powerhub import crud, models, storage
from powerhub.index_config import resolve_vector_config
from services.text_search import TextSearch
from services.vector_search import VectorSearch

logger = logging.getLogger(__name__)

DOC_TABLE = "powerhub_search_docs"


def _text_index_path(index_id: str) -> str:
    return os.path.join(config.INDEX_FOLDER_PATH, f"{index_id}_ivf.pkl")


def _ensure_doc_table(db: Session) -> None:
    engine = db.get_bind()
    inspector = inspect(engine)
    if DOC_TABLE in inspector.get_table_names():
        return
    metadata = MetaData()
    Table(
        DOC_TABLE,
        metadata,
        Column("id", String, primary_key=True),
        Column("org_id", String, index=True),
        Column("file_id", String, index=True),
        Column("folder_id", String, nullable=True),
        Column("name", String),
        Column("path", String),
        Column("extension", String),
        Column("content", Text),
        Column("concatenated_text", Text),
    )
    metadata.create_all(bind=engine)


def _build_rows(db: Session, org_id: str, folder_id: str | None) -> list[dict]:
    files = crud.files_for_index(db, org_id, folder_id)
    rows: list[dict] = []
    for file in files:
        folder = (
            db.query(models.VaultFolder).filter_by(id=file.folder_id).first()
            if file.folder_id
            else None
        )
        path = crud.folder_path(db, folder)
        ext = (file.extension or "").lower()
        content = file.content_text or ""
        # Re-parse PDF/Word on index build so text, tables, figures, and image OCR
        # are included even for files uploaded before the rich parser existed.
        if ext in {"pdf", "docx", "doc"} and file.storage_path:
            try:
                refreshed = storage.reparse_stored_file(
                    file.name,
                    file.storage_path,
                    org_id=org_id,
                    file_id=file.id,
                )
                if refreshed.strip():
                    content = refreshed
                    file.content_text = refreshed
            except Exception as exc:
                logger.warning("Reparse failed for %s: %s", file.id, exc)
        concatenated = f"{file.name}\n{path}\n{content}".strip()
        rows.append(
            {
                "id": file.id,
                "org_id": org_id,
                "file_id": file.id,
                "folder_id": folder_id,
                "name": file.name,
                "path": path,
                "extension": file.extension or "",
                "content": content,
                "concatenated_text": concatenated,
            }
        )
    if files:
        db.commit()
    return rows


def _sync_docs(db: Session, org_id: str, folder_id: str | None, rows: list[dict]) -> int:
    _ensure_doc_table(db)
    engine = db.get_bind()
    metadata = MetaData()
    table = Table(DOC_TABLE, metadata, autoload_with=engine)

    # Clear prior materializations for this scope and any overlapping file IDs
    # so re-indexing a folder does not collide with an older whole-vault sync.
    file_ids = [row["id"] for row in rows]
    if folder_id:
        db.execute(table.delete().where(table.c.folder_id == folder_id))
    else:
        db.execute(table.delete().where(table.c.org_id == org_id))
    if file_ids:
        db.execute(table.delete().where(table.c.id.in_(file_ids)))

    if rows:
        db.execute(table.insert(), rows)
    db.commit()
    return len(rows)


def _purge_docs_for_scope(db: Session, org_id: str, folder_id: str | None) -> None:
    _ensure_doc_table(db)
    engine = db.get_bind()
    metadata = MetaData()
    table = Table(DOC_TABLE, metadata, autoload_with=engine)
    if folder_id:
        db.execute(table.delete().where(table.c.folder_id == folder_id))
    else:
        db.execute(table.delete().where(table.c.org_id == org_id))
    db.commit()


def _delete_text_index_file(index_id: str) -> None:
    path = _text_index_path(index_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning("Failed to remove text index file %s: %s", path, exc)


def _rebuild_text_index(index_id: str, rows: list[dict]) -> None:
    text_search = TextSearch(index_file=index_id)
    text_search.index = {}
    text_search.documents = {}
    text_search.doc_lengths = {}
    text_search.cache = {}
    text_search.avg_doc_length = 0
    for row in rows:
        try:
            text_search.add_document(row["id"], row["concatenated_text"])
        except Exception as exc:
            logger.warning("Skipping text index for %s: %s", row["id"], exc)
    text_search.data = [(row["id"], row["concatenated_text"]) for row in rows]


def _rebuild_vector_index(
    index_id: str,
    org_id: str,
    rows: list[dict],
    *,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    try:
        vector_search = VectorSearch(
            file_id=index_id,
            org_id=org_id,
            embedding_model=embedding_model,
        )
        return vector_search.create_index(
            data=rows,
            text_column="concatenated_text",
            id_column="id",
            org_id=org_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except Exception as exc:
        logger.warning("Milvus indexing unavailable, text index only: %s", exc)
        return len(rows)


def _folder_path(db: Session, folder_id: str | None) -> str | None:
    if not folder_id:
        return None
    folder = db.query(models.VaultFolder).filter_by(id=folder_id).first()
    if folder is None:
        return None
    return (folder.path or f"/{folder.name}").rstrip("/")


def links_affected_by_folder(
    db: Session, org_id: str, changed_folder_id: str | None
) -> list[models.VaultSearchIndexLink]:
    """Return index links whose vault scope includes the changed folder."""
    links = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(org_id=org_id)
        .all()
    )
    if not changed_folder_id:
        return links

    changed_path = _folder_path(db, changed_folder_id)
    if changed_path is None:
        return []

    affected: list[models.VaultSearchIndexLink] = []
    for link in links:
        if not link.folder_id:
            affected.append(link)
            continue
        index_path = _folder_path(db, link.folder_id)
        if index_path is None:
            continue
        if changed_path == index_path or changed_path.startswith(f"{index_path}/"):
            affected.append(link)
    return affected


def get_index_integration_status(
    db: Session, link: models.VaultSearchIndexLink
) -> dict:
    """Return power-hub-search integration metadata for a vault index link."""
    search_index = search_crud.get_search_index(db, link.search_index_id)
    vector_stats: dict = {"exists": False}
    vector_cfg = resolve_vector_config(db, link.org_id, search_index=search_index)
    try:
        vector_stats = VectorSearch(
            file_id=link.search_index_id,
            org_id=link.org_id,
            embedding_model=vector_cfg["embedding_model"],
        ).get_stats()
    except Exception as exc:
        vector_stats = {"exists": False, "detail": str(exc)}

    text_index_ready = os.path.exists(_text_index_path(link.search_index_id))
    return {
        "search_index_id": link.search_index_id,
        "source": search_index.source if search_index else "powerhub",
        "table_name": search_index.table_name if search_index else DOC_TABLE,
        "registered": search_index is not None,
        "text_index_ready": text_index_ready,
        "vector_index": vector_stats,
        "embedding_model": vector_cfg["embedding_model"],
        "chunk_size": vector_cfg["chunk_size"],
        "chunk_overlap": vector_cfg["chunk_overlap"],
        "admin_search_url": f"/admin/search?index={link.search_index_id}&org={link.org_id}",
        "admin_index_url": f"/admin/indexes/{link.search_index_id}",
        "api_search_url": f"/api/v1/search/{link.search_index_id}",
        "powerhub_search_url": f"/api/v1/powerhub/indexes/{link.id}/search",
    }


def sync_index_from_vault(
    db: Session, link: models.VaultSearchIndexLink
) -> models.VaultSearchIndexLink:
    """Re-sync vault files into the existing power-hub-search index."""
    rows = _build_rows(db, link.org_id, link.folder_id)
    count = _sync_docs(db, link.org_id, link.folder_id, rows)
    search_index = search_crud.get_search_index(db, link.search_index_id)
    vector_cfg = resolve_vector_config(db, link.org_id, search_index=search_index)
    _rebuild_text_index(link.search_index_id, rows)
    inserted = _rebuild_vector_index(
        link.search_index_id,
        link.org_id,
        rows,
        **vector_cfg,
    )

    link.document_count = inserted or count
    link.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(link)
    return link


def sync_indexes_for_folder(
    db: Session, org_id: str, folder_id: str | None
) -> list[str]:
    """Re-sync all indexes whose scope includes the given folder. Returns link IDs."""
    synced: list[str] = []
    for link in links_affected_by_folder(db, org_id, folder_id):
        try:
            sync_index_from_vault(db, link)
            synced.append(link.id)
        except Exception as exc:
            logger.warning("Auto-sync failed for index link %s: %s", link.id, exc)
    return synced


def create_index_from_vault(
    db: Session,
    *,
    org_id: str,
    title: str,
    description: str | None,
    folder_id: str,
    created_by: str,
    embedding_model: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> models.VaultSearchIndexLink:
    folder = (
        db.query(models.VaultFolder)
        .filter_by(id=folder_id, org_id=org_id, is_deleted=False)
        .first()
    )
    if folder is None:
        raise ValueError("Folder not found. Choose an existing vault folder to index.")

    existing = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(org_id=org_id, folder_id=folder_id)
        .first()
    )
    if existing is not None:
        raise ValueError(
            f"An index already exists for “{folder.path or folder.name}”. "
            "Use Sync to refresh it instead of creating a duplicate."
        )

    rows = _build_rows(db, org_id, folder_id)
    if not rows:
        raise ValueError(
            f"No documents found in “{folder.path or folder.name}”. "
            "Upload files into that folder (or a subfolder) first."
        )

    count = _sync_docs(db, org_id, folder_id, rows)
    folder_label = folder.path or f"/{folder.name}"
    vector_cfg = resolve_vector_config(
        db,
        org_id,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    payload = search_schemas.SearchIndexCreate(
        title=title,
        description=description
        or f"Power Hub index of {folder_label} ({count} documents)",
        table_name=DOC_TABLE,
        text_columns="name,path,content,concatenated_text",
        id_col="id",
        org_id=org_id,
        source="powerhub",
        schema_name=None,
        created_by=created_by,
        embedding_model=vector_cfg["embedding_model"],
        chunk_size=vector_cfg["chunk_size"],
        chunk_overlap=vector_cfg["chunk_overlap"],
    )
    search_index = search_crud.create_search_index(db=db, search_index=payload)
    index_id = search_index.global_id

    _rebuild_text_index(index_id, rows)
    inserted = _rebuild_vector_index(
        index_id,
        org_id,
        rows,
        **vector_cfg,
    )

    link = models.VaultSearchIndexLink(
        id=storage.new_id(),
        org_id=org_id,
        title=title,
        description=description,
        folder_id=folder_id,
        search_index_id=index_id,
        created_by=created_by,
        document_count=inserted or count,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def delete_index_link(db: Session, link: models.VaultSearchIndexLink) -> None:
    search_index = search_crud.get_search_index(db, link.search_index_id)
    vector_cfg = resolve_vector_config(db, link.org_id, search_index=search_index)
    try:
        VectorSearch(
            file_id=link.search_index_id,
            org_id=link.org_id,
            embedding_model=vector_cfg["embedding_model"],
        ).drop_index()
    except Exception as exc:
        logger.warning("Failed to drop Milvus collection: %s", exc)
    _purge_docs_for_scope(db, link.org_id, link.folder_id)
    _delete_text_index_file(link.search_index_id)
    search_crud.delete_search_index(db, link.search_index_id)
    db.delete(link)
    db.commit()


def cleanup_powerhub_search_index(db: Session, index_id: str, org_id: str) -> None:
    """Remove vault link and materialized docs when deleting from search admin."""
    link = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(search_index_id=index_id, org_id=org_id)
        .first()
    )
    if link is not None:
        _purge_docs_for_scope(db, link.org_id, link.folder_id)
        db.delete(link)
    _delete_text_index_file(index_id)
    db.commit()
