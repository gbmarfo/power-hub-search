"""Power Hub SQLAlchemy models — files, folders, shares, recycle bin, audit."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database.database import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class VaultFolder(Base):
    __tablename__ = "powerhub_folder"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey("powerhub_folder.id"), nullable=True)
    org_id = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False, default="/")
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    original_parent_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class VaultFile(Base):
    __tablename__ = "powerhub_file"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    folder_id = Column(String, ForeignKey("powerhub_folder.id"), nullable=True)
    org_id = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)
    storage_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    extension = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    content_text = Column(Text, nullable=True)
    starred = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    original_folder_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    modified_by = Column(String, nullable=True)


class VaultShare(Base):
    __tablename__ = "powerhub_share"

    id = Column(String, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    item_type = Column(String, nullable=False)  # file | folder
    item_id = Column(String, nullable=False, index=True)
    org_id = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    role = Column(String, default="viewer")  # viewer | editor | full_control
    password_hash = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    download_limit = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0)
    notify = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)


class VaultAccess(Base):
    """Internal people/group access grants (distinct from share links)."""

    __tablename__ = "powerhub_access"

    id = Column(String, primary_key=True)
    item_type = Column(String, nullable=False)
    item_id = Column(String, nullable=False, index=True)
    grantee_type = Column(String, nullable=False)  # user | group
    grantee_id = Column(String, nullable=False)
    role = Column(String, default="viewer")
    granted_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class VaultGroup(Base):
    __tablename__ = "powerhub_group"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    org_id = Column(String, nullable=False, index=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class VaultGroupMember(Base):
    __tablename__ = "powerhub_group_member"

    id = Column(String, primary_key=True)
    group_id = Column(String, ForeignKey("powerhub_group.id"), nullable=False)
    user_id = Column(String, nullable=False)
    added_at = Column(DateTime, default=_utcnow)


class VaultAuditEvent(Base):
    __tablename__ = "powerhub_audit"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False, index=True)
    item_type = Column(String, nullable=True)
    item_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)


class VaultNotification(Base):
    __tablename__ = "powerhub_notification"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    org_id = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # mention | access | expiry
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)


class VaultSettings(Base):
    __tablename__ = "powerhub_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String, unique=True, nullable=False)
    allowed_domains = Column(Text, default="aya.collective")
    allow_public_email = Column(Boolean, default=False)
    recycle_retention_days = Column(Integer, default=30)
    storage_quota_bytes = Column(Integer, default=10 * 1024 * 1024 * 1024)


class VaultSearchIndexLink(Base):
    """Maps a Power Hub library/folder to a power-hub-search index."""

    __tablename__ = "powerhub_search_index_link"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    folder_id = Column(String, nullable=True)  # None = entire org vault
    search_index_id = Column(String, nullable=False, index=True)
    created_by = Column(String, nullable=False)
    document_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class VaultActivity(Base):
    __tablename__ = "powerhub_activity"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    item_name = Column(String, nullable=True)
    item_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
