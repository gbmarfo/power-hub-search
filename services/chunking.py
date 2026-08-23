"""Text chunking helpers for vector indexing."""

from __future__ import annotations

CHUNK_ID_SEP = "::chunk::"


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character chunks."""
    clean = (text or "").strip()
    if not clean:
        return []
    if chunk_size <= 0 or len(clean) <= chunk_size:
        return [clean]

    overlap = max(0, min(overlap, chunk_size - 1))
    step = chunk_size - overlap
    chunks: list[str] = []
    for start in range(0, len(clean), step):
        piece = clean[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(clean):
            break
    return chunks or [clean]


def expand_rows_for_chunking(
    rows: list[dict],
    *,
    text_column: str,
    id_column: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    """Expand document rows into chunk rows for vector indexing."""
    if chunk_size <= 0:
        return rows

    expanded: list[dict] = []
    for row in rows:
        parent_id = str(row[id_column])
        text = row.get(text_column) or ""
        chunks = split_text(text, chunk_size, chunk_overlap)
        if len(chunks) <= 1:
            expanded.append(dict(row))
            continue
        for index, chunk in enumerate(chunks):
            chunk_row = dict(row)
            chunk_row[id_column] = f"{parent_id}{CHUNK_ID_SEP}{index}"
            chunk_row[text_column] = chunk
            expanded.append(chunk_row)
    return expanded


def parent_doc_id(doc_id: str) -> str:
    if CHUNK_ID_SEP in doc_id:
        return doc_id.split(CHUNK_ID_SEP, 1)[0]
    return doc_id


def dedupe_results_by_parent(results: list[dict]) -> list[dict]:
    """Keep the highest-scoring hit per parent document when chunks were indexed."""
    best: dict[str, dict] = {}
    for result in results:
        raw_id = str(result.get("id", ""))
        parent_id = parent_doc_id(raw_id)
        score = float(result.get("score") or 0)
        current = best.get(parent_id)
        if current is None or score > float(current.get("score") or 0):
            entry = dict(result)
            entry["id"] = parent_id
            if raw_id != parent_id:
                entry["chunk_id"] = raw_id
            best[parent_id] = entry
    return sorted(best.values(), key=lambda item: float(item.get("score") or 0), reverse=True)
