import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# The ONE place the database engine is chosen. This is what makes the future
# SQLite -> PostgreSQL swap a single-line change: later you set DATABASE_URL to
# something like "postgresql+psycopg2://user:password@host/dbname" and nothing
# else in the app needs to know.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shareit.db")

# SQLite-only wrinkle: by default SQLite refuses to be used from more than one
# thread, but FastAPI serves requests from a threadpool. This arg relaxes that.
# Other engines (Postgres) must NOT receive it, so we add it only for SQLite.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# The engine is the low-level connection manager to the database.
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# A "session" is one unit of work / conversation with the DB. SessionLocal is a
# factory: call SessionLocal() to get a fresh session. We turn autocommit/autoflush
# off so writes happen only when we explicitly commit.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Every ORM model class will inherit from Base. Base collects all your table
# definitions so that Base.metadata.create_all(...) knows what tables to create.
Base = declarative_base()


def get_db():
    """FastAPI dependency: give an endpoint a DB session, then always close it
    when the request finishes (even if the endpoint raises an error)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
