from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

import config

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/account/token",
    auto_error=config.AUTH_REQUIRED,
)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now() + (
        expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)] = None) -> str:
    if not config.AUTH_REQUIRED:
        return "anonymous"
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError as exc:
        raise credentials_exception from exc


def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> str | None:
    if not config.AUTH_REQUIRED:
        return None
    if token is None:
        return None
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None
