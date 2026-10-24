"""JSON API for resumable (chunked) uploads — the thin HTTP layer over the upload
services in app/services.py. Four steps, all cookie-or-Bearer authed like /files:

  POST   /uploads                         -> manifest: declare the file, get a uuid
  PUT    /uploads/{uuid}/chunks/{pos}     -> send one chunk (idempotent, overwrites)
  GET    /uploads/{uuid}                  -> resume: which chunk positions are missing
  POST   /uploads/{uuid}/finalize         -> verify + assemble -> the finished File

The services hold all the rules (quota reservation, running-total guard, assembly,
checksum, cleanup); each handler just wires request -> service -> response."""
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.security import get_current_user
from app.services import (
    finalize_upload,
    get_missing_chunks,
    save_manifest,
    write_chunk,
)

router = APIRouter(
    prefix="/uploads", tags=["uploads"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=schemas.UploadOut, status_code=status.HTTP_201_CREATED)
def create_manifest(manifest: schemas.ManifestIn, db: Session = Depends(get_db)):
    """Run the up-front guards, reserve the quota, and return the new upload's uuid."""
    return save_manifest(
        db,
        filename=manifest.filename,
        content_type=manifest.content_type,
        total_size=manifest.total_size,
        total_num_chunks=manifest.total_num_chunks,
    )


@router.put("/{upload_uuid}/chunks/{position}")
async def upload_chunk(
    upload_uuid: str,
    position: int,
    chunk: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Store one chunk at its position (re-sending the same position overwrites it)."""
    received = await write_chunk(db, upload_uuid=upload_uuid, position=position, body=chunk)
    return {"position": received}


@router.get("/{upload_uuid}")
def resume_query(upload_uuid: str, db: Session = Depends(get_db)) -> dict:
    """Which positions the server is still missing, so the client resends only the gaps."""
    return {"missing": get_missing_chunks(db, upload_uuid)}


@router.post(
    "/{upload_uuid}/finalize",
    response_model=schemas.FileOut,
    status_code=status.HTTP_201_CREATED,
)
async def finalize(
    upload_uuid: str,
    body: schemas.FinalizeIn,
    db: Session = Depends(get_db),
):
    """Assemble the parts, verify the checksum, and commit the finished File."""
    return await finalize_upload(db, upload_uuid=upload_uuid, client_checksum=body.checksum)
