import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.config import settings


# auto_error=False: a missing Authorization header must NOT auto-reject, because the
# web UI authenticates via a cookie instead. We decide below.
bearer_scheme = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    password_bytes = password.encode()
    return bcrypt.hashpw(password=password_bytes, salt=bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

def create_access_token(subject: models.User) -> str:
    payload = {
        "sub": str(subject.id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access"
    }
    return jwt.encode(
        payload=payload,
        key=settings.secret_key,
        algorithm=settings.algorithm
    )

def create_refresh_token(subject: models.User) -> str:
    payload = {
        "sub": str(subject.id),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        "type": "refresh"
    }
    return jwt.encode(
        payload=payload,
        key=settings.secret_key,
        algorithm=settings.algorithm
    )

def decode_token(token: str) -> dict:
    return jwt.decode(
        jwt=token,
        key=settings.secret_key,
        algorithms=[settings.algorithm,]
    )

async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    # Accept the token from the Authorization header (JSON API / native clients) OR
    # from an access_token cookie (the web UI). Header takes precedence if present.
    token = creds.credentials if creds else request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong credentials"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong credentials"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth failed"
        ) from e

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong credentials"
        )

    user = db.scalars(select(models.User).where(models.User.id == int(payload.get("sub")))).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong credentials"
        )
    
    return user