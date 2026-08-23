"""Pydantic schemas for Power Hub API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginPasswordRequest(BaseModel):
    email: str
    password: str


class LoginEmailRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = None


class UserOut(BaseModel):
    user_id: str
    username: str
    full_name: str | None = None
    email: str | None = None
    organization_id: str | None = None
    role: str | None = None
    is_active: int | None = None
    capabilities: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class FolderCreate(BaseModel):
    name: str
    parent_id: str | None = None


class FolderOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    path: str
    owner_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    item_type: Literal["folder"] = "folder"


class FileOut(BaseModel):
    id: str
    name: str
    folder_id: str | None
    mime_type: str | None = None
    extension: str | None = None
    size_bytes: int = 0
    starred: bool = False
    version: int = 1
    owner_id: str
    modified_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    path: str | None = None
    item_type: Literal["file"] = "file"


class RenameRequest(BaseModel):
    name: str


class MoveRequest(BaseModel):
    target_folder_id: str | None = None


class LibraryListing(BaseModel):
    folder: FolderOut | None = None
    breadcrumbs: list[FolderOut] = Field(default_factory=list)
    folders: list[FolderOut] = Field(default_factory=list)
    files: list[FileOut] = Field(default_factory=list)


class ShareCreate(BaseModel):
    item_type: Literal["file", "folder"]
    item_id: str
    role: Literal["viewer", "editor", "full_control"] = "viewer"
    password: str | None = None
    expires_at: datetime | None = None
    download_limit: int | None = None
    notify: bool = False


class AccessGrantCreate(BaseModel):
    item_type: Literal["file", "folder"]
    item_id: str
    grantee_type: Literal["user", "group"]
    grantee_id: str
    role: Literal["viewer", "editor", "full_control"] = "viewer"
    notify: bool = True


class ShareOut(BaseModel):
    id: str
    token: str
    item_type: str
    item_id: str
    role: str
    created_by: str
    expires_at: datetime | None = None
    download_limit: int | None = None
    download_count: int = 0
    is_active: bool = True
    created_at: datetime | None = None
    url: str | None = None
    item_name: str | None = None


class AccessOut(BaseModel):
    id: str
    item_type: str
    item_id: str
    grantee_type: str
    grantee_id: str
    role: str
    granted_by: str
    grantee_label: str | None = None


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    member_count: int = 0
    created_by: str


class SettingsUpdate(BaseModel):
    allowed_domains: str | None = None
    allow_public_email: bool | None = None
    recycle_retention_days: int | None = None


class SettingsOut(BaseModel):
    org_id: str
    allowed_domains: str
    allow_public_email: bool
    recycle_retention_days: int
    storage_quota_bytes: int
    storage_used_bytes: int = 0


class RecycleItem(BaseModel):
    id: str
    name: str
    item_type: Literal["file", "folder"]
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    days_remaining: int | None = None
    original_location: str | None = None


class AuditOut(BaseModel):
    id: str
    actor: str
    action: str
    item_type: str | None = None
    item_id: str | None = None
    detail: str | None = None
    created_at: datetime | None = None


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str | None = None
    is_read: bool
    created_at: datetime | None = None


class SearchHit(BaseModel):
    id: str
    name: str
    item_type: Literal["file", "folder"]
    path: str | None = None
    extension: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None


class DashboardOut(BaseModel):
    continue_working: list[FileOut] = Field(default_factory=list)
    team_activity: list[dict] = Field(default_factory=list)
    online_users: list[dict] = Field(default_factory=list)
    vault_legends: list[dict] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)
    storage: dict = Field(default_factory=dict)


class SearchIndexCreateRequest(BaseModel):
    title: str
    description: str | None = None
    folder_id: str  # required — index files from this vault folder (and subfolders)


class SearchIndexIntegrationOut(BaseModel):
    search_index_id: str
    source: str = "powerhub"
    table_name: str = "powerhub_search_docs"
    registered: bool = True
    text_index_ready: bool = False
    vector_index: dict = Field(default_factory=dict)
    admin_search_url: str
    admin_index_url: str
    api_search_url: str
    powerhub_search_url: str


class SearchIndexLinkOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    folder_id: str | None = None
    folder_name: str | None = None
    folder_path: str | None = None
    search_index_id: str
    document_count: int = 0
    created_by: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    integration: SearchIndexIntegrationOut | None = None


class FolderIndexOption(BaseModel):
    id: str
    name: str
    path: str
    file_count: int = 0


class InvitationCreate(BaseModel):
    email: str
    role: Literal["member", "manager", "admin"] = "member"


TokenResponse.model_rebuild()
