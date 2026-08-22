import uuid
from sqlalchemy.orm import Session
from . import models, schemas
from sqlalchemy.sql import text
from sqlalchemy import inspect, Table, MetaData, func


# Query a database table or view by its name and client ID with optional column selection
def query_table_or_view(db: Session, table_or_view_name: str, filters: dict = None, columns: list = None):
    
    table = models.Base.metadata.tables[table_or_view_name]
    # query = db.query(*[table.c[col] for col in columns] if columns else table).filter_by(client_id=client_id)
    query = db.query(*[table.c[col] for col in columns] if columns else table)
    if filters:
        for key, value in filters.items():
            query = query.filter(table.c[key] == value)
    return query.all()

# Retrieve the names of all tables and views in the database
def get_all_tables_and_views(db: Session):
    """
    Get the names of all tables and views in the database.

    :param db: The database session.
    :return: A list of table and view names.
    """
    inspector = inspect(db.bind)
    return inspector.get_table_names() + inspector.get_view_names()

def get_table_or_view_columns(db: Session, table_or_view_name: str, schema: str = None):
    """
    Get the columns of a table or view.
    
    :param db: The database session.
    :param table_or_view_name: The name of the table or view.
    :param schema: The schema of the table or view (optional).
    :return: A list of column names.
    """
    inspector = inspect(db.bind)
    return [column['name'] for column in inspector.get_columns(table_or_view_name, schema=schema)]

def query_table_with_columns(db: Session, table_name: str, text_columns: list, id_column: str, schema: str = None, filters: dict = None): 
    """
    Query a table and concatenate specified text columns into a single column.

    :param db: The database session.
    :param table_name: The name of the table to query.
    :param text_columns: A list of text column names to concatenate.
    :param id_column: The ID column name.
    :param schema: The schema of the table (optional).
    :return: A list of rows with concatenated text columns.
    """
    try:
        meta = MetaData()
        table = Table(table_name, meta, autoload_with=db.bind, schema=schema)

        id_col = table.c[id_column]
        
        # Check if text_columns has more than one column
        if len(text_columns) > 1:
            # Concatenate all text columns
            concatenated_column = func.concat(*[table.c[column] for column in text_columns])
        else:
            # Use the single column directly
            concatenated_column = table.c[text_columns[0]]

        # Build the query
        query = db.query(id_col, concatenated_column.label("concatenated_text"))

        if filters:
            for key, value in filters.items():
                query = query.filter(table.c[key] == value)

        # Execute the query and fetch results
        results = query.all()

        return results
    
    except AttributeError as e:
        raise ValueError(f"Column not found: {e}") from e
    except Exception as e:
        raise RuntimeError(f"An error occurred while querying the table: {e}") from e