"""Admin, groups, settings, audit, and search-index management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.database import get_db
from database import models as db_models
from powerhub import crud, models, schemas, search_bridge, storage
from powerhub.capabilities import capabilities_for, normalize_role
from powerhub.deps import HubUser, get_hub_user
from database import schemas as search_schemas

router = APIRouter()


@router.get("/settings", response_model=schemas.SettingsOut)
def get_settings(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    settings = crud.ensure_settings(db, hub.org_id)
    return schemas.SettingsOut(
        org_id=settings.org_id,
        allowed_domains=settings.allowed_domains or "",
        allow_public_email=bool(settings.allow_public_email),
        recycle_retention_days=settings.recycle_retention_days or 30,
        storage_quota_bytes=settings.storage_quota_bytes or 0,
        storage_used_bytes=crud.storage_used(db, hub.org_id),
    )


@router.patch("/settings", response_model=schemas.SettingsOut)
def update_settings(
    body: schemas.SettingsUpdate,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("settings.manage")
    settings = crud.ensure_settings(db, hub.org_id)
    if body.allowed_domains is not None:
        settings.allowed_domains = body.allowed_domains
    if body.allow_public_email is not None:
        settings.allow_public_email = body.allow_public_email
    if body.recycle_retention_days is not None:
        settings.recycle_retention_days = body.recycle_retention_days
    db.commit()
    db.refresh(settings)
    return schemas.SettingsOut(
        org_id=settings.org_id,
        allowed_domains=settings.allowed_domains or "",
        allow_public_email=bool(settings.allow_public_email),
        recycle_retention_days=settings.recycle_retention_days or 30,
        storage_quota_bytes=settings.storage_quota_bytes or 0,
        storage_used_bytes=crud.storage_used(db, hub.org_id),
    )


@router.get("/users")
def list_users(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    hub.require("users.manage")
    users = (
        db.query(db_models.User)
        .filter(db_models.User.organization_id == hub.org_id)
        .order_by(db_models.User.full_name)
        .all()
    )
    return {
        "results": [crud.user_to_out(u) for u in users],
        "count": len(users),
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    role: str | None = None,
    is_active: int | None = None,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("users.manage")
    user = crud.get_user_by_id(db, user_id)
    if user is None or user.organization_id != hub.org_id:
        raise HTTPException(status_code=404, detail="User not found")
    if normalize_role(user.role) == "superuser" and hub.role != "superuser":
        raise HTTPException(status_code=403, detail="Cannot modify Super User")
    if role is not None:
        new_role = normalize_role(role)
        if new_role == "admin" and hub.role != "superuser":
            hub.require("admins.manage")
        if new_role == "superuser" and hub.role != "superuser":
            raise HTTPException(status_code=403, detail="Only Super User can assign Super User")
        user.role = new_role
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    return crud.user_to_out(user)


@router.get("/audit", response_model=list[schemas.AuditOut])
def audit_log(
    action: str | None = None,
    actor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("audit.view")
    query = db.query(models.VaultAuditEvent).filter(models.VaultAuditEvent.org_id == hub.org_id)
    if action:
        query = query.filter(models.VaultAuditEvent.action == action)
    if actor:
        query = query.filter(models.VaultAuditEvent.actor == actor)
    events = query.order_by(models.VaultAuditEvent.created_at.desc()).limit(limit).all()
    return [
        schemas.AuditOut(
            id=e.id,
            actor=e.actor,
            action=e.action,
            item_type=e.item_type,
            item_id=e.item_id,
            detail=e.detail,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/groups", response_model=list[schemas.GroupOut])
def list_groups(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    hub.require("groups.view")
    groups = db.query(models.VaultGroup).filter_by(org_id=hub.org_id).all()
    results = []
    for group in groups:
        count = db.query(models.VaultGroupMember).filter_by(group_id=group.id).count()
        results.append(
            schemas.GroupOut(
                id=group.id,
                name=group.name,
                description=group.description,
                member_count=count,
                created_by=group.created_by,
            )
        )
    return results


@router.post("/groups", response_model=schemas.GroupOut)
def create_group(
    body: schemas.GroupCreate,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("groups.manage")
    group = models.VaultGroup(
        id=storage.new_id(),
        name=body.name,
        description=body.description,
        org_id=hub.org_id,
        created_by=hub.user_id,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return schemas.GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        member_count=0,
        created_by=group.created_by,
    )


@router.post("/groups/{group_id}/members/{user_id}")
def add_group_member(
    group_id: str,
    user_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("groups.manage")
    group = db.query(models.VaultGroup).filter_by(id=group_id, org_id=hub.org_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    exists = (
        db.query(models.VaultGroupMember)
        .filter_by(group_id=group_id, user_id=user_id)
        .first()
    )
    if exists is None:
        db.add(
            models.VaultGroupMember(
                id=storage.new_id(), group_id=group_id, user_id=user_id
            )
        )
        db.commit()
    return {"message": "added"}


@router.delete("/groups/{group_id}/members/{user_id}")
def remove_group_member(
    group_id: str,
    user_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("groups.manage")
    member = (
        db.query(models.VaultGroupMember)
        .filter_by(group_id=group_id, user_id=user_id)
        .first()
    )
    if member:
        db.delete(member)
        db.commit()
    return {"message": "removed"}


@router.get("/folders", response_model=list[schemas.FolderIndexOption])
def list_folders_for_indexing(
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    """List vault folders with file counts for search-index creation."""
    hub.require("folders.view")
    return [
        schemas.FolderIndexOption(**row)
        for row in crud.list_folders_with_counts(db, hub.org_id)
    ]


def _index_link_out(db: Session, link: models.VaultSearchIndexLink) -> schemas.SearchIndexLinkOut:
    folder_name = None
    folder_path = None
    if link.folder_id:
        folder = db.query(models.VaultFolder).filter_by(id=link.folder_id).first()
        if folder:
            folder_name = folder.name
            folder_path = folder.path or f"/{folder.name}"
    integration = search_bridge.get_index_integration_status(db, link)
    return schemas.SearchIndexLinkOut(
        id=link.id,
        title=link.title,
        description=link.description,
        folder_id=link.folder_id,
        folder_name=folder_name,
        folder_path=folder_path,
        search_index_id=link.search_index_id,
        document_count=link.document_count or 0,
        created_by=link.created_by,
        created_at=link.created_at,
        updated_at=link.updated_at,
        integration=schemas.SearchIndexIntegrationOut(**integration),
    )


def _enrich_search_results(
    db: Session, org_id: str, results: list[dict]
) -> list[dict]:
    enriched: list[dict] = []
    for hit in results:
        entry = dict(hit)
        file_id = str(hit.get("id", ""))
        if not file_id:
            enriched.append(entry)
            continue
        record = (
            db.query(models.VaultFile)
            .filter_by(id=file_id, org_id=org_id, is_deleted=False)
            .first()
        )
        if record is None:
            enriched.append(entry)
            continue
        folder = (
            db.query(models.VaultFolder).filter_by(id=record.folder_id).first()
            if record.folder_id
            else None
        )
        entry["name"] = record.name
        entry["path"] = crud.folder_path(db, folder)
        entry["extension"] = record.extension
        entry["file_id"] = record.id
        entry["download_url"] = f"/api/v1/powerhub/files/{record.id}/download"
        enriched.append(entry)
    return enriched


@router.get("/indexes", response_model=list[schemas.SearchIndexLinkOut])
def list_search_indexes(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    hub.require("indexes.view")
    links = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(org_id=hub.org_id)
        .order_by(models.VaultSearchIndexLink.created_at.desc())
        .all()
    )
    return [_index_link_out(db, link) for link in links]


@router.post("/indexes", response_model=schemas.SearchIndexLinkOut)
def create_search_index(
    body: schemas.SearchIndexCreateRequest,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("indexes.create")
    if not body.folder_id or not str(body.folder_id).strip():
        raise HTTPException(
            status_code=400,
            detail="folder_id is required. Select a vault folder whose files should be indexed.",
        )
    try:
        link = search_bridge.create_index_from_vault(
            db,
            org_id=hub.org_id,
            title=body.title,
            description=body.description,
            folder_id=body.folder_id,
            created_by=hub.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Index creation failed: {exc}") from exc

    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="index.create",
        item_type="search_index",
        item_id=link.search_index_id,
        detail=f"{link.title} ← {body.folder_id}",
    )
    return _index_link_out(db, link)


@router.get("/indexes/{link_id}", response_model=schemas.SearchIndexLinkOut)
def get_search_index(
    link_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("indexes.view")
    link = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(id=link_id, org_id=hub.org_id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Index link not found")
    return _index_link_out(db, link)


@router.post("/indexes/{link_id}/sync", response_model=schemas.SearchIndexLinkOut)
def sync_search_index(
    link_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    """Re-sync vault files into the registered power-hub-search index."""
    hub.require("indexes.create")
    link = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(id=link_id, org_id=hub.org_id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Index link not found")
    try:
        link = search_bridge.sync_index_from_vault(db, link)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Index sync failed: {exc}") from exc
    crud.log_audit(
        db,
        org_id=hub.org_id,
        actor=hub.username,
        action="index.sync",
        item_type="search_index",
        item_id=link.search_index_id,
        detail=link.title,
    )
    return _index_link_out(db, link)


@router.delete("/indexes/{link_id}")
def delete_search_index(
    link_id: str,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    hub.require("indexes.delete")
    link = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(id=link_id, org_id=hub.org_id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Index link not found")
    search_bridge.delete_index_link(db, link)
    return {"message": "deleted"}


@router.post("/indexes/{link_id}/search")
def search_via_power_hub_search(
    link_id: str,
    body: search_schemas.SearchRequest,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    """Proxy search to the power-hub-search index created from this vault."""
    hub.require("search.use")
    link = (
        db.query(models.VaultSearchIndexLink)
        .filter_by(id=link_id, org_id=hub.org_id)
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Index link not found")

    from routers.search_router import _run_search

    try:
        results = _run_search(
            index_id=link.search_index_id,
            query=body.query,
            mode=body.mode,
            top_k=body.top_k,
            offset=body.offset,
            org_id=hub.org_id,
            metadata_filters=body.metadata_filters,
            vector_weight=body.vector_weight,
        )
        if body.mode != search_schemas.SearchMode.similarity:
            results = results[body.offset : body.offset + body.top_k]
        results = _enrich_search_results(db, hub.org_id, results)
        return {
            "results": results,
            "mode": body.mode.value,
            "total_returned": len(results),
            "search_index_id": link.search_index_id,
            "integration": search_bridge.get_index_integration_status(db, link),
        }
    except Exception as exc:
        # Fall back to library name search if vector backend is down
        hits = crud.search_library(db, hub.org_id, body.query, None)
        return {
            "results": hits,
            "mode": "library_fallback",
            "total_returned": len(hits),
            "search_index_id": link.search_index_id,
            "warning": str(exc),
        }


@router.get("/capabilities")
def role_capabilities(hub: HubUser = Depends(get_hub_user)):
    return {
        "role": hub.role,
        "capabilities": capabilities_for(hub.role),
    }
