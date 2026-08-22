import logging
import os
import shutil
import uuid
from pathlib import Path

import numpy as np

import config
from services.llm_reranker import LLMReranker, create_panoramic_view
from services.multimodal_encoder import get_multimodal_encoder
from services.multimodal_milvus_store import (
    MultimodalMilvusStore,
    build_multimodal_filter_expr,
)

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class MultimodalRAGService:
    """Composed image retrieval + optional GPT-4o generative reranking."""

    def __init__(self, index_id: str, org_id: str | None = None):
        self.index_id = index_id
        self.org_id = org_id
        self.encoder = get_multimodal_encoder()
        self.store = MultimodalMilvusStore(index_id=index_id, org_id=org_id)
        self.reranker = LLMReranker()
        self.upload_dir = Path(config.MULTIMODAL_UPLOAD_DIR) / index_id
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict:
        return {
            "index_id": self.index_id,
            "encoder": self.encoder.status(),
            "vector_stats": self.store.get_stats(),
            "reranker_available": self.reranker.is_available,
            "upload_dir": str(self.upload_dir),
        }

    def ensure_collection(self) -> None:
        if not self.encoder.is_available:
            raise RuntimeError("Multimodal encoder is not available")
        if not self.store.collection_exists():
            self.store.create_collection(dimension=self.encoder.dimension)

    def save_upload(self, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES:
            raise ValueError(
                f"Unsupported image type '{suffix}'. Allowed: {sorted(ALLOWED_IMAGE_SUFFIXES)}"
            )
        safe_name = f"{uuid.uuid4().hex}{suffix}"
        path = self.upload_dir / safe_name
        path.write_bytes(content)
        return str(path)

    def index_image_files(
        self,
        image_paths: list[str],
        captions: list[str] | None = None,
        doc_ids: list[str] | None = None,
        org_id: str | None = None,
    ) -> int:
        if not image_paths:
            raise ValueError("No images provided")

        self.ensure_collection()
        captions = captions or [""] * len(image_paths)
        doc_ids = doc_ids or [uuid.uuid4().hex for _ in image_paths]

        embeddings: list[np.ndarray] = []
        stored_paths: list[str] = []
        for image_path in image_paths:
            embeddings.append(self.encoder.encode_image(image_path))
            stored_paths.append(image_path)

        embedding_matrix = np.vstack(embeddings)
        return self.store.insert_images(
            doc_ids=[str(d) for d in doc_ids],
            image_paths=stored_paths,
            embeddings=embedding_matrix,
            captions=captions,
            org_id=org_id or self.org_id,
        )

    def index_uploaded_files(
        self,
        files: list[tuple[str, bytes]],
        captions: list[str] | None = None,
        org_id: str | None = None,
    ) -> list[dict]:
        saved_paths: list[str] = []
        generated_ids: list[str] = []
        for filename, content in files:
            path = self.save_upload(filename, content)
            saved_paths.append(path)
            generated_ids.append(uuid.uuid4().hex)

        count = self.index_image_files(
            image_paths=saved_paths,
            captions=captions,
            doc_ids=generated_ids,
            org_id=org_id,
        )
        return [
            {"doc_id": doc_id, "image_path": path, "indexed": True}
            for doc_id, path in zip(generated_ids, saved_paths, strict=True)
        ][:count]

    def index_directory(
        self,
        directory_path: str,
        pattern: str = "*.jpg",
        org_id: str | None = None,
    ) -> int:
        directory = Path(directory_path)
        if not directory.is_dir():
            raise ValueError(f"Directory not found: {directory_path}")

        image_paths = sorted(
            str(path)
            for path in directory.glob(pattern)
            if path.suffix.lower() in ALLOWED_IMAGE_SUFFIXES
        )
        if not image_paths:
            raise ValueError(f"No images found in {directory_path} matching {pattern}")

        return self.index_image_files(image_paths=image_paths, org_id=org_id)

    def search(
        self,
        query_text: str = "",
        query_image_path: str | None = None,
        top_k: int | None = None,
        org_id: str | None = None,
        metadata_filters: dict[str, str] | None = None,
        offset: int = 0,
    ) -> list[dict]:
        if not query_text.strip() and not query_image_path:
            raise ValueError("Provide query text and/or a query image")

        self.ensure_collection()
        top_k = top_k or config.MULTIMODAL_DEFAULT_TOP_K
        query_embedding = self.encoder.encode_query(query_image_path, query_text)
        filter_expr = build_multimodal_filter_expr(org_id or self.org_id, metadata_filters)
        return self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_expr=filter_expr,
            offset=offset,
        )

    def search_with_rerank(
        self,
        query_text: str,
        query_image_path: str,
        top_k: int | None = None,
        org_id: str | None = None,
        metadata_filters: dict[str, str] | None = None,
    ) -> dict:
        top_k = top_k or config.MULTIMODAL_DEFAULT_TOP_K
        results = self.search(
            query_text=query_text,
            query_image_path=query_image_path,
            top_k=top_k,
            org_id=org_id,
            metadata_filters=metadata_filters,
        )
        if not results:
            return {
                "results": [],
                "ranked_indices": [],
                "best_result": None,
                "explanation": "No candidates retrieved.",
                "panoramic_image_path": None,
            }

        retrieved_paths = [item["image_path"] for item in results if item.get("image_path")]
        panoramic_path = str(self.upload_dir / f"panoramic_{uuid.uuid4().hex}.jpg")
        create_panoramic_view(query_image_path, retrieved_paths, panoramic_path)

        product_infos = [
            item.get("caption") or f"Image candidate {item.get('rank', 0)}"
            for item in results
        ]
        ranked_indices, explanation = self.reranker.rerank(
            combined_image_path=panoramic_path,
            instruction=query_text,
            product_infos=product_infos,
        )

        reranked_results = []
        for index in ranked_indices:
            if 0 <= index < len(results):
                entry = dict(results[index])
                entry["rerank_position"] = len(reranked_results)
                reranked_results.append(entry)

        best_result = reranked_results[0] if reranked_results else results[0]
        return {
            "results": results,
            "reranked_results": reranked_results,
            "ranked_indices": ranked_indices,
            "best_result": best_result,
            "explanation": explanation,
            "panoramic_image_path": panoramic_path,
        }

    def drop_index(self) -> None:
        self.store.drop_collection()
        if self.upload_dir.exists():
            shutil.rmtree(self.upload_dir, ignore_errors=True)

    @staticmethod
    def relative_asset_path(index_id: str, absolute_path: str) -> str | None:
        base = Path(config.MULTIMODAL_UPLOAD_DIR) / index_id
        try:
            rel = Path(absolute_path).resolve().relative_to(base.resolve())
            return str(rel).replace(os.sep, "/")
        except ValueError:
            return None
