import logging

import numpy as np

import config
from services.chunking import dedupe_results_by_parent, expand_rows_for_chunking
from services.milvus_store import MilvusVectorStore, build_filter_expr
from services.text_search import TextSearch

logger = logging.getLogger(__name__)


def _get_torch_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class VectorSearch:
    """Semantic search backed by Milvus with optional local text index integration."""

    def __init__(
        self,
        file_id: str | None = None,
        org_id: str | None = None,
        embedding_model: str | None = None,
    ):
        self.file_id = file_id
        self.org_id = org_id
        self.embedding_model_name = embedding_model or config.BASE_EMBEDDING_MODEL
        self.torch_device = _get_torch_device()
        from sentence_transformers import SentenceTransformer

        self.embedding_model = SentenceTransformer(
            self.embedding_model_name,
            device=self.torch_device,
        )
        self._store: MilvusVectorStore | None = None
        if file_id:
            self._store = MilvusVectorStore(index_id=file_id, org_id=org_id)

    @property
    def store(self) -> MilvusVectorStore:
        if self._store is None:
            raise ValueError("Vector store not initialized. Provide a file_id.")
        return self._store

    def get_embeddings(self, texts: list[str]) -> np.ndarray:
        vectors = self.embedding_model.encode(texts, convert_to_tensor=False)
        arr = np.array(vectors, dtype="float32")
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms

    def embedding_dimension(self) -> int:
        return self.get_embeddings(["dimension probe"]).shape[1]

    def create_index(
        self,
        data: list[dict],
        text_column: str,
        id_column: str,
        org_id: str | None = None,
        chunk_size: int = 0,
        chunk_overlap: int = 0,
    ) -> int:
        if not data:
            raise ValueError("Cannot create index from empty data")

        vector_rows = expand_rows_for_chunking(
            data,
            text_column=text_column,
            id_column=id_column,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        texts = [row[text_column] for row in vector_rows]
        doc_ids = [str(row[id_column]) for row in vector_rows]
        embeddings = self.get_embeddings(texts)

        effective_org_id = org_id or self.org_id
        if self.store.collection_exists():
            self.store.drop_collection()

        self.store.create_collection(dimension=embeddings.shape[1])
        return self.store.insert_documents(
            doc_ids=doc_ids,
            texts=texts,
            embeddings=embeddings,
            org_id=effective_org_id,
        )

    def add_documents(
        self,
        new_data: list[dict],
        text_column: str,
        id_column: str,
        org_id: str | None = None,
        chunk_size: int = 0,
        chunk_overlap: int = 0,
    ) -> int:
        vector_rows = expand_rows_for_chunking(
            new_data,
            text_column=text_column,
            id_column=id_column,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        texts = [row[text_column] for row in vector_rows]
        doc_ids = [str(row[id_column]) for row in vector_rows]
        embeddings = self.get_embeddings(texts)
        return self.store.upsert_documents(
            doc_ids=doc_ids,
            texts=texts,
            embeddings=embeddings,
            org_id=org_id or self.org_id,
        )

    def delete_documents(self, doc_ids: list[str]) -> None:
        self.store.delete_documents([str(d) for d in doc_ids])

    def similarity_search(
        self,
        query: str,
        top_k: int = 10,
        org_id: str | None = None,
        metadata_filters: dict[str, str] | None = None,
        offset: int = 0,
    ) -> list[dict]:
        query_embedding = self.get_embeddings([query])[0]
        filter_expr = build_filter_expr(org_id or self.org_id, metadata_filters)
        return dedupe_results_by_parent(
            self.store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_expr=filter_expr,
                offset=offset,
            )
        )

    def similarity_search_lite(self, query: str, top_k: int = 5) -> list[dict]:
        return self.similarity_search(query, top_k=top_k)

    def boolean_semantic_search(
        self,
        query: str,
        top_k: int = 5,
        org_id: str | None = None,
    ) -> list[dict]:
        if not query.strip():
            return []

        text_search = TextSearch(index_file=self.file_id)
        boolean_results = text_search.boolean_search(query)
        if not boolean_results:
            return []

        allowed_ids = {str(doc["id"]) for doc in boolean_results}
        vector_results = self.similarity_search(
            query,
            top_k=max(top_k * 3, 20),
            org_id=org_id,
        )
        filtered = dedupe_results_by_parent(
            [r for r in vector_results if str(r["id"]) in allowed_ids]
        )
        return filtered[:top_k]

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        org_id: str | None = None,
        vector_weight: float = 0.5,
    ) -> list[dict]:
        text_search = TextSearch(index_file=self.file_id)
        text_results = text_search.bm25_search(query)
        vector_results = self.similarity_search(query, top_k=top_k * 2, org_id=org_id)

        scores: dict[str, float] = {}
        payloads: dict[str, dict] = {}

        for rank, result in enumerate(text_results):
            doc_id = str(result["id"])
            scores[doc_id] = scores.get(doc_id, 0.0) + (1 - vector_weight) / (rank + 1)
            payloads[doc_id] = result

        for rank, result in enumerate(vector_results):
            doc_id = str(result["id"])
            scores[doc_id] = scores.get(doc_id, 0.0) + vector_weight / (rank + 1)
            payloads.setdefault(doc_id, result)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: top_k * 3]
        merged = [
            {
                "id": doc_id,
                "text": payloads[doc_id].get("text"),
                "score": score,
            }
            for doc_id, score in ranked
        ]
        return dedupe_results_by_parent(merged)[:top_k]

    def drop_index(self) -> None:
        self.store.drop_collection()

    def get_stats(self) -> dict:
        return self.store.get_stats()
