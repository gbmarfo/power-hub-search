"""Power Hub data access helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from powerhub import models, storage
from powerhub.capabilities import capabilities_for, normalize_role


def get_user_by_email(db: Session, email: str):
    from database import models as db_models

    return (
        db.query(db_models.User)
        .filter(func.lower(db_models.User.email) == email.lower())
        .first()
    )


def get_user_by_username(db: Session, username: str):
    from database import models as db_models

    return (
        db.query(db_models.User)
        .filter(db_models.User.username == username)
        .first()
    )


def get_user_by_id(db: Session, user_id: str):
    from database import models as db_models

    return db.query(db_models.User).filter(db_models.User.user_id == user_id).first()


def user_to_out(user) -> dict:
    role = normalize_role(user.role)
    return {
        "user_id": user.user_id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "organization_id": user.organization_id,
        "role": role,
        "is_active": user.is_active,
        "capabilities": capabilities_for(role),
    }


def ensure_settings(db: Session, org_id: str) -> models.VaultSettings:
    settings = (
        db.query(models.VaultSettings)
        .filter(models.VaultSettings.org_id == org_id)
        .first()
    )
    if settings is None:
        settings = models.VaultSettings(org_id=org_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def log_audit(
    db: Session,
    *,
    org_id: str,
    actor: str,
    action: str,
    item_type: str | None = None,
    item_id: str | None = None,
    detail: str | None = None,
) -> None:
    event = models.VaultAuditEvent(
        id=storage.new_id(),
        org_id=org_id,
        actor=actor,
        action=action,
        item_type=item_type,
        item_id=item_id,
        detail=detail,
    )
    db.add(event)
    activity = models.VaultActivity(
        id=storage.new_id(),
        org_id=org_id,
        actor=actor,
        action=action,
        item_name=detail,
        item_id=item_id,
    )
    db.add(activity)
    db.commit()


def notify(
    db: Session,
    *,
    user_id: str,
    org_id: str,
    kind: str,
    title: str,
    body: str | None = None,
) -> None:
    note = models.VaultNotification(
        id=storage.new_id(),
        user_id=user_id,
        org_id=org_id,
        kind=kind,
        title=title,
        body=body,
    )
    db.add(note)
    db.commit()


def folder_path(db: Session, folder: models.VaultFolder | None) -> str:
    if folder is None:
        return "/"
    parts: list[str] = []
    current = folder
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        parts.append(current.name)
        if not current.parent_id:
            break
        current = db.query(models.VaultFolder).filter_by(id=current.parent_id).first()
    return "/" + "/".join(reversed(parts))


def breadcrumbs(db: Session, folder: models.VaultFolder | None) -> list[models.VaultFolder]:
    if folder is None:
        return []
    chain: list[models.VaultFolder] = []
    current = folder
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        if not current.parent_id:
            break
        current = db.query(models.VaultFolder).filter_by(id=current.parent_id).first()
    return list(reversed(chain))


def storage_used(db: Session, org_id: str) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.VaultFile.size_bytes), 0))
        .filter(
            models.VaultFile.org_id == org_id,
            models.VaultFile.is_deleted.is_(False),
        )
        .scalar()
    )
    return int(total or 0)


def list_children(
    db: Session, org_id: str, folder_id: str | None
) -> tuple[list[models.VaultFolder], list[models.VaultFile]]:
    folders = (
        db.query(models.VaultFolder)
        .filter(
            models.VaultFolder.org_id == org_id,
            models.VaultFolder.is_deleted.is_(False),
            models.VaultFolder.parent_id == folder_id
            if folder_id
            else models.VaultFolder.parent_id.is_(None),
        )
        .order_by(models.VaultFolder.name)
        .all()
    )
    files = (
        db.query(models.VaultFile)
        .filter(
            models.VaultFile.org_id == org_id,
            models.VaultFile.is_deleted.is_(False),
            models.VaultFile.folder_id == folder_id
            if folder_id
            else models.VaultFile.folder_id.is_(None),
        )
        .order_by(models.VaultFile.name)
        .all()
    )
    return folders, files


def create_folder(
    db: Session,
    *,
    org_id: str,
    owner_id: str,
    name: str,
    parent_id: str | None,
) -> models.VaultFolder:
    parent = None
    if parent_id:
        parent = (
            db.query(models.VaultFolder)
            .filter_by(id=parent_id, org_id=org_id, is_deleted=False)
            .first()
        )
        if parent is None:
            raise ValueError("Parent folder not found")
    folder = models.VaultFolder(
        id=storage.new_id(),
        name=name.strip(),
        parent_id=parent_id,
        org_id=org_id,
        owner_id=owner_id,
        path="/",
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    folder.path = folder_path(db, folder)
    db.commit()
    db.refresh(folder)
    return folder


def upload_file(
    db: Session,
    *,
    org_id: str,
    owner_id: str,
    folder_id: str | None,
    filename: str,
    data: bytes,
) -> models.VaultFile:
    if folder_id:
        folder = (
            db.query(models.VaultFolder)
            .filter_by(id=folder_id, org_id=org_id, is_deleted=False)
            .first()
        )
        if folder is None:
            raise ValueError("Folder not found")
    file_id = storage.new_id()
    path = storage.save_upload(org_id, file_id, filename, data)
    text = storage.extract_text(filename, data)
    record = models.VaultFile(
        id=file_id,
        name=filename,
        folder_id=folder_id,
        org_id=org_id,
        owner_id=owner_id,
        storage_path=path,
        mime_type=storage.guess_mime(filename),
        extension=storage.extension_of(filename),
        size_bytes=len(data),
        content_text=text,
        modified_by=owner_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def soft_delete_file(db: Session, file: models.VaultFile, actor: str) -> None:
    file.is_deleted = True
    file.deleted_at = datetime.utcnow()
    file.deleted_by = actor
    file.original_folder_id = file.folder_id
    file.folder_id = None
    file.storage_path = storage.move_to_recycle(file.storage_path, file.id)
    db.commit()


def soft_delete_folder(db: Session, folder: models.VaultFolder, actor: str) -> None:
    folder.is_deleted = True
    folder.deleted_at = datetime.utcnow()
    folder.deleted_by = actor
    folder.original_parent_id = folder.parent_id
    folder.parent_id = None
    # Soft-delete nested files/folders
    children_folders = (
        db.query(models.VaultFolder)
        .filter_by(parent_id=folder.id, is_deleted=False)
        .all()
    )
    for child in children_folders:
        soft_delete_folder(db, child, actor)
    children_files = (
        db.query(models.VaultFile)
        .filter_by(folder_id=folder.id, is_deleted=False)
        .all()
    )
    for child in children_files:
        soft_delete_file(db, child, actor)
    db.commit()


def restore_file(db: Session, file: models.VaultFile) -> None:
    file.is_deleted = False
    file.deleted_at = None
    file.deleted_by = None
    target = file.original_folder_id
    if target:
        parent = db.query(models.VaultFolder).filter_by(id=target, is_deleted=False).first()
        if parent is None:
            target = None
    file.folder_id = target
    file.original_folder_id = None
    file.storage_path = storage.restore_from_recycle(
        file.storage_path, file.org_id, file.id, file.name
    )
    db.commit()


def restore_folder(db: Session, folder: models.VaultFolder) -> None:
    folder.is_deleted = False
    folder.deleted_at = None
    folder.deleted_by = None
    target = folder.original_parent_id
    if target:
        parent = db.query(models.VaultFolder).filter_by(id=target, is_deleted=False).first()
        if parent is None:
            target = None
    folder.parent_id = target
    folder.original_parent_id = None
    folder.path = folder_path(db, folder)
    db.commit()


def search_library(
    db: Session,
    org_id: str,
    query: str,
    kind: str | None = None,
) -> list[dict]:
    q = (query or "").strip()
    hits: list[dict] = []
    if kind in (None, "", "all", "folders"):
        folders = (
            db.query(models.VaultFolder)
            .filter(
                models.VaultFolder.org_id == org_id,
                models.VaultFolder.is_deleted.is_(False),
                models.VaultFolder.name.ilike(f"%{q}%") if q else True,
            )
            .limit(50)
            .all()
        )
        for folder in folders:
            hits.append(
                {
                    "id": folder.id,
                    "name": folder.name,
                    "item_type": "folder",
                    "path": folder.path,
                }
            )
    if kind in (None, "", "all", "documents", "images", "media", "files"):
        files_q = db.query(models.VaultFile).filter(
            models.VaultFile.org_id == org_id,
            models.VaultFile.is_deleted.is_(False),
        )
        if q:
            files_q = files_q.filter(
                or_(
                    models.VaultFile.name.ilike(f"%{q}%"),
                    models.VaultFile.content_text.ilike(f"%{q}%"),
                )
            )
        files = files_q.limit(100).all()
        image_ext = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
        media_ext = {"mp3", "mp4", "wav", "mov", "avi", "webm"}
        doc_ext = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"}
        for file in files:
            ext = (file.extension or "").lower()
            if kind == "images" and ext not in image_ext:
                continue
            if kind == "media" and ext not in media_ext:
                continue
            if kind == "documents" and ext not in doc_ext:
                continue
            folder = (
                db.query(models.VaultFolder).filter_by(id=file.folder_id).first()
                if file.folder_id
                else None
            )
            hits.append(
                {
                    "id": file.id,
                    "name": file.name,
                    "item_type": "file",
                    "path": folder_path(db, folder),
                    "extension": file.extension,
                    "mime_type": file.mime_type,
                    "size_bytes": file.size_bytes,
                }
            )
    return hits[:50]


def files_for_index(
    db: Session, org_id: str, folder_id: str | None
) -> list[models.VaultFile]:
    query = db.query(models.VaultFile).filter(
        models.VaultFile.org_id == org_id,
        models.VaultFile.is_deleted.is_(False),
    )
    if not folder_id:
        return query.all()

    folder = (
        db.query(models.VaultFolder)
        .filter_by(id=folder_id, org_id=org_id, is_deleted=False)
        .first()
    )
    if folder is None:
        return []

    # Include the selected folder and all descendant folders.
    prefix = (folder.path or f"/{folder.name}").rstrip("/")
    folder_ids = [
        f.id
        for f in db.query(models.VaultFolder)
        .filter(
            models.VaultFolder.org_id == org_id,
            models.VaultFolder.is_deleted.is_(False),
            or_(
                models.VaultFolder.id == folder_id,
                models.VaultFolder.path == prefix,
                models.VaultFolder.path.like(f"{prefix}/%"),
            ),
        )
        .all()
    ]
    if not folder_ids:
        folder_ids = [folder_id]
    return query.filter(models.VaultFile.folder_id.in_(folder_ids)).all()


def list_folders_with_counts(db: Session, org_id: str) -> list[dict]:
    folders = (
        db.query(models.VaultFolder)
        .filter(
            models.VaultFolder.org_id == org_id,
            models.VaultFolder.is_deleted.is_(False),
        )
        .order_by(models.VaultFolder.path, models.VaultFolder.name)
        .all()
    )
    results = []
    for folder in folders:
        count = len(files_for_index(db, org_id, folder.id))
        results.append(
            {
                "id": folder.id,
                "name": folder.name,
                "path": folder.path or f"/{folder.name}",
                "file_count": count,
            }
        )
    return results
