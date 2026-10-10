import bcrypt
import jwt

from datetime import datetime, timedelta, timezone

from app import models
from app.config import settings


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