from sqlalchemy import Column, Integer, String, Text

import config
from .database import Base


def table_args() -> dict:
    url = config.INDEX_DB_URL or ""
    if url.startswith("sqlite"):
        return {}
    return {"schema": "ai"}


# Models for the Account Service
class Organization(Base):
    __tablename__ = "organization"
    __table_args__ = table_args()

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String)
    description = Column(Text)
    contact_name = Column(String)
    contact_phone = Column(String)
    contact_email = Column(String)
    contact_address = Column(String)
    organization_id = Column(String)
    organization_type = Column(String)

class User(Base):
    __tablename__ = "user"
    __table_args__ = table_args()

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String)
    username = Column(String)
    password = Column(String)
    email = Column(String)
    organization_id = Column(String)
    role = Column(String)
    is_active = Column(Integer)
    user_id = Column(String)


# Models for the Search Service
# These models represent the database tables for the search service.
class SearchIndex(Base):
    __tablename__ = "search_index"
    __table_args__ = table_args()

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    global_id = Column(String)
    title = Column(String)
    description = Column(String)
    table_name = Column(String)
    text_columns = Column(Text)
    id_col = Column(String)
    org_id = Column(String)
    source = Column(String)
    schema_name = Column(String)
    created_by = Column(String)

class IndexDocument(Base):
    __tablename__ = "index_document"
    __table_args__ = table_args()

    id = Column(Integer, primary_key=True, index=True)
    global_id = Column(String)
    index_id = Column(Integer)
    filename = Column(String)
    filepath = Column(String)
    client_id = Column(String)


# Models for the Connection Service
# These models represent the database tables for the connection service.
class Connection(Base):
    __tablename__ = "connection"
    __table_args__ = table_args()

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    connection_id = Column(String)
    connection_name = Column(String)
    connection_type = Column(String)
    host = Column(String)
    port = Column(Integer)
    username = Column(String)
    password = Column(String)
    database_name = Column(String)
    schema_name = Column(String)
    client_id = Column(String)