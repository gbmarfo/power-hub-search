import logging
import re
from typing import Any

import numpy as np
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

import config

logger = logging.getLogger(__name__)

_milvus_connected = False


def _ensure_connection() -> None:
    global _milvus_connected
    if _milvus_connected:
        return
    connect_kwargs: dict[str, Any] = {"uri": config.MILVUS_URI}
    if config.MILVUS_USER:
        connect_kwargs["user"] = config.MILVUS_USER
    if config.MILVUS_PASSWORD:
        connect_kwargs["password"] = config.MILVUS_PASSWORD
    if config.MILVUS_DB_NAME and config.MILVUS_DB_NAME != "default":
        connect_kwargs["db_name"] = config.MILVUS_DB_NAME
    connections.connect(alias="default", **connect_kwargs)
    _milvus_connected = True


def sanitize_collection_name(index_id: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", index_id)
    if not name[0].isalpha():
        name = f"idx_{name}"
    return name[:255]


def _build_index_params() -> dict[str, Any]:
    if config.MILVUS_INDEX_TYPE.upper() == "IVF_FLAT":
        return {
            "index_type": "IVF_FLAT",
            "metric_type": config.MILVUS_METRIC_TYPE,
            "params": {"nlist": 128},
        }
    return {
        "index_type": "HNSW",
        "metric_type": config.MILVUS_METRIC_TYPE,
        "params": {
            "M": config.MILVUS_HNSW_M,
            "efConstruction": config.MILVUS_HNSW_EF_CONSTRUCTION,
        },
    }


def _search_params() -> dict[str, Any]:
    params: dict[str, Any] = {"metric_type": config.MILVUS_METRIC_TYPE}
    if config.MILVUS_INDEX_TYPE.upper() == "IVF_FLAT":
        params["params"] = {"nprobe": 16}
    else:
        params["params"] = {"ef": config.MILVUS_SEARCH_EF}
    return params


class MilvusVectorStore:
    """Milvus-backed vector store with filtering, upsert, and hybrid search support."""

    TEXT_MAX_LENGTH = 65535

    def __init__(self, index_id: str, org_id: str | None = None):
        _ensure_connection()
        self.index_id = index_id
        self.org_id = org_id
        self.collection_name = sanitize_collection_name(index_id)
        self._collection: Collection | None = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            if not utility.has_collection(self.collection_name):
                raise ValueError(
                    f"Milvus collection '{self.collection_name}' does not exist. "
                    "Create the index first."
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
                name="text",
                dtype=DataType.VARCHAR,
                max_length=self.TEXT_MAX_LENGTH,
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
            description=f"Search index {self.index_id}",
            enable_dynamic_field=True,
        )
        collection = Collection(name=self.collection_name, schema=schema)
        collection.create_index(field_name="embedding", index_params=_build_index_params())
        collection.load()
        self._collection = collection
        logger.info("Created Milvus collection %s (dim=%s)", self.collection_name, dimension)
        return collection

    def insert_documents(
        self,
        doc_ids: list[str],
        texts: list[str],
        embeddings: np.ndarray,
        org_id: str | None = None,
    ) -> int:
        if len(doc_ids) != len(texts) or len(doc_ids) != len(embeddings):
            raise ValueError("doc_ids, texts, and embeddings must have the same length")

        org_values = [org_id or self.org_id or ""] * len(doc_ids)
        truncated_texts = [t[: self.TEXT_MAX_LENGTH] for t in texts]
        str_ids = [str(d) for d in doc_ids]

        data = [str_ids, truncated_texts, org_values, embeddings.tolist()]
        result = self.collection.insert(data)
        self.collection.flush()
        return result.insert_count

    def upsert_documents(
        self,
        doc_ids: list[str],
        texts: list[str],
        embeddings: np.ndarray,
        org_id: str | None = None,
    ) -> int:
        self.delete_documents(doc_ids)
        return self.insert_documents(doc_ids, texts, embeddings, org_id=org_id)

    def delete_documents(self, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        quoted = ", ".join(f'"{doc_id}"' for doc_id in doc_ids)
        self.collection.delete(expr=f"doc_id in [{quoted}]")
        self.collection.flush()

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filter_expr: str | None = None,
        offset: int = 0,
    ) -> list[dict]:
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        results = self.collection.search(
            data=query_embedding.tolist(),
            anns_field="embedding",
            param=_search_params(),
            limit=top_k,
            offset=offset,
            expr=filter_expr,
            output_fields=["doc_id", "text", "org_id"],
        )

        hits: list[dict] = []
        for hit_group in results:
            for hit in hit_group:
                hits.append(
                    {
                        "id": hit.entity.get("doc_id"),
                        "text": hit.entity.get("text"),
                        "score": float(hit.score),
                        "org_id": hit.entity.get("org_id"),
                    }
                )
        return hits

    def drop_collection(self) -> None:
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            self._collection = None
            logger.info("Dropped Milvus collection %s", self.collection_name)

    def get_stats(self) -> dict:
        if not self.collection_exists():
            return {"exists": False, "collection": self.collection_name}
        col = self.collection
        return {
            "exists": True,
            "collection": self.collection_name,
            "num_entities": col.num_entities,
        }


def build_filter_expr(
    org_id: str | None = None,
    metadata_filters: dict[str, str] | None = None,
) -> str | None:
    clauses: list[str] = []
    if org_id:
        clauses.append(f'org_id == "{org_id}"')
    if metadata_filters:
        for key, value in metadata_filters.items():
            if key in ("doc_id", "text", "org_id", "embedding"):
                continue
            clauses.append(f'{key} == "{value}"')
    if not clauses:
        return None
    return " and ".join(clauses)


def check_milvus_health() -> dict:
    try:
        _ensure_connection()
        version = utility.get_server_version()
        return {"status": "ok", "version": version}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
