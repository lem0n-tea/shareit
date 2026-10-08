import os, mimetypes, uuid, shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/files", tags=["files"])

# Where uploaded bytes live on disk: a configured, relative directory. 
# Created at import time so it always exists.
STORAGE_DIR = settings.storage_dir
os.makedirs(STORAGE_DIR, exist_ok=True)

STORAGE_LIMIT = settings.storage_limit or shutil.disk_usage(STORAGE_DIR).total

@router.post("", response_model=schemas.FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    disk_free_space = shutil.disk_usage(STORAGE_DIR).free
    current_storage_size = db.query(func.sum(models.File.size)).scalar() or 0

    available_space = min(disk_free_space, STORAGE_LIMIT - current_storage_size)

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > available_space:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Not enough free space"
        )
        
    name, extension = os.path.splitext(upload.filename or "")
    extension = extension[1:].lower() or None

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required"
        )

    content_type = upload.content_type
    if not content_type or content_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        content_type = guessed or "application/octet-stream"
 
    contents = await upload.read()
    size = len(contents)

    if size > available_space:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Not enough free space"
        )

    filepath = uuid.uuid4().hex
    with open(os.path.join(STORAGE_DIR, filepath), 'wb') as f:
        f.write(contents)

    file = models.File(
        name=name,
        extension=extension,
        content_type=content_type,
        size=size,
        path=filepath
    )

    try:
        db.add(file)
        db.commit()
    except IntegrityError:
        db.rollback()
        os.remove(os.path.join(STORAGE_DIR, filepath))

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Such file already exists"
        )
    except Exception as e:
        db.rollback()
        os.remove(os.path.join(STORAGE_DIR, filepath))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        ) from e

    db.refresh(file)
    return file

@router.get("", response_model=list[schemas.FileOut], status_code=status.HTTP_200_OK)
async def list_files(
    db: Session = Depends(get_db)
):
    return db.scalars(select(models.File)).all()
