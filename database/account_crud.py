import uuid
from sqlalchemy.orm import Session
from . import models, schemas
from sqlalchemy.sql import text
from sqlalchemy import inspect, Table, MetaData, func


def create_organization(db: Session, organization: schemas.OrganizationCreate):
    """
    Create a new organization in the database.
    """
    db_organization = models.Organization(
        name=organization.name,
        description=organization.description,
        contact_name=organization.contact_name,
        contact_phone=organization.contact_phone,
        contact_email=organization.contact_email,
        contact_address=organization.contact_address,
        organization_id=uuid.uuid4()
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization

def get_organization(db: Session, organization_id: str):
    """
    Retrieve an organization by its ID.
    """
    return db.query(models.Organization).filter(models.Organization.organization_id == organization_id).first()

def get_organization_by_name(db: Session, name: str):
    """
    Retrieve an organization by its name.
    """
    return db.query(models.Organization).filter(models.Organization.name == name).first()

def get_organizations(db: Session, skip: int = 0, limit: int = 100):
    """
    Retrieve a list of organizations with pagination.
    """
    return db.query(models.Organization).offset(skip).limit(limit).all()

def update_organization(db: Session, organization_id: str, organization: schemas.Organization):
    """
    Update an existing organization by its ID.
    """
    db_organization = db.query(models.Organization).filter(models.Organization.organization_id == organization_id).first()
    if db_organization:
        for key, value in organization.dict(exclude_unset=True).items():
            setattr(db_organization, key, value)
        db.commit()
        db.refresh(db_organization)
        return db_organization
    return None

def delete_organization(db: Session, organization_id: str):
    """
    Delete an organization by its ID.
    """
    db_organization = db.query(models.Organization).filter(models.Organization.organization_id == organization_id).first()
    if db_organization:
        db.delete(db_organization)
        db.commit()
        return True
    return False


def create_user(db: Session, user: schemas.UserCreate):
    """
    Create a new user in the database.
    """
    db_user = models.User(
        full_name=user.full_name,
        username=user.username,
        password=user.password,
        email=user.email,
        organization_id=user.organization_id,
        role=user.role,
        is_active=user.is_active,
        user_id=uuid.uuid4()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: str):
    """
    Retrieve a user by their ID.
    """
    return db.query(models.User).filter(models.User.user_id == user_id).first()

def get_user_by_username(db: Session, username: str):
    """
    Retrieve a user by their username.
    """
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    Retrieve a list of users with pagination.
    """
    return db.query(models.User).offset(skip).limit(limit).all()

def update_user(db: Session, user_id: str, user: schemas.User):
    """
    Update an existing user by their ID.
    """
    db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if db_user:
        for key, value in user.dict(exclude_unset=True).items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
        return db_user
    return None

def delete_user(db: Session, user_id: str):
    """
    Delete a user by their ID.
    """
    db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False

def get_users_by_organization(db: Session, organization_id: str, skip: int = 0, limit: int = 100):
    """
    Retrieve a list of users by their organization ID with pagination.
    """
    return db.query(models.User).filter(models.User.organization_id == organization_id).offset(skip).limit(limit).all()