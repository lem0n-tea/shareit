from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


# TODO (you): define the File model here, matching the schema we agreed on.
#
#   __tablename__ = "files"
#
#   id            integer, primary key, auto-increment
#   name          string, not null        -> original filename WITHOUT extension
#   extension     string, nullable        -> e.g. "jpg"; null/"unidentified" if unknown
#   content_type  string                  -> MIME type, set at upload
#   size          BigInteger, not null    -> size in bytes
#   uploaded_at   datetime, not null      -> let the DB set it: server_default=func.now()
#   path          string, not null        -> relative key / generated filename on disk
#
#   UNIQUE (name, extension)  ->  __table_args__ = (UniqueConstraint("name", "extension"),)
#
# Syntax reminders (from your SQLAlchemy work):
#   Column(Integer, primary_key=True)                 # auto-incrementing PK
#   Column(String, nullable=False)                    # NOT NULL
#   Column(DateTime, nullable=False, server_default=func.now())
#
# Write the class below, then follow the verification steps I gave you.
