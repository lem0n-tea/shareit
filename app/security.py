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

def create_access_token_for_sub(sub: str) -> str:
    """Build an access token from a subject id directly (no DB/User object needed).
    Used by the refresh middleware, which only has the id from the refresh token."""
    payload = {
        "sub": sub,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload=payload, key=settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: models.User) -> str:
    return create_access_token_for_sub(str(subject.id))

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


def valid_token_sub(token: str | None, expected_type: str) -> str | None:
    """Return the token's `sub` if it is a valid, non-expired token of the expected
    type; otherwise None. Used by the refresh middleware to check cookies cheaply."""
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:  # covers expired + malformed
        return None
    if payload.get("type") != expected_type:
        return None
    return payload.get("sub")

async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    # Token source order: Authorization header (API clients) > a fresh token the
    # refresh middleware stashed on request.state for this request > the cookie.
    if creds:
        token = creds.credentials
    else:
        token = getattr(request.state, "access_token", None) or request.cookies.get("access_token")
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