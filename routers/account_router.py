from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from auth.authentication import oauth2_scheme, get_current_user, create_access_token
from database.models import User
from database import schemas, models, account_crud
from database.database import SessionLocal, engine, get_db

models.Base.metadata.create_all(bind=engine)

router = APIRouter()

@router.post("/token", summary="Generate JWT Token",
            description="Generate a JWT token for the user.")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Generate a JWT token for the user.
    """
    user = account_crud.get_user_by_username(db=db, username=form_data.username)
    if user is None or user.password != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/protected", summary="Protected Route",
            description="A protected route that requires a valid JWT token.")
async def protected_route(current_user: str = Depends(get_current_user)):
    return {"message": "This is a protected route", "user": current_user}


@router.get("/users", summary="List users")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    users = account_crud.get_users(db=db, skip=skip, limit=limit)
    return {
        "results": [
            {
                "id": user.id,
                "user_id": user.user_id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "organization_id": user.organization_id,
                "role": user.role,
                "is_active": user.is_active,
            }
            for user in users
        ],
        "count": len(users),
    }


@router.get("/organizations", summary="List organizations")
async def list_organizations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    organizations = account_crud.get_organizations(db=db, skip=skip, limit=limit)
    return {
        "results": [
            {
                "id": org.id,
                "organization_id": org.organization_id,
                "name": org.name,
                "description": org.description,
                "contact_email": org.contact_email,
                "organization_type": org.organization_type,
            }
            for org in organizations
        ],
        "count": len(organizations),
    }


@router.post("/user/create", summary="Create a new user",
            description="Create a new user in the database.")
async def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user in the database.
    """
    db_user = account_crud.create_user(db=db, user=user)
    if db_user is None:
        raise HTTPException(status_code=400, detail="User already exists")
    return {"message": "User created successfully",
            "user": db_user.username}

@router.get("/user/{user_id}", summary="Get user by ID",
            description="Get user details by user ID.")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get user details by user ID.
    """
    db_user = account_crud.get_user(db=db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.post("/organization/create", summary="Create a new organization",
            description="Create a new organization in the database.")
async def create_organization(organization: schemas.OrganizationCreate, db: Session = Depends(get_db)):
    """
    Create a new organization in the database.
    """
    db_organization = account_crud.create_organization(db=db, organization=organization)
    if db_organization is None:
        raise HTTPException(status_code=400, detail="Organization already exists")
    return {"message": "Organization created successfully",
            "organization": db_organization.name}

@router.get("/organization/{organization_id}", summary="Get organization by ID",
            description="Get organization details by organization ID.")
async def get_organization(organization_id: int, db: Session = Depends(get_db)):
    """
    Get organization details by organization ID.
    """
    db_organization = account_crud.get_organization(db=db, organization_id=organization_id)
    if db_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return db_organization
