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
    filename, extension = os.path.splitext(upload.filename or "")
    extension = extension[1:].lower() or None

    if not filename:
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
        name=filename,
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
    except:
        db.rollback()
        os.remove(os.path.join(STORAGE_DIR, filepath))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )

    db.refresh(file)
    return file

    """TODO (you): implement the upload flow we designed.

    The steps (as you restated them), plus the failure handling:
      1. Read the raw bytes from `upload`.
      2. Derive from the ORIGINAL filename: name (without extension) + extension.
         Compute size from the bytes. Determine content_type (use what the client
         sent, else derive from the extension, else a generic fallback).
      3. Generate a unique on-disk name -> this becomes the row's `path`.
      4. Write the bytes to disk FIRST.
      5. Create the models.File row, add it, and commit.
         - If the commit fails because of the UNIQUE(name, extension) constraint,
           roll back, DELETE the file you just wrote, and return 409 Conflict.
         - If it fails for any other reason after the disk write, also delete the file.
      6. Refresh the row and return it (FastAPI will shape it into FileOut).

    Tools you'll reach for (look up any you haven't used):
      await upload.read()         upload.filename        upload.content_type
      os.path.splitext(...)       uuid.uuid4().hex       mimetypes.guess_type(...)
      open(path, "wb")           os.path.join(STORAGE_DIR, ...)   os.remove(...)
      db.add(obj) / db.commit() / db.refresh(obj) / db.rollback()
      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="...")
      except IntegrityError:      # raised on the duplicate

    Write it below, replacing this raise.
    """
    raise NotImplementedError
