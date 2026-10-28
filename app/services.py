"""Shared file-handling logic, used by BOTH the JSON API (routers/files.py) and the
web UI (routers/web.py). Keeping it here means the quota/consistency rules live in one
place; each router just differs in what it returns (JSON vs HTML)."""
import asyncio
import hashlib
import mimetypes
import os
import shutil
import uuid
import operator
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select, tuple_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.config import settings

# Where uploaded bytes live on disk. Created at import so it always exists.
STORAGE_DIR = settings.storage_dir
os.makedirs(STORAGE_DIR, exist_ok=True)

PENDING_UPLOADS_DIR = settings.pending_uploads_dir
os.makedirs(PENDING_UPLOADS_DIR, exist_ok=True)

# Capacity: the configured limit, or the whole disk if none is set.
STORAGE_LIMIT = settings.storage_limit or shutil.disk_usage(STORAGE_DIR).total

SORT_COLUMNS = {
    "name": models.File.name,
    "type": func.coalesce(models.File.extension, ""),
    "size": models.File.size,
    "uploaded_at": models.File.uploaded_at
}
TYPE_CAST_MAP = {
    "name": str,
    "type": str,
    "size": int,
    "uploaded_at": datetime.fromisoformat
}

async def save_upload(
    upload: UploadFile, db: Session, content_length: str | None = None
) -> models.File:
    """Stream the upload to disk in 1 MB chunks (never loading the whole file into
    memory), enforcing the per-file cap and the storage quota as it goes. Writes the
    file first, then commits the row; cleans up the file on any failure."""  
    available_disk_space = get_available_space(db)
   
    max_size = settings.max_upload_size
    too_big = f"File exceeds the {max_size // 1024**3} GB limit"

    # Fast reject using the declared size, before streaming a single byte.
    if content_length:
        declared = int(content_length)
        if declared > max_size:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, too_big)
        if declared > available_disk_space:
            if reap_stale_uploads(db) > 0:
                available_disk_space = get_available_space(db) 
            if declared > available_disk_space:
                raise HTTPException(
                    status.HTTP_507_INSUFFICIENT_STORAGE, "Not enough free space"
                )

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
                if size > available_disk_space:
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

def get_available_space(db: Session) -> int:
    current_storage_size = db.scalar(select(func.sum(models.File.size))) or 0
    reserved_space = db.scalar(select(func.sum(models.Upload.total_size))
                            .where(or_(
                                models.Upload.status == models.UploadStatus.IN_PROGRESS,
                                models.Upload.status == models.UploadStatus.FINALIZING
                            ))) or 0
    used_disk_space = current_storage_size + reserved_space

    disk_free_space = shutil.disk_usage(STORAGE_DIR).free

    return min(disk_free_space, STORAGE_LIMIT - used_disk_space)

def save_manifest(
    db: Session,
    *,
    filename: str,
    content_type: str,
    total_size: int,
    total_num_chunks: int
) -> models.Upload:
    if total_size > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size // 1024**3} GB limit"
        )

    name, extension = os.path.splitext(filename or "")
    extension = extension[1:].lower() or None
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A filename is required")

    same_filename = db.scalars(select(models.File).where(models.File.name == name, models.File.extension == extension)).first()
    if same_filename:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Such file already exists"
        )

    available_disk_space = get_available_space(db)
    
    if total_size > available_disk_space:
        if reap_stale_uploads(db) > 0:
            available_disk_space = get_available_space(db) 
        if total_size > available_disk_space:
            raise HTTPException(
                status.HTTP_507_INSUFFICIENT_STORAGE, "Not enough free space"
            )
            

    while True:
        try:
            upload_uuid = uuid.uuid4().hex
            os.makedirs(os.path.join(PENDING_UPLOADS_DIR, upload_uuid))
            break
        except FileExistsError:
            continue

    upload = models.Upload(
        uuid=upload_uuid,
        name=name,
        extension=extension,
        content_type=content_type,
        total_size=total_size,
        total_num_chunks=total_num_chunks
    )
    try:
        db.add(upload)
        db.commit()
    except Exception as e:
        db.rollback()
        os.rmdir(os.path.join(PENDING_UPLOADS_DIR, upload_uuid))
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Upload initialization failed") from e

    db.refresh(upload)
    return upload

async def write_chunk(db: Session, *, upload_uuid: str, position: int, body: UploadFile) -> int:
    pending_upload = db.scalars(select(models.Upload).where(models.Upload.uuid == upload_uuid)).first()
    if pending_upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found"
        )
    if pending_upload.status != models.UploadStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All declared chunks have been received"
        )

    if position < 0 or position > pending_upload.total_num_chunks - 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chunk position is out of range for the declared upload"
        )

    dest = os.path.join(PENDING_UPLOADS_DIR, upload_uuid, str(position))
    size = 0
    try:
        received_chunks = [p for p in Path(os.path.join(PENDING_UPLOADS_DIR, upload_uuid)).iterdir() 
                               if p.is_file() and p.name != str(position)]
        received_size = sum(p.stat().st_size for p in received_chunks )
        
        with open(dest, "wb") as out:
            while True:
                chunk = await body.read(1024 * 1024)  # 1 MB at a time
                if not chunk:
                    break
                size += len(chunk)
                if received_size + size > pending_upload.total_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Chunks exceed declared total size"
                    )
                out.write(chunk)

        last_activity = pending_upload.last_activity.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - last_activity).total_seconds() > 60:
            pending_upload.last_activity = datetime.now(timezone.utc)
            db.commit()

    except HTTPException:
        if os.path.exists(dest):
            os.remove(dest)
        raise
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Chunk upload failed") from e

    return position

def get_received_chunks(upload_uuid: str) -> list[int]:
    try:
        files = [p for p in Path(os.path.join(PENDING_UPLOADS_DIR, upload_uuid)).iterdir() if p.is_file()]
        return [int(f.name) for f in files]
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to read received chunks") from e

async def finalize_upload(db: Session, *, upload_uuid: str, client_checksum: str) -> models.File:
    pending_upload = db.scalars(select(models.Upload).where(models.Upload.uuid == upload_uuid)).first()
    if pending_upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found"
        )
    
    if pending_upload.status != models.UploadStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload finalization have already been initiated"
        )
    pending_upload.status = models.UploadStatus.FINALIZING
    pending_upload.last_activity = datetime.now(timezone.utc)
    db.commit()

    upload_dir = os.path.join(PENDING_UPLOADS_DIR, upload_uuid)

    # Parts are still intact here, so an incomplete upload can resume
    received_chunks = sorted(get_received_chunks(upload_uuid))
    if received_chunks != list(range(pending_upload.total_num_chunks)):
        pending_upload.status = models.UploadStatus.IN_PROGRESS
        pending_upload.last_activity = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload is incomplete"
        )

    # Stream the parts in order into one file, hashing as we go and deleting each part
    # once copied. Past this point the parts are consumed, so any failure means
    # the upload can no longer resume
    hasher = hashlib.sha256()
    filepath = uuid.uuid4().hex
    dest = os.path.join(STORAGE_DIR, filepath)
    size = 0
    try:
        with open(dest, "wb") as out:
            for part in received_chunks:
                source = os.path.join(upload_dir, str(part))
                with open(source, "rb") as f:
                    while chunk := f.read(1024 * 1024):
                        size += len(chunk)
                        out.write(chunk)
                        hasher.update(chunk)
                os.remove(source)
    except Exception as e:
        _abandon_upload(db, pending_upload, upload_dir, dest)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Finalization failed") from e

    # Integrity check: a mismatch means the reassembly is wrong
    # The parts are gone, so abandon and let the client retry.
    if hasher.hexdigest() != client_checksum.strip().lower():
        _abandon_upload(db, pending_upload, upload_dir, dest)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expected and received checksums mismatch"
        )

    # Commit the real file and drop the upload row in one transaction
    file = models.File(
        name=pending_upload.name, extension=pending_upload.extension,
        content_type=pending_upload.content_type, size=size, path=filepath,
    )
    db.add(file)
    db.delete(pending_upload)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _abandon_upload(db, pending_upload, upload_dir, dest)
        raise HTTPException(status.HTTP_409_CONFLICT, "Such file already exists")
    except Exception as e:
        db.rollback()
        _abandon_upload(db, pending_upload, upload_dir, dest)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Finalization failed") from e

    db.refresh(file)
    # Parts already removed during assembly; drop the empty upload dir
    shutil.rmtree(upload_dir, ignore_errors=True)
    return file


def _abandon_upload(db: Session, upload: models.Upload, upload_dir: str, dest: str) -> None:
    """Give up on an upload that can no longer be resumed: remove the assembled file and
    any remaining parts, and delete the upload row so its reserved quota is released."""
    if os.path.exists(dest):
        os.remove(dest)
    shutil.rmtree(upload_dir, ignore_errors=True)
    try:
        db.delete(upload)
        db.commit()
    except Exception:
        db.rollback()
    

def get_missing_chunks(db: Session, upload_uuid: str) -> list[int]:
    pending_upload = db.scalars(select(models.Upload).where(models.Upload.uuid == upload_uuid)).first()
    if pending_upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found"
        )
    
    received_chunks = set(get_received_chunks(upload_uuid))
    expected_chunks = set(range(pending_upload.total_num_chunks))

    return sorted(list(expected_chunks - received_chunks))

def reap_stale_uploads(db: Session) -> int:
    stale_uploads = db.scalars(select(models.Upload)
                               .where(
                                   (models.Upload.last_activity < datetime.now(timezone.utc) - timedelta(seconds=settings.upload_stale_after_seconds)),
                                   models.Upload.status.in_([models.UploadStatus.IN_PROGRESS, models.UploadStatus.FINALIZING])
                               )).all()
    reap_count = 0
    for upload in stale_uploads:
        try:
            upload_path = os.path.join(PENDING_UPLOADS_DIR, upload.uuid)
            if os.path.exists(upload_path):
                shutil.rmtree(upload_path)

            db.delete(upload)
            db.commit()
            reap_count += 1
        except Exception as e:
            db.rollback()
            continue
    
    return reap_count

async def periodic_reaper():
    while True:
        try:
            db = SessionLocal()
            try:
                await asyncio.to_thread(reap_stale_uploads, db)
            finally:
                db.close()
        except Exception:
            pass
        await asyncio.sleep(settings.periodic_reap_interval_seconds)

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

async def get_file_list(db: Session, *, sort: str, direction: str,
                        after_value=None, after_id=None, limit: int) -> tuple[list[models.File], int]:
    if SORT_COLUMNS.get(sort) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort column name"
        )

    sort_column = SORT_COLUMNS.get(sort)
    sort_id = models.File.id

    if direction.lower() == "asc":
        order_column = sort_column.asc()
        order_id = sort_id.asc()
        op = operator.gt
    elif direction.lower() == "desc":
        order_column = sort_column.desc()
        order_id = sort_id.desc()
        op = operator.lt
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ordering direction"
        )

    stmt = select(models.File).order_by(order_column, order_id).limit(limit)

    if after_value is not None and after_id is not None:
        try:
            after_value = TYPE_CAST_MAP.get(sort)(after_value)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"after_value is not a valid {sort} value"
            )
        
        stmt = stmt.where(op(tuple_(sort_column, sort_id), (after_value, after_id)))

    files = db.scalars(stmt).all()
    total = db.scalar(select(func.count(models.File.id)))

    return files, total

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

def remove_files(file_ids: list[int], db: Session) -> int:
    deleted_count = 0
    for file_id in file_ids:
        file = db.scalars(select(models.File).where(models.File.id == file_id)).first()
        if file is None:
            continue

        remove_file(file, db)
        deleted_count += 1

    return deleted_count