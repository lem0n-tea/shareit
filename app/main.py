from fastapi import FastAPI, Request, Response

from app.config import settings
from app.database import Base, engine
from app.routers import files, auth, web, clipboard
from app.security import create_access_token_for_sub, valid_token_sub

# Importing models registers your tables on Base.metadata. WITHOUT this import,
# SQLAlchemy would not know the "files" table exists, and create_all would make
# nothing.
from app import models

# Create any missing tables at startup. This is fine for development. For real
# schema *changes* later (adding/altering columns on an existing DB), you'd switch
# to migrations with Alembic -- a roadmap item, not needed yet.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shareit")


@app.middleware("http")
async def refresh_access_cookie(request: Request, call_next):
    """Silently refresh the web UI's access cookie. If the access_token cookie is
    missing/expired but the refresh_token cookie is still valid, mint a new access
    token: stash it on request.state so THIS request authenticates, and set it as a
    cookie so FUTURE requests carry it. Bearer-header (API) requests send no cookies,
    so this is a no-op for them."""
    new_access = None
    if valid_token_sub(request.cookies.get("access_token"), "access") is None:
        sub = valid_token_sub(request.cookies.get("refresh_token"), "refresh")
        if sub is not None:
            new_access = create_access_token_for_sub(sub)
            request.state.access_token = new_access

    response = await call_next(request)

    if new_access:
        response.set_cookie(
            "access_token", new_access,
            httponly=True, secure=True, samesite="lax", path="/",
            max_age=settings.access_token_expire_minutes * 60,
        )
    return response


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Reject oversized uploads at the edge, BEFORE FastAPI parses the body (which
    would otherwise receive and spool the whole file to a temp dir first). The web UI
    also pre-checks file size in the browser, so this mainly guards non-browser or
    JS-bypassed requests."""
    cl = request.headers.get("content-length")
    if cl and int(cl) > settings.max_upload_size:
        return Response(
            f"File exceeds the {settings.max_upload_size // 1024**3} GB limit",
            status_code=413,
        )
    return await call_next(request)


# Mount the files router. Its routes live under the prefix it declares ("/files").
app.include_router(files.router)

app.include_router(clipboard.router)

app.include_router(auth.router)

# The web UI (HTML pages + HTMX), served by the same app.
app.include_router(web.router)


@app.get("/health")
def health():
    """A trivial endpoint so you can confirm the server is actually running."""
    return {"status": "ok"}
