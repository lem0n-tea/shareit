from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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

class FilePage(BaseModel):
    items: list[FileOut]
    total: int

class ClipboardIn(BaseModel):
    snippet: str = Field(max_length=10000, default="")

class ClipboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snippet: str
    updated_at: datetime | None

class PasswordIn(BaseModel):
    password: str = Field(min_length=8)

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RefreshIn(BaseModel):
    refresh_token: str