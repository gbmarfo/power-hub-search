"""Power Hub authentication, profile, and dashboard routes."""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.authentication import create_access_token
from database.database import get_db
from database import models as db_models
from powerhub import crud, models, schemas
from powerhub.capabilities import capabilities_for
from powerhub.deps import HubUser, get_hub_user

router = APIRouter()

# In-memory email codes for passwordless demo (expires after 15 minutes)
_EMAIL_CODES: dict[str, dict] = {}


def _public_domains() -> set[str]:
    return {
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com",
        "aol.com",
        "proton.me",
        "mail.com",
    }


def _domain_allowed(db: Session, org_id: str, email: str) -> bool:
    settings = crud.ensure_settings(db, org_id)
    domain = email.split("@")[-1].lower()
    allowed = {d.strip().lower() for d in (settings.allowed_domains or "").split(",") if d.strip()}
    if domain in allowed:
        return True
    if settings.allow_public_email and domain in _public_domains():
        return True
    return False


@router.post("/auth/password", response_model=schemas.TokenResponse)
def login_with_password(body: schemas.LoginPasswordRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, body.email) or crud.get_user_by_username(db, body.email)
    if user is None or user.password != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Contact your administrator.")
    token = create_access_token(data={"sub": user.username})
    crud.log_audit(db, org_id=user.organization_id or "aya-collective", actor=user.username, action="sign_in")
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut(**crud.user_to_out(user)))


@router.post("/auth/email/request")
def request_email_code(body: schemas.LoginEmailRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid work email")

    user = crud.get_user_by_email(db, email)
    org_id = user.organization_id if user else "aya-collective"
    settings = crud.ensure_settings(db, org_id)

    if user and not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Contact your administrator.")

    if user is None:
        domain = email.split("@")[-1]
        if not _domain_allowed(db, org_id, email):
            raise HTTPException(
                status_code=403,
                detail="Email domain is not allowed. Ask an admin for an invitation.",
            )
        # Auto-provision member
        username = email.split("@")[0]
        base = username
        i = 1
        while crud.get_user_by_username(db, username):
            username = f"{base}{i}"
            i += 1
        from powerhub import storage

        user = db_models.User(
            full_name="",
            username=username,
            password="",
            email=email,
            organization_id=org_id,
            role="member",
            is_active=1,
            user_id=storage.new_id(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    code = "".join(random.choices(string.digits, k=6))
    _EMAIL_CODES[email] = {
        "code": code,
        "attempts": 0,
        "expires": datetime.utcnow() + timedelta(minutes=15),
        "username": user.username,
    }
    # Demo mode: return code in response (no SMTP required)
    return {
        "message": "Sign-in code sent",
        "email": email,
        "expires_in_minutes": 15,
        "demo_code": code,
        "demo_link": f"/hub/login?email={email}&code={code}",
    }


@router.post("/auth/email/verify", response_model=schemas.TokenResponse)
def verify_email_code(body: schemas.VerifyCodeRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    entry = _EMAIL_CODES.get(email)
    if entry is None:
        raise HTTPException(status_code=400, detail="No active code for this email. Request a new one.")
    if datetime.utcnow() > entry["expires"]:
        _EMAIL_CODES.pop(email, None)
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if entry["attempts"] >= 5:
        _EMAIL_CODES.pop(email, None)
        raise HTTPException(status_code=400, detail="Too many attempts. Request a new code.")
    if body.code.strip() != entry["code"]:
        entry["attempts"] += 1
        raise HTTPException(status_code=401, detail="Invalid code")
    _EMAIL_CODES.pop(email, None)
    user = crud.get_user_by_username(db, entry["username"])
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_access_token(data={"sub": user.username})
    crud.log_audit(db, org_id=user.organization_id or "aya-collective", actor=user.username, action="sign_in")
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut(**crud.user_to_out(user)))


@router.get("/me", response_model=schemas.UserOut)
def me(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    user = crud.get_user_by_id(db, hub.user_id)
    return schemas.UserOut(**crud.user_to_out(user))


@router.patch("/me", response_model=schemas.UserOut)
def update_profile(
    body: schemas.ProfileUpdate,
    hub: HubUser = Depends(get_hub_user),
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_id(db, hub.user_id)
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.password:
        user.password = body.password
    db.commit()
    db.refresh(user)
    return schemas.UserOut(**crud.user_to_out(user))


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    recent = (
        db.query(models.VaultFile)
        .filter(
            models.VaultFile.org_id == hub.org_id,
            models.VaultFile.is_deleted.is_(False),
            models.VaultFile.modified_by == hub.user_id,
        )
        .order_by(models.VaultFile.updated_at.desc())
        .limit(8)
        .all()
    )
    if not recent:
        recent = (
            db.query(models.VaultFile)
            .filter(
                models.VaultFile.org_id == hub.org_id,
                models.VaultFile.is_deleted.is_(False),
            )
            .order_by(models.VaultFile.updated_at.desc())
            .limit(8)
            .all()
        )

    activity = (
        db.query(models.VaultActivity)
        .filter(models.VaultActivity.org_id == hub.org_id)
        .order_by(models.VaultActivity.created_at.desc())
        .limit(12)
        .all()
    )
    file_count = (
        db.query(func.count(models.VaultFile.id))
        .filter(models.VaultFile.org_id == hub.org_id, models.VaultFile.is_deleted.is_(False))
        .scalar()
    )
    folder_count = (
        db.query(func.count(models.VaultFolder.id))
        .filter(models.VaultFolder.org_id == hub.org_id, models.VaultFolder.is_deleted.is_(False))
        .scalar()
    )
    share_count = (
        db.query(func.count(models.VaultShare.id))
        .filter(models.VaultShare.org_id == hub.org_id, models.VaultShare.is_active.is_(True))
        .scalar()
    )
    user_count = (
        db.query(func.count(db_models.User.id))
        .filter(db_models.User.organization_id == hub.org_id, db_models.User.is_active == 1)
        .scalar()
    )
    settings = crud.ensure_settings(db, hub.org_id)
    used = crud.storage_used(db, hub.org_id)

    # Simple legends from activity counts
    legends_raw = (
        db.query(models.VaultActivity.actor, func.count(models.VaultActivity.id))
        .filter(models.VaultActivity.org_id == hub.org_id)
        .group_by(models.VaultActivity.actor)
        .order_by(func.count(models.VaultActivity.id).desc())
        .limit(5)
        .all()
    )

    continue_working = [
        schemas.FileOut(
            id=f.id,
            name=f.name,
            folder_id=f.folder_id,
            mime_type=f.mime_type,
            extension=f.extension,
            size_bytes=f.size_bytes,
            starred=bool(f.starred),
            version=f.version,
            owner_id=f.owner_id,
            modified_by=f.modified_by,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in recent
    ]

    return schemas.DashboardOut(
        continue_working=continue_working,
        team_activity=[
            {
                "id": a.id,
                "actor": a.actor,
                "action": a.action,
                "item_name": a.item_name,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activity
        ],
        online_users=[{"username": hub.username, "full_name": hub.full_name or hub.username}],
        vault_legends=[{"actor": a, "score": int(c)} for a, c in legends_raw],
        stats={
            "files": int(file_count or 0),
            "folders": int(folder_count or 0),
            "shares": int(share_count or 0),
            "users": int(user_count or 0),
        },
        storage={
            "used_bytes": used,
            "quota_bytes": settings.storage_quota_bytes,
        },
    )


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def list_notifications(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    notes = (
        db.query(models.VaultNotification)
        .filter(models.VaultNotification.user_id == hub.user_id)
        .order_by(models.VaultNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        schemas.NotificationOut(
            id=n.id,
            kind=n.kind,
            title=n.title,
            body=n.body,
            is_read=bool(n.is_read),
            created_at=n.created_at,
        )
        for n in notes
    ]


@router.post("/notifications/read-all")
def mark_notifications_read(hub: HubUser = Depends(get_hub_user), db: Session = Depends(get_db)):
    db.query(models.VaultNotification).filter(
        models.VaultNotification.user_id == hub.user_id,
        models.VaultNotification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"message": "ok"}
