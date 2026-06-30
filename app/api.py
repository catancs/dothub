from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_session
from .models import User, ApiKey
from . import bundle, security, setups

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

class SignupIn(BaseModel):
    username: str
    email: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class KeyIn(BaseModel):
    label: str = ""

class PublishIn(BaseModel):
    title: str
    description: str = ""
    slug: str | None = None
    files: dict[str, str]

def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    # 1) Bearer API key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        kh = security.hash_api_key(auth.split(" ", 1)[1].strip())
        ak = db.scalar(select(ApiKey).where(ApiKey.key_hash == kh))
        if ak:
            return db.get(User, ak.user_id)
    # 2) session cookie
    uid = request.session.get("uid")
    if uid:
        u = db.get(User, uid)
        if u:
            return u
    raise HTTPException(status_code=401, detail="authentication required")

@router.post("/api/signup")
def signup(body: SignupIn, request: Request, db: Session = Depends(get_session)):
    exists = db.scalar(select(User).where((User.username == body.username) | (User.email == body.email)))
    if exists:
        raise HTTPException(status_code=400, detail="username or email taken")
    u = User(username=body.username, email=body.email,
             password_hash=security.hash_password(body.password))
    db.add(u); db.commit()
    request.session["uid"] = u.id
    return {"id": u.id, "username": u.username}

@router.post("/api/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_session)):
    u = db.scalar(select(User).where(User.email == body.email))
    if not u or not security.verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    request.session["uid"] = u.id
    return {"id": u.id, "username": u.username}

@router.post("/api/keys")
def mint_key(body: KeyIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    plain, key_hash = security.generate_api_key()
    db.add(ApiKey(user_id=user.id, key_hash=key_hash, label=body.label)); db.commit()
    return {"api_key": plain}  # shown once

@router.get("/api/setups")
def api_list(q: str | None = None, db: Session = Depends(get_session)):
    return setups.list_setups(db, query=q)

@router.get("/api/setups/{slug}")
def api_get(slug: str, db: Session = Depends(get_session)):
    try:
        return setups.preview(db, slug)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")

@router.post("/api/setups")
def api_publish(body: PublishIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    try:
        return setups.publish(db, user, body.title, body.description, body.files, body.slug)
    except bundle.BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except setups.OwnershipError:
        raise HTTPException(status_code=403, detail="slug owned by another user")

@router.get("/api/setups/{slug}/download")
def api_download(slug: str, db: Session = Depends(get_session)):
    from .storage import presign_get
    try:
        res = setups.install(db, slug)  # increments downloads
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")
    s, v = setups._load_latest(db, slug)
    return {"url": presign_get(v.archive_key), "version": res["version"]}

@router.get("/", response_class=HTMLResponse)
def html_feed(request: Request, db: Session = Depends(get_session)):
    return templates.TemplateResponse("feed.html", {"request": request, "setups": setups.list_setups(db)})

@router.get("/s/{slug}", response_class=HTMLResponse)
def html_detail(slug: str, request: Request, db: Session = Depends(get_session)):
    try:
        p = setups.preview(db, slug)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")
    return templates.TemplateResponse("detail.html", {"request": request, "p": p})
