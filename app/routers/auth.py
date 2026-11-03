import jwt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, models
from app.database import get_db
from app.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.services import get_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    credentials: schemas.PasswordIn,
    db: Session = Depends(get_db)
):
    user = get_user(db)
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password has already been set"
        )

    user = models.User(
        password_hash=hash_password(credentials.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = schemas.TokenOut(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user)
    )

    return token

@router.post("/login", response_model=schemas.TokenOut, status_code=status.HTTP_200_OK)
async def login_user(
    credentials: schemas.PasswordIn,
    db: Session = Depends(get_db)
):
    user = get_user(db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong credentials"
        )

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong credentials"
        )

    token = schemas.TokenOut(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user)
    )

    return token

@router.post("/refresh", response_model=schemas.AccessTokenOut, status_code=status.HTTP_200_OK)
async def refresh_access_token(
    body: schemas.RefreshIn,
    db: Session = Depends(get_db)
):
    try:
        payload = decode_token(body.refresh_token)
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

    if payload.get("type") != "refresh":
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

    new_access_token = schemas.AccessTokenOut(
        access_token=create_access_token(user)
    )
    return new_access_token