"""Files, folders, recycle bin, and library search routes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.database import get_db
from powerhub import crud, models, schemas, storage
from powerhub.deps import HubUser, get_hub_user

router = APIRouter()


def _folder_out(folder: models.VaultFolder) -> schemas.FolderOut:
    return schemas.FolderOut(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        owner_id=folder.owner_id,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _file_out(db: Session, file: models.VaultFile) -> schemas.FileOut:
    folder = (
        db.query(models.VaultFolder).filter_by(id=file.folder_id).first()
        if file.folder_id
        else None
    )
    return schemas.FileOut(
        id=file.id,
        name=file.name,
        folder_id=file.folder_id,
        mime_type=file.mime_type,
        extension=file.extension,
        size_bytes=file.size_bytes,
        starred=bool(file.starred),
        version=file.version,
        owner_id=file.owner_id,
        modified_by=file.modified_by,
        created_at=file.created_at,
        updated_at=file.updated_at,
        path=crud.folder_path(db, folder),
    )


@router.get("/library", response_model=schemas.LibraryListing)
def list_library(
    folder_id: str | None = None,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("folders.view")
    current = None
    if folder_id:
        current = (
            db.query(models.VaultFolder)
            .filter_by(id=folder_id, org_id=hub.org_id, is_deleted=False)
            .first()
        )
        if current is None:
            raise HTTPException(status_code=404, detail="Folder not found")
    folders, files = crud.list_children(db, hub.org_id, folder_id)
    crumbs = [_folder_out(f) for f in crud.breadcrumbs(db, current)]
    return schemas.LibraryListing(
        folder=_folder_out(current) if current else None,
        breadcrumbs=crumbs,
        folders=[_folder_out(f) for f in folders],
        files=[_file_out(db, f) for f in files],
    )


@router.post("/folders", response_model=schemas.FolderOut)
def create_folder(
    body: schemas.FolderCreate,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("folders.create")
    try:
        folder = crud.create_folder(
            db,
            org_id=hub.org_id,
            owner_id=hub.user_id,
            name=body.name,
            parent_id=body.parent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="folder.create",
        item_type="folder",
        item_id=folder.id,
        detail=folder.name,
    )
    return _folder_out(folder)


@router.post("/files/upload", response_model=schemas.FileOut)
async def upload_file(
    folder_id: str | None = None,
    file: UploadFile = File(...),
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("files.upload")
    data = await file.read()
    try:
        record = crud.upload_file(
            db,
            org_id=hub.org_id,
            owner_id=hub.user_id,
            folder_id=folder_id,
            filename=file.filename or "upload.bin",
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="file.upload",
        item_type="file",
        item_id=record.id,
        detail=record.name,
    )
    return _file_out(db, record)


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("files.download")
    record = (
        db.query(models.VaultFile)
        .filter_by(id=file_id, org_id=hub.org_id, is_deleted=False)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    path = Path(record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File content missing")
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="file.download",
        item_type="file",
        item_id=record.id,
        detail=record.name,
    )
    return FileResponse(path, filename=record.name, media_type=record.mime_type)


@router.post("/files/{file_id}/rename", response_model=schemas.FileOut)
def rename_file(
    file_id: str,
    body: schemas.RenameRequest,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("files.rename")
    record = (
        db.query(models.VaultFile)
        .filter_by(id=file_id, org_id=hub.org_id, is_deleted=False)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    record.name = body.name.strip()
    record.modified_by = hub.user_id
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return _file_out(db, record)


@router.post("/files/{file_id}/move", response_model=schemas.FileOut)
def move_file(
    file_id: str,
    body: schemas.MoveRequest,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("files.move")
    record = (
        db.query(models.VaultFile)
        .filter_by(id=file_id, org_id=hub.org_id, is_deleted=False)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if body.target_folder_id:
        folder = (
            db.query(models.VaultFolder)
            .filter_by(id=body.target_folder_id, org_id=hub.org_id, is_deleted=False)
            .first()
        )
        if folder is None:
            raise HTTPException(status_code=404, detail="Target folder not found")
    record.folder_id = body.target_folder_id
    record.modified_by = hub.user_id
    db.commit()
    db.refresh(record)
    return _file_out(db, record)


@router.post("/files/{file_id}/star", response_model=schemas.FileOut)
def toggle_star(
    file_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    record = (
        db.query(models.VaultFile)
        .filter_by(id=file_id, org_id=hub.org_id, is_deleted=False)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    record.starred = not bool(record.starred)
    db.commit()
    db.refresh(record)
    return _file_out(db, record)


@router.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    record = (
        db.query(models.VaultFile)
        .filter_by(id=file_id, org_id=hub.org_id, is_deleted=False)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    from powerhub.capabilities import has_capability

    if record.owner_id == hub.user_id:
        if not (
            has_capability(hub.role, "files.delete_own")
            or has_capability(hub.role, "files.delete")
        ):
            raise HTTPException(status_code=403, detail="Missing capability: files.delete_own")
    else:
        hub.require("files.delete")
    crud.soft_delete_file(db, record, hub.username)
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="file.delete",
        item_type="file",
        item_id=record.id,
        detail=record.name,
    )
    return {"message": "moved to recycle bin"}


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    folder = (
        db.query(models.VaultFolder)
        .filter_by(id=folder_id, org_id=hub.org_id, is_deleted=False)
        .first()
    )
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder.owner_id != hub.user_id:
        hub.require("files.delete")
    crud.soft_delete_folder(db, folder, hub.username)
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="folder.delete",
        item_type="folder",
        item_id=folder.id,
        detail=folder.name,
    )
    return {"message": "moved to recycle bin"}


@router.get("/recycle", response_model=list[schemas.RecycleItem])
def recycle_bin(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    settings = crud.ensure_settings(db, hub.org_id)
    retention = settings.recycle_retention_days or 30
    can_view_all = hub.role in {"admin", "superuser"}
    files = db.query(models.VaultFile).filter_by(org_id=hub.org_id, is_deleted=True).all()
    folders = db.query(models.VaultFolder).filter_by(org_id=hub.org_id, is_deleted=True).all()
    items: list[schemas.RecycleItem] = []
    now = datetime.utcnow()
    for f in files:
        if not can_view_all and f.deleted_by != hub.username and f.owner_id != hub.user_id:
            continue
        days = retention
        if f.deleted_at:
            elapsed = (now - f.deleted_at).days
            days = max(0, retention - elapsed)
        items.append(
            schemas.RecycleItem(
                id=f.id,
                name=f.name,
                item_type="file",
                deleted_at=f.deleted_at,
                deleted_by=f.deleted_by,
                days_remaining=days,
                original_location="/",
            )
        )
    for folder in folders:
        if not can_view_all and folder.deleted_by != hub.username and folder.owner_id != hub.user_id:
            continue
        days = retention
        if folder.deleted_at:
            elapsed = (now - folder.deleted_at).days
            days = max(0, retention - elapsed)
        items.append(
            schemas.RecycleItem(
                id=folder.id,
                name=folder.name,
                item_type="folder",
                deleted_at=folder.deleted_at,
                deleted_by=folder.deleted_by,
                days_remaining=days,
                original_location=folder.path,
            )
        )
    return items


@router.post("/recycle/{item_type}/{item_id}/restore")
def restore_item(
    item_type: str,
    item_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    if item_type == "file":
        record = db.query(models.VaultFile).filter_by(id=item_id, org_id=hub.org_id, is_deleted=True).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Item not found")
        crud.restore_file(db, record)
    elif item_type == "folder":
        folder = db.query(models.VaultFolder).filter_by(id=item_id, org_id=hub.org_id, is_deleted=True).first()
        if folder is None:
            raise HTTPException(status_code=404, detail="Item not found")
        crud.restore_folder(db, folder)
    else:
        raise HTTPException(status_code=400, detail="Invalid item type")
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="recycle.restore",
        item_type=item_type,
        item_id=item_id,
    )
    return {"message": "restored"}


@router.delete("/recycle/{item_type}/{item_id}")
def purge_item(
    item_type: str,
    item_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("recycle.purge")
    if item_type == "file":
        record = db.query(models.VaultFile).filter_by(id=item_id, org_id=hub.org_id, is_deleted=True).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Item not found")
        storage.permanently_delete(record.storage_path)
        db.delete(record)
        db.commit()
    elif item_type == "folder":
        folder = db.query(models.VaultFolder).filter_by(id=item_id, org_id=hub.org_id, is_deleted=True).first()
        if folder is None:
            raise HTTPException(status_code=404, detail="Item not found")
        db.delete(folder)
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="Invalid item type")
    return {"message": "purged"}


@router.get("/search", response_model=list[schemas.SearchHit])
def search_library(
    q: str = "",
    kind: str | None = None,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("search.use")
    hits = crud.search_library(db, hub.org_id, q, kind)
    return [schemas.SearchHit(**h) for h in hits]
