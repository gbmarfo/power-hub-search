from enum import Enum

from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    ranked_naive = "ranked_naive"
    full_text = "full_text"
    boolean_ranked = "boolean_ranked"
    exact = "exact"
    fuzzy = "fuzzy"
    similarity = "similarity"
    exact_similarity = "exact_similarity"
    hybrid = "hybrid"


class SearchRequest(BaseModel):
    query: str
    mode: SearchMode = SearchMode.similarity
    top_k: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    org_id: str | None = None
    metadata_filters: dict[str, str] | None = None
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    results: list[dict]
    mode: str
    total_returned: int


class MultimodalIndexCreate(BaseModel):
    title: str
    description: str | None = None
    org_id: str
    created_by: str | None = None


class MultimodalSearchResponse(BaseModel):
    results: list[dict]
    total_returned: int
    query_type: str


class MultimodalRerankResponse(BaseModel):
    results: list[dict]
    reranked_results: list[dict]
    ranked_indices: list[int]
    best_result: dict | None
    explanation: str
    panoramic_url: str | None = None


class OrganizationBase(BaseModel):
    name: str | None = None
    description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_address: str | None = None
    organization_id: str | None = None
    organization_type: str | None = None

class OrganizationCreate(OrganizationBase):
    pass

class Organization(OrganizationBase):
    id: int

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    full_name: str | None = None
    username: str | None = None
    password: str | None = None
    email: str | None = None
    organization_id: str | None = None
    role: str | None = None
    is_active: int | None = None
    user_id: str | None = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class SearchIndexBase(BaseModel):
    global_id: str | None = None
    title: str | None = None
    description: str | None = None
    table_name: str | None = None
    text_columns: str | None = None
    id_col: str | None = None
    org_id: str | None = None
    source: str | None = None
    schema_name: str | None = None
    created_by: str | None = None
    embedding_model: str | None = None
    chunk_size: int | None = Field(default=None, ge=0, le=10000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=5000)

class SearchIndexCreate(SearchIndexBase):
    pass

class SearchIndex(SearchIndexBase):
    id: int

    class Config:
        from_attributes = True


class IndexDocumentBase(BaseModel):
    global_id: str 
    index_id: str
    filename: str
    filepath: str

class IndexDocumentCreate(IndexDocumentBase):
    pass

class IndexDocument(IndexDocumentBase):
    id: int

    class Config:
        from_attributes = True