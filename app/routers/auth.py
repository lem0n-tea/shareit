from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, models
from app.database import get_db
from app.security import hash_password, verify_password, create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    credentials: schemas.PasswordIn,
    db: Session = Depends(get_db)
):
    user = db.scalars(select(models.User)).first()
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
    user = db.scalars(select(models.User)).first()
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