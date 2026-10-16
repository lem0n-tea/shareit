"""Shared file-handling logic, used by BOTH the JSON API (routers/files.py) and the
web UI (routers/web.py). Keeping it here means the quota/consistency rules live in one
place; each router just differs in what it returns (JSON vs HTML)."""
import mimetypes
import os
import shutil
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings

# Where uploaded bytes live on disk. Created at import so it always exists.
STORAGE_DIR = settings.storage_dir
os.makedirs(STORAGE_DIR, exist_ok=True)

# Capacity: the configured limit, or the whole disk if none is set.
STORAGE_LIMIT = settings.storage_limit or shutil.disk_usage(STORAGE_DIR).total


async def save_upload(
    upload: UploadFile, db: Session, content_length: str | None = None
) -> models.File:
    """Stream the upload to disk in 1 MB chunks (never loading the whole file into
    memory), enforcing the per-file cap and the storage quota as it goes. Writes the
    file first, then commits the row; cleans up the file on any failure."""
    disk_free_space = shutil.disk_usage(STORAGE_DIR).free
    current_storage_size = db.scalar(select(func.sum(models.File.size))) or 0
    available_space = min(disk_free_space, STORAGE_LIMIT - current_storage_size)
    max_size = settings.max_upload_size
    too_big = f"File exceeds the {max_size // 1024**3} GB limit"

    # Fast reject using the declared size, before streaming a single byte.
    if content_length:
        declared = int(content_length)
        if declared > max_size:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, too_big)
        if declared > available_space:
            raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "Not enough free space")

    name, extension = os.path.splitext(upload.filename or "")
    extension = extension[1:].lower() or None
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A filename is required")

    content_type = upload.content_type
    if not content_type or content_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        content_type = guessed or "application/octet-stream"

    filepath = uuid.uuid4().hex
    dest = os.path.join(STORAGE_DIR, filepath)
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)  # 1 MB at a time
                if not chunk:
                    break
                size += len(chunk)
                # Enforce the limits even if Content-Length was absent or lied.
                if size > max_size:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, too_big)
                if size > available_space:
                    raise HTTPException(
                        status.HTTP_507_INSUFFICIENT_STORAGE, "Not enough free space"
                    )
                out.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            os.remove(dest)
        raise
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "File upload failed") from e

    file = models.File(
        name=name, extension=extension, content_type=content_type,
        size=size, path=filepath,
    )
    try:
        db.add(file)
        db.commit()
    except IntegrityError:
        db.rollback()
        os.remove(dest)
        raise HTTPException(status.HTTP_409_CONFLICT, "Such file already exists")
    except Exception as e:
        db.rollback()
        os.remove(dest)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "File upload failed") from e

    db.refresh(file)
    return file


def get_usage(db: Session) -> tuple[int, int]:
    """Return (bytes used, capacity). Capacity is the stable denominator for the bar."""
    used = db.scalar(select(func.sum(models.File.size))) or 0
    return used, STORAGE_LIMIT


def read_clipboard(db: Session) -> models.Clipboard | None:
    return db.scalars(select(models.Clipboard)).first()


def set_clipboard(snippet: str, db: Session) -> models.Clipboard:
    """Upsert the single clipboard row (portable ORM update → onupdate refreshes the time)."""
    row = db.scalars(select(models.Clipboard)).first()
    if row is None:
        row = models.Clipboard(snippet=snippet)
        db.add(row)
    else:
        row.snippet = snippet
    db.commit()
    db.refresh(row)
    return row


def get_file_or_404(file_id: int, db: Session) -> models.File:
    file = db.scalars(select(models.File).where(models.File.id == file_id)).first()
    if not file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return file


def remove_file(file: models.File, db: Session) -> None:
    """Delete the row first (what the user sees), then best-effort remove the bytes."""
    db.delete(file)
    db.commit()
    try:
        filepath = os.path.join(STORAGE_DIR, file.path)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass
