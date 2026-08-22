from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.authentication import get_current_user
from database import models, schemas, search_crud
from database.database import engine, get_db
from services.text_search import TextSearch
from services.vector_search import VectorSearch

models.Base.metadata.create_all(bind=engine)

router = APIRouter()


def _run_search(
    index_id: str,
    query: str,
    mode: schemas.SearchMode,
    top_k: int = 10,
    offset: int = 0,
    org_id: str | None = None,
    metadata_filters: dict[str, str] | None = None,
    vector_weight: float = 0.5,
) -> list[dict]:
    text_search = TextSearch(index_file=index_id)
    vector_search = VectorSearch(file_id=index_id, org_id=org_id)

    if mode == schemas.SearchMode.ranked_naive:
        return text_search.ranked_search(query)
    if mode == schemas.SearchMode.full_text:
        return text_search.bm25_search(query)
    if mode == schemas.SearchMode.boolean_ranked:
        return text_search.boolean_ranked_search(query)
    if mode == schemas.SearchMode.exact:
        return text_search.boolean_search(query)
    if mode == schemas.SearchMode.fuzzy:
        return text_search.fuzzy_search(query)
    if mode == schemas.SearchMode.similarity:
        return vector_search.similarity_search(
            query,
            top_k=top_k,
            org_id=org_id,
            metadata_filters=metadata_filters,
            offset=offset,
        )
    if mode == schemas.SearchMode.exact_similarity:
        return vector_search.boolean_semantic_search(
            query, top_k=top_k, org_id=org_id
        )
    if mode == schemas.SearchMode.hybrid:
        return vector_search.hybrid_search(
            query,
            top_k=top_k,
            org_id=org_id,
            vector_weight=vector_weight,
        )
    raise HTTPException(status_code=400, detail=f"Unsupported search mode: {mode}")


@router.post(
    "/{index_id}",
    summary="Unified enterprise search",
    response_model=schemas.SearchResponse,
)
async def unified_search(
    index_id: str,
    body: schemas.SearchRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    index = search_crud.get_search_index(db, index_id)
    if index is None:
        raise HTTPException(status_code=404, detail="Search index not found")

    org_id = body.org_id or index.org_id
    try:
        results = _run_search(
            index_id=index_id,
            query=body.query,
            mode=body.mode,
            top_k=body.top_k,
            offset=body.offset,
            org_id=org_id,
            metadata_filters=body.metadata_filters,
            vector_weight=body.vector_weight,
        )
        if body.mode != schemas.SearchMode.similarity:
            results = results[body.offset : body.offset + body.top_k]
        return schemas.SearchResponse(
            results=results,
            mode=body.mode.value,
            total_returned=len(results),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/ranked_naive", summary="Ranked Search using TF-IDF")
async def ranked_search(
    query: str,
    index_id: str,
    current_user: str = Depends(get_current_user),
):
    try:
        return {"results": TextSearch(index_file=index_id).ranked_search(query)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/full_text", summary="Ranked Search using BM25")
async def ranked_search_bm25(
    query: str,
    index_id: str,
    current_user: str = Depends(get_current_user),
):
    try:
        return {"results": TextSearch(index_file=index_id).bm25_search(query)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/boolean_ranked", summary="Boolean then TF-IDF ranked search")
async def boolean_ranked_search(
    query: str,
    index_id: str,
    current_user: str = Depends(get_current_user),
):
    try:
        return {"results": TextSearch(index_file=index_id).boolean_ranked_search(query)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/exact", summary="Exact boolean search")
async def keyword_search(
    query: str,
    index_id: str,
    current_user: str = Depends(get_current_user),
):
    try:
        return {"results": TextSearch(index_file=index_id).boolean_search(query)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/fuzzy", summary="Fuzzy search")
async def fuzzy_search(
    query: str,
    index_id: str,
    current_user: str = Depends(get_current_user),
):
    try:
        return {"results": TextSearch(index_file=index_id).fuzzy_search(query)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/similarity", summary="Milvus vector similarity search")
async def similarity_search(
    query: str,
    index_id: str,
    top_k: int = 10,
    org_id: str | None = None,
    current_user: str = Depends(get_current_user),
):
    try:
        results = VectorSearch(file_id=index_id, org_id=org_id).similarity_search(
            query, top_k=top_k, org_id=org_id
        )
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/exact_similarity", summary="Boolean filter + vector rerank")
async def exact_similarity_search(
    query: str,
    index_id: str,
    top_k: int = 5,
    org_id: str | None = None,
    current_user: str = Depends(get_current_user),
):
    try:
        results = VectorSearch(file_id=index_id, org_id=org_id).boolean_semantic_search(
            query, top_k=top_k, org_id=org_id
        )
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{index_id}/hybrid", summary="Hybrid BM25 + Milvus vector search (RRF)")
async def hybrid_search_endpoint(
    query: str,
    index_id: str,
    top_k: int = 10,
    org_id: str | None = None,
    vector_weight: float = 0.5,
    current_user: str = Depends(get_current_user),
):
    try:
        results = VectorSearch(file_id=index_id, org_id=org_id).hybrid_search(
            query, top_k=top_k, org_id=org_id, vector_weight=vector_weight
        )
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
