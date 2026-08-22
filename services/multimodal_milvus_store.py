import logging
import re
from typing import Any

import numpy as np
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    utility,
)

from services.milvus_store import _ensure_connection, sanitize_collection_name

import config

logger = logging.getLogger(__name__)


def multimodal_collection_name(index_id: str) -> str:
    base = sanitize_collection_name(index_id)
    if base.startswith("mm_"):
        return base[:255]
    return f"mm_{base}"[:255]


def _multimodal_index_params() -> dict[str, Any]:
    if config.MILVUS_INDEX_TYPE.upper() == "IVF_FLAT":
        return {
            "index_type": "IVF_FLAT",
            "metric_type": config.MULTIMODAL_METRIC_TYPE,
            "params": {"nlist": 128},
        }
    return {
        "index_type": "HNSW",
        "metric_type": config.MULTIMODAL_METRIC_TYPE,
        "params": {
            "M": config.MILVUS_HNSW_M,
            "efConstruction": config.MILVUS_HNSW_EF_CONSTRUCTION,
        },
    }


def _multimodal_search_params() -> dict[str, Any]:
    params: dict[str, Any] = {"metric_type": config.MULTIMODAL_METRIC_TYPE}
    if config.MILVUS_INDEX_TYPE.upper() == "IVF_FLAT":
        params["params"] = {"nprobe": 16}
    else:
        params["params"] = {"ef": config.MILVUS_SEARCH_EF}
    return params


class MultimodalMilvusStore:
    """Milvus collection for image paths + embeddings with dynamic metadata."""

    CAPTION_MAX = 4096
    PATH_MAX = 1024

    def __init__(self, index_id: str, org_id: str | None = None):
        _ensure_connection()
        self.index_id = index_id
        self.org_id = org_id
        self.collection_name = multimodal_collection_name(index_id)
        self._collection: Collection | None = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            if not utility.has_collection(self.collection_name):
                raise ValueError(
                    f"Multimodal collection '{self.collection_name}' does not exist"
                )
            self._collection = Collection(self.collection_name)
            self._collection.load()
        return self._collection

    def collection_exists(self) -> bool:
        return utility.has_collection(self.collection_name)

    def create_collection(self, dimension: int) -> Collection:
        if utility.has_collection(self.collection_name):
            self._collection = Collection(self.collection_name)
            self._collection.load()
            return self._collection

        fields = [
            FieldSchema(
                name="doc_id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=512,
            ),
            FieldSchema(
                name="image_path",
                dtype=DataType.VARCHAR,
                max_length=self.PATH_MAX,
            ),
            FieldSchema(
                name="caption",
                dtype=DataType.VARCHAR,
                max_length=self.CAPTION_MAX,
            ),
            FieldSchema(
                name="org_id",
                dtype=DataType.VARCHAR,
                max_length=128,
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=dimension,
            ),
        ]
        schema = CollectionSchema(
            fields,
            description=f"Multimodal RAG index {self.index_id}",
            enable_dynamic_field=True,
        )
        collection = Collection(name=self.collection_name, schema=schema)
        collection.create_index(
            field_name="embedding", index_params=_multimodal_index_params()
        )
        collection.load()
        self._collection = collection
        logger.info("Created multimodal collection %s", self.collection_name)
        return collection

    def insert_images(
        self,
        doc_ids: list[str],
        image_paths: list[str],
        embeddings: np.ndarray,
        captions: list[str] | None = None,
        org_id: str | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        if not (len(doc_ids) == len(image_paths) == len(embeddings)):
            raise ValueError("doc_ids, image_paths, and embeddings must match")

        captions = captions or [""] * len(doc_ids)
        org_values = [org_id or self.org_id or ""] * len(doc_ids)
        rows: list[dict[str, Any]] = []
        for idx, doc_id in enumerate(doc_ids):
            row = {
                "doc_id": str(doc_id),
                "image_path": image_paths[idx][: self.PATH_MAX],
                "caption": captions[idx][: self.CAPTION_MAX],
                "org_id": org_values[idx],
                "embedding": embeddings[idx].tolist(),
            }
            if metadata and idx < len(metadata):
                row.update(metadata[idx])
            rows.append(row)

        result = self.collection.insert(rows)
        self.collection.flush()
        return result.insert_count

    def upsert_images(
        self,
        doc_ids: list[str],
        image_paths: list[str],
        embeddings: np.ndarray,
        captions: list[str] | None = None,
        org_id: str | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        self.delete_images(doc_ids)
        return self.insert_images(
            doc_ids, image_paths, embeddings, captions, org_id, metadata
        )

    def delete_images(self, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        quoted = ", ".join(f'"{doc_id}"' for doc_id in doc_ids)
        self.collection.delete(expr=f"doc_id in [{quoted}]")
        self.collection.flush()

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 9,
        filter_expr: str | None = None,
        offset: int = 0,
    ) -> list[dict]:
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        results = self.collection.search(
            data=query_embedding.tolist(),
            anns_field="embedding",
            param=_multimodal_search_params(),
            limit=top_k,
            offset=offset,
            expr=filter_expr,
            output_fields=["doc_id", "image_path", "caption", "org_id"],
        )

        hits: list[dict] = []
        for hit_group in results:
            for rank, hit in enumerate(hit_group):
                entity = hit.entity
                hits.append(
                    {
                        "id": entity.get("doc_id"),
                        "image_path": entity.get("image_path"),
                        "caption": entity.get("caption"),
                        "score": float(hit.score),
                        "org_id": entity.get("org_id"),
                        "rank": rank,
                    }
                )
        return hits

    def drop_collection(self) -> None:
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            self._collection = None

    def get_stats(self) -> dict:
        if not self.collection_exists():
            return {"exists": False, "collection": self.collection_name}
        col = self.collection
        return {
            "exists": True,
            "collection": self.collection_name,
            "num_entities": col.num_entities,
            "metric_type": config.MULTIMODAL_METRIC_TYPE,
        }


def build_multimodal_filter_expr(
    org_id: str | None = None,
    metadata_filters: dict[str, str] | None = None,
) -> str | None:
    clauses: list[str] = []
    if org_id:
        clauses.append(f'org_id == "{org_id}"')
    if metadata_filters:
        for key, value in metadata_filters.items():
            if key in ("doc_id", "image_path", "caption", "org_id", "embedding"):
                continue
            safe = re.sub(r'["\\]', "", str(value))
            clauses.append(f'{key} == "{safe}"')
    if not clauses:
        return None
    return " and ".join(clauses)
