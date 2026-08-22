"""Local filesystem storage for Power Hub vault files."""

from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from pathlib import Path

import config


def vault_root() -> Path:
    root = Path(getattr(config, "POWERHUB_STORAGE_PATH", "./data/powerhub/files"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def recycle_root() -> Path:
    root = Path(getattr(config, "POWERHUB_STORAGE_PATH", "./data/powerhub/files")).parent / "recycle"
    root.mkdir(parents=True, exist_ok=True)
    return root


def guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def save_upload(org_id: str, file_id: str, filename: str, data: bytes) -> str:
    org_dir = vault_root() / org_id
    org_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{file_id}_{Path(filename).name}"
    path = org_dir / safe_name
    path.write_bytes(data)
    return str(path)


def move_to_recycle(storage_path: str, file_id: str) -> str:
    src = Path(storage_path)
    dest = recycle_root() / f"{file_id}_{src.name}"
    if src.exists():
        shutil.move(str(src), str(dest))
        return str(dest)
    return storage_path


def restore_from_recycle(storage_path: str, org_id: str, file_id: str, filename: str) -> str:
    src = Path(storage_path)
    dest_dir = vault_root() / org_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{file_id}_{Path(filename).name}"
    if src.exists():
        shutil.move(str(src), str(dest))
        return str(dest)
    return storage_path


def permanently_delete(storage_path: str) -> None:
    path = Path(storage_path)
    if path.exists() and path.is_file():
        path.unlink()


def extract_text(filename: str, data: bytes) -> str:
    """Best-effort text extraction for search indexing."""
    ext = extension_of(filename)
    if ext in {"txt", "md", "csv", "json", "log", "py", "js", "ts", "html", "css", "xml"}:
        try:
            return data.decode("utf-8", errors="ignore")[:200_000]
        except Exception:
            return ""
    if ext == "pdf":
        try:
            from io import BytesIO

            from PyPDF2 import PdfReader

            reader = PdfReader(BytesIO(data))
            parts: list[str] = []
            for page in reader.pages[:50]:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)[:200_000]
        except Exception:
            return ""
    return ""


def new_id() -> str:
    return str(uuid.uuid4())
