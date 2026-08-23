"""Seed default org, users, folders, and sample documents for Power Hub."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from database import models as db_models
from powerhub import crud, models, storage

logger = logging.getLogger(__name__)

ORG_ID = "aya-collective"
SAMPLE_README = """# Welcome to Power Hub

Power Hub is your organization's secure home for files and folders.
Upload documents, organize them into libraries, share with colleagues,
and create search indexes that sync with power-hub-search.

## Getting started
1. Browse My Files in the left rail
2. Create folders and upload documents
3. Open Search Indexes to build a searchable index of this vault
"""


def seed_powerhub(db: Session) -> None:
    org = (
        db.query(db_models.Organization)
        .filter(db_models.Organization.organization_id == ORG_ID)
        .first()
    )
    if org is None:
        org = db_models.Organization(
            name="AYA Collective",
            description="Power Hub demo organization",
            contact_name="Vault Admin",
            contact_email="admin@aya.collective",
            organization_id=ORG_ID,
            organization_type="enterprise",
        )
        db.add(org)
        db.commit()

    users = [
        {
            "full_name": "Super User",
            "username": "superuser",
            "password": "SuperUser!23",
            "email": "superuser@aya.collective",
            "role": "superuser",
            "user_id": "user-super",
        },
        {
            "full_name": "Vault Admin",
            "username": "admin",
            "password": "Admin!23",
            "email": "admin@aya.collective",
            "role": "admin",
            "user_id": "user-admin",
        },
        {
            "full_name": "Maya Manager",
            "username": "maya",
            "password": "Manager!23",
            "email": "maya@aya.collective",
            "role": "manager",
            "user_id": "user-maya",
        },
        {
            "full_name": "Noah Member",
            "username": "noah",
            "password": "Member!23",
            "email": "noah@aya.collective",
            "role": "member",
            "user_id": "user-noah",
        },
    ]
    for spec in users:
        existing = (
            db.query(db_models.User)
            .filter(db_models.User.username == spec["username"])
            .first()
        )
        if existing is None:
            db.add(
                db_models.User(
                    full_name=spec["full_name"],
                    username=spec["username"],
                    password=spec["password"],
                    email=spec["email"],
                    organization_id=ORG_ID,
                    role=spec["role"],
                    is_active=1,
                    user_id=spec["user_id"],
                )
            )
    db.commit()

    crud.ensure_settings(db, ORG_ID)

    # Seed sample library once
    existing_files = (
        db.query(models.VaultFile)
        .filter(models.VaultFile.org_id == ORG_ID)
        .count()
    )
    if existing_files == 0:
        policies = crud.create_folder(
            db,
            org_id=ORG_ID,
            owner_id="user-admin",
            name="Policies",
            parent_id=None,
        )
        projects = crud.create_folder(
            db,
            org_id=ORG_ID,
            owner_id="user-maya",
            name="Projects",
            parent_id=None,
        )
        onboard = crud.create_folder(
            db,
            org_id=ORG_ID,
            owner_id="user-maya",
            name="Onboarding",
            parent_id=projects.id,
        )
        for folder, name, body, owner in [
            (
                None,
                "README.md",
                SAMPLE_README.encode("utf-8"),
                "user-admin",
            ),
            (
                policies.id,
                "acceptable-use.txt",
                b"Acceptable Use Policy\n\nUse Power Hub for official work documents only.\n",
                "user-admin",
            ),
            (
                onboard.id,
                "new-hire-checklist.txt",
                b"New hire checklist\n- Complete profile\n- Join Groups\n- Review Policies\n",
                "user-maya",
            ),
        ]:
            crud.upload_file(
                db,
                org_id=ORG_ID,
                owner_id=owner,
                folder_id=folder,
                filename=name,
                data=body,
            )
        crud.log_audit(
            db,
            org_id=ORG_ID,
            actor="system",
            action="seed",
            detail="Seeded Power Hub sample library",
        )
        logger.info("Power Hub sample library seeded")

    # Default group
    if db.query(models.VaultGroup).filter_by(org_id=ORG_ID).count() == 0:
        group = models.VaultGroup(
            id=storage.new_id(),
            name="All Staff",
            description="Everyone in AYA Collective",
            org_id=ORG_ID,
            created_by="user-admin",
        )
        db.add(group)
        for uid in ("user-admin", "user-maya", "user-noah", "user-super"):
            db.add(
                models.VaultGroupMember(
                    id=storage.new_id(),
                    group_id=group.id,
                    user_id=uid,
                )
            )
        db.commit()
