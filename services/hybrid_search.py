import logging

from fastapi import HTTPException

from services.text_search import TextSearch
from services.vector_search import VectorSearch

logger = logging.getLogger(__name__)


class HybridSearch:
    def __init__(self, index_file: str | None = None, org_id: str | None = None):
        self.index_file = index_file
        self.org_id = org_id

    def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.5,
    ) -> dict:
        try:
            vector_search = VectorSearch(file_id=self.index_file, org_id=self.org_id)
            combined = vector_search.hybrid_search(
                query=query,
                top_k=top_k,
                org_id=self.org_id,
                vector_weight=vector_weight,
            )
            text_search = TextSearch(index_file=self.index_file)
            text_results = text_search.bm25_search(query)[:top_k]
            vector_results = vector_search.similarity_search(
                query, top_k=top_k, org_id=self.org_id
            )
            return {
                "results": combined,
                "vector_results": vector_results,
                "text_results": text_results,
            }
        except Exception as exc:
            logger.exception("Hybrid search failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
