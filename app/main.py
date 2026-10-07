from fastapi import FastAPI

from app.database import Base, engine

# Importing models registers your tables on Base.metadata. WITHOUT this import,
# SQLAlchemy would not know the "files" table exists, and create_all would make
# nothing.
from app import models  # noqa: F401

# Create any missing tables at startup. This is fine for development. For real
# schema *changes* later (adding/altering columns on an existing DB), you'd switch
# to migrations with Alembic -- a roadmap item, not needed yet.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shareit")


@app.get("/health")
def health():
    """A trivial endpoint so you can confirm the server is actually running."""
    return {"status": "ok"}
