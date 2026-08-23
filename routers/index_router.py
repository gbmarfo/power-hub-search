from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.authentication import get_current_user
from database import schemas, models, search_crud
from database.database import get_db
from powerhub import search_bridge
from services.text_search import TextSearch
from services.vector_search import VectorSearch

router = APIRouter()


@router.post("/create", summary="Create a new search index")
def create_index_from_db(
    search_index: schemas.SearchIndexCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    search_index_record = search_crud.create_search_index(db=db, search_index=search_index)
    search_index_id = search_index_record.global_id

    text_search = TextSearch(index_file=search_index_id)
    searchable_columns = search_index_record.text_columns.split(",")
    id_column = search_index_record.id_col

    text_search.add_data(
        db=db,
        table_name=search_index_record.table_name,
        text_columns=searchable_columns,
        id_column=id_column,
        schema=search_index_record.schema_name,
    )

    vector_search = VectorSearch(
        file_id=search_index_id,
        org_id=search_index_record.org_id,
        embedding_model=search_index_record.embedding_model,
    )
    inserted = vector_search.create_index(
        data=[
            {id_column: row[0], "concatenated_text": row[1]}
            for row in text_search.data
        ],
        text_column="concatenated_text",
        id_column=id_column,
        org_id=search_index_record.org_id,
        chunk_size=search_index_record.chunk_size or 0,
        chunk_overlap=search_index_record.chunk_overlap or 0,
    )

    return {
        "message": "Search index created successfully",
        "id": search_index_id,
        "documents_indexed": inserted,
        "vector_backend": "milvus",
    }


@router.get("/list", summary="List search indexes for an organization")
def list_indexes(
    org_id: str,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    indexes = search_crud.get_search_indexes(db, org_id=org_id, skip=skip, limit=limit)
    return {
        "results": [
            schemas.SearchIndex.model_validate(index).model_dump()
            for index in indexes
        ],
        "count": len(indexes),
    }


@router.get("/{index_id}", summary="Get search index metadata")
def get_index(
    index_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    index = search_crud.get_search_index(db, index_id)
    if index is None:
        raise HTTPException(status_code=404, detail="Search index not found")
    vector_stats = VectorSearch(
        file_id=index_id,
        org_id=index.org_id,
        embedding_model=index.embedding_model,
    ).get_stats()
    return {
        "index": schemas.SearchIndex.model_validate(index).model_dump(),
        "vector_stats": vector_stats,
    }


@router.delete("/{index_id}", summary="Delete search index and Milvus collection")
def delete_index(
    index_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    index = search_crud.get_search_index(db, index_id)
    if index is None:
        raise HTTPException(status_code=404, detail="Search index not found")

    VectorSearch(
        file_id=index_id,
        org_id=index.org_id,
        embedding_model=index.embedding_model,
    ).drop_index()
    if index.source == "powerhub":
        search_bridge.cleanup_powerhub_search_index(db, index_id, index.org_id or "")
    deleted = search_crud.delete_search_index(db, index_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete index metadata")
    return {"message": "Search index deleted", "id": index_id}
