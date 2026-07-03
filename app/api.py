from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_session
from .models import User, ApiKey, Follow
from . import bundle, security, setups
from .validation import validate_signup
from .ratelimit import limiter

router = APIRouter()

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
    agent: str = "claude-code"
    files: dict[str, str]

def _resolve_user(request: Request, db: Session) -> User | None:
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
        return db.get(User, uid)
    return None

def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    u = _resolve_user(request, db)
    if u is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return u

def optional_user(request: Request, db: Session = Depends(get_session)) -> User | None:
    return _resolve_user(request, db)

@router.post("/api/signup")
@limiter.limit("5/minute")
def signup(body: SignupIn, request: Request, db: Session = Depends(get_session)):
    try:
        validate_signup(body.username, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    exists = db.scalar(select(User).where((User.username == body.username) | (User.email == body.email)))
    if exists:
        raise HTTPException(status_code=400, detail="username or email taken")
    u = User(username=body.username, email=body.email,
             password_hash=security.hash_password(body.password))
    db.add(u); db.commit()
    request.session["uid"] = u.id
    return {"id": u.id, "username": u.username}

@router.post("/api/login")
@limiter.limit("10/minute")
def login(body: LoginIn, request: Request, db: Session = Depends(get_session)):
    u = db.scalar(select(User).where(User.email == body.email))
    if not u or not security.verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    request.session["uid"] = u.id
    return {"id": u.id, "username": u.username}

@router.post("/api/keys")
@limiter.limit("5/minute")
def mint_key(body: KeyIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)):
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
        return setups.publish(db, user, body.title, body.description, body.files, body.slug, body.agent)
    except bundle.BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except setups.OwnershipError:
        raise HTTPException(status_code=403, detail="slug owned by another user")

@router.post("/api/setups/{slug}/download")
def api_download(slug: str, user: User = Depends(current_user), db: Session = Depends(get_session)):
    try:
        # increments downloads + records a pull; returns {slug, version, files, effects}
        return setups.install(db, slug, user)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")

class RevertIn(BaseModel):
    version: int

@router.post("/api/setups/{slug}/revert")
def api_revert(slug: str, body: RevertIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    try:
        return setups.revert(db, user, slug, body.version)
    except setups.OwnershipError:
        raise HTTPException(status_code=403, detail="not your setup")
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")

@router.post("/api/follow/{username}")
def api_follow(username: str, user: User = Depends(current_user), db: Session = Depends(get_session)):
    target = db.scalar(select(User).where(User.username == username))
    if not target:
        raise HTTPException(status_code=404, detail="no such user")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="cannot follow yourself")
    exists = db.scalar(select(Follow).where(Follow.follower_id == user.id, Follow.followee_id == target.id))
    if not exists:
        db.add(Follow(follower_id=user.id, followee_id=target.id)); db.commit()
    return {"following": True, "username": username}

@router.delete("/api/follow/{username}")
def api_unfollow(username: str, user: User = Depends(current_user), db: Session = Depends(get_session)):
    target = db.scalar(select(User).where(User.username == username))
    if not target:
        raise HTTPException(status_code=404, detail="no such user")
    f = db.scalar(select(Follow).where(Follow.follower_id == user.id, Follow.followee_id == target.id))
    if f:
        db.delete(f); db.commit()
    return {"following": False, "username": username}

class AccountIn(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    link_github: str | None = None
    link_linkedin: str | None = None
    link_x: str | None = None

@router.post("/api/account")
def api_account(body: AccountIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    for field in ("display_name", "bio", "link_github", "link_linkedin", "link_x"):
        setattr(user, field, getattr(body, field))
    db.commit()
    return {"ok": True}
