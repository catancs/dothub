from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app import security
# Aliased: the signup/verify handlers bind a local `email` form field, so the
# module is referenced as `mailer` to avoid shadowing. Aliasing keeps
# `app.email.send_verification_email` monkeypatchable (same module object).
from app import email as mailer
from app.config import settings
from app.web._render import render
from app.api import optional_user
from app.validation import validate_signup
from app.ratelimit import limiter

router = APIRouter()


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(optional_user)):
    return render(request, "login.html", {"error": None}, user=user)


@router.post("/login")
@limiter.limit("10/minute")
def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    ident = identifier.strip()
    user = db.scalar(
        select(User).where((User.email == ident) | (User.username == ident))
    )
    if user is None or not security.verify_password(password, user.password_hash):
        resp = render(
            request,
            "login.html",
            {"error": "Those credentials did not match. Please try again."},
        )
        resp.status_code = 401
        return resp
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/signup")
def signup_page(request: Request, user: User | None = Depends(optional_user)):
    return render(request, "signup.html", {"error": None}, user=user)


@router.post("/signup")
@limiter.limit("5/minute")
def signup_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    try:
        validate_signup(username, email, password)
    except ValueError as e:
        resp = render(request, "signup.html", {"error": str(e)})
        resp.status_code = 400
        return resp
    exists = db.scalar(
        select(User).where((User.username == username) | (User.email == email))
    )
    if exists is not None:
        resp = render(
            request,
            "signup.html",
            {"error": "That username or email is already taken."},
        )
        resp.status_code = 400
        return resp
    user = User(
        username=username,
        email=email,
        password_hash=security.hash_password(password),
    )
    token, token_hash = security.generate_verification_token()
    user.verification_token_hash = token_hash
    user.verification_sent_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    request.session["uid"] = user.id
    mailer.send_verification_email(user.email, f"{settings.base_url}/verify/{token}")
    return RedirectResponse("/", status_code=303)


@router.get("/verify/{token}")
def verify_email(
    request: Request,
    token: str,
    db: Session = Depends(get_session),
    user: User | None = Depends(optional_user),
):
    token_hash = security.hash_api_key(token)
    target = db.scalar(
        select(User).where(User.verification_token_hash == token_hash)
    )
    if target is None:
        resp = render(request, "verify_result.html", {"status": "invalid"}, user=user)
        resp.status_code = 404
        return resp
    sent = target.verification_sent_at
    # SQLite returns naive datetimes; normalise to UTC before comparing.
    if sent is not None and sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    if sent is None or datetime.now(timezone.utc) - sent > timedelta(hours=24):
        return render(request, "verify_result.html", {"status": "expired"}, user=user)
    target.email_verified = True
    target.verification_token_hash = None
    target.verification_sent_at = None
    db.commit()
    return render(request, "verify_result.html", {"status": "success"}, user=user)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
