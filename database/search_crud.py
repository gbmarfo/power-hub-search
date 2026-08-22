import uuid
from sqlalchemy.orm import Session
from . import models, schemas
from sqlalchemy.sql import text
from sqlalchemy import inspect, Table, MetaData, func


# Retrieve a specific search index by its ID 
def get_search_index(db: Session, search_index_id: str):
    return db.query(models.SearchIndex).filter(models.SearchIndex.global_id == search_index_id).first()

# Retrieve a list of search indexes for a specific Organization ID with pagination
def get_search_indexes(db: Session, org_id: str, skip: int = 0, limit: int = 10):
    return db.query(models.SearchIndex).filter(models.SearchIndex.org_id == org_id).order_by(models.SearchIndex.title).offset(skip).limit(limit).all()

# Create a new search index in the database
def create_search_index(db: Session, search_index: schemas.SearchIndexCreate):
    db_search_index = models.SearchIndex(**search_index.dict())
    db_search_index.global_id = str(uuid.uuid4())
    db.add(db_search_index)
    db.commit()
    db.refresh(db_search_index)
    return db_search_index

# Update an existing search index by its ID and Org ID
def update_search_index(db: Session, search_index_id: str, search_index: schemas.SearchIndexCreate, org_id: str):
    db_search_index = db.query(models.SearchIndex).filter(models.SearchIndex.global_id == search_index_id, models.SearchIndex.org_id == org_id).first()
    if db_search_index:
        for key, value in search_index.dict().items():
            setattr(db_search_index, key, value)
        db.commit()
        db.refresh(db_search_index)
        return db_search_index
    return None

# Delete a search index by its ID
def delete_search_index(db: Session, search_index_id: str):
    db_search_index = db.query(models.SearchIndex).filter(models.SearchIndex.global_id == search_index_id).first()
    if db_search_index:
        db.delete(db_search_index)
        db.commit()
        return True
    return False

# Retrieve a search index by its title and Org ID
def get_search_index_by_title(db: Session, title: str, org_id: str):
    return db.query(models.SearchIndex).filter(models.SearchIndex.title == title, models.SearchIndex.org_id == org_id).first()


# Retrieve a search index by its database table and client ID
def get_search_index_by_db_table(db: Session, tablename: str, org_id: str):
    return db.query(models.SearchIndex).filter(models.SearchIndex.table_name == tablename, models.SearchIndex.org_id == org_id).first()
