import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.authentication import get_current_user
from database import models, schemas, search_crud
from database.database import engine, get_db
from services.multimodal_rag import MultimodalRAGService

import config

models.Base.metadata.create_all(bind=engine)

router = APIRouter()


def _get_service(index_id: str, org_id: str | None = None) -> MultimodalRAGService:
    if not config.MULTIMODAL_ENABLED:
        raise HTTPException(status_code=503, detail="Multimodal RAG is disabled")
    return MultimodalRAGService(index_id=index_id, org_id=org_id)


def _asset_url(index_id: str, absolute_path: str | None) -> str | None:
    if not absolute_path:
        return None
    rel = MultimodalRAGService.relative_asset_path(index_id, absolute_path)
    if not rel:
        return None
    return f"/api/v1/multimodal/{index_id}/assets/{rel}"


def _enrich_results(index_id: str, results: list[dict]) -> list[dict]:
    enriched = []
    for item in results:
        row = dict(item)
        row["image_url"] = _asset_url(index_id, row.get("image_path"))
        enriched.append(row)
    return enriched


@router.get("/status", summary="Multimodal RAG capability status")
async def multimodal_status(current_user: str = Depends(get_current_user)):
    encoder_status = {}
    try:
        from services.multimodal_encoder import get_multimodal_encoder

        encoder_status = get_multimodal_encoder().status()
    except Exception as exc:
        encoder_status = {"available": False, "error": str(exc)}

    return {
        "enabled": config.MULTIMODAL_ENABLED,
        "encoder": encoder_status,
        "reranker_configured": bool(config.OPENAI_API_KEY),
        "metric_type": config.MULTIMODAL_METRIC_TYPE,
        "default_top_k": config.MULTIMODAL_DEFAULT_TOP_K,
    }


@router.post("/index/create", summary="Create a multimodal RAG index")
def create_multimodal_index(
    body: schemas.MultimodalIndexCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.create_search_index(
        db=db,
        search_index=schemas.SearchIndexCreate(
            title=body.title,
            description=body.description,
            org_id=body.org_id,
            source="multimodal",
            created_by=body.created_by or current_user,
        ),
    )
    service = _get_service(record.global_id, org_id=body.org_id)
    service.ensure_collection()
    return {
        "message": "Multimodal index created",
        "id": record.global_id,
        "org_id": body.org_id,
        "encoder": service.encoder.status(),
        "vector_stats": service.store.get_stats(),
    }


@router.get("/{index_id}", summary="Get multimodal index status")
def get_multimodal_index(
    index_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.get_search_index(db, index_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Index not found")
    service = _get_service(index_id, org_id=record.org_id)
    return {
        "index": schemas.SearchIndex.model_validate(record).model_dump(),
        **service.status(),
    }


@router.post("/{index_id}/images", summary="Upload and index images")
async def index_images(
    index_id: str,
    files: list[UploadFile] = File(...),
    captions: str | None = Form(None),
    org_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.get_search_index(db, index_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Index not found")

    caption_list = None
    if captions:
        try:
            caption_list = json.loads(captions)
        except json.JSONDecodeError:
            caption_list = [line.strip() for line in captions.splitlines() if line.strip()]

    uploads: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        uploads.append((upload.filename or f"{uuid.uuid4().hex}.jpg", content))

    service = _get_service(index_id, org_id=org_id or record.org_id)
    indexed = service.index_uploaded_files(
        files=uploads,
        captions=caption_list,
        org_id=org_id or record.org_id,
    )
    for item in indexed:
        item["image_url"] = _asset_url(index_id, item.get("image_path"))

    return {
        "message": f"Indexed {len(indexed)} images",
        "indexed": indexed,
        "vector_stats": service.store.get_stats(),
    }


@router.post("/{index_id}/images/directory", summary="Index images from server directory")
def index_directory(
    index_id: str,
    directory_path: str = Form(...),
    pattern: str = Form("*.jpg"),
    org_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.get_search_index(db, index_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Index not found")

    service = _get_service(index_id, org_id=org_id or record.org_id)
    count = service.index_directory(
        directory_path=directory_path,
        pattern=pattern,
        org_id=org_id or record.org_id,
    )
    return {
        "message": f"Indexed {count} images from directory",
        "documents_indexed": count,
        "vector_stats": service.store.get_stats(),
    }


@router.post(
    "/{index_id}/search",
    summary="Composed image+text multimodal search",
    response_model=schemas.MultimodalSearchResponse,
)
async def multimodal_search(
    index_id: str,
    query_text: str = Form(""),
    query_image: UploadFile | None = File(None),
    top_k: int = Form(config.MULTIMODAL_DEFAULT_TOP_K),
    org_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.get_search_index(db, index_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Index not found")

    service = _get_service(index_id, org_id=org_id or record.org_id)
    query_image_path = None
    if query_image is not None:
        content = await query_image.read()
        query_image_path = service.save_upload(query_image.filename or "query.jpg", content)

    try:
        results = service.search(
            query_text=query_text,
            query_image_path=query_image_path,
            top_k=top_k,
            org_id=org_id or record.org_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    enriched = _enrich_results(index_id, results)
    query_type = "composed" if query_image_path and query_text.strip() else (
        "image" if query_image_path else "text"
    )
    return schemas.MultimodalSearchResponse(
        results=enriched,
        total_returned=len(enriched),
        query_type=query_type,
    )


@router.post(
    "/{index_id}/search/rerank",
    summary="Multimodal search with GPT-4o generative reranking",
    response_model=schemas.MultimodalRerankResponse,
)
async def multimodal_search_rerank(
    index_id: str,
    query_text: str = Form(...),
    query_image: UploadFile = File(...),
    top_k: int = Form(config.MULTIMODAL_DEFAULT_TOP_K),
    org_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.get_search_index(db, index_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Index not found")

    service = _get_service(index_id, org_id=org_id or record.org_id)
    content = await query_image.read()
    query_image_path = service.save_upload(query_image.filename or "query.jpg", content)

    try:
        payload = service.search_with_rerank(
            query_text=query_text,
            query_image_path=query_image_path,
            top_k=top_k,
            org_id=org_id or record.org_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload["results"] = _enrich_results(index_id, payload.get("results", []))
    payload["reranked_results"] = _enrich_results(
        index_id, payload.get("reranked_results", [])
    )
    if payload.get("best_result"):
        best = dict(payload["best_result"])
        best["image_url"] = _asset_url(index_id, best.get("image_path"))
        payload["best_result"] = best

    panoramic_url = _asset_url(index_id, payload.get("panoramic_image_path"))
    return schemas.MultimodalRerankResponse(
        results=payload["results"],
        reranked_results=payload["reranked_results"],
        ranked_indices=payload["ranked_indices"],
        best_result=payload["best_result"],
        explanation=payload["explanation"],
        panoramic_url=panoramic_url,
    )


@router.get("/{index_id}/assets/{asset_path:path}", summary="Serve indexed image asset")
def get_multimodal_asset(index_id: str, asset_path: str):
    base = Path(config.MULTIMODAL_UPLOAD_DIR) / index_id
    file_path = (base / asset_path).resolve()
    if not str(file_path).startswith(str(base.resolve())):
        raise HTTPException(status_code=403, detail="Invalid asset path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(file_path)


@router.delete("/{index_id}", summary="Delete multimodal index and Milvus collection")
def delete_multimodal_index(
    index_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    record = search_crud.get_search_index(db, index_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Index not found")

    _get_service(index_id, org_id=record.org_id).drop_index()
    search_crud.delete_search_index(db, index_id)
    return {"message": "Multimodal index deleted", "id": index_id}
