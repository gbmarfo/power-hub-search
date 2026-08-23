"""Capability matrix and role helpers for Power Hub."""

from __future__ import annotations

ROLE_CAPABILITIES: dict[str, list[str]] = {
    "member": [
        "files.view",
        "files.upload",
        "files.download",
        "files.rename",
        "files.delete_own",
        "folders.create",
        "folders.view",
        "sharing.create",
        "sharing.manage_own",
        "recycle.view_own",
        "recycle.restore_own",
        "search.use",
        "indexes.view",
        "indexes.create",
        "profile.edit",
    ],
    "manager": [
        "files.view",
        "files.upload",
        "files.download",
        "files.rename",
        "files.move",
        "files.delete_own",
        "folders.create",
        "folders.view",
        "sharing.create",
        "sharing.manage_own",
        "recycle.view_own",
        "recycle.restore_own",
        "search.use",
        "indexes.view",
        "indexes.create",
        "indexes.delete",
        "groups.view",
        "groups.manage",
        "invitations.create",
        "profile.edit",
        "audit.view",
    ],
    "admin": [
        "files.view",
        "files.upload",
        "files.download",
        "files.rename",
        "files.move",
        "files.delete",
        "folders.create",
        "folders.view",
        "sharing.create",
        "sharing.manage",
        "recycle.view",
        "recycle.restore",
        "recycle.purge",
        "search.use",
        "indexes.view",
        "indexes.create",
        "indexes.delete",
        "groups.view",
        "groups.manage",
        "users.manage",
        "settings.manage",
        "invitations.create",
        "audit.view",
        "permissions.manage",
        "profile.edit",
    ],
    "superuser": [
        "files.view",
        "files.upload",
        "files.download",
        "files.rename",
        "files.move",
        "files.delete",
        "folders.create",
        "folders.view",
        "sharing.create",
        "sharing.manage",
        "recycle.view",
        "recycle.restore",
        "recycle.purge",
        "search.use",
        "indexes.view",
        "indexes.create",
        "indexes.delete",
        "groups.view",
        "groups.manage",
        "users.manage",
        "settings.manage",
        "invitations.create",
        "audit.view",
        "permissions.manage",
        "admins.manage",
        "profile.edit",
    ],
}


def normalize_role(role: str | None) -> str:
    if not role:
        return "member"
    key = role.strip().lower().replace(" ", "").replace("_", "")
    mapping = {
        "member": "member",
        "manager": "manager",
        "admin": "admin",
        "superuser": "superuser",
        "super": "superuser",
    }
    return mapping.get(key, "member")


def capabilities_for(role: str | None) -> list[str]:
    return list(ROLE_CAPABILITIES.get(normalize_role(role), ROLE_CAPABILITIES["member"]))


def has_capability(role: str | None, capability: str) -> bool:
    return capability in capabilities_for(role)
