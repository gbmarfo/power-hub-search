"""Shared auth dependency for Power Hub routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.authentication import get_current_user
from database.database import get_db
from powerhub import crud
from powerhub.capabilities import has_capability, normalize_role


@dataclass
class HubUser:
    username: str
    user_id: str
    email: str | None
    full_name: str | None
    org_id: str
    role: str

    def require(self, capability: str) -> None:
        if not has_capability(self.role, capability):
            raise HTTPException(status_code=403, detail=f"Missing capability: {capability}")


def get_hub_user(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HubUser:
    user = crud.get_user_by_username(db, current_user)
    if user is None:
        # Allow JWT subject to match email for passwordless path
        user = crud.get_user_by_email(db, current_user)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Contact your administrator.")
    return HubUser(
        username=user.username,
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        org_id=user.organization_id or "aya-collective",
        role=normalize_role(user.role),
    )
