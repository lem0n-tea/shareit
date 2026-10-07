import os, mimetypes, uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/files", tags=["files"])

# Where uploaded bytes live on disk: a configured, relative directory. 
# Created at import time so it always exists.
STORAGE_DIR = os.getenv("STORAGE_DIR", "./storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

@router.post("", response_model=schemas.FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
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

    filepath = uuid.uuid4().hex
    with open(os.path.join(STORAGE_DIR, filepath), 'wb') as f:
        f.write(contents)

    file = models.File(
        name=name,
        extension=extension,
        content_type=content_type,
        size=len(contents),
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
