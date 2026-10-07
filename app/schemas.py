from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    """The public shape of a file, sent back to the client."""

    # from_attributes=True lets FastAPI build this straight from a SQLAlchemy ORM
    # object (it reads the attributes off the models.File row).
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    extension: str | None
    content_type: str
    size: int
    uploaded_at: datetime
