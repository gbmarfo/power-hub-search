"""Bridge Power Hub vault documents into power-hub-search indexes."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import Column, MetaData, String, Table, Text, inspect
from sqlalchemy.orm import Session

from database import schemas as search_schemas
from database import search_crud
from powerhub import crud, models, storage
from services.text_search import TextSearch
from services.vector_search import VectorSearch

logger = logging.getLogger(__name__)

DOC_TABLE = "powerhub_search_docs"


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
        content = file.content_text or ""
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
    return rows


def _sync_docs(db: Session, org_id: str, folder_id: str | None, rows: list[dict]) -> int:
    _ensure_doc_table(db)
    engine = db.get_bind()
    metadata = MetaData()
    table = Table(DOC_TABLE, metadata, autoload_with=engine)

    if folder_id:
        db.execute(table.delete().where(table.c.folder_id == folder_id))
    else:
        db.execute(table.delete().where(table.c.org_id == org_id))

    if rows:
        db.execute(table.insert(), rows)
    db.commit()
    return len(rows)


def create_index_from_vault(
    db: Session,
    *,
    org_id: str,
    title: str,
    description: str | None,
    folder_id: str | None,
    created_by: str,
) -> models.VaultSearchIndexLink:
    rows = _build_rows(db, org_id, folder_id)
    if not rows:
        raise ValueError(
            "No documents found to index. Upload files to the vault (or selected folder) first."
        )

    count = _sync_docs(db, org_id, folder_id, rows)

    payload = search_schemas.SearchIndexCreate(
        title=title,
        description=description or f"Power Hub vault index ({count} documents)",
        table_name=DOC_TABLE,
        text_columns="name,path,content,concatenated_text",
        id_col="id",
        org_id=org_id,
        source="powerhub",
        schema_name=None,
        created_by=created_by,
    )
    search_index = search_crud.create_search_index(db=db, search_index=payload)
    index_id = search_index.global_id

    text_search = TextSearch(index_file=index_id)
    for row in rows:
        try:
            text_search.add_document(row["id"], row["concatenated_text"])
        except Exception as exc:
            logger.warning("Skipping text index for %s: %s", row["id"], exc)
    text_search.data = [(row["id"], row["concatenated_text"]) for row in rows]

    inserted = 0
    try:
        vector_search = VectorSearch(file_id=index_id, org_id=org_id)
        inserted = vector_search.create_index(
            data=rows,
            text_column="concatenated_text",
            id_column="id",
            org_id=org_id,
        )
    except Exception as exc:
        logger.warning("Milvus indexing unavailable, text index only: %s", exc)
        inserted = len(rows)

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
    try:
        VectorSearch(file_id=link.search_index_id, org_id=link.org_id).drop_index()
    except Exception as exc:
        logger.warning("Failed to drop Milvus collection: %s", exc)
    search_crud.delete_search_index(db, link.search_index_id)
    db.delete(link)
    db.commit()
