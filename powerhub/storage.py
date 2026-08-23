"""Local filesystem storage for Power Hub vault files."""

from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path

import config
from powerhub.document_parser import (
    ParseResult,
    parse_document,
    save_extracted_images,
)


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


def extract_document(filename: str, data: bytes, *, org_id: str | None = None, file_id: str | None = None) -> ParseResult:
    """Parse text, tables, figures, and images (with OCR) for search indexing."""
    ext = extension_of(filename)
    if ext in {"pdf", "docx", "doc"}:
        result = parse_document(filename, data)
        if org_id and file_id and result.images:
            try:
                save_extracted_images(org_id, file_id, result.images)
            except Exception:
                pass
        return result

    result = ParseResult()
    if ext in {"txt", "md", "csv", "json", "log", "py", "js", "ts", "html", "css", "xml"}:
        try:
            result.text = data.decode("utf-8", errors="ignore")[:400_000]
        except Exception:
            result.text = ""
    return result


def extract_text(
    filename: str,
    data: bytes,
    *,
    org_id: str | None = None,
    file_id: str | None = None,
) -> str:
    """Best-effort searchable text including tables/figures/image OCR for Office docs."""
    return extract_document(filename, data, org_id=org_id, file_id=file_id).as_search_text()


def reparse_stored_file(filename: str, storage_path: str, *, org_id: str, file_id: str) -> str:
    """Re-run rich parsing from disk (used when building search indexes)."""
    path = Path(storage_path)
    if not path.is_file():
        return ""
    data = path.read_bytes()
    return extract_text(filename, data, org_id=org_id, file_id=file_id)


def new_id() -> str:
    return str(uuid.uuid4())
