from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas, models
from app.database import get_db
from app.security import get_current_user
from app.services import read_clipboard, set_clipboard


router = APIRouter(prefix="/clipboard", tags=["clipboard"], dependencies=[Depends(get_current_user)])

@router.put("", response_model=schemas.ClipboardOut, status_code=status.HTTP_200_OK)
async def share_clipboard(
    clipboard: schemas.ClipboardIn,
    db: Session = Depends(get_db)
):
    return set_clipboard(clipboard.snippet, db)


@router.get("", response_model=schemas.ClipboardOut, status_code=status.HTTP_200_OK)
async def get_clipboard(
    db: Session = Depends(get_db)
):
    return read_clipboard(db) or schemas.ClipboardOut(snippet="", updated_at=None)
    