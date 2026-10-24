import enum
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UploadStatus(enum.Enum):
    IN_PROGRESS = "in_progress"
    FINALIZING = "finalizing"
    DONE = "done"

class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("name", "extension", name="uq_file_name_extension"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    extension: Mapped[str | None] = mapped_column(String(30))
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False) 

class Upload(Base):
    __tablename__ = "uploads"

    uuid: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False, default=lambda: uuid4().hex)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    extension: Mapped[str | None] = mapped_column(String(30))
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_num_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[UploadStatus] = mapped_column(default=UploadStatus.IN_PROGRESS, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class Clipboard(Base):
    __tablename__ = "clipboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snippet: Mapped[str] = mapped_column(Text(10000), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=lambda: datetime.now(timezone.utc),
                                                 onupdate=lambda: datetime.now(timezone.utc))

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False) 