"""Sharing links, access grants, and public share preview."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.database import get_db
from powerhub import crud, models, schemas, storage
from powerhub.deps import HubUser, get_hub_user

router = APIRouter()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@router.post("/shares", response_model=schemas.ShareOut)
def create_share(
    body: schemas.ShareCreate,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("sharing.create")
    if body.item_type == "file":
        item = db.query(models.VaultFile).filter_by(id=body.item_id, org_id=hub.org_id, is_deleted=False).first()
    else:
        item = db.query(models.VaultFolder).filter_by(id=body.item_id, org_id=hub.org_id, is_deleted=False).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    token = secrets.token_urlsafe(18)
    share = models.VaultShare(
        id=storage.new_id(),
        token=token,
        item_type=body.item_type,
        item_id=body.item_id,
        org_id=hub.org_id,
        created_by=hub.user_id,
        role=body.role,
        password_hash=_hash_password(body.password) if body.password else None,
        expires_at=body.expires_at,
        download_limit=body.download_limit,
        notify=body.notify,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="share.create",
        item_type=body.item_type,
        item_id=body.item_id,
        detail=getattr(item, "name", None),
    )
    return schemas.ShareOut(
        id=share.id,
        token=share.token,
        item_type=share.item_type,
        item_id=share.item_id,
        role=share.role,
        created_by=share.created_by,
        expires_at=share.expires_at,
        download_limit=share.download_limit,
        download_count=share.download_count,
        is_active=bool(share.is_active),
        created_at=share.created_at,
        url=f"/hub/s/{share.token}",
        item_name=getattr(item, "name", None),
    )


@router.get("/shares", response_model=list[schemas.ShareOut])
def list_shares(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.VaultShare).filter(models.VaultShare.org_id == hub.org_id)
    if scope == "mine" or hub.role not in {"admin", "superuser"}:
        query = query.filter(models.VaultShare.created_by == hub.user_id)
    shares = query.order_by(models.VaultShare.created_at.desc()).all()
    results = []
    for share in shares:
        name = None
        if share.item_type == "file":
            item = db.query(models.VaultFile).filter_by(id=share.item_id).first()
            name = item.name if item else None
        else:
            item = db.query(models.VaultFolder).filter_by(id=share.item_id).first()
            name = item.name if item else None
        results.append(
            schemas.ShareOut(
                id=share.id,
                token=share.token,
                item_type=share.item_type,
                item_id=share.item_id,
                role=share.role,
                created_by=share.created_by,
                expires_at=share.expires_at,
                download_limit=share.download_limit,
                download_count=share.download_count or 0,
                is_active=bool(share.is_active),
                created_at=share.created_at,
                url=f"/hub/s/{share.token}",
                item_name=name,
            )
        )
    return results


@router.delete("/shares/{share_id}")
def revoke_share(
    share_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    share = db.query(models.VaultShare).filter_by(id=share_id, org_id=hub.org_id).first()
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")
    if share.created_by != hub.user_id:
        hub.require("sharing.manage")
    share.is_active = False
    db.commit()
    return {"message": "revoked"}


@router.post("/access", response_model=schemas.AccessOut)
def grant_access(
    body: schemas.AccessGrantCreate,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("sharing.create")
    grant = models.VaultAccess(
        id=storage.new_id(),
        item_type=body.item_type,
        item_id=body.item_id,
        grantee_type=body.grantee_type,
        grantee_id=body.grantee_id,
        role=body.role,
        granted_by=hub.user_id,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    if body.notify and body.grantee_type == "user":
        crud.notify(
            db,
            user_id=body.grantee_id,
            org_id=hub.org_id,
            kind="access",
            title="You were granted access",
            body=f"{hub.full_name or hub.username} shared an item with you as {body.role}",
        )
    return schemas.AccessOut(
        id=grant.id,
        item_type=grant.item_type,
        item_id=grant.item_id,
        grantee_type=grant.grantee_type,
        grantee_id=grant.grantee_id,
        role=grant.role,
        granted_by=grant.granted_by,
        grantee_label=body.grantee_id,
    )


@router.get("/access/{item_type}/{item_id}", response_model=list[schemas.AccessOut])
def list_access(
    item_type: str,
    item_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    grants = (
        db.query(models.VaultAccess)
        .filter_by(item_type=item_type, item_id=item_id)
        .all()
    )
    results = []
    for grant in grants:
        label = grant.grantee_id
        if grant.grantee_type == "user":
            user = crud.get_user_by_id(db, grant.grantee_id)
            if user:
                label = user.full_name or user.email or user.username
        else:
            group = db.query(models.VaultGroup).filter_by(id=grant.grantee_id).first()
            if group:
                label = group.name
        results.append(
            schemas.AccessOut(
                id=grant.id,
                item_type=grant.item_type,
                item_id=grant.item_id,
                grantee_type=grant.grantee_type,
                grantee_id=grant.grantee_id,
                role=grant.role,
                granted_by=grant.granted_by,
                grantee_label=label,
            )
        )
    return results


@router.delete("/access/{access_id}")
def revoke_access(
    access_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    grant = db.query(models.VaultAccess).filter_by(id=access_id).first()
    if grant is None:
        raise HTTPException(status_code=404, detail="Access grant not found")
    db.delete(grant)
    db.commit()
    return {"message": "removed"}


@router.get("/public/share/{token}")
def public_share_meta(token: str, db: Session = Depends(get_db)):
    share = db.query(models.VaultShare).filter_by(token=token, is_active=True).first()
    if share is None:
        raise HTTPException(status_code=404, detail="Share link not found or revoked")
    if share.expires_at and datetime.utcnow() > share.expires_at:
        raise HTTPException(status_code=410, detail="Share link expired")
    if share.download_limit is not None and (share.download_count or 0) >= share.download_limit:
        raise HTTPException(status_code=410, detail="Download limit reached")

    name = None
    mime = None
    size = None
    if share.item_type == "file":
        item = db.query(models.VaultFile).filter_by(id=share.item_id, is_deleted=False).first()
        if item is None:
            raise HTTPException(status_code=404, detail="Shared file missing")
        name, mime, size = item.name, item.mime_type, item.size_bytes
    else:
        item = db.query(models.VaultFolder).filter_by(id=share.item_id, is_deleted=False).first()
        if item is None:
            raise HTTPException(status_code=404, detail="Shared folder missing")
        name = item.name

    return {
        "token": token,
        "item_type": share.item_type,
        "name": name,
        "mime_type": mime,
        "size_bytes": size,
        "role": share.role,
        "password_required": bool(share.password_hash),
        "can_download": share.item_type == "file",
    }


@router.get("/public/share/{token}/download")
def public_share_download(
    token: str,
    password: str | None = None,
    db: Session = Depends(get_db),
):
    share = db.query(models.VaultShare).filter_by(token=token, is_active=True).first()
    if share is None or share.item_type != "file":
        raise HTTPException(status_code=404, detail="Share not found")
    if share.password_hash:
        if not password or _hash_password(password) != share.password_hash:
            raise HTTPException(status_code=401, detail="Password required")
    if share.expires_at and datetime.utcnow() > share.expires_at:
        raise HTTPException(status_code=410, detail="Share link expired")
    if share.download_limit is not None and (share.download_count or 0) >= share.download_limit:
        raise HTTPException(status_code=410, detail="Download limit reached")

    item = db.query(models.VaultFile).filter_by(id=share.item_id, is_deleted=False).first()
    if item is None or not Path(item.storage_path).exists():
        raise HTTPException(status_code=404, detail="File missing")
    share.download_count = (share.download_count or 0) + 1
    db.commit()
    return FileResponse(item.storage_path, filename=item.name, media_type=item.mime_type)
