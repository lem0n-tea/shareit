from datetime import timezone

import jwt
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import icons, models
from app.config import settings
from app.database import get_db
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
)
from app.services import (
    get_file_list,
    get_file_or_404,
    get_usage,
    read_clipboard,
    remove_file,
    save_upload,
    set_clipboard,
)

router = APIRouter(tags=["web"])

# How many file rows one page (initial load or "load more") returns.
PAGE_SIZE = 10

# Templates live in app/templates. The path is relative to the process CWD, which is
# the project root locally and /app in the container -- both resolve to app/templates.
templates = Jinja2Templates(directory="app/templates")


def _utc_iso(dt) -> str:
    """Emit the timestamp as an ISO string EXPLICITLY marked UTC (+00:00). SQLite
    hands datetimes back naive, so we attach UTC; the browser then converts to the
    viewer's local timezone. Without the marker, JS would misread it as local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


templates.env.filters["utc_iso"] = _utc_iso


templates.env.filters["file_icon"] = icons.file_icon
templates.env.globals["icon"] = icons.icon


def _user_from_cookie(request: Request, db: Session) -> models.User | None:
    """Return the logged-in user from the access_token cookie, or None. Unlike
    get_current_user (which raises 401 for the API), web pages use this to decide
    whether to render or redirect to the login page."""
    # Prefer a fresh token the refresh middleware set on request.state this request;
    # otherwise the cookie.
    token = getattr(request.state, "access_token", None) or request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:  # covers expired + malformed
        return None
    if payload.get("type") != "access":
        return None
    return db.scalars(
        select(models.User).where(models.User.id == int(payload.get("sub")))
    ).first()


def _set_auth_cookies(response: Response, user: models.User) -> None:
    """Set the access + refresh tokens as hardened cookies.
    HttpOnly: unreadable by JS (resists XSS token theft).
    Secure: only ever sent over HTTPS.
    SameSite=lax: not sent on cross-site POSTs (CSRF protection).
    max_age: matched to each token's own expiry so they die together."""
    response.set_cookie(
        "access_token", create_access_token(user),
        httponly=True, secure=True, samesite="lax", path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        "refresh_token", create_refresh_token(user),
        httponly=True, secure=True, samesite="lax", path="/",
        max_age=settings.refresh_token_expire_days * 86400,
    )


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = _user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    # First page, default sort (newest first). Fetch one extra to know if more remain.
    files, _ = await get_file_list(
        db, sort="uploaded_at", direction="desc",
        after_value=None, after_id=None, limit=PAGE_SIZE + 1,
    )
    has_more = len(files) > PAGE_SIZE
    files = files[:PAGE_SIZE]
    clipboard = read_clipboard(db)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "files": files, "has_more": has_more,
            "clipboard": clipboard, "max_upload_size": settings.max_upload_size,
        },
    )


@router.get("/files-page", response_class=HTMLResponse)
async def files_page(
    request: Request,
    sort: str = "uploaded_at",
    direction: str = "desc",
    after_value: str | None = None,
    after_id: int | None = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Next page of file rows for the client's keyset "load more" / re-sort.
    Returns just the <tr> rows; X-Has-More tells the client whether to keep the button."""
    files, _ = await get_file_list(
        db, sort=sort, direction=direction,
        after_value=after_value, after_id=after_id, limit=PAGE_SIZE + 1,
    )
    has_more = len(files) > PAGE_SIZE
    files = files[:PAGE_SIZE]
    resp = templates.TemplateResponse(request, "_rows.html", {"files": files})
    resp.headers["X-Has-More"] = "1" if has_more else "0"
    return resp


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalars(select(models.User)).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Wrong password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    # Post/Redirect/Get: redirect after a successful POST, setting cookies on the way.
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    _set_auth_cookies(response, user)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response


@router.post("/upload")
async def web_upload(
    request: Request,
    upload: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Let save_upload's HTTPException (409/413/507) propagate with its real status and
    # detail; the client's upload queue reads them and shows the error against the file.
    file = await save_upload(upload, db, request.headers.get("content-length"))
    # Success: render just the new <tr>; the client prepends it to the table body. The
    # HX-Trigger header fires a "filesChanged" event so the storage bar refreshes.
    resp = templates.TemplateResponse(request, "_row.html", {"file": file})
    resp.headers["HX-Trigger"] = "filesChanged"
    return resp


@router.get("/usage", response_class=HTMLResponse)
def usage(
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    used, capacity = get_usage(db)
    return templates.TemplateResponse(
        request, "_storage.html", {"used": used, "capacity": capacity}
    )


@router.delete("/delete/{file_id}")
def web_delete(
    file_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    remove_file(get_file_or_404(file_id, db), db)
    # Empty 200 (not 204) so HTMX performs the swap and removes the row; HX-Trigger
    # refreshes the storage bar.
    resp = Response(status_code=status.HTTP_200_OK)
    resp.headers["HX-Trigger"] = "filesChanged"
    return resp


@router.post("/clip", response_class=HTMLResponse)
def web_set_clipboard(
    request: Request,
    snippet: str = Form(""),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Truncate as a server-side backstop to the textarea's maxlength.
    clipboard = set_clipboard(snippet[:10000], db)
    return templates.TemplateResponse(request, "_clipboard.html", {"clipboard": clipboard})
