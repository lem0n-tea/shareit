import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user
from app.services import STORAGE_DIR, get_file_list, get_file_or_404, remove_file, remove_files, save_upload

router = APIRouter(
    prefix="/files", tags=["files"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=schemas.FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await save_upload(upload, db, request.headers.get("content-length"))


@router.get("/{file_id}/download", response_class=FileResponse)
async def download_file(file_id: int, db: Session = Depends(get_db)):
    file = get_file_or_404(file_id, db)
    filepath = os.path.join(STORAGE_DIR, file.path)
    if not os.path.exists(filepath):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "File missing on disk"
        )
    filename = f"{file.name}.{file.extension}" if file.extension else file.name
    return FileResponse(path=filepath, filename=filename, media_type=file.content_type)

@router.get("", response_model=schemas.FilePage)
async def list_files(
    db: Session = Depends(get_db),
    sort: Literal["name", "type", "size", "uploaded_at"] = "uploaded_at",
    direction: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(gt=1, le=100)] = 10,
    after_value: str | None = None,
    after_id: int | None = None
):
    if (after_value is None) != (after_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="after_value and after_id must be set together"
        )

    files, total = await get_file_list(
        db,
        sort=sort,
        direction=direction,
        after_value=after_value,
        after_id=after_id,
        limit=limit,
    )

    return schemas.FilePage(
        items=files,
        total=total
    )

@router.delete("", status_code=status.HTTP_200_OK)
async def delete_files_bulk(
    ids: Annotated[list[int], Query()],
    db: Session = Depends(get_db)
) -> dict:
   count = remove_files(ids, db)
   return {"deleted": count}

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    remove_file(get_file_or_404(file_id, db), db)
